"""Suggestion bar — bottom widget showing one suggestion at a time with accept/decline."""

from textual.widgets import Static
from textual.reactive import reactive
from desktop.suggestion import suggestion_queue


class SuggestionBar(Static):
    """Bottom bar showing the current suggestion, Tab=Accept, Esc=Decline."""

    text = reactive("")

    def on_mount(self):
        suggestion_queue.on_change(self._update)
        self._update()

    def _update(self):
        sug = suggestion_queue.current()
        if sug:
            self.text = f" 💡 {sug.text}    [Tab=Accept] [Esc=Decline]"
        else:
            self.text = ""

    def render(self) -> str:
        if not self.text:
            return ""
        bar_w = self.size.width or 80
        return self.text.ljust(bar_w)
