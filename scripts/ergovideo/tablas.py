"""Tablas del método OWAS (Karhu, Kansi y Kuorinka, 1977).

Transcritas de Ergonautas (Universitat Politècnica de València),
https://www.ergonautas.upv.es/metodos/owas/owas-ayuda.php, tablas 1 a 7, leídas el 6/11/2026.
La tabla de combinaciones se leyó de la tabla HTML de la página, no de memoria.

Todo el cálculo de categorías se hace con estas tablas, en código. Nunca con una IA.
"""

from __future__ import annotations

ESPALDA = {
    1: "Espalda derecha",
    2: "Espalda doblada",
    3: "Espalda con giro",
    4: "Espalda doblada con giro",
}
BRAZOS = {
    1: "Los dos brazos bajos",
    2: "Un brazo bajo y el otro elevado",
    3: "Los dos brazos elevados",
}
PIERNAS = {
    1: "Sentado",
    2: "De pie con las dos piernas rectas",
    3: "De pie con una pierna recta y la otra flexionada",
    4: "De pie o en cuclillas, piernas flexionadas, peso equilibrado",
    5: "De pie o en cuclillas, piernas flexionadas, peso desequilibrado",
    6: "Arrodillado",
    7: "Andando",
}
CARGA = {1: "Hasta 10 kg", 2: "Más de 10 kg y hasta 20 kg", 3: "Más de 20 kg"}
# Convención de carga OWAS: INSST/IBV (10 kg exactos en el tramo 1). Ergonautas los pone en el tramo 2.
CONVENCION_CARGA_OWAS = "INSST: ≤ 10 kg → 1; > 10 y ≤ 20 kg → 2; > 20 kg → 3"

REGIONES = {"espalda": ESPALDA, "brazos": BRAZOS, "piernas": PIERNAS, "carga": CARGA}

# Descripción limitada a la carga postural evaluada (Ergonautas, tabla 5): una categoría 1 no acredita
# la ausencia de otros riesgos del puesto.
CATEGORIAS = {
    1: ("Postura normal", "No requiere acción."),
    2: ("Posible daño musculoesquelético", "Se requieren acciones correctivas en un futuro cercano."),
    3: ("Efectos dañinos", "Se requieren acciones correctivas lo antes posible."),
    4: ("Efectos sumamente dañinos", "Se requieren acciones correctivas inmediatamente."),
}

# Tabla 6: categoría de acción por combinación. Clave (espalda, brazos); valor: cadena de 21 cifras,
# piernas 1..7 y, dentro de cada pierna, carga 1, 2, 3.
_COMBINACIONES = {
    (1, 1): "111 111 111 222 222 111 111",
    (1, 2): "111 111 111 222 222 111 111",
    (1, 3): "111 111 111 223 223 111 112",
    (2, 1): "223 223 223 333 333 222 233",
    (2, 2): "223 223 233 344 344 334 234",
    (2, 3): "334 223 333 344 444 444 234",
    (3, 1): "111 111 112 333 444 111 111",  # corregido (auditoría 06/11/2026): 3143 = 3
    (3, 2): "223 111 112 444 444 333 111",
    (3, 3): "223 111 233 444 444 444 111",
    (4, 1): "233 223 223 444 444 444 234",
    (4, 2): "334 234 334 444 444 444 234",
    (4, 3): "444 234 334 444 444 444 234",
}


def categoria_combinacion(espalda: int, brazos: int, piernas: int, carga: int) -> int:
    """Categoría de acción (1–4) de un código de postura completo (tabla 6)."""
    if espalda not in ESPALDA or brazos not in BRAZOS or piernas not in PIERNAS or carga not in CARGA:
        raise ValueError(f"Código OWAS fuera de rango: {espalda}{brazos}{piernas}{carga}")
    fila = _COMBINACIONES[(espalda, brazos)].replace(" ", "")
    return int(fila[(piernas - 1) * 3 + (carga - 1)])


# Tabla 7: categoría por frecuencia relativa. Columnas: ≤10 %, ≤20 % … ≤100 %.
_FRECUENCIA = {
    "espalda": {1: "1111111111", 2: "1112222233", 3: "1122233333", 4: "1223333444"},
    "brazos": {1: "1111111111", 2: "1112222233", 3: "1122222333"},
    "piernas": {
        1: "1111111112", 2: "1111111122", 3: "1112222233", 4: "1223333444",
        5: "1223333444", 6: "1122233333", 7: "1111111122",
    },
}


def categoria_frecuencia(region: str, codigo: int, porcentaje: float) -> int:
    """Categoría (1–4) de un código según el % del tiempo en que aparece (tabla 7).

    La columna k (1..10) abarca (10·(k−1) %, 10·k %]; el 0 % cae en la primera.
    """
    if region not in _FRECUENCIA or codigo not in _FRECUENCIA[region]:
        raise ValueError(f"Sin tabla de frecuencia para {region} {codigo}")
    if not 0 <= porcentaje <= 100 + 1e-9:
        raise ValueError(f"Porcentaje fuera de rango: {porcentaje}")
    columna = max(0, min(9, int(-(-round(porcentaje, 6) // 10)) - 1))  # techo(p/10) − 1
    return int(_FRECUENCIA[region][codigo][columna])


def codigo_carga(kg: float) -> int:
    """Código de carga OWAS con la convención del INSST: ≤ 10 kg → 1; > 10 y ≤ 20 kg → 2; > 20 kg → 3."""
    if kg < 0:
        raise ValueError("La carga no puede ser negativa")
    if kg <= 10:
        return 1
    return 2 if kg <= 20 else 3


# Error máximo (95 %) según el número de observaciones, como lo da Ergonautas.
ERROR_POR_OBSERVACIONES = {100: 10, 200: 7, 300: 6, 400: 5}


# =============================================================================== REBA
# Hignett y McAtamney (2000). Tablas leídas de https://www.ergonautas.upv.es/metodos/reba/reba-ayuda.php
# (tablas HTML de la página, 6/11/2026).

# Tabla A: fila = tronco 1..5; columnas = cuello 1..3 × piernas 1..4.
_REBA_A = [
    "1234 1234 3356",
    "2345 3456 4567",
    "2456 4567 5678",
    "3567 5678 6789",
    "4678 6789 7899",
]
# Tabla B: fila = brazo 1..6; columnas = antebrazo 1..2 × muñeca 1..3.
_REBA_B = ["122 123", "123 234", "345 455", "455 567", "678 788", "788 899"]
# Tabla C: fila = puntuación A 1..12; columnas = puntuación B 1..12.
_REBA_C = [
    [1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7],
    [1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8],
    [2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8],
    [3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9],
    [4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9, 9],
    [6, 6, 6, 7, 8, 8, 9, 9, 10, 10, 10, 10],
    [7, 7, 7, 8, 9, 9, 9, 10, 10, 11, 11, 11],
    [8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11],
    [9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12],
    [10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12],
    [11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12],
    [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12],
]
REBA_NIVELES = [  # (puntuación mínima, nivel, riesgo, actuación)
    (1, 0, "Inapreciable", "No es necesaria actuación."),
    (2, 1, "Bajo", "Puede ser necesaria la actuación."),
    (4, 2, "Medio", "Es necesaria la actuación."),
    (8, 3, "Alto", "Es necesaria la actuación cuanto antes."),
    (11, 4, "Muy alto", "Es necesaria la actuación de inmediato."),
]


def reba_tabla_a(tronco: int, cuello: int, piernas: int) -> int:
    return int(_REBA_A[tronco - 1].split()[cuello - 1][piernas - 1])


def reba_tabla_b(brazo: int, antebrazo: int, muneca: int) -> int:
    return int(_REBA_B[brazo - 1].split()[antebrazo - 1][muneca - 1])


def reba_tabla_c(a: int, b: int) -> int:
    """Tabla C de REBA. A y B por encima de 12 (tras sumar carga y agarre) usan la fila o columna 12."""
    if a < 1 or b < 1:
        raise ValueError(f"Puntuaciones REBA no válidas: A={a}, B={b}")
    return _REBA_C[min(a, 12) - 1][min(b, 12) - 1]


def reba_nivel(puntuacion: int) -> tuple:
    if not 1 <= puntuacion <= 15:
        raise ValueError(f"Puntuación REBA fuera de 1–15: {puntuacion}")
    return [n for n in REBA_NIVELES if puntuacion >= n[0]][-1]


# =============================================================================== RULA
# McAtamney y Corlett (1993). Tablas leídas de https://www.ergonautas.upv.es/metodos/rula/rula-ayuda.php
# (tablas HTML de la página, 6/11/2026).

# Tabla A: clave (brazo 1..6, antebrazo 1..3); columnas = muñeca 1..4 × giro 1..2.
_RULA_A = {
    (1, 1): "12 22 23 33", (1, 2): "22 22 33 33", (1, 3): "23 33 33 44",
    (2, 1): "23 33 34 44", (2, 2): "33 33 34 44", (2, 3): "34 44 44 55",
    (3, 1): "33 44 44 55", (3, 2): "34 44 44 55", (3, 3): "44 44 45 55",
    (4, 1): "44 44 45 55", (4, 2): "44 44 45 55", (4, 3): "44 45 55 66",
    (5, 1): "55 55 56 67", (5, 2): "56 66 67 77", (5, 3): "66 67 77 78",
    (6, 1): "77 77 78 89", (6, 2): "88 88 89 99", (6, 3): "99 99 99 99",
}
# Tabla B: fila = cuello 1..6; columnas = tronco 1..6 × piernas 1..2.
_RULA_B = [
    "13 23 34 55 66 77",
    "23 23 45 55 67 77",
    "33 34 45 56 67 77",
    "55 56 67 77 77 88",
    "77 77 78 88 88 88",
    "88 88 88 89 99 99",
]
# Tabla C: fila = puntuación C 1..8 (8+); columnas = puntuación D 1..7 (7+).
_RULA_C = ["1233455", "2234455", "3334456", "3334566", "4445677", "4456677", "5566777", "5567777"]
# RULA solo da nivel y actuación; no se añaden etiquetas de riesgo propias.
RULA_NIVELES = [
    (1, 1, "Nivel 1", "Postura aceptable si no se mantiene ni se repite durante largos periodos."),
    (3, 2, "Nivel 2", "Pueden requerirse cambios en la tarea; conviene profundizar en el estudio."),
    (5, 3, "Nivel 3", "Se requiere el rediseño de la tarea."),
    (7, 4, "Nivel 4", "Se requieren cambios urgentes en la tarea."),
]


def rula_tabla_a(brazo: int, antebrazo: int, muneca: int, giro: int) -> int:
    return int(_RULA_A[(brazo, antebrazo)].split()[muneca - 1][giro - 1])


def rula_tabla_b(cuello: int, tronco: int, piernas: int) -> int:
    return int(_RULA_B[cuello - 1].split()[tronco - 1][piernas - 1])


def rula_tabla_c(c: int, d: int) -> int:
    """Tabla C de RULA: C ≥ 8 usa la fila 8+ y D ≥ 7 la columna 7+ (se conservan C y D originales aparte)."""
    if c < 1 or d < 1:
        raise ValueError(f"Puntuaciones RULA no válidas: C={c}, D={d}")
    return int(_RULA_C[min(c, 8) - 1][min(d, 7) - 1])


def rula_nivel(puntuacion: int) -> tuple:
    if not 1 <= puntuacion <= 7:
        raise ValueError(f"Puntuación RULA fuera de 1–7: {puntuacion}")
    return [n for n in RULA_NIVELES if puntuacion >= n[0]][-1]
