from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static, Input
from textual.containers import Vertical
from desktop.system.permissions import check_all
from desktop.config import desktop_config


class LaunchScreen(Screen):
    """Permission check + config screen at startup."""

    def compose(self):
        yield Header()
        with Vertical(id="launch-container"):
            yield Static("MERLIN — Desktop TUI", classes="title")
            yield Static("Checking system capabilities...", id="status-msg")
            yield Static("", id="perm-results")

            # Wake word config (shown once if not set, or always if user wants)
            yield Static("Wake word:", id="wake-label")
            yield Input(
                placeholder="e.g. marlin, merlino, computer, jarvis",
                id="wake-input",
                value=", ".join(desktop_config.get("wake_words") or ["marlin", "merlino", "merlin"]),
            )
            yield Button("START MERLIN", id="start-btn", variant="primary", disabled=True)
        yield Footer()

    async def on_mount(self):
        await self.run_perm_check()

    async def run_perm_check(self):
        import asyncio
        self.query_one("#start-btn").disabled = True
        self.query_one("#status-msg").update("Checking permissions...")

        result = await asyncio.get_event_loop().run_in_executor(None, check_all)

        lines = []
        blocking_failures = 0
        checks = [
            ("🎤 Microphone (required)", result.microphone, True),
            ("📷 Webcam (optional)", result.webcam, False),
            ("🖥️ Screen capture (required)", result.screen_capture, True),
            ("🌐 Internet (required)", result.internet, True),
            ("📁 File access (required)", result.file_access, True),
        ]
        for label, ok, required in checks:
            if ok:
                lines.append(f" ✓ {label}")
            elif required:
                lines.append(f" ✗ {label}")
                blocking_failures += 1
            else:
                lines.append(f" - {label} (not found)")

        if result.sudo:
            lines.append(f" ✓ 🔓 Sudo: cached")
        else:
            lines.append(f" - 🔓 Sudo: available (per-command)")

        if result.errors:
            for e in result.errors:
                lines.append(f"   ⚠ {e}")

        can_start = blocking_failures == 0
        self.query_one("#perm-results").update("\n".join(lines))
        self.query_one("#status-msg").update(
            "All systems ready" if can_start else "Missing required permissions"
        )
        self.query_one("#start-btn").disabled = not can_start

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "start-btn":
            # Save wake words from input
            wake_text = self.query_one("#wake-input", Input).value.strip()
            if wake_text:
                words = [w.strip().lower() for w in wake_text.split(",") if w.strip()]
                if words:
                    desktop_config.set("wake_words", words)
            self.app.push_screen("main")
