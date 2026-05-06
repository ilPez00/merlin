# Merlin — Caveman Plan

**Mission**: Always-on AI field intelligence. Wearables stream sensor data to an agent that sees what you see, hears what you hear, and acts.

**Current state**: ~10,450 LOC, 41 agent tools, 3 LLM backends, 4 client targets, 9 modes. Phone HUD app and Desktop TUI are daily-driver quality. Hardware is 4 README specs (zero implementation code).

**Strategy**: Ship hardware in order of cheapest/fastest. Each wearable gets a Lite (MVP) and Pro variant. App and TUI get polish passes.

---

## Common architecture

All wearables share this protocol — no server changes needed:

```
Wearable ──BLE──> Phone ──WebSocket──> PC Server ──LLM──> Response
              or WiFi ──direct──> PC Server (camera)
```

Phone = BLE hub + GPS + cellular bridge. Wearables optionally connect WiFi direct to PC for low-latency camera/audio.

Binary frame format (reused from existing phone protocol): `JSON_HEADER\nBLOB` with type, mode, timestamp, payload.

---

## 1. Ring (build first — cheapest, fastest, ~2-3 weeks)

Smallest form factor. Gesture input + haptic feedback. No display.

### Ring Lite (~$10 BOM)
| Component | Part | Cost |
|-----------|------|------|
| MCU | nRF52840 (BLE, ultra-low power) | $4 |
| IMU | LIS3DH accelerometer | $1 |
| Haptic | LRA motor (Jinlong 10mm) | $1.50 |
| Battery | 60mAh LiPo | $2 |
| LED | RGB 0603 | $0.50 |
| PCB | Flexible 18mm round, 2-layer | $3 |
| Charging | Pogo pin cradle | $2 |
| Enclosure | Resin 3D print | $1 |
| **Total** | | **~$15** *(was ~$10 before adding cradle)* |

Firmware: BLE GATT peripheral, tap/double-tap/triple-tap via LIS3DH, deep sleep between events, RGB status. 3-5 day battery.

### Ring Pro (~$18)
- Adds capacitive touch (nRF52 built-in)
- CR2032 coin cell option (1-month life)
- Thumb rub gesture (scroll)
- Water-resistant coating

### Gesture set
| Gesture | Action |
|---------|--------|
| Tap | Confirm / send observe |
| Double-tap | Repeat last AI response |
| Triple-tap | Emergency / panic |
| Thumb slide | Scroll / cycle modes |
| Fist clench | Start phone voice recording |

### Milestones
1. nRF52840 dev board + LIS3DH + haptic on breadboard — gesture detection works
2. Custom flexible PCB (circular, 18mm)
3. BLE to phone — gestures appear as events in HUD
4. Silicone/resin enclosure
5. Charging cradle
6. 3-day battery validated

---

## 2. Glasses (~$53 BOM, 4-6 weeks)

Already fully specced in `hardware/`. Zero implementation code.

### Glass Lite (~$53)
| Component | Cost |
|-----------|------|
| XIAO ESP32S3 Sense (MCU+camera+mic) | $14.90 |
| SSD1306 OLED 0.96" | $3.50 |
| MPU6050 IMU | $1.80 |
| EC11 rotary encoder | $1.50 |
| 500mAh LiPo (collar clip) | $4.50 |
| TP4056 charger + switch | $1.50 |
| Protoboard + wire + connectors | $4.40 |
| 3x 3D printed nylon 12 parts | $13.00 |
| microSD 16GB + misc | $5.00 |
| Screws/inserts/silicone pads | $3.00 |
| **Total** | **~$53** |

Firmware: FreeRTOS tasks — camera (JPEG 0.1-1fps), audio (PCM 16kHz 4s chunks), IMU (20Hz), OLED widgets, encoder input, WiFi/WebSocket binary frames.

### Glass Pro (~$85)
- Custom shield PCB (replaces protoboard, ~$15)
- 2x 250mAh temple batteries (balanced, ~$13)
- BLE ring integration
- 1.3" OLED
- Eye tracking (OV7670 IR, ~$6)

### Milestones
1. Order all BOM parts
2. PlatformIO project + WiFi/WebSocket handshake
3. Camera capture + binary frame send
4. OLED display + widget system
5. Encoder input + mode switching
6. Protoboard assembly + 3D print mount
7. 30-min continuous streaming validated

---

## 3. Watch (~$28-45 BOM, 4-6 weeks)

Wrist companion. Glanceable notifications, health data, quick actions.

### Watch Lite (~$28)
| Component | Part | Cost |
|-----------|------|------|
| MCU | nRF52840 (BLE only) | $4 |
| Display | 1.3" round TFT LCD (GC9A01, 240x240) | $8 |
| IMU | ICM-20948 (9-axis, step counting) | $3 |
| Haptic | ERM motor | $1 |
| Battery | 250mAh LiPo | $3 |
| Charging | Magnetic pogo pins | $2 |
| Input | Single button + flick-wrist | $1 |
| PCB | Round 35mm | $4 |
| Enclosure | 3D print + silicone strap | $2 |
| **Total** | | **~$28** |

Firmware: BLE GATT client to phone. Receive notifications/responses. Display driver (round text rendering). Step counting. Haptic feedback. Flick-wrist wake.

### Watch Pro (~$45)
- MCU: ESP32-S3 (adds WiFi direct to PC)
- Sensors: MAX30102 HR+SpO2, BMP280 barometer
- Display: 1.5" round AMOLED
- GPS: Quectel L76K

### Display contents
| State | Shows |
|-------|-------|
| Idle | Time, steps, battery, connection |
| Notification | AI response (scrollable), sender |
| Mode | Mode name + color pulse |
| Health (Pro) | HR, SpO2, calories |
| Navigation (Pro) | Next turn, distance |

### Milestones
1. nRF dev board + round display — text rendering works
2. BLE to phone — receives notifications
3. Step counting via IMU — validates accuracy
4. Haptic on notification
5. Custom round PCB + enclosure + strap
6. 3-day battery validated

---

## 4. Necklace (2 versions, 3-5 weeks)

Always-on microphone + optional camera. Worn on lanyard, rests at chest.

### Necklace Audio (Lite, ~$20)
| Component | Part | Cost |
|-----------|------|------|
| MCU | nRF52840 (BLE to phone) | $4 |
| Mic array | 2x INMP441 MEMS (beamforming) | $4 |
| Battery | 800mAh LiPo | $7 |
| Haptic | ERM motor | $1 |
| Button | Capacitive touch / physical PTT | $1 |
| LED | RGB (visible through fabric) | $0.50 |
| PCB | 30x20mm | $3 |
| Enclosure | Fabric-wrapped 3D print | $2 |
| Lanyard | Magnetic breakaway clasp | $2 |
| **Total** | | **~$24** *(was ~$20 before adding lanyard hardware)* |

Firmware: BLE to phone. Dual mic audio capture with beamforming. Push-to-talk button → query → response. Deep sleep between speech.

### Necklace Camera (Pro, ~$30)
- MCU: ESP32-S3 (adds WiFi direct to PC)
- Camera: OV2640 (chest-level outward POV)
- WiFi direct for camera streaming (bypasses phone for lower latency)

### Use cases
| Scenario | Role |
|----------|------|
| Walking | Audio-only, wake word always listening |
| Meeting | Audio-only, transcribes |
| Inspection | Camera mode, chest-level POV stream |
| Hands-free | Push-to-talk, response via phone speaker |
| Power bank | 800mAh can top up ring/watch |

### Milestones
1. ESP32 dev board + dual INMP441 — audio capture + beamforming works
2. BLE + WiFi — dual connectivity
3. Push-to-talk → query → response cycle
4. Camera version: OV2640 + WiFi streaming
5. Enclosure + lanyard
6. 8h continuous audio validated

---

## 5. App (Phone HUD) — polish (~1 week)

Already working. Needs audit + hardening.

- Audit all 12 `lib/*.js` modules — verify not stubs
- Test `build-apk.sh` produces working signed APK from modular code
- End-to-end: phone → server → agent → response (all modes)
- Phone standalone mode (direct API, no server)
- Loading states, error recovery, PWA install timing
- Offline diary (IndexedDB) sync edge cases

---

## 6. Desktop TUI — fix stubs (~3-5 days)

Already daily-driver quality. 3 real bugs.

- Fix widget stubs: `weather`, `next_event`, `avg_time_spent` all return `"--"`
- Consolidate voice pipeline: `main_screen.py` duplicates `audio/mic.py`. Use `MicListener` everywhere.
- Fix `conversation_summary()`: reads `conversations.json` which is never written
- Memory search: currently keyword-only (ChromaDB stubbed)
- Electron HUD: currently receive-only, add bi-directional send
- Daemon mode: run without TUI, tray icon, OS notifications

---

## Build order

```
Week 1-2:   Ring Lite (dev board + sensor + haptic -> gesture detection)
Week 2-3:   App polish + TUI fixes (parallel)
Week 3-4:   Ring Pro (custom PCB + enclosure + charging cradle)
Week 4-6:   Necklace Audio (dual mic, BLE, push-to-talk)
Week 5-6:   Glasses Part 1 (WiFi/WS, camera, OLED, encoder)
Week 6-8:   Necklace Camera (ESP32-S3 + OV2640)
Week 7-8:   Glasses Part 2 (protoboard + 3D print + assembly)
Week 8-10:  Watch Lite (nRF + round display + step counting)
Week 10-12: Watch Pro + Glasses Pro (custom PCBs, sensors)
```

---

## Monetization

| Model | Revenue | Effort | Verdict |
|-------|---------|--------|---------|
| **Merlin Dev Kit** (Ring Lite + Glass Lite + Necklace Audio + guide) | $249/kit, 60% margin | Low (bundle) | **HIGH** |
| **Individual devices** (Ring $79, Glasses $199, Watch $149, Necklace $99) | per unit | Low | **HIGH** |
| **Enterprise field ops** (10-device fleet + server + SLA) | $15-25k/deploy | High | **HIGH** |
| **Merlin Cloud** (API proxy + sync storage) | $5-10/mo | Medium | **LOW** |
| **Paid desktop app** | $20-50 | Low | **LOW** |
| **Consulting** | $150-200/h | Medium | **MEDIUM** |

**Caveman take**: Sell hardware kits. The phone app and TUI are free moats that make the hardware valuable. Ring is the loss leader at $79 — developers buy it to experiment and become your distribution channel. SaaS is a distraction. Enterprise is a separate bet.
