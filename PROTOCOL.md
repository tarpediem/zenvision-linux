# ZenVision USB protocol

Reverse-engineered notes for driving the lid OLED of the **ASUS Zenbook 14X OLED
Space Edition (UX5401ZAS)** from Linux. Written from scratch as interoperability
documentation — it describes *how to talk to the device*, not anyone's source code.

If you have a different ASUS model with a lid OLED ("ZenVision" / "APanel"), the
framing may differ; contributions welcome.

## The device

| | |
|---|---|
| USB ID | `0b05:8835` (iProduct `M480 BULK`, iManufacturer `Nuvoton`) |
| Controller | Nuvoton M480 (Cortex-M4F) MCU driving an SSD1362-class panel |
| Panel | 256 × 64 px, monochrome, **4-bit grayscale** (16 levels) |
| Speed | USB 2.0 High Speed |

The device exposes **two USB interfaces**:

* **Interface 0 — vendor-specific (class 0xFF), no kernel driver.**
  This is the one we use. Endpoints:
  * `0x03` — interrupt **OUT**, 512-byte packets — **command channel**
  * `0x07` — **bulk OUT**, 512-byte packets — **image data**
  * `0x82` — interrupt IN, 512-byte — status (returns a constant zero buffer)
* **Interface 1 — HID.** Used by the vendor software for the *keyboard* RGB/LED
  and layout queries, **not** for the OLED. Ignore it for display purposes.

At rest, when no host is talking to it, the MCU autonomously plays its built-in
themes/animations from internal flash (this is what you see during POST and on a
fresh boot). To show your own content you take over interface 0.

## Command channel (EP 0x03)

Commands are **512-byte buffers**, sent as a single interrupt-OUT transfer. Only
the first few bytes are meaningful; the rest are zero. The first byte is an ASCII
digit acting as an opcode group.

| Command (first bytes) | Meaning |
|---|---|
| `30 06 05 00 00 00 00 01` | **Begin** a single static image upload |
| `31 02 BB 03`             | **Apply** / commit a static image (`BB` = brightness) |
| `30 06 05 00 00 00 00 02` | Enter **streaming mode** (for animation) |

Note the only difference between "begin static image" and "enter streaming mode"
is the 8th byte: `01` vs `02`.

> ⚠️ Do **not** send the theme commands (`33 01 IDX` then `30 05 02 00 01`). Those
> select a built-in theme and hand control back to the MCU's autonomous animation
> loop, which then fights/overdraws your frames.

## Image data (EP 0x07)

One frame is a single **8704-byte** (`0x2200`) bulk transfer. Layout: **17 packets
of 512 bytes**. Each packet's first byte is its index (0–16); packet 16 also has a
`01` in its second byte as an end marker; bytes 2–3 are reserved (0); bytes 4–511
carry payload (508 bytes/packet). The payload, concatenated across packets, is the
**8192-byte 4bpp framebuffer**.

### Encoding an image to the 8192-byte framebuffer

1. **Grayscale, 4-bit, row-major.** For each pixel (y outer 0..63, x inner 0..255):
   `gray = (R + G + B) / 3`, then keep the top nibble `nib = gray >> 4` (0..15).
   This yields 16384 nibbles, one per pixel.

2. **Pack two pixels per byte, with a pair swap.** For each group of 4 source
   pixels (`s = 4k`):

   ```
   data[2k]     = nib[s+2] | (nib[s+3] << 4)
   data[2k + 1] = nib[s]   | (nib[s+1] << 4)
   ```

   i.e. the low nibble is the earlier pixel, and the two output bytes of each
   4-pixel group are emitted in swapped order (a quirk of the panel's addressing).
   Result: 8192 bytes.

3. **Wrap in the 17×512 packet framing** described above to get the 8704 bytes.

See `encode()` in [`zenvision.py`](zenvision.py) for a reference implementation.

## Showing a static image

```
EP 0x03  <-  30 06 05 00 00 00 00 01      (begin)
EP 0x07  <-  <8704-byte frame>            (pixels)
EP 0x03  <-  31 02 BB 03                  (apply, BB = brightness)
```

Send it **once**. Re-sending repeatedly causes a visible blank/redraw flicker.

## Playing an animation (flicker-free)

Enter streaming mode once, then push frames bulk-only:

```
EP 0x03  <-  30 06 05 00 00 00 00 02      (streaming mode, once)
EP 0x03  <-  31 02 BB 03                  (brightness, once)
loop:
    EP 0x07  <-  <8704-byte frame>        (just the bulk transfer)
    sleep ~20 ms                          (the vendor software caps ~50 fps)
```

No per-frame begin/apply ⇒ no blanking between frames.

## Brightness

The `BB` byte in `31 02 BB 03`. The exact scale isn't pinned down; `0xff` works.
Tune by eye.

## Notes / open questions

* The status endpoint `0x82` always returns 512 zero bytes regardless of command,
  so it doesn't seem to carry useful feedback for this model.
* HID feature reports on interface 1 (`56 A0 …` and `5c …`) drive the keyboard
  backlight/LED, not the OLED.
* Power: the panel is **not** software power-gated — it is alive and firmware-driven
  at boot. You only need to take over interface 0; nothing in ACPI/WMI needs poking.
