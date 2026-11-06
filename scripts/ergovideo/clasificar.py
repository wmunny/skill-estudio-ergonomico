"""Clasificación OWAS de una observación. Reglas fijas sobre intervalos, sin IA.

Para cada región se devuelven:
- el conjunto de códigos posibles con el margen de medida y lo desconocido (nunca se rellena con el valor favorable);
- el código nominal: el que dan las medidas tal cual, sin margen, o None si falta algún dato necesario.
"""

from __future__ import annotations

import math

from . import reglas as R
from .config import Config, Umbrales, margen

FACTOR_APROXIMADA = 1.5  # igual que revision.FACTOR_APROXIMADA (sin importar revision para evitar ciclos)
from .tablas import categoria_combinacion

nan = math.nan


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _iv(m: dict, k: str, mg, minimo=None):
    return R.intervalo(m.get(k, nan), mg(k), minimo)


RODILLAS_SUPUESTAS = {"menos30": 10.0, "30a60": 45.0, "mas60": 90.0}


def piernas(m: dict, u: Umbrales, postura_base: str, mg, supuesto: dict | None = None) -> tuple[frozenset, list[str]]:
    """Códigos de piernas posibles (1–7). Andar, arrodillarse y sentarse son heurísticas propias, provisionales.

    `supuesto` (declarado o de la revisión visual): {"rodillas": "menos30"|"30a60"|"mas60", "apoyo":
    "bilateral"|"unilateral"}. Solo rellena lo que no se ve; nunca sustituye a una medida."""
    notas = []
    out = set()
    if postura_base == "sentado":
        # Sentado declarado (o estimado en la revisión): las piernas no necesitan verse para OWAS.
        return frozenset({1}), ["sentado_declarado"]
    if not _ok(m.get("rodilla_I", nan)) and not _ok(m.get("rodilla_D", nan)):
        notas.append("piernas_no_visibles")
    elif not _ok(m.get("rodilla_I", nan)) or not _ok(m.get("rodilla_D", nan)):
        notas.append("una_pierna_no_visible")
    supuesto = supuesto or {}
    rod_sup = RODILLAS_SUPUESTAS.get(supuesto.get("rodillas"))
    if rod_sup is not None or supuesto.get("apoyo") == "bilateral":
        m = dict(m)
        for s_ in "ID":
            if rod_sup is not None and not _ok(m.get(f"rodilla_{s_}", nan)):
                m[f"rodilla_{s_}"] = rod_sup
                if "rodillas_supuestas" not in notas:
                    notas.append("rodillas_supuestas")
        if supuesto.get("apoyo") == "bilateral" and not _ok(m.get("tobillos", nan)):
            m["tobillos"] = 0.0
            notas.append("apoyo_supuesto")
    iv = lambda k, minimo=None: _iv(m, k, mg, minimo)  # noqa: E731

    andando = R.presente(iv("velocidad", 0.0), u.andando_velocidad)
    if True in andando:
        out.add(7)
    if False not in andando:
        return frozenset(out), notas

    def lado_arrodillado(s):
        return {a and b for a in R.presente(iv(f"pierna_{s}", 0.0), u.arrodillado_pierna)
                for b in R.presente(iv(f"rodilla_{s}", 0.0), 60.0)}
    # De pie (declarado o estimado): ni arrodillado ni sentado.
    arrodillado = {False} if postura_base == "de_pie" else {a or b for a in lado_arrodillado("I") for b in lado_arrodillado("D")}
    if True in arrodillado:
        out.add(6)
    if False not in arrodillado:
        return frozenset(out), notas

    # Sentado
    if postura_base == "de_pie":
        sentado = {False}
    else:
        def media(a, b):
            if a is None or b is None:
                return a or b
            return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

        def maximo(a, b):
            if a is None or b is None:
                return None  # el lado que no se ve podría ser el mayor
            return (max(a[0], b[0]), max(a[1], b[1]))
        muslo = media(iv("muslo_I", 0.0), iv("muslo_D", 0.0))
        c1 = R.posibles(lambda x: x >= u.sentado_muslo, muslo, [u.sentado_muslo], (False, True))
        c2 = R.posibles(lambda x: x <= u.sentado_pierna, maximo(iv("pierna_I", 0.0), iv("pierna_D", 0.0)),
                        [u.sentado_pierna], (False, True))
        c3 = R.posibles(lambda x: x <= 120, maximo(iv("rodilla_I", 0.0), iv("rodilla_D", 0.0)), [120], (False, True))
        sentado = {a and b and c for a in c1 for b in c2 for c in c3}
    if True in sentado:
        out.add(1)
    if False not in sentado:
        return frozenset(out), notas

    fi = R.owas_rodilla_flexionada(iv("rodilla_I", 0.0), u)
    fd = R.owas_rodilla_flexionada(iv("rodilla_D", 0.0), u)
    tob = iv("tobillos")
    pie = R.posibles(lambda x: "I" if x > u.pie_levantado_m else "D" if x < -u.pie_levantado_m else "",
                     tob, [-u.pie_levantado_m, u.pie_levantado_m], ("", "I", "D"))
    ri, rd = iv("rodilla_I", 0.0), iv("rodilla_D", 0.0)
    dif = None if ri is None or rd is None else (ri[0] - rd[1], ri[1] - rd[0])
    asim = R.presente(R._abs_iv(dif), u.asimetria_rodillas)
    for a in fi:
        for b in fd:
            for p in pie:
                for s in asim:
                    if p:  # un pie levantado: el peso va en la otra pierna
                        apoyo_flex = b if p == "I" else a
                        out.add(5 if apoyo_flex else 3)
                    elif not a and not b:
                        out.add(2)
                    elif a != b:
                        out.add(3)
                    else:
                        out.add(5 if s else 4)
    return frozenset(out), notas


def regiones(m: dict, cfg: Config, kg: float | None, postura_base: str, vista=None, modo="",
             sin_margen: bool = False) -> dict:
    """Conjuntos de códigos posibles por región y notas de lo que falta."""
    u = cfg.umbrales
    aprox = m.get("_aprox", frozenset())
    mg = (lambda k: 0.0) if sin_margen else (lambda k: margen(k, vista, modo) * (FACTOR_APROXIMADA if k in aprox else 1.0))  # noqa: E731
    iv = lambda k, minimo=None: _iv(m, k, mg, minimo)  # noqa: E731
    notas = []
    if not _ok(m.get("tronco_flex", nan)):
        notas.append("espalda_no_visible")
    if not _ok(m.get("tronco_giro", nan)):
        notas.append("giro_no_medido")
    if not _ok(m.get("tronco_lat", nan)):
        notas.append("lateral_no_medida")
    esp = R.owas_espalda(iv("tronco_flex", 0.0), iv("tronco_giro", 0.0), iv("tronco_lat", 0.0), u)
    vistos = [k for k in ("brazo_alt_I", "brazo_alt_D") if _ok(m.get(k, nan))]
    if not vistos:
        notas.append("brazos_no_visibles")
    elif len(vistos) == 1:
        notas.append("un_brazo_no_visible")
    bra = R.owas_brazos(iv("brazo_alt_I"), iv("brazo_alt_D"), u)
    pie, np_ = piernas(m, u, postura_base, mg, getattr(cfg, "supuesto_piernas", None))
    car = R.owas_carga(kg)
    if kg is None:
        notas.append("carga_no_declarada")
    return dict(espalda=esp, brazos=bra, piernas=pie, carga=car, notas=notas + np_)


def clasificar(m: dict, cfg: Config, kg: float | None, postura_base: str = "auto", vista=None, modo="") -> dict:
    """Observación OWAS: conjuntos con margen, código nominal (sin margen) y categorías posibles."""
    con = regiones(m, cfg, kg, postura_base, vista, modo, sin_margen=cfg.muestreo.sin_margen)
    nom = regiones(m, cfg, kg, postura_base, vista, modo, sin_margen=True)
    out = {"notas": con["notas"]}
    for r in ("espalda", "brazos", "piernas", "carga"):
        out[f"{r}_posibles"] = sorted(con[r])
        out[r] = next(iter(nom[r])) if len(nom[r]) == 1 else None
    cats = {categoria_combinacion(e, b, p, c) for e in con["espalda"] for b in con["brazos"]
            for p in con["piernas"] for c in con["carga"]}
    out["categoria_posibles"] = sorted(cats)
    out["categoria"] = (categoria_combinacion(out["espalda"], out["brazos"], out["piernas"], out["carga"])
                        if None not in (out["espalda"], out["brazos"], out["piernas"], out["carga"]) else None)
    return out


def codigo_piernas(m: dict, u: Umbrales, postura_base: str = "auto") -> tuple[int | None, list[str]]:
    """Código nominal de piernas (sin margen): el único posible o None si depende de algo que no se ve."""
    s, notas = piernas(m, u, postura_base, lambda k: 0.0)
    return (next(iter(s)) if len(s) == 1 else None), notas


def piernas_posibles(m: dict, cfg: Config, postura_base: str = "auto", vista=None, modo="") -> frozenset:
    aprox = m.get("_aprox", frozenset())
    mg = (lambda k: 0.0) if cfg.muestreo.sin_margen else (lambda k: margen(k, vista, modo) * (FACTOR_APROXIMADA if k in aprox else 1.0))  # noqa: E731
    return piernas(m, cfg.umbrales, postura_base, mg, getattr(cfg, "supuesto_piernas", None))[0]


def codigo_espalda(m: dict, u: Umbrales) -> tuple[int | None, list[str]]:
    s = R.owas_espalda(R.intervalo(m.get("tronco_flex", nan), 0.0, 0.0), R.intervalo(m.get("tronco_giro", nan), 0.0, 0.0),
                       R.intervalo(m.get("tronco_lat", nan), 0.0, 0.0), u)
    return (next(iter(s)) if len(s) == 1 else None), []


def codigo_brazos(m: dict, u: Umbrales) -> tuple[int | None, list[str]]:
    s = R.owas_brazos(R.intervalo(m.get("brazo_alt_I", nan), 0.0), R.intervalo(m.get("brazo_alt_D", nan), 0.0), u)
    return (next(iter(s)) if len(s) == 1 else None), []
