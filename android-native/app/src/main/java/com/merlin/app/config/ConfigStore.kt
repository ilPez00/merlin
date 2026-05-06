package com.merlin.app.config

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("merlin_config")

class ConfigStore(private val context: Context) {

    companion object {
        private val KEY_API_KEY = stringPreferencesKey("api_key")
        private val KEY_PROVIDER = stringPreferencesKey("provider")
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_ACTIVITY_MODE = stringPreferencesKey("activity_mode")
        private val KEY_WAKE_WORDS = stringPreferencesKey("wake_words")
    }

    suspend fun getApiKey(): String = context.dataStore.data.map { it[KEY_API_KEY] ?: "" }.first()
    suspend fun setApiKey(key: String) { context.dataStore.edit { it[KEY_API_KEY] = key } }

    suspend fun getProvider(): String = context.dataStore.data.map { it[KEY_PROVIDER] ?: "deepseek" }.first()
    suspend fun setProvider(p: String) { context.dataStore.edit { it[KEY_PROVIDER] = p } }

    suspend fun getBaseUrl(): String = context.dataStore.data.map { it[KEY_BASE_URL] ?: "" }.first()
    suspend fun setBaseUrl(url: String) { context.dataStore.edit { it[KEY_BASE_URL] = url } }

    suspend fun getActivityMode(): String = context.dataStore.data.map { it[KEY_ACTIVITY_MODE] ?: "SCOUT" }.first()
    suspend fun setActivityMode(m: String) { context.dataStore.edit { it[KEY_ACTIVITY_MODE] = m } }

    suspend fun getWakeWords(): String = context.dataStore.data.map { it[KEY_WAKE_WORDS] ?: "marlin,merlino,merlin" }.first()
    suspend fun setWakeWords(w: String) { context.dataStore.edit { it[KEY_WAKE_WORDS] = w } }

    fun getApiEndpoint(provider: String, baseUrl: String): String {
        if (provider == "custom" && baseUrl.isNotBlank()) return baseUrl
        return when (provider) {
            "deepseek" -> "https://api.deepseek.com/v1"
            "openai" -> "https://api.openai.com/v1"
            "anthropic" -> "https://api.anthropic.com/v1"
            else -> "https://api.deepseek.com/v1"
        }
    }
}
