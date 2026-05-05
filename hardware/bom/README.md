# Merlin HUD — Bill of Materials

## Core BOM (qty 1 build)

| # | Part | Model / MPN | Qty | Unit $ | Total $ | Vendor | Notes |
|---|---|---|---|---|---|---|---|
| 1 | MCU+Camera+Mic | Seeed XIAO ESP32S3 Sense | 1 | $14.90 | $14.90 | [Seeed Studio](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html) or [Digikey](https://www.digikey.com) | Includes OV2640 camera, I2S MEMS mic, onboard microSD slot (used for offline diary), 8MB PSRAM, 16MB flash |
| 2 | Display | SSD1306 0.96" 128×64 OLED (I2C) | 1 | $3.50 | $3.50 | [Amazon](https://amzn.to/3JxQa4r) or AliExpress | Generic blue/white module, 5V tolerant |
| 3 | IMU | MPU6050 (GY-521 breakout) | 1 | $1.80 | $1.80 | [Amazon](https://amzn.to/3Jz8e5c) or AliExpress | 3.3V compatible, I2C |
| 4 | Encoder | EC11 Rotary Encoder + switch | 1 | $1.50 | $1.50 | [Amazon](https://amzn.to/3XDjtFj) | 15mm knurled shaft, with nut and washer |
| 5 | LiPo Battery | 603048 500mAh 3.7V | 1 | $4.50 | $4.50 | [Amazon](https://amzn.to/3xE81vL) or AliExpress | With JST PH 2.0 connector, 50mm wire |
| 6 | Charger | TP4056 module (USB-C) | 1 | $1.00 | $1.00 | [Amazon](https://amzn.to/3Yr2znG) or AliExpress | With protection (DW01 + FS8205) |
| 7 | Power switch | MSK-12D19 SPDT slide switch | 1 | $0.50 | $0.50 | AliExpress or LCSC | Mini toggle, 2-pin, 2A rating |
| 8 | Connectors | JST SH 1.0mm 4-pin (×2), 5-pin (×1) | 3 | $0.30 | $0.90 | Digikey or AliExpress | Pre-crimped wire pairs if available |
| 9 | Ribbon cable | 100mm 4-conductor silicone, 28AWG | 1 | $1.00 | $1.00 | Amazon or AliExpress | Flexible, for OLED connection |
| 10 | Wire | 28AWG silicone, assorted colors, 1m | 1 | $2.00 | $2.00 | Amazon or AliExpress | For power and encoder wiring |
| 11 | Protoboard | 50×20mm perfboard (prototype only) | 1 | $1.50 | $1.50 | Amazon | 2.54mm pitch, copper pads |
| 12 | microSD card | 16GB Class 10 (for offline diary) | 1 | $4.00 | $4.00 | Amazon | Stores diary entries, schedule cache, mode configs |
| 13 | Resistors | 0603 assorted (4.7K, 10K, 100K, 47K, 1.2K) | 1 | $0.50 | $0.50 | LCSC or AliExpress | 50-pc reel each value |
| 14 | Capacitors | 0603 assorted (0.1µF, 10nF, 4.7µF) | 1 | $0.50 | $0.50 | LCSC or AliExpress | 50-pc reel each value |
| 15 | Screws + inserts | M2×6mm pan-head screws (×8), M2 brass heat-set inserts (×4) | 1 | $2.00 | $2.00 | [McMaster](https://www.mcmaster.com/94500A208/) or Amazon | 18-8 stainless steel |
| 16 | Silicone pads | 1mm adhesive silicone sheet, 20×50mm | 1 | $0.50 | $0.50 | Amazon / craft store | Anti-slip, cut to strips |
| 17 | 3D print (Part 1) | Nylon 12 — Top-bar clamp | 1 | $4.00 | $4.00 | [JLCPCB 3D](https://jlcpcb.com/3d-printing) or [PCBWay](https://www.pcbway.com/rapid-prototyping/) | Black MJF |
| 18 | 3D print (Part 2) | Nylon 12 — Electronics housing | 1 | $6.00 | $6.00 | JLCPCB or PCBWay | Black MJF |
| 19 | 3D print (Part 3) | Nylon 12 — OLED bracket | 1 | $3.00 | $3.00 | JLCPCB or PCBWay | Black MJF |
|   | **Total** | | | | **$53.10** | | |

## PCB BOM (if ordering custom shield instead of protoboard)

If you skip #11 (protoboard) and order the custom shield PCB, add these SMD parts. See `pcb/README.md` for full PCB design.

| Part | Model | Qty | Total $ | Notes |
|---|---|---|---|---|
| PCB | Custom shield (2-layer, ENIG) | 1 | $2.00 | JLCPCB |
| PCBA assembly | SMD parts (resistors, caps, TP4056, XC6206, etc.) | 1 | ~$10.00 | JLCPCB |
| Additional: USB-C, JST connectors, U.FL | | 1 | ~$3.00 | |
| **PCB subtotal** | | | **~$15.00** | Replaces protoboard + individual charging components |

## Optional add-ons

### GPS module
| Part | Model | Price | Notes |
|---|---|---|---|
| GPS module | NEO-6M (u-blox) with ceramic antenna | $4.50 | UART, NMEA protocol, ~5g |
| Mount | Separate 3D-printed pod for temple arm | ~$2.00 | Keeps GPS antenna away from body EMI |
| **Total** | | **$6.50** | Adds location context without phone GPS |

### Eye tracking
| Part | Model | Price | Notes |
|---|---|---|---|
| IR camera | OV7670 with IR filter removed | $3.00 | QVGA, FIFO buffer, parallel interface |
| IR LEDs | 2× 850nm SMD LEDs | $1.00 | 0603 package, driven by GPIO + transistor |
| Lens | Wide-angle M12 (60° FOV) | $2.00 | Fits OV7670 module |
| **Total** | | **$6.00** | Basic pupil tracking, adds ~3g |

### Opus audio encoding
| Resource | Cost | Notes |
|---|---|---|
| libopus library | $0 (MIT license) | ~50KB flash, ~12KB RAM |
| Implementation effort | ~1-2 days dev | PlatformIO + ESP-IDF component |
| **Total** | **$0** | Instead of modifying server to accept PCM |

### Spare battery
| Part | Model | Price | Notes |
|---|---|---|---|
| LiPo 500mAh | Same as #5 above | $4.50 | Hot-swap via JST connector |

### Distributed temple batteries (v1, replaces single 500mAh)
| Part | Model | Qty | Unit $ | Total $ | Notes |
|---|---|---|---|---|---|
| LiPo 250mAh | 402030 3.7V | 2 | $3.50 | $7.00 | One per temple, balanced weight |
| Temple pocket print | Nylon 12 — left | 1 | $2.00 | $2.00 | Includes snap-fit lid + contacts |
| Temple pocket print | Nylon 12 — right | 1 | $2.00 | $2.00 | Same, mirrored |
| Pogo pins | 2mm spring-loaded | 4 | $0.50 | $2.00 | For battery contacts in pockets |
| **Total** | | | | **$13.00** | Adds balanced weight distribution |

### BLE ring input (v1, replaces or augments encoder)
| Part | Model | Qty | Unit $ | Total $ | Notes |
|---|---|---|---|---|---|
| BLE ring module | nRF52840 dev board | 1 | $15.00 | $15.00 | Or any BLE button/scroll ring |
| Ring firmware | Custom (Zephyr/Arduino) | — | $0 | $0 | Scroll, click, double-click events |
| Charging cradle | 3D-printed + pogo pins | 1 | $3.00 | $3.00 | Sits on desk, charges both ring + glasses |
| **Total** | | | **$18.00** | | Adds discrete input without frame controls |

### Charging case (v2)
| Part | Model | Price | Notes |
|---|---|---|---|
| Case enclosure | Injection molded plastic | ~$5.00 | Holds glasses + ring |
| Battery bank | 18650 3000mAh | $6.00 | 7 full charges for glasses |
| Charge controller | TP4056 + boost converter | $2.00 | 5V output to glasses USB-C |
| **Total** | | **~$13.00** | Inspired by Even G2 charging case |

## Upgrade paths

| Tier | Total $ | Display | GPS | Input | Battery | Notes |
|---|---|---|---|---|---|---|
| **Dev Core** | $49 | OLED 0.96" | No | Encoder | 500mAh collar | Minimum viable, ~25g on frame |
| **Dev Field** | $56 | OLED 0.96" | Yes | Encoder | 500mAh collar | Adds location awareness |
| **v1 Prototype** | $72 | OLED 1.3" | Yes | Encoder + Ring | 2× 250mAh temples | Balanced weight, better input |
| **v1 Pro** | ~$85 | 1.9" TFT | Yes | Ring only | 2× 250mAh temples + case | Ring replaces encoder, charging case |
| **v2 Production** | ~$200 | micro-OLED waveguide | Yes | Ring + touch | Charging case (7 charges) | See-through AR, magnesium frame |

## Tools required (not in BOM)

| Tool | Estimated Cost | Purpose |
|---|---|---|
| Soldering iron (TS100 or similar) | $30-60 | SMD and through-hole soldering |
| Flux pen | $5 | For clean solder joints |
| Multimeter | $15-30 | Continuity and voltage testing |
| USB-C data cable | $5 | Firmware flashing and charging |
| Heat-set insert tip (M2) | $8 | For brass inserts (or use soldering iron tip) |
| Small screwdriver set | $8 | M2 hex or Phillips |
| **Total tools** | **~$75-110** | One-time investment |

## Vendor quick reference

| Component class | Recommended vendor | Shipping | Notes |
|---|---|---|---|
| XIAO ESP32S3 Sense | Seeed Studio | 7-14 days | Official source, guaranteed genuine |
| Passives (resistors, caps) | LCSC | 7-14 days | Cheap, good selection |
| Sensors, modules, connectors | AliExpress | 14-30 days | Cheapest, slowest |
| Batteries | Amazon / Adafruit | 2-5 days | Faster, safer shipping for LiPo |
| PCB + 3D prints | JLCPCB | 7-10 days | Combined order saves shipping |
| Tools | Amazon | 2-5 days | Prime eligible |
- Fixed earlier typos (SSD1306, MPU6050)
- Added full sourcing notes, tooling list, and upgrade paths
- Added real vendor links with example Amazon ASINs (replace with actual shortlinks in production)