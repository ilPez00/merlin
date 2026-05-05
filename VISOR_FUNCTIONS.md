# Merlin Visor — Activity-Based AI Glasses

## The system

The Merlin Visor is a wearable AI interface that mounts on glasses. It gathers sensor data from your surroundings and voice, processes it on a PC server through an agentic AI, and shows you only what matters for what you're doing right now — a horse blindfold for attention, not a firehose.

```
  ┌────────────┐    ┌──────────────┐    ┌────────────┐
  │  ON GLASSES│    │  ON PC SERVER│    │  ON CLOUD  │
  │            │    │              │    │            │
  │ Sensors    │───>│ Stream       │───>│ LLM        │
  │ Display    │<───│ Processor    │<───│ (DeepSeek  │
  │ Input      │    │ Agent loop   │    │  / Claude) │
  │            │    │ MCP client   │───>│ Praxis API │
  └────────────┘    └──────────────┘    └────────────┘
```

---

## 7 core capabilities

### 1. GATHER — sensors capture surroundings + voice

| Sensor | Data | Rate per mode | Purpose |
|---|---|---|---|
| Camera (forward) | JPEG 640×480 q0.65 | 0–1 fps configurable | Visual context for AI |
| Microphone | PCM 16kHz 16bit mono | 4s chunks or push-to-talk | Audio transcription, voice commands |
| IMU (MPU6050) | ax, ay, az, gx, gy, gz JSON | 20 Hz | Motion context, gesture detection |
| GPS (NEO-6M) | lat, lon, alt, speed JSON | 1 Hz | Location context, nav |
| Encoder / ring | scroll, click, double-click, press | Event-driven | User intent, mode switching |
| Battery | voltage level | 1/min | Power management |

Every mode turns sensors on/off and sets their rates independently.

### 2. VISUALIZE — OLED HUD shows only what's relevant

The display composes widgets based on the current activity mode. User can rearrange and toggle each widget.

**Available widgets:**

| Widget | Shows | Used in modes |
|---|---|---|
| `mode_tag` | Colored mode name badge (top-left) | All modes |
| `status_bar` | WiFi, battery, recording dot | All except Incognito |
| `ai_text` | Last AI response, scrollable via encoder | Work, Walk, Talk, Flirt |
| `sensor_readout` | IMU / speed / altitude values | Drive, Ski, Walk |
| `schedule` | Next time slot from Axiom schedule | Work, Walk |
| `diary_prompt` | "Log this moment?" quick button | Take Notes, Walk |
| `transcription` | Live subtitles | Talk, Flirt |
| `navigation` | Next turn, ETA, distance | Drive, Walk |
| `reps_timer` | Exercise name, reps, sets, rest timer | Lift |
| `compass` | Heading degrees | Walk, Ski |
| `blank` | Nothing — screen off | Incognito |

### 3. SAVE — offline diary

Every moment can be saved as a diary entry, even without internet.

**Entry types:**

| Type | Trigger | Fields |
|---|---|---|
| `note` | Voice dictation or encoder click | content, mood, tags |
| `voice_note` | Push-to-talk | audio blob → server transcribes, saves as entry |
| `photo` | Camera capture on demand | JPEG, auto-tagged |
| `place` | GPS at encoder click | lat, lng, name, tags |
| `tracker` | AI-detected (lift = log reps) | exercise, reps, sets, weight |
| `checkin` | Morning/evening prompt | mood, win, 1-sentence |

**Offline-first:**
- Entries saved to ESP32 flash (or SD card on Sense board)
- Sync queue on the PC server (if PC is off, queued until next boot)
- All metadata (tags, domain, location) attached on-device before sync

**Auto-triggers** (like Praxis triggers):
- GPS at a gym → auto-suggest "Log a workout?"
- Camera sees food → "Log this meal?"
- Encoder click at end of conversation → "Save diary entry?"

### 4. SORT — Axiom-style auto-classification

The server classifies every piece of data as it arrives:

- **Domain tagging**: raw context → Body & Fitness, Career & Craft, Friendship & Social, etc.
- **Pattern detection**: "You always log workouts after 6pm", "You meet this person every Tuesday"
- **Progress change detection**: ≥10% shift in any goal metric = auto-highlight in diary
- **Theme grouping**: related entries clustered by topic across time
- **Mood analysis**: sentiment trends from voice tone + diary entries

The visor shows category badges on the display. The full picture lives on the companion app.

### 5. RETRIEVE — query past data

| Voice command | What happens |
|---|---|
| "Merlin, what did I do yesterday?" | Searches local diary cache → AI summarizes |
| "Merlin, show my notebook from last week" | PC agent calls Praxis MCP server → returns text → OLED scrolls it |
| "Merlin, what patterns do you see?" | PC agent runs Axiom-analysis on past data → insight on OLED |
| "Merlin, how many pushups this week?" | Agent queries Praxis tracker data via MCP |
| "Merlin, remind me what we talked about" | Searches last conversation transcript |

Results appear on the OLED display, scrollable with the encoder.

### 6. SCHEDULE — Axiom-style daily planning

Each morning, the server generates a daily schedule based on your goals, habits, and calendar:

```
06:00 [wake]         →  no mode change
07:00 [exercise]     →  visor switches to "Lift"
08:30 [deep_work]    →  visor switches to "Work"
12:00 [lunch]        →  visor switches to "Walk" (goes outside)
14:00 [meeting]      →  visor switches to "Talk"
16:00 [deep_work]    →  visor switches to "Work"
18:00 [social]       →  visor switches to "Flirt" or "Talk"
21:00 [wind_down]    →  visor switches to "Take Notes" or Incognito
```

**Schedule features on the visor:**
- `schedule` widget shows next slot + time remaining
- Encoder click on a slot = "Mark complete" + optional voice note
- Schedule auto-activates the associated mode (user can override)
- End of day: auto-summary of completed vs missed slots
- Works offline (schedule cached on device); syncs on reconnect
- User can regenerate schedule on demand

### 7. SEND / CREATE — agent acts on your behalf

The server-side AI agent has full tool access:

| Tool | Scope |
|---|---|
| `write_file` | Create/edit files on PC |
| `run_shell` | Execute shell commands |
| `capture_screen` | Screenshot the PC desktop |
| `read_file` / `list_dir` | PC filesystem access |
| Praxis MCP | Query/create diary entries, goals, trackers, profiles |
| `send_email` | Email via SMTP |
| Scheduled tasks | "Remind me tomorrow at 9am" → agent sets a cron job |

Triggered by voice ("Merlin, write that email") or encoder double-click (push-to-query with current context). Result comes back as text on the OLED display and optionally as an action on the PC.

---

## Activity mode system

### Architecture

Every mode is a JSON config preset stored on the device and synced to the server:

```json
{
  "id": "lift",
  "name": "Lift",
  "color": "#EF4444",
  "icon": "💪",
  "sensors": {
    "camera": { "enabled": true, "fps": 1.0, "resolution": "640x480" },
    "audio": { "enabled": true, "mode": "push_to_talk", "chunk_ms": 4000 },
    "imu": { "enabled": true, "hz": 20 },
    "gps": { "enabled": false }
  },
  "display": {
    "elements": ["mode_tag", "status_bar", "reps_timer", "ai_text"],
    "brightness": 80,
    "auto_dim_after_s": 30
  },
  "ai": {
    "mode_label": "LIFT",
    "observe_interval_s": null,
    "description": "You're at the gym lifting weights. Focus on rep counting, form, and logging sets."
  },
  "audio_out": "glasses_speaker",
  "schedule_link": ["exercise"],
  "incognito": false
}
```

Users create, clone, edit, and delete modes through:
1. **Companion app** (visual editor)
2. **Voice**: "Merlin, new mode called 'Run' with camera at 0.5fps, GPS on, show compass"
3. **CLI**: `merlin mode create --name Run --clone Walk --camera-fps 0.5`

### Factory presets (9 modes)

---

#### WORK

Real name of the mode: "Work"
- Color: `#4A6FA5` (slate blue)
- Icon: `💼`

| Sensor | Setting |
|---|---|
| Camera | 0.2 fps (occasional screen/code context) |
| Audio | On — transcribe meetings and dictation |
| GPS | Off |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "WORK" in slate blue |
| `status_bar` | WiFi + battery only |
| `schedule` | Shows current + next Axiom time slot |
| `ai_text` | Last AI response (screen analysis, code help, meeting notes) |

AI focus: "The user is working at their desk. Help with code, files, meeting recap, screen analysis. You have full tool access."

Audio out: headphones (if connected) or glasses speaker

Schedule auto-link: `deep_work`, `meeting`, `admin`

---

#### LIFT

Real name of the mode: "Lift"
- Color: `#EF4444` (fire red)
- Icon: `💪`

| Sensor | Setting |
|---|---|
| Camera | 1.0 fps (form analysis, rep counting) |
| Audio | Push-to-talk (log sets by voice) |
| GPS | Off |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "LIFT" in fire red |
| `status_bar` | Battery only |
| `reps_timer` | Current exercise name, reps completed, sets, rest timer countdown |
| `ai_text` | Form tips, "3 more to failure", next exercise suggestion |

AI focus: "The user is lifting weights. Count reps from camera frames, track rest intervals, suggest next exercises based on logged history. Log completed sets."

Audio out: glasses speaker (short cues: "Last rep", "Rest over")

Schedule auto-link: `exercise`

---

#### DRIVE

Real name of the mode: "Drive"
- Color: `#10B981` (emerald green)
- Icon: `🚗`

| Sensor | Setting |
|---|---|
| Camera | 0.1 fps (road context, sign reading) |
| Audio | Voice commands only |
| GPS | High accuracy, 1 Hz |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "DRIVE" in emerald, extra large text |
| `status_bar` | Battery only |
| `navigation` | Next turn distance + direction, current speed, ETA, traffic level |
| `sensor_readout` | Speed in km/h |

AI focus: "The user is driving. Prioritize navigation, traffic, safety. Keep text brief and large. No distractions."

Audio out: glasses speaker (turn alerts)

Schedule auto-link: `travel`, `commute`

---

#### SKI

Real name of the mode: "Ski"
- Color: `#38BDF8` (ice blue)
- Icon: `⛷️`

| Sensor | Setting |
|---|---|
| Camera | 0.5 fps (trail conditions, snow quality) |
| Audio | Voice commands |
| GPS | High accuracy, 1 Hz (speed + altitude) |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "SKI" in ice blue |
| `status_bar` | Battery + temperature |
| `sensor_readout` | Speed km/h, altitude m, vertical drop, run count |
| `compass` | Heading + trail name below |
| `ai_text` | Trail conditions, lift status, lodge recommendations |

AI focus: "The user is skiing. Track runs (altitude deltas), log vertical, suggest trails based on skill level and conditions."

Audio out: glasses speaker (lift status, trail suggestions)

Schedule auto-link: `sports`, `outdoor`

---

#### WALK

Real name of the mode: "Walk"
- Color: `#4ADE80` (warm green)
- Icon: `🚶`

| Sensor | Setting |
|---|---|
| Camera | 0.3 fps (scout awareness) |
| Audio | Voice notes on demand |
| GPS | On, 0.2 Hz (battery-friendly) |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "WALK" in warm green |
| `status_bar` | WiFi + battery |
| `compass` | Heading |
| `schedule` | Next appointment or "free until next slot" |
| `ai_text` | POI alerts, environmental observations |
| `diary_prompt` | "Log this moment?" on encoder click |

AI focus: "The user is walking. Scout the environment — note interesting places, people, weather. Offer observations proactively every 30s. If GPS detects a POI, suggest bookmarking it."

Audio out: glasses speaker (brief observations) or headphones

Schedule auto-link: `break`, `errand`, `leisure`

---

#### TALK

Real name of the mode: "Talk"
- Color: `#E11D48` (rose)
- Icon: `💬`

| Sensor | Setting |
|---|---|
| Camera | Off (privacy) |
| Audio | On — continuous transcription |
| GPS | Off |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "TALK" in rose |
| `status_bar` | Battery + recording dot |
| `transcription` | Live subtitles of what the other person says |
| `ai_text` | Conversation cues, prep notes, names, "ask about X" |

AI focus: "The user is in conversation. Transcribe in real time. Surface key names, topics, and questions. Cross-reference past conversations. If the other person mentions something from a previous talk, show that context."

Audio out: headphones only (discrete)

Schedule auto-link: `meeting`, `social`, `coffee`

---

#### TAKE NOTES

Real name of the mode: "Take Notes"
- Color: `#F59E0B` (amber)
- Icon: `📝`

| Sensor | Setting |
|---|---|
| Camera | 0.2 fps (document, whiteboard, screen capture) |
| Audio | On — continuous dictation |
| GPS | On (tag location to notes) |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "NOTES" in amber |
| `status_bar` | WiFi + battery + recording dot |
| `transcription` | Live dictation being transcribed |
| `diary_prompt` | Category selector (Work, Personal, Idea, etc.) + tag chips |

AI focus: "The user is taking notes. Transcribe everything. Classify content into categories. If camera sees a whiteboard or document, capture and OCR it. Save every entry to the diary."

Audio out: headphones or glasses speaker

Schedule auto-link: `learning`, `planning`, `reflection`

---

#### FLIRT

Real name of the mode: "Flirt"
- Color: `#F472B6` (blush pink)
- Icon: `💗`

| Sensor | Setting |
|---|---|
| Camera | Off (privacy) |
| Audio | On — subtle transcription |
| GPS | Off |

| Display widget | Behavior |
|---|---|
| `mode_tag` | "FLIRT" in blush pink (small, discrete) |
| `status_bar` | Battery only |
| `transcription` | Subtle cues — name, "ask about her trip to X", "she mentioned loving Y" |
| `ai_text` | Gentle conversation suggestions, recall past chats, compliments |

AI focus: "The user is on a date or in a romantic context. Extremely subtle. Only show short, useful cues. Never interrupt. Recall past conversations. Suggest questions based on what she's said. Keep display dim and sparse."

Audio out: headphones only (absolutely discrete)

Schedule auto-link: `date`, `romance`

---

#### INCOGNITO

Real name of the mode: "Incognito"
- Color: `#374151` (dark gray)
- Icon: `👁️‍🗨️`

| Sensor | Setting |
|---|---|
| Camera | Off |
| Audio | Off — stream to phone/headphones only (no local storage) |
| GPS | Off |
| Display | Off — blank |

| Display widget | Behavior |
|---|---|
| `blank` | Nothing. Screen is physically powered off. |

AI focus: None — purely passive. If user activates audio pass-through, sound goes to phone speakers / headphones with zero on-device buffering.

Audio out: phone speakers or headphones (must be connected) — zero on-device processing

Schedule auto-link: (none — always available)

---

### Horse blindfold principle

Every activity mode intentionally **hides** information to keep you focused:

| Mode | Shows | Filters out |
|---|---|---|
| Lift | Reps, timer, form note | Email, weather, social pings, calendar |
| Drive | Nav, speed, ETA | Diary, IMU readout, calendar, todo |
| Flirt | Name prompt, cue | Work messages, GPS, schedule, todo |
| Work | Calendar, todo, prep notes | Speed, altitude, compass, social |
| Ski | Speed, altitude, run count | Email, calendar, todo, social |
| Walk | Compass, POI, schedule | Rep counting, nav turns, work messages |
| Talk | Subtitles, cue, prep notes | Everything except conversation context |
| Take Notes | Transcription, diary UI | Everything except capture |
| Incognito | Nothing | Everything |

---

### Creating and editing modes

**Via voice:**
```
"Merlin, new mode called 'Run'"
"Merlin, edit my 'Drive' mode — set camera off"
"Merlin, clone 'Walk' into 'Hike'"
"Merlin, delete 'Ski'"  (confirms first)
```

**Via companion app (web UI hosted on PC server):**
```
MODE EDITOR
┌────────────────────────────────────────┐
│ Mode name:  [ Lift                ]   │
│ Color:      [ #EF4444  ]  [ 🎨 ]     │
│                                       │
│ Sensors                                 │
│  ☑ Camera     [1.0 fps ▼]              │
│  ☑ Audio      [Push to talk ▼]         │
│  ☐ GPS                                  │
│  ☑ IMU        [20 Hz]                   │
│                                         │
│ Display pattern: (drag to reorder)      │
│  [mode_tag] [status_bar] [reps_timer]   │
│  [+ Add widget]                         │
│                                         │
│ AI prompt: (free text)                  │
│ [The user is lifting weights...     ]  │
│                                         │
│ Schedule link: [exercise ▼]             │
│                                         │
│ [  SAVE  ]  [  CLONE  ]  [  DELETE  ] │
└────────────────────────────────────────┘
```

### Mode lifecycle

1. **Create** — companion app or voice
2. **Store** — saved to ESP32 flash (SPIFFS) + synced to server config
3. **Select** — encoder menu (scroll → click) or voice ("Merlin, switch to Work") or schedule auto-activate
4. **Run** — visor applies sensor rates, layout, sends `{type:"mode_change", mode:"Lift"}` to server, server adjusts AI strategy
5. **Edit** — clone from any existing mode and tweak
6. **Delete** — removed from flash + server config (confirms if currently active)

---

## Competitive positioning

| Capability | Omi Glass | Even G2 | Merlin Visor |
|---|---|---|---|
| Camera | ✓ 0.5 fps lifelogging | ✗ (deliberate) | ✓ 0–1 fps configurable |
| Microphone | ✓ always-on | ✓ on-demand | ✓ per-mode config |
| Display | ✗ (phone app only) | ✓ micro-OLED waveguide | ✓ OLED clip-on (text) |
| Offline diary | ✓ transcripts saved first | ✗ | ✓ full diary + schedule cache |
| Daily schedule | ✗ | ✓ calendar sync | ✓ Axiom AI scheduling |
| Smart sorting | ✓ summaries | ✗ | ✓ domain + pattern + mood |
| Activity modes | ✗ (always recording) | ✗ (always calendar) | ✓ 9+ user-customizable |
| Incognito | ✗ | ✗ | ✓ full off mode |
| Open source | ✓ (full) | ✗ (SDK only) | ✓ (full) |
| BOM cost | ~$299 (dev kit) | ~$650+ | ~$50 (DIY) |
| Praxis MCP integration | ✗ | ✗ | ✓ agent → Praxis via MCP |

**Merlin's unique position:** The only device that combines always-on sensing + offline diary + AI scheduling + activity-based privacy + agentic goal coaching. Omi has sensing and diary but zero display. Even has display and calendar but no camera or diary. Merlin is the only one where modes act as a horse blindfold — intentionally hiding information based on what you're doing.

---

## Hardware evolution path

| Phase | Device | Display | Battery | Input | Weight on frame |
|---|---|---|---|---|---|
| Dev kit | ESP32-S3 on protoboard + 3D printed clip | OLED 0.96" (I2C) | 500mAh LiPo (collar clip) | EC11 encoder | ~25g |
| v1 prototype | Custom PCB + distributed cells | 1.3" TFT or SH1107 OLED | 2× 250mAh on temples + charging case | Encoder + BLE ring | ~20g |
| v2 production | Magnesium frame (injection mold) | Micro-OLED waveguide (see-through) | Charging case (7 charges) | Ring (primary) + touch (secondary) | <40g |
