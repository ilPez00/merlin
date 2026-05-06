"""
PC microphone listener.
Records from default mic → feeds RingBuffer → runs local Whisper every CHUNK_SEC →
checks for wake word → fires on_command(text) coroutine.
"""

import asyncio
import logging
import threading
import time
from typing import Callable, Awaitable

import numpy as np

from .buffer import RingBuffer, SAMPLE_RATE
from .transcriber import Transcriber
from .wake import WakeWordDetector

log = logging.getLogger("merlin.mic")

CHUNK_SEC = 2
SILENCE_RMS = 150  # int16 RMS below this = silence, skip transcription


class MicListener:
    def __init__(
        self,
        on_command: Callable[[str], Awaitable[None]],
        wake_words: list[str] | None = None,
    ):
        self._ring = RingBuffer(seconds=30)
        self._transcriber = Transcriber()
        self._wake = WakeWordDetector(wake_words)
        self._on_command = on_command
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Public ───────────────────────────────────────────────────────────────────

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._running = True
        t = threading.Thread(target=self._record_loop, daemon=True, name="merlin-mic")
        t.start()
        asyncio.ensure_future(self._transcribe_loop(), loop=self._loop)
        log.info("mic listener started (wake words: %s)", self._wake.words)

    def stop(self) -> None:
        self._running = False

    # ── Internal — recording (runs in background thread) ─────────────────────────

    def _record_loop(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            log.error("sounddevice not installed; run: pip install sounddevice")
            return

        def _cb(indata: np.ndarray, frames: int, t_info, status):
            samples = (indata[:, 0] * 32767).astype(np.int16)
            self._ring.write(samples)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=SAMPLE_RATE // 10,  # 100ms blocks
                callback=_cb,
            ):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            log.error("mic input error: %s", e)

    # ── Internal — transcription + wake detection (asyncio task) ─────────────────

    async def _transcribe_loop(self) -> None:
        while self._running:
            await asyncio.sleep(CHUNK_SEC)
            try:
                await self._process_chunk()
            except Exception as e:
                log.error("transcribe loop error: %s", e)

    async def _process_chunk(self) -> None:
        chunk = self._ring.read(CHUNK_SEC)
        if len(chunk) < SAMPLE_RATE // 4:
            return

        rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        if rms < SILENCE_RMS:
            return

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, self._transcriber.transcribe, chunk, SAMPLE_RATE
        )
        if not text:
            return

        matched = self._wake.check(text)
        if matched:
            command = self._wake.strip_wake(text).strip()
            if command:
                log.info("wake='%s' command='%s'", matched, command)
                asyncio.ensure_future(self._on_command(command))
            else:
                log.info("wake word '%s' with no command — listening...", matched)
