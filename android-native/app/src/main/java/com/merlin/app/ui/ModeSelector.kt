package com.merlin.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class ActivityMode(
    val name: String,
    val color: Color,
    val label: String
)

val ACTIVITY_MODES = listOf(
    ActivityMode("SCOUT", Color(0xFF00E5FF), "SCOUT"),
    ActivityMode("WORK", Color(0xFF4A6FA5), "WORK"),
    ActivityMode("LIFT", Color(0xFFEF4444), "LIFT"),
    ActivityMode("WALK", Color(0xFF4ADE80), "WALK"),
    ActivityMode("TALK", Color(0xFFE11D48), "TALK"),
    ActivityMode("NOTES", Color(0xFFF59E0B), "NOTES"),
    ActivityMode("DRIVE", Color(0xFF10B981), "DRIVE"),
    ActivityMode("SKI", Color(0xFF38BDF8), "SKI"),
    ActivityMode("RECON", Color(0xFF546E7A), "RECON"),
)

@Composable
fun ModeSelector(
    selectedMode: String,
    onModeSelected: (String) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 8.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        ACTIVITY_MODES.forEach { mode ->
            val isSelected = mode.name == selectedMode
            TextButton(
                onClick = { onModeSelected(mode.name) },
                colors = ButtonDefaults.textButtonColors(
                    contentColor = if (isSelected) mode.color else Color(0xFF555555)
                ),
                modifier = Modifier.height(32.dp)
            ) {
                Text(
                    mode.label,
                    fontSize = 10.sp,
                    letterSpacing = 1.sp,
                    color = if (isSelected) mode.color else Color(0xFF555555)
                )
            }
        }
    }
}
