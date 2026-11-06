"""Filtros mecánicos contra oclusiones y reconstrucciones imposibles de MediaPipe.

Dos niveles, como en la PoC postura-poc:
 1. Puntos (por fotograma), antes de calcular medidas:
    - longitud de los huesos: en 3D cada segmento mide siempre lo mismo; si se aleja de su mediana,
      el punto distal es dudoso;
    - coherencia 2D–3D: si en 3D el segmento sube y en la imagen baja (o al revés), el 3D se ha inventado.
 2. Series temporales de cada medida:
    - rango fisiológico;
    - valores atípicos (Hampel);
    - tramos cortos separados por saltos imposibles (velocidad máxima);
    - relleno de huecos cortos por interpolación; los largos se dejan vacíos.
Los filtros solo quitan datos imposibles. No detectan una articulación tapada pero plausible:
eso lo dice la cobertura y la visibilidad, y lo revisa una persona.
"""

from __future__ import annotations

import numpy as np

from .config import SEGMENTOS, Filtros

RAZONES = {
    "visibilidad": "Visibilidad baja o persona no detectada",
    "huesos": "Longitud de hueso anómala",
    "coherencia": "Incoherencia 2D–3D",
    "rango": "Fuera de rango fisiológico",
    "atipicos": "Valor atípico (Hampel)",
    "saltos": "Tramo corto tras un salto imposible",
    "interpolados": "Hueco corto interpolado",
}


def puntos_invalidos(lm: np.ndarray, wlm: np.ndarray, width: int, height: int, f: Filtros) -> np.ndarray:
    """Matriz (N, 33) de razones: '' si el punto es válido, 'huesos' o 'coherencia' si no."""
    n = lm.shape[0]
    malo = np.full((n, 33), "", dtype=object)
    vis = np.nan_to_num(lm[:, :, 3], nan=0.0) >= f.visibilidad
    for a, b in SEGMENTOS:
        ok = vis[:, a] & vis[:, b]
        d3 = wlm[:, b] - wlm[:, a]
        largo = np.linalg.norm(d3, axis=1)
        if ok.sum() >= 5:
            ref = np.nanmedian(largo[ok])
            if ref > 0:
                hueso = ok & (np.abs(largo / ref - 1) > f.tolerancia_hueso)
                malo[hueso & (malo[:, b] == ""), b] = "huesos"
        s3 = d3[:, 1] / np.maximum(largo, 1e-9)
        dx = (lm[:, b, 0] - lm[:, a, 0]) * width
        dy = (lm[:, b, 1] - lm[:, a, 1]) * height
        s2 = dy / np.maximum(np.hypot(dx, dy), 1e-9)
        incoh = ok & (s3 * s2 < 0) & (np.abs(s3) > f.coherencia_vertical) & (np.abs(s2) > f.coherencia_vertical)
        malo[incoh & (malo[:, b] == ""), b] = "coherencia"
    return malo


def filtrar_serie(v: np.ndarray, t: np.ndarray, rango: tuple, vmax: float, f: Filtros,
                  cuenta: dict | None = None, escala_hampel: float = 1.0) -> np.ndarray:
    """Aplica rango, Hampel, saltos y relleno de huecos cortos. NaN = sin dato."""
    cuenta = cuenta if cuenta is not None else {}
    for k in ("rango", "atipicos", "saltos", "interpolados"):
        cuenta.setdefault(k, 0)
    v = np.array(v, float)
    n = len(v)
    if n < 3:
        return v
    dt = float(np.median(np.diff(t))) if n > 1 else 0.1

    # 1. Rango fisiológico
    fuera = ~np.isnan(v) & ((v < rango[0]) | (v > rango[1]))
    cuenta["rango"] += int(fuera.sum())
    v[fuera] = np.nan

    # 2. Hampel
    h = max(2, round(f.hampel_ventana_s / dt))
    src = v.copy()
    minimo = f.hampel_minimo * escala_hampel
    for i in np.flatnonzero(~np.isnan(src)):
        win = src[max(0, i - h): i + h + 1]
        win = win[~np.isnan(win)]
        if len(win) < 5:
            continue
        med = np.median(win)
        mad = 1.4826 * np.median(np.abs(win - med))
        if abs(src[i] - med) > max(f.hampel_sigmas * mad, minimo):
            v[i] = np.nan
            cuenta["atipicos"] += 1

    # 3. Tramos cortos delimitados por saltos imposibles
    def salto(i: int) -> bool:
        return 0 < i < n and not np.isnan(v[i]) and not np.isnan(v[i - 1]) and \
            abs(v[i] - v[i - 1]) / max(t[i] - t[i - 1], 1e-6) > vmax

    i = 0
    while i < n:
        if np.isnan(v[i]):
            i += 1
            continue
        e = i
        while e + 1 < n and not np.isnan(v[e + 1]) and not salto(e + 1):
            e += 1
        dur = t[e] - t[i] + dt
        largo = e - i + 1
        if largo <= 2 or (dur < f.tramo_minimo_s and (salto(i) or salto(e + 1))):
            v[i:e + 1] = np.nan
            cuenta["saltos"] += largo
        i = e + 1

    # 4. Relleno de huecos cortos
    i = 1
    while i < n:
        if not np.isnan(v[i]) or np.isnan(v[i - 1]):
            i += 1
            continue
        e = i
        while e < n and np.isnan(v[e]):
            e += 1
        if e < n:
            a = i - 1
            span = t[e] - t[a]
            if span - dt <= f.hueco_maximo_s + 1e-6 and abs(v[e] - v[a]) / span <= vmax:
                v[i:e] = v[a] + (v[e] - v[a]) * (t[i:e] - t[a]) / span
                cuenta["interpolados"] += e - i
        i = e + 1
    return v
