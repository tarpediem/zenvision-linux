#!/usr/bin/env python3
"""zenvision-linux — userspace driver for the ASUS ZenVision lid OLED.

Target: ASUS Zenbook 14X OLED Space Edition (UX5401ZAS), the 3.5" 256x64
monochrome PMOLED in the lid, exposed over USB as a Nuvoton M480 device
(VID:PID 0b05:8835).

The display protocol was reverse-engineered for interoperability; see
PROTOCOL.md for the full description.

Usage:
    sudo ./zenvision.py image  picture.png [--bright 0xff]
    sudo ./zenvision.py image  --white                  # white test pattern
    sudo ./zenvision.py off                             # clear (all black)
    sudo ./zenvision.py anim   frames_dir/ [--fps 20]   # play a frame folder

Requires: pyusb, pillow, and raw USB access (run as root or install the
provided udev rule). See README.md.
"""
import argparse
import glob
import sys
import time

import usb.core
import usb.util
from PIL import Image

VID, PID = 0x0B05, 0x8835
IFACE = 0
EP_CMD = 0x03    # interrupt OUT — control commands (512 bytes)
EP_BULK = 0x07   # bulk OUT      — framebuffer (8704 bytes)
W, H = 256, 64   # panel resolution
FRAME_BYTES = 8704


def encode(img):
    """PIL image -> 8704-byte ZenVision framebuffer (4bpp grayscale + framing).

    See PROTOCOL.md. Three stages: per-pixel 4-bit gray (row-major), 4bpp pack
    with the panel's pair-swap, then split into 17 x 512-byte packets each
    carrying a 1-byte index header.
    """
    img = img.convert("L")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    px = img.load()

    # 1) 4-bit gray per pixel, row-major
    n = bytearray(W * H)
    i = 0
    for y in range(H):
        for x in range(W):
            n[i] = px[x, y] >> 4
            i += 1

    # 2) pack to 4bpp (8192 bytes), with the 2-byte swap per 4-pixel group
    data = bytearray(8192)
    for k in range(4096):
        s = 4 * k
        data[2 * k] = n[s + 2] | (n[s + 3] << 4)
        data[2 * k + 1] = n[s] | (n[s + 1] << 4)

    # 3) frame into 17 x 512-byte packets (byte0 = packet index)
    out = bytearray(FRAME_BYTES)
    pos = d = 0
    while pos < FRAME_BYTES and d <= 0x1FFF:
        bp = pos & 0x1FF
        if bp == 0:
            out[pos] = (pos >> 9) & 0xFF
        elif bp == 1:
            if (pos >> 9) == 16:
                out[pos] = 1
        elif bp >= 4:
            out[pos] = data[d]
            d += 1
        pos += 1
    return bytes(out)


def _cmd(*head):
    b = bytearray(512)
    b[: len(head)] = bytes(head)
    return bytes(b)


class ZenVision:
    """Thin driver over the vendor interface (iface 0)."""

    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("ZenVision (0b05:8835) not found")
        try:
            if self.dev.is_kernel_driver_active(IFACE):
                self.dev.detach_kernel_driver(IFACE)
        except Exception:
            pass
        usb.util.claim_interface(self.dev, IFACE)

    def _c(self, data):
        self.dev.write(EP_CMD, data, timeout=3000)

    def _b(self, data):
        self.dev.write(EP_BULK, data, timeout=3000)

    def show_image(self, fb, bright=0xFF):
        """Display a single static framebuffer (begin -> data -> apply)."""
        self._c(_cmd(0x30, 0x06, 0x05, 0x00, 0x00, 0x00, 0x00, 0x01))  # begin
        self._b(fb)                                                    # pixels
        self._c(_cmd(0x31, 0x02, bright & 0xFF, 0x03))                 # apply

    def stream_begin(self, bright=0xFF):
        """Enter streaming/animation mode (frames pushed bulk-only, no flicker)."""
        self._c(_cmd(0x30, 0x06, 0x05, 0x00, 0x00, 0x00, 0x00, 0x02))  # mode 2
        self._c(_cmd(0x31, 0x02, bright & 0xFF, 0x03))                 # brightness

    def stream_frame(self, fb):
        self._b(fb)

    def close(self):
        try:
            usb.util.release_interface(self.dev, IFACE)
        except Exception:
            pass


def _load_frames(folder):
    files = sorted(glob.glob(folder.rstrip("/") + "/*.png") +
                   glob.glob(folder.rstrip("/") + "/*.gif") +
                   glob.glob(folder.rstrip("/") + "/*.jpg"))
    if not files:
        sys.exit("no image frames found in " + folder)
    return [encode(Image.open(f)) for f in files]


def main():
    ap = argparse.ArgumentParser(description="Drive the ASUS ZenVision lid OLED from Linux.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("image", help="show a single image")
    pi.add_argument("path", nargs="?")
    pi.add_argument("--white", action="store_true", help="white test pattern")
    pi.add_argument("--bright", type=lambda x: int(x, 0), default=0xFF)
    pi.add_argument("--hold", type=float, default=0.0, help="keep the channel open N seconds")

    sub.add_parser("off", help="clear the panel (all black)")

    pa = sub.add_parser("anim", help="play a folder of frames")
    pa.add_argument("dir")
    pa.add_argument("--fps", type=float, default=20.0)
    pa.add_argument("--bright", type=lambda x: int(x, 0), default=0xFF)
    pa.add_argument("--dur", type=float, default=0.0, help="seconds (0 = loop forever)")

    args = ap.parse_args()
    zv = ZenVision()
    try:
        if args.cmd == "image":
            if args.white:
                fb = encode(Image.new("L", (W, H), 255))
            elif args.path:
                fb = encode(Image.open(args.path))
            else:
                sys.exit("give an image path or --white")
            zv.show_image(fb, args.bright)
            if args.hold:
                time.sleep(args.hold)

        elif args.cmd == "off":
            zv.show_image(encode(Image.new("L", (W, H), 0)), 0x00)

        elif args.cmd == "anim":
            frames = _load_frames(args.dir)
            zv.stream_begin(args.bright)
            print("streaming %d frames @ %.0f fps (Ctrl-C to stop)" % (len(frames), args.fps))
            delay = 1.0 / args.fps
            end = (time.time() + args.dur) if args.dur > 0 else None
            try:
                while end is None or time.time() < end:
                    for fb in frames:
                        zv.stream_frame(fb)
                        time.sleep(delay)
            except KeyboardInterrupt:
                pass
    finally:
        zv.close()


if __name__ == "__main__":
    main()
