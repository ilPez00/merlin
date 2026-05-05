# Merlin HUD — Custom Shield PCB Spec

## Motivation

The XIAO ESP32S3 Sense provides the controller, camera, and mic. Everything else (IMU, OLED, encoder, battery charger) connects via headers. A custom shield PCB eliminates wiring, adds reliability, and fits inside the glasses mount.

## Form factor

| Property      | Value                         |
|---------------|-------------------------------|
| Dimensions    | 50mm × 22mm                   |
| Stackup       | 2-layer, 1.6mm FR4, ENIG      |
| Mounting      | 4× M2 holes at corners         |
| Edge connector| XIAO castellated pads on bottom|
| Weight (bare) | ~6g                           |

## Schematic blocks

### 1. Power

```
USB-C ──> TP4056 ──> XB5356A ──> XIAO 5V pin
                │                  │
                └──> XC6206 ──> 3.3V rail (OLED, IMU)
```

- TP4056 LiPo charger with USB-C input, 1A charge current (RPROG = 1.2K)
- XB5356A protection IC for over-discharge cutoff (2.5V threshold)
- 3.3V LDO (XC6206P332MR) for OLED/IMU (XIAO has its own regulator, but extra rail prevents IMU noise)
- 4.7µF + 0.1µF decoupling on every IC
- Battery voltage divider (100K + 47K) → XIAO GPIO9 ADC

### 2. I2C Bus (shared, 4.7K pull-ups to 3.3V)

```
XIAO D4/D5 ──┬── JST SH 4-pin ──> OLED display
             ├── MPU6050 (QFN-24 or breakout)
             └── (future) BH1750 light sensor
```

### 3. Encoder Input

```
EC11 encoder ──┬── CLK ── 10nF ── XIAO D0
               ├── DT  ── 10nF ── XIAO D1
               └── SW  ── 10K ── XIAO D2
                               └── 3.3V
```

- JST SH 5-pin connector: CLK, DT, SW, GND, 3.3V
- 10nF caps on CLK/DT for hardware debounce
- 10K pull-up on SW to 3.3V

### 4. BLE Antenna / Ring Input

- ESP32-S3 has built-in BLE — no additional IC needed
- U.FL/IPEX connector for external 2.4GHz antenna (shared WiFi + BLE)
- Body blockage degrades internal PCB antenna significantly, so external antenna recommended when worn on glasses
- Future: dedicate UART header (J5) for standalone BLE ring receiver module (e.g. nRF52840) if range needs improvement

### 5. SD Card (for offline diary)

- XIAO ESP32S3 Sense has onboard microSD slot — use it for offline diary storage
- Add JST SH 4-pin header breakout to access microSD lines (D11/D12/D13/D10) for external SD socket if needed

## Full BOM (SMD, on-shield)

| Ref  | Part                     | Package     | Qty |
|------|--------------------------|-------------|-----|
| U1   | TP4056                   | SOP-8       | 1   |
| U2   | XC6206P332MR             | SOT-23-3    | 1   |
| U3   | MPU6050                  | QFN-24 4×4  | 1   |
| U4   | XB5356A                  | SOT-23-5    | 1   |
| J1   | USB-C (charge only)      | 6-pin SMD   | 1   |
| J2   | JST SH 4-pin (OLED)      | SMD         | 1   |
| J3   | JST SH 5-pin (encoder)   | SMD         | 1   |
| J4   | U.FL connector           | SMD         | 1   |
| R1,R2| 4.7K 0603                | 0603        | 2   |
| R3,R4| 10K 0603                 | 0603        | 2   |
| R5   | 100K 0603 (batt divider) | 0603        | 1   |
| R6   | 47K 0603 (batt divider)  | 0603        | 1   |
| R7   | 1.2K 0603 (RPROG)        | 0603        | 1   |
| C1-C5| 0.1µF 0603               | 0603        | 5   |
| C6   | 4.7µF 0603               | 0603        | 1   |
| C7-C9| 10nF 0603                | 0603        | 3   |
| D1   | Red LED (charge indicator)| 0603 LED    | 1   |
| D2   | 1N5819 Schottky          | SOD-123     | 1   |

## Design rules

| Parameter  | Value           |
|------------|-----------------|
| Trace width| 0.3mm min (power: 0.5mm) |
| Clearance  | 0.2mm (8mil)    |
| Copper pour| GND on bottom   |
| Vias       | 0.3mm drill, 0.6mm pad |
| Board edge | 0.5mm fillet on all corners |
| I2C traces | <50mm, matched length |

## PCB layout notes

```
        ┌──────────────────────────────────────┐
        │  ┌──────┐  ┌───┐  ┌───┐  ┌─────┐   │
        │  │ USB-C│  │U1 │  │U2 │  │U4   │   │
        │  └──────┘  │TP4│  │LDO│  │Prot │   │
        │             │056│  │   │  │ect  │   │
        │  ┌──┐      └───┘  └───┘  └─────┘   │
        │  │J4│┌────┐  ┌──────┐  ┌──────┐     │
        │  │RF││ MPU│  │J2    │  │J3    │     │
        │  └──┘│6050│  │OLED  │  │ENCO  │     │
        │      └────┘  └──────┘  └──────┘     │
        │= = = = = = = = = = = = = = = = = = │ GND pour
        │   ●   ●         ●   ●               │ M2 holes
        │  [=== XIAO ESP32S3 Sense ===]       │
        └──────────────────────────────────────┘
```

- XIAO sits on the bottom edge (castellated pads soldered directly)
- Battery charger (U1) at top-left, near USB-C
- MPU6050 (U3) centered for neutral vibration sensing
- Connectors J2/J3 at right edge for easy cable routing
- Keep high-current charge path (USB-C → TP4056 → battery) separate from sensitive analog (IMU)

## Manufacturing (JLCPCB)

| Step   | Cost  | Lead time |
|--------|-------|-----------|
| PCB    | $2    | 2-3 days  |
| PCBA   | $8-12 | 5-7 days  |
| Shipping| $6   | 3-5 days  |

- PCBA: JLCPCB assembles all SMD parts (including U1-U4, resistors, caps). XIAO is hand-soldered afterward.
- Stencil: Not needed for QTY 1 (hand-solder SMD or use hotplate).

## Assembly notes

1. Solder all SMD passives and ICs first (reflow or hotplate at 245°C)
2. Solder JST SH connectors, USB-C, U.FL (hand solder)
3. Solder XIAO ESP32S3 Sense to castellated pads (flux, drag-solder)
4. Test power rail: 3.3V at TP2, 4.2V at battery connector
5. Test I2C scan: addresses 0x3C (OLED), 0x68 (MPU6050)
6. Test encoder: CLK/DT toggling on rotation

## Revision history

| Rev | Changes |
|-----|---------|
| A   | Initial prototype |
