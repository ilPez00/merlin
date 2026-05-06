from textual.screen import ModalScreen
from textual.widgets import Input, Button, Label
from textual.containers import Vertical


class SudoDialog(ModalScreen):
    """Modal asking for sudo password for a specific command."""

    def __init__(self, cmd: str):
        super().__init__()
        self.cmd = cmd

    def compose(self):
        with Vertical(classes="sudo-dialog"):
            yield Label(f"🔓 Sudo needed for:\n{self.cmd}")
            yield Input(password=True, placeholder="Enter sudo password...", id="sudo-pw")
            yield Button("Submit", id="sudo-submit", variant="primary")
            yield Button("Cancel", id="sudo-cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "sudo-cancel":
            self.dismiss(None)
        elif event.button.id == "sudo-submit":
            pw = self.query_one("#sudo-pw", Input).value
            self.dismiss(pw)

    def on_input_submitted(self, event: Input.Submitted):
        pw = self.query_one("#sudo-pw", Input).value
        self.dismiss(pw)
