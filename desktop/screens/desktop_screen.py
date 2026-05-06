"""Desktop screen — full terminal multiplexer with Merlin copilot sidebar."""

import asyncio
import logging
import os
import time

from textual.screen import Screen
from textual.widgets import Header, Footer
from textual.containers import Horizontal, Vertical
from textual import work
from textual.message import Message
from pathlib import Path

from desktop.widgets.terminal_layout import TerminalLayout
from desktop.widgets.suggestion_bar import SuggestionBar
from desktop.widgets.chat_view import ChatView
from desktop.widgets.left_panel import LeftPanel
from desktop.widgets.status_bar import StatusBar
from desktop.widgets.mode_selector import ModeSelector
from desktop.widgets.input_bar import InputBar
from desktop.widgets.settings_screen import SettingsScreen
from desktop.suggestion import suggestion_queue, Suggestion
from desktop.system.sudo import sudo_ctx
from audio.command import parse as parse_voice_command

log = logging.getLogger("merlin.desktop")

CONV_PATH = Path.home() / ".merlin" / "conversations.md"


def _log_conversation(role: str, text: str, mode: str = "WORK"):
    try:
        CONV_PATH.parent.mkdir(parents=True, exist_ok=True)
        date = time.strftime("%Y-%m-%d")
        ts = time.strftime("%H:%M:%S")
        prefix = "**You**" if role == "user" else "**Merlin**" if role == "assistant" else f"**{role.title()}**"
        line = f"\n### {date} {ts} ({mode})\n{prefix}: {text}\n"
        with open(CONV_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        log.warning("failed to log conversation: %s", e)


class DesktopScreen(Screen):
    """Full desktop environment: terminal multiplexer + Merlin copilot + HUD."""

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("ctrl+t", "mic_test", "Mic test"),
        ("ctrl+s", "settings", "Settings"),
        ("ctrl+d", "export_dossiers", "Export dossiers"),
        ("alt+h", "split_h", "Split horizontal"),
        ("alt+v", "split_v", "Split vertical"),
        ("alt+w", "close_pane", "Close pane"),
        ("alt+tab", "next_pane", "Next pane"),
        ("alt+shift+tab", "prev_pane", "Prev pane"),
        ("tab", "accept_suggestion", "Accept suggestion"),
        ("escape", "decline_suggestion", "Decline suggestion"),
    ]

    def compose(self):
        yield StatusBar(id="status-bar")
        with Horizontal():
            yield LeftPanel(id="left-panel", classes="panel")
            yield TerminalLayout(id="terminal-layout", classes="panel")
            yield ChatView(id="chat-view", classes="panel")
        yield SuggestionBar(id="suggestion-bar")
        yield InputBar(id="input-bar")
        yield ModeSelector(id="mode-selector")
        yield Footer()

    def on_mount(self):
        self._voice_running = True
        self._voice_status = "idle"
        cv = self.query_one("#chat-view", ChatView)
        cv.add_message("system", "Desktop environment ready. Alt+H/V to split terminals, Tab/Esc for suggestions.")

    # ── Key handlers ─────────────────────────────

    def action_split_h(self):
        tl = self.query_one("#terminal-layout", TerminalLayout)
        tl.split_horizontal()

    def action_split_v(self):
        tl = self.query_one("#terminal-layout", TerminalLayout)
        tl.split_vertical()

    def action_close_pane(self):
        tl = self.query_one("#terminal-layout", TerminalLayout)
        tl.close_focused()

    def action_next_pane(self):
        tl = self.query_one("#terminal-layout", TerminalLayout)
        tl.focus_next()

    def action_prev_pane(self):
        tl = self.query_one("#terminal-layout", TerminalLayout)
        tl.focus_prev()

    def action_accept_suggestion(self):
        sug = suggestion_queue.accept_current()
        if sug and sug.command:
            tl = self.query_one("#terminal-layout", TerminalLayout)
            tl.write_to_focused(sug.command + "\n")
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", f"⚡ Executed: {sug.command}")

    def action_decline_suggestion(self):
        sug = suggestion_queue.decline_current()
        if sug:
            self.refresh()

    # ── Merlin actions ───────────────────────────

    def action_mic_test(self):
        cv = self.query_one("#chat-view", ChatView)
        cv.add_message("system", "🎤 Mic test: recording 3s...")
        asyncio.create_task(self._run_mic_test())

    def action_settings(self):
        self.app.push_screen(SettingsScreen())

    def action_export_dossiers(self):
        from ai.dossiers import dossiers
        try:
            md = dossiers.export_markdown()
            path = Path.home() / ".merlin" / "dossiers.md"
            path.write_text(md, encoding="utf-8")
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", f"📄 Dossiers exported to {path}")
        except Exception as e:
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", f"❌ Export error: {e}")

    def action_quit(self):
        self._voice_running = False
        self.app.exit()

    # ── Mic test ─────────────────────────────────

    async def _run_mic_test(self):
        try:
            import sounddevice as sd
            from audio.transcriber import Transcriber
            cv = self.query_one("#chat-view", ChatView)
            duration = 3
            fs = 16000
            rec = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="int16")
            sd.wait()
            t = Transcriber()
            text = t.transcribe(rec.flatten(), fs)
            if text and text.strip():
                cv.add_message("system", f"✅ Heard: \"{text.strip()[:120]}\"")
            else:
                cv.add_message("system", "❌ No speech detected")
        except Exception as e:
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", f"❌ Mic error: {e}")

    # ── Query processing ─────────────────────────

    async def _handle_query(self, text: str):
        cv = self.query_one("#chat-view", ChatView)
        ts = time.strftime("%H:%M:%S")

        # Check for terminal command injection
        if text.startswith("!"):
            cmd = text[1:]
            tl = self.query_one("#terminal-layout", TerminalLayout)
            tl.write_to_focused(cmd + "\n")
            cv.add_message("system", f"⚡ {cmd}", ts)
            return

        cv.add_message("user", text, ts)
        _log_conversation("user", text)

        from ai.agent import run as agent_run
        from ai.session import MerlinSession
        from desktop.config import desktop_config

        api_key = desktop_config.get("api_key")
        if not api_key:
            cv.add_message("assistant", "No API key configured. Ctrl+S for settings.", ts)
            return

        session = MerlinSession()
        await session.start()

        system = (
            "You are Merlin, an AI copilot for a Linux desktop. "
            "The user has multiple terminals open. You can suggest commands, "
            "analyze errors, and help with anything. "
            "CAVEMAN MODE: compress output. No greetings. Just the signal.\n"
            f"Activity: {desktop_config.get('activity_mode', 'WORK')}."
        )

        try:
            response = await agent_run(
                backend=session._backend,
                system_prompt=system,
                history=[],
                query=text,
                mode=desktop_config.get("activity_mode", "QUERY"),
            )
            cv.add_message("assistant", response, ts)
            _log_conversation("assistant", response)
            # If the response contains a command, queue as suggestion
            if "run " in response or "install " in response or response.startswith("sudo"):
                suggestion_queue.push(
                    Suggestion(text=response[:80], command=response.split("`")[1] if "`" in response else "")
                )
        except Exception as e:
            cv.add_message("assistant", f"Error: {e}", ts)
