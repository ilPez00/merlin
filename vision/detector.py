"""
Merlin — YOLO11n local object detector.
Runs on PC CPU (~30ms/frame for yolo11n).  Processes JPEG bytes from the
phone camera before the result is sent to the LLM.

Why: avoids encoding every frame as base64 and paying vision-token cost for
routine scouting frames.  SCOUT/NAV modes get a text summary; only ANALYZE
mode sends the raw image to the LLM.
"""

import asyncio
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("merlin.vision")

_model = None
_load_attempted = False

# Confidence threshold — below this, detections are ignored
CONF_THRESHOLD = 0.35

# Classes to always include even at lower confidence (people, vehicles)
HIGH_PRIORITY = {
    "person", "car", "truck", "bus", "motorcycle", "bicycle",
    "traffic light", "stop sign", "fire hydrant",
}


def _load_model():
    global _model, _load_attempted
    if _load_attempted:
        return _model
    _load_attempted = True
    try:
        from ultralytics import YOLO
        log.info("loading YOLO11n (first run downloads ~6MB)...")
        _model = YOLO("yolo11n.pt")
        log.info("YOLO11n ready")
    except ImportError:
        log.warning("ultralytics not installed: pip install ultralytics")
    except Exception as e:
        log.warning("YOLO load failed: %s", e)
    return _model


@dataclass
class DetectionResult:
    counts: dict[str, int] = field(default_factory=dict)
    confidences: dict[str, float] = field(default_factory=dict)  # max conf per class

    def to_context(self) -> str:
        if not self.counts:
            return ""
        parts = []
        # Sort: high-priority first, then by count desc
        for name, n in sorted(
            self.counts.items(),
            key=lambda kv: (kv[0] not in HIGH_PRIORITY, -kv[1]),
        ):
            conf = self.confidences.get(name, 0)
            parts.append(f"{name}×{n}({conf:.0%})")
        return "[objects] " + ", ".join(parts)

    @property
    def is_empty(self) -> bool:
        return not self.counts


def detect_sync(jpeg_bytes: bytes) -> Optional[DetectionResult]:
    """Synchronous detection — call from run_in_executor."""
    model = _load_model()
    if model is None:
        return None
    if not jpeg_bytes:
        return None

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        results = model(img, conf=CONF_THRESHOLD, verbose=False)
        if not results:
            return DetectionResult()

        r = results[0]
        counts: dict[str, int] = {}
        confs: dict[str, float] = {}

        for box in r.boxes:
            cls_id = int(box.cls[0])
            name = model.names[cls_id]
            c = float(box.conf[0])
            counts[name] = counts.get(name, 0) + 1
            if c > confs.get(name, 0.0):
                confs[name] = c

        return DetectionResult(counts=counts, confidences=confs)
    except Exception as e:
        log.warning("detect error: %s", e)
        return None


async def detect(jpeg_bytes: bytes) -> Optional[DetectionResult]:
    """Async wrapper — runs detection in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, detect_sync, jpeg_bytes)
