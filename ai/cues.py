"""Cue engine — delegates to dossiers for matching, triggers LLM updates periodically."""

import time
import logging

from ai.dossiers import dossiers

log = logging.getLogger("merlin.cues")

_last_update_time = 0


def process_transcript(transcript: str) -> list[dict]:
    """Main entry point. Called every ~5s from the voice pipeline.

    Triggers dossier LLM update every 60s, then runs local cue matching.
    Returns list of cue dicts (max 2) or empty list.
    """
    global _last_update_time

    now = time.time()

    # Trigger dossier update every 60s (runs async in background)
    if now - _last_update_time > 60:
        _last_update_time = now
        _trigger_dossier_update()

    # Local cue matching (instant, no LLM)
    return dossiers.match_cues(transcript)


async def _trigger_dossier_update():
    """Run dossier LLM update."""
    try:
        await dossiers.update_from_conversations()
    except Exception as e:
        log.debug("dossier update error: %s", e)
