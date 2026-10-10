from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QLineF, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap, QColor, QFont, QFontMetrics, QTransform
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem


def _to_qimage(gray: np.ndarray) -> QImage:
    gray = np.ascontiguousarray(gray)
    h, w = gray.shape
    img = QImage(gray.data, w, h, w, QImage.Format.Format_Grayscale8)
    return img.copy()  # detach from the numpy buffer's lifetime


def _cosmetic_pen(color: QColor, width: int) -> QPen:
    pen = QPen(color)
    pen.setWidth(width)
    pen.setCosmetic(True)
    return pen


class ImageView(QGraphicsView):
    """Zoomable, pannable grayscale image viewer.

    Supports an optional non-uniform pixel scale (so B-scans can be displayed
    at their true physical mm aspect ratio instead of 1:1 pixel aspect), an
    overlay line/rect/text (used by the fundus pane to show the current
    B-scan's position and the full scan footprint), optional circles and
    vertical lines (ETDRS rings and where the current B-scan crosses them),
    a scale bar, and a wheel mode that can either zoom or step through frames.

    Overlay coordinates are image pixels. They are mapped through the pixmap's
    display scale when painted, so they stay glued to the image.
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
        self._circles: list[tuple[float, float, float, float, QColor]] = []
        self._vlines: list[tuple[float, QColor]] = []
        self._marker: tuple[float, float] | None = None
        self._scale_bar: tuple[float, str] | None = None
        self._legend: list[tuple[QColor, str]] = []
        self._pixel_scale_xy = (1.0, 1.0)

        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor(20, 20, 20))

    def clear_image(self):
        """Remove the displayed image without destroying scene items."""
        self._pixmap_item.setPixmap(QPixmap())
        self._overlay_line = None
        self._overlay_rect = None
        self._overlay_text = None
        self._circles = []
        self._vlines = []
        self._marker = None
        self._scale_bar = None
        self._legend = []
        self._scene.setSceneRect(0, 0, 0, 0)
        self.viewport().update()

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

    def set_circles(self, circles: list[tuple[float, float, float, float, QColor]] | None):
        """Ellipses in image pixels: (cx, cy, rx, ry, color)."""
        self._circles = list(circles) if circles else []
        self.viewport().update()

    def set_vlines(self, vlines: list[tuple[float, QColor]] | None):
        """Full-height lines at image-x columns."""
        self._vlines = list(vlines) if vlines else []
        self.viewport().update()

    def set_marker(self, point: tuple[float, float] | None):
        self._marker = point
        self.viewport().update()

    def set_scale_bar(self, length_px: float | None, label: str | None = None):
        if length_px is None or not label:
            self._scale_bar = None
        else:
            self._scale_bar = (float(length_px), label)
        self.viewport().update()

    def set_legend(self, items: list[tuple[QColor, str]] | None):
        self._legend = list(items) if items else []
        self.viewport().update()

    def copy_overlays_to(self, other: ImageView):
        """Copy overlay geometry onto another view of the same image pixels."""
        other._overlay_line = None if self._overlay_line is None else QLineF(self._overlay_line)
        other._overlay_rect = None if self._overlay_rect is None else QRectF(self._overlay_rect)
        other._overlay_text = self._overlay_text
        other._circles = list(self._circles)
        other._vlines = list(self._vlines)
        other._marker = self._marker
        other._scale_bar = self._scale_bar
        other._legend = list(self._legend)
        other.viewport().update()

    def drawForeground(self, painter: QPainter, rect):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        sx, sy = self._pixel_scale_xy
        if self._overlay_rect is not None:
            painter.setPen(_cosmetic_pen(QColor(255, 200, 0), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = self._overlay_rect
            painter.drawRect(QRectF(r.x() * sx, r.y() * sy, r.width() * sx, r.height() * sy))
        if self._overlay_line is not None:
            painter.setPen(_cosmetic_pen(QColor(0, 220, 0), 1))
            line = self._overlay_line
            painter.drawLine(
                QLineF(line.x1() * sx, line.y1() * sy, line.x2() * sx, line.y2() * sy)
            )
        # Largest ring first so the inner strokes stay visible.
        for cx, cy, rx, ry, color in reversed(self._circles):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(_cosmetic_pen(QColor(0, 0, 0), 4))
            ellipse = QRectF((cx - rx) * sx, (cy - ry) * sy, 2 * rx * sx, 2 * ry * sy)
            painter.drawEllipse(ellipse)
            painter.setPen(_cosmetic_pen(color, 2))
            painter.drawEllipse(ellipse)
        pixmap = self._pixmap_item.pixmap()
        if not pixmap.isNull() and self._vlines:
            height = pixmap.height() * sy
            for x, color in self._vlines:
                x_s = x * sx
                painter.setPen(_cosmetic_pen(QColor(0, 0, 0), 4))
                painter.drawLine(QLineF(x_s, 0, x_s, height))
                painter.setPen(_cosmetic_pen(color, 2))
                painter.drawLine(QLineF(x_s, 0, x_s, height))
        if self._marker is not None:
            self._draw_marker(painter, sx, sy)
        if self._scale_bar is not None and not pixmap.isNull():
            self._draw_scale_bar(painter, sx, sy, pixmap.width(), pixmap.height())
        if self._legend:
            self._draw_legend(painter)
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

    def _draw_marker(self, painter: QPainter, sx: float, sy: float):
        mx, my = self._marker
        vp = painter.transform().map(QPointF(mx * sx, my * sy))
        painter.save()
        painter.resetTransform()
        arm = 7
        for color, width in ((QColor(0, 0, 0), 3), (QColor(255, 255, 255), 1)):
            painter.setPen(_cosmetic_pen(color, width))
            painter.drawLine(QPointF(vp.x() - arm, vp.y()), QPointF(vp.x() + arm, vp.y()))
            painter.drawLine(QPointF(vp.x(), vp.y() - arm), QPointF(vp.x(), vp.y() + arm))
        painter.restore()

    def _draw_scale_bar(self, painter: QPainter, sx: float, sy: float, width: int, height: int):
        length_px, label = self._scale_bar
        margin_x = 16 * sx
        margin_y = 22 * sy
        x2 = width * sx - margin_x
        x1 = x2 - length_px * sx
        y = height * sy - margin_y
        p1 = painter.transform().map(QPointF(x1, y))
        p2 = painter.transform().map(QPointF(x2, y))
        painter.save()
        painter.resetTransform()
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(label)
        cap = 5
        baseline = p1.y() - 8
        text_x = (p1.x() + p2.x() - text_w) / 2
        # A ring line can cross this corner. Cover it so the bar stays readable.
        left = min(p1.x(), p2.x(), text_x) - 8
        right = max(p1.x(), p2.x(), text_x + text_w) + 8
        top = baseline - fm.ascent() - 4
        bottom = max(p1.y(), p2.y()) + cap + 6
        painter.fillRect(QRectF(left, top, right - left, bottom - top), QColor(0, 0, 0, 210))
        for color, width_px in ((QColor(0, 0, 0), 4), (QColor(255, 255, 255), 2)):
            painter.setPen(_cosmetic_pen(color, width_px))
            painter.drawLine(p1, p2)
            painter.drawLine(QPointF(p1.x(), p1.y() - cap), QPointF(p1.x(), p1.y() + cap))
            painter.drawLine(QPointF(p2.x(), p2.y() - cap), QPointF(p2.x(), p2.y() + cap))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QPointF(text_x, baseline), label)
        painter.restore()

    def _draw_legend(self, painter: QPainter):
        painter.save()
        painter.resetTransform()
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)
        y = 18
        right = self.viewport().width() - 10
        for color, text in self._legend:
            painter.setPen(color)
            text_w = fm.horizontalAdvance(text)
            painter.drawText(QPointF(right - text_w, y), text)
            y += fm.height()
        painter.restore()

    def fit_to_view(self):
        try:
            if self._pixmap_item.pixmap().isNull():
                return
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        except RuntimeError:
            # A stale reference can survive if the scene was cleared elsewhere.
            self._pixmap_item = QGraphicsPixmapItem()
            self._scene.addItem(self._pixmap_item)

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
