import struct
import sys
import zlib
from pathlib import Path


def png(path: Path, width: int, height: int, pixel) -> None:
    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def main() -> None:
    out = Path(sys.argv[1])
    frames = int(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for f in range(1, frames + 1):
        def pixel(x, y, f=f):
            inside = 20 + f <= x < 40 + f and 10 <= y < 26
            return (180, 120, 90) if inside else (30, 200, 40)
        png(out / f"frame_{f:04d}.png", 64, 36, pixel)


if __name__ == "__main__":
    main()
