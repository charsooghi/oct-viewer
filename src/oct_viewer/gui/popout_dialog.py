from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QDialog, QVBoxLayout

from .image_view import ImageView


class PopoutDialog(QDialog):
    """A bigger, standalone view of a single fundus/B-scan image for detail inspection."""

    def __init__(self, title: str, image: np.ndarray, pixel_scale_xy: tuple[float, float], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 900)

        view = ImageView()
        view.set_image(image, pixel_scale_xy=pixel_scale_xy)

        layout = QVBoxLayout(self)
        layout.addWidget(view)
