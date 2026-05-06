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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetupScreen(
    onContinue: (provider: String, apiKey: String, baseUrl: String) -> Unit
) {
    var provider by remember { mutableStateOf("deepseek") }
    var apiKey by remember { mutableStateOf("") }
    var baseUrl by remember { mutableStateOf("") }
    var showCustomUrl by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = Color.Black
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                "MERLIN",
                color = Color(0xFF00E5FF),
                fontSize = 32.sp,
                letterSpacing = 4.sp
            )
            Text(
                "AI field intelligence",
                color = Color(0xFF888888),
                fontSize = 12.sp,
                modifier = Modifier.padding(bottom = 32.dp)
            )

            // Provider selector
            Text("Provider", color = Color(0xFF888888), fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(4.dp))
            var providerExpanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(
                expanded = providerExpanded,
                onExpandedChange = { providerExpanded = it }
            ) {
                OutlinedTextField(
                    value = provider,
                    onValueChange = {},
                    readOnly = true,
                    modifier = Modifier
                        .menuAnchor()
                        .fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFF00E5FF),
                        unfocusedBorderColor = Color(0xFF333333),
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                    ),
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = providerExpanded) }
                )
                ExposedDropdownMenu(
                    expanded = providerExpanded,
                    onDismissRequest = { providerExpanded = false }
                ) {
                    listOf("deepseek", "openai", "anthropic", "custom").forEach { p ->
                        DropdownMenuItem(
                            text = { Text(p, color = Color.White) },
                            onClick = {
                                provider = p
                                showCustomUrl = p == "custom"
                                providerExpanded = false
                            }
                        )
                    }
                }
            }

            Spacer(Modifier.height(12.dp))

            // Custom URL
            if (showCustomUrl) {
                Text("Base URL", color = Color(0xFF888888), fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(4.dp))
                OutlinedTextField(
                    value = baseUrl,
                    onValueChange = { baseUrl = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("https://api.example.com/v1", color = Color(0xFF444444)) },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFF00E5FF),
                        unfocusedBorderColor = Color(0xFF333333),
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                    )
                )
                Spacer(Modifier.height(12.dp))
            }

            // API Key
            Text("API Key", color = Color(0xFF888888), fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(4.dp))
            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("sk-...", color = Color(0xFF444444)) },
                visualTransformation = PasswordVisualTransformation(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFF00E5FF),
                    unfocusedBorderColor = Color(0xFF333333),
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                )
            )

            Spacer(Modifier.height(8.dp))

            if (error.isNotEmpty()) {
                Text(error, color = Color(0xFFEF4444), fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
            }

            Button(
                onClick = {
                    if (apiKey.isBlank()) {
                        error = "Enter an API key"
                    } else {
                        onContinue(provider, apiKey, baseUrl)
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00E5FF))
            ) {
                Text("CONTINUE", color = Color.Black, fontSize = 14.sp, letterSpacing = 2.sp)
            }
        }
    }
}
