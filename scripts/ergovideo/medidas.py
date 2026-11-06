"""Medidas posturales por fotograma a partir de los puntos de MediaPipe.

Convenciones
- 2D: píxeles de la imagen, Y hacia abajo. Es lo que mide un técnico sobre el vídeo; fiable cuando el
  movimiento ocurre en un plano paralelo a la imagen (vista lateral para la flexión del tronco).
- 3D: coordenadas «world» de MediaPipe (metros, origen en la cadera, Y hacia abajo). Independiente del punto
  de vista, pero la profundidad es una estimación monocular.
- Modo «auto»: por fotograma, 2D si el trabajador está de perfil (giro respecto a la cámara ≥ 55°) y 3D si
  está de frente, de espaldas o en oblicuo. La torsión y la inclinación lateral salen siempre del 3D.
- La vertical es la de la cámara: hay que grabar con el móvil nivelado.
- Lado visible: si un lado no se ve, el tronco y la escala se calculan con el otro.
"""

from __future__ import annotations

import math

import numpy as np

from .config import MEDIDAS, PUNTOS, Config, CADERA_D, CADERA_I, HOMBRO_D, HOMBRO_I
from .filtros import RAZONES, filtrar_serie, puntos_invalidos

ARRIBA = np.array([0.0, -1.0, 0.0])
ABAJO = -ARRIBA


def _ang(u: np.ndarray, v: np.ndarray) -> float:
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu < 1e-9 or nv < 1e-9:
        return math.nan
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(u, v) / (nu * nv))))))


def _horizontal(v: np.ndarray) -> np.ndarray | None:
    h = np.array([v[0], 0.0, v[2]])
    n = np.linalg.norm(h)
    return h / n if n > 1e-9 else None


def vista_camara(w: np.ndarray) -> float:
    """Giro del trabajador respecto a la cámara (0° = de frente o de espaldas, 90° = de perfil)."""
    v = (w[HOMBRO_D] - w[HOMBRO_I]) + (w[CADERA_D] - w[CADERA_I])
    return math.degrees(math.atan2(abs(v[2]), abs(v[0]) + 1e-9))


def medidas_fotograma(p2: np.ndarray, w: np.ndarray, usable: np.ndarray, cfg: Config,
                      escala_px: float | None = None, usable_giro: np.ndarray | None = None) -> dict:
    """Medidas de un fotograma.

    p2: (33, 2) puntos en píxeles; w: (33, 3) puntos 3D; usable: (33,) bool (visibles y no rechazados).
    escala_px: longitud de referencia del tronco en píxeles (para la altura de los brazos).
    Devuelve un dict con las medidas de MEDIDAS (NaN si no se pueden calcular) y metadatos.
    """
    out = {k: math.nan for k in MEDIDAS}
    vista = vista_camara(w)
    modo = cfg.modo_angulos if cfg.modo_angulos != "auto" else ("2d" if vista >= cfg.filtros.vista_lateral else "3d")
    out["vista"] = vista
    out["modo"] = modo
    usable_giro = usable if usable_giro is None else usable_giro
    P3 = lambda i: w[i]  # noqa: E731
    P2 = lambda i: np.array([p2[i][0], p2[i][1], 0.0])  # noqa: E731
    P = P2 if modo == "2d" else P3

    # Tronco: con los dos lados o con el lado visible.
    lados = [s for s in "ID" if usable[PUNTOS[s]["hombro"]] and usable[PUNTOS[s]["cadera"]]]
    out["lado_tronco"] = "ambos" if len(lados) == 2 else (lados[0] if lados else None)
    # Eje lateral (hacia la derecha del trabajador) y eje hacia delante, horizontales (3D).
    x = _horizontal(w[CADERA_D] - w[CADERA_I])
    if x is None:
        x = _horizontal(w[HOMBRO_D] - w[HOMBRO_I])
    f = np.cross(ARRIBA, x) if x is not None else None
    sgn = (1.0 if f[0] >= 0 else -1.0) if f is not None else 1.0  # sentido de «delante» en la imagen (2D)

    def sag2(v):  # ángulo en el plano de la imagen respecto a la vertical, positivo hacia delante
        return math.degrees(math.atan2(v[0] * sgn, -v[1]))

    def sag3(v):  # ángulo en el plano sagital (3D) respecto a la vertical, positivo hacia delante
        return math.degrees(math.atan2(float(v @ f), float(v @ ARRIBA)))

    def media(fn, nombre):
        return np.mean([fn(PUNTOS[s][nombre]) for s in lados], axis=0)

    t = t2 = None
    if lados:
        t2 = media(P2, "hombro") - media(P2, "cadera")
        t = media(P3, "hombro") - media(P3, "cadera")
        if modo == "2d":
            out["tronco_flex"] = _ang(t2, ARRIBA)
            out["tronco_sag"] = sag2(t2)
        if f is not None:
            tu, tf, tx = float(t @ ARRIBA), float(t @ f), float(t @ x)
            nt = float(np.linalg.norm(t))
            if modo == "3d":
                out["tronco_flex"] = math.degrees(math.atan2(abs(tf), tu))
                out["tronco_sag"] = math.degrees(math.atan2(tf, tu))
            out["tronco_lat"] = math.degrees(math.asin(min(1.0, abs(tx) / max(nt, 1e-9))))
        elif modo == "3d":
            out["tronco_flex"] = _ang(t, ARRIBA)

    # Cuello: eje hombros→orejas respecto al eje del tronco, en el plano sagital (positivo = flexión).
    orejas = [i for i in (7, 8) if usable[i]]
    if lados and orejas and f is not None:
        if modo == "2d":
            h = np.mean([P2(i) for i in orejas], axis=0) - media(P2, "hombro")
            out["cuello"] = sag2(h) - sag2(t2)
        else:
            h = np.mean([P3(i) for i in orejas], axis=0) - media(P3, "hombro")
            out["cuello"] = sag3(h) - sag3(t)

    # Torsión: línea de hombros frente a línea de caderas en el plano horizontal (3D).
    if all(usable_giro[i] for i in (HOMBRO_I, HOMBRO_D, CADERA_I, CADERA_D)):
        a = _horizontal(w[HOMBRO_D] - w[HOMBRO_I])
        b = _horizontal(w[CADERA_D] - w[CADERA_I])
        if a is not None and b is not None:
            out["tronco_giro"] = math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b)))))

    # Escala para la altura de los brazos: longitud del tronco en píxeles.
    if escala_px is None and lados:
        escala_px = float(np.mean([np.linalg.norm(p2[PUNTOS[s]["hombro"]] - p2[PUNTOS[s]["cadera"]]) for s in lados]))
    out["escala_px"] = escala_px if escala_px else math.nan

    for s in "ID":
        k = PUNTOS[s]
        # Brazo: altura del codo o de la muñeca (la más alta) sobre el hombro, en longitudes de tronco (2D).
        if usable[k["hombro"]] and escala_px:
            alturas = [p2[k["hombro"]][1] - p2[j][1] for j in (k["codo"], k["muneca"]) if usable[j]]
            if alturas:
                out[f"brazo_alt_{s}"] = max(alturas) / escala_px
        # Pierna
        if usable[k["cadera"]] and usable[k["rodilla"]] and usable[k["tobillo"]]:
            cad, rod, tob = P(k["cadera"]), P(k["rodilla"]), P(k["tobillo"])
            out[f"rodilla_{s}"] = 180.0 - _ang(cad - rod, tob - rod)
            out[f"muslo_{s}"] = _ang(rod - cad, ABAJO)
            out[f"pierna_{s}"] = _ang(tob - rod, ABAJO)
    # Extremidad superior (REBA y RULA), por lado.
    if t is not None and f is not None:
        tn = t / max(np.linalg.norm(t), 1e-9)
        abajo_t = -tn
        ft = f - (f @ tn) * tn
        ft = ft / max(np.linalg.norm(ft), 1e-9)
        xs = w[HOMBRO_D] - w[HOMBRO_I]
        xs = xs - (xs @ tn) * tn
        xs = xs / max(np.linalg.norm(xs), 1e-9)
        for s in "ID":
            k = PUNTOS[s]
            if usable[k["hombro"]] and usable[k["codo"]]:
                u = w[k["codo"]] - w[k["hombro"]]
                abd = math.degrees(math.asin(min(1.0, abs(float(u @ xs)) / max(np.linalg.norm(u), 1e-9))))
                out[f"brazo_abd_{s}"] = abd
                elev = _ang(u, abajo_t)
                # Extensión solo por debajo de 90°: más allá, detrás del eje del tronco es flexión por encima de la cabeza.
                atras = float(u @ ft) < 0 and abs(float(u @ ft)) > abs(float(u @ xs)) and elev < 90
                if modo == "2d" and abd <= cfg.umbrales.brazo_abducido:
                    # De perfil: ángulo en la imagen entre el brazo y el eje del tronco hacia abajo (+ = flexión).
                    u2 = P2(k["codo"]) - P2(k["hombro"])
                    rel = sag2(-t2) - sag2(u2)
                    rel = (rel + 180) % 360 - 180
                    out[f"brazo_flex_{s}"] = min(180.0, rel + 360) if rel < -90 else rel  # >90° atrás = por encima
                else:
                    # 3D; también de perfil si el brazo está abducido (la abducción no se ve en el plano de la imagen).
                    out[f"brazo_flex_{s}"] = -elev if atras else elev
                if usable[k["muneca"]]:
                    # El codo se dobla en cualquier plano: siempre en 3D.
                    out[f"codo_{s}"] = 180.0 - _ang(P3(k["hombro"]) - P3(k["codo"]), P3(k["muneca"]) - P3(k["codo"]))
            # Muñeca: con los puntos de la mano de MediaPipe Pose (índice y meñique). Estimación tosca.
            mano = [17, 19] if s == "I" else [18, 20]
            if usable[k["codo"]] and usable[k["muneca"]] and all(usable[i] for i in mano):
                m3 = np.mean([w[i] for i in mano], axis=0) - w[k["muneca"]]
                if 0.02 <= np.linalg.norm(m3) <= 0.2:
                    out[f"muneca_{s}"] = _ang(w[k["muneca"]] - w[k["codo"]], m3)
            # Antebrazo respecto a la línea media (RULA): posición lateral de la muñeca en semianchos de hombros.
            otro = PUNTOS["D" if s == "I" else "I"]["hombro"]
            if usable_giro[k["hombro"]] and usable_giro[otro] and usable[k["muneca"]]:
                centro = (w[k["hombro"]] + w[otro]) / 2
                o = w[k["hombro"]] - centro
                hw = float(np.linalg.norm(o))
                if hw > 1e-6:
                    out[f"antebrazo_lat_{s}"] = float((w[k["muneca"]] - centro) @ (o / hw)) / hw

    ti, td = PUNTOS["I"]["tobillo"], PUNTOS["D"]["tobillo"]
    if usable[ti] and usable[td]:
        out["tobillos"] = float(w[td][1] - w[ti][1])  # Y hacia abajo: positivo = tobillo izq. más alto
    return out


def _mediana_movil(v: np.ndarray, t: np.ndarray, semi_s: float) -> np.ndarray:
    out = np.full_like(v, np.nan)
    for i in range(len(v)):
        m = np.abs(t - t[i]) <= semi_s
        win = v[m]
        win = win[~np.isnan(win)]
        if len(win):
            out[i] = np.median(win)
    return out


# Puntos de los que depende cada medida (para marcar la medida como «aproximada» si lo es alguno).
_L = {"I": dict(h=11, c=13, m=15, ca=23, r=25, t=27, mano=(17, 19)), "D": dict(h=12, c=14, m=16, ca=24, r=26, t=28, mano=(18, 20))}
PUNTOS_MEDIDA = {
    "tronco_flex": (11, 12, 23, 24), "tronco_sag": (11, 12, 23, 24), "tronco_lat": (11, 12, 23, 24),
    "tronco_giro": (11, 12, 23, 24), "cuello": (7, 8, 11, 12), "tobillos": (27, 28),
}
for _s, _p in _L.items():
    PUNTOS_MEDIDA.update({
        f"brazo_alt_{_s}": (_p["h"], _p["c"], _p["m"]), f"brazo_flex_{_s}": (_p["h"], _p["c"]),
        f"brazo_abd_{_s}": (_p["h"], _p["c"], 11, 12), f"codo_{_s}": (_p["h"], _p["c"], _p["m"]),
        f"muneca_{_s}": (_p["c"], _p["m"]) + _p["mano"], f"antebrazo_lat_{_s}": (11, 12, _p["m"]),
        f"rodilla_{_s}": (_p["ca"], _p["r"], _p["t"]), f"muslo_{_s}": (_p["ca"], _p["r"]), f"pierna_{_s}": (_p["r"], _p["t"]),
    })


def calcular(pose, cfg: Config, mascaras: dict | None = None) -> dict:
    """mascaras (de revision.politica): «quitar» (N, 33) puntos que no se usan; «aprox» (N, 33) puntos aproximados."""
    """Series de medidas filtradas de un vídeo.

    Devuelve dict con: t, series (filtradas), crudas, razones (recuentos por medida), invalidos (N,33),
    vista, modo, velocidad (longitudes de tronco/s), lado_tronco, visibilidad media por punto.
    """
    f = cfg.filtros
    N = len(pose.times)
    t = pose.times
    det = pose.detectado
    vis = np.nan_to_num(pose.lm[:, :, 3], nan=0.0)
    invalidos = puntos_invalidos(pose.lm, pose.wlm, pose.width, pose.height, f)
    usable = (vis >= f.visibilidad) & (invalidos == "") & det[:, None]
    usable_giro = (vis >= f.visibilidad_giro) & (invalidos == "") & det[:, None]
    if mascaras is not None:
        usable &= ~mascaras["quitar"]
        usable_giro &= ~mascaras["quitar"]
    p2 = np.stack([pose.lm[:, :, 0] * pose.width, pose.lm[:, :, 1] * pose.height], axis=-1)

    # Escala del tronco en píxeles: mediana móvil (4 s) para que no la deforme una flexión momentánea.
    esc = np.full(N, np.nan)
    for i in range(N):
        if det[i]:
            lados = [s for s in "ID" if usable[i, PUNTOS[s]["hombro"]] and usable[i, PUNTOS[s]["cadera"]]]
            if lados:
                esc[i] = np.mean([np.linalg.norm(p2[i, PUNTOS[s]["hombro"]] - p2[i, PUNTOS[s]["cadera"]]) for s in lados])
    escala = _mediana_movil(esc, t, 2.0)
    # La flexión acorta el tronco aparente: se toma el percentil 90 local como referencia de longitud.
    for i in range(N):
        m = (np.abs(t - t[i]) <= 2.0) & ~np.isnan(esc)
        if m.sum() >= 3:
            escala[i] = np.percentile(esc[m], 90)

    crudas = {k: np.full(N, np.nan) for k in MEDIDAS}
    vista = np.full(N, np.nan)
    modo = np.array([""] * N, dtype=object)
    lado = np.array([None] * N, dtype=object)
    for i in range(N):
        if not det[i]:
            continue
        m = medidas_fotograma(p2[i], pose.wlm[i], usable[i], cfg,
                              escala_px=None if np.isnan(escala[i]) else float(escala[i]), usable_giro=usable_giro[i])
        for k in MEDIDAS:
            crudas[k][i] = m[k]
        vista[i], modo[i], lado[i] = m["vista"], m["modo"], m["lado_tronco"]

    series, razones = {}, {}
    for k, spec in MEDIDAS.items():
        cuenta = {r: 0 for r in RAZONES}
        cuenta["visibilidad"] = int(np.isnan(crudas[k]).sum())
        esc_h = spec.get("hampel", f.hampel_minimo) / f.hampel_minimo
        series[k] = filtrar_serie(crudas[k], t, spec["rango"], spec["vmax"], f, cuenta, escala_hampel=esc_h)
        razones[k] = cuenta
    # Puntos rechazados por los filtros de puntos (para el informe).
    for k in MEDIDAS:
        razones[k]["huesos"] = 0
        razones[k]["coherencia"] = 0
    razones["_puntos"] = {"huesos": int((invalidos == "huesos").sum()), "coherencia": int((invalidos == "coherencia").sum())}

    # Velocidad del centro de la cadera (2D) en longitudes de tronco por segundo, sobre 1 s.
    cad = np.where(usable[:, [CADERA_I]] & usable[:, [CADERA_D]],
                   (p2[:, CADERA_I] + p2[:, CADERA_D]) / 2, np.nan)
    vel = np.full(N, np.nan)
    for i in range(N):
        a = np.flatnonzero((t >= t[i] - 0.5) & (t < t[i]) & ~np.isnan(cad[:, 0]))
        b = np.flatnonzero((t > t[i]) & (t <= t[i] + 0.5) & ~np.isnan(cad[:, 0]))
        if len(a) and len(b) and not np.isnan(escala[i]) and escala[i] > 0:
            ia, ib = a[0], b[-1]
            vel[i] = np.linalg.norm(cad[ib] - cad[ia]) / escala[i] / max(t[ib] - t[ia], 1e-6)
    # Valor interpolado (o sustituido por el filtro): hay dato en la serie pero no es el medido en ese fotograma.
    interpolado = {k: ~np.isnan(series[k]) & (np.isnan(crudas[k]) | (np.abs(series[k] - np.nan_to_num(crudas[k])) > 1e-9))
                   for k in MEDIDAS}
    ap = mascaras["aprox"] if mascaras is not None else np.zeros((N, 33), bool)
    aproximado = {k: ~np.isnan(series[k]) & ap[:, list(PUNTOS_MEDIDA.get(k, ()))].any(axis=1) if PUNTOS_MEDIDA.get(k)
                  else np.zeros(N, bool) for k in MEDIDAS}
    return dict(t=t, series=series, crudas=crudas, razones=razones, invalidos=invalidos, usable=usable, interpolado=interpolado,
                aproximado=aproximado, quitados=(mascaras["quitar"] if mascaras is not None else np.zeros((N, 33), bool)),
                vista=vista, modo=modo, lado_tronco=lado, velocidad=vel, escala_px=escala,
                visibilidad=vis, detectado=det)
