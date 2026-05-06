package com.merlin.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.ImageCapture
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.merlin.app.agent.ApiClient
import com.merlin.app.agent.WhisperClient
import com.merlin.app.audio.AudioCapture
import com.merlin.app.camera.CameraPreview
import com.merlin.app.camera.FrameCapture
import com.merlin.app.config.ConfigStore
import kotlinx.coroutines.launch

@Composable
fun VisorScreen(
    configStore: ConfigStore,
    onOpenSettings: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val accentColor = remember { mutableStateOf(Color(0xFF00E5FF)) }
    val selectedMode = remember { mutableStateOf("SCOUT") }
    val chatHistory = remember { mutableStateListOf<String>() }
    val isListening = remember { mutableStateOf(false) }

    // Clients
    var apiClient by remember { mutableStateOf<ApiClient?>(null) }
    var whisperClient by remember { mutableStateOf<WhisperClient?>(null) }
    val audioCapture = remember { AudioCapture() }

    // Permission launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {}

    // Init clients
    LaunchedEffect(Unit) {
        val apiKey = configStore.getApiKey()
        val provider = configStore.getProvider()
        val baseUrl = configStore.getApiEndpoint(provider, configStore.getBaseUrl())
        apiClient = ApiClient(apiKey, baseUrl)
        whisperClient = WhisperClient(apiKey, baseUrl)
    }

    // Request permissions
    LaunchedEffect(Unit) {
        val permissions = arrayOf(
            Manifest.permission.CAMERA,
            Manifest.permission.RECORD_AUDIO,
        )
        val allGranted = permissions.all {
            ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
        }
        if (!allGranted) {
            permissionLauncher.launch(permissions)
        }
    }

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        // Camera (full screen)
        CameraPreview(
            modifier = Modifier.fillMaxSize(),
            onTap = {
                scope.launch {
                    val key = configStore.getApiKey()
                    val text = "What do you see?"
                    chatHistory.add(0, "📷 Observing...")
                    val result = apiClient?.chat(text, mode = selectedMode.value)
                    chatHistory[0] = result?.text ?: "Error: ${result?.error}"
                }
            }
        )

        // Scanline overlay
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = Color(0x0800E5FF)
        ) {}

        // UI overlay
        Column(
            modifier = Modifier.fillMaxSize()
        ) {
            // Spacer for camera
            Spacer(Modifier.weight(1f))

            // Chat bubbles
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                verticalArrangement = Arrangement.Bottom
            ) {
                chatHistory.take(3).forEach { msg ->
                    ChatBubble(
                        text = msg,
                        accentColor = accentColor.value,
                        onDismiss = { chatHistory.remove(msg) }
                    )
                }
            }

            // Query bar
            QueryBar(
                onSend = { query ->
                    scope.launch {
                        chatHistory.add(0, "You: $query")
                        val result = apiClient?.chat(query, mode = selectedMode.value)
                        chatHistory[0] = result?.text ?: "Error: ${result?.error}"
                    }
                },
                onMicPress = {
                    scope.launch {
                        isListening.value = true
                        chatHistory.add(0, "🎤 Listening...")
                        val audio = audioCapture.capture(5000)
                        if (audio.isNotEmpty()) {
                            val text = whisperClient?.transcribe(audio) ?: ""
                            if (text.isNotBlank()) {
                                chatHistory[0] = "You: $text"
                                val result = apiClient?.chat(text, mode = selectedMode.value)
                                chatHistory[0] = result?.text ?: "Error: ${result?.error}"
                            } else {
                                chatHistory[0] = "❌ No speech detected"
                            }
                        }
                        isListening.value = false
                    }
                },
                isListening = isListening.value
            )

            // Mode selector
            ModeSelector(
                selectedMode = selectedMode.value,
                onModeSelected = { mode ->
                    selectedMode.value = mode
                    ACTIVITY_MODES.find { it.name == mode }?.let {
                        accentColor.value = it.color
                    }
                    scope.launch { configStore.setActivityMode(mode) }
                }
            )
        }

        // Settings button (top-right)
        TextButton(
            onClick = onOpenSettings,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(top = 48.dp, end = 8.dp)
        ) {
            Text("⚙", color = Color(0xFF888888), fontSize = 18.sp)
        }

        // Mode indicator (top-left)
        Surface(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(top = 48.dp, start = 12.dp),
            color = accentColor.value.copy(alpha = 0.2f),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(4.dp)
        ) {
            Text(
                selectedMode.value,
                color = accentColor.value,
                fontSize = 11.sp,
                letterSpacing = 2.sp,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
            )
        }
    }
}
