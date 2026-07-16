#!/usr/bin/env bash
# Merge two single-arch PyInstaller --onedir .app bundles into one universal2
# bundle. PyInstaller's own --target-arch universal2 flag requires every native
# dependency to ship as a fat binary, which PySide6/numpy/etc. do not - so CI
# builds arm64 and x86_64 separately and stitches Mach-O files with lipo.
#
# This does NOT work for --onefile builds (embedded PKG archive); this project
# uses --onedir, where each library is a separate file on disk.
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

echo "Checking bundle layouts match..."
ARM_LIST="$(cd "$ARM_APP" && find . -type f | sort)"
X86_LIST="$(cd "$X86_APP" && find . -type f | sort)"
if [[ "$ARM_LIST" != "$X86_LIST" ]]; then
  echo "ERROR: arm64 and x86_64 app bundles have different file layouts." >&2
  diff <(echo "$ARM_LIST") <(echo "$X86_LIST") >&2 || true
  exit 1
fi

rm -rf "$OUT_APP"
cp -R "$ARM_APP" "$OUT_APP"

is_macho() {
  local f="$1"
  [[ -f "$f" ]] && file "$f" | grep -q 'Mach-O'
}

merge_file() {
  local rel="$1"
  local out_file="$OUT_APP/$rel"
  local x86_file="$X86_APP/$rel"

  if ! is_macho "$out_file"; then
    return 0
  fi
  if [[ ! -f "$x86_file" ]] || ! is_macho "$x86_file"; then
    echo "ERROR: Mach-O $rel has no x86_64 counterpart to merge." >&2
    exit 1
  fi

  local tmp="${out_file}.universal"
  lipo -create "$out_file" "$x86_file" -output "$tmp"
  chmod "$(stat -f '%OLp' "$out_file")" "$tmp"
  mv "$tmp" "$out_file"
  echo "Merged: $rel"
}

while IFS= read -r -d '' arm_file; do
  rel="${arm_file#"$OUT_APP"/}"
  merge_file "$rel"
done < <(find "$OUT_APP" -type f -print0)

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
