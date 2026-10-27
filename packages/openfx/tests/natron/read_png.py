import struct
import sys
import zlib
from pathlib import Path


def decode(path: Path):
    data = path.read_bytes()
    pos = 8
    idat = b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    bpp = channels * depth // 8
    raw = zlib.decompress(idat)
    stride = width * bpp
    rows = []
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        kind = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return width, height, depth, channels, rows


def main() -> None:
    width, height, depth, channels, rows = decode(Path(sys.argv[1]))
    region_w = int(sys.argv[2]) if len(sys.argv) > 2 else width
    region_h = int(sys.argv[3]) if len(sys.argv) > 3 else height
    step = depth // 8
    scale = (1 << depth) - 1
    alphas = set()
    reds = set()
    for row in rows[height - region_h:]:
        for x in range(region_w):
            px = row[x * channels * step:(x + 1) * channels * step]
            values = [int.from_bytes(px[c * step:(c + 1) * step], "big") / scale for c in range(channels)]
            alphas.add(round(values[-1] if channels in (2, 4) else 1.0, 3))
            reds.add(round(values[0], 3))
    print(f"{width}x{height} region={region_w}x{region_h} channels={channels} depth={depth} alpha={sorted(alphas)} red={sorted(reds)}")


if __name__ == "__main__":
    main()
