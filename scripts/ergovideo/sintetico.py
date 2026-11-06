"""Esqueletos sintéticos con el formato de MediaPipe, para probar las medidas y la clasificación OWAS
con posturas conocidas (sin vídeo). No sustituye a una validación con personas reales."""

from __future__ import annotations

import math

import numpy as np

W, H, ESCALA, CX, CY = 1280, 720, 300.0, 640.0, 300.0
ABAJO = np.array([0.0, 1.0, 0.0])
ARRIBA = -ABAJO


def _rot(eje: np.ndarray, ang_deg: float) -> np.ndarray:
    a = math.radians(ang_deg)
    eje = eje / np.linalg.norm(eje)
    K = np.array([[0, -eje[2], eje[1]], [eje[2], 0, -eje[0]], [-eje[1], eje[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


def esqueleto(flexion=0.0, lateral=0.0, giro=0.0, brazo_I=0.0, brazo_D=0.0,
              muslo_I=0.0, rodilla_I=0.0, muslo_D=0.0, rodilla_D=0.0, levantar_I=0.0,
              cuello=0.0, abd_I=0.0, abd_D=0.0, codo_I=0.0, codo_D=0.0, muneca_I=0.0, muneca_D=0.0,
              cruzar_I=0.0) -> np.ndarray:
    """Puntos 3D (33, 3) en metros, Y hacia abajo, origen en la cadera, el trabajador mirando a −Z.

    flexion/lateral/giro: grados del tronco. brazo_X: elevación del brazo respecto a la vertical, hacia delante
    (0 = colgando, 90 = horizontal, 180 = vertical arriba). muslo_X: muslo respecto a la vertical, hacia delante.
    rodilla_X: flexión de la rodilla. levantar_I: metros que se levanta el pie izquierdo (pierna en el aire).
    cuello: flexión del cuello respecto al tronco. abd_X: abducción del brazo (hacia fuera, en el plano frontal;
    sustituye a brazo_X). codo_X: flexión del codo. muneca_X: flexión de la muñeca. cruzar_I: grados que el
    antebrazo izq. se gira hacia la línea media (para RULA).
    """
    x = np.array([1.0, 0.0, 0.0])   # de la cadera dcha. a la izq. (el trabajador mira a la cámara)
    f = np.array([0.0, 0.0, -1.0])  # hacia delante
    P = np.zeros((33, 3))
    P[23], P[24] = 0.1 * x, -0.1 * x
    # Tronco: flexión (alrededor de x), inclinación lateral (alrededor de f) y torsión (alrededor del eje del tronco).
    R = _rot(f, lateral) @ _rot(x, flexion)
    eje = R @ ARRIBA
    Rg = _rot(eje, giro) @ R
    hm = Rg @ (0.5 * ARRIBA)
    P[11], P[12] = hm + Rg @ (0.18 * x), hm - Rg @ (0.18 * x)
    cab = hm + Rg @ (_rot(x, cuello) @ (0.2 * ARRIBA))
    fr = Rg @ f
    P[0] = cab + 0.08 * fr
    for i, s in ((1, 1), (2, 1), (3, 1), (4, -1), (5, -1), (6, -1)):
        P[i] = cab + 0.06 * fr + s * 0.03 * (Rg @ x) + 0.03 * (Rg @ ARRIBA)
    P[7], P[8] = cab + Rg @ (0.07 * x), cab - Rg @ (0.07 * x)
    P[9], P[10] = cab + 0.07 * fr + 0.02 * (Rg @ x) - 0.04 * (Rg @ ARRIBA), cab + 0.07 * fr - 0.02 * (Rg @ x) - 0.04 * (Rg @ ARRIBA)
    for sh, el, wr, ang, abd, cod, mun, cr, fuera, mano in (
            (11, 13, 15, brazo_I, abd_I, codo_I, muneca_I, cruzar_I, x, (17, 19, 21)),
            (12, 14, 16, brazo_D, abd_D, codo_D, muneca_D, 0.0, -x, (18, 20, 22))):
        if abd:
            d = math.cos(math.radians(abd)) * ABAJO + math.sin(math.radians(abd)) * fuera
        else:
            d = math.cos(math.radians(ang)) * ABAJO + math.sin(math.radians(ang)) * f
        P[el] = P[sh] + 0.3 * d
        # Antebrazo: se dobla hacia delante (o hacia arriba si el brazo ya apunta adelante).
        n = f - (f @ d) * d
        n = n / np.linalg.norm(n) if np.linalg.norm(n) > 1e-6 else ARRIBA
        if cr:  # el antebrazo se dobla hacia la línea media en lugar de hacia delante
            n = math.cos(math.radians(cr)) * n - math.sin(math.radians(cr)) * fuera
            n = n - (n @ d) * d
            n = n / np.linalg.norm(n)
        a = math.cos(math.radians(cod)) * d + math.sin(math.radians(cod)) * n
        P[wr] = P[el] + 0.27 * a
        # Mano: se dobla respecto al antebrazo, en el plano del antebrazo.
        m = n - (n @ a) * a
        m = m / np.linalg.norm(m) if np.linalg.norm(m) > 1e-6 else ARRIBA
        h = math.cos(math.radians(mun)) * a + math.sin(math.radians(mun)) * m
        lat = np.cross(a, m)
        P[mano[0]] = P[wr] + 0.08 * h - 0.02 * lat   # meñique
        P[mano[1]] = P[wr] + 0.08 * h + 0.02 * lat   # índice
        P[mano[2]] = P[wr] + 0.04 * h + 0.03 * lat   # pulgar
    for hip, kn, an, he, ft, th, k, lev in ((23, 25, 27, 29, 31, muslo_I, rodilla_I, levantar_I),
                                            (24, 26, 28, 30, 32, muslo_D, rodilla_D, 0.0)):
        dm = math.cos(math.radians(th)) * ABAJO + math.sin(math.radians(th)) * f
        dp = math.cos(math.radians(th - k)) * ABAJO + math.sin(math.radians(th - k)) * f
        P[kn] = P[hip] + 0.45 * dm
        P[an] = P[kn] + 0.43 * dp
        P[an] = P[an] + lev * ARRIBA if lev else P[an]
        P[he] = P[an] - 0.05 * f
        P[ft] = P[an] + 0.15 * f
    return P


def proyectar(P: np.ndarray, vista: float = 0.0, desplazamiento_x: float = 0.0,
              visibilidad: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Gira el cuerpo `vista` grados alrededor de la vertical y lo proyecta (ortográfica) a una imagen W×H.

    Devuelve (lm (33, 4) normalizados como MediaPipe, wlm (33, 3))."""
    Rv = _rot(ARRIBA, vista)
    w = (Rv @ P.T).T
    lm = np.zeros((33, 4))
    lm[:, 0] = (CX + ESCALA * (w[:, 0] + desplazamiento_x)) / W
    lm[:, 1] = (CY + ESCALA * w[:, 1]) / H
    lm[:, 2] = w[:, 2]
    lm[:, 3] = 1.0 if visibilidad is None else visibilidad
    return lm, w


def pose_sintetica(posturas: list[dict], fps: float = 10.0, vista: float = 30.0, velocidad_x: float = 0.0,
                   ruido: float = 0.0, semilla: int = 0):
    """Objeto Pose a partir de una lista de posturas (una por fotograma)."""
    from .pose import Pose

    rng = np.random.default_rng(semilla)
    lms, wlms = [], []
    for i, p in enumerate(posturas):
        lm, w = proyectar(esqueleto(**p), vista, desplazamiento_x=velocidad_x * i / fps)
        if ruido:
            lm[:, :2] += rng.normal(0, ruido, (33, 2))
            w += rng.normal(0, ruido, (33, 3))
        lms.append(lm)
        wlms.append(w)
    n = len(posturas)
    return Pose("sintetico", np.arange(n) / fps, np.arange(n), np.array(lms), np.array(wlms), W, H, fps, n / fps, "sintetico")


def fotograma(**postura):
    """(p2 en píxeles, w 3D, usable) de una postura, listo para medidas_fotograma."""
    vista = postura.pop("vista", 0.0)
    lm, w = proyectar(esqueleto(**postura), vista)
    p2 = np.stack([lm[:, 0] * W, lm[:, 1] * H], axis=-1)
    return p2, w, np.ones(33, bool)
