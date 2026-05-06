"""Voice command parser — intercepts wake-word-triggered text for local actions.

Patterns matched BEFORE sending to the LLM, saving latency and tokens.
If no pattern matches, returns None — caller falls through to agent."""

import re
import logging

log = logging.getLogger("merlin.command")

COMMANDS = {
    # Navigation
    r"^(up|scroll up|show more)$": ("scroll", "up"),
    r"^(down|scroll down|show less)$": ("scroll", "down"),
    r"^show (?P<widget>\w+)$": ("show_widget", None),

    # Mode switching
    r"^(switch to|go to|set mode|change to) (?P<mode>work|lift|walk|talk|notes|scout|recon|drive|ski)$": (
        "switch_mode", None,
    ),
    r"^(work mode|lift mode|walk mode|talk mode|notes mode|scout mode|recon mode|drive mode|ski mode)$": (
        "switch_mode", None,
    ),

    # Data queries (handled by agent, but parse the intent)
    r"^(how tired am I|am I tired|my energy level)$": ("query", "tiredness"),
    r"^(show|what are) (my )?todo(s| list)?$": ("query", "todos"),
    r"^(show|how many) (my )?(calories|kcal|steps)( today)?$": ("query", "fitness"),
    r"^(show|how much) (did I |have I )?spend(ing)?( today)?$": ("query", "spending"),
    r"^(show|what's|what is) (my )?(schedule|calendar)( today)?$": ("query", "schedule"),
    r"^(what (did|have) I (eat|consumed)|show (my )?meals)( today)?$": ("query", "nutrition"),

    # Prep notes
    r"^(take a note|note this down|write this down)$": ("action", "prep_note"),
    r"^summarize (the )?(conversation|meeting|call)$": ("action", "summary"),

    # App control
    r"^(switch to visor|visor mode)$": ("app_mode", "visor"),
    r"^(switch to copilot|copilot mode)$": ("app_mode", "copilot"),
    r"^(go|enter) incognito( mode)?$": ("app_mode", "incognito"),
}

# Extract capture groups
_re_compile = [(re.compile(p, re.IGNORECASE), action) for p, action in COMMANDS.items()]


def parse(text: str) -> tuple | None:
    """Parse a command from wake-word-triggered text.

    Returns (action_type, payload) on match, or None to fall through to agent.
    """
    if not text:
        return None

    t = text.strip().lower()
    for pattern, (action, default_payload) in _re_compile:
        m = pattern.search(t)
        if m:
            # Extract named groups
            payload = default_payload
            groups = m.groupdict()
            if "mode" in groups:
                payload = groups["mode"].upper()
            elif "widget" in groups:
                payload = groups["widget"].lower()
            log.info("command match: %s → (%s, %s)", pattern.pattern, action, payload)
            return (action, payload)

    return None
