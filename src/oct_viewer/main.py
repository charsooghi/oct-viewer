from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from oct_viewer.gui.main_window import MainWindow


def main():
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setApplicationName("OCT Viewer")
    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        window._load_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
