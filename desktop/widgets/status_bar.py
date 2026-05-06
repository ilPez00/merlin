from textual.widgets import Static
from textual.reactive import reactive


class StatusBar(Static):
    """Top bar: mode, connection, icons."""

    mode = reactive("WORK")
    listening = reactive(False)
    indicators = reactive("")

    def render(self) -> str:
        ico = []
        if self.listening:
            ico.append("🎤")
        ico.append("📷")
        ico.append("🔓")
        ico_str = " ".join(ico)
        return f" MERLIN    {self.mode}    {'● Listening' if self.listening else '○ Idle'}    {ico_str}"
