"""Tier 1 behavioral cues — local pattern matching for name recall, follow-ups, topic bridges.

Runs on every transcription chunk (every ~5s). No LLM calls.
Matches current speech against stored conversation patterns and returns instant cues."""

import json
import logging
import re
import time
from pathlib import Path

log = logging.getLogger("merlin.cues")

CONV_PATH = Path.home() / ".merlin" / "conversations.md"
DATA_DIR = Path.home() / ".merlin" / "data"
CUES_PATH = DATA_DIR / "cues_knowledge.json"

# ── Name patterns (common introductions and name mentions) ─────────────

_NAME_PATTERNS = [
    r"(?:I'm|I am|my name is|meet|this is|say hi to) (\w+(?: \w+)?)",
    r"(?:his name is|her name is|their name is) (\w+(?: \w+)?)",
    r"(?:that's|this is|meet) (\w+(?: \w+)?)(?:,|\s|$)",
]

_FOLLOWUP_PATTERNS = [
    r"(?:I'?ll|I will|I can|let me|going to) (send|share|forward|email|ping|upload|attach|check|look|review|get back|follow up)",
    r"(?:promise|owe you|remind me|note to self)",
    r"(?:you should|you could|try|have you considered)",
]

_QUESTION_PATTERNS = [
    r".*\?$",
    r"(?:can you|could you|would you|will you|are you|did you|have you|do you)",
]

_ACHIEVEMENT_PATTERNS = [
    r"(?:finished|completed|did|ran|walked|climbed|read|wrote|built|shipped|launched)",
    r"(?:got|won|earned|achieved|hit|reached|broke|passed)",
    r"(?:marathon|race|event|promotion|interview|contest|competition)",
]

_COMPLIMENT_TRIGGERS = [
    r"(?:congrats|congratulations|awesome|great job|well done|amazing|proud)",
]

_TOPIC_KEYWORDS = [
    r"(?:working on|building|developing|learning|studying|reading|watching|playing|thinking about)",
]


class KnowledgeBase:
    """Stored knowledge extracted from past conversations."""

    def __init__(self):
        self.people: dict[str, dict] = {}
        self.topics: dict[str, dict] = {}
        self.open_questions: list[dict] = []
        self.promised_actions: list[dict] = []
        self.last_build: float = 0

    def load(self):
        if CUES_PATH.exists():
            try:
                data = json.loads(CUES_PATH.read_text())
                self.people = data.get("people", {})
                self.topics = data.get("topics", {})
                self.open_questions = data.get("open_questions", [])
                self.promised_actions = data.get("promised_actions", [])
                self.last_build = data.get("last_build", 0)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "people": self.people,
            "topics": self.topics,
            "open_questions": self.open_questions,
            "promised_actions": self.promised_actions,
            "last_build": self.last_build,
        }
        CUES_PATH.write_text(json.dumps(data, indent=2))

    def add_person(self, name: str, context: str):
        if name not in self.people:
            self.people[name] = {"contexts": [], "last_mentioned": time.time()}
        if context and context not in self.people[name].setdefault("contexts", []):
            self.people[name]["contexts"].append(context)
            if len(self.people[name]["contexts"]) > 5:
                self.people[name]["contexts"] = self.people[name]["contexts"][-5:]
        self.people[name]["last_mentioned"] = time.time()

    def add_topic(self, topic: str, context: str):
        key = topic.lower()
        if key not in self.topics:
            self.topics[key] = {"variations": [], "contexts": [], "last_mentioned": time.time()}
        if topic not in self.topics[key].setdefault("variations", []):
            self.topics[key]["variations"].append(topic)
        if context and len(self.topics[key].setdefault("contexts", [])) < 10:
            self.topics[key]["contexts"].append(context)
        self.topics[key]["last_mentioned"] = time.time()

    def add_open_question(self, asked_by: str, question: str):
        self.open_questions.append({
            "asked_by": asked_by,
            "question": question,
            "timestamp": time.time(),
        })
        # Keep last 50
        self.open_questions = self.open_questions[-50:]

    def add_promised_action(self, promised_to: str, action: str):
        self.promised_actions.append({
            "promised_to": promised_to,
            "action": action,
            "timestamp": time.time(),
        })
        self.promised_actions = self.promised_actions[-30:]

    def remove_resolved_question(self, question_text: str):
        self.open_questions = [q for q in self.open_questions if q["question"] != question_text]


knowledge = KnowledgeBase()


# ── Conversation scanner ──────────────────────────────────────────────

def scan_conversations():
    """Scan ~/.merlin/conversations.md and extract people, topics, questions, promises."""
    if not CONV_PATH.exists():
        return

    try:
        text = CONV_PATH.read_text(encoding="utf-8")
    except OSError:
        return

    lines = text.strip().split("\n")
    user_lines = []
    for line in lines:
        if line.startswith("**You**"):
            user_lines.append(line)

    for line in user_lines:
        text = line.replace("**You**: ", "").strip()

        # Extract names
        for pat in _NAME_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                name = m.group(1).strip().title()
                if name and len(name) > 2 and name.lower() not in ("i'm", "i am", "my", "his", "her", "their"):
                    # Extract surrounding context
                    idx = text.find(m.group(0))
                    ctx = text[max(0, idx - 40):idx + len(m.group(0)) + 40].strip()
                    knowledge.add_person(name, ctx)

        # Extract topics
        for pat in _TOPIC_KEYWORDS:
            for m in re.finditer(pat + r" (.+?)(?:\.|,|$)", text, re.IGNORECASE):
                topic = m.group(1).strip()
                if topic and len(topic) < 60:
                    knowledge.add_topic(topic, text[:80])

        # Extract promises
        for pat in _FOLLOWUP_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                action = text[m.start():m.end() + 40].strip()[:80]
                knowledge.add_promised_action("(from conversation)", action)

        # Extract questions from user lines that end with ?
        if text.strip().endswith("?"):
            knowledge.add_open_question("(past conversation)", text[:80])

    knowledge.last_build = time.time()
    knowledge.save()
    log.info("scanned conversations: %d people, %d topics, %d questions, %d promises",
             len(knowledge.people), len(knowledge.topics),
             len(knowledge.open_questions), len(knowledge.promised_actions))


# ── Live cue matcher ──────────────────────────────────────────────────

def match_cues(transcript: str) -> list[dict]:
    """Check current transcript against knowledge base. Returns list of cue dicts.

    Each cue: {"type": str, "text": str, "priority": int}
    """
    cues = []

    if not transcript or len(transcript) < 3:
        return cues

    text_lower = transcript.lower()

    # 1. Name recall — is the user talking to/about someone we know?
    for name, info in knowledge.people.items():
        name_lower = name.lower()
        first_name = name.split()[0].lower()
        if first_name in text_lower and len(first_name) > 2:
            contexts = info.get("contexts", [])
            ctx_str = ""
            if contexts:
                ctx_str = f" — {contexts[0]}"
            # Check for open questions from this person
            pending = [q for q in knowledge.open_questions if name_lower in q.get("asked_by", "").lower()]
            if pending:
                cues.append({
                    "type": "follow_up",
                    "text": f"He asked about: \"{pending[0]['question']}\" — bring it up.",
                    "priority": 8,
                })
            else:
                cues.append({
                    "type": "name_recall",
                    "text": f"That's {name}{ctx_str}",
                    "priority": 6,
                })
            break  # One name cue per transcript

    # 2. Follow-up detection — did we promise something?
    for action in knowledge.promised_actions[:3]:
        for word in action["action"].lower().split()[:5]:
            if word in text_lower and len(word) > 3:
                cues.append({
                    "type": "follow_up",
                    "text": f"You promised to {action['action'][:60]} — mention it's done.",
                    "priority": 7,
                })
                break

    # 3. Topic bridge — is current transcript similar to past topics?
    for topic_key, info in knowledge.topics.items():
        for var in info.get("variations", [topic_key]):
            if var.lower() in text_lower and len(var) > 3:
                contexts = info.get("contexts", [])
                if contexts:
                    cues.append({
                        "type": "topic_bridge",
                        "text": f"You dealt with this before: {contexts[0][:80]}",
                        "priority": 5,
                    })
                break

    # 4. Achievement / compliment trigger
    for pat in _ACHIEVEMENT_PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            cues.append({
                "type": "compliment",
                "text": "They mentioned an achievement — say congrats.",
                "priority": 4,
            })
            break

    # Deduplicate by text (keep highest priority)
    seen = set()
    unique = []
    for c in sorted(cues, key=lambda x: -x["priority"]):
        if c["text"] not in seen:
            seen.add(c["text"])
            unique.append(c)
    return unique[:2]  # max 2 cues per tick


# ── Cue processor (called from voice pipeline) ───────────────────────

_last_scan_time = 0


def process_transcript(transcript: str) -> list[dict]:
    """Main entry point. Called every ~5s from the voice pipeline.

    Returns list of cue dicts to display, or empty list.
    """
    global _last_scan_time

    # Re-scan conversations every 60s
    now = time.time()
    if now - _last_scan_time > 60:
        _last_scan_time = now
        scan_conversations()

    # Also scan on first call
    if not knowledge.people and not knowledge.topics:
        scan_conversations()

    return match_cues(transcript)
