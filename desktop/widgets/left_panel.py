from textual.widgets import Static
from textual.reactive import reactive
from ai.widgets import MODE_WIDGETS, resolve as resolve_widget


class LeftPanel(Static):
    """Shows webcam status, buffer bar, last heard, and mode context strip."""

    buffer_pct = reactive(0.0)
    last_heard = reactive("")
    webcam_active = reactive(False)
    sudo_ready = reactive(False)
    current_mode = reactive("WORK")
    widget_values = reactive("")

    def on_mount(self):
        self._refresh_widgets()

    def set_mode(self, mode: str):
        self.current_mode = mode
        self._refresh_widgets()

    def _refresh_widgets(self):
        mode = self.current_mode
        widget_ids = MODE_WIDGETS.get(mode, [])
        parts = []
        for wid in widget_ids[:4]:
            val = resolve_widget(wid)
            if val:
                parts.append(val)
        self.widget_values = "   ".join(parts)

    def render(self) -> str:
        mode = self.current_mode
        cam_icon = "📷" if self.webcam_active else "📷"
        mic_icon = "🎤"
        sudo_icon = "🔓" if self.sudo_ready else "🔒"
        bar_len = 16
        filled = int(self.buffer_pct * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        lines = [
            f"{cam_icon} Webcam: {'active' if self.webcam_active else 'inactive'}",
            f"{mic_icon} Buffer [{self.buffer_pct * 100:.0f}%]  {bar}",
        ]
        if self.last_heard:
            heard = self.last_heard[:55]
            lines.append(f'   "{heard}"')
        lines.append(f"{sudo_icon} Sudo: {'ready' if self.sudo_ready else 'needed'}")

        # Context strip
        ctx = self.widget_values
        if ctx:
            lines.append("")
            lines.append(f"── {mode} ──")
            lines.append(ctx)

        return "\n".join(lines)
