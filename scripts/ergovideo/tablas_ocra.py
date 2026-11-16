"""Constantes del índice OCRA (todas en un único sitio, con su fuente).

Fuentes de las tablas clásicas:
- Occhipinti E. (1998). OCRA: a concise index for the assessment of exposure to repetitive movements of the upper
  limbs. Ergonomics 41(9):1290-1311. Colombini D., Occhipinti E., Grieco A. (2002). Risk assessment and management of
  repetitive movements and exertions of upper limbs. Elsevier.
- ISO 11228-3:2007, anexo C (índice OCRA), y UNE-EN 1005-5:2007 (misma estructura de multiplicadores).
- INSST: materiales divulgativos sobre movimientos repetitivos (criterios de acción técnica).

AVISO NORMATIVO. ISO 11228-3:2026 se publicó el 8 de mayo de 2026 y sustituye a la edición de 2007. Estas tablas son
las CLÁSICAS (edición de 2007 y bibliografía de Colombini y Occhipinti). No se ha comprobado su conformidad con la
edición de 2026. Cada constante lleva `verificar_iso_2026 = True` hasta que un experto la contraste. La herramienta
NO afirma conformidad con ISO 11228-3:2026.

Todas las funciones son puras y deterministas: las puntuaciones se calculan aquí, nunca con el modelo de lenguaje.
"""

from __future__ import annotations

import math

EDICION_TABLAS = "clásicas (ISO 11228-3:2007, anexo C; Colombini y Occhipinti)"
AVISO_NORMATIVO = ("Tablas clásicas de OCRA (ISO 11228-3:2007, anexo C, y Colombini y Occhipinti). ISO 11228-3:2026 "
                   "(publicada el 08/05/2026) sustituye a la edición de 2007: no se ha verificado la conformidad con ella.")

# Cada entrada: valor, fuente y si hay que contrastarla con ISO 11228-3:2026.
FUENTES = {
    "frecuencia_referencia": dict(fuente="ISO 11228-3:2007 C; Occhipinti (1998): CF = 30 acciones/min",
                                  verificar_iso_2026=True),
    "fom_borg": dict(fuente="ISO 11228-3:2007 C (tabla del multiplicador de fuerza por Borg CR-10); Colombini et al. (2002)",
                     verificar_iso_2026=True),
    "pom_fraccion": dict(fuente="ISO 11228-3:2007 C.2: PoM = 1 si la postura forzada ocupa < 1/3 del ciclo; se toma el "
                                "multiplicador más bajo. Escalones superiores pendientes de contraste celda a celda",
                         verificar_iso_2026=True),
    "posturas_forzadas": dict(fuente="Criterios de ISO 11228-3:2007 / UNE-EN 1005-5 para hombro y muñeca; el del codo es "
                                     "una aproximación propia (la pronosupinación no se mide con MediaPipe)",
                              verificar_iso_2026=True),
    "rem": dict(fuente="Criterio de estereotipia indicado en el encargo (ciclo < 15 s o la misma acción > 50 % del ciclo "
                       "→ 0,70). Otras versiones lo gradúan (0,85 / 0,70): ver docs/REVISION_METODOS.md",
                verificar_iso_2026=True),
    "adm": dict(fuente="Colombini et al. (2002) / ISO 11228-3:2007 C: factores adicionales por fracción del ciclo",
                verificar_iso_2026=True),
    "rcm_horas": dict(fuente="ISO 11228-3:2007 C; Colombini et al. (2002): horas sin recuperación adecuada → RcM",
                      verificar_iso_2026=True),
    "recuperacion": dict(fuente="Colombini et al. (2002): proporción trabajo/recuperación 5:1 (50 min / 10 min); la "
                                "hora previa a la comida y al final del turno cuentan como recuperadas",
                         verificar_iso_2026=True),
    "dum": dict(fuente="ISO 11228-3:2007 C (versión de 4 tramos del encargo; existen versiones con más tramos)",
                verificar_iso_2026=True),
    "clasificacion": dict(fuente="ISO 11228-3:2007 C (3 bandas) y Colombini y Occhipinti (5 bandas)",
                          verificar_iso_2026=True),
}

# ------------------------------------------------------------------ frecuencia de referencia
FRECUENCIA_REFERENCIA = 30.0  # acciones técnicas por minuto (CF)

# ------------------------------------------------------------------ FoM: Borg CR-10 → multiplicador
FOM_BORG = [(0.5, 1.0), (1.0, 0.85), (1.5, 0.75), (2.0, 0.65), (2.5, 0.55), (3.0, 0.45), (3.5, 0.35),
            (4.0, 0.20), (4.5, 0.10), (5.0, 0.01)]
INTERPOLAR_FOM = False  # el método clásico da escalones; sin interpolar se usa el escalón conservador


def fom(borg: float) -> dict:
    """Multiplicador de fuerza para un Borg CR-10 medio ponderado.

    Sin interpolación: el valor nominal es el escalón conservador (el Borg se redondea al escalón superior de 0,5, que da
    el multiplicador más bajo) y `alternativa` es el escalón inferior, para la sensibilidad.
    """
    if borg is None or borg < 0:
        raise ValueError("Borg CR-10 debe ser ≥ 0")
    if borg <= FOM_BORG[0][0]:
        return dict(nominal=1.0, alternativa=1.0, borg_escalon=FOM_BORG[0][0])
    if borg >= FOM_BORG[-1][0]:
        return dict(nominal=FOM_BORG[-1][1], alternativa=FOM_BORG[-1][1], borg_escalon=FOM_BORG[-1][0])
    for (b0, f0), (b1, f1) in zip(FOM_BORG, FOM_BORG[1:]):
        if abs(borg - b0) < 1e-9:
            return dict(nominal=f0, alternativa=f0, borg_escalon=b0)
        if b0 < borg < b1:
            if INTERPOLAR_FOM:
                f = f0 + (f1 - f0) * (borg - b0) / (b1 - b0)
                return dict(nominal=round(f, 4), alternativa=f1, borg_escalon=borg)
            return dict(nominal=f1, alternativa=f0, borg_escalon=b1)
    return dict(nominal=FOM_BORG[-1][1], alternativa=FOM_BORG[-1][1], borg_escalon=FOM_BORG[-1][0])  # pragma: no cover


FOM_MIN, FOM_MAX = FOM_BORG[-1][1], FOM_BORG[0][1]

# ------------------------------------------------------------------ PoM: fracción del ciclo en postura forzada
# (límite inferior de la fracción, multiplicador). La fracción se compara con ≥ límite.
POM_FRACCION = [(0.0, 1.0), (1 / 3, 0.70), (2 / 3, 0.60), (0.9, 0.50)]
ARTICULACIONES = ("hombro", "codo", "muneca", "agarre")

# Posturas forzadas que se pueden medir con MediaPipe (grados). Criterios del método salvo el codo.
POSTURA_FORZADA = dict(
    hombro_flexion=80.0,      # brazo flexionado ≥ 80° (a la altura del hombro o más)
    hombro_abduccion=45.0,    # brazo separado ≥ 45°
    codo_flexion=100.0,       # aproximación propia: codo muy cerrado (la pronosupinación no se mide)
    muneca_flexion=45.0,      # flexión o extensión de la muñeca ≥ 45°
)


def pom_articulacion(fraccion: float) -> float:
    if fraccion is None or not (0 <= fraccion <= 1 + 1e-9):
        raise ValueError("la fracción del ciclo debe estar entre 0 y 1")
    m = 1.0
    for lim, val in POM_FRACCION:
        if fraccion >= lim - 1e-12:
            m = val
    return m


POM_MIN = min(v for _, v in POM_FRACCION)

# ------------------------------------------------------------------ ReM: estereotipia
REM_CICLO_S = 15.0           # ciclo más corto → estereotipia
REM_MISMA_ACCION = 0.50      # la misma acción más de esta fracción del ciclo → estereotipia
REM_VALOR = 0.70


def rem(ciclo_s: float | None, misma_accion: float | None) -> float:
    if ciclo_s is not None and ciclo_s < REM_CICLO_S:
        return REM_VALOR
    if misma_accion is not None and misma_accion > REM_MISMA_ACCION:
        return REM_VALOR
    return 1.0


# ------------------------------------------------------------------ AdM: factores adicionales
ADM_FRACCION = [(0.0, 1.0), (0.25, 0.95), (0.51, 0.90), (0.80, 0.80)]
FACTORES_ADICIONALES = {
    "guantes": "Guantes inadecuados que dificultan el agarre",
    "vibracion": "Herramientas que vibran",
    "precision": "Exigencia de precisión extrema",
    "golpes": "Golpes con la mano o con herramientas (martilleo, encajes a golpe)",
    "frio": "Exposición a frío o a superficies frías",
    "compresion": "Compresión localizada de la mano o el antebrazo",
    "contragolpe": "Contragolpes o tirones de la herramienta",
    "ritmo_maquina": "Ritmo impuesto por la máquina",
}


def adm_factor(fraccion: float) -> float:
    if fraccion is None or not (0 <= fraccion <= 1 + 1e-9):
        raise ValueError("la fracción del ciclo debe estar entre 0 y 1")
    m = 1.0
    for lim, val in ADM_FRACCION:
        if fraccion >= lim - 1e-12:
            m = val
    return m


ADM_MIN = min(v for _, v in ADM_FRACCION)

# ------------------------------------------------------------------ RcM: horas sin recuperación adecuada
RCM_HORAS = {0: 1.0, 1: 0.90, 2: 0.80, 3: 0.70, 4: 0.60, 5: 0.45, 6: 0.25, 7: 0.10, 8: 0.0}
PROPORCION_TRABAJO_RECUPERACION = 5.0   # 50 min de trabajo por 10 de recuperación
RECUPERACION_MINIMA_MIN = 8.0           # una pausa más corta no cuenta como recuperación


def rcm(horas: float) -> dict:
    """RcM para un número de horas sin recuperación (si no es entero, rango entre los dos escalones)."""
    if horas is None or horas < 0:
        raise ValueError("horas sin recuperación ≥ 0")
    h = min(horas, 8.0)
    lo_h, hi_h = math.floor(h + 1e-9), math.ceil(h - 1e-9)
    nominal_h = int(math.floor(h + 0.5))
    return dict(nominal=RCM_HORAS[nominal_h], min=RCM_HORAS[hi_h], max=RCM_HORAS[lo_h], horas=round(h, 2))


# ------------------------------------------------------------------ DuM: minutos netos repetitivos
DUM_TRAMOS = [(120.0, 2.0), (240.0, 1.5), (480.0, 1.0)]   # (límite superior excluyente/incluyente, valor)
DUM_MAS = 0.5


def dum(minutos: float) -> float:
    if minutos is None or minutos < 0:
        raise ValueError("minutos repetitivos ≥ 0")
    if minutos < 120:
        return 2.0
    if minutos < 240:
        return 1.5
    if minutos <= 480:
        return 1.0
    return DUM_MAS


# ------------------------------------------------------------------ clasificación del índice
# Bandas sobre el índice redondeado a una décima (así las tablas, que van de décima en décima, no dejan huecos).
CLASIFICACIONES = {
    "iso2007": dict(
        nombre="ISO 11228-3:2007 (3 bandas)",
        bandas=[(2.2, "verde", "Aceptable", "Sin riesgo o riesgo muy bajo: no requiere actuación."),
                (3.5, "amarillo", "Riesgo incierto o muy bajo", "Se recomienda mejorar el puesto, vigilar y formar."),
                (math.inf, "rojo", "No aceptable", "Riesgo presente: rediseñar el puesto o la tarea.")]),
    "colombini5": dict(
        nombre="Colombini y Occhipinti (5 bandas)",
        bandas=[(2.2, "verde", "Aceptable", "No requiere actuación."),
                (3.5, "amarillo", "Muy bajo o incierto", "Mejorar el puesto, vigilar y formar."),
                (4.5, "rojo_bajo", "Riesgo bajo", "Rediseñar el puesto y la tarea; vigilancia de la salud."),
                (9.0, "rojo", "Riesgo medio", "Rediseñar el puesto y la tarea con prioridad; vigilancia de la salud."),
                (math.inf, "morado", "Riesgo alto", "Actuar de inmediato: rediseño urgente; vigilancia de la salud.")]),
}
CLASIFICACION_DEFECTO = "iso2007"


def clasificar(indice: float, esquema: str = CLASIFICACION_DEFECTO) -> dict:
    if esquema not in CLASIFICACIONES:
        raise ValueError(f"clasificación desconocida: {esquema} ({', '.join(CLASIFICACIONES)})")
    if indice is None:
        return dict(color=None, nivel="Sin dato", accion="", banda=None)
    x = math.inf if math.isinf(indice) else round(indice + 1e-9, 1)
    for k, (lim, color, nivel, accion) in enumerate(CLASIFICACIONES[esquema]["bandas"]):
        if x <= lim:
            return dict(color=color, nivel=nivel, accion=accion, banda=k)
    raise AssertionError  # pragma: no cover


URGENCIA_COLOR = {"verde": 0, "amarillo": 2, "rojo_bajo": 3, "rojo": 3, "morado": 4}  # escala de hallazgos.URGENCIAS
