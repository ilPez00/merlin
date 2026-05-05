# Merlin HUD — ESP32-S3 Firmware Spec

**Target**: Seeed XIAO ESP32S3 Sense (ESP32-S3R8, 8MB PSRAM, 16MB flash, OV2640 camera, I2S MEMS mic)

## Functional requirements

1. **WebSocket client** — connects to Merlin server at `ws://<server>:8765`
2. **Camera capture** — 640x480 JPEG at 0.65 quality, throttled per mode (0.1-1 fps). Uses ESP32 camera driver via `esp_camera.h`.
3. **Audio capture** — I2S MEMS mic, 16-bit 16kHz mono PCM, buffered into 4-second chunks, sent as raw PCM.
4. **IMU streaming** — MPU6050 on I2C, read at ~20Hz, send JSON `{type:"imu", ax,ay,az,gx,gy,gz, ts}` on WiFi task
5. **OLED display** — SSD1306 on I2C (same bus as MPU6050). Composable widget system per mode:
   - All modes show: mode tag (colored badge), status bar (WiFi, battery)
   - Per-mode widgets: ai_text, schedule, diary_prompt, transcription, navigation, reps_timer, compass, sensor_readout, blank
   - When AI responds: scrolls response text
   - Menu: mode selection overlay (all saved modes)
6. **Encoder input** — EC11 rotary encoder with click switch:
   - Rotate: scroll/paginate through text, or cycle modes in menu
   - Click: send `{type:"observe", mode}` — trigger AI observation, or confirm menu selection
   - Double-click (within 500ms): push-to-talk (records 5s audio, sends as query)
   - Long-press (1.5s): open mode selection menu
7. **Mode system** — fully dynamic, user-customizable. Modes stored as JSON configs on SPIFFS:
   - Each mode defines: name, color hex, sensor rates per-type, display widget list, AI mode label, observe interval, schedule link tags, audio out target, incognito flag
   - Factory presets (9): Work, Lift, Drive, Ski, Walk, Talk, Take Notes, Flirt, Incognito
   - User can create, clone, edit, delete modes via voice or companion app
   - On mode change, sends `{type:"mode_change", mode:"Work"}` to server
   - Mode configs synced bidirectionally with server config file
8. **BLE peripheral** — for ring input (future):
   - Advertises as `Merlin-Visor`
   - Accepts scroll, click, double-click events from BLE ring
   - Same event handling as onboard encoder (scroll, click, double-click)
9. **Offline diary** — stores entries to onboard SD card:
   - Entry types: note, voice_note, photo, place, tracker, checkin
   - All entries include: timestamp, GPS (if available), mode, tags
   - Works without WiFi: entries queued, synced on reconnect
   - Auto-triggered suggestions: "Log this?" on context change (camera sees food, GPS at gym, etc.)
10. **Schedule cache** — daily schedule from Axiom server stored locally:
    - Shows next time slot + duration on schedule widget
    - Encoder click on slot = "Mark complete" + optional voice note
    - Auto-activates mode when schedule slot matches a mode's schedule_link
    - End-of-day summary of completed vs missed

## Data flow

```
  ESP32 ──WiFi──> PC Merlin Server
    │                 │
    ├─ JPEG frames    ├─ AI responses ──> OLED display
    ├─ PCM audio      ├─ status ────────> OLED display
    ├─ IMU JSON       │
    ├─ encoder events │
    └─ mode changes   │
```

## Pin allocation (XIAO ESP32S3 Sense)

| Function          | Pin      | Notes                          |
|-------------------|----------|--------------------------------|
| Camera            | Internal | Fixed on Sense board           |
| I2S mic (built-in)| Internal | Fixed on Sense board           |
| OLED SDA          | D4 (GPIO4) | I2C                          |
| OLED SCL          | D5 (GPIO5) | I2C                          |
| MPU6050 SDA       | D4 (shared) | Same I2C bus                |
| MPU6050 SCL       | D5 (shared) | Same I2C bus                |
| Encoder CLK       | D0 (GPIO0) | Interrupt                     |
| Encoder DT        | D1 (GPIO1) | Interrupt                     |
| Encoder SW        | D2 (GPIO2) | Pull-up, interrupt            |
| Battery ADC       | D9 (GPIO9) | Voltage divider               |

## Software architecture

```
main/
  main.cpp              ─ setup(), loop(), FreeRTOS task creation
  wifi_task.cpp         ─ WiFi connect + reconnect with exponential backoff
  ws_client.cpp/.h      ─ WebSocket client (libwebsockets or esp_websocket)
  camera_task.cpp/.h    ─ Camera init, frame capture, JPEG encode, queue
  audio_task.cpp/.h     ─ I2S mic read, PCM buffering, chunk management
  imu_task.cpp/.h       ─ MPU6050 read, filtering, JSON serialization
  display_task.cpp/.h   ─ OLED framebuffer, composable widgets, text rendering, menu
  encoder_task.cpp/.h   ─ Rotary encoder debounce, direction, click/double-click/long-press
  ble_task.cpp/.h       ─ BLE peripheral for ring input (future)
  diary_task.cpp/.h     ─ Offline diary: SD card write, entry queue, sync manager
  schedule_task.cpp/.h  ─ Axiom schedule cache: store, retrieve, mark completions
  mode_config.cpp/.h    ─ Mode config manager: SPIFFS read/write, factory presets, validation
  protocol.cpp/.h       ─ Wire protocol: pack binary frames, parse JSON responses
  sensor_config.h       ─ Per-sensor rate limits and pin definitions
```

## Protocol adaptation

The server expects binary frames with a JSON header line: `JSON_HEADER\nBLOB`:

```
{"type":"frame","ts":...,"mode":"SCOUT"}
<JPEG bytes>
```

The ESP32 firmware replicates this exact format.

### Audio format concern

Server expects WebM/Opus. Two options:

1. **(Recommended)** Modify `stream_processor.py` to accept raw PCM — add a `format` field:
   `{"type":"audio","format":"pcm","sample_rate":16000}`
2. Compile Opus encoder into firmware (possible, ~50KB flash, more complex)

## FreeRTOS task layout

| Task         | Stack  | Core | Priority | Notes                                |
|--------------|--------|------|----------|--------------------------------------|
| Camera       | 8192   | 0    | 3        | Captures frame, encodes JPEG         |
| Audio        | 4096   | 1    | 2        | I2S read, buffers 4s chunks          |
| IMU          | 2048   | 0    | 1        | Polls MPU6050 at 20Hz                |
| Display      | 4096   | 1    | 1        | OLED composable widgets, menu        |
| Encoder      | 2048   | 0    | 2        | Debounce, detect rotate/click/dbl    |
| BLE          | 4096   | 0    | 1        | BLE peripheral, ring input relay     |
| Diary        | 4096   | 1    | 1        | SD card write, entry queue, sync     |
| Schedule     | 2048   | 0    | 1        | Slot lookup, timer, auto-mode-switch |
| Mode config  | 2048   | 0    | 1        | SPIFFS read/write, factory reset     |
| WiFi/WS      | 8192   | 1    | 3        | WiFi maintain, WS send/recv          |

## Dependencies (PlatformIO ini)

```ini
[env:xiao_esp32s3]
platform = espressif32@~6.6.0
board = seeed_xiao_esp32s3
framework = arduino
board_build.arduino.memory_type = qio_opi
board_build.flash_mode = qio

lib_deps =
    bblanchon/ArduinoJson@^7.0
    adafruit/Adafruit SSD1306@^2.5
    adafruit/Adafruit GFX Library@^1.11
    electronicspices/MPU6050@^1.0
    madhephaestus/ESP32RotaryEncoder@^1.2
    links2004/WebSockets@^2.4.1
```

## Build & flash

```bash
pio run --target upload           # Flash via USB-C
pio device monitor --baud 115200  # Serial debug console
```

## Power management

- Deep sleep between camera captures (when frame rate is < 1 Hz)
- WiFi DTIM interval: 10 (reduce power)
- OLED sleep after 30s inactivity — wake on encoder or ring movement
- Battery ADC read every 60s, send `{type:"battery", level:percent}`
- Incognito mode: WiFi off, display off, BLE off, audio passthrough only — all sensors powered down
- Schedule-aware: if next time slot is "sleep", enter deep sleep until 30 min before next slot
- Diary writes to SD card in batches (every 5 entries or 60s) to minimize write current peaks

## Future improvements

- Over-the-air (OTA) firmware updates via WebSocket or HTTP
- MicroPython fallback for rapid prototyping (but camera + audio streaming is harder)
- On-device wake word via TensorFlow Lite Micro with keyword spotting model
- Save frames to SD card (onboard slot) in buffer mode
