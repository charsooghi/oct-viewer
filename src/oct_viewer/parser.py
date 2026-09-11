"""Loads Heidelberg HEYEX .e2e files into the internal Study/Series model.

The E2E format is undocumented and reverse-engineered, so this combines two
MIT-licensed libraries that each cover it differently:

- ``oct-converter`` for patient demographics: we walk its chunk directory
  ourselves (see ``_read_patient_chunk``) rather than calling
  ``read_all_metadata``, which decodes unrelated chunks as strict ASCII/UTF-8
  and raises on files containing non-ASCII text. Its date helpers are still
  used, since its birthdate parsing is more complete than eyepy's.
- ``eyepy``'s low-level ``HeE2eReader`` for everything per-series: B-scan pixel
  data, the localizer/IR image *with its physical scale (mm/px)*, per-B-scan
  scan positions, and laterality. This is what makes the fundus scan-line
  overlay and the physically-correct B-scan aspect ratio possible - oct-converter
  doesn't expose localizer calibration.

Parsing is best-effort throughout: anything that fails to extract for a given
series is dropped with a warning rather than aborting the whole load.
"""
from __future__ import annotations

import logging
import struct

import numpy as np

import oct_viewer._stubs  # noqa: F401 - stub cv2 before oct-converter image_types load
from eyepy.io.he.e2e_reader import E2ESliceStructure, HeE2eReader
from oct_converter.readers.binary_structs import e2e_binary
from oct_converter.readers.e2e import E2E

from .models import BScanPosition, Patient, Series, Study

log = logging.getLogger(__name__)

_PATIENT_CHUNK_TYPE = 9
# first_name[31] surname[51] title[15] birthdate:u32 sex[1] patient_id[25]
_PATIENT_CHUNK_LAYOUT = struct.Struct("<31s51s15sI1s25s")


def _allow_unsegmented_slices() -> None:
    """Let eyepy load B-scans that carry no layer segmentation.

    ``E2ESliceStructure.get_layers`` raises ``KeyError`` instead of returning an
    empty result when a slice has no layer annotation, which aborts the whole
    series. The viewer never draws layers, so treating them as absent is safe.
    """
    original = E2ESliceStructure.get_layers

    def get_layers(self):
        try:
            return original(self)
        except KeyError:
            return {}

    E2ESliceStructure.get_layers = get_layers


_allow_unsegmented_slices()


def _to_uint8(volume: np.ndarray) -> np.ndarray:
    arr = np.asarray(volume)
    if arr.dtype == np.uint8:
        return arr
    arr = np.nan_to_num(arr.astype(np.float64), nan=0.0)
    lo, hi = arr.min(), arr.max()
    if hi > lo:
        arr = (arr - lo) / (hi - lo)
    np.clip(arr, 0.0, 1.0, out=arr)
    return (arr * 255).astype(np.uint8)


def _decode_e2e_text(raw: bytes) -> str:
    """Decode a fixed-width, NUL-padded E2E string field.

    HEYEX writes these in the acquisition machine's Windows code page, not
    ASCII/UTF-8, so accented names must not abort the load.
    """
    return raw.split(b"\x00", 1)[0].decode("cp1252", errors="replace").strip()


def _read_patient_chunk(e2e: E2E) -> dict:
    """Return the first patient-demographics chunk, or ``{}`` if there is none."""
    with open(e2e.filepath, "rb") as f:
        for position in e2e.directory_stack:
            f.seek(position + e2e.byte_skip)
            directory = e2e_binary.main_directory_structure.parse(f.read(52))

            starts = []
            for _ in range(directory.num_entries):
                entry = e2e_binary.sub_directory_structure.parse(f.read(44))
                if entry.start > entry.pos:
                    starts.append(entry.start)

            for start in starts:
                f.seek(start + e2e.byte_skip)
                try:
                    chunk = e2e_binary.chunk_structure.parse(f.read(60))
                except Exception:
                    continue  # anonymised/truncated chunk headers turn up in the wild
                if chunk.type != _PATIENT_CHUNK_TYPE:
                    continue

                raw = f.read(_PATIENT_CHUNK_LAYOUT.size)
                if len(raw) < _PATIENT_CHUNK_LAYOUT.size:
                    continue
                first_name, surname, _title, birthdate, sex, patient_id = (
                    _PATIENT_CHUNK_LAYOUT.unpack(raw)
                )
                return {
                    "first_name": _decode_e2e_text(first_name),
                    "surname": _decode_e2e_text(surname),
                    "birthdate": birthdate,
                    "sex": _decode_e2e_text(sex),
                    "patient_id": _decode_e2e_text(patient_id),
                }
    return {}


def _load_patient(e2e: E2E) -> Patient:
    try:
        p = _read_patient_chunk(e2e)
    except Exception:
        log.warning("Could not read patient demographics.", exc_info=True)
        p = {}

    dob = None
    raw_dob = p.get("birthdate")
    if raw_dob:
        try:
            if len(str(raw_dob)) == 8:
                # Some files store DOB directly as YYYYMMDD.
                dob = str(raw_dob)
            else:
                julian = (raw_dob / 64) - 14558805
                dob = str(e2e.julian_to_ymd(julian))
        except Exception:
            log.warning("Could not parse patient birthdate.", exc_info=True)

    return Patient(
        patient_id=p.get("patient_id") or "unknown",
        first_name=p.get("first_name") or "",
        surname=p.get("surname") or "",
        dob=dob,
        sex=p.get("sex") or None,
    )


def _laterality_str(raw) -> str:
    if isinstance(raw, str) and raw.isdigit():
        raw = int(raw)
    if isinstance(raw, int):
        return chr(raw) if raw else "?"
    return str(raw) if raw else "?"


def _build_series(series_struct) -> Series | None:
    ev = series_struct.get_volume()
    bscans = _to_uint8(ev.data)

    localizer = ev.localizer
    fundus = None
    fundus_scale = None
    if localizer is not None:
        try:
            fundus = _to_uint8(localizer.data)
            fundus_scale = (float(localizer.scale_x), float(localizer.scale_y))
        except Exception:
            log.warning("Series %s: could not decode localizer image.", series_struct.id, exc_info=True)

    bscan_meta = []
    try:
        bscan_meta = series_struct.get_bscan_meta()
    except Exception:
        log.warning("Series %s: could not read per-B-scan positions.", series_struct.id, exc_info=True)

    positions = None
    axial_scale = 0.0
    lateral_scale = 0.0
    if bscan_meta and len(bscan_meta) == bscans.shape[0]:
        positions = [
            BScanPosition(
                start_xy=tuple(b["start_pos"]),
                end_xy=tuple(b["end_pos"]),
                center_xy=(b.get("center_x", 0.0), b.get("center_y", 0.0)),
                quality=b.get("quality"),
                acquisition_time=str(b["acquisitionTime"]) if b.get("acquisitionTime") else None,
            )
            for b in bscan_meta
        ]
        axial_scale = float(bscan_meta[0].get("scale_y", 0.0))
        width_px = bscans.shape[2]
        first = bscan_meta[0]
        lateral_span = abs(first["end_pos"][0] - first["start_pos"][0])
        if width_px and lateral_span:
            lateral_scale = lateral_span / width_px

    acquisition_date = positions[0].acquisition_time if positions else None
    laterality = _laterality_str(series_struct.laterality() if callable(series_struct.laterality) else series_struct.laterality)

    return Series(
        volume_id=str(series_struct.id),
        laterality=laterality,
        acquisition_date=acquisition_date,
        num_bscans=bscans.shape[0],
        lateral_scale=lateral_scale,
        axial_scale=axial_scale,
        bscans=bscans,
        fundus=fundus,
        fundus_scale=fundus_scale,
        bscan_positions=positions,
    )


def load_e2e(path: str) -> Study:
    e2e = E2E(path)
    patient = _load_patient(e2e)

    series_list: list[Series] = []
    reader = HeE2eReader(path)
    with reader as opened:
        for series_struct in opened.series:
            n = series_struct.n_bscans
            if not isinstance(n, int) or n <= 1:
                continue  # not a real OCT volume (e.g. a lone fundus photo entry)
            try:
                series = _build_series(series_struct)
            except Exception:
                log.warning("Skipping series %s: failed to decode.", series_struct.id, exc_info=True)
                continue
            if series is not None:
                series_list.append(series)

    if not series_list:
        raise ValueError("No OCT B-scan series could be decoded from this .e2e file.")

    return Study(source_path=path, patient=patient, series=series_list)
