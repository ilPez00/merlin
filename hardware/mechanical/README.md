# Merlin HUD — Frame Mount Mechanical Spec

## Target frame

**Ray-Ban Wayfarer (RB2140)** — the iconic frame.

| Dimension          | Value  |
|--------------------|--------|
| Lens height        | ~37mm  |
| Bridge width       | ~14mm  |
| Temple width (hinge)| ~16mm |
| Top bar width      | ~5mm   |
| Top bar span (between hinges) | ~130mm |

## Design principles

1. **No modification** — clip-on/off, no adhesive, no drilling
2. **Weight < 30g total** on the frame (ideally < 20g)
3. **Center of mass on top bar** — avoid loading temples (ear pressure)
4. **Low profile** — should look like chunky glasses, not a VR headset
5. **Repeatable** — printable on common 3D printers (180×180mm bed)

## Part 1: Top-Bar Clamp (base)

### Geometry
- C-channel that wraps around the top bar of the Wayfarer frame
- Inner channel: 52mm span (centered between hinge points) × 5.5mm wide × 4.5mm deep
- Wall thickness: 2mm
- Tapered edges (1mm at tips) for visual blending
- Four M2 brass heat-set inserts (3mm deep, flush) at corners

### Interference fit
- Inside channel lined with 1mm silicone adhesive pad (sold as anti-slip strips)
- Slight inward spring tension (~0.2mm undersized channel width) for grip
- Removable by prying open at the front edge

### Weight target
- Nylon 12 (MJF): ~1.8g
- PETG (FDM): ~2.2g

```
  ┌──────────────────────────────────────┐
  │  ┌────────────────────────────────┐  │  ← channel roof
  │  │  ════ ════ ════ ════          │  │  ← silicone pads
  │  │  ┌─┐         ┌─┐              │  │
  │  │  │M│  FRAME  │M│              │  │  ← M2 inserts
  │  │  └─┘         └─┘              │  │
  │  └────────────────────────────────┘  │
  └──────────────────────────────────────┘
  (top view, frame top bar runs through)
```

## Part 2: Electronics Housing (main body)

### Geometry
- Rectangular pod: 55mm × 22mm × 12mm (L×W×H)
- Internal cavity: 50mm × 18mm × 6mm
- Fillets: 2mm radius on all exterior edges
- Draft angle: 3° for printability

### Features
- **Camera hole**: 4mm diameter on front face, centered 3mm from top edge, aligned with OV2640 sensor on XIAO
- **Encoder slot**: 6mm × 3mm opening on left side, 12mm from front edge
- **Power switch slot**: 5mm × 2mm on right side, 8mm from rear edge
- **Ventilation**: 12× 0.5mm holes in a 4×3 grid on top face
- **Standoffs**: 4× M2 threaded standoffs (2mm tall) molded into bottom face, aligning with clamp's M2 inserts
- **USB-C access**: 10mm × 5mm cutout on right side for XIAO's USB-C port

### Cabling
- JST SH 4-pin ribbon exit: 3mm × 1.5mm slot on left edge, near rear
- Battery wire exit: 4mm × 2mm slot on right edge, near rear

### Weight target
- Nylon 12 (MJF): ~4.5g
- PETG (FDM): ~5.5g

```
             ┌─────────────┐
     cam hole│ ●           │
             │             │
  ┌──────────┴─────────────┴──────────┐
  │  ┌───────────────────────────┐    │
  │  │ [XIAO]          [MPU6050] │    │
──┤  │                     [OLED]│    ├── ← encoder slot
  │  │          [BAT CHARGER]    │    │
  │  └───────────────────────────┘    │
  │                     ┌──┐          │
  │           USB-C cut │  │          │
  │                     └──┘          │
  └───────────────────────────────────┘
  ║       ║                   ║       ║  ← standoffs to clamp
```

## Part 3: OLED Display Bracket

### Geometry
- Clips onto the left temple arm, near the hinge (30-60mm from hinge)
- Temple offset: wraps around ~14mm wide temple, 5mm thick grip
- Arm length: 25mm with a 45° downward bend at the end
- Display cradle: holds the SSD1306 module (25mm × 12mm × 2mm) at ~45° angle
- The wearer glances down-left to see the display

### Adjustability
- Pivot joint: M1.6 screw + nut at the temple attachment point
- Range: ±15° rotation, locked with a wing nut or friction fit
- The ribbon cable (JST SH 4-pin, 100mm silicone) routes along the temple under the bracket

### Weight target
- Nylon 12 (MJF): ~2g
- PETG (FDM): ~2.5g

```
   ┌──────────────────────┐
   │     TEMPLE ARM       │
   │  ====================│========
   │  ║                  ║│    ← bracket wraps here
   │  ║    ┌─────────────║┐
   │  ║    │Display      ║│
   │  ║    │    45° bend ││
   │  ║    └─────────────┘│
   └──────────────────────┘
```

## Part 4: Temple Battery Pockets (v1, alternative to collar clip)

If using distributed battery cells (2× 250mAh), each temple arm has a small pocket.

### Geometry
- Left temple pocket: 45mm × 14mm × 5mm, sits between hinge and ear
- Right temple pocket: same dimensions
- Snap-fit lid with battery contacts (spring-loaded pogo pins)
- Weight: 1.5g each (total 3g for both)

### Wiring
- Thin 30AWG silicone wires (2 per side) route along the inside of the temple, through the hinge, into the main housing
- Left cell → housing (parallel with right cell)
- Provides ~500mAh total, distributed evenly

## Part 5: Battery Cable Guide (if using collar clip instead)

If using a collar-clipped battery, a small cable guide clips under the temple to route the wire cleanly.

### Geometry
- Thin U-channel: 12mm × 5mm × 3mm
- Hinged snap-fit lid
- Weight: 0.3g

```
         ┌────┐
    temple│ ║  │
     arm──╫── ║──
           │ ║  │
           └────┘
```

## 3D printing specs

| Parameter     | Nylon 12 (MJF)     | PETG (FDM)           |
|---------------|--------------------|-----------------------|
| Layer height  | 0.1mm              | 0.15mm              |
| Infill        | 100% (MJF default) | 40% gyroid           |
| Supports      | None (self-supporting)| Tree supports for encoder slot|
| Post-process  | Bead-blast          | Vapor smooth or sand|
| Color         | Black or matte gray | Black               |
| Cost (3 parts)| ~$13 (JLCPCB)      | ~$0.50 (home printer)|

## Files to generate

```
mechanical/
  merlin-visor-assembly.step    ─ Full assembly reference model
  top-bar-clamp.stl             ─ Part 1
  electronics-housing.stl       ─ Part 2
  oled-bracket.stl              ─ Part 3
  temple-battery-left.stl       ─ Part 4a (v1 battery)
  temple-battery-right.stl      ─ Part 4b (v1 battery)
  battery-cable-guide.stl       ─ Part 5 (collar-clip version)
  ring-cradle.stl               ─ Part 6: charging dock for BLE ring (optional)
  drawings/
    assembly-drawing.pdf        ─ 2D assembly with dimensions
    exploded-view.pdf           ─ Exploded view for assembly instructions
```

## Assembly sequence

1. Press 4× M2 brass heat-set inserts into the clamp (150°C soldering iron, 3mm depth)
2. Attach silicone pads inside the clamp channel
3. Slide housing onto clamp, fasten with 4× M2×6mm pan-head screws
4. Route OLED ribbon cable through housing slot, plug into J2
5. Route battery wires through housing slot, plug into J3 (via TP4056)
6. Insert XIAO into housing, plug USB-C if needed for flash
7. Clip the assembled unit onto the Wayfarer top bar
8. Attach OLED bracket to temple, position display, tighten pivot screw
9. Clip battery to collar, route wire along temple with cable guide
10. Power on: green LED on TP4056 module confirms battery OK

## Ergonomic notes

- The display bracket may be swapped to the right temple if the user is left-eye dominant
- The 45° downward angle avoids blocking forward vision — the display sits in the lower-left periphery
- If the user wears prescription Wayfarers, verify the bridge clearance before printing (the clamp should not touch the lenses)
- **Two battery strategies:**
  - **Collar clip** (dev kit): lighter on head (~25g). Battery on shirt collar, thin wire to housing. Best for desk or stationary use.
  - **Distributed temples** (v1): slightly heavier on head (~30g total). Batteries on both temples, balanced weight. Better for active use (walking, skiing, lifting).
- Incognito mode reduces display burn and encourages longer wear — screen off, but device stays on for audio passthrough
- The encoder sits on the left side of the housing, operable by the left hand (thumb reach). Left-handed users can mirror the design.
