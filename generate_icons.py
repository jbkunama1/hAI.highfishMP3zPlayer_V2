#!/usr/bin/env python3
"""
MP3z Icon Generator
Einmalig ausführen: python3 generate_icons.py
Erzeugt icon-192.png und icon-512.png im gleichen Verzeichnis.
Benötigt: pip install pillow --break-system-packages
"""
from PIL import Image, ImageDraw
import math, os, sys

def make_icon(size):
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    d   = ImageDraw.Draw(img)
    pad = size * 0.04
    d.ellipse([pad, pad, size-pad, size-pad], fill=(10,10,15,255))
    ring_w = max(4, size // 20)
    for i in range(20):
        t = i / 19
        r = int(255 * (1 - t * 0.4))
        g = int(94  + t * (154 - 94))
        b = int(58  * (1 - t * 0.6))
        start = i * 18 - 90
        box = [pad+ring_w//2, pad+ring_w//2, size-pad-ring_w//2, size-pad-ring_w//2]
        d.arc(box, start, start+19, fill=(r,g,b,255), width=ring_w)
    cc = size * 0.28
    cx = cy = size / 2
    d.ellipse([cx-cc, cy-cc, cx+cc, cy+cc], fill=(255,94,58,255))
    ci = cc * 0.6
    d.ellipse([cx-ci, cy-ci, cx+ci, cy+ci], fill=(255,154,60,255))
    nh, nw = cc*0.38, cc*0.46
    nx, ny = cx - cc*0.05, cy + cc*0.32
    d.ellipse([nx-nw, ny-nh, nx+nw, ny+nh], fill=(10,10,15,255))
    sw = max(2, int(size*0.028))
    sh, sx = cc*0.9, nx+nw-sw//2
    d.rectangle([sx, ny-sh, sx+sw, ny], fill=(10,10,15,255))
    fw, fh = cc*0.38, cc*0.32
    d.arc([sx, ny-sh, sx+fw*2, ny-sh+fh*2], -90, 45,
          fill=(10,10,15,255), width=max(2, int(size*0.028)))
    return img

here = os.path.dirname(os.path.abspath(__file__))
for size in [192, 512]:
    p = os.path.join(here, f'icon-{size}.png')
    make_icon(size).save(p)
    print(f'✓ {p}')
print('Icons fertig!')
