#!/usr/bin/env bash
# Launch the frozen app briefly and fail on import/startup crashes.
# Catches issues like missing native libs / ImportError before users download.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path-to-OCT Viewer.app|path-to-OCT Viewer.exe-dir>" >&2
  exit 1
fi

TARGET="$1"
LOG="$(mktemp)"
cleanup() { rm -f "$LOG"; }
trap cleanup EXIT

if [[ "$(uname -s)" == "Darwin" ]]; then
  MAIN="$TARGET/Contents/MacOS/OCT Viewer"
  if [[ ! -x "$MAIN" ]]; then
    echo "Missing executable: $MAIN" >&2
    exit 1
  fi
  # Headless Qt so CI runners without a full GUI session still exercise imports.
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

  run_once() {
    local label="$1"
    shift
    echo "Smoke launch ($label)..."
    : >"$LOG"
    "$@" >"$LOG" 2>&1 &
    local pid=$!
    sleep 8
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      echo "OK ($label): process stayed alive (imports loaded)."
      return 0
    fi
    wait "$pid" || true
    if grep -E 'ImportError|ModuleNotFoundError|\[PYI-.*ERROR\]|Traceback \(most recent call last\)' "$LOG"; then
      echo "FAIL ($label): startup crash:" >&2
      cat "$LOG" >&2
      return 1
    fi
    echo "WARN ($label): process exited early without ImportError; log follows:"
    cat "$LOG"
    return 0
  }

  run_once "arm64-native" "$MAIN"
  # Exercise the Intel slice under Rosetta on Apple Silicon runners.
  if arch -x86_64 /usr/bin/true 2>/dev/null; then
    run_once "x86_64-rosetta" arch -x86_64 "$MAIN"
  else
    echo "Skip x86_64 smoke (Rosetta unavailable)."
  fi
else
  # Windows: TARGET is the onedir folder containing "OCT Viewer.exe"
  EXE="$TARGET/OCT Viewer.exe"
  if [[ ! -f "$EXE" ]]; then
    echo "Missing executable: $EXE" >&2
    exit 1
  fi
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
  echo "Smoke launch (Windows)..."
  "$EXE" >"$LOG" 2>&1 &
  pid=$!
  sleep 8
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    echo "OK: process stayed alive (imports loaded)."
    exit 0
  fi
  wait "$pid" || true
  if grep -E 'ImportError|ModuleNotFoundError|\[PYI-.*ERROR\]|Traceback \(most recent call last\)' "$LOG"; then
    echo "FAIL: startup crash:" >&2
    cat "$LOG" >&2
    exit 1
  fi
  echo "WARN: process exited early without ImportError; log follows:"
  cat "$LOG"
fi
