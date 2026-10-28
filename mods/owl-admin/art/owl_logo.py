"""Draws the Owl Admin logo (front-facing owl head, the menu's red/cream palette) as a
256x256 RGBA PNG with 4x4 supersampling. Stdlib only.  usage: python owl_logo.py out.png"""
import struct
import sys
import zlib

N, SS = 256, 4


def hexc(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


RED, DARK, CREAM, DEEP = hexc("#e5242b"), hexc("#140909"), hexc("#f2e6e2"), hexc("#8a2a2e")


def circ(cx, cy, r):
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def poly(*pts):
    def inside(x, y):
        c = False
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c
    return inside


def mirror(*pts):
    return poly(*[(N - x, y) for x, y in pts])


# painter's order: later layers draw over earlier ones
L_TUFT = ((40, 30), (64, 118), (112, 76))
BROW = ((66, 92), (128, 122), (190, 92), (190, 104), (128, 136), (66, 104))
BLACK = hexc("#050303")


def grow(pts, k=1.14):
    """The tuft scaled about its centroid: a red rim so the black owl reads on the dark header."""
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return tuple((cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts)


layers = [
    (RED, [circ(128, 144, 96), poly(*grow(L_TUFT)), mirror(*grow(L_TUFT))]),   # rim
    (BLACK, [circ(128, 144, 90), poly(*L_TUFT), mirror(*L_TUFT)]),
    (RED, [circ(90, 136, 38), circ(166, 136, 38)]),             # eye rings
    (CREAM, [circ(90, 136, 31), circ(166, 136, 31)]),           # eyes
    (BLACK, [circ(94, 140, 15), circ(162, 140, 15)]),           # pupils
    (CREAM, [circ(99, 134, 5), circ(167, 134, 5)]),             # glints
    (RED, [poly(*BROW)]),                                        # stern brow
    (CREAM, [poly((114, 162), (142, 162), (128, 194))]),         # beak
]
for i, x0 in enumerate((96, 128, 160)):                          # chest chevrons
    y0 = 206 + (8 if i != 1 else 14)
    layers.append((RED, [poly((x0 - 12, y0 - 8), (x0, y0), (x0 + 12, y0 - 8), (x0 + 12, y0 - 2),
                               (x0, y0 + 6), (x0 - 12, y0 - 2))]))

rows = []
for py in range(N):
    row = bytearray([0])
    for px in range(N):
        acc, a = [0, 0, 0], 0
        for sy in range(SS):
            for sx in range(SS):
                x, y = px + (sx + .5) / SS, py + (sy + .5) / SS
                col = None
                for c, shapes in layers:
                    if any(f(x, y) for f in shapes):
                        col = c
                if col:
                    a += 1
                    for k in range(3):
                        acc[k] += col[k]
        if a:
            row += bytes([acc[0] // a, acc[1] // a, acc[2] // a, 255 * a // (SS * SS)])
        else:
            row += b"\0\0\0\0"
    rows.append(bytes(row))


def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)


png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 6, 0, 0, 0)) + \
    chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
open(sys.argv[1], "wb").write(png)
print("wrote", sys.argv[1], len(png), "bytes")
