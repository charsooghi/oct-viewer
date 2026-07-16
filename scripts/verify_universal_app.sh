#!/usr/bin/env bash
# Fail CI if the merged .app main code path is not universal2 / not signed.
# Arch-specific sidecar binaries (different filenames per arch, e.g. ffmpeg)
# are allowed to remain single-arch.
set -euo pipefail

APP="${1:?Usage: $0 /path/to/OCT Viewer.app}"
MAIN="$APP/Contents/MacOS/OCT Viewer"
errors=0

echo "Main executable:"
lipo -info "$MAIN"
main_info="$(lipo -info "$MAIN")"
if ! echo "$main_info" | grep -q 'x86_64' || ! echo "$main_info" | grep -q 'arm64'; then
  echo "FAIL: main executable is not universal2 ($main_info)"
  errors=1
fi

is_arch_sidecar() {
  # Filenames that intentionally differ between architectures.
  case "$1" in
    *aarch64*|*arm64*|*x86_64*|*x86-64*|*ffmpeg*) return 0 ;;
    *) return 1 ;;
  esac
}

echo "Checking shared Mach-O binaries have arm64 and x86_64 slices..."
while IFS= read -r -d '' f; do
  if ! file "$f" | grep -q 'Mach-O'; then
    continue
  fi
  if is_arch_sidecar "$f"; then
    echo "Skip arch-sidecar: $f"
    continue
  fi
  info="$(lipo -info "$f" 2>&1)" || {
    echo "FAIL: $f ($info)"
    errors=1
    continue
  }
  if ! echo "$info" | grep -q 'x86_64'; then
    echo "FAIL: $f missing x86_64 ($info)"
    errors=1
  fi
  if ! echo "$info" | grep -q 'arm64'; then
    echo "FAIL: $f missing arm64 ($info)"
    errors=1
  fi
done < <(find "$APP" -type f -print0)

echo "Verifying code signature..."
if ! codesign --verify --deep --strict "$APP"; then
  errors=1
fi

if [[ "$errors" -ne 0 ]]; then
  echo "Universal app verification failed." >&2
  exit 1
fi

echo "Universal app verification passed."
