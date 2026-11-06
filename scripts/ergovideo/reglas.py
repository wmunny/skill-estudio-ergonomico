"""Reglas deterministas de OWAS, REBA y RULA sobre intervalos.

Cada medida entra como intervalo [mínimo, máximo] (valor medido ± margen de medida) o como None si no se conoce.
Cada regla devuelve el CONJUNTO de puntuaciones posibles dentro de ese intervalo: si el intervalo no cruza ningún
umbral, una sola; si lo cruza, varias; si el dato es desconocido, todas las que permite el método. Nada de lo que
falta se convierte en el valor favorable.

Convenciones de frontera (versionadas en CONVENCIONES):
- OWAS y REBA: lectura literal de Ergonautas (p. ej. REBA tronco «flexión > 20° y ≤ 60°» → 20° es 2).
- RULA: en la frontera entre dos puntuaciones, la mayor (notas de McAtamney, 2024, citadas por la auditoría).
- Carga OWAS: convención INSST (10 kg exactos → tramo 1).
- Extensión del tronco en RULA: adaptación propia (se puntúa por su magnitud como la flexión). Punto abierto.
"""

from __future__ import annotations

import math

CONVENCIONES = {
    "OWAS": "Fronteras literales de Ergonautas; pierna flexionada si flexión ≥ 30° (muslo-pantorrilla ≤ 150°); "
            "brazo elevado si codo o muñeca están al nivel del hombro o por encima; carga según INSST (≤ 10 kg → 1).",
    "REBA": "Fronteras literales de Ergonautas/NTP 601 (el valor límite va en el tramo que lo incluye con «≤»).",
    "RULA": "En la frontera entre dos puntuaciones, la mayor (McAtamney, 2024, según la auditoría; pendiente de "
            "verificar el documento).",
}

DELTA = 1e-4
Intervalo = tuple  # (mínimo, máximo) o None


def intervalo(valor: float | None, margen: float, minimo: float | None = None) -> Intervalo | None:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    lo, hi = valor - margen, valor + margen
    if minimo is not None:
        lo, hi = max(minimo, lo), max(minimo, hi)
    return (lo, hi)


def posibles(f, iv: Intervalo | None, cortes: list[float], todos) -> frozenset:
    """Valores de f en el intervalo: extremos y, para cada umbral interior, el propio umbral y sus vecinos."""
    if iv is None:
        return frozenset(todos)
    lo, hi = iv
    xs = {lo, hi}
    for c in cortes:
        for x in (c - DELTA, c, c + DELTA):
            if lo <= x <= hi:
                xs.add(x)
    return frozenset(f(x) for x in xs)


def booleano(valor: bool | None) -> frozenset:
    """Dato declarado: sí/no, o desconocido (las dos posibilidades)."""
    return frozenset({False, True}) if valor is None else frozenset({bool(valor)})


def presente(iv: Intervalo | None, umbral: float) -> frozenset:
    """¿La medida supera un criterio de detección (estrictamente)?"""
    return posibles(lambda x: x > umbral, iv, [umbral], (False, True))


def _abs_iv(iv: Intervalo | None) -> Intervalo | None:
    if iv is None:
        return None
    lo, hi = iv
    if lo <= 0 <= hi:
        return (0.0, max(-lo, hi))
    return (min(abs(lo), abs(hi)), max(abs(lo), abs(hi)))


# =============================================================================== OWAS

def owas_espalda(flex: Intervalo | None, giro: Intervalo | None, lat: Intervalo | None, u) -> frozenset:
    """1 derecha · 2 doblada (> 20°) · 3 con giro (torsión o inclinación lateral > 20°) · 4 doblada con giro."""
    doblada = posibles(lambda x: x > u.espalda_flexion, _abs_iv(flex), [u.espalda_flexion], (False, True))
    girada = {a or b for a in presente(giro, u.espalda_giro) for b in presente(lat, u.espalda_lateral)}
    return frozenset((4 if d and g else 2 if d else 3 if g else 1) for d in doblada for g in girada)


def owas_brazo_elevado(alt: Intervalo | None, u) -> frozenset:
    """Elevado si el codo o la muñeca están al nivel del hombro o por encima (altura ≥ margen)."""
    return posibles(lambda x: x >= u.brazo_margen, alt, [u.brazo_margen], (False, True))


def owas_brazos(alt_i: Intervalo | None, alt_d: Intervalo | None, u) -> frozenset:
    return frozenset(1 + int(a) + int(b) for a in owas_brazo_elevado(alt_i, u) for b in owas_brazo_elevado(alt_d, u))


def owas_rodilla_flexionada(rod: Intervalo | None, u) -> frozenset:
    """Flexionada si la flexión es ≥ 30° (ángulo muslo-pantorrilla ≤ 150°)."""
    return posibles(lambda x: x >= u.rodilla_flexion, rod, [u.rodilla_flexion], (False, True))


def owas_carga(kg: float | None) -> frozenset:
    from .tablas import codigo_carga
    return frozenset({1, 2, 3}) if kg is None else frozenset({codigo_carga(kg)})


# =============================================================================== REBA (literal)

def reba_tronco_base(sag: Intervalo | None) -> frozenset:
    """1 erguido (0°) · 2 flexión o extensión hasta 20° · 3 flexión > 20° y ≤ 60° o extensión > 20° · 4 flexión > 60°."""
    def f(x):
        if x == 0:
            return 1
        if -20 <= x <= 20:
            return 2
        if x < -20 or x <= 60:
            return 3
        return 4
    return posibles(f, sag, [-20, 0, 20, 60], (1, 2, 3, 4))


def reba_cuello_base(c: Intervalo | None) -> frozenset:
    """1 flexión de 0° a 20° · 2 flexión > 20° o extensión."""
    return posibles(lambda x: 1 if 0 <= x <= 20 else 2, c, [0, 20], (1, 2))


def reba_rodillas(rod: Intervalo | None, sentado: frozenset) -> frozenset:
    """+1 flexión de 30° a 60° · +2 más de 60° salvo sentado (lectura literal: sentado, > 60° no suma)."""
    out = set()
    for s in sentado:
        def f(x, s=s):
            if x < 30:
                return 0
            if x <= 60:
                return 1
            return 0 if s else 2
        out |= posibles(f, rod, [30, 60], (0, 1) if s else (0, 1, 2))
    return frozenset(out)


def reba_carga(kg: float | None, brusca: bool | None) -> frozenset:
    """< 5 kg → 0 · 5–10 kg → +1 · > 10 kg → +2; fuerza brusca +1."""
    base = {0, 1, 2} if kg is None else {0 if kg < 5 else 1 if kg <= 10 else 2}
    return frozenset(b + int(x) for b in base for x in booleano(brusca))


def reba_brazo_base(fl: Intervalo | None) -> frozenset:
    """1 de 20° de extensión a 20° de flexión · 2 extensión > 20° o flexión > 20° y ≤ 45° · 3 > 45° y ≤ 90° · 4 > 90°."""
    def f(x):
        if -20 <= x <= 20:
            return 1
        if x < -20 or x <= 45:
            return 2
        return 3 if x <= 90 else 4
    return posibles(f, fl, [-20, 20, 45, 90], (1, 2, 3, 4))


def reba_brazo(fl, abd, rotado, elevado, apoyado, u) -> frozenset:
    """Base + 1 si abducido o rotado + 1 si hombro elevado − 1 si apoyado; mínimo 1."""
    out = set()
    for b in reba_brazo_base(fl):
        for ab in presente(abd, u.brazo_abducido):
            for ro in booleano(rotado):
                for el in booleano(elevado):
                    for ap in booleano(apoyado):
                        out.add(max(1, b + int(ab or ro) + int(el) - int(ap)))
    return frozenset(out)


def reba_antebrazo(codo: Intervalo | None) -> frozenset:
    """1 flexión de 60° a 100° · 2 < 60° o > 100°."""
    return posibles(lambda x: 1 if 60 <= x <= 100 else 2, codo, [60, 100], (1, 2))


def reba_muneca(m: Intervalo | None, declarada: str | None, desviada: bool | None) -> frozenset:
    """1 flexión/extensión hasta 15° · 2 > 15°; +1 torsión o desviación."""
    if declarada:
        base = {1 if declarada in ("neutra", "menos15") else 2}
    else:
        base = posibles(lambda x: 1 if x <= 15 else 2, m, [15], (1, 2))
    return frozenset(b + int(d) for b in base for d in booleano(desviada))


def reba_agarre(agarre: int | None) -> frozenset:
    return frozenset({0, 1, 2, 3}) if agarre is None else frozenset({agarre})


def actividad(indicadores: dict, claves=("estatica", "repetitiva", "cambios")) -> frozenset:
    """REBA: +1 por cada indicador presente (hasta +3); desconocido → las dos posibilidades."""
    sumas = {0}
    for k in claves:
        sumas = {s + int(v) for s in sumas for v in booleano(indicadores.get(k))}
    return frozenset(sumas)


# =============================================================================== RULA (en la frontera, la mayor)

def rula_brazo_base(fl: Intervalo | None) -> frozenset:
    """1 entre 20° de extensión y 20° de flexión · 2 extensión ≥ 20° o flexión ≥ 20° y < 45° · 3 ≥ 45° y < 90° · 4 ≥ 90°."""
    def f(x):
        if -20 < x < 20:
            return 1
        if x <= -20 or x < 45:
            return 2
        return 3 if x < 90 else 4
    return posibles(f, fl, [-20, 20, 45, 90], (1, 2, 3, 4))


def rula_brazo(fl, abd, elevado, apoyado, u) -> frozenset:
    """Base + 1 hombro elevado + 1 abducido − 1 apoyado (modificadores del artículo original de 1993); mínimo 1."""
    out = set()
    for b in rula_brazo_base(fl):
        for el in booleano(elevado):
            for ab in presente(abd, u.brazo_abducido):
                for ap in booleano(apoyado):
                    out.add(max(1, b + int(el) + int(ab) - int(ap)))
    return frozenset(out)


def rula_antebrazo(codo: Intervalo | None, lat: Intervalo | None, u) -> frozenset:
    """1 flexión > 60° y < 100° · 2 en el resto (60° y 100° → 2); +1 si cruza la línea media o va a un lado."""
    base = posibles(lambda x: 1 if 60 < x < 100 else 2, codo, [60, 100], (1, 2))
    fuera = posibles(lambda x: 1 if (x <= u.antebrazo_cruza or x >= u.antebrazo_fuera) else 0, lat,
                     [u.antebrazo_cruza, u.antebrazo_fuera], (0, 1))
    return frozenset(b + f for b in base for f in fuera)


def rula_muneca(m: Intervalo | None, declarada: str | None, desviada: bool | None) -> frozenset:
    """1 neutra (0°) · 2 flexión o extensión > 0° y < 15° · 3 ≥ 15°; +1 desviación radial o cubital."""
    if declarada:
        base = {{"neutra": 1, "menos15": 2, "mas15": 3}[declarada]}
    else:
        base = posibles(lambda x: 1 if x <= 0 else 2 if x < 15 else 3, m, [0, 15], (1, 2, 3))
    return frozenset(b + int(d) for b in base for d in booleano(desviada))


def rula_giro(extremo: bool | None) -> frozenset:
    return frozenset((2 if e else 1) for e in booleano(extremo))


def rula_cuello(c: Intervalo | None, girado: bool | None, inclinado: bool | None) -> frozenset:
    """1 flexión ≥ 0° y < 10° · 2 ≥ 10° y < 20° · 3 ≥ 20° · 4 extensión; +1 rotada; +1 inclinada (independientes)."""
    def f(x):
        if x < 0:
            return 4
        return 1 if x < 10 else 2 if x < 20 else 3
    base = posibles(f, c, [0, 10, 20], (1, 2, 3, 4))
    return frozenset(b + int(g) + int(i) for b in base for g in booleano(girado) for i in booleano(inclinado))


def rula_tronco(sag: Intervalo | None, giro: Intervalo | None, lat: Intervalo | None, u) -> frozenset:
    """1 erguido (0°) · 2 > 0° y < 20° · 3 ≥ 20° y < 60° · 4 ≥ 60°; +1 rotado; +1 inclinado (independientes).
    La extensión se puntúa por su magnitud (adaptación propia: el método no la puntúa)."""
    base = posibles(lambda x: 1 if x == 0 else 2 if x < 20 else 3 if x < 60 else 4, _abs_iv(sag), [0, 20, 60],
                    (1, 2, 3, 4))
    return frozenset(b + int(g) + int(l_) for b in base for g in presente(giro, u.giro_presente)
                     for l_ in presente(lat, u.giro_presente))


def rula_musculo(indicadores: dict) -> frozenset:
    """+1 si la postura es estática (> 1 min) o repetitiva (> 4 veces/min)."""
    return frozenset(int(a or b) for a in booleano(indicadores.get("estatica"))
                     for b in booleano(indicadores.get("repetitiva")))


def rula_fuerza(kg: float | None, indicadores: dict, brusca: bool | None) -> frozenset:
    """0 < 2 kg intermitente · 1 2–10 kg intermitente · 2 2–10 kg estática/repetitiva o ≥ 10 kg intermitente ·
    3 ≥ 10 kg estática/repetitiva o golpes (en la frontera, la mayor: 2 kg y 10 kg suben de tramo)."""
    kgs = [0.0, 5.0, 15.0] if kg is None else [kg]
    out = set()
    for k in kgs:
        for est in booleano(indicadores.get("estatica")):
            for rep in booleano(indicadores.get("repetitiva")):
                for br in booleano(brusca):
                    sost = est or rep
                    if br:
                        out.add(3)
                    elif k < 2:
                        out.add(0)
                    elif k < 10:
                        out.add(2 if sost else 1)
                    else:
                        out.add(3 if sost else 2)
    return frozenset(out)


# =============================================================================== apoyo de las piernas

def apoyo_reba(piernas_owas: frozenset, declarado: str | None) -> frozenset:
    """REBA: 1 sentado, andando o apoyo bilateral simétrico · 2 apoyo unilateral, ligero o inestable.
    Sin declarar: desde los códigos OWAS posibles; arrodillado no implica inestabilidad (→ 1 o 2)."""
    if declarado:
        return frozenset({1 if declarado == "bilateral" else 2})
    out = set()
    for p in piernas_owas:
        out |= {1: {1}, 2: {1}, 3: {2}, 4: {1}, 5: {2}, 6: {1, 2}, 7: {1}}[p]
    return frozenset(out)


def apoyo_rula(piernas_owas: frozenset, declarado: str | None) -> frozenset:
    """RULA: 1 sentado con pies apoyados o de pie con peso simétrico · 2 en otro caso.
    Sin declarar: sentado (no se ve si los pies apoyan), arrodillado y andando → 1 o 2."""
    if declarado:
        return frozenset({1 if declarado == "bilateral" else 2})
    out = set()
    for p in piernas_owas:
        out |= {1: {1, 2}, 2: {1}, 3: {2}, 4: {1}, 5: {2}, 6: {1, 2}, 7: {1, 2}}[p]
    return frozenset(out)
