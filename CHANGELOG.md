# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
