import numpy as np
import os
import tempfile
import wave
import logging

log = logging.getLogger("merlin.audio")

try:
    import whisper
    _MODEL = None
except ImportError:
    whisper = None
    _MODEL = None


def _get_model():
    global _MODEL
    if whisper is None:
        return None
    if _MODEL is None:
        log.info("loading whisper tiny...")
        _MODEL = whisper.load_model("tiny")
    return _MODEL


class Transcriber:
    def __init__(self, language: str = "en"):
        self.language = language
        self._model = None

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        model = _get_model()
        if model is None:
            return "[whisper not installed]"
        try:
            result = model.transcribe(
                audio.astype(np.float32) / 32768.0,
                language=self.language,
                fp16=False,
                temperature=0,
            )
            return (result.get("text") or "").strip()
        except Exception as e:
            log.warning("transcription error: %s", e)
            return ""

    def transcribe_file(self, path: str) -> str:
        model = _get_model()
        if model is None:
            return "[whisper not installed]"
        try:
            result = model.transcribe(
                path,
                language=self.language,
                fp16=False,
                temperature=0,
            )
            return (result.get("text") or "").strip()
        except Exception as e:
            log.warning("transcription error: %s", e)
            return ""

    @staticmethod
    def save_wav(audio: np.ndarray, path: str, sample_rate: int = 16000):
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())
