"""Launch Magic Mirror Maze on this computer."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Magic Mirror Maze")
    parser.add_argument("--camera", type=int, default=0, help="Camera index, for example 10 for /dev/video10.")
    parser.add_argument("--fullscreen", action="store_true")
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from .window import MazeWindow

    app = QApplication(sys.argv)
    window = MazeWindow(camera=args.camera)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
