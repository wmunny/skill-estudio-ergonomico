"""Descarga los modelos de MediaPipe Pose Landmarker (repositorio oficial de Google) a modelos/."""

import sys
import urllib.request
from pathlib import Path

URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{m}/float16/1/pose_landmarker_{m}.task"
DESTINO = Path(__file__).resolve().parents[1] / "modelos"


def main(modelos=("full", "heavy")) -> None:
    DESTINO.mkdir(exist_ok=True)
    for m in modelos:
        ruta = DESTINO / f"pose_landmarker_{m}.task"
        if ruta.exists():
            print(f"Ya existe {ruta.name}")
            continue
        print(f"Descargando {ruta.name}…")
        urllib.request.urlretrieve(URL.format(m=m), ruta)


if __name__ == "__main__":
    main(sys.argv[1:] or ("full", "heavy"))
