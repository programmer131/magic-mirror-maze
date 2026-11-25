"""Launch Magic Mirror Maze on this computer."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Magic Mirror Maze")
    parser.add_argument("--camera", type=int, default=None, help="Camera index, for example 10 for /dev/video10. Omit to detect a USB camera.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--arabic", action="store_true", help="Open the hands-free Arabic tutor directly.")
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    from .window import MazeWindow

    app = QApplication(sys.argv)
    window = MazeWindow(camera=args.camera, camera_enabled=not args.arabic)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.show()
    if args.arabic:
        QTimer.singleShot(0, lambda: window._open_activity('arabic'))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
