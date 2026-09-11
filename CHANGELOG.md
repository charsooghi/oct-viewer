# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.6] - 2026-09-11

### Fixed

- Some `.e2e` files failed to open with a "'utf-8' codec can't decode byte ...
  invalid start byte" error. Patient demographics were read through a
  library-wide metadata dump that also decoded unrelated device-info chunks as
  strict UTF-8, so a single accented character anywhere in the file aborted the
  load. The viewer now reads only the patient record it needs, and decodes
  names as Windows-1252, so accented names show correctly.
- Series without layer segmentation were silently dropped (often the dense
  volume scans), leaving only part of a file's sessions in the series list.

### Added

- Standalone enface images in `.e2e` files (e.g. BAF and extra IR/SLO
  captures) now appear in the left tree alongside OCT volumes.
- The left tree groups acquisitions by visit date, with each session listed
  under its day in chronological order.
- Selecting an enface-only item shows that image in the main viewer and
  disables B-scan navigation controls.

## [0.1.5] - 2026-07-16

### Fixed

- macOS app crashed on launch on older macOS versions: OpenCV (cv2) was bundled
  via oct-converter but is not needed for .e2e viewing; it required macOS 14+
  and missing dylibs (e.g. OpenEXR). cv2 is now stubbed at runtime and excluded
  from the frozen app. Also stopped collecting the entire oct-converter package
  (and pydicom / imageio_ffmpeg) to shrink the universal build and avoid
  arch-specific sidecar binaries that broke the universal merge.

## [0.1.4] - 2026-07-16

### Fixed

- macOS builds are now universal binaries (Apple Silicon + Intel) instead of
  arm64-only, which caused "this application is not supported on this Mac" on
  Intel Macs.

## [0.1.3] - 2026-07-15

### Fixed

- The app's built-in version number wasn't being updated when a new release
  was tagged, so the in-app "update available" notice could fire even when
  you were already running the latest version. The version is now stamped
  in automatically from the release tag at build time, instead of being
  tracked by hand.

## [0.1.2] - 2026-07-15

### Fixed

- Scan-position overlay on the fundus image was vertically inverted: the
  line shown for the current B-scan didn't match its actual location
  (caught by comparing blood vessel landmarks visible in both images)

## [0.1.1] - 2026-07-15

### Added

- Open and browse HEYEX `.e2e` files: patient info, every series/session in
  the file, the fundus/localizer image, and the B-scan stack
- B-scan navigation via slider, spinbox, arrow keys, or mouse wheel
- Zoom (mouse wheel) and pan (drag) on both the fundus and B-scan images
- Double-click either image to open a larger detail view
- Scan-position overlay on the fundus image: the current B-scan's line plus
  a box showing the full scan area
- Contrast/brightness adjustment
- Patient/series/B-scan metadata table (`View > Image Info`)
- In-app notice when a newer version is available
- Standalone Windows and macOS builds, produced automatically via CI
