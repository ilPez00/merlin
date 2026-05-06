package com.merlin.app.agent

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ApiClient(private val apiKey: String, private val baseUrl: String) {

    companion object {
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    data class ChatResult(val text: String, val error: String? = null)

    suspend fun chat(text: String, frameB64: String? = null, mode: String = "SCOUT"): ChatResult {
        val url = "$baseUrl/chat/completions"
        val body = buildJsonBody(text, frameB64, mode)

        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $apiKey")
            .header("Content-Type", "application/json")
            .post(body.toRequestBody(JSON_MEDIA))
            .build()

        return try {
            val response = kotlinx.coroutines.Dispatchers.IO.let { dispatcher ->
                kotlinx.coroutines.withContext(dispatcher) {
                    client.newCall(request).execute()
                }
            }
            val responseBody = response.body?.string() ?: ""
            if (!response.isSuccessful) {
                return ChatResult("", error = "API ${response.code}: ${responseBody.take(200)}")
            }

            val json = JSONObject(responseBody)
            val choices = json.optJSONArray("choices")
            if (choices != null && choices.length() > 0) {
                val message = choices.getJSONObject(0).optJSONObject("message")
                val content = message?.optString("content", "") ?: ""
                ChatResult(text = content)
            } else {
                ChatResult("", error = "No response choices")
            }
        } catch (e: Exception) {
            ChatResult("", error = e.message ?: "Network error")
        }
    }

    private fun buildJsonBody(text: String, frameB64: String?, mode: String): String {
        val messages = JSONArray()

        // System prompt
        messages.put(JSONObject().apply {
            put("role", "system")
            put("content", "You are Merlin, an AI field assistant. Be concise, grounded in context. Current mode: $mode.")
        })

        // User message with optional vision
        val userContent = if (frameB64 != null) {
            JSONArray().apply {
                put(JSONObject().apply {
                    put("type", "image_url")
                    put("image_url", JSONObject().apply {
                        put("url", "data:image/jpeg;base64,$frameB64")
                        put("detail", "low")
                    })
                })
                put(JSONObject().apply {
                    put("type", "text")
                    put("text", text)
                })
            }
        } else {
            text
        }

        messages.put(JSONObject().apply {
            put("role", "user")
            put("content", userContent)
        })

        val model = when {
            baseUrl.contains("deepseek") -> "deepseek-chat"
            baseUrl.contains("openai") -> "gpt-4o"
            else -> "deepseek-chat"
        }

        return JSONObject().apply {
            put("model", model)
            put("messages", messages)
            put("max_tokens", 2048)
            put("temperature", 0.7)
            put("stream", false)
        }.toString()
    }
}
