from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Patient:
    patient_id: str
    first_name: str
    surname: str
    dob: str | None
    sex: str | None


@dataclass
class BScanPosition:
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    center_xy: tuple[float, float]
    quality: float | None = None
    acquisition_time: str | None = None


@dataclass
class Series:
    volume_id: str
    laterality: str
    acquisition_date: str | None
    num_bscans: int
    lateral_scale: float  # degrees/px across a single B-scan's width
    axial_scale: float  # mm/px down a B-scan's depth
    bscans: np.ndarray | None  # (N, H, W) uint8, or None for enface-only series
    fundus: np.ndarray | None  # (H, W) uint8, None if not present in file
    modality: str = "OCT"
    scan_pattern: str = ""
    fundus_scale: tuple[float, float] | None = None  # (degrees/px x, degrees/px y)
    contours: dict[str, np.ndarray] = field(default_factory=dict)  # name -> (N, W)
    bscan_positions: list[BScanPosition] | None = None

    @property
    def is_volume(self) -> bool:
        return self.bscans is not None and self.num_bscans > 0

    @property
    def visit_date(self) -> str:
        return self.acquisition_date[:10] if self.acquisition_date else "Unknown date"

    @property
    def label(self) -> str:
        time = ""
        if self.acquisition_date and "T" in self.acquisition_date:
            time = self.acquisition_date.split("T", 1)[1].split(".", 1)[0]
            if time == "00:00:00":
                time = ""
        prefix = f"{time}  ·  " if time else ""
        kind = self.scan_pattern or self.modality
        if self.is_volume:
            h, w = self.bscans.shape[1:3]
            return f"{prefix}{self.laterality}  ·  {kind}  ·  {self.num_bscans} B-scans  ·  {w}x{h}"
        if self.fundus is not None:
            h, w = self.fundus.shape[:2]
            return f"{prefix}{self.laterality}  ·  {self.modality}  ·  {w}x{h}"
        return f"{prefix}{self.laterality}  ·  {kind}"


@dataclass
class Study:
    source_path: str
    patient: Patient
    series: list[Series]
