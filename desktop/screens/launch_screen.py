from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Vertical
from desktop.system.permissions import check_all


class LaunchScreen(Screen):
    """Permission check screen at startup."""

    def compose(self):
        yield Header()
        with Vertical(id="launch-container"):
            yield Static("MERLIN — Desktop TUI", classes="title")
            yield Static("Checking system capabilities...", id="status-msg")
            yield Static("", id="perm-results")
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
        checks = [
            ("🎤 Microphone", result.microphone),
            ("📷 Webcam", result.webcam),
            ("🖥️ Screen capture", result.screen_capture),
            ("🌐 Internet", result.internet),
            ("📁 File access", result.file_access),
        ]
        for label, ok in checks:
            icon = "✓" if ok else "✗"
            lines.append(f" {icon} {label}")

        if result.sudo:
            lines.append(f" ✓ 🔓 Sudo: cached")
        else:
            lines.append(f" - 🔓 Sudo: available (per-command)")

        if result.errors:
            for e in result.errors:
                lines.append(f"   ⚠ {e}")

        self.query_one("#perm-results").update("\n".join(lines))
        self.query_one("#status-msg").update("All systems ready" if result.all_ok else "Some checks failed")
        self.query_one("#start-btn").disabled = not result.all_ok

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "start-btn":
            self.app.push_screen("main")
