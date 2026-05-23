from __future__ import annotations

import argparse
import os
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Windows .ico from the ShelfyGAI SVG.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication(["shelfygai-icon-build"])

    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f"Could not read SVG icon: {source}")

    png_entries = [_render_png(renderer, size) for size in ICON_SIZES]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_build_ico(png_entries))

    if QGuiApplication.instance() is app:
        app.quit()
    return 0


def _render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(byte_array)


def _build_ico(png_entries: list[bytes]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(png_entries))
    directory = bytearray()
    payload = bytearray()
    offset = 6 + (16 * len(png_entries))

    for size, png_data in zip(ICON_SIZES, png_entries, strict=True):
        encoded_size = 0 if size >= 256 else size
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                encoded_size,
                encoded_size,
                0,
                0,
                1,
                32,
                len(png_data),
                offset,
            )
        )
        payload.extend(png_data)
        offset += len(png_data)

    return header + bytes(directory) + bytes(payload)


if __name__ == "__main__":
    raise SystemExit(main())
