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
    lateral_scale: float  # mm/px across a single B-scan's width
    axial_scale: float  # mm/px down a B-scan's depth
    bscans: np.ndarray  # (N, H, W) uint8
    fundus: np.ndarray | None  # (H, W) uint8, None if not present in file
    fundus_scale: tuple[float, float] | None = None  # (mm/px x, mm/px y) of the fundus image
    contours: dict[str, np.ndarray] = field(default_factory=dict)  # name -> (N, W)
    bscan_positions: list[BScanPosition] | None = None

    @property
    def label(self) -> str:
        date = self.acquisition_date.split(".")[0] if self.acquisition_date else "unknown date"
        h, w = self.bscans.shape[1:3]
        return f"{date}  ·  {self.laterality}  ·  {self.num_bscans} B-scans  ·  {w}x{h}"


@dataclass
class Study:
    source_path: str
    patient: Patient
    series: list[Series]
