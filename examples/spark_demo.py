#!/usr/bin/env python3
"""Generate a generic demo animation (a rotating, breathing starburst) sized for
the ZenVision panel. Writes PNG frames you can feed to `zenvision.py anim`.

This is just an original placeholder graphic so the repo has a runnable demo —
point `anim` at any folder of 256x64 frames to show your own content.

    python examples/spark_demo.py --out frames --w 256 --h 64
    sudo ./zenvision.py anim frames/ --fps 20
"""
import argparse
import math
import os

from PIL import Image, ImageDraw

RAY_LEN = [1.00, 0.82, 0.94, 0.78, 1.00, 0.86, 0.96, 0.80, 0.98, 0.84, 0.92]


def draw(size, rot, pulse, n_rays=11, ss=4):
    w, h = size
    W, H = w * ss, h * ss
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    base = min(W, H) * 0.47
    inner = base * 0.06
    for i in range(n_rays):
        a = rot + 2 * math.pi * i / n_rays
        outer = base * RAY_LEN[i % len(RAY_LEN)] * (0.88 + 0.12 * pulse)
        half = (math.pi / n_rays) * (0.30 + 0.06 * pulse)
        sr = base * 0.16
        tip = (cx + outer * math.cos(a), cy + outer * math.sin(a))
        sh1 = (cx + sr * math.cos(a - half), cy + sr * math.sin(a - half))
        sh2 = (cx + sr * math.cos(a + half), cy + sr * math.sin(a + half))
        cen = (cx + inner * math.cos(a), cy + inner * math.sin(a))
        d.polygon([cen, sh1, tip, sh2], fill=255)
    d.ellipse([cx - inner * 1.6, cy - inner * 1.6, cx + inner * 1.6, cy + inner * 1.6], fill=255)
    return img.resize((w, h), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frames")
    ap.add_argument("--w", type=int, default=256)
    ap.add_argument("--h", type=int, default=64)
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--spin", type=float, default=1.0, help="full turns over the loop")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for f in range(args.frames):
        t = f / args.frames
        rot = 2 * math.pi * args.spin * t
        pulse = 0.5 - 0.5 * math.cos(2 * math.pi * t)
        frame = Image.new("L", (args.w, args.h), 0)
        spark = draw((args.h, args.h), rot, pulse)  # square, panel-height
        frame.paste(spark, ((args.w - args.h) // 2, 0))
        frame.save(os.path.join(args.out, "frame_%03d.png" % f))
    print("wrote %d frames to %s/" % (args.frames, args.out))


if __name__ == "__main__":
    main()
