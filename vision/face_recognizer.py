"""
Merlin — Face recognition via face_recognition (dlib ResNet).
Enrolled faces stored as 128-d encodings in ~/.merlin/faces/<name>.npy.
Multiple photos per person supported (average encoding used at enroll time).
"""

import io
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("merlin.faces")

FACES_DIR = Path.home() / ".merlin" / "faces"
TOLERANCE = 0.52        # lower = stricter. 0.6 is library default; 0.52 reduces false positives
MIN_FACE_SIZE = 40      # pixels — ignore tiny faces (noise at distance)
_fr = None              # lazy-loaded face_recognition module


def _lib():
    global _fr
    if _fr is None:
        try:
            import face_recognition as _face_recognition
            _fr = _face_recognition
        except ImportError:
            raise RuntimeError("face_recognition not installed: pip install face_recognition")
    return _fr


def _faces_dir() -> Path:
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    return FACES_DIR


# ── Enrollment ────────────────────────────────────────────────────────────────

def enroll_sync(name: str, jpeg_bytes: bytes) -> str:
    """
    Extract face encoding from jpeg_bytes and save under name.
    Adds to existing encodings if the person was already enrolled.
    Returns a status string.
    """
    fr = _lib()
    img = _jpeg_to_rgb(jpeg_bytes)
    if img is None:
        return "Error: could not decode image."

    locs = fr.face_locations(img, model="hog")
    if not locs:
        return "No face detected in the image. Try again with better lighting or move closer."

    # Filter tiny faces
    locs = [loc for loc in locs if (loc[2] - loc[0]) >= MIN_FACE_SIZE]
    if not locs:
        return "Face detected but too small. Move closer to the camera."

    if len(locs) > 1:
        log.info("enroll: %d faces found, using largest", len(locs))
        locs = [max(locs, key=lambda l: (l[2] - l[0]) * (l[1] - l[3]))]

    encodings = fr.face_encodings(img, locs)
    if not encodings:
        return "Could not generate face encoding. Try again."

    new_enc = encodings[0]
    path = _faces_dir() / f"{_safe(name)}.npy"

    if path.exists():
        existing = np.load(str(path))
        if existing.ndim == 1:
            existing = existing[np.newaxis, :]
        combined = np.vstack([existing, new_enc[np.newaxis, :]])
    else:
        combined = new_enc[np.newaxis, :]

    np.save(str(path), combined)
    count = combined.shape[0]
    log.info("enrolled '%s' (%d encoding(s))", name, count)
    return f"Enrolled {name} ({count} photo(s) saved). Recognition will improve with more photos."


def forget_sync(name: str) -> str:
    """Remove all stored encodings for a person."""
    path = _faces_dir() / f"{_safe(name)}.npy"
    if not path.exists():
        return f"'{name}' not found in face database."
    path.unlink()
    log.info("removed face data for '%s'", name)
    return f"Removed {name} from face database."


def list_enrolled() -> list[str]:
    """Return list of enrolled names."""
    return sorted(
        p.stem for p in _faces_dir().glob("*.npy")
    )


# ── Recognition ───────────────────────────────────────────────────────────────

from dataclasses import dataclass, field

@dataclass
class FaceResult:
    name: str
    confidence: float   # 0-1, higher = more confident
    location: tuple     # (top, right, bottom, left)

    @property
    def is_unknown(self) -> bool:
        return self.name == "Unknown"


def recognize_sync(jpeg_bytes: bytes) -> list[FaceResult]:
    """
    Detect and identify all faces in jpeg_bytes.
    Returns list of FaceResult (may include 'Unknown' entries).
    """
    fr = _lib()
    img = _jpeg_to_rgb(jpeg_bytes)
    if img is None:
        return []

    locs = fr.face_locations(img, model="hog")
    if not locs:
        return []

    locs = [loc for loc in locs if (loc[2] - loc[0]) >= MIN_FACE_SIZE]
    if not locs:
        return []

    encodings = fr.face_encodings(img, locs)

    # Load known faces
    known_names, known_encs = _load_known()
    results: list[FaceResult] = []

    for loc, enc in zip(locs, encodings):
        if not known_encs:
            results.append(FaceResult("Unknown", 0.0, loc))
            continue

        distances = fr.face_distance(known_encs, enc)
        best_idx = int(np.argmin(distances))
        best_dist = float(distances[best_idx])

        if best_dist <= TOLERANCE:
            confidence = round(1.0 - best_dist, 2)
            results.append(FaceResult(known_names[best_idx], confidence, loc))
        else:
            results.append(FaceResult("Unknown", 0.0, loc))

    return results


def to_context(results: list[FaceResult]) -> str:
    if not results:
        return ""
    known = [r for r in results if not r.is_unknown]
    unknown_n = sum(1 for r in results if r.is_unknown)
    parts = [f"{r.name}({r.confidence:.0%})" for r in known]
    if unknown_n:
        parts.append(f"Unknown×{unknown_n}")
    return "[faces] " + ", ".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jpeg_to_rgb(jpeg_bytes: bytes) -> Optional[np.ndarray]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        return np.array(img)
    except Exception as e:
        log.warning("image decode error: %s", e)
        return None


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip())


_known_cache: Optional[tuple[list[str], list[np.ndarray]]] = None
_known_mtime: float = 0.0


def _load_known() -> tuple[list[str], list[np.ndarray]]:
    """Load known face encodings, cached until files change."""
    global _known_cache, _known_mtime

    faces_dir = _faces_dir()
    files = sorted(faces_dir.glob("*.npy"))
    if not files:
        return [], []

    latest_mtime = max(f.stat().st_mtime for f in files)
    if _known_cache is not None and latest_mtime <= _known_mtime:
        return _known_cache

    names: list[str] = []
    encs: list[np.ndarray] = []
    for f in files:
        try:
            data = np.load(str(f))
            if data.ndim == 1:
                data = data[np.newaxis, :]
            for enc in data:
                names.append(f.stem)
                encs.append(enc)
        except Exception as e:
            log.warning("could not load face data %s: %s", f.name, e)

    _known_cache = (names, encs)
    _known_mtime = latest_mtime
    log.debug("loaded %d face encoding(s) for %d person(s)", len(encs), len(files))
    return names, encs


def invalidate_cache():
    global _known_cache
    _known_cache = None
