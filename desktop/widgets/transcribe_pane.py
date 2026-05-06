"""Transcribe pane — live whisper transcription shown in a terminal-style pane."""

import time
from textual.widget import Widget


class TranscribePane(Widget):
    """A special terminal pane that shows live transcriptions."""

    def __init__(self, title: str = "TRANSCRIBE", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self._lines: list[dict] = []  # [{time, text}]
        self._recording = False

    def add_line(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self._lines.append({"time": ts, "text": text})
        if len(self._lines) > 100:
            self._lines = self._lines[-100:]
        self.refresh()

    def render_line(self, y: int) -> str:
        idx = len(self._lines) - self.size.height + y
        if idx < 0 or idx >= len(self._lines):
            return " " * self.size.width
        line = self._lines[idx]
        status = "🔴" if self._recording else "⏹"
        text = f" [{line['time']}] {line['text']}"
        return text.ljust(self.size.width)
