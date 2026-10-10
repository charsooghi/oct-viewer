"""ETDRS ring geometry in the localizer's degree coordinate system.

Eyepy reads B-scan start/end positions as degrees and places the origin at
the center of the localizer image. It does not read a fovea landmark, and it
does not read a millimeter scale for the localizer (the field size is eyepy's
hardcoded 30°). ``MM_PER_DEG`` is the Spectralis standard-eye estimate
(288 µm per degree). The overlay is labeled estimated until that scale can be
read from the file. The follow-up plan is in the README under "ETDRS rings".
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Spectralis standard eye (axial length 24.385 mm) when the file has no
# patient-specific axial length.
MM_PER_DEG = 0.288

# (label, diameter in mm, stroke color). Inner ring first.
RINGS: tuple[tuple[str, float, str], ...] = (
    ("1 mm", 1.0, "#FFE14A"),
    ("3 mm", 3.0, "#FF8C1A"),
    ("6 mm", 6.0, "#2EC4D6"),
)

USER_NOTE = (
    "Estimated. The rings are the standard 1, 3 and 6 mm ETDRS diameters, "
    "centered on the localizer center. The file has no fovea landmark, so that "
    "center is the assumed fovea. Lateral millimeters use 288 µm per degree "
    "(Spectralis standard eye). That factor is not read from the .e2e file."
)


@dataclass(frozen=True)
class Ring:
    name: str
    color_hex: str
    cx: float
    cy: float
    rx: float
    ry: float


@dataclass(frozen=True)
class Crossing:
    x_px: float
    name: str
    color_hex: str


def legend_entries() -> tuple[tuple[str, str], ...]:
    return tuple((name, color) for name, _diameter, color in RINGS)


def radius_deg(diameter_mm: float) -> float:
    return (diameter_mm / 2.0) / MM_PER_DEG


def lateral_mm_per_px(deg_per_px: float) -> float:
    return deg_per_px * MM_PER_DEG


def fundus_rings(width: int, height: int, scale_xy: tuple[float, float]) -> tuple[Ring, ...]:
    """Concentric ETDRS rings centered on the localizer origin (image center)."""
    sx, sy = scale_xy
    if width <= 0 or height <= 0 or sx <= 0 or sy <= 0:
        return ()
    if not math.isfinite(sx) or not math.isfinite(sy):
        return ()
    cx = width / 2.0
    cy = height / 2.0
    rings: list[Ring] = []
    for name, diameter_mm, color in RINGS:
        radius = radius_deg(diameter_mm)
        rings.append(
            Ring(
                name=name,
                color_hex=color,
                cx=cx,
                cy=cy,
                rx=radius / sx,
                ry=radius / sy,
            )
        )
    return tuple(rings)


def _circle_ts(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    radius: float,
) -> list[float]:
    """Fractions along the segment where it meets a circle at the origin."""
    ax, ay = start_xy
    bx, by = end_xy
    dx = bx - ax
    dy = by - ay
    a = dx * dx + dy * dy
    if a < 1e-12:
        return []
    b = 2.0 * (ax * dx + ay * dy)
    c = ax * ax + ay * ay - radius * radius
    disc = b * b - 4.0 * a * c
    if disc < 0:
        return []
    root = math.sqrt(disc)
    ts: list[float] = []
    for sign in (-1.0, 1.0):
        t = (-b + sign * root) / (2.0 * a)
        if -1e-6 <= t <= 1.0 + 1e-6:
            ts.append(min(1.0, max(0.0, t)))
    ts.sort()
    unique: list[float] = []
    for t in ts:
        if not unique or abs(t - unique[-1]) > 1e-4:
            unique.append(t)
    return unique


def bscan_crossings(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    width_px: int,
) -> tuple[Crossing, ...]:
    """A-scan columns where this B-scan crosses each ETDRS ring.

    ``start_xy`` / ``end_xy`` are in degrees, the same coordinates as the
    fundus scan line. Column 0 is ``start_xy`` and the last column is
    ``end_xy``.
    """
    if width_px < 2:
        return ()
    crossings: list[Crossing] = []
    for name, diameter_mm, color in RINGS:
        for t in _circle_ts(start_xy, end_xy, radius_deg(diameter_mm)):
            crossings.append(
                Crossing(x_px=t * (width_px - 1), name=name, color_hex=color)
            )
    crossings.sort(key=lambda c: c.x_px)
    return tuple(crossings)


def scale_bar_for(mm_per_px: float, image_width_px: int) -> tuple[float, str] | None:
    """A horizontal bar length in image pixels and a label such as ``1 mm``."""
    if image_width_px <= 0 or not math.isfinite(mm_per_px) or mm_per_px <= 0:
        return None
    candidates_um = (100, 200, 250, 500, 1000, 2000)
    max_px = image_width_px * 0.28
    min_px = 36.0
    best: tuple[float, str] | None = None
    for um in candidates_um:
        length_px = (um / 1000.0) / mm_per_px
        if min_px <= length_px <= max_px:
            best = (length_px, _um_label(um))
    if best is not None:
        return best
    um = 500
    return ((um / 1000.0) / mm_per_px, _um_label(um))


def _um_label(um: int) -> str:
    if um % 1000 == 0:
        return f"{um // 1000} mm"
    return f"{um} µm"
