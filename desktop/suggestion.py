"""Suggestion engine — queues AI suggestions, one at a time, Tab/Esc to accept/decline."""

import logging
import re

log = logging.getLogger("merlin.suggestion")


class Suggestion:
    def __init__(self, text: str, command: str = "", pane_id: str = ""):
        self.text = text          # Display text: "npm run dev → npm start?"
        self.command = command    # What to execute on accept (empty = just display)
        self.pane_id = pane_id    # Terminal to execute in
        self.accepted = False
        self.declined = False


class SuggestionQueue:
    """Queues suggestions, shows one at a time."""

    def __init__(self):
        self.queue: list[Suggestion] = []
        self.history: list[Suggestion] = []
        self._on_change = None

    def on_change(self, callback):
        self._on_change = callback

    def push(self, sug: Suggestion):
        self.queue.append(sug)
        log.info("suggestion queued: %s", sug.text)
        if self._on_change:
            self._on_change()

    def current(self) -> Suggestion | None:
        if self.queue:
            return self.queue[0]
        return None

    def accept_current(self) -> Suggestion | None:
        sug = self.current()
        if sug:
            sug.accepted = True
            self.queue.pop(0)
            self.history.append(sug)
            if self._on_change:
                self._on_change()
        return sug

    def decline_current(self) -> Suggestion | None:
        sug = self.current()
        if sug:
            sug.declined = True
            self.queue.pop(0)
            self.history.append(sug)
            if self._on_change:
                self._on_change()
        return sug

    def clear(self):
        self.queue.clear()
        if self._on_change:
            self._on_change()

    def detect_error_suggestion(self, terminal_output: str, cwd: str = "") -> Suggestion | None:
        """Analyze terminal output for common errors and suggest fixes."""
        if not terminal_output:
            return None

        lines = terminal_output.lower()

        # Command not found (zsh format: "zsh: command not found: npm")
        m = re.search(r"(?:command not found|not found)[:\s]+(\S+)", lines)
        if m:
            cmd = m.group(1)
            return Suggestion(
                text=f"'{cmd}' not found. Install it?",
                command=f"sudo apt install {cmd}",
            )

        # npm script missing
        if "missing script" in lines or "npm err!" in lines:
            return Suggestion(
                text="npm error detected. Check package.json?",
            )

        # Python traceback
        if "traceback" in lines or "error:" in lines and ".py" in lines:
            return Suggestion(
                text="Python error detected. Show full traceback?",
            )

        # Git
        if "not a git repository" in lines:
            return Suggestion(
                text="Not a git repo. Initialize?",
                command="git init",
            )

        # Permission denied
        if "permission denied" in lines:
            return Suggestion(
                text="Permission denied. Retry with sudo?",
                command=f"sudo {terminal_output.split(chr(10))[-1] if chr(10) in terminal_output else ''}",
            )

        return None


suggestion_queue = SuggestionQueue()
