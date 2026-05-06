package com.merlin.app.agent

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class WhisperClient(private val apiKey: String, private val baseUrl: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    suspend fun transcribe(audioBytes: ByteArray): String {
        // Use OpenAI Whisper API (works with any OpenAI-compat key)
        val url = when {
            baseUrl.contains("openai") -> "https://api.openai.com/v1/audio/transcriptions"
            baseUrl.contains("deepseek") -> "https://api.deepseek.com/v1/audio/transcriptions"
            else -> "https://api.openai.com/v1/audio/transcriptions"
        }

        return try {
            val audioBody = audioBytes.toRequestBody("audio/wav".toMediaType())
            val body = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("model", "whisper-1")
                .addFormDataPart("file", "audio.wav", audioBody)
                .addFormDataPart("response_format", "json")
                .build()

            val request = Request.Builder()
                .url(url)
                .header("Authorization", "Bearer $apiKey")
                .post(body)
                .build()

            val response = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                client.newCall(request).execute()
            }
            val responseBody = response.body?.string() ?: "{}"
            if (!response.isSuccessful) return ""

            JSONObject(responseBody).optString("text", "")
        } catch (e: Exception) {
            ""
        }
    }
}
