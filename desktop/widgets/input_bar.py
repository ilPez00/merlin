from textual.widgets import Input, Button
from textual.containers import Horizontal
from textual.message import Message


class InputBar(Horizontal):
    """Text input + mic indicator."""

    def compose(self):
        yield Input(placeholder="Ask Merlin or type a command...", id="chat-input")
        yield Button("🎤", id="mic-btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "mic-btn":
            self.post_message(self.MicPressed())
            self.query_one("#mic-btn").label = "🔴"

    def on_input_submitted(self, event: Input.Submitted):
        self.post_message(self.QuerySubmitted(event.value))
        event.input.value = ""

    class MicPressed(Message):
        pass

    class QuerySubmitted(Message):
        def __init__(self, text: str):
            super().__init__()
            self.text = text
