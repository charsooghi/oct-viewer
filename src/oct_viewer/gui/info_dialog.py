from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView

from ..models import Series, Patient


class InfoDialog(QDialog):
    """A HEYEX-style key/value metadata table for the current patient/series/B-scan."""

    def __init__(self, patient: Patient, series: Series, bscan_index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Information")
        self.resize(500, 600)

        rows: list[tuple[str, str]] = []
        rows.append(("Patient name", f"{patient.first_name} {patient.surname}".strip()))
        rows.append(("Patient ID", patient.patient_id))
        rows.append(("Date of birth", patient.dob or "-"))
        rows.append(("Sex", patient.sex or "-"))
        rows.append(("", ""))
        rows.append(("Volume/series ID", series.volume_id))
        rows.append(("Laterality", series.laterality))
        rows.append(("Acquired", series.acquisition_date or "-"))
        h, w = series.bscans.shape[1:3]
        rows.append(("B-scans", str(series.num_bscans)))
        rows.append(("B-scan size (px)", f"{w} x {h}"))
        rows.append(("Lateral scale (mm/px)", f"{series.lateral_scale:.5f}"))
        rows.append(("Axial scale (mm/px)", f"{series.axial_scale:.5f}"))
        if series.fundus is not None:
            fh, fw = series.fundus.shape[:2]
            rows.append(("Fundus/localizer size (px)", f"{fw} x {fh}"))
        if series.fundus_scale:
            rows.append(("Fundus scale (mm/px)", f"{series.fundus_scale[0]:.5f}"))

        if series.bscan_positions and 0 <= bscan_index < len(series.bscan_positions):
            pos = series.bscan_positions[bscan_index]
            rows.append(("", ""))
            rows.append((f"Current B-scan (#{bscan_index})", ""))
            rows.append(("  Start position (mm)", f"{pos.start_xy[0]:.3f}, {pos.start_xy[1]:.3f}"))
            rows.append(("  End position (mm)", f"{pos.end_xy[0]:.3f}, {pos.end_xy[1]:.3f}"))
            rows.append(("  Center (mm)", f"{pos.center_xy[0]:.3f}, {pos.center_xy[1]:.3f}"))
            if pos.quality is not None:
                rows.append(("  Quality", f"{pos.quality:.3f}"))
            if pos.acquisition_time:
                rows.append(("  Acquisition time", pos.acquisition_time))

        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels(["Field", "Value"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, (key, value) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(key))
            table.setItem(row, 1, QTableWidgetItem(value))

        layout = QVBoxLayout(self)
        layout.addWidget(table)
