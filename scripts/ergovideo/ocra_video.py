"""Lo que aporta el vídeo a OCRA (opcional): MediaPipe no es imprescindible.

OCRA es un método observacional (vídeo a cámara lenta, entrevista y datos de organización). Si MediaPipe ve al
trabajador, se usa para:
(a) proponer el tiempo de ciclo por la periodicidad de las series de muñeca, codo y hombro;
(b) estimar la fracción del tiempo con hombro, codo y muñeca en postura forzada (para PoM), como rango;
(c) proponer instantes candidatos a acción técnica (paradas y cambios de velocidad de la mano) para la revisión.
Si no sirve (plano cerrado de manos, oclusión), el análisis sigue por la vía observacional.

`validar` comprueba lo que OCRA necesita del vídeo: al menos 3 ciclos, manos y objetos visibles, la mano más activa
del lado de la cámara y fotogramas suficientes (≥ 25 fps). No penaliza que no se vean las piernas ni el tronco.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import tablas_ocra as T
from .config import margen

CICLOS_MINIMOS = 3
FPS_RECOMENDADO = 25.0
FPS_MINIMO = 15.0
MANOS_VISIBLES = 70.0        # % de fotogramas con la muñeca visible
CICLO_MIN_S, CICLO_MAX_S = 2.0, 300.0
AUTOCORR_MINIMA = 0.3        # pico de autocorrelación por debajo → ciclo no fiable
COBERTURA_POSTURA = 50.0     # % mínimo de fotogramas medidos para dar una fracción de postura
LADO = {"I": "izq", "D": "dch"}


# ------------------------------------------------------------------ (a) tiempo de ciclo

def _rejilla(t: np.ndarray, x: np.ndarray, dt: float):
    ok = ~np.isnan(x)
    if ok.sum() < 10 or ok.mean() < 0.6:
        return None
    tg = np.arange(t[0], t[-1], dt)
    return np.interp(tg, t[ok], x[ok])


def ciclo_periodicidad(res: dict, duracion: float) -> dict:
    """Periodo dominante de las series de los brazos por autocorrelación (media de las series disponibles)."""
    t = res["t"]
    if len(t) < 20:
        return dict(ciclo_s=None, confianza=0.0, ciclos=None, series=[], motivo="muy pocos fotogramas")
    dt = float(np.median(np.diff(t)))
    claves = [k for s in "ID" for k in (f"brazo_alt_{s}", f"codo_{s}", f"brazo_flex_{s}", f"antebrazo_lat_{s}")]
    acs, usadas = [], []
    max_lag = int(min(CICLO_MAX_S, duracion / 2) / dt)
    min_lag = int(CICLO_MIN_S / dt)
    if max_lag <= min_lag + 2:
        return dict(ciclo_s=None, confianza=0.0, ciclos=None, series=[], motivo="vídeo demasiado corto")
    for k in claves:
        x = _rejilla(t, res["series"].get(k, np.full(len(t), np.nan)), dt)
        if x is None or np.std(x) < 1e-6:
            continue
        x = (x - x.mean()) / x.std()
        n = len(x)
        ac = np.array([np.dot(x[:n - L], x[L:]) / (n - L) for L in range(max_lag + 1)])
        acs.append(ac)
        usadas.append(k)
    if not acs:
        return dict(ciclo_s=None, confianza=0.0, ciclos=None, series=[], motivo="los brazos no se ven lo suficiente")
    ac = np.mean(acs, axis=0)
    picos = [L for L in range(max(min_lag, 1), max_lag) if ac[L] >= ac[L - 1] and ac[L] >= ac[L + 1] and ac[L] > 0]
    if not picos:
        return dict(ciclo_s=None, confianza=0.0, ciclos=None, series=usadas, motivo="sin periodicidad clara")
    mejor = max(ac[L] for L in picos)
    # El primer pico que llega al 85 % del mejor (evita elegir un múltiplo del ciclo).
    L = next(L for L in picos if ac[L] >= 0.85 * mejor)
    ciclo = L * dt
    conf = float(ac[L])
    return dict(ciclo_s=round(ciclo, 2), confianza=round(conf, 2), ciclos=round(duracion / ciclo, 1), series=usadas,
                fiable=conf >= AUTOCORR_MINIMA,
                motivo="" if conf >= AUTOCORR_MINIMA else f"periodicidad débil (autocorrelación {conf:.2f})")


# ------------------------------------------------------------------ (b) fracciones de postura forzada

def _fraccion(cond_lo: np.ndarray, cond_hi: np.ndarray, medido: np.ndarray) -> dict:
    """Fracción del tiempo en postura forzada. Lo no medido se recorre: cuenta 0 en el mínimo y 1 en el máximo."""
    n = len(medido)
    if n == 0:
        return dict(min=0.0, max=1.0, cobertura=0.0)
    seguro = np.sum(cond_lo & medido)
    posible = np.sum(cond_hi & medido) + np.sum(~medido)
    return dict(min=float(seguro / n), max=float(posible / n), cobertura=float(100 * medido.mean()))


def fracciones_postura(res: dict, inicio: float | None = None, fin: float | None = None) -> dict:
    """Por lado (dch/izq): fracción del tiempo con hombro, codo y muñeca en postura forzada, con el margen de medida.

    `cond_lo`: forzada aun restando el margen (seguro); `cond_hi`: forzada sumando el margen (posible).
    """
    t = res["t"]
    sel = np.ones(len(t), bool)
    if inicio is not None:
        sel &= t >= inicio - 1e-6
    if fin is not None:
        sel &= t <= fin + 1e-6
    s = res["series"]
    P = T.POSTURA_FORZADA
    out = {}
    for lado in "ID":
        def serie(k):
            return s[f"{k}_{lado}"][sel]
        fl, ab, co, mu = serie("brazo_flex"), serie("brazo_abd"), serie("codo"), serie("muneca")
        mf, ma, mc, mm = margen("brazo_flex_I"), margen("brazo_abd_I"), margen("codo_I"), margen("muneca_I")
        med_h = ~np.isnan(fl) | ~np.isnan(ab)
        flz, abz = np.nan_to_num(fl, nan=-999), np.nan_to_num(ab, nan=-999)
        h = _fraccion((flz - mf >= P["hombro_flexion"]) | (abz - ma >= P["hombro_abduccion"]),
                      (flz + mf >= P["hombro_flexion"]) | (abz + ma >= P["hombro_abduccion"]), med_h)
        coz = np.nan_to_num(co, nan=-999)
        c = _fraccion(coz - mc >= P["codo_flexion"], coz + mc >= P["codo_flexion"], ~np.isnan(co))
        muz = np.nan_to_num(mu, nan=-999)
        m = _fraccion(muz - mm >= P["muneca_flexion"], muz + mm >= P["muneca_flexion"], ~np.isnan(mu))
        out[LADO[lado]] = dict(hombro=h, codo=c, muneca=m)
    return out


def postura_como_entrada(fr: dict) -> dict:
    """Fracción medida → valor de entrada de ocra (rango). Con poca cobertura se recorre entero."""
    if fr["cobertura"] < COBERTURA_POSTURA:
        return dict(valor=None, origen="desconocido", nota=f"medido solo el {fr['cobertura']:.0f} % del tiempo")
    a, b = round(fr["min"], 3), round(fr["max"], 3)
    return dict(valor=a if a == b else [a, b], origen="medido",
                nota=f"MediaPipe, cobertura {fr['cobertura']:.0f} %, con margen de medida")


# ------------------------------------------------------------------ (c) candidatos a acción técnica

def candidatos_at(pose, res: dict, inicio: float | None = None, fin: float | None = None,
                  separacion_s: float = 0.4) -> dict:
    """Instantes en que la mano se para o cambia bruscamente de velocidad (orientan la revisión; no son AT)."""
    t = pose.times
    out = {}
    escala = res.get("escala_px")
    for lado, idx in (("I", 15), ("D", 16)):
        xy = np.stack([pose.lm[:, idx, 0] * pose.width, pose.lm[:, idx, 1] * pose.height], axis=1)
        vis = np.nan_to_num(pose.lm[:, idx, 3], nan=0.0)
        xy[vis < 0.5] = np.nan
        v = np.full(len(t), np.nan)
        v[1:] = np.linalg.norm(np.diff(xy, axis=0), axis=1) / np.maximum(np.diff(t), 1e-6)
        if escala is not None:
            v = v / np.where(np.isnan(escala) | (escala <= 0), np.nan, escala)
        ok = ~np.isnan(v)
        cand = []
        if ok.sum() > 5:
            vm = np.nanmedian(v)
            for k in range(1, len(t) - 1):
                if not (ok[k - 1] and ok[k] and ok[k + 1]):
                    continue
                if inicio is not None and t[k] < inicio or fin is not None and t[k] > fin:
                    continue
                parada = v[k] <= v[k - 1] and v[k] <= v[k + 1] and v[k] < 0.35 * vm
                cambio = abs(v[k + 1] - v[k - 1]) > 2.5 * vm
                if (parada or cambio) and (not cand or t[k] - cand[-1]["t"] >= separacion_s):
                    cand.append(dict(t=round(float(t[k]), 2), tipo="parada" if parada else "cambio de velocidad"))
        out[LADO[lado]] = cand
    return out


def actividad_manos(pose) -> dict:
    """Recorrido de cada muñeca (px normalizados) y profundidad mediana (z menor = más cerca de la cámara)."""
    out = {}
    for lado, idx in (("I", 15), ("D", 16)):
        xy = pose.lm[:, idx, :2].copy()
        vis = np.nan_to_num(pose.lm[:, idx, 3], nan=0.0)
        xy[vis < 0.5] = np.nan
        d = np.linalg.norm(np.diff(xy, axis=0), axis=1)
        z = pose.lm[:, idx, 2]
        out[LADO[lado]] = dict(recorrido=float(np.nansum(d)), visible=float(100 * np.mean(vis >= 0.5)),
                               z=float(np.nanmedian(z)) if np.any(~np.isnan(z)) else None)
    return out


# ------------------------------------------------------------------ validez del vídeo para OCRA

def validar(info: dict, pose=None, res: dict | None = None, ficha: dict | None = None,
            ciclo_declarado: float | None = None) -> dict:
    """¿Sirve el vídeo para OCRA? Devuelve nivel (verde/ambar/rojo), motivos, cómo mejorar y lo que aporta MediaPipe."""
    motivos, mejorar, niveles = [], [], []
    dur = info.get("duracion") or (pose.duracion if pose is not None else 0)
    ciclo, fuente_ciclo, per = None, None, None
    if ficha and (ficha.get("ciclo") or {}).get("fin") is not None:
        c = ficha["ciclo"]
        ciclo, fuente_ciclo = float(c["fin"]) - float(c.get("inicio", 0)), "revisión visual"
    elif ciclo_declarado:
        ciclo, fuente_ciclo = float(ciclo_declarado), "declarado"
    if res is not None:
        per = ciclo_periodicidad(res, dur)
        if ciclo is None and per["ciclo_s"] and per.get("fiable"):
            ciclo, fuente_ciclo = per["ciclo_s"], "periodicidad (MediaPipe)"
    if ciclo:
        n = dur / ciclo
        if n >= CICLOS_MINIMOS:
            niveles.append("verde")
        elif n >= 2:
            niveles.append("ambar")
            motivos.append(f"Solo {n:.1f} ciclos completos (ciclo de {ciclo:.1f} s, {fuente_ciclo}): OCRA pide al menos 3.")
        else:
            niveles.append("rojo")
            motivos.append(f"Menos de 2 ciclos ({n:.1f}; ciclo de {ciclo:.1f} s): no se puede elegir un ciclo representativo.")
        if n < CICLOS_MINIMOS:
            mejorar.append(f"Graba al menos {CICLOS_MINIMOS} ciclos completos seguidos ({math.ceil(CICLOS_MINIMOS * ciclo)} s o más).")
    else:
        niveles.append("ambar")
        motivos.append("No se ha podido determinar el tiempo de ciclo: decláralo o márcalo en la revisión.")
    fps = info.get("fps") or (pose.fps_video if pose is not None else None)
    if fps:
        if fps >= FPS_RECOMENDADO - 0.5:
            niveles.append("verde")
        elif fps >= FPS_MINIMO:
            niveles.append("ambar")
            motivos.append(f"{fps:.0f} fps: los gestos rápidos pueden perderse (se recomiendan ≥ 25 fps).")
            mejorar.append("Graba a 25 fps o más (mejor 50–60 fps para ver los gestos a cámara lenta).")
        else:
            niveles.append("rojo")
            motivos.append(f"{fps:.0f} fps: demasiado pocos fotogramas para contar acciones técnicas.")
            mejorar.append("Graba a 25 fps o más.")
    act = None
    if pose is not None and pose.detectado.mean() > 0:
        act = actividad_manos(pose)
        activa = max(act, key=lambda m: act[m]["recorrido"])
        otra = "izq" if activa == "dch" else "dch"
        nombre = {"dch": "derecha", "izq": "izquierda"}
        if act[activa]["visible"] < MANOS_VISIBLES:
            niveles.append("ambar")
            motivos.append(f"La mano {nombre[activa]} (la más activa) solo se ve el {act[activa]['visible']:.0f} % del tiempo.")
            mejorar.append(f"Coloca la cámara del lado de la mano {nombre[activa]} y sin obstáculos entre la cámara y las manos.")
        za, zo = act[activa]["z"], act[otra]["z"]
        if za is not None and zo is not None and za > zo + 0.05:
            niveles.append("ambar")
            motivos.append(f"La mano más activa ({nombre[activa]}) queda en el lado lejano de la cámara.")
            mejorar.append(f"Graba desde el lado de la mano {nombre[activa]}.")
        if act[otra]["visible"] < 40:
            motivos.append(f"La mano {nombre[otra]} apenas se ve: su recuento de AT dependerá de la revisión o saldrá como rango.")
    elif pose is None or pose.detectado.mean() == 0:
        motivos.append("MediaPipe no detecta a la persona (p. ej., plano cerrado de manos): se sigue por la vía "
                       "observacional; la postura se declara o sale como rango.")
    if ficha and ficha.get("manos_visibles") is False:
        niveles.append("rojo")
        motivos.append("La revisión indica que las manos o los objetos no se ven en las operaciones.")
        mejorar.append("Encuadra las manos y los objetos que manipulan; acerca la cámara si hace falta.")
    nivel = "rojo" if "rojo" in niveles else "ambar" if "ambar" in niveles else "verde"
    return dict(nivel=nivel, motivos=motivos, como_mejorar=mejorar, ciclo_s=ciclo, ciclo_fuente=fuente_ciclo,
                periodicidad=per, manos=act)


# ------------------------------------------------------------------ láminas del ciclo para contar AT

def laminas_ciclo(video: str | Path, salida: Path, inicio: float, fin: float, fps: float = 6.0,
                  columnas: int = 4, filas: int = 3, ancho: int = 400, pose=None, candidatos: dict | None = None) -> list[Path]:
    """Láminas JPG del ciclo representativo a `fps` fotogramas por segundo (4–8), con el tiempo impreso y la cara
    difuminada si MediaPipe la ve. Los candidatos a AT (si los hay) se marcan con un punto en la esquina."""
    import cv2
    from .visual import _difuminar_cara
    salida.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    fps_v = cap.get(cv2.CAP_PROP_FPS) or 25.0
    tiempos = np.arange(inicio, fin + 1e-6, 1.0 / fps)
    cand_t = sorted({c["t"] for cs in (candidatos or {}).values() for c in cs})
    imgs = []
    for t in tiempos:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps_v)))
        ok, img = cap.read()
        if not ok:
            continue
        if pose is not None:
            k = int(np.argmin(np.abs(pose.times - t)))
            if not np.isnan(pose.lm[k, 0, 0]):
                _difuminar_cara(img, pose.lm[k], img.shape[1], img.shape[0])
        alto = int(img.shape[0] * ancho / img.shape[1])
        im = cv2.resize(img, (ancho, alto))
        cv2.rectangle(im, (0, 0), (118, 30), (0, 0, 0), -1)
        cv2.putText(im, f"{t:.2f} s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        if any(abs(t - c) <= 0.5 / fps for c in cand_t):
            cv2.circle(im, (ancho - 16, 16), 9, (0, 200, 255), -1, cv2.LINE_AA)
        imgs.append(im)
    cap.release()
    rutas = []
    por = columnas * filas
    for i in range(0, len(imgs), por):
        bloque = imgs[i:i + por]
        h, w = bloque[0].shape[:2]
        lam = np.full((filas * (h + 4), columnas * (w + 4), 3), 40, np.uint8)
        for j, im in enumerate(bloque):
            r, c = divmod(j, columnas)
            lam[r * (h + 4):r * (h + 4) + h, c * (w + 4):c * (w + 4) + w] = im
        lam = lam[: (math.ceil(len(bloque) / columnas)) * (h + 4)]
        ruta = salida / f"ocra_ciclo_{i // por + 1:02d}.jpg"
        cv2.imwrite(str(ruta), lam, [cv2.IMWRITE_JPEG_QUALITY, 85])
        rutas.append(ruta)
    return rutas


def captura_instante(video: str | Path, t: float, ruta: Path, texto: str, pose=None, ancho: int = 480) -> Path | None:
    """Fotograma de un instante clave del ciclo (cara difuminada si MediaPipe la ve) con un rótulo."""
    import cv2
    from .visual import _difuminar_cara
    cap = cv2.VideoCapture(str(video))
    fps_v = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps_v)))
    ok, img = cap.read()
    cap.release()
    if not ok:
        return None
    if pose is not None:
        k = int(np.argmin(np.abs(pose.times - t)))
        if not np.isnan(pose.lm[k, 0, 0]):
            _difuminar_cara(img, pose.lm[k], img.shape[1], img.shape[0])
    alto = int(img.shape[0] * ancho / img.shape[1])
    im = cv2.resize(img, (ancho, alto))
    cv2.rectangle(im, (0, alto - 30), (ancho, alto), (0, 0, 0), -1)
    import unicodedata
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()  # OpenCV no pinta tildes
    cv2.putText(im, texto[:60], (8, alto - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(ruta), im, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return ruta
