"""Frame relevance system — stores, scores, prunes, and retrieves captured frames.

Every captured frame gets scored and the top N are retained as visual memory."""

import base64
import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger("merlin.frames")

FRAMES_DIR = Path.home() / ".merlin" / "frames"
MAX_FRAMES = 50  # default, configurable


class FrameStore:
    def __init__(self):
        FRAMES_DIR.mkdir(parents=True, exist_ok=True)
        self.max_frames = MAX_FRAMES

    # ── Save a frame ─────────────────────────────

    def save(self, frame_b64: str, mode: str = "", ai_text: str = "", keywords: list[str] = None) -> str:
        """Save a frame with metadata. Returns frame ID (ISO timestamp)."""
        fid = time.strftime("%Y%m%d_%H%M%S") + f"_{os.urandom(2).hex()}"

        # Decode and save JPEG
        try:
            img_data = base64.b64decode(frame_b64)
            (FRAMES_DIR / f"{fid}.jpg").write_bytes(img_data)
        except Exception as e:
            log.warning("frame save error: %s", e)
            return ""

        # Save metadata
        meta = {
            "id": fid,
            "timestamp": time.time(),
            "mode": mode,
            "ai_text": ai_text[:500] if ai_text else "",
            "keywords": keywords or [],
            "referenced_in": [],
            "dossier_people": [],
            "is_favorite": False,
            "score": 50.0,  # base score for user tap
            "file_jpg": f"{fid}.jpg",
        }
        self._write_meta(fid, meta)

        # Score boost for keywords in AI text
        if ai_text:
            # Detect object names (nouns capitalized or after "a" / "the")
            detected = set(re.findall(r'\b([A-Z][a-z]+|[a-z]+)\b', ai_text))
            meta["keywords"] = list(detected)[:10]
            meta["score"] += min(30, len(detected) * 3)
            self._write_meta(fid, meta)

        self._prune()
        log.info("frame saved: %s (score %.1f)", fid, meta["score"])
        return fid

    def save_from_bytes(self, jpeg_bytes: bytes, mode: str = "", ai_text: str = "") -> str:
        """Save from raw JPEG bytes."""
        b64 = base64.b64encode(jpeg_bytes).decode()
        return self.save(b64, mode, ai_text)

    # ── Scoring updates ──────────────────────────

    def mark_referenced(self, fid: str):
        """Increment score when a frame is mentioned in conversation."""
        meta = self._read_meta(fid)
        if meta:
            meta["score"] += 20
            meta["referenced_in"] = meta.get("referenced_in", [])
            meta["referenced_in"].append(time.time())
            if len(meta["referenced_in"]) > 10:
                meta["referenced_in"] = meta["referenced_in"][-10:]
            self._write_meta(fid, meta)

    def mark_favorite(self, fid: str):
        """Mark a frame as favorite (never pruned)."""
        meta = self._read_meta(fid)
        if meta:
            meta["is_favorite"] = True
            meta["score"] = 999
            self._write_meta(fid, meta)

    def add_dossier_match(self, fid: str, person: str):
        """Boost score when frame content matches a dossier person."""
        meta = self._read_meta(fid)
        if meta:
            meta["score"] += 15
            people = meta.get("dossier_people", [])
            if person not in people:
                people.append(person)
            meta["dossier_people"] = people
            self._write_meta(fid, meta)

    # ── Query ────────────────────────────────────

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search frames by keyword, mode, or date."""
        results = []
        query_lower = query.lower()

        for fname in sorted(os.listdir(FRAMES_DIR)):
            if not fname.endswith(".json"):
                continue
            meta = self._read_meta(fname.replace(".json", ""))
            if not meta:
                continue

            text = (meta.get("ai_text", "") + " " + " ".join(meta.get("keywords", []))).lower()
            if query_lower in text or query_lower in meta.get("mode", "").lower():
                results.append(meta)

        results.sort(key=lambda m: -m.get("score", 0))
        return results[:max_results]

    def get(self, fid: str) -> dict | None:
        return self._read_meta(fid)

    def get_image_b64(self, fid: str) -> str | None:
        meta = self._read_meta(fid)
        if not meta:
            return None
        jpg_path = FRAMES_DIR / meta.get("file_jpg", f"{fid}.jpg")
        if jpg_path.exists():
            return base64.b64encode(jpg_path.read_bytes()).decode()
        return None

    def recent(self, n: int = 10) -> list[dict]:
        """Return the N most recent frames by timestamp."""
        metas = []
        for fname in sorted(os.listdir(FRAMES_DIR)):
            if not fname.endswith(".json"):
                continue
            meta = self._read_meta(fname.replace(".json", ""))
            if meta:
                metas.append(meta)
        metas.sort(key=lambda m: -m.get("timestamp", 0))
        return metas[:n]

    def top(self, n: int = 10) -> list[dict]:
        """Return the N highest-scoring frames."""
        metas = []
        for fname in sorted(os.listdir(FRAMES_DIR)):
            if not fname.endswith(".json"):
                continue
            meta = self._read_meta(fname.replace(".json", ""))
            if meta:
                metas.append(meta)
        metas.sort(key=lambda m: -m.get("score", 0))
        return metas[:n]

    # ── Pruning ──────────────────────────────────

    def _prune(self):
        """Remove lowest-scoring non-favorite frames if over max."""
        metas = []
        for fname in sorted(os.listdir(FRAMES_DIR)):
            if not fname.endswith(".json"):
                continue
            meta = self._read_meta(fname.replace(".json", ""))
            if meta:
                metas.append(meta)

        if len(metas) <= self.max_frames:
            return

        # Sort by score ascending, keep favorites at the end
        non_fav = [m for m in metas if not m.get("is_favorite")]
        fav = [m for m in metas if m.get("is_favorite")]
        non_fav.sort(key=lambda m: m.get("score", 0))

        to_remove = len(metas) - self.max_frames
        for meta in non_fav[:to_remove]:
            self._delete_frame(meta["id"])
            log.info("pruned frame: %s (score %.1f)", meta["id"], meta.get("score", 0))

    def _delete_frame(self, fid: str):
        """Delete frame files."""
        for ext in [".jpg", ".json"]:
            p = FRAMES_DIR / f"{fid}{ext}"
            if p.exists():
                p.unlink()

    # ── Persistence helpers ──────────────────────

    def _write_meta(self, fid: str, meta: dict):
        (FRAMES_DIR / f"{fid}.json").write_text(json.dumps(meta, indent=2))

    def _read_meta(self, fid: str) -> dict | None:
        p = FRAMES_DIR / f"{fid}.json"
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return None


frames = FrameStore()
