# zenvision-linux

> 🟢 **The first open-source Linux driver for the ASUS ZenVision lid OLED** — the
> protocol was reverse-engineered from scratch (Ghidra on MyASUS). Want live
> applets and audio-reactive visualisers on top? See the companion app
> **[zenvision-studio](https://github.com/tarpediem/zenvision-studio)**.

Userspace Linux driver for the **ASUS ZenVision** lid OLED — the 3.5", 256×64
monochrome screen embedded in the lid of the **ASUS Zenbook 14X OLED Space
Edition (UX5401ZAS)**.

ASUS only ships software for this screen on Windows (inside MyASUS). This project
reverse-engineers the USB protocol and lets you drive the panel from Linux:
show images, play animations, or display whatever you like.

> Status: **working** on UX5401ZAS. Other ASUS lid-OLED models may use a similar
> protocol — reports and PRs welcome.

![demo](docs/demo.gif)

## How it works

The lid screen is a Nuvoton M480 USB device (`0b05:8835`). It is **not** a DRM
display — you don't get a `/dev/fb`; instead you push a 256×64, 4-bit-grayscale
framebuffer to a bulk endpoint after a small command handshake. Full details in
[PROTOCOL.md](PROTOCOL.md).

## Requirements

- Python 3.9+
- [`pyusb`](https://pypi.org/project/pyusb/) and [`Pillow`](https://pypi.org/project/Pillow/)
- `libusb-1.0`
- Raw USB access (root, or the provided udev rule)

```bash
python -m venv .venv && . .venv/bin/activate
pip install pyusb pillow
```

## Usage

```bash
# Static image (auto-resized to 256x64, converted to grayscale)
sudo ./zenvision.py image picture.png

# White test pattern / clear
sudo ./zenvision.py image --white
sudo ./zenvision.py off

# Play a folder of frames as a smooth animation
sudo ./zenvision.py anim frames/ --fps 20
```

Brightness: `--bright 0xff` (scale is approximate; tune by eye).

### Generate the demo animation

`examples/spark_demo.py` renders a generic rotating-starburst animation into a
`frames/` folder you can feed to `anim`:

```bash
pip install pillow
python examples/spark_demo.py --out frames --w 256 --h 64
sudo ./zenvision.py anim frames/ --fps 20
```

Want a logo? Render any monochrome 256×64 frames into a folder and point `anim` at
it. (Tip: `rsvg-convert` an SVG, or `ffmpeg -i clip.gif frames/%03d.png`.)

## Running without root (udev)

Copy the rule so your user can access the device:

```bash
sudo cp udev/99-zenvision.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then run without `sudo` (you may need to be in the `plugdev` group).

## Notes & safety

- The panel is firmware-powered and survives a re-plug; experiments are recoverable
  with a reboot. Sending malformed control reports on the HID interface can soft-reset
  the MCU (it re-enumerates cleanly) — this driver only uses the vendor interface.
- This is an independent, unofficial project. Not affiliated with or endorsed by ASUS.
- No ASUS firmware, binaries, or decompiled code are included or required.

## Contributing

If you have another ASUS model with a lid OLED, please open an issue with:
`lsusb`, your model number, and whether the framing here works. The protocol doc
is written to make porting straightforward.

## License

[MIT](LICENSE).
