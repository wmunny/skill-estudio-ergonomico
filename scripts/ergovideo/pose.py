"""Estimación de postura con MediaPipe Pose Landmarker (API Tasks), fotograma a fotograma."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
MODELOS = RAIZ / "modelos"
URL_MODELO = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{m}/float16/1/pose_landmarker_{m}.task"


@dataclass
class Pose:
    video: str
    times: np.ndarray        # (N,) segundos
    frames: np.ndarray       # (N,) índice del fotograma en el vídeo original
    lm: np.ndarray           # (N, 33, 4) x, y normalizados a la imagen, z relativa, visibilidad; NaN sin persona
    wlm: np.ndarray          # (N, 33, 3) coordenadas «world» en metros, origen en la cadera, Y hacia abajo
    width: int
    height: int
    fps_video: float
    duracion: float
    modelo: str

    @property
    def detectado(self) -> np.ndarray:
        return ~np.isnan(self.lm[:, 0, 0])

    def guardar(self, ruta: Path) -> None:
        np.savez_compressed(ruta, times=self.times, frames=self.frames, lm=self.lm, wlm=self.wlm,
                            meta=np.array([self.video, self.width, self.height, self.fps_video, self.duracion, self.modelo], dtype=object))

    @classmethod
    def cargar(cls, ruta: Path) -> "Pose":
        d = np.load(ruta, allow_pickle=True)
        v, w, h, fps, dur, mod = d["meta"]
        return cls(str(v), d["times"], d["frames"], d["lm"], d["wlm"], int(w), int(h), float(fps), float(dur), str(mod))


def ruta_modelo(nombre: str) -> Path:
    ruta = MODELOS / f"pose_landmarker_{nombre}.task"
    if not ruta.exists():
        raise FileNotFoundError(
            f"Falta el modelo {ruta.name}. Descárgalo con: .venv\\Scripts\\python scripts\\descargar_modelos.py "
            f"(origen: {URL_MODELO.format(m=nombre)})")
    return ruta


def info_video(ruta: str | Path) -> dict:
    cap = cv2.VideoCapture(str(ruta))
    if not cap.isOpened():
        raise ValueError(f"No se puede abrir el vídeo: {ruta}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return dict(fps=fps, fotogramas=n, ancho=w, alto=h, duracion=n / fps if fps else 0.0)


def _huella(ruta: Path, fps_analisis: float, modelo: str) -> str:
    st = ruta.stat()
    return hashlib.sha1(f"{ruta.resolve()}|{st.st_size}|{st.st_mtime_ns}|{fps_analisis}|{modelo}".encode()).hexdigest()[:12]


def estimar(ruta_video: str | Path, fps_analisis: float = 10.0, modelo: str = "full",
            cache_dir: Path | None = None, progreso: bool = True) -> Pose:
    """Ejecuta MediaPipe sobre el vídeo a `fps_analisis` fotogramas por segundo (como máximo)."""
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    ruta_video = Path(ruta_video)
    if cache_dir:
        cache = Path(cache_dir) / f"pose_{ruta_video.stem}_{_huella(ruta_video, fps_analisis, modelo)}.npz"
        if cache.exists():
            return Pose.cargar(cache)

    cap = cv2.VideoCapture(str(ruta_video))
    if not cap.isOpened():
        raise ValueError(f"No se puede abrir el vídeo: {ruta_video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    paso = max(1, round(fps / fps_analisis))

    opciones = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(ruta_modelo(modelo))),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=0.5, min_pose_presence_confidence=0.5, min_tracking_confidence=0.5)

    times, idx, lms, wlms = [], [], [], []
    with vision.PoseLandmarker.create_from_options(opciones) as det:
        i = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if i % paso == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                t_ms = int(round(i * 1000 / fps))
                res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), t_ms)
                if res.pose_landmarks:
                    p = res.pose_landmarks[0]
                    lms.append([[q.x, q.y, q.z, q.visibility if q.visibility is not None else 1.0] for q in p])
                    wp = res.pose_world_landmarks[0]
                    wlms.append([[q.x, q.y, q.z] for q in wp])
                else:
                    lms.append(np.full((33, 4), np.nan))
                    wlms.append(np.full((33, 3), np.nan))
                times.append(i / fps)
                idx.append(i)
                if progreso and len(times) % 100 == 0:
                    print(f"  {ruta_video.name}: {i}/{total} fotogramas", file=sys.stderr)
            i += 1
    cap.release()
    if not times:
        raise ValueError(f"El vídeo {ruta_video} no tiene fotogramas legibles")
    pose = Pose(str(ruta_video), np.array(times), np.array(idx), np.array(lms, float), np.array(wlms, float),
                w, h, float(fps), i / fps, modelo)
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        pose.guardar(cache)
    return pose
