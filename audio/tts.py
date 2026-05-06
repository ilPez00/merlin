import asyncio
import logging
import os
import tempfile

log = logging.getLogger("merlin.tts")

VOICE = os.environ.get("MERLIN_TTS_VOICE", "en-US-JennyNeural")
_PLAYER_CMD = (
    "mpg123 -q {f} 2>/dev/null || "
    "ffplay -nodisp -autoexit -loglevel quiet {f} 2>/dev/null || "
    "aplay {f} 2>/dev/null"
)


async def speak(text: str, voice: str | None = None) -> None:
    text = text.strip()
    if not text:
        return
    try:
        import edge_tts
    except ImportError:
        log.warning("edge-tts not installed; run: pip install edge-tts")
        return

    v = voice or VOICE
    tmp = None
    try:
        communicate = edge_tts.Communicate(text, v)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = f.name
        await communicate.save(tmp)
        cmd = _PLAYER_CMD.format(f=tmp)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except Exception as e:
        log.warning("TTS error: %s", e)
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
