import re
import logging

log = logging.getLogger("merlin.wake")


class WakeWordDetector:
    """Checks transcribed text for wake words."""

    def __init__(self, words: list[str] | None = None):
        self.words = words or ["marlin", "merlino", "merlin"]
        self._patterns = [re.compile(re.escape(w), re.IGNORECASE) for w in self.words]

    def check(self, text: str) -> str | None:
        """Returns the matched word if found, else None."""
        if not text:
            return None
        for p in self._patterns:
            m = p.search(text)
            if m:
                return m.group(0)
        return None

    def strip_wake(self, text: str) -> str:
        """Remove the wake word from the text, return the remainder."""
        for p in self._patterns:
            text = p.sub("", text, count=1).strip()
        return re.sub(r"^\s*[,.:;!?\-]+\s*", "", text).strip()

    def set_words(self, words: list[str]):
        self.words = words
        self._patterns = [re.compile(re.escape(w), re.IGNORECASE) for w in self.words]
