"""
StreamProcessor — handles incoming phone data, batches it, and pushes
summarized context to the AI session. Also handles explicit query, observe,
pose keypoints, and wake-command voice requests.
"""

import asyncio
import base64
import logging
import os
import tempfile
import time
from typing import Any, Callable

from .rep_counter import RepCounter

log = logging.getLogger("merlin.processor")

DEFAULT_PUSH_INTERVAL = 10


class StreamProcessor:
    def __init__(self, session, send_fn: Callable):
        """
        Parameters
        ----------
        session  : MerlinSession
        send_fn  : async callable(msg: dict) — sends JSON to all clients
        """
        self.session = session
        self._send = send_fn

        self._latest_frame: bytes | None = None
        self._latest_gps: dict | None = None
        self._imu_samples: list[dict] = []
        self._audio_chunks: list[bytes] = []
        self._current_mode: str = "SCOUT"
        self._push_interval: int = DEFAULT_PUSH_INTERVAL
        self._rep_counter = RepCounter()

        self._push_task = asyncio.create_task(self._push_loop())

    # ── Phone message handlers ─────────────────────────────────────────────────

    async def on_frame(self, header: dict, payload: bytes):
        self._latest_frame = payload
        log.debug("frame received: %d bytes (mode=%s)", len(payload), header.get("mode"))

    async def on_audio(self, header: dict, payload: bytes):
        if header.get("wake"):
            asyncio.create_task(self._handle_wake_audio(payload, header))
        else:
            self._audio_chunks.append(payload)
            log.debug("audio chunk: %d bytes", len(payload))

    async def on_imu(self, msg: dict):
        self._imu_samples.append(msg)
        if len(self._imu_samples) > 20:
            self._imu_samples = self._imu_samples[-20:]

    async def on_gps(self, msg: dict):
        self._latest_gps = msg
        log.debug("gps: %.5f, %.5f", msg.get("lat", 0), msg.get("lon", 0))

    async def on_mode_change(self, msg: dict):
        mode = msg.get("mode", "SCOUT")
        log.info("mode change: %s → %s", self._current_mode, mode)
        self._current_mode = mode
        self._push_task.cancel()
        self._push_task = asyncio.create_task(self._push_loop())

    async def on_query(self, msg: dict):
        text = msg.get("text", "").strip()
        mode = msg.get("mode", self._current_mode)
        if not text:
            return
        log.info("phone query [%s]: %s", mode, text)
        asyncio.create_task(self._handle_query(text, mode))

    async def on_observe(self, msg: dict):
        mode = msg.get("mode", self._current_mode)
        log.info("observe request [%s]", mode)
        asyncio.create_task(self._handle_observe(mode))

    async def on_file_list(self, msg: dict):
        log.debug("file_list from phone: path=%s, entries=%d",
                  msg.get("path"), len(msg.get("entries", [])))

    async def on_pose(self, msg: dict):
        """Handle pose keypoints from the phone (MoveNet)."""
        keypoints = msg.get("keypoints", [])
        mode = msg.get("mode", self._current_mode)
        log.debug("pose: %d keypoints (mode=%s)", len(keypoints), mode)

        # Feed to rep counter for live analysis
        result = self._rep_counter.feed(keypoints)
        if result:
            # Rep detected — notify the phone
            await self._send({
                "type": "exercise_update",
                "exercise": result["exercise"],
                "reps": result["total_reps"],
                "recent_sets": result["recent_sets"],
                "mode": mode,
            })

    async def on_wake_command(self, msg: dict):
        """Wake word detected by phone; next audio chunk is a voice command."""
        mode = msg.get("mode", self._current_mode)
        log.info("wake command pending from phone (mode=%s)", mode)
        # The actual processing happens in _handle_wake_audio when audio arrives

    async def flush(self):
        self._push_task.cancel()
        if self._audio_chunks:
            await self._push_context()

    # ── Wake audio handler ─────────────────────────────────────────────────────

    async def _handle_wake_audio(self, payload: bytes, header: dict):
        """Transcribe wake-triggered audio immediately and process as a command."""
        transcript = await self._transcribe([payload])
        if transcript:
            mode = header.get("mode", self._current_mode)
            log.info("wake command transcription: %s", transcript)
            await self._handle_query(transcript, mode)

    # ── Internal query/observe handlers ───────────────────────────────────────

    async def _handle_query(self, text: str, mode: str):
        """Run the agentic query loop and send response to all clients."""
        try:
            response = await self.session.query(text, mode=mode)
            await self._send({"type": "response", "text": response, "mode": mode})
        except Exception as e:
            log.error("query handler error: %s", e)
            await self._send({"type": "response", "text": f"Error: {e}", "mode": mode})

    async def _handle_observe(self, mode: str):
        """Run proactive auto-observation and send result."""
        try:
            await self._push_context()
            observation = await self.session.auto_observe(mode=mode)
            if observation:
                await self._send({"type": "response", "text": observation, "mode": mode})
        except Exception as e:
            log.error("observe handler error: %s", e)

    # ── Periodic push loop ─────────────────────────────────────────────────────

    async def _push_loop(self):
        interval = self._mode_push_interval(self._current_mode)
        while True:
            await asyncio.sleep(interval)
            try:
                await self._push_context()
            except Exception as e:
                log.error("context push error: %s", e)

    def _mode_push_interval(self, mode: str) -> int:
        return {
            "SCOUT":   10,
            "NAV":     15,
            "ANALYZE": 5,
            "LISTEN":  8,
            "QUERY":   12,
            "RECON":   20,
        }.get(mode, DEFAULT_PUSH_INTERVAL)

    async def _push_context(self):
        parts = []

        if self._audio_chunks:
            transcript = await self._transcribe(self._audio_chunks[:])
            self._audio_chunks.clear()
            if transcript:
                parts.append(f"[audio transcript]\n{transcript}")

        if self._latest_gps:
            g = self._latest_gps
            lat = g.get("lat") or 0.0
            lon = g.get("lon") or 0.0
            parts.append(
                f"[location] lat={lat:.5f} lon={lon:.5f} "
                f"alt={g.get('alt')} acc={g.get('acc')}m speed={g.get('speed')}"
            )

        if self._imu_samples:
            n = len(self._imu_samples)
            avg_ax = sum(s.get("ax") or 0 for s in self._imu_samples) / n
            avg_ay = sum(s.get("ay") or 0 for s in self._imu_samples) / n
            avg_az = sum(s.get("az") or 0 for s in self._imu_samples) / n
            parts.append(
                f"[motion] avg accel x={avg_ax:.2f} y={avg_ay:.2f} z={avg_az:.2f}"
            )
            self._imu_samples.clear()

        frame_b64 = None
        if self._latest_frame:
            frame_b64 = base64.b64encode(self._latest_frame).decode()
            self._latest_frame = None

        if parts or frame_b64:
            await self.session.push_context(
                text="\n".join(parts),
                frame_b64=frame_b64,
                mode=self._current_mode,
            )

    # ── Audio transcription ────────────────────────────────────────────────────

    async def _transcribe(self, chunks: list[bytes]) -> str | None:
        """Concatenate WebM audio chunks and transcribe via Whisper."""
        from openai import AsyncOpenAI

        combined = b"".join(chunks)
        if len(combined) < 1000:
            return None

        client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("MERLIN_API_KEY"),
        )

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(combined)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as f:
                result = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text",
                )
            return result.strip() if result else None
        except Exception as e:
            log.error("transcription error: %s", e)
            return None
        finally:
            os.unlink(tmp_path)
