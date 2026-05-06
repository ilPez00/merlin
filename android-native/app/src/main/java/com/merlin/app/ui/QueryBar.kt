package com.merlin.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun QueryBar(
    onSend: (String) -> Unit,
    onMicPress: () -> Unit,
    isListening: Boolean = false
) {
    var text by remember { mutableStateOf("") }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            modifier = Modifier.weight(1f).height(44.dp),
            placeholder = { Text("Ask Merlin…", color = Color(0xFF444444), fontSize = 13.sp) },
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFF00E5FF),
                unfocusedBorderColor = Color(0xFF333333),
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White,
                cursorColor = Color(0xFF00E5FF)
            ),
            shape = RoundedCornerShape(8.dp),
            singleLine = true
        )

        // Mic button
        FilledTonalButton(
            onClick = onMicPress,
            modifier = Modifier.size(44.dp),
            colors = ButtonDefaults.filledTonalButtonColors(
                containerColor = if (isListening) Color(0xFF00E5FF) else Color(0xFF1A1A1A)
            ),
            shape = RoundedCornerShape(8.dp)
        ) {
            Text(if (isListening) "🔴" else "🎤", fontSize = 16.sp)
        }

        // Send button
        FilledTonalButton(
            onClick = {
                if (text.isNotBlank()) {
                    onSend(text.trim())
                    text = ""
                }
            },
            modifier = Modifier.size(44.dp),
            colors = ButtonDefaults.filledTonalButtonColors(
                containerColor = Color(0xFF00E5FF)
            ),
            shape = RoundedCornerShape(8.dp)
        ) {
            Text("▶", color = Color.Black, fontSize = 14.sp)
        }
    }
}
