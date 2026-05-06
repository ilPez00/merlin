"""Power level engine — estimates social, economic, aesthetic, intellectual power from visual + contextual data.

Adaptive guessing engine: starts broad, narrows over time as more observations are collected."""

import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger("merlin.powers")

POWERS_PATH = Path.home() / ".merlin" / "data" / "power_levels.json"

DEFAULT_POWERS = {
    "social": {"value": 50, "confidence": 0.1, "observations": 0},
    "economic": {"value": 50, "confidence": 0.1, "observations": 0},
    "aesthetic": {"value": 50, "confidence": 0.1, "observations": 0},
    "intellectual": {"value": 50, "confidence": 0.1, "observations": 0},
}


class PowerLevelEngine:
    """Estimates and adapts power levels for scanned people."""

    def __init__(self):
        self.data: dict[str, dict] = {}
        self.load()

    def load(self):
        if POWERS_PATH.exists():
            try:
                self.data = json.loads(POWERS_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        POWERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        POWERS_PATH.write_text(json.dumps(self.data, indent=2))

    def get(self, person_name: str) -> dict:
        """Get power levels for a person. Returns defaults if unknown."""
        key = person_name.lower().strip()
        if key in self.data:
            return self.data[key]
        return dict(DEFAULT_POWERS)

    def update(self, person_name: str, cues: dict) -> dict:
        """Update power levels based on new visual/contextual cues.

        Cues is a dict with keys like:
        { "social": { "clue": "well dressed", "direction": 1 },
          "economic": { "clue": "expensive watch", "direction": 1 },
          "aesthetic": { "clue": "art in background", "direction": 1 },
          "intellectual": { "clue": "bookshelf behind", "direction": 1 } }

        Direction: 1 = increase, -1 = decrease.
        """
        key = person_name.lower().strip()
        current = self.get(person_name)

        for dim, cue in cues.items():
            if dim not in current:
                continue
            direction = cue.get("direction", 0)
            old_val = current[dim]["value"]
            old_conf = current[dim]["confidence"]
            old_obs = current[dim]["observations"]

            # Each observation increases confidence, moves value
            new_obs = old_obs + 1
            new_conf = min(1.0, old_conf + 0.15)
            step = direction * 8 * (1 - new_conf + 0.2)  # bigger steps when less confident
            new_val = max(0, min(100, old_val + step))

            current[dim] = {
                "value": round(new_val, 1),
                "confidence": round(new_conf, 2),
                "observations": new_obs,
                "last_clue": cue.get("clue", ""),
            }

        self.data[key] = current
        self.save()

        log.info("power levels updated for %s: S=%d Ec=%d A=%d I=%d",
                 person_name,
                 current["social"]["value"], current["economic"]["value"],
                 current["aesthetic"]["value"], current["intellectual"]["value"])
        return current

    def summarize(self, person_name: str) -> str:
        """Return a compressed caveman-mode power level summary."""
        pl = self.get(person_name)
        if pl["social"]["observations"] == 0:
            return f"{person_name}: unknown"

        s = pl['social']['value']
        ec = pl['economic']['value']
        a = pl['aesthetic']['value']
        i = pl['intellectual']['value']
        return f"{person_name}: S{s:.0f} Ec{ec:.0f} A{a:.0f} I{i:.0f}"

    def extract_cues_from_ai_text(self, ai_text: str) -> dict:
        """Parse AI observation text for power level cues.

        Looks for keywords that suggest social/economic/aesthetic/intellectual status.
        Returns cues dict for update().
        """
        cues: dict[str, dict] = {}
        t = ai_text.lower()

        # Social power
        social_clues = [
            ("confident", 1), ("well dressed", 1), ("suit", 1), ("tie", 1),
            ("audience", 1), ("crowd", 1), ("leading", 1), ("speaking", 1),
            ("nervous", -1), ("shy", -1), ("alone", -1), ("uniform", 0),
        ]
        for word, direction in social_clues:
            if word in t:
                cues["social"] = {"clue": word, "direction": direction}
                break

        # Economic power
        economic_clues = [
            ("expensive", 1), ("luxury", 1), ("watch", 1), ("suit", 1),
            ("office", 1), ("car", 1), ("restaurant", 1), ("business", 1),
            ("cheap", -1), ("worn", -1), ("old", -1), ("broken", -1),
        ]
        for word, direction in economic_clues:
            if word in t:
                cues["economic"] = {"clue": word, "direction": direction}
                break

        # Aesthetic power
        aesthetic_clues = [
            ("beautiful", 1), ("art", 1), ("design", 1), ("stylish", 1),
            ("fashion", 1), ("minimalist", 1), ("elegant", 1), ("colorful", 1),
            ("messy", -1), ("plain", -1), ("ugly", -1),
        ]
        for word, direction in aesthetic_clues:
            if word in t:
                cues["aesthetic"] = {"clue": word, "direction": direction}
                break

        # Intellectual power
        intellectual_clues = [
            ("book", 1), ("bookshelf", 1), ("laptop", 1), ("code", 1),
            ("scientific", 1), ("research", 1), ("professor", 1), ("student", 1),
            ("diploma", 1), ("degree", 1), ("certificate", 1),
        ]
        for word, direction in intellectual_clues:
            if word in t:
                cues["intellectual"] = {"clue": word, "direction": direction}
                break

        return cues


power_engine = PowerLevelEngine()
