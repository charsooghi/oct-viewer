from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QLineF, QRectF, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap, QColor, QFont, QTransform
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem


def _to_qimage(gray: np.ndarray) -> QImage:
    gray = np.ascontiguousarray(gray)
    h, w = gray.shape
    img = QImage(gray.data, w, h, w, QImage.Format.Format_Grayscale8)
    return img.copy()  # detach from the numpy buffer's lifetime


class ImageView(QGraphicsView):
    """Zoomable, pannable grayscale image viewer.

    Supports an optional non-uniform pixel scale (so B-scans can be displayed
    at their true physical mm aspect ratio instead of 1:1 pixel aspect), an
    overlay line/rect/text (used by the fundus pane to show the current
    B-scan's position and the full scan footprint), and a wheel mode that can
    either zoom or step through frames.
    """

    doubleClicked = Signal()
    wheelStep = Signal(int)  # emitted instead of zooming when wheel_mode == "navigate"

    def __init__(self, parent=None, wheel_mode: str = "zoom"):
        super().__init__(parent)
        self.wheel_mode = wheel_mode  # "zoom" or "navigate"
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._overlay_line: QLineF | None = None
        self._overlay_rect: QRectF | None = None
        self._overlay_text: str | None = None
        self._pixel_scale_xy = (1.0, 1.0)

        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor(20, 20, 20))

    def set_image(self, gray_u8: np.ndarray, contrast: float = 1.0, brightness: float = 0.0, pixel_scale_xy: tuple[float, float] = (1.0, 1.0)):
        adjusted = gray_u8.astype(np.float32) * contrast + brightness * 255
        np.clip(adjusted, 0, 255, out=adjusted)
        qimg = _to_qimage(adjusted.astype(np.uint8))
        pixmap = QPixmap.fromImage(qimg)
        self._pixmap_item.setPixmap(pixmap)

        # Normalize so at least one axis stays at native pixel scale (never
        # shrink), and the other is stretched to reflect true physical mm
        # proportions - this is what makes B-scans match HEYEX's stretched look.
        sx, sy = pixel_scale_xy
        m = min(sx, sy) or 1.0
        self._pixel_scale_xy = (sx / m, sy / m)
        self._pixmap_item.setTransform(QTransform.fromScale(*self._pixel_scale_xy))

        self._scene.setSceneRect(self._pixmap_item.sceneBoundingRect())
        self.fit_to_view()
        # Guard against the viewport not yet having its final layout size
        # (e.g. right after construction, before the splitter settles).
        QTimer.singleShot(0, self.fit_to_view)

    def set_overlay_line(self, line: QLineF | None):
        self._overlay_line = line
        self.viewport().update()

    def set_overlay_rect(self, rect: QRectF | None):
        self._overlay_rect = rect
        self.viewport().update()

    def set_overlay_text(self, text: str | None):
        self._overlay_text = text
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect):
        if self._overlay_rect is not None:
            pen = QPen(QColor(255, 200, 0))
            pen.setWidth(0)
            painter.setPen(pen)
            painter.drawRect(self._overlay_rect)
        if self._overlay_line is not None:
            pen = QPen(QColor(0, 220, 0))
            pen.setWidth(0)  # cosmetic: constant 1px regardless of zoom
            painter.setPen(pen)
            painter.drawLine(self._overlay_line)
        if self._overlay_text:
            painter.save()
            painter.resetTransform()
            painter.setPen(QColor(255, 255, 0))
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(8, 18, self._overlay_text)
            painter.restore()

    def fit_to_view(self):
        if not self._pixmap_item.pixmap().isNull():
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_to_view()

    def wheelEvent(self, event):
        if self.wheel_mode == "navigate" and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            steps = 1 if event.angleDelta().y() > 0 else -1
            self.wheelStep.emit(steps)
            return
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)
