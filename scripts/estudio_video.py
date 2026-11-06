r"""Punto de entrada: .venv\Scripts\python scripts\estudio_video.py <inspeccionar|analizar> ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from ergovideo.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
