from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, Signal, QLineF, QRectF, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QSlider,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QFormLayout,
    QGroupBox,
)

from .._version import __version__
from ..models import Study, Series
from ..parser import load_e2e
from .image_view import ImageView
from .popout_dialog import PopoutDialog
from .info_dialog import InfoDialog
from .update_check import UpdateCheckWorker

log = logging.getLogger(__name__)

SERIES_ROLE = Qt.ItemDataRole.UserRole

# True physical (mm) B-scan aspect can be extreme (axial resolution is often
# 5-10x finer than lateral) - HEYEX itself displays B-scans at their native
# pixel aspect ratio rather than true physical proportions, so we do the same.
def _bscan_pixel_scale(series: Series) -> tuple[float, float]:
    return (1.0, 1.0)


class LoadWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            study = load_e2e(self._path)
        except Exception as exc:  # noqa: BLE001 - surface any parse failure to the user
            log.exception("Failed to load %s", self._path)
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(study)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OCT Viewer v{__version__}")
        self.resize(1400, 900)

        self._study: Study | None = None
        self._current_series: Series | None = None
        self._current_index = 0
        self._contrast = 1.0
        self._brightness = 0.0
        self._worker: LoadWorker | None = None
        self._progress: QProgressDialog | None = None
        self._popouts: list[PopoutDialog] = []  # keep references alive

        self._build_ui()
        self._build_menu()
        self._start_update_check()

    def _start_update_check(self):
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _on_update_available(self, latest_tag: str, release_url: str):
        box = QMessageBox(self)
        box.setWindowTitle("Update Available")
        box.setText(f"A new version ({latest_tag}) is available.\nYou're running v{__version__}.")
        open_btn = box.addButton("Open Download Page", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl(release_url))

    # ---------------------------------------------------------------- UI

    def _build_menu(self):
        open_action = QAction("&Open .e2e File...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open)

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        self.info_action = QAction("&Image Info...", self)
        self.info_action.setShortcut("Ctrl+I")
        self.info_action.triggered.connect(self._show_info_dialog)
        self.info_action.setEnabled(False)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.info_action)

    def _build_ui(self):
        # Left: patient / series tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Patient / Series"])
        self.tree.setMinimumWidth(320)
        self.tree.itemSelectionChanged.connect(self._on_series_selected)

        # Center: fundus + bscan views
        self.fundus_view = ImageView(wheel_mode="zoom")
        self.bscan_view = ImageView(wheel_mode="navigate")
        self.bscan_view.wheelStep.connect(self._step)
        self.fundus_view.doubleClicked.connect(lambda: self._open_popout("fundus"))
        self.bscan_view.doubleClicked.connect(lambda: self._open_popout("bscan"))

        # Stacked (not side-by-side): B-scans are naturally wide, so each pane
        # gets the full window width rather than being squeezed into a column.
        image_splitter = QSplitter(Qt.Orientation.Vertical)
        image_splitter.addWidget(self._labeled(self.fundus_view, "Fundus / Localizer  (double-click to enlarge)"))
        image_splitter.addWidget(self._labeled(self.bscan_view, "B-scan  (scroll to step, double-click to enlarge)"))
        image_splitter.setStretchFactor(0, 1)
        image_splitter.setStretchFactor(1, 1)

        # Navigation bar under the images
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._on_index_changed)
        self.frame_spin = QSpinBox()
        self.frame_spin.valueChanged.connect(self._on_spin_changed)
        self.frame_count_label = QLabel("/ 0")
        prev_btn = QPushButton("< Prev")
        prev_btn.clicked.connect(lambda: self._step(-1))
        next_btn = QPushButton("Next >")
        next_btn.clicked.connect(lambda: self._step(1))

        nav_layout = QHBoxLayout()
        nav_layout.addWidget(prev_btn)
        nav_layout.addWidget(self.slider, stretch=1)
        nav_layout.addWidget(self.frame_spin)
        nav_layout.addWidget(self.frame_count_label)
        nav_layout.addWidget(next_btn)

        # Contrast / brightness
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(10, 300)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self._on_display_changed)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self._on_display_changed)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_display)

        display_layout = QHBoxLayout()
        display_layout.addWidget(QLabel("Contrast"))
        display_layout.addWidget(self.contrast_slider)
        display_layout.addWidget(QLabel("Brightness"))
        display_layout.addWidget(self.brightness_slider)
        display_layout.addWidget(reset_btn)

        center_layout = QVBoxLayout()
        center_layout.addWidget(image_splitter, stretch=1)
        center_layout.addLayout(nav_layout)
        center_layout.addLayout(display_layout)
        center_widget = QWidget()
        center_widget.setLayout(center_layout)

        # Right: metadata panel
        self.meta_panel = self._build_meta_panel()

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.tree)
        main_splitter.addWidget(center_widget)
        main_splitter.addWidget(self.meta_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)

        self.setCentralWidget(main_splitter)
        self.statusBar().showMessage("Open an .e2e file to begin (File > Open, or Ctrl+O).")

    def _labeled(self, widget: QWidget, title: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        layout.addWidget(widget)
        return container

    def _build_meta_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(260)
        layout = QVBoxLayout(panel)

        patient_box = QGroupBox("Patient")
        patient_form = QFormLayout(patient_box)
        self.lbl_name = QLabel("-")
        self.lbl_id = QLabel("-")
        self.lbl_dob = QLabel("-")
        self.lbl_sex = QLabel("-")
        patient_form.addRow("Name:", self.lbl_name)
        patient_form.addRow("Patient ID:", self.lbl_id)
        patient_form.addRow("DOB:", self.lbl_dob)
        patient_form.addRow("Sex:", self.lbl_sex)

        series_box = QGroupBox("Series")
        series_form = QFormLayout(series_box)
        self.lbl_laterality = QLabel("-")
        self.lbl_date = QLabel("-")
        self.lbl_dims = QLabel("-")
        self.lbl_spacing = QLabel("-")
        series_form.addRow("Laterality:", self.lbl_laterality)
        series_form.addRow("Acquired:", self.lbl_date)
        series_form.addRow("Dimensions:", self.lbl_dims)
        series_form.addRow("Scale (mm/px):", self.lbl_spacing)

        layout.addWidget(patient_box)
        layout.addWidget(series_box)
        layout.addStretch(1)

        disclaimer = QLabel(
            "For personal viewing/data-recovery only.\n"
            "Not a certified medical device; rendering may\n"
            "differ from the original HEYEX software."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(disclaimer)
        return panel

    # ------------------------------------------------------------ loading

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open HEYEX .e2e file", "", "HEYEX Export (*.e2e)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._progress = QProgressDialog("Loading .e2e file...", None, 0, 0, self)
        self._progress.setWindowTitle("OCT Viewer")
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setCancelButton(None)
        self._progress.show()

        self._worker = LoadWorker(path)
        self._worker.succeeded.connect(self._on_load_succeeded)
        self._worker.failed.connect(self._on_load_failed)
        self._worker.start()

    def _on_load_succeeded(self, study: Study):
        if self._progress:
            self._progress.close()
            self._progress = None
        self._study = study
        self._populate_tree(study)
        self.info_action.setEnabled(True)
        self.statusBar().showMessage(f"Loaded {study.source_path}")

    def _on_load_failed(self, message: str):
        if self._progress:
            self._progress.close()
            self._progress = None
        QMessageBox.critical(self, "Failed to load file", message)
        self.statusBar().showMessage("Load failed.")

    def _populate_tree(self, study: Study):
        self.tree.clear()
        p = study.patient
        name = f"{p.first_name} {p.surname}".strip() or "(unnamed patient)"
        patient_item = QTreeWidgetItem([f"{name}  (ID: {p.patient_id})"])
        self.tree.addTopLevelItem(patient_item)
        for series in study.series:
            item = QTreeWidgetItem([series.label])
            item.setData(0, SERIES_ROLE, series)
            patient_item.addChild(item)
        patient_item.setExpanded(True)
        if patient_item.childCount():
            self.tree.setCurrentItem(patient_item.child(0))

        self.lbl_name.setText(name)
        self.lbl_id.setText(p.patient_id)
        self.lbl_dob.setText(p.dob or "-")
        self.lbl_sex.setText(p.sex or "-")

    # ------------------------------------------------------------- series

    def _on_series_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        series = items[0].data(0, SERIES_ROLE)
        if series is None:
            return
        self._current_series = series
        self._current_index = 0

        self.slider.blockSignals(True)
        self.slider.setRange(0, series.num_bscans - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)

        self.frame_spin.blockSignals(True)
        self.frame_spin.setRange(0, series.num_bscans - 1)
        self.frame_spin.setValue(0)
        self.frame_spin.blockSignals(False)

        self.frame_count_label.setText(f"/ {series.num_bscans - 1}")

        self.lbl_laterality.setText(series.laterality)
        self.lbl_date.setText(series.acquisition_date or "-")
        h, w = series.bscans.shape[1:3]
        self.lbl_dims.setText(f"{series.num_bscans} x {h} x {w}")
        self.lbl_spacing.setText(f"lateral={series.lateral_scale:.4f}, axial={series.axial_scale:.4f}")

        if series.fundus is not None:
            scale = series.fundus_scale or (1.0, 1.0)
            self.fundus_view.set_image(series.fundus, pixel_scale_xy=scale)
        else:
            self.fundus_view._scene.clear()

        self._render_current_frame()

    def _on_index_changed(self, value: int):
        self._current_index = value
        self.frame_spin.blockSignals(True)
        self.frame_spin.setValue(value)
        self.frame_spin.blockSignals(False)
        self._render_current_frame()

    def _on_spin_changed(self, value: int):
        self.slider.setValue(value)  # triggers _on_index_changed

    def _step(self, delta: int):
        self.slider.setValue(self.slider.value() + delta)

    def _on_display_changed(self):
        self._contrast = self.contrast_slider.value() / 100.0
        self._brightness = self.brightness_slider.value() / 100.0
        self._render_current_frame()

    def _reset_display(self):
        self.contrast_slider.setValue(100)
        self.brightness_slider.setValue(0)

    def _render_current_frame(self):
        series = self._current_series
        if series is None:
            return
        frame = series.bscans[self._current_index]
        pixel_scale = _bscan_pixel_scale(series)
        self.bscan_view.set_image(frame, contrast=self._contrast, brightness=self._brightness, pixel_scale_xy=pixel_scale)
        frame_text = f"B-scan {self._current_index + 1} / {series.num_bscans}"
        self.bscan_view.set_overlay_text(frame_text)
        self._update_overlay(frame_text)

    def _update_overlay(self, frame_text: str):
        series = self._current_series
        if series is None or series.fundus is None or not series.bscan_positions or not series.fundus_scale:
            self.fundus_view.set_overlay_line(None)
            self.fundus_view.set_overlay_rect(None)
            self.fundus_view.set_overlay_text(None)
            return
        line = self._compute_overlay_line(series, self._current_index)
        rect = self._compute_scan_area_rect(series)
        self.fundus_view.set_overlay_line(line)
        self.fundus_view.set_overlay_rect(rect)
        self.fundus_view.set_overlay_text(frame_text)

    @staticmethod
    def _mm_to_px(x_mm: float, y_mm: float, series: Series) -> tuple[float, float]:
        sx, sy = series.fundus_scale
        h, w = series.fundus.shape[:2]
        px = w / 2 + x_mm / sx
        py = h / 2 - y_mm / sy
        return px, py

    @classmethod
    def _compute_overlay_line(cls, series: Series, index: int) -> QLineF | None:
        positions = series.bscan_positions
        if index >= len(positions):
            return None
        p = positions[index]
        x1, y1 = cls._mm_to_px(*p.start_xy, series)
        x2, y2 = cls._mm_to_px(*p.end_xy, series)
        return QLineF(x1, y1, x2, y2)

    @classmethod
    def _compute_scan_area_rect(cls, series: Series) -> QRectF | None:
        positions = series.bscan_positions
        if not positions:
            return None
        xs, ys = [], []
        for p in positions:
            xs.extend([p.start_xy[0], p.end_xy[0]])
            ys.extend([p.start_xy[1], p.end_xy[1]])
        corners = [
            cls._mm_to_px(min(xs), min(ys), series),
            cls._mm_to_px(max(xs), max(ys), series),
        ]
        (x1, y1), (x2, y2) = corners
        return QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def _open_popout(self, which: str):
        series = self._current_series
        if series is None:
            return
        if which == "fundus" and series.fundus is not None:
            dlg = PopoutDialog("Fundus / Localizer", series.fundus, series.fundus_scale or (1.0, 1.0), self)
        elif which == "bscan":
            frame = series.bscans[self._current_index]
            scale = _bscan_pixel_scale(series)
            dlg = PopoutDialog(f"B-scan {self._current_index + 1} / {series.num_bscans}", frame, scale, self)
        else:
            return
        self._popouts.append(dlg)
        dlg.finished.connect(lambda _=None, d=dlg: self._popouts.remove(d) if d in self._popouts else None)
        dlg.show()

    def _show_info_dialog(self):
        if self._study is None or self._current_series is None:
            return
        dlg = InfoDialog(self._study.patient, self._current_series, self._current_index, self)
        dlg.exec()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._step(-1)
        elif event.key() == Qt.Key.Key_Right:
            self._step(1)
        else:
            super().keyPressEvent(event)
