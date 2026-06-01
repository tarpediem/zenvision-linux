# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A userspace Linux driver for the **ASUS ZenVision lid OLED** — the 3.5" 256×64
4-bit-grayscale PMOLED in the lid of the ASUS Zenbook 14X OLED Space Edition
(UX5401ZAS). The USB protocol was reverse-engineered from scratch (Ghidra on
MyASUS); there is **no vendor source, firmware, or decompiled code** in this repo.
The panel is a Nuvoton M480 USB device, VID:PID `0b05:8835`.

This is *not* a DRM display — there is no `/dev/fb`. You push a framebuffer to a
bulk USB endpoint after a small command handshake.

## Commands

```bash
# Environment
python -m venv .venv && . .venv/bin/activate
pip install pyusb pillow            # or: pip install -r requirements.txt

# Drive the panel (needs root, or install the udev rule below)
sudo ./zenvision.py image picture.png [--bright 0xff] [--hold N]
sudo ./zenvision.py image --white                 # white test pattern
sudo ./zenvision.py off                           # clear to black
sudo ./zenvision.py anim frames/ --fps 20 [--dur N]

# Generate the demo animation (writes PNG frames)
python examples/spark_demo.py --out frames --w 256 --h 64

# Run without sudo: install the udev rule, then re-plug / re-trigger
sudo cp udev/99-zenvision.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

There is no build step, linter config, or test suite. Verification is manual: run
a command against the physical device and look at the screen. Without the hardware
attached, `ZenVision.__init__` raises `RuntimeError("...not found")`.

## Architecture

Everything lives in **`zenvision.py`** (~190 lines), with **`PROTOCOL.md`** as the
authoritative spec. Treat PROTOCOL.md and the code as a matched pair — any change
to framing/encoding in one must be mirrored in the other.

Three layers, top to bottom:

1. **`encode(img)`** — pure function, PIL image → 8704-byte frame. The encoding is
   the subtle part and is exact, not approximate:
   - Convert to grayscale, take the top nibble of each pixel (16 levels), row-major.
   - Pack 2 pixels/byte **with a pair swap**: within each 4-pixel group, the two
     output bytes are emitted in swapped order (`data[2k]` holds pixels s+2/s+3,
     `data[2k+1]` holds s/s+1). This is a panel addressing quirk — don't "simplify"
     it away. → 8192-byte framebuffer.
   - Wrap into **17 × 512-byte packets** (8704 bytes total): each packet's byte 0 is
     its index 0–16; packet 16 has `01` at byte 1 as an end marker; bytes 4–511 carry
     508 payload bytes each.

2. **`ZenVision`** — thin USB wrapper over **interface 0 only** (vendor class 0xFF).
   Detaches any kernel driver, claims the interface. Two endpoints: `EP_CMD = 0x03`
   (interrupt OUT, 512-byte command buffers) and `EP_BULK = 0x07` (bulk OUT, the
   8704-byte frame). Two display flows:
   - **Static** (`show_image`): begin cmd → bulk frame → apply/brightness cmd. Send
     **once**; re-sending flickers.
   - **Streaming** (`stream_begin` + `stream_frame`): one mode-2 + brightness cmd,
     then push frames bulk-only in a loop → flicker-free animation (~50 fps cap).

3. **`main()`** — argparse CLI (`image` / `off` / `anim` subcommands) wiring the
   above together.

## Hardware constraints to respect

- **Only ever touch interface 0** (vendor). Interface 1 is HID for the *keyboard*
  RGB/LEDs, not the OLED. Malformed HID control reports can soft-reset the MCU.
- **Never send the theme-select commands** (`33 01 IDX` then `30 05 02 00 01`). They
  hand control back to the MCU's autonomous animation loop, which then fights/overdraws
  your frames. See the ⚠️ note in PROTOCOL.md.
- The panel is firmware-powered, survives re-plug, and re-enumerates cleanly; bad
  experiments are recoverable with a reboot. Nothing in ACPI/WMI needs poking.
- The status endpoint `0x82` always returns zeros — no useful feedback for this model.

## Porting

Other ASUS lid-OLED models may use similar framing but it can differ. PROTOCOL.md is
written to make porting straightforward; the command opcodes and packet framing are
the most likely things to vary.
