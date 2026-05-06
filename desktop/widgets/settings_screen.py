from textual.screen import ModalScreen
from textual.widgets import Input, Button, Static, Select, Label
from textual.containers import Vertical
from desktop.config import desktop_config


class SettingsScreen(ModalScreen):
    """Settings modal — API key, provider, wake words, etc."""

    def compose(self):
        with Vertical(classes="settings-dialog"):
            yield Static("⚙ SETTINGS", classes="settings-title")

            yield Static("API Provider:", classes="label")
            yield Select(
                [(p, p) for p in ["deepseek", "openai", "anthropic", "custom"]],
                value=desktop_config.get("provider") or "deepseek",
                id="settings-provider",
            )
            yield Static("API Key:", classes="label")
            yield Input(
                placeholder="sk-...",
                id="settings-api-key",
                password=True,
                value=desktop_config.get("api_key") or "",
            )
            yield Static("Custom Base URL:", classes="label")
            yield Input(
                placeholder="https://api.example.com/v1",
                id="settings-base-url",
                value=desktop_config.get("base_url") or "",
            )
            yield Static("Wake words (comma-separated):", classes="label")
            yield Input(
                id="settings-wake",
                value=", ".join(desktop_config.get("wake_words") or ["marlin", "merlino", "merlin"]),
            )
            yield Static("TTS Voice:", classes="label")
            yield Input(
                id="settings-tts",
                value=desktop_config.get("tts_voice") or "en-US-JennyNeural",
            )

            yield Button("SAVE & CLOSE", id="settings-save", variant="primary")
            yield Button("CANCEL", id="settings-cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "settings-save":
            import os
            api_key = self.query_one("#settings-api-key", Input).value.strip()
            provider = self.query_one("#settings-provider", Select).value
            base_url = self.query_one("#settings-base-url", Input).value.strip()
            wake = self.query_one("#settings-wake", Input).value.strip()
            tts = self.query_one("#settings-tts", Input).value.strip()

            if api_key:
                desktop_config.set("api_key", api_key)
                os.environ["MERLIN_API_KEY"] = api_key
            if provider:
                desktop_config.set("provider", provider)
            if base_url:
                desktop_config.set("base_url", base_url)
            if wake:
                words = [w.strip().lower() for w in wake.split(",") if w.strip()]
                if words:
                    desktop_config.set("wake_words", words)
            if tts:
                desktop_config.set("tts_voice", tts)

            self.app.pop_screen()

        elif event.button.id == "settings-cancel":
            self.app.pop_screen()
