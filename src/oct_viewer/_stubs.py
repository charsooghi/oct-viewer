"""Import stubs for optional oct-converter dependencies.

oct-converter's image_types modules import cv2 at load time, but OCT Viewer only
calls E2E.read_all_metadata() and never uses cv2. Bundled OpenCV also requires
recent macOS versions and pulls in dylibs (e.g. OpenEXR) that break on older Macs.
"""
from __future__ import annotations

import sys
import types

if "cv2" not in sys.modules:
    sys.modules["cv2"] = types.ModuleType("cv2")
