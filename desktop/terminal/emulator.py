"""Terminal emulator — wraps pyte to maintain a screen buffer from PTY output."""

import pyte


class TerminalEmulator:
    """Maintains a 2D character buffer using pyte's VT100 emulation."""

    def __init__(self, rows: int = 24, cols: int = 80):
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)
        self.rows = rows
        self.cols = cols

    def feed(self, data: bytes):
        """Feed raw bytes from the PTY into the emulator."""
        try:
            text = data.decode("utf-8", errors="replace")
            self.stream.feed(text)
        except Exception as e:
            pass

    def resize(self, rows: int, cols: int):
        """Resize the screen buffer."""
        self.screen.resize(rows, cols)
        self.rows = rows
        self.cols = cols

    def get_lines(self) -> list[list[dict]]:
        """Return the screen buffer as a 2D array of cell dicts.

        Each cell: {char, fg, bg, bold, italic, underscore, reverse}
        """
        result = []
        for row_idx in range(self.screen.lines):
            line = []
            for col_idx in range(self.screen.columns):
                char = self.screen.buffer[row_idx][col_idx]
                line.append({
                    "char": char.data or " ",
                    "fg": self._ansi_to_color(char.fg),
                    "bg": self._ansi_to_color(char.bg),
                    "bold": char.bold,
                    "italics": char.italics,
                    "underscore": char.underscore,
                    "reverse": char.reverse,
                })
            result.append(line)
        return result

    def get_plain_text(self) -> str:
        """Return the full screen as plain text (no escape codes)."""
        return "\n".join(self.screen.display)

    def get_last_lines(self, n: int = 5) -> str:
        """Return the last N lines of the screen buffer."""
        lines = self.screen.display
        return "\n".join(lines[-n:])

    @staticmethod
    def _ansi_to_color(ansi_color) -> str:
        """Convert pyte ANSI color to hex or named color."""
        if ansi_color is None or ansi_color == "default":
            return ""
        # pyte uses named colors (like 'white', 'black', etc.) or ANSI numbers
        color_map = {
            "black": "#000000", "red": "#EF4444", "green": "#4ADE80",
            "brown": "#F59E0B", "blue": "#3B82F6", "magenta": "#E040FB",
            "cyan": "#00E5FF", "lightgray": "#AAAAAA",
            "darkgray": "#555555", "lightred": "#FF6B6B",
            "lightgreen": "#8BFF8B", "yellow": "#FFD700",
            "lightblue": "#87CEEB", "lightmagenta": "#FF87FF",
            "lightcyan": "#87FFFF", "white": "#FFFFFF",
        }
        if isinstance(ansi_color, str):
            return color_map.get(ansi_color.lower(), "")
        if isinstance(ansi_color, int):
            # ANSI 256-color: convert to hex roughly
            if ansi_color < 16:
                named = ["#000000","#EF4444","#4ADE80","#F59E0B","#3B82F6","#E040FB",
                         "#00E5FF","#AAAAAA","#555555","#FF6B6B","#8BFF8B","#FFD700",
                         "#87CEEB","#FF87FF","#87FFFF","#FFFFFF"]
                return named[ansi_color] if ansi_color < len(named) else ""
            return ""
        return ""
