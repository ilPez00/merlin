import asyncio
import logging
import time

from textual.screen import Screen
from textual.widgets import Header, Footer
from textual.containers import Horizontal, Vertical
from textual import work

from desktop.widgets.left_panel import LeftPanel
from desktop.widgets.chat_view import ChatView
from desktop.widgets.input_bar import InputBar
from desktop.widgets.status_bar import StatusBar
from desktop.widgets.mode_selector import ModeSelector
from desktop.widgets.sudo_dialog import SudoDialog
from desktop.system.sudo import sudo_ctx
from audio.command import parse as parse_voice_command

log = logging.getLogger("merlin.desktop")

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import cv2
except ImportError:
    cv2 = None


class MainScreen(Screen):
    """Main chat + status TUI screen."""

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("ctrl+t", "mic_test", "Mic test"),
        ("ctrl+l", "show_log", "Show log"),
    ]

    def compose(self):
        yield StatusBar(id="status-bar")
        with Horizontal():
            yield LeftPanel(id="left-panel", classes="panel")
            yield ChatView(id="chat-view", classes="panel")
        yield InputBar(id="input-bar")
        yield ModeSelector(id="mode-selector")
        yield Footer()

    def on_mount(self):
        self._voice_status = "starting"
        self._voice_running = True
        self._camera_running = True
        self._setup_voice_pipeline()
        self._setup_camera()
        self._setup_cleanup_timer()
        self._setup_widget_refresh()
        # Welcome message
        cv = self.query_one("#chat-view", ChatView)
        cv.add_message("system", "Merlin listening. Press Ctrl+T to test mic, say wake word to query.")

    # ── Actions ─────────────────────────────────

    def action_mic_test(self):
        """Test microphone: record 3s, transcribe, show result."""
        cv = self.query_one("#chat-view", ChatView)
        cv.add_message("system", "🎤 Microphone test: recording 3s...")
        asyncio.create_task(self._run_mic_test())

    def action_show_log(self):
        cv = self.query_one("#chat-view", ChatView)
        cv.add_message("system", f"Voice status: {self._voice_status}. Watch terminal for merlin.desktop logs.")

    async def _run_mic_test(self):
        cv = self.query_one("#chat-view", ChatView)
        try:
            duration = 3
            fs = 16000
            cv.add_message("system", f"Recording {duration}s... speak now")
            rec = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="int16")
            sd.wait()
            cv.add_message("system", f"Captured {len(rec)} samples. Transcribing...")

            from audio.transcriber import Transcriber
            t = Transcriber()
            text = t.transcribe(rec.flatten(), fs)
            if text and text.strip():
                cv.add_message("system", f"✅ Heard: \"{text.strip()[:120]}\"")
            else:
                cv.add_message("system", "❌ No speech detected. Check mic permissions.")
        except Exception as e:
            cv.add_message("system", f"❌ Mic test error: {e}")

    # ── Message handling ──────────────────────

    def on_input_bar_query_submitted(self, event: InputBar.QuerySubmitted):
        self._handle_query(event.text)

    def on_input_bar_mic_pressed(self):
        self._handle_voice_query()

    def on_mode_selector_tab_changed(self, event):
        tab_id = event.pane.id
        if tab_id:
            mode_name = tab_id.upper()
            sb = self.query_one("#status-bar", StatusBar)
            sb.mode = mode_name
            lp = self.query_one("#left-panel", LeftPanel)
            lp.set_mode(mode_name)
            from desktop.config import desktop_config
            desktop_config.set("activity_mode", mode_name)

    def _log_voice_status(self, msg: str):
        try:
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", msg)
        except Exception:
            pass

    def _handle_voice_command(self, action: str, payload):
        """Handle parsed voice commands locally without LLM."""
        cv = self.query_one("#chat-view", ChatView)
        lp = self.query_one("#left-panel", LeftPanel)
        sb = self.query_one("#status-bar", StatusBar)

        if action == "scroll":
            if payload == "up":
                cv.add_message("system", "↑ scrolled up")
            elif payload == "down":
                cv.add_message("system", "↓ scrolled down")
        elif action == "show_widget":
            cv.add_message("system", f"Showing widget: {payload}")
        elif action == "switch_mode":
            from desktop.config import desktop_config
            desktop_config.set("activity_mode", payload)
            sb.mode = payload
            lp.set_mode(payload)
            # Update mode tab
            mt = self.query_one("#mode-selector", ModeSelector)
            mt.active = payload
            cv.add_message("system", f"Switched to {payload} mode")
        elif action == "query":
            cv.add_message("system", f"Querying {payload}...")
            self._handle_query(payload)
        elif action == "action":
            if payload == "prep_note":
                cv.add_message("system", "Ready to take a note. Speak your prep note.")
            elif payload == "summary":
                cv.add_message("system", "Generating conversation summary...")
                self._handle_query("summarize the recent conversation")
        elif action == "app_mode":
            cv.add_message("system", f"App mode: {payload}")
            # Future: switch between visor/copilot/incognito

    # ── Query processing ──────────────────────

    async def _handle_query(self, text: str):
        cv = self.query_one("#chat-view", ChatView)
        ts = time.strftime("%H:%M:%S")
        cv.add_message("user", text, ts)

        # Check for sudo password request
        if "sudo password" in text.lower() or text.strip() == "__sudo_pw__":
            # This is a response from the sudo dialog
            return

        from audio.storage import AudioStorage
        store = AudioStorage()
        recent = store.get_recent_text(30)
        context = f"[recent audio context]\n{recent}" if recent else ""

        webcam = ""
        if hasattr(self, "_last_frame_b64") and self._last_frame_b64:
            webcam = f"[webcam frame available, call capture_webcam to see it]"

        from ai.agent import run as agent_run
        from ai.session import MerlinSession
        from desktop.config import desktop_config

        session = MerlinSession()
        await session.start()

        system = (
            "You are Merlin, an AI desktop assistant with full PC access.\n"
            "You can read/write files, run shell commands, capture the screen, "
            "capture the webcam, and speak aloud. Be concise and proactive.\n"
            "Use run_shell with 'sudo' prefix for admin commands. "
            "If sudo is not available, tell the user to speak their password.\n"
            f"Current activity mode: {desktop_config.get('activity_mode', 'QUERY')}."
        )
        if recent:
            system += f"\n\nRecent audio context (user was discussing or hearing):\n{recent[:500]}"
        if webcam:
            system += f"\n\n{webcam}"

        try:
            response = await agent_run(
                backend=session._backend,
                system_prompt=system,
                history=[],
                query=text,
                mode=desktop_config.get("activity_mode", "QUERY"),
            )

            # Check if the response indicates sudo is needed
            if "sudo" in response.lower() and ("password" in response.lower() or "provide" in response.lower()):
                await self._prompt_sudo(text)
                return

            cv.add_message("assistant", response, time.strftime("%H:%M:%S"))
            await self._speak(response)
        except Exception as e:
            cv.add_message("assistant", f"Error: {e}", time.strftime("%H:%M:%S"))

    async def _prompt_sudo(self, original_query: str):
        """Show sudo dialog, capture password, re-run query."""
        dialog = SudoDialog("Command requested sudo. Speak or type your password.")
        pw = await self.app.push_screen(dialog)
        if pw:
            from ai.tools import set_sudo_password
            set_sudo_password(pw)
            sudo_ctx.set_password(pw)
            lp = self.query_one("#left-panel", LeftPanel)
            lp.sudo_ready = True
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", "🔓 Sudo password received. Retrying command...")
            await self._handle_query(original_query)

    async def _handle_voice_query(self):
        sb = self.query_one("#status-bar", StatusBar)
        sb.listening = True
        self._voice_status = "recording"
        self.refresh()

        try:
            duration = 5
            fs = 16000
            self.call_from_thread(self._log_voice_status, f"🎤 Recording {duration}s...")
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="int16")
            sd.wait()
            self._voice_status = "transcribing"

            from audio.transcriber import Transcriber
            t = Transcriber()
            text = t.transcribe(recording.flatten(), fs)
            if text.strip():
                self.call_from_thread(self._log_voice_status, f"✅ Transcribed: \"{text.strip()[:80]}\"")
                await self._handle_query(text.strip())
            else:
                self.call_from_thread(self._log_voice_status, "❌ No speech detected")
        except Exception as e:
            self.call_from_thread(self._log_voice_status, f"❌ Voice error: {e}")
            log.warning("voice query error: %s", e)
        finally:
            sb.listening = False
            self._voice_status = "listening"

    # ── Continuous voice pipeline ────────────

    def _setup_voice_pipeline(self):
        self._voice_running = True
        # Show mic status
        try:
            cv = self.query_one("#chat-view", ChatView)
            cv.add_message("system", "Voice pipeline initializing...")
        except Exception:
            pass
        self._run_voice_loop()

    @work(thread=True)
    def _run_voice_loop(self):
        import numpy as np
        from audio.buffer import RingBuffer
        from audio.transcriber import Transcriber
        from audio.wake import WakeWordDetector
        from audio.storage import AudioStorage
        from desktop.config import desktop_config

        ring = RingBuffer(seconds=desktop_config.get("buffer_seconds") or 600)
        transcriber = Transcriber()
        wake = WakeWordDetector(desktop_config.get("wake_words"))
        store = AudioStorage()
        fs = 16000

        try:
            stream = sd.InputStream(samplerate=fs, channels=1, dtype="int16")
            stream.start()
            self._voice_status = "listening"
            self.call_from_thread(self._log_voice_status, "Voice pipeline active 🎤")
        except Exception as e:
            self._voice_status = f"mic error: {e}"
            log.warning("voice pipeline: mic unavailable: %s", e)
            self.call_from_thread(self._log_voice_status, f"⚠ Mic error: {e}")
            return

        block_samples = int(fs * 5)
        # Wait for widgets to be mounted before accessing them
        import time as _time
        _time.sleep(1)
        try:
            lp = self.query_one("#left-panel", LeftPanel)
            lp_ref = lp
        except Exception:
            lp_ref = None

        while self._voice_running:
            try:
                chunk, _ = stream.read(block_samples)
                ring.write(chunk.flatten())

                # Transcribe tail every 5s
                audio_tail = ring.read(10)
                text = transcriber.transcribe(audio_tail, fs)
                if text:
                    store.save_transcript(time.time(), text, audio_tail.tobytes())

                    if lp_ref:
                        try:
                            lp_ref.last_heard = text[:60]
                            lp_ref.buffer_pct = ring.fill_ratio
                            self.refresh()
                        except Exception:
                            pass

                    # Voice command check
                    cmd = parse_voice_command(text)
                    if cmd:
                        action, payload = cmd
                        self.call_from_thread(self._handle_voice_command, action, payload)
                        continue

                    # Wake word check
                    match = wake.check(text)
                    if match:
                        self._voice_status = f"wake: {match}"
                        store.mark_triggered(
                            time.strftime("%Y-%m-%d_%H-%M-%S")
                        )
                        command = wake.strip_wake(text)
                        self.call_from_thread(self._log_voice_status, f"🔊 Wake word '{match}' detected")
                        if command:
                            cmd2 = parse_voice_command(command)
                            if cmd2:
                                self.call_from_thread(self._handle_voice_command, cmd2[0], cmd2[1])
                            else:
                                self.call_from_thread(self._handle_query, command)
                        else:
                            self.call_from_thread(self._handle_query, "yes?")
                        self._voice_status = "listening"
            except Exception as e:
                log.warning("voice loop error: %s", e)
                continue

        stream.stop()
        stream.close()

    # ── Webcam ─────────────────────────────────

    def _setup_camera(self):
        self._camera_running = True
        self._run_camera_loop()

    @work(thread=True)
    def _run_camera_loop(self):
        if cv2 is None:
            return
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return

        while self._camera_running:
            ret, frame = cap.read()
            if ret:
                lp = self.query_one("#left-panel", LeftPanel)
                lp.webcam_active = True
                self.refresh()

                import base64
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                b64 = base64.b64encode(buf).tobytes().decode()
                self._last_frame_b64 = b64
                from ai.tools import set_webcam_frame
                set_webcam_frame(b64)
            import time as _time
            _time.sleep(2)

        cap.release()

    # ── TTS ─────────────────────────────────────

    async def _speak(self, text: str):
        try:
            import edge_tts
            from desktop.config import desktop_config
            voice = desktop_config.get("tts_voice") or "en-US-JennyNeural"
            tts = edge_tts.Communicate(text, voice)
            await tts.save("/tmp/merlin_tts.mp3")
            import subprocess
            subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "/tmp/merlin_tts.mp3"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log.warning("TTS error: %s", e)

    # ── Cleanup timer ───────────────────────────

    def _setup_cleanup_timer(self):
        self._cleanup_timer = asyncio.get_event_loop().call_later(3600, self._cleanup)

    def _cleanup(self):
        from audio.storage import AudioStorage
        store = AudioStorage()
        store.cleanup_old()
        self._cleanup_timer = asyncio.get_event_loop().call_later(3600, self._cleanup)

    # ── Widget refresh ──────────────────────────

    def _setup_widget_refresh(self):
        self._widget_timer = asyncio.get_event_loop().call_later(30, self._tick_widgets)

    def _tick_widgets(self):
        lp = self.query_one("#left-panel", LeftPanel)
        lp._refresh_widgets()
        self._widget_timer = asyncio.get_event_loop().call_later(30, self._tick_widgets)


    # ── Quit ────────────────────────────────────

    def action_quit(self):
        self._voice_running = False
        self._camera_running = False
        self.app.exit()
