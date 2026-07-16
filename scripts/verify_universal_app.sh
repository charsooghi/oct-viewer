#!/usr/bin/env bash
# Fail CI if the merged .app is not fully universal2 or not ad-hoc signed.
set -euo pipefail

APP="${1:?Usage: $0 /path/to/OCT Viewer.app}"
MAIN="$APP/Contents/MacOS/OCT Viewer"
errors=0

echo "Main executable:"
lipo -info "$MAIN"

echo "Checking every Mach-O binary has arm64 and x86_64 slices..."
while IFS= read -r -d '' f; do
  if file "$f" | grep -q 'Mach-O'; then
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
