"""
Merlin — Rep Counter
Analyzes pose keypoint streams (MoveNet) to detect exercise repetitions
using heuristics on joint angles and positions.

Keypoint indices (COCO format, 17 keypoints):
  0=nose, 1=L_eye, 2=R_eye, 3=L_ear, 4=R_ear,
  5=L_shoulder, 6=R_shoulder, 7=L_elbow, 8=R_elbow,
  9=L_wrist, 10=R_wrist, 11=L_hip, 12=R_hip,
  13=L_knee, 14=R_knee, 15=L_ankle, 16=R_ankle
"""

import logging
import math
from collections import deque

log = logging.getLogger("merlin.repcounter")

# Number of recent pose frames to keep for pattern analysis
POSE_WINDOW = 15


def _angle(a: dict, b: dict, c: dict) -> float:
    """Angle (degrees) at point b formed by a-b-c."""
    ax, ay = a.get("x", 0), a.get("y", 0)
    bx, by = b.get("x", 0), b.get("y", 0)
    cx, cy = c.get("x", 0), c.get("y", 0)
    v1 = (ax - bx, ay - by)
    v2 = (cx - bx, cy - by)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    m1 = math.hypot(*v1)
    m2 = math.hypot(*v2)
    if m1 * m2 == 0:
        return 0.0
    cos_a = max(-1, min(1, dot / (m1 * m2)))
    return math.degrees(math.acos(cos_a))


def _keypoint(kps: list, idx: int) -> dict | None:
    """Return keypoint dict if confidence > 0.3, else None."""
    if idx < len(kps):
        kp = kps[idx]
        if isinstance(kp, dict) and kp.get("score", 0) > 0.3:
            return kp
    return None


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class RepCounter:
    def __init__(self):
        # Ring buffer of recent pose frames
        self._history: deque[list] = deque(maxlen=POSE_WINDOW)
        # Per-exercise state
        self._state: dict[str, dict] = {}

    def feed(self, keypoints: list) -> dict | None:
        """
        Process a single pose frame. Returns a result dict when a rep is detected,
        or None if no new rep.
        """
        if not keypoints or len(keypoints) < 17:
            return None

        self._history.append(keypoints)

        # Try to detect various exercises
        result = self._detect_pushups() or self._detect_squats() or self._detect_curls()
        return result

    def reset(self, exercise: str | None = None):
        """Reset state for a specific exercise or all exercises."""
        if exercise:
            self._state.pop(exercise, None)
        else:
            self._state.clear()
        self._history.clear()

    # ── Exercise detectors ──────────────────────────────────────────────────────

    def _detect_pushups(self) -> dict | None:
        """
        Pushups: shoulder-to-hip distance oscillates as body goes up/down.
        Track the y-distance between shoulders and hips.
        """
        if len(self._history) < 3:
            return None

        latest = self._history[-1]
        ls = _keypoint(latest, 5)   # L_shoulder
        rs = _keypoint(latest, 6)   # R_shoulder
        lh = _keypoint(latest, 11)  # L_hip
        rh = _keypoint(latest, 12)  # R_hip

        if not all([ls, rs, lh, rh]):
            return None

        # Average shoulder y and hip y
        shoulder_y = (ls["y"] + rs["y"]) / 2
        hip_y = (lh["y"] + rh["y"]) / 2
        dist = hip_y - shoulder_y  # positive when hips below shoulders

        state = self._state.setdefault("pushups", {
            "phase": None,  # "up" or "down"
            "count": 0,
            "set_count": 0,
            "reps_in_set": 0,
            "peak_dist": 0,
            "valley_dist": float("inf"),
            "recent_values": deque(maxlen=10),
        })

        s = state
        s["recent_values"].append(dist)

        if len(s["recent_values"]) < 5:
            return None

        avg_dist = _avg(list(s["recent_values"]))

        if s["phase"] is None:
            s["phase"] = "up" if avg_dist > 0.05 else "down"

        if s["phase"] == "up" and avg_dist < 0.02:
            # Transitioned to down position
            s["phase"] = "down"
            s["valley_dist"] = avg_dist
        elif s["phase"] == "down" and avg_dist > 0.06:
            # Came back up — one rep
            s["phase"] = "up"
            s["count"] += 1
            s["reps_in_set"] += 1
            s["peak_dist"] = avg_dist
            return {
                "exercise": "pushups",
                "total_reps": s["count"],
                "recent_sets": max(1, s["count"] // 10),
            }

        return None

    def _detect_squats(self) -> dict | None:
        """
        Squats: hip y-coordinate oscillates (hip goes down then up).
        """
        if len(self._history) < 3:
            return None

        latest = self._history[-1]
        lh = _keypoint(latest, 11)
        rh = _keypoint(latest, 12)

        if not all([lh, rh]):
            return None

        hip_y = (lh["y"] + rh["y"]) / 2

        state = self._state.setdefault("squats", {
            "phase": None,
            "count": 0,
            "set_count": 0,
            "reps_in_set": 0,
            "recent_hip_y": deque(maxlen=8),
        })

        s = state
        s["recent_hip_y"].append(hip_y)

        if len(s["recent_hip_y"]) < 4:
            return None

        avg = _avg(list(s["recent_hip_y"]))

        if s["phase"] is None:
            s["phase"] = "up" if avg < 0.5 else "down"

        if s["phase"] == "up" and avg > 0.55:
            s["phase"] = "down"
        elif s["phase"] == "down" and avg < 0.45:
            s["phase"] = "up"
            s["count"] += 1
            s["reps_in_set"] += 1
            return {
                "exercise": "squats",
                "total_reps": s["count"],
                "recent_sets": max(1, s["count"] // 10),
            }

        return None

    def _detect_curls(self) -> dict | None:
        """
        Bicep curls: elbow angle oscillates (bends then straightens).
        Track the angle at the elbow formed by shoulder-elbow-wrist.
        Uses both arms and picks the one with clearer signal.
        """
        if len(self._history) < 3:
            return None

        latest = self._history[-1]
        rs = _keypoint(latest, 6)   # R_shoulder
        re = _keypoint(latest, 8)   # R_elbow
        rw = _keypoint(latest, 10)  # R_wrist
        ls = _keypoint(latest, 5)   # L_shoulder
        le = _keypoint(latest, 7)   # L_elbow
        lw = _keypoint(latest, 9)   # L_wrist

        state = self._state.setdefault("curls", {
            "phase": None,
            "count": 0,
            "recent_angle": deque(maxlen=8),
        })
        s = state

        # Try right arm first
        if all([rs, re, rw]):
            angle = _angle(rs, re, rw)
        elif all([ls, le, lw]):
            angle = _angle(ls, le, lw)
        else:
            return None

        s["recent_angle"].append(angle)

        if len(s["recent_angle"]) < 4:
            return None

        avg_angle = _avg(list(s["recent_angle"]))

        if s["phase"] is None:
            s["phase"] = "straight" if avg_angle > 120 else "bent"

        if s["phase"] == "straight" and avg_angle < 90:
            s["phase"] = "bent"
        elif s["phase"] == "bent" and avg_angle > 120:
            s["phase"] = "straight"
            s["count"] += 1
            return {
                "exercise": "curls",
                "total_reps": s["count"],
                "recent_sets": max(1, s["count"] // 10),
            }

        return None
