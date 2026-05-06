import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".merlin"
CONFIG_PATH = CONFIG_DIR / "desktop_config.json"


class DesktopConfig:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.data = self._defaults()
        self.load()

    def _defaults(self):
        return {
            "provider": "deepseek",
            "api_key": "",
            "base_url": "",
            "model": "",
            "wake_words": ["marlin", "merlino", "merlin"],
            "tts_voice": "en-US-JennyNeural",
            "activity_mode": "WORK",
            "mic_device": None,
            "camera_device": 0,
            "buffer_seconds": 600,
        }

    def load(self):
        if CONFIG_PATH.exists():
            try:
                saved = json.loads(CONFIG_PATH.read_text())
                self.data.update({k: v for k, v in saved.items() if v})
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        CONFIG_PATH.write_text(json.dumps(self.data, indent=2))

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def api_endpoint(self):
        p = self.get("provider")
        base = self.get("base_url")
        if base:
            return base
        defaults = {
            "deepseek": "https://api.deepseek.com/v1",
            "openai": "https://api.openai.com/v1",
        }
        return defaults.get(p, "https://api.deepseek.com/v1")

    def api_model(self):
        m = self.get("model")
        if m:
            return m
        defaults = {
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o",
        }
        return defaults.get(self.get("provider"), "deepseek-chat")


desktop_config = DesktopConfig()
