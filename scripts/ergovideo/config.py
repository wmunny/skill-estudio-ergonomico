"""Parámetros de la skill. Los umbrales de OWAS salen de Ergonautas (Mattila et al., 1999);
el resto son convenciones iniciales que hay que calibrar con un ergónomo."""

from __future__ import annotations

from dataclasses import dataclass, field

# Índices de MediaPipe Pose (33 puntos).
NARIZ, OJO_I, OJO_D, OREJA_I, OREJA_D = 0, 2, 5, 7, 8
HOMBRO_I, HOMBRO_D, CODO_I, CODO_D, MUNECA_I, MUNECA_D = 11, 12, 13, 14, 15, 16
CADERA_I, CADERA_D, RODILLA_I, RODILLA_D, TOBILLO_I, TOBILLO_D = 23, 24, 25, 26, 27, 28
CARA = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Lados: I = izquierdo del trabajador, D = derecho (convención de MediaPipe).
PUNTOS = {
    "I": dict(hombro=HOMBRO_I, codo=CODO_I, muneca=MUNECA_I, cadera=CADERA_I, rodilla=RODILLA_I, tobillo=TOBILLO_I),
    "D": dict(hombro=HOMBRO_D, codo=CODO_D, muneca=MUNECA_D, cadera=CADERA_D, rodilla=RODILLA_D, tobillo=TOBILLO_D),
}

# Segmentos [proximal, distal] para el filtro de longitud de huesos.
SEGMENTOS = [(11, 13), (13, 15), (12, 14), (14, 16), (23, 25), (25, 27), (24, 26), (26, 28)]

ESQUELETO = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28), (27, 31), (28, 32), (27, 29), (28, 30),
]


@dataclass
class Umbrales:
    # OWAS (Ergonautas, tablas 1 y 3)
    espalda_flexion: float = 20.0       # grados: inclinación mayor → espalda doblada
    espalda_giro: float = 20.0          # grados: torsión mayor → espalda con giro
    espalda_lateral: float = 20.0       # grados: inclinación lateral mayor → espalda con giro
    rodilla_flexion: float = 30.0       # grados de flexión (muslo-pantorrilla ≤ 150°) → pierna flexionada
    brazo_margen: float = 0.0           # longitudes de tronco: margen sobre el hombro para «brazo elevado»
    # Heurísticas propias (no son de OWAS)
    arrodillado_pierna: float = 60.0    # pantorrilla a más de estos grados de la vertical → rodilla en el suelo
    sentado_muslo: float = 55.0         # muslo a más de estos grados de la vertical…
    sentado_pierna: float = 35.0        # …con la pantorrilla a menos de estos → sentado
    pie_levantado_m: float = 0.08       # diferencia de altura de los tobillos (m, 3D) → peso en una pierna
    asimetria_rodillas: float = 30.0    # grados de diferencia entre rodillas flexionadas → peso desequilibrado
    andando_velocidad: float = 0.6      # longitudes de tronco por segundo del centro de la cadera → andando
    # Criterios de detección (no son umbrales de los métodos, que no dan grados): provisionales.
    giro_presente: float = 20.0         # REBA/RULA: torsión o inclinación lateral del tronco «presente»
    brazo_abducido: float = 30.0        # REBA/RULA: brazo abducido
    antebrazo_cruza: float = 0.0        # RULA: muñeca en la línea media o más allá (semianchos de hombros)
    antebrazo_fuera: float = 2.0        # RULA: muñeca a un lado del cuerpo (semianchos de hombros)


@dataclass
class Filtros:
    visibilidad: float = 0.5            # visibilidad mínima de MediaPipe para usar un punto
    visibilidad_giro: float = 0.3       # el giro necesita los dos hombros y caderas: se admite algo menos
    tolerancia_hueso: float = 0.3       # variación máxima de la longitud 3D de un segmento respecto a su mediana
    coherencia_vertical: float = 0.5    # seno (30°) para comparar si el segmento sube o baja en 2D y 3D
    hampel_ventana_s: float = 0.5
    hampel_sigmas: float = 3.0
    hampel_minimo: float = 12.0         # en unidades de la medida (grados en los ángulos)
    tramo_minimo_s: float = 0.4         # tramos más cortos entre saltos imposibles se descartan
    hueco_maximo_s: float = 0.3         # huecos más cortos se interpolan
    vista_lateral: float = 55.0         # grados de giro respecto a la cámara a partir de los que se usa 2D


# Rango fisiológico y velocidad máxima plausible (unidad/s) de cada medida.
MEDIDAS = {
    "tronco_flex": dict(rango=(0, 130), vmax=300, unidad="°", nombre="Flexión del tronco"),
    "tronco_lat": dict(rango=(0, 60), vmax=300, unidad="°", nombre="Inclinación lateral del tronco"),
    "tronco_giro": dict(rango=(0, 90), vmax=300, unidad="°", nombre="Torsión del tronco"),
    "brazo_alt_I": dict(rango=(-4, 3), vmax=8, hampel=0.3, unidad="tronco", nombre="Altura mano/codo izq. sobre el hombro"),
    "brazo_alt_D": dict(rango=(-4, 3), vmax=8, hampel=0.3, unidad="tronco", nombre="Altura mano/codo dch. sobre el hombro"),
    "rodilla_I": dict(rango=(0, 165), vmax=400, unidad="°", nombre="Flexión rodilla izq."),
    "rodilla_D": dict(rango=(0, 165), vmax=400, unidad="°", nombre="Flexión rodilla dch."),
    "muslo_I": dict(rango=(0, 160), vmax=400, unidad="°", nombre="Muslo izq. respecto a la vertical"),
    "muslo_D": dict(rango=(0, 160), vmax=400, unidad="°", nombre="Muslo dch. respecto a la vertical"),
    "pierna_I": dict(rango=(0, 120), vmax=400, unidad="°", nombre="Pantorrilla izq. respecto a la vertical"),
    "pierna_D": dict(rango=(0, 120), vmax=400, unidad="°", nombre="Pantorrilla dch. respecto a la vertical"),
    "tronco_sag": dict(rango=(-60, 130), vmax=300, unidad="°", nombre="Flexión (+) o extensión (−) del tronco"),
    "cuello": dict(rango=(-60, 90), vmax=300, unidad="°", nombre="Flexión (+) o extensión (−) del cuello"),
    "brazo_flex_I": dict(rango=(-90, 190), vmax=600, unidad="°", nombre="Flexión del brazo izq."),
    "brazo_flex_D": dict(rango=(-90, 190), vmax=600, unidad="°", nombre="Flexión del brazo dch."),
    "brazo_abd_I": dict(rango=(0, 90), vmax=600, unidad="°", nombre="Abducción del brazo izq."),
    "brazo_abd_D": dict(rango=(0, 90), vmax=600, unidad="°", nombre="Abducción del brazo dch."),
    "codo_I": dict(rango=(0, 165), vmax=700, unidad="°", nombre="Flexión del codo izq."),
    "codo_D": dict(rango=(0, 165), vmax=700, unidad="°", nombre="Flexión del codo dch."),
    "muneca_I": dict(rango=(0, 100), vmax=800, unidad="°", nombre="Flexión de la muñeca izq. (estimada)"),
    "muneca_D": dict(rango=(0, 100), vmax=800, unidad="°", nombre="Flexión de la muñeca dch. (estimada)"),
    "antebrazo_lat_I": dict(rango=(-3, 5), vmax=12, hampel=0.3, unidad="semiancho", nombre="Muñeca izq. respecto a la línea media"),
    "antebrazo_lat_D": dict(rango=(-3, 5), vmax=12, hampel=0.3, unidad="semiancho", nombre="Muñeca dch. respecto a la línea media"),
    "tobillos": dict(rango=(-0.7, 0.7), vmax=4, hampel=0.06, unidad="m", nombre="Altura tobillo izq. − dch."),
}

# Qué medidas necesita cada región OWAS para poder codificarse.
REGION_MEDIDAS = {
    "espalda": ["tronco_flex"],
    "brazos": ["brazo_alt_I", "brazo_alt_D"],
    "piernas": ["rodilla_I", "rodilla_D"],
}


# Margen de medida provisional (± unidades de la medida) hasta calibrar con vídeos anotados. Si el intervalo
# medida ± margen cruza un umbral, la puntuación sale como rango. De frente o de espaldas (cálculo 3D con giro
# respecto a la cámara < 25°) se multiplica por FACTOR_FRONTAL.
MARGENES = {
    "tronco_flex": 5.0, "tronco_sag": 5.0, "tronco_lat": 5.0, "tronco_giro": 5.0, "cuello": 5.0,
    "brazo_flex": 10.0, "brazo_abd": 10.0, "codo": 10.0, "rodilla": 10.0, "muslo": 10.0, "pierna": 10.0,
    "muneca": 15.0, "brazo_alt": 0.15, "antebrazo_lat": 0.3, "tobillos": 0.03, "velocidad": 0.2,
}
FACTOR_FRONTAL = 1.5
VISTA_FRONTAL = 25.0


def margen(medida: str, vista: float | None = None, modo: str = "") -> float:
    base = MARGENES.get(medida.rsplit("_", 1)[0] if medida.endswith(("_I", "_D")) else medida, 0.0)
    if modo == "3d" and vista is not None and vista == vista and vista < VISTA_FRONTAL:
        return base * FACTOR_FRONTAL
    return base


@dataclass
class Muestreo:
    intervalo_s: float = 1.0            # intervalo entre observaciones OWAS (clásico: 30–60 s en directo)
    ventana_s: float = 0.4              # cada observación toma la mediana de ±ventana/2 alrededor del instante
    z: float = 1.96
    margen_objetivo: float = 10.0       # puntos de %: error máximo aceptable (OWAS: 100 observaciones → 10 %)
    sin_margen: bool = False            # True: aplicar los umbrales al valor medido sin margen (solo pruebas)
    observaciones_minimas: int = 100
    duracion_minima_s: float = 20 * 60  # OWAS: 20–40 min de observación
    decorrelacion_maxima_s: float = 30.0
    cobertura: tuple = (80.0, 50.0)     # % de observaciones codificables: verde ≥ 80, ámbar ≥ 50


@dataclass
class Config:
    umbrales: Umbrales = field(default_factory=Umbrales)
    filtros: Filtros = field(default_factory=Filtros)
    muestreo: Muestreo = field(default_factory=Muestreo)
    modo_angulos: str = "auto"          # auto | 2d | 3d
    postura_base: str = "auto"          # auto | de_pie | sentado (pista del usuario para la pierna)
