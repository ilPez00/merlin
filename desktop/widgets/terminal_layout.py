"""Terminal layout manager — handles split panes, focus tracking, hotkeys."""

import logging
from textual.widget import Widget
from textual.containers import Horizontal, Vertical
from desktop.widgets.terminal_pane import TerminalPane

log = logging.getLogger("merlin.terminal.layout")


class TerminalLayout(Widget):
    """Manages a tree of terminal panes with horizontal/vertical splits."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._panes: list[TerminalPane] = []
        self._focused_idx = 0
        self._container = None

    def compose(self):
        # Start with a single terminal pane
        pane = self._create_pane()
        self._panes = [pane]
        yield pane

    def _create_pane(self, shell: str = "/bin/zsh") -> TerminalPane:
        pane = TerminalPane(shell=shell, title=f"term{len(self._panes)}")
        pane.on_output(self._on_pane_output)
        return pane

    def _on_pane_output(self, last_lines: str):
        """Called when a pane produces output — check for errors/suggestions."""
        from desktop.suggestion import suggestion_queue
        sug = suggestion_queue.detect_error_suggestion(last_lines)
        if sug:
            sug.pane_id = str(self._focused_idx)
            suggestion_queue.push(sug)

    def split_horizontal(self):
        if not self._panes:
            return
        new_pane = self._create_pane()
        # Replace the current container with a Vertical containing both
        current = self._panes[self._focused_idx]
        parent = current.parent
        if parent:
            new_pane = self._create_pane()
            self._panes.append(new_pane)
            # Simple: just add below the current pane
            self.mount(new_pane, before=current, after=True)
            self._focused_idx = len(self._panes) - 1
            self._reflow()

    def split_vertical(self):
        new_pane = self._create_pane()
        self._panes.append(new_pane)
        self.mount(new_pane, before=self._panes[self._focused_idx])
        self._reflow()

    def close_focused(self):
        if len(self._panes) <= 1:
            return
        pane = self._panes[self._focused_idx]
        pane.close()
        pane.remove()
        self._panes.pop(self._focused_idx)
        if self._focused_idx >= len(self._panes):
            self._focused_idx = len(self._panes) - 1
        self._reflow()

    def focus_next(self):
        if self._panes:
            self._focused_idx = (self._focused_idx + 1) % len(self._panes)
            self._panes[self._focused_idx].focus()

    def focus_prev(self):
        if self._panes:
            self._focused_idx = (self._focused_idx - 1) % len(self._panes)
            self._panes[self._focused_idx].focus()

    def get_focused_pane(self) -> TerminalPane | None:
        if self._panes and self._focused_idx < len(self._panes):
            return self._panes[self._focused_idx]
        return None

    def write_to_focused(self, text: str):
        pane = self.get_focused_pane()
        if pane:
            pane.write(text)

    def _reflow(self):
        self.refresh(layout=True)

    def on_mount(self):
        if self._panes:
            self._panes[0].focus()
