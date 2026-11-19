from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DB = os.getenv("DATABASE_PATH", "./clipforge.db")
ARTIFACTS = Path(os.getenv("ARTIFACTS_DIR", "./artifacts"))
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
app = FastAPI(title="ClipForge AI — Flow + Free Tools", version="0.5.0")

STAGES = ["plan_ready", "flow_clips", "voiceover", "render", "complete"]

class CreateJob(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    language: str = Field(default="English", max_length=30)
    duration_seconds: int = Field(default=60, ge=15, le=600)
    formats: list[str] = Field(default_factory=lambda: ["youtube_16_9", "shorts_9_16"])
    resolution: str = "1080p"

def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c

def stamp():
    return datetime.now(timezone.utc).isoformat()

@app.on_event("startup")
def startup():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, topic TEXT, language TEXT, duration_seconds INTEGER,
            formats TEXT, resolution TEXT, status TEXT, progress INTEGER,
            message TEXT, plan TEXT, created_at TEXT, updated_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS uploads (
            job_id TEXT, scene_number INTEGER, format_name TEXT, filename TEXT,
            PRIMARY KEY(job_id,scene_number,format_name)
        )""")

def auth(authorization: str | None = Header(default=None)):
    expected = os.getenv("API_ACCESS_TOKEN", "").strip()
    if not expected:
        if os.getenv("APP_ENV", "development") == "production":
            raise HTTPException(503, "Set API_ACCESS_TOKEN on the server.")
        return
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if supplied != expected:
        raise HTTPException(401, "Invalid access token.")

def gemini_generate(prompt: str) -> str:
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing. Create a free Gemini API key in Google AI Studio and add it to the server.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
    }
    req = Request(url, data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=180) as response:
            data = json.loads(response.read())
    except HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:1200]
        raise RuntimeError(f"Gemini API HTTP {e.code}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"Gemini connection failed: {e}") from e
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini did not return a usable text response.")

def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    return json.loads(text)

def build_plan(job: dict) -> dict:
    n = max(4, min(16, round(job["duration_seconds"] / 7)))
    prompt = f"""
Act as a careful YouTube documentary writer and film storyboard director.
Topic: {job['topic']}
Output narration language: {job['language']}
Target runtime: {job['duration_seconds']} seconds.
Create exactly {n} sequential scenes. Return ONLY valid JSON:
{{
 "title":"SEO title",
 "description":"short video description",
 "tags":["tag1","tag2"],
 "narration":"complete voiceover narration in the requested language",
 "style_bible":"consistent art direction and palette",
 "character_bible":"consistent main character appearance, clothing and proportions; or say no recurring character",
 "scenes":[
   {{"scene_number":1,"narration":"spoken sentence(s) for this scene",
     "flow_prompt":"Google Flow prompt in clear English. Describe the exact visual action, camera framing/movement, lighting, continuity details, aspect ratio agnostic composition, 5-8 second clip. No text, logos or subtitles."}}
 ]
}}
Make it factual and avoid invented statistics. Strong hook in scene 1. Each scene should continue directly from the previous one. Use one consistent character bible and repeat key character details in every relevant flow_prompt. Prompts should work in Google Flow Text-to-Video or Frames-to-Video.
"""
    plan = parse_json(gemini_generate(prompt))
    if not isinstance(plan.get("scenes"), list) or not plan["scenes"]:
        raise RuntimeError("Gemini response did not contain scenes.")
    if len(plan["scenes"]) > 20:
        plan["scenes"] = plan["scenes"][:20]
    return plan

def row_dict(row):
    d = dict(row)
    d["formats"] = json.loads(d["formats"])
    d["plan"] = json.loads(d["plan"]) if d["plan"] else None
    return d

@app.get("/health")
def health():
    return {"ok": True, "service": "clipforge-flow-free", "version": "0.5.0"}

@app.post("/v1/jobs", status_code=202)
def create_job(payload: CreateJob, background: BackgroundTasks, _=Depends(auth)):
    allowed = {"youtube_16_9", "shorts_9_16"}
    formats = [x for x in payload.formats if x in allowed]
    if not formats:
        raise HTTPException(400, "Select at least one output format.")
    job_id = str(uuid.uuid4())
    with conn() as c:
        c.execute("""INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (job_id, payload.topic.strip(), payload.language, payload.duration_seconds,
                   json.dumps(formats), "1080p", "planning", 5,
                   "Gemini is writing the script and Google Flow prompts.", None, stamp(), stamp()))
    background.add_task(make_plan_task, job_id)
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return row_dict(row)

def make_plan_task(job_id: str):
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return
    try:
        plan = build_plan(dict(row))
        with conn() as c:
            c.execute("UPDATE jobs SET plan=?,status='plan_ready',progress=15,message=?,updated_at=? WHERE id=?",
                      (json.dumps(plan, ensure_ascii=False), "Flow prompts are ready. Generate the clips in Google Flow and upload them.", stamp(), job_id))
    except Exception as e:
        with conn() as c:
            c.execute("UPDATE jobs SET status='failed',message=?,updated_at=? WHERE id=?",
                      (str(e)[:2000], stamp(), job_id))

@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, _=Depends(auth)):
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    result = row_dict(row)
    if result["plan"]:
        result["scenes"] = result["plan"].get("scenes", [])
        result["narration"] = result["plan"].get("narration", "")
        result["seo"] = {k: result["plan"].get(k) for k in ("title","description","tags")}
    with conn() as c:
        uploaded = c.execute("SELECT scene_number,format_name FROM uploads WHERE job_id=? ORDER BY scene_number",
                             (job_id,)).fetchall()
    result["uploaded_clips"] = [dict(x) for x in uploaded]
    return result

@app.post("/v1/jobs/{job_id}/clips/{scene_number}/{format_name}")
async def upload_clip(job_id: str, scene_number: int, format_name: str,
                      file: UploadFile = File(...), _=Depends(auth)):
    if format_name not in ("youtube_16_9", "shorts_9_16"):
        raise HTTPException(400, "format_name must be youtube_16_9 or shorts_9_16.")
    with conn() as c:
        row = c.execute("SELECT plan FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    plan = json.loads(row["plan"] or "{}")
    scenes = plan.get("scenes", [])
    if scene_number < 1 or scene_number > len(scenes):
        raise HTTPException(400, "Scene number is outside this storyboard.")
    if not (file.filename or "").lower().endswith((".mp4", ".mov", ".webm", ".m4v")):
        raise HTTPException(400, "Upload an MP4, MOV, WEBM or M4V clip.")
    data = await file.read()
    if len(data) > 250 * 1024 * 1024:
        raise HTTPException(413, "Each clip must be under 250 MB.")
    folder = ARTIFACTS / job_id / "clips"
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix.lower()
    target = folder / f"scene_{scene_number:02}_{format_name}{suffix}"
    target.write_bytes(data)
    with conn() as c:
        c.execute("""INSERT INTO uploads(job_id,scene_number,format_name,filename)
            VALUES(?,?,?,?) ON CONFLICT(job_id,scene_number,format_name)
            DO UPDATE SET filename=excluded.filename""",
            (job_id, scene_number, format_name, target.name))
        c.execute("UPDATE jobs SET status='clips_uploading',progress=25,message=?,updated_at=? WHERE id=?",
                  (f"Uploaded scene {scene_number} ({format_name}).", stamp(), job_id))
    return {"ok": True, "scene_number": scene_number, "format": format_name, "filename": target.name}

@app.post("/v1/jobs/{job_id}/voiceover")
async def upload_voiceover(job_id: str, file: UploadFile = File(...), _=Depends(auth)):
    with conn() as c:
        row = c.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
        raise HTTPException(400, "Upload MP3, WAV, M4A, AAC or OGG audio.")
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(413, "Audio file must be under 100 MB.")
    folder = ARTIFACTS / job_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"voiceover{suffix}").write_bytes(data)
    return {"ok": True, "filename": f"voiceover{suffix}"}

def run_cmd(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=2400)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])

def make_srt(plan, duration, target):
    scenes = plan["scenes"]
    weights = [max(1, len(str(s.get("narration","")).split())) for s in scenes]
    total = sum(weights)
    def ts(sec):
        ms = int(sec * 1000)
        h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    cursor = 0.0
    lines = []
    for i, (scene, weight) in enumerate(zip(scenes, weights), 1):
        end = duration if i == len(scenes) else cursor + duration * weight / total
        lines.extend([str(i), f"{ts(cursor)} --> {ts(end)}", scene.get("narration",""), ""])
        cursor = end
    target.write_text("\n".join(lines), encoding="utf-8")

def render_format(job_id, fmt, plan, clips, audio, out):
    folder = out.parent
    concat = folder / f"{fmt}_concat.txt"
    # Use exact uploaded Flow clips in scene order; FFmpeg concat demuxer expects compatible streams.
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in clips), encoding="utf-8")
    srt = folder / "captions.srt"
    # Normalize source clips to 25fps and requested frame size while concatenating via filter graph.
    width, height = (1920,1080) if fmt == "youtube_16_9" else (1080,1920)
    inputs = []
    for p in clips:
        inputs += ["-i", str(p)]
    filter_parts = []
    labels = []
    for i in range(len(clips)):
        label = f"v{i}"
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps=25,format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filter_parts.append("".join(labels) + f"concat=n={len(clips)}:v=1:a=0[vconcat]")
    srt_path = (ARTIFACTS / job_id / "captions.srt").as_posix()
    srt_path = srt_path.replace(":", r"\\:").replace("'", r"\\'")
    font_size = 42 if fmt == "shorts_9_16" else 34
    filter_parts.append(
        f"[vconcat]subtitles='{srt_path}':force_style='FontName=DejaVu Sans,"
        f"FontSize={font_size},Outline=2,Shadow=1,MarginV=55'[vout]"
    )
    args = [FFMPEG, "-y"] + inputs
    if audio:
        args += ["-i", str(audio)]
    args += ["-filter_complex", ";".join(filter_parts), "-map", "[vout]"]
    if audio:
        args += ["-map", f"{len(clips)}:a:0"]
    args += ["-c:v","libx264","-preset","veryfast","-crf","21"]
    if audio:
        args += ["-c:a","aac","-b:a","160k","-shortest"]
    args += ["-movflags","+faststart",str(out)]
    run_cmd(args)

@app.post("/v1/jobs/{job_id}/render")
def render(job_id: str, _=Depends(auth)):
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        uploads = c.execute("SELECT * FROM uploads WHERE job_id=?", (job_id,)).fetchall()
    if not row:
        raise HTTPException(404, "Job not found.")
    job = dict(row)
    plan = json.loads(job["plan"] or "{}")
    scenes = plan.get("scenes", [])
    if not scenes:
        raise HTTPException(409, "Wait until the Gemini storyboard is ready.")
    upload_map = {(x["scene_number"], x["format_name"]): x["filename"] for x in uploads}
    folder = ARTIFACTS / job_id
    formats = json.loads(job["formats"])
    for fmt in formats:
        missing = [i for i in range(1, len(scenes)+1) if (i,fmt) not in upload_map]
        if missing:
            raise HTTPException(409, f"Missing {fmt} clips for scenes: {missing}")
    audio_candidates = [folder / f"voiceover{x}" for x in (".mp3",".wav",".m4a",".aac",".ogg")]
    audio = next((x for x in audio_candidates if x.exists()), None)
    duration = int(job["duration_seconds"])
    # If no narration audio is uploaded, render silent clips with scene captions as a subtitle track.
    # This avoids claiming a generated voice when none was provided.
    outputs = {}
    srt = folder / "captions.srt"
    make_srt(plan, duration, srt)
    for fmt in formats:
        clips = [folder / "clips" / upload_map[(i,fmt)] for i in range(1, len(scenes)+1)]
        out = folder / ("clipforge_youtube_16_9_1080p.mp4" if fmt == "youtube_16_9" else "clipforge_shorts_9_16_1080p.mp4")
        try:
            render_format(job_id, fmt, plan, clips, audio, out)
        except Exception as e:
            raise HTTPException(500, f"FFmpeg render failed: {str(e)[:1000]}")
        outputs[fmt] = f"/v1/jobs/{job_id}/files/{fmt}"
    (folder / "seo.json").write_text(json.dumps({k:plan.get(k) for k in ("title","description","tags")}, ensure_ascii=False, indent=2))
    outputs["seo"] = f"/v1/jobs/{job_id}/files/seo"
    with conn() as c:
        c.execute("UPDATE jobs SET status='completed',progress=100,message=?,updated_at=? WHERE id=?",
                  ("1080p MP4 exports are ready." if audio else "1080p MP4 exports are ready (without voiceover audio).", stamp(), job_id))
    return {"ok": True, "status": "completed", "outputs": outputs, "audio_included": bool(audio)}

@app.get("/v1/jobs/{job_id}/files/{kind}")
def download(job_id: str, kind: str, _=Depends(auth)):
    names = {"youtube_16_9":"clipforge_youtube_16_9_1080p.mp4",
             "shorts_9_16":"clipforge_shorts_9_16_1080p.mp4", "seo":"seo.json"}
    if kind not in names:
        raise HTTPException(404, "Unknown output.")
    path = ARTIFACTS / job_id / names[kind]
    if not path.is_file():
        raise HTTPException(404, "Output is not ready.")
    return FileResponse(path, filename=path.name)

@app.get("/v1/jobs/{job_id}/flow-guide")
def flow_guide(job_id: str, _=Depends(auth)):
    with conn() as c:
        row = c.execute("SELECT plan,formats FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    plan = json.loads(row["plan"] or "{}")
    if not plan:
        raise HTTPException(409, "Storyboard is not ready yet.")
    return {
        "instructions": "Generate each scene manually in Google Flow using the prompt. Download each clip, then upload it with the matching scene number and format. Use only the Google Flow UI; this app does not automate private endpoints or account sessions.",
        "flow_url": "https://labs.google/fx/tools/flow",
        "formats": json.loads(row["formats"]),
        "scenes": plan.get("scenes", [])
    }
