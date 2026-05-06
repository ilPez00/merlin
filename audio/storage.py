import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("merlin.audio.storage")

STORAGE_DIR = Path.home() / ".merlin" / "audio_buffer"
METADATA_FILE = STORAGE_DIR / "index.json"


class AudioStorage:
    """Manages the rolling audio buffer on disk + weekly cleanup."""

    def __init__(self, storage_dir: str | Path = STORAGE_DIR):
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index: dict = self._load_index()
        self._triggered_ids: set[str] = set()

    # ── Save ────────────────────────────────────

    def save_transcript(self, timestamp: float, text: str, audio: bytes | None = None) -> str:
        """Save a transcript chunk. Returns the chunk id (ISO timestamp)."""
        ts = datetime.fromtimestamp(timestamp)
        chunk_id = ts.strftime("%Y-%m-%d_%H-%M-%S")
        txt_path = self.dir / f"{chunk_id}.txt"
        txt_path.write_text(text, encoding="utf-8")

        entry = {
            "id": chunk_id,
            "timestamp": timestamp,
            "text": text[:200],
            "triggered": False,
            "txt_file": str(txt_path.name),
        }

        if audio:
            pcm_path = self.dir / f"{chunk_id}.pcm"
            pcm_path.write_bytes(audio)
            entry["pcm_file"] = str(pcm_path.name)
            entry["pcm_bytes"] = len(audio)

        self._index["chunks"][chunk_id] = entry
        self._save_index()
        return chunk_id

    def mark_triggered(self, chunk_id: str):
        if chunk_id in self._index.get("chunks", {}):
            self._index["chunks"][chunk_id]["triggered"] = True
            self._triggered_ids.add(chunk_id)
            self._save_index()

    # ── Query ────────────────────────────────────

    def get_recent_text(self, seconds: int = 60) -> str:
        """Return concatenated transcripts from the last N seconds."""
        cutoff = time.time() - seconds
        texts = []
        for cid, entry in sorted(self._index.get("chunks", {}).items()):
            if entry["timestamp"] >= cutoff:
                texts.append(entry.get("text", ""))
        return "\n".join(t for t in texts if t)

    def get_triggered_texts(self) -> list[dict]:
        """Return all chunks that triggered a wake word, with their text."""
        result = []
        for cid, entry in self._index.get("chunks", {}).items():
            if entry.get("triggered"):
                txt = (self.dir / entry["txt_file"]).read_text(encoding="utf-8") if entry.get("txt_file") else ""
                result.append({"id": cid, "timestamp": entry["timestamp"], "text": txt})
        return result

    # ── Cleanup ─────────────────────────────────

    def cleanup_old(self, max_days: int = 7):
        """Delete chunks older than max_days that are NOT triggered."""
        cutoff = time.time() - max_days * 86400
        deleted = 0
        to_remove = []
        for cid, entry in self._index.get("chunks", {}).items():
            if entry["timestamp"] < cutoff and not entry.get("triggered"):
                self._delete_chunk_files(entry)
                to_remove.append(cid)
                deleted += 1
        for cid in to_remove:
            del self._index["chunks"][cid]
        if deleted:
            self._save_index()
            log.info("cleaned %d old audio chunks (>%d days)", deleted, max_days)
        return deleted

    def _delete_chunk_files(self, entry: dict):
        for key in ("txt_file", "pcm_file"):
            fname = entry.get(key)
            if fname:
                fpath = self.dir / fname
                if fpath.exists():
                    fpath.unlink()

    # ── Index persistence ────────────────────────

    def _load_index(self) -> dict:
        if METADATA_FILE.exists():
            try:
                return json.loads(METADATA_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"created": time.time(), "chunks": {}}

    def _save_index(self):
        METADATA_FILE.write_text(json.dumps(self._index, indent=2))
