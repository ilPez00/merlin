from textual.widgets import Static
from textual.reactive import reactive


class ChatView(Static):
    """Scrollable conversation display."""

    lines = reactive("")

    def add_message(self, role: str, text: str, timestamp: str = ""):
        ts = f" [{timestamp}]" if timestamp else ""
        prefix = "Merlin:" if role == "assistant" else "You:"
        new = f"{ts}\n{prefix} {text}\n"
        current = self.lines
        self.lines = (current + "\n" + new).strip()
        self.refresh()

    def render(self) -> str:
        return self.lines or "Merlin is listening...\nSay \"Merlin\" or type a question."
