# ClipForge AI v0.5 — Google Flow + bepul AI

## Ishlash sxemasi
1. Ilovaga mavzu, til, davomiylik va formatlarni kiriting.
2. Backend Gemini Developer API orqali ssenariy va Google Flow promptlarini yaratadi.
3. Ilovada Refresh tugmasini bosing, promptlarni ko'ring.
4. Open Google Flow tugmasi bilan Flow saytini oching.
5. Har bir sahna uchun Flow'da video yarating. Har format uchun mos nisbatni tanlang (landscape 16:9, portrait 9:16) va videolarni yuklab oling.
6. Backend `/docs` sahifasida har bir scene/format uchun clip upload qiling. Zarur bo'lsa narration audio faylini ham upload qiling.
7. `POST /v1/jobs/{job_id}/render` ni ishga tushiring.
8. Tayyor MP4'larni `GET /v1/jobs/{job_id}/files/youtube_16_9` yoki `shorts_9_16` orqali yuklab oling.

## Bepul xizmatlar
- Gemini API: Google AI Studio'dan bepul tier mavjud bo'lgan model va API key oling. Free tier limitlari va mavjud modellar hudud/vaqt bo'yicha o'zgaradi.
- Google Flow: Google hisobiga kunlik Flow credits berilishi mumkin; bepul foydalanuvchilar uchun video yaratish peak vaqtida cheklanishi mumkin. Kreditlar model va klip uzunligiga qarab sarflanadi.
- FFmpeg: ochiq manbali, bepul video montaj.
- Voiceover: hozircha foydalanuvchi audio faylni yuklaydi. Keyingi versiyada lokal Kokoro/Piper TTS serverini qo'shish mumkin.

## Server sozlash
`GEMINI_API_KEY` va `API_ACCESS_TOKEN` server environment variables ichiga qo'ying. API keyni APK ichiga yozmang.
Render deployment uchun `render.yaml` va Dockerfile bor. Render server/disk bepul bo'lmasligi mumkin; bu deployment bepul degani emas.
Mahalliy sinov: `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Muhim cheklovlar
- Google Flow avtomatik boshqarilmaydi: promptlarni ilova beradi, foydalanuvchi Flow UI'da video yaratib, kliplarni yuklaydi. Google Flow uchun rasmiy public generation API mavjudligi tasdiqlanmagan; private endpoint, session-cookie scraping yoki CAPTCHA bypass ishlatilmaydi.
- Hozirgi renderer Flow kliplarini 1080p o'lchamga masshtablaydi. Agar Flow'dan tushgan manba 720p/360p bo'lsa, bu haqiqiy native 1080p detal bermaydi.
- Renderer kliplarni kesib, subtitr vaqtlarini taxminan umumiy davomiylik bo'yicha taqsimlaydi. Professional word-level captions uchun Whisper/forced alignment qo'shilishi kerak.
- TTS audio ixtiyoriy yuklanadi; audio bo'lmasa MP4 ovozsiz bo'ladi.
- Bu prototype: production uchun job owner/auth, upload scanning, limits, robust queue, cleanup, logs va backup kerak.
