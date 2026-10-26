from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from keymaster_app.ui.theme import BORDER, MUTED

CHECKER_LIGHT = QColor("#5a5f68")
CHECKER_DARK = QColor("#3a3e45")
CELL = 10


def load_image(path: str | None) -> QImage | None:
    if not path:
        return None
    reader = QImageReader(path)
    if not reader.canRead():
        return None
    image = reader.read()
    if image.isNull():
        return None
    return image.convertToFormat(QImage.Format_ARGB32)


class PreviewView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.image: QImage | None = None
        self.message = ""
        self.setMinimumSize(QSize(240, 150))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, image: QImage | None) -> None:
        self.image = image
        self.update()

    def set_message(self, message: str) -> None:
        self.message = message
        self.update()

    def has_image(self) -> bool:
        return self.image is not None and not self.image.isNull()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QColor(BORDER))
        painter.drawRoundedRect(area, 8, 8)
        if not self.has_image():
            painter.setPen(QColor(MUTED))
            painter.drawText(area.adjusted(12, 12, -12, -12), Qt.AlignCenter | Qt.TextWordWrap, self.message)
            return
        size = self.image.size().scaled(area.size().toSize() - QSize(16, 16), Qt.KeepAspectRatio)
        target = QRectF(0, 0, size.width(), size.height())
        target.moveCenter(area.center())
        painter.save()
        painter.setClipRect(target)
        painter.setPen(Qt.NoPen)
        y = int(target.top())
        row = 0
        while y < target.bottom():
            x = int(target.left())
            col = row
            while x < target.right():
                painter.fillRect(x, y, CELL, CELL, CHECKER_LIGHT if col % 2 == 0 else CHECKER_DARK)
                x += CELL
                col += 1
            y += CELL
            row += 1
        painter.drawImage(target, self.image)
        painter.restore()
