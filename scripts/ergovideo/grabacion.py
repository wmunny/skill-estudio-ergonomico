"""Diagnóstico de cada vídeo y recomendaciones de grabación.

Base de las recomendaciones:
- Aghazadeh y Xiong (KAIST), preprint SSRN 6035502 (2025, sin revisión por pares): MediaPipe supera a MMPose frente a
  captura óptica de movimiento (ICC REBA 0,87; RULA 0,92). Error angular medio por vista: frontal 18,4°, 45° 14,7°,
  lateral 13,5°; la vista frontal es la peor para los ángulos y la de 45° el mejor compromiso para MediaPipe. La tarea
  con obstáculo delante dio el mayor error (29,8°): la oclusión es la principal fuente de error.
- Hallazgos de la PoC postura-poc: MediaPipe se inventa las articulaciones tapadas; elegir 2D o 3D según la vista;
  calcular con el lado visible; el % de tiempo de OWAS necesita grabaciones largas.
"""

from __future__ import annotations

import numpy as np

GENERALES = [
    "Cámara fija (trípode) y nivelada, a la altura de la cadera o el pecho: la vertical de la imagen se toma como vertical real.",
    "Colócala a unos 45° entre el frente y el lateral del trabajador, del lado de la mano que más trabaja. Con MediaPipe es el "
    "mejor compromiso (error angular medio 14,7° frente a 18,4° de frente y 13,5° de lado; Aghazadeh y Xiong, 2025, preprint).",
    "Evita la vista frontal pura para medir la flexión del tronco y de las rodillas: es la que más error angular da.",
    "Que no haya mesas, máquinas ni la propia carga entre la cámara y el trabajador: trabajar tras un obstáculo duplicó el error "
    "en el mismo estudio (29,8°).",
    "Encuadra el cuerpo entero, de la cabeza a los pies, durante todo el ciclo; deja margen para los desplazamientos.",
    "Resolución mínima 1280×720 (mejor 1920×1080) y la persona ocupando al menos la mitad de la altura de la imagen.",
    "Si un brazo queda tapado por el torso, añade una segunda cámara en el otro lado, sincronizada (modo «mejor-camara»).",
    "Graba varios ciclos completos: OWAS pide 20–40 min de observación y unas 100 observaciones independientes para un "
    "error del 10 %.",
    "Informa al trabajador y obtén su consentimiento; el informe difumina la cara, pero el vídeo original no.",
]


def diagnostico(pose, res: dict, umbral_vis: float = 0.5) -> dict:
    """Calidad de un vídeo para OWAS: detección, punto de vista, tamaño de la persona y cobertura por región."""
    det = res["detectado"]
    vis = res["visibilidad"]
    vista = res["vista"][det]
    lm = pose.lm
    altura = []
    for k in np.flatnonzero(det):
        ys = lm[k, [0, 27, 28, 29, 30], 1]
        altura.append(np.nanmax(ys) - np.nanmin(ys))
    # De espaldas: el hombro izquierdo del trabajador aparece a la izquierda de la imagen (de frente sale a la derecha).
    # No se usa la visibilidad de la nariz: MediaPipe la da alta aunque la cara no se vea.
    ancho_h = (lm[:, 11, 0] - lm[:, 12, 0]) * pose.width
    tronco = np.hypot((lm[:, 11, 0] - lm[:, 23, 0]) * pose.width, (lm[:, 11, 1] - lm[:, 23, 1]) * pose.height)
    espaldas = det & (np.nan_to_num(ancho_h) < -0.25 * np.nan_to_num(tronco, nan=1.0))
    modo = res["modo"][det]
    s = res["series"]
    cob = lambda k: float(100 * np.mean(~np.isnan(s[k]))) if len(s[k]) else 0.0  # noqa: E731
    d = dict(
        video=pose.video, duracion_s=pose.duracion, ancho=pose.width, alto=pose.height, fps_video=pose.fps_video,
        fps_analisis=1 / float(np.median(np.diff(pose.times))) if len(pose.times) > 1 else 0, fotogramas=len(pose.times),
        modelo=pose.modelo,
        deteccion=float(100 * det.mean()),
        vista_frontal=float(100 * np.mean(vista < 25)) if len(vista) else 0.0,
        vista_45=float(100 * np.mean((vista >= 25) & (vista <= 65))) if len(vista) else 0.0,
        vista_lateral=float(100 * np.mean(vista > 65)) if len(vista) else 0.0,
        vista_mediana=float(np.median(vista)) if len(vista) else float("nan"),
        de_espaldas=float(100 * espaldas.sum() / max(1, det.sum())),
        modo_2d=float(100 * np.mean(modo == "2d")) if len(modo) else 0.0,
        altura_persona=float(100 * np.median(altura)) if altura else 0.0,
        cobertura={k: cob(k) for k in s},
        razones=res["razones"],
    )
    d["consejos"] = consejos(d)
    return d


def consejos(d: dict) -> list[str]:
    c = []
    cob = d["cobertura"]
    if d["deteccion"] < 90:
        c.append(f"La persona solo se detecta en el {d['deteccion']:.0f} % de los fotogramas: revisa el encuadre, la luz y que no "
                 "salga del plano.")
    if d["vista_frontal"] > 50:
        c.append(f"El trabajador está de frente o de espaldas a la cámara el {d['vista_frontal']:.0f} % del tiempo: es la vista con "
                 "más error angular para MediaPipe. Gira la cámara unos 45°.")
    if d["de_espaldas"] > 30:
        c.append(f"Está de espaldas el {d['de_espaldas']:.0f} % del tiempo: los brazos quedan tapados por el torso. Cambia la cámara "
                 "de lado o añade una segunda.")
    if d["alto"] < 720:
        c.append(f"Resolución baja ({d['ancho']}×{d['alto']}): graba al menos a 1280×720.")
    if 0 < d["altura_persona"] < 45:
        c.append(f"La persona ocupa solo el {d['altura_persona']:.0f} % de la altura de la imagen: acerca la cámara o usa más zoom "
                 "sin cortar los pies.")
    for s, lado, otro in (("I", "izquierdo", "izquierdo"), ("D", "derecho", "derecho")):
        if cob.get(f"brazo_alt_{s}", 100) < 60:
            c.append(f"El brazo {lado} se ve solo en el {cob[f'brazo_alt_{s}']:.0f} % del vídeo: pon la cámara (o una segunda) en el "
                     f"lado {otro} del trabajador.")
    if min(cob.get("rodilla_I", 100), cob.get("rodilla_D", 100)) < 60:
        c.append("Las piernas se ven poco: encuadra los pies y quita obstáculos (mesas, cajas) entre la cámara y el trabajador.")
    if cob.get("tronco_giro", 100) < 50:
        c.append(f"La torsión del tronco solo se puede medir en el {cob['tronco_giro']:.0f} % del vídeo (necesita ver los dos hombros "
                 "y las dos caderas): la espalda «con giro» puede estar infravalorada.")
    return c
