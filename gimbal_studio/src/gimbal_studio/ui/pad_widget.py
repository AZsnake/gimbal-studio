from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class PadWidget(QWidget):
    """Circular two-axis control that reports normalized coordinates."""

    value_changed = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._x = 0.0
        self._y = 0.0
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_value(self, x: float, y: float) -> None:
        self._x, self._y = self._clamp_to_circle(x, y)
        self.update()

    def value(self) -> tuple[float, float]:
        return self._x, self._y

    @staticmethod
    def _clamp_to_circle(x: float, y: float) -> tuple[float, float]:
        x = max(-1.0, min(1.0, float(x)))
        y = max(-1.0, min(1.0, float(y)))
        length = math.hypot(x, y)
        if length > 1.0:
            x /= length
            y /= length
        return x, y

    def _set_from_position(self, position: QPointF) -> None:
        radius = max(1.0, min(self.width(), self.height()) / 2.0 - 18.0)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        x = (position.x() - center.x()) / radius
        y = (center.y() - position.y()) / radius
        self.set_value(x, y)
        self.value_changed.emit(self._x, self._y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_from_position(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._set_from_position(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = max(1.0, min(self.width(), self.height()) / 2.0 - 18.0)
        painter.setPen(QPen(QColor("#555555"), 1))
        painter.setBrush(QColor("#1e1e1e"))
        painter.drawEllipse(center, radius, radius)

        painter.setPen(QPen(QColor("#3a3a3a"), 1))
        painter.drawLine(
            QPointF(center.x() - radius, center.y()),
            QPointF(center.x() + radius, center.y()),
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - radius),
            QPointF(center.x(), center.y() + radius),
        )

        knob = QPointF(
            center.x() + self._x * radius,
            center.y() - self._y * radius,
        )
        painter.setPen(QPen(QColor("#f6c77f"), 2))
        painter.setBrush(QColor("#e8a54b"))
        painter.drawEllipse(knob, 11.0, 11.0)
