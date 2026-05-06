"""Terminal pane widget — renders a PTY-backed terminal in Textual."""

import asyncio
import logging
from textual.widget import Widget
from textual.reactive import reactive
from textual.keys import Keys
from desktop.terminal.pty import PtyProcess
from desktop.terminal.emulator import TerminalEmulator

log = logging.getLogger("merlin.terminal.pane")


class TerminalPane(Widget):
    """A single terminal widget that renders a PTY+pyte buffer."""

    title = reactive("term")
    cursor_visible = reactive(True)
    has_focus = reactive(False)

    def __init__(self, shell: str = "/bin/zsh", title: str = "term", pane_id: str = None, **kwargs):
        super().__init__(**kwargs)
        self.shell = shell
        self.title = title
        self._pane_id = pane_id or id(self)
        self.pty = PtyProcess(shell)
        self.emulator = TerminalEmulator(24, 80)
        self._cursor_row = 0
        self._cursor_col = 0
        self._on_output_callback = None

    def on_output(self, callback):
        self._on_output_callback = callback

    def on_mount(self):
        self.pty.spawn()
        self.pty.on_output = self._handle_pty_output
        asyncio.get_event_loop().call_soon(self._start_reader)

    def _start_reader(self):
        asyncio.get_event_loop().add_reader(self.pty.master_fd, self.pty._read_callback)

    def _handle_pty_output(self, data: bytes):
        self.emulator.feed(data)
        self._cursor_row = self.emulator.screen.cursor.y
        self._cursor_col = self.emulator.screen.cursor.x
        self.refresh()
        if self._on_output_callback:
            self._on_output_callback(self.emulator.get_last_lines(3))

    def write(self, text: str):
        """Write text to the PTY (as if typed)."""
        self.pty.write(text.encode())

    def resize_pty(self, rows: int, cols: int):
        self.pty.resize(rows, cols)
        self.emulator.resize(rows, cols)

    def close(self):
        try:
            asyncio.get_event_loop().remove_reader(self.pty.master_fd)
        except Exception:
            pass
        self.pty.close()

    # ── Key handling ─────────────────────────────

    def on_key(self, event):
        if event.key == "enter":
            self.pty.write(b"\r")
        elif event.key == "tab":
            self.pty.write(b"\t")
        elif event.key == "escape":
            self.pty.write(b"\x1b")
        elif event.key == "backspace":
            self.pty.write(b"\x7f")
        elif event.key == "delete":
            self.pty.write(b"\x1b[3~")
        elif event.key == "home":
            self.pty.write(b"\x1b[H")
        elif event.key == "end":
            self.pty.write(b"\x1b[F")
        elif event.key.startswith("up"):
            self.pty.write(b"\x1b[A")
        elif event.key.startswith("down"):
            self.pty.write(b"\x1b[B")
        elif event.key.startswith("right"):
            self.pty.write(b"\x1b[C")
        elif event.key.startswith("left"):
            self.pty.write(b"\x1b[D")
        elif event.key.startswith("ctrl+"):
            char = event.key[5]
            if char == "c":
                self.pty.write(b"\x03")
            elif char == "d":
                self.pty.write(b"\x04")
            elif char == "l":
                self.pty.write(b"\x0c")
            elif char == "a":
                self.pty.write(b"\x01")
            elif char == "e":
                self.pty.write(b"\x05")
            elif char == "w":
                self.pty.write(b"\x17")
            elif char == "u":
                self.pty.write(b"\x15")
            elif char == "z":
                self.pty.write(b"\x1a")
        elif event.key == " ":
            self.pty.write(b" ")
        elif len(event.key) == 1:
            self.pty.write(event.key.encode())

    def render_line(self, y: int) -> str:
        """Render a single line of the terminal buffer."""
        if y < 0 or y >= self.emulator.rows:
            return " " * self.size.width

        line_cells = self.emulator.get_lines()
        if y >= len(line_cells):
            return " " * self.size.width

        cells = line_cells[y]
        result = ""
        for cell in cells:
            result += cell.get("char", " ")
        # Pad to full width
        w = self.size.width
        return result.ljust(w)
