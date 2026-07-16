#!/usr/bin/env bash
# Merge two single-arch PyInstaller --onedir .app bundles into one universal2
# bundle. PyInstaller's own --target-arch universal2 flag requires every native
# dependency to ship as a fat binary, which PySide6/numpy/etc. do not - so CI
# builds arm64 and x86_64 separately and stitches Mach-O files with lipo.
#
# This does NOT work for --onefile builds (embedded PKG archive); this project
# uses --onedir, where each library is a separate file on disk.
#
# Some packages ship arch-specific sidecar binaries with different filenames
# (e.g. imageio_ffmpeg's ffmpeg-macos-aarch64 vs ffmpeg-macos-x86_64). Those are
# copied from both sides rather than lipo'd. Prefer excluding such packages when
# the app does not need them.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <arm64.app> <x86_64.app> <output.app>" >&2
  exit 1
fi

ARM_APP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
X86_APP="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
OUT_APP="$(cd "$(dirname "$3")" && pwd)/$(basename "$3")"

if [[ ! -d "$ARM_APP" || ! -d "$X86_APP" ]]; then
  echo "Input .app bundles must exist." >&2
  exit 1
fi

is_macho() {
  local f="$1"
  [[ -f "$f" ]] && file "$f" | grep -q 'Mach-O'
}

rm -rf "$OUT_APP"
cp -R "$ARM_APP" "$OUT_APP"

# Copy any files that exist only in the x86_64 bundle (arch-specific sidecars).
while IFS= read -r -d '' x86_file; do
  rel="${x86_file#"$X86_APP"/}"
  out_file="$OUT_APP/$rel"
  if [[ ! -e "$out_file" ]]; then
    mkdir -p "$(dirname "$out_file")"
    cp "$x86_file" "$out_file"
    echo "Copied x86-only: $rel"
  fi
done < <(find "$X86_APP" -type f -print0)

merged=0
while IFS= read -r -d '' arm_file; do
  rel="${arm_file#"$OUT_APP"/}"
  out_file="$OUT_APP/$rel"
  x86_file="$X86_APP/$rel"

  if ! is_macho "$out_file"; then
    continue
  fi
  if [[ ! -f "$x86_file" ]]; then
    # Arch-specific single-file Mach-O (kept as-is; both arch variants should
    # already be present via the copy step above when names differ).
    echo "Keeping single-arch Mach-O (no same-path pair): $rel"
    continue
  fi
  if ! is_macho "$x86_file"; then
    echo "ERROR: $rel is Mach-O in arm64 but not in x86_64." >&2
    exit 1
  fi

  tmp="${out_file}.universal"
  lipo -create "$out_file" "$x86_file" -output "$tmp"
  chmod "$(stat -f '%OLp' "$out_file")" "$tmp"
  mv "$tmp" "$out_file"
  echo "Merged: $rel"
  merged=$((merged + 1))
done < <(find "$OUT_APP" -type f -print0)

if [[ "$merged" -lt 1 ]]; then
  echo "ERROR: no Mach-O files were lipo-merged." >&2
  exit 1
fi

echo "Re-signing universal app bundle (inner binaries first)..."
while IFS= read -r -d '' macho_file; do
  codesign --force --sign - --timestamp=none "$macho_file"
done < <(find "$OUT_APP/Contents" -type f -print0 | while IFS= read -r -d '' f; do
  if is_macho "$f"; then printf '%s\0' "$f"; fi
done)

codesign --force --sign - --timestamp=none "$OUT_APP"

echo "Verifying main executable..."
MAIN_EXEC="$OUT_APP/Contents/MacOS/OCT Viewer"
lipo -info "$MAIN_EXEC"
codesign --verify --deep --strict "$OUT_APP"
