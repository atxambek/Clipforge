package ai.clipforge.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private val Ink = Color(0xFF101426)
private val Panel = Color(0xFF1A2138)
private val Purple = Color(0xFF8B5CF6)
private val Cyan = Color(0xFF22D3EE)
private val Muted = Color(0xFF9AA6C3)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ClipForgeFreeApp() }
    }
}

private fun apiCall(base: String, token: String, path: String, method: String, body: JSONObject? = null): JSONObject {
    val conn = (URL(base.trim().removeSuffix("/") + path).openConnection() as HttpURLConnection).apply {
        requestMethod = method
        connectTimeout = 20000
        readTimeout = 120000
        setRequestProperty("Accept", "application/json")
        if (token.isNotBlank()) setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
    }
    try {
        if (body != null) conn.outputStream.use { it.write(body.toString().toByteArray()) }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val raw = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (code !in 200..299) throw IllegalStateException(runCatching { JSONObject(raw).optString("detail") }.getOrNull() ?: "HTTP $code")
        return JSONObject(raw)
    } finally { conn.disconnect() }
}

@Composable
fun ClipForgeFreeApp() {
    val context = LocalContext.current
    var topic by remember { mutableStateOf("") }
    var duration by remember { mutableStateOf("60 seconds") }
    var language by remember { mutableStateOf("English") }
    var formats by remember { mutableStateOf(setOf("YouTube 16:9", "Shorts 9:16")) }
    var server by remember { mutableStateOf("https://YOUR-SERVER-DOMAIN") }
    var token by remember { mutableStateOf("") }
    var jobId by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("Not started") }
    var message by remember { mutableStateOf("Gemini free tier + Google Flow free credits + FFmpeg.") }
    var prompts by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun durationSeconds() = when(duration) {
        "30 seconds" -> 30; "60 seconds" -> 60; "90 seconds" -> 90
        "3 minutes" -> 180; "5 minutes" -> 300; "10 minutes" -> 600
        else -> 60
    }
    fun formatCodes() = formats.mapNotNull {
        when(it) { "YouTube 16:9" -> "youtube_16_9"; "Shorts 9:16" -> "shorts_9_16"; else -> null }
    }

    MaterialTheme(colorScheme = darkColorScheme(background = Ink, surface = Panel, primary = Purple)) {
        Surface(Modifier.fillMaxSize(), color = Ink) {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(15.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(44.dp).background(Brush.linearGradient(listOf(Purple, Cyan)), RoundedCornerShape(13.dp)),
                        contentAlignment = Alignment.Center) { Icon(Icons.Default.Movie, null, tint = Color.White) }
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text("CLIPFORGE AI", fontWeight = FontWeight.Black, fontSize = 20.sp, color = Color.White)
                        Text("FLOW + FREE AI WORKFLOW", color = Muted, fontSize = 10.sp)
                    }
                }
                Text("Create videos with free tools", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Bold)
                Text("Gemini prepares the script and Flow prompts. You generate clips in Google Flow, then upload them for editing.", color = Muted, fontSize = 13.sp)

                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Tag("VIDEO TOPIC")
                        OutlinedTextField(topic, { topic = it }, modifier = Modifier.fillMaxWidth(),
                            minLines = 2, placeholder = { Text("Masalan: Why do we dream?") })
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Column(Modifier.weight(1f)) {
                                Tag("DURATION")
                                var open by remember { mutableStateOf(false) }
                                Box {
                                    OutlinedButton({ open = true }, Modifier.fillMaxWidth()) { Text(duration, fontSize = 11.sp) }
                                    DropdownMenu(open, { open = false }) {
                                        listOf("30 seconds","60 seconds","90 seconds","3 minutes","5 minutes","10 minutes").forEach {
                                            DropdownMenuItem(text = { Text(it) }, onClick = { duration = it; open = false })
                                        }
                                    }
                                }
                            }
                            Column(Modifier.weight(1f)) {
                                Tag("LANGUAGE")
                                var open by remember { mutableStateOf(false) }
                                Box {
                                    OutlinedButton({ open = true }, Modifier.fillMaxWidth()) { Text(language, fontSize = 11.sp) }
                                    DropdownMenu(open, { open = false }) {
                                        listOf("English","Uzbek","Russian","Spanish","French","German","Hindi").forEach {
                                            DropdownMenuItem(text = { Text(it) }, onClick = { language = it; open = false })
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(14.dp)) {
                        Tag("OUTPUT")
                        listOf("YouTube 16:9", "Shorts 9:16").forEach { item ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(item in formats, { checked ->
                                    formats = if (checked) formats + item else formats - item
                                })
                                Text(item, color = Color.White)
                                Spacer(Modifier.weight(1f))
                                Text("1080p export", color = Cyan, fontSize = 11.sp)
                            }
                        }
                    }
                }
                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Tag("BACKEND")
                        OutlinedTextField(server, { server = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("HTTPS server URL") })
                        OutlinedTextField(token, { token = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("Access token") })
                    }
                }
                Button(onClick = {
                    busy = true; message = "Gemini is preparing the script and Flow prompts…"; prompts = ""
                    scope.launch {
                        try {
                            val body = JSONObject().put("topic", topic.trim())
                                .put("language", language).put("duration_seconds", durationSeconds())
                                .put("formats", org.json.JSONArray(formatCodes())).put("resolution", "1080p")
                            val result = withContext(Dispatchers.IO) { apiCall(server, token, "/v1/jobs", "POST", body) }
                            jobId = result.optString("id")
                            status = result.optString("status")
                            message = result.optString("message")
                        } catch (e: Exception) { message = e.message ?: "Connection error" }
                        finally { busy = false }
                    }
                }, enabled = topic.isNotBlank() && formats.isNotEmpty() && !busy,
                    modifier = Modifier.fillMaxWidth().height(54.dp), colors = ButtonDefaults.buttonColors(containerColor = Purple)) {
                    if (busy) CircularProgressIndicator(Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
                    else Icon(Icons.Default.AutoAwesome, null)
                    Spacer(Modifier.width(7.dp)); Text("GENERATE SCRIPT & FLOW PROMPTS", fontWeight = FontWeight.Bold)
                }

                if (jobId.isNotBlank()) {
                    Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("JOB: $jobId", color = Cyan, fontSize = 11.sp)
                            Text("Status: $status", color = Color.White, fontWeight = FontWeight.Bold)
                            Text(message, color = Muted, fontSize = 12.sp)
                            OutlinedButton(onClick = {
                                busy = true
                                scope.launch {
                                    try {
                                        val result = withContext(Dispatchers.IO) { apiCall(server, token, "/v1/jobs/$jobId", "GET") }
                                        status = result.optString("status")
                                        message = result.optString("message")
                                        val scenes = result.optJSONArray("scenes")
                                        if (scenes != null) {
                                            prompts = (0 until scenes.length()).joinToString("\\n\\n") { i ->
                                                val s = scenes.getJSONObject(i)
                                                "SCENE ${s.optInt("scene_number")}\\n${s.optString("flow_prompt")}"
                                            }
                                        }
                                    } catch (e: Exception) { message = e.message ?: "Refresh error" }
                                    finally { busy = false }
                                }
                            }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                                Icon(Icons.Default.Refresh, null); Text("REFRESH & LOAD FLOW PROMPTS")
                            }
                            OutlinedButton(onClick = {
                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://labs.google/fx/tools/flow")))
                            }, modifier = Modifier.fillMaxWidth()) {
                                Icon(Icons.Default.OpenInNew, null); Text("OPEN GOOGLE FLOW")
                            }
                        }
                    }
                }
                if (prompts.isNotBlank()) {
                    Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Tag("COPY PROMPTS INTO GOOGLE FLOW")
                            Text(prompts, color = Color.White, fontSize = 12.sp)
                        }
                    }
                }
                Text("Workflow: Gemini script → Google Flow clips → upload clips → FFmpeg edit → MP4.", color = Muted, fontSize = 11.sp)
                Text("Google Flow generation is manual in this version; no private API, cookie scraping or CAPTCHA bypass.", color = Cyan, fontSize = 10.sp)
            }
        }
    }
}

@Composable private fun Tag(s: String) {
    Text(s, color = Cyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
}
