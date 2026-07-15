"""Lightweight "check for updates" - not a silent auto-updater.

Pings GitHub's Releases API once on startup and, if a newer tag exists,
signals the main window to show a link to the download page. Any failure
(offline, GitHub unreachable, rate-limited) is swallowed silently since this
is a nice-to-have, not core functionality.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from urllib.error import URLError

from PySide6.QtCore import QThread, Signal

from .._version import __version__

log = logging.getLogger(__name__)

RELEASES_API = "https://api.github.com/repos/charsooghi/oct-viewer/releases/latest"
RELEASES_PAGE = "https://github.com/charsooghi/oct-viewer/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lower().lstrip("v")
    parts = []
    for piece in cleaned.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class UpdateCheckWorker(QThread):
    update_available = Signal(str, str)  # latest_version tag, release page url

    def run(self):
        try:
            req = urllib.request.Request(RELEASES_API, headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.load(resp)
        except (URLError, TimeoutError, ValueError, OSError):
            log.info("Update check skipped (offline or GitHub unreachable).")
            return
        except Exception:
            log.warning("Unexpected error during update check.", exc_info=True)
            return

        latest_tag = data.get("tag_name", "")
        release_url = data.get("html_url") or RELEASES_PAGE
        if latest_tag and _parse_version(latest_tag) > _parse_version(__version__):
            self.update_available.emit(latest_tag, release_url)
