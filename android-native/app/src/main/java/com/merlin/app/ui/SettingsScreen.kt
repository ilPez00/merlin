package com.merlin.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.merlin.app.config.ConfigStore
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    configStore: ConfigStore,
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    var apiKey by remember { mutableStateOf("") }
    var wakeWords by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        apiKey = configStore.getApiKey()
        wakeWords = configStore.getWakeWords()
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = Color.Black
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
        ) {
            Spacer(Modifier.height(48.dp))
            Text("SETTINGS", color = Color(0xFF00E5FF), fontSize = 20.sp, letterSpacing = 3.sp)
            Spacer(Modifier.height(24.dp))

            Text("API Key", color = Color(0xFF888888), fontSize = 11.sp)
            Spacer(Modifier.height(4.dp))
            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = PasswordVisualTransformation(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFF00E5FF),
                    unfocusedBorderColor = Color(0xFF333333),
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                )
            )

            Spacer(Modifier.height(16.dp))

            Text("Wake words", color = Color(0xFF888888), fontSize = 11.sp)
            Spacer(Modifier.height(4.dp))
            OutlinedTextField(
                value = wakeWords,
                onValueChange = { wakeWords = it },
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFF00E5FF),
                    unfocusedBorderColor = Color(0xFF333333),
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                )
            )

            Spacer(Modifier.height(24.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = onBack,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFF00E5FF))
                ) {
                    Text("BACK")
                }
                Button(
                    onClick = {
                        scope.launch {
                            configStore.setApiKey(apiKey)
                            configStore.setWakeWords(wakeWords)
                            onBack()
                        }
                    },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00E5FF))
                ) {
                    Text("SAVE", color = Color.Black)
                }
            }
        }
    }
}
