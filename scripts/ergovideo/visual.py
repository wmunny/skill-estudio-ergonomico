"""Vídeo y capturas con el esqueleto superpuesto, y gráficos del estudio."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .config import CARA, ESQUELETO

COLOR_CAT = {None: (150, 150, 150), 1: (80, 175, 76), 2: (40, 200, 240), 3: (0, 140, 255), 4: (50, 50, 220)}  # BGR
COLOR_CAT_HEX = {1: "#4caf50", 2: "#f0c828", 3: "#ff8c00", 4: "#dc3232"}


def ffmpeg() -> str | None:
    ruta = os.environ.get("FFMPEG_PATH")
    if ruta and Path(ruta).exists():
        return ruta
    return shutil.which("ffmpeg")


def _difuminar_cara(img: np.ndarray, lm: np.ndarray, w: int, h: int) -> None:
    pts = lm[CARA, :2]
    if np.isnan(pts).any():
        return
    xs, ys = pts[:, 0] * w, pts[:, 1] * h
    hombros = np.linalg.norm((lm[11, :2] - lm[12, :2]) * [w, h]) if not np.isnan(lm[11, 0]) else 0
    r = max(xs.max() - xs.min(), ys.max() - ys.min(), 0.45 * hombros, 12) * 0.9
    cx, cy = xs.mean(), ys.mean()
    x0, x1 = int(max(0, cx - r)), int(min(w, cx + r))
    y0, y1 = int(max(0, cy - 1.2 * r)), int(min(h, cy + r))
    if x1 - x0 > 2 and y1 - y0 > 2:
        roi = img[y0:y1, x0:x1]
        k = max(15, (min(roi.shape[:2]) // 2) * 2 + 1)
        img[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)


def dibujar(img: np.ndarray, lm: np.ndarray, usable: np.ndarray, invalido: np.ndarray, vis_min: float,
            difuminar: bool = True) -> None:
    h, w = img.shape[:2]
    if np.isnan(lm[0, 0]):
        return
    if difuminar:
        _difuminar_cara(img, lm, w, h)
    grosor = max(2, w // 400)
    P = lambda i: (int(lm[i, 0] * w), int(lm[i, 1] * h))  # noqa: E731
    for a, b in ESQUELETO:
        if lm[a, 3] >= vis_min and lm[b, 3] >= vis_min:
            col = (0, 230, 0) if usable[a] and usable[b] else (0, 0, 230)
            cv2.line(img, P(a), P(b), col, grosor, cv2.LINE_AA)
        else:
            cv2.line(img, P(a), P(b), (160, 160, 160), 1, cv2.LINE_AA)
    for i in range(11, 29):
        if invalido[i]:
            x, y = P(i)
            d = grosor * 3
            cv2.line(img, (x - d, y - d), (x + d, y + d), (0, 0, 255), grosor)
            cv2.line(img, (x - d, y + d), (x + d, y - d), (0, 0, 255), grosor)
        elif lm[i, 3] >= vis_min:
            cv2.circle(img, P(i), grosor * 2, (255, 255, 255), -1, cv2.LINE_AA)
        else:
            cv2.circle(img, P(i), grosor * 2, (160, 160, 160), 1, cv2.LINE_AA)


def rotulo(img: np.ndarray, lineas: list[str], categoria: int | None) -> None:
    h, w = img.shape[:2]
    esc = max(0.45, w / 1600)
    alto = int(26 * esc * 1.6) * len(lineas) + 10
    cv2.rectangle(img, (0, 0), (w, alto), (0, 0, 0), -1)
    cv2.rectangle(img, (0, 0), (12, alto), COLOR_CAT[categoria], -1)
    for k, t in enumerate(lineas):
        cv2.putText(img, t, (20, int((k + 1) * 26 * esc * 1.6)), cv2.FONT_HERSHEY_SIMPLEX, esc, (255, 255, 255),
                    max(1, int(esc * 2)), cv2.LINE_AA)


def _texto_obs(o: dict | None, t: float) -> tuple[list[str], int | None]:
    if o is None:
        return [f"t = {t:6.1f} s"], None
    cod = "".join(str(o[r]) if o[r] is not None else "?" for r in ("espalda", "brazos", "piernas", "carga"))
    cat = o["categoria"]
    l1 = f"t = {t:6.1f} s   OWAS {cod}   categoria {cat if cat else '-'}"
    l2 = f"vista {o['vista']:.0f} deg ({o['modo']})" if o.get("vista") == o.get("vista") else ""
    return [l1, l2 + "   DEMOSTRACION NO VALIDADA"], cat


def _texto_ergo(f: dict | None) -> str:
    if not f:
        return ""
    def r(d):
        if not d:
            return "-"
        a, b = d["rango"]
        return f"{a}" if a == b else f"{a}-{b}"
    partes = []
    if f.get("reba") is not None:
        partes.append(f"REBA {r(f['reba'])}")
    if f.get("rula"):
        partes.append(f"RULA izq {r(f['rula'].get('I'))} dch {r(f['rula'].get('D'))}")
    return "   ".join(partes)


def video_esqueleto(pose, res: dict, obs: list[dict], nombre: str, salida: Path, vis_min: float, difuminar: bool = True,
                    ancho_max: int = 1280, ergo_fs: list | None = None) -> Path:
    """Vídeo a la frecuencia de análisis con el esqueleto, la cara difuminada y el código OWAS más cercano."""
    cap = cv2.VideoCapture(pose.video)
    escala = min(1.0, ancho_max / pose.width)
    w, h = int(pose.width * escala) // 2 * 2, int(pose.height * escala) // 2 * 2
    fps = 1 / float(np.median(np.diff(pose.times))) if len(pose.times) > 1 else 10
    tmp = salida.with_suffix(".tmp.mp4")
    out = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    obs = [o for o in obs if nombre in o["t_video"]]
    t_obs = np.array([o["t_video"][nombre] for o in obs]) if obs else np.array([])
    objetivo = {int(f): k for k, f in enumerate(pose.frames)}
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i in objetivo:
            ok, img = cap.retrieve()
            if not ok:
                break
            k = objetivo[i]
            dibujar(img, pose.lm[k], res["usable"][k], res["invalidos"][k] != "", vis_min, difuminar)
            img = cv2.resize(img, (w, h)) if escala < 1 else img[:h, :w]
            o = obs[int(np.argmin(np.abs(t_obs - pose.times[k])))] if len(t_obs) else None
            lineas, cat = _texto_obs(o, pose.times[k])
            if ergo_fs:
                lineas[0] += "   " + _texto_ergo(ergo_fs[k])
            rotulo(img, lineas, cat)
            out.write(img)
        i += 1
    cap.release()
    out.release()
    exe = ffmpeg()
    if exe:
        r = subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(tmp), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-crf", "23", "-movflags", "+faststart", str(salida)], capture_output=True)
        if r.returncode == 0:
            tmp.unlink(missing_ok=True)
            return salida
    tmp.replace(salida)
    return salida


def captura(pose, res: dict, k: int, o: dict | None, ruta: Path, vis_min: float, difuminar: bool = True) -> Path:
    lineas, cat = _texto_obs(o, pose.times[k])
    return captura_lineas(pose, res, k, lineas, cat, ruta, vis_min, difuminar)


def captura_lineas(pose, res: dict, k: int, lineas: list[str], cat: int | None, ruta: Path, vis_min: float,
                   difuminar: bool = True) -> Path:
    cap = cv2.VideoCapture(pose.video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(pose.frames[k]))
    ok, img = cap.read()
    cap.release()
    if not ok:
        img = np.zeros((pose.height, pose.width, 3), np.uint8)
    dibujar(img, pose.lm[k], res["usable"][k], res["invalidos"][k] != "", vis_min, difuminar)
    rotulo(img, lineas, cat)
    if img.shape[1] > 1280:
        img = cv2.resize(img, (1280, int(img.shape[0] * 1280 / img.shape[1])))
    cv2.imwrite(str(ruta), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return ruta


# ---------------------------------------------------------------- gráficos

def graficos(obs: list[dict], resumen: dict, fuentes: list[dict], dir_salida: Path, umbrales) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rutas = {}
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

    # 1. % del tiempo por código con su IC 95 %
    from .tablas import BRAZOS, ESPALDA, PIERNAS
    filas = [(reg, c, nom) for reg, d in (("espalda", ESPALDA), ("brazos", BRAZOS), ("piernas", PIERNAS)) for c, nom in d.items()]
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(filas) + 1))
    for y, (reg, c, nom) in enumerate(filas):
        d = resumen["regiones"][reg]["codigos"][c]
        cat = d["categoria"] or 1
        ax.barh(y, d["porcentaje"], color=COLOR_CAT_HEX[cat], height=0.7)
        lo, hi = d["ic_aprox"]
        ax.plot([lo, hi], [y, y], color="#333", lw=1)
        ax.text(min(hi, 100) + 1, y, f"{d['porcentaje']:.0f} %", va="center", fontsize=8)
    ax.set_yticks(range(len(filas)), [f"{reg[:3].capitalize()} {c} · {nom[:38]}" for reg, c, nom in filas], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 110)
    ax.set_xlabel("% nominal del tiempo observable (barra: intervalo aproximado; no es un IC 95 % verificado)")
    ax.set_title("Frecuencia de cada código OWAS · color = categoría de acción por frecuencia", fontsize=10)
    fig.tight_layout()
    rutas["porcentajes"] = dir_salida / "porcentajes.png"
    fig.savefig(rutas["porcentajes"], dpi=130)
    plt.close(fig)

    # 2. Cronograma por vídeo: medidas y códigos
    for f in fuentes:
        mis = [o for o in obs if f["nombre"] in o["indice"]]
        if not mis:
            continue
        res = f["res"]
        fig, axs = plt.subplots(5, 1, figsize=(10, 7), sharex=True, gridspec_kw=dict(height_ratios=[2.2, 1.6, 1, 1, 1]))
        t = res["t"]
        s = res["series"]
        axs[0].plot(t, res["crudas"]["tronco_flex"], color="#bbb", lw=0.8, label="tronco (sin filtrar)")
        axs[0].plot(t, s["tronco_flex"], color="#1f5fa8", lw=1.3, label="flexión del tronco")
        axs[0].plot(t, s["tronco_giro"], color="#8e44ad", lw=0.9, label="torsión")
        axs[0].axhline(umbrales.espalda_flexion, color="#1f5fa8", ls=":", lw=0.8)
        axs[0].set_ylabel("grados")
        axs[0].legend(fontsize=7, ncol=3, loc="upper right")
        axs[1].plot(t, s["brazo_alt_I"], color="#c0392b", lw=1, label="brazo izq.")
        axs[1].plot(t, s["brazo_alt_D"], color="#16a085", lw=1, label="brazo dch.")
        axs[1].axhline(umbrales.brazo_margen, color="#555", ls=":", lw=0.8)
        axs[1].set_ylabel("sobre hombro\n(troncos)")
        axs[1].legend(fontsize=7, ncol=2, loc="upper right")
        to = [o["t_video"][f["nombre"]] for o in mis]
        for ax, reg, top in ((axs[2], "espalda", 4), (axs[3], "brazos", 3), (axs[4], "piernas", 7)):
            vals = [o[reg] if o[reg] is not None else np.nan for o in mis]
            cols = [COLOR_CAT_HEX.get(o["categoria"], "#bbb") for o in mis]
            ax.scatter(to, vals, c=cols, s=10, marker="s")
            ax.set_ylim(0.5, top + 0.5)
            ax.set_yticks(range(1, top + 1))
            ax.set_ylabel(reg)
        axs[4].set_xlabel("tiempo del vídeo (s) · color = categoría de la combinación")
        axs[0].set_title(f"{f['nombre']}: medidas filtradas y códigos OWAS por observación", fontsize=10)
        fig.tight_layout()
        ruta = dir_salida / f"cronograma_{_seguro(f['nombre'])}.png"
        fig.savefig(ruta, dpi=120)
        plt.close(fig)
        rutas[f"cronograma_{f['nombre']}"] = ruta
    return rutas


def _seguro(nombre: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(nombre).stem)
