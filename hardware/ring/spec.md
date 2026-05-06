# Merlin Ring — Product Specification v0.1 (MVP)

## 1. Purpose

A BLE gesture-input ring worn on the finger. The ring is Merlin's **discreet always-available input** — tap to observe, double-tap to repeat, triple-tap for emergency, long-press for voice, tilt to scroll. No screen, no mic, no camera. Pure gesture + haptic.

No biometric sensing in MVP (HR, SpO2, skin temp). Those belong on the watch form factor where skin contact is reliable.

---

## 2. Gesture set (MVP)

| Gesture | Detection | Action |
|---------|-----------|--------|
| Tap | LIS3DH single-click interrupt (hardware) | Send `{type:"ring_gesture", gesture:"tap"}` → phone triggers AI observe |
| Double-tap | LIS3DH double-click interrupt (hardware) | Repeat last AI response |
| Triple-tap | Software: double-tap interrupt + 500ms window for 3rd tap | Emergency / panic mode |
| Long-press (2s still) | Software: accel magnitude ≈ 1g (no movement) for 2s | Toggle scroll mode OR start voice recording |
| Tilt scroll | Software: after long-press, accel tilt angle change | Scroll responses up/down, cycle modes |

No capacitive touch needed. No gyro needed. Tilt uses LIS3DH gravity-vector angle.

---

## 3. Hardware architecture

```
┌──────────────────────────────────────────┐
│           RING (on finger)               │
│                                          │
│  ┌──────────────┐    ┌────────────────┐  │
│  │ nRF52840     │◄───│ LIS3DH accel   │  │
│  │ (BLE MCU)    │    │ (I2C, int pin) │  │
│  │              │◄───│ LRA haptic     │  │
│  │              │◄───│ RGB LED        │  │
│  │              │◄───│ Battery ADC    │  │
│  └──────┬───────┘    └────────────────┘  │
│         │                                 │
│  ┌──────┴───────┐                         │
│  │ TP4056       │◄── 5V from pogo pins   │
│  │ LiPo charger │                         │
│  └──────┬───────┘                         │
│         │                                 │
│  ┌──────┴───────┐                         │
│  │ 60mAh LiPo   │                         │
│  │ (601224)     │                         │
│  └──────────────┘                         │
│                                          │
│  Bottom face: 2 pogo pins (VCC, GND)    │
└──────────────────────────────────────────┘
                  │ pogo contact
                  ▼
┌──────────────────────────────────────────┐
│       CHARGING CRADLE (desk)            │
│                                          │
│  ┌──────────────┐    ┌────────────────┐  │
│  │ TI BQ51003   │◄───│ 15mm Rx coil   │  │
│  │ Qi receiver  │    └────────────────┘  │
│  └──────┬───────┘                        │
│         │ 5V DC                          │
│  ┌──────┴───────┐                        │
│  │ Pogo pins    │──── to ring VCC/GND   │
│  └──────────────┘                        │
│                                          │
│  Input: Qi wireless OR USB-C             │
└──────────────────────────────────────────┘
```

---

## 4. Pin allocation (nRF52840)

| Function | nRF52 Pin | Notes |
|----------|-----------|-------|
| LIS3DH SDA | P0.03 | I2C data |
| LIS3DH SCL | P0.04 | I2C clock |
| LIS3DH INT1 | P0.05 | Tap interrupt (rising edge) |
| LRA PWM | P0.06 | PWM output, ~175Hz LRA drive |
| RGB LED data | P0.08 | NeoPixel/SK6812 data line |
| Battery ADC | P0.28 | Voltage divider, 100K+47K |
| Charge status | P0.29 | TP4056 CHRG pin (open drain) |
| Pogo VCC | VBUS | 5V from cradle via pogo pin |
| Pogo GND | GND | Ground via pogo pin |

---

## 5. Power architecture

- **Battery**: 601224 60mAh 3.7V LiPo (12×12×4mm, fits 18mm ring PCB)
- **Charger**: TP4056 (SOP-8), 100mA charge current (RPROG=12K)
- **Protection**: DW01+FS8205 (over-discharge cutoff at 2.5V)
- **Regulator**: nRF52840 internal DC/DC + LDO (1.8V core, 3.3V I/O)
- **LIS3DH supply**: 3.3V from nRF52 (30µA active, 1µA sleep)

### Power budget

| State | Current | Duration per event | Daily use estimate | Daily mAh |
|-------|---------|-------------------|-------------------|-----------|
| Deep sleep (BLE adv) | 15µA | continuous | 24h | 0.36 |
| Active (gesture + BLE notify) | 5mA | 500ms | 50 taps | 0.03 |
| Haptic buzz | 50mA | 100ms | 30 buzzes | 0.04 |
| Data streaming | 8mA | 2s | 5 sessions | 0.02 |
| **Total daily** | | | | **~0.45 mAh** |

**Estimated life on 60mAh: ~13 days** (theoretical). **Realistic: 3-5 days** (includes advertising overhead, connection intervals, retries, temperature).

---

## 6. Charging

- **Cradle input**: Qi wireless (WPC 1.2, 5W) OR USB-C direct
- **Qi receiver**: TI BQ51003 (WCSP-20, 2.3×2.9mm) + 15mm wound ferrite coil
- **Charge current**: 100mA (safe for 60mAh cell, ~0.17C)
- **Charge time**: ~45 min from empty (60mAh / 100mA × 1.3 efficiency)
- **Charge termination**: TP4056 stops at 4.2V, 0.1C cutoff

---

## 7. Enclosure

- **Material**: Resin 3D print (SLA, smooth surface)
- **Sizes**: S (US 5-6 / 15.7mm), M (US 7-8 / 17.3mm), L (US 9-10 / 19.0mm)
- **Wall thickness**: 1.5mm minimum
- **Height**: 8mm (band width)
- **Sealing**: Conformal coating on PCB + silicone O-ring between shell halves
- **Assembly**: Top shell + bottom ring band, press-fit with PCB sandwiched
- **Pogo pins**: Flush with bottom surface, recessed 0.3mm

---

## 8. Communication protocol

BLE GATT service:

```
Service: Merlin Ring (UUID: AAAA0001-0000-0000-0000-000000000000)
  Characteristic: Gesture (UUID: AAAA0001-0000-0000-0000-000000000001)
    Properties: Notify
    Value: uint8
      1 = tap
      2 = double_tap
      3 = triple_tap
      4 = long_press
      5 = tilt_up
      6 = tilt_down
    Descriptor: CCCD (0x2902)

  Characteristic: Battery Level (UUID: 00002A19-0000-1000-8000-00805F9B34FB)
    Properties: Read, Notify
    Value: uint8 (0-100%)
```

Phone scans for `Merlin-Ring` advertisement, connects, enables gesture notify. On disconnect, phone attempts reconnect with 5s backoff.

---

## 9. Mechanical constraints

| Parameter | Value |
|-----------|-------|
| PCB diameter | 18mm (size S: 16mm) |
| PCB thickness | 0.8mm (flexible, staggered rigid sections) |
| Max component height | 3.0mm (top side), 1.5mm (bottom side) |
| Pogo pin height | 2.0mm compressed, 3.0mm uncompressed |
| Ring weight target | <8g |
| Center of mass | Inside finger, not on top |

---

## 10. Development order

1. **Week 1**: nRF52840 DK + LIS3DH breakout on breadboard. Single tap → serial print.
2. **Week 2**: Full gesture state machine (5 gestures). Debounced, reliable.
3. **Week 3**: BLE GATT service. Gesture events visible on phone (nRF Connect).
4. **Week 4**: Haptic + LED + battery ADC. Buzz patterns, RGB states, battery read.
5. **Week 5**: Custom flexible PCB design (KiCad) → order from JLCPCB.
6. **Week 6**: Charging cradle (Qi receiver + pogo pins + 3D printed base).
7. **Week 7**: Enclosure design (S/M/L) + resin 3D print.
8. **Week 8**: Full integration: gesture → BLE → phone → server → AI → response → haptic.
