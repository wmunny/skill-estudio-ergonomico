"""Ficha de acciones técnicas (AT) de OCRA: una entrada por gesto, mano y ciclo, validada en código.

Claude rellena la ficha mirando láminas del ciclo representativo a 4–8 fotogramas por segundo (bloque `ocra` de
revision.json, ver docs/REVISION_VISUAL.md). El código aplica los criterios de recuento de OCRA (Colombini y
Occhipinti; anexo de ISO 11228-3:2007; UNE-EN 1005-5; INSST) y decide cuántas AT cuenta cada entrada. Claude informa,
el código cuenta y el usuario confirma.

Cada entrada:
    {"t": 1.2, "mano": "dch|izq", "gesto": "<uno de GESTOS>", "objeto": "pieza", "confianza": "alta|media|baja",
     "cuenta": true,              # lo que propone el revisor (por defecto true)
     "repeticiones": 1,           # girar, accionar herramienta, golpear, pasadas
     "distancia_m": 0.4,          # transportar
     "con_esfuerzo_o_precision": true,  # introducir, encajar, sacar
     "gesto_distinto": true,      # introducir/encajar justo después de posicionar el mismo objeto
     "regla": "texto libre", "nota": "texto libre"}

Estados: «valida» (cuenta), «no_es_at» (registrada, no cuenta), «rechazada» (el revisor la contaba y la regla dice que
no), «dudosa» (cuenta solo en el extremo alto del rango: confianza baja o falta un dato de la regla).
"""

from __future__ import annotations

# gesto → (AT por unidad, regla, condición especial)
GESTOS = {
    "alcanzar": (0, "Alcanzar no es AT por sí solo: se valora en la postura y forma parte de «coger».", None),
    "coger": (1, "Coger o agarrar: 1 AT.", None),
    "agarrar": (1, "Coger o agarrar: 1 AT.", None),
    "pasar_mano": (1, "Pasar de una mano a otra: 1 AT por mano (anota una entrada en cada mano).", None),
    "posicionar": (1, "Posicionar en un punto definido: 1 AT.", None),
    "introducir": (1, "Introducir con esfuerzo o precisión: 1 AT (aparte de posicionar solo si es un gesto distinto).", "esfuerzo"),
    "encajar": (1, "Encajar con esfuerzo o precisión: 1 AT (aparte de posicionar solo si es un gesto distinto).", "esfuerzo"),
    "sacar": (1, "Sacar con esfuerzo o precisión: 1 AT.", "esfuerzo"),
    "empujar": (1, "Empujar: 1 AT.", None),
    "tirar": (1, "Tirar: 1 AT.", None),
    "presionar": (1, "Presionar: 1 AT.", None),
    "girar": (1, "Girar: 1 AT por giro.", "repeticiones"),
    "coger_herramienta": (1, "Herramienta: coger 1 AT.", None),
    "posicionar_herramienta": (1, "Herramienta: posicionar 1 AT.", None),
    "accionar_herramienta": (1, "Herramienta: 1 AT por accionamiento.", "repeticiones"),
    "devolver_herramienta": (0, "Devolver una herramienta suspendida soltándola es soltar: no es AT.", None),
    "dejar_herramienta_soporte": (1, "Dejar la herramienta en un soporte con precisión es posicionar: 1 AT.", None),
    "soltar": (0, "Soltar o abrir la mano no es AT.", None),
    "abrir_mano": (0, "Soltar o abrir la mano no es AT.", None),
    "transportar": (1, "Transportar: no es AT a menos de 1 m; 1 AT a 1 m o más.", "distancia"),
    "sujetar": (0, "Sujetar estático (mano de apoyo) no es AT: se valora en la postura y el agarre.", None),
    "control_visual": (0, "El control visual no es AT.", None),
    "andar": (0, "Andar no es AT.", None),
    "esperar": (0, "Esperar no es AT.", None),
    "golpear": (1, "Golpes: 1 AT cada uno.", "repeticiones"),
    "pasada": (1, "Pasadas repetidas: 1 AT cada una.", "repeticiones"),
}
TIPO_GESTO = {  # para colorear la línea de tiempo
    "coger": "coger", "agarrar": "coger", "pasar_mano": "coger", "coger_herramienta": "herramienta",
    "posicionar": "posicionar", "posicionar_herramienta": "herramienta", "dejar_herramienta_soporte": "herramienta",
    "accionar_herramienta": "herramienta", "introducir": "encajar", "encajar": "encajar", "sacar": "encajar",
    "empujar": "fuerza", "tirar": "fuerza", "presionar": "fuerza", "girar": "girar", "golpear": "fuerza",
    "pasada": "fuerza", "transportar": "transportar",
}
CONFIANZAS = ("alta", "media", "baja")
DISTANCIA_TRANSPORTE_M = 1.0
VENTANA_DUPLICADO_S = 1.0


class FichaInvalida(ValueError):
    pass


def validar(ficha: dict, duracion_video: float | None = None) -> dict:
    """Aplica las reglas a cada entrada y cuenta las AT por mano y ciclo (rango si hay entradas dudosas)."""
    errores = []
    ciclo = ficha.get("ciclo") or {}
    try:
        c_ini, c_fin = float(ciclo.get("inicio", 0.0)), float(ciclo["fin"]) if "fin" in ciclo else None
    except (TypeError, ValueError):
        c_ini, c_fin = 0.0, None
        errores.append("ocra.ciclo: inicio y fin numéricos")
    if c_fin is not None and c_fin <= c_ini:
        errores.append("ocra.ciclo: fin debe ser mayor que inicio")
    if duracion_video and c_fin is not None and c_fin > duracion_video + 1.0:
        errores.append(f"ocra.ciclo: el ciclo termina después del vídeo ({duracion_video:.1f} s)")
    acciones = ficha.get("acciones", [])
    if not isinstance(acciones, list):
        raise FichaInvalida("ocra.acciones debe ser una lista")
    salida = []
    for i, a in enumerate(acciones):
        donde = f"ocra.acciones[{i}]"
        g = a.get("gesto")
        if g not in GESTOS:
            errores.append(f"{donde}.gesto {g!r} no válido ({', '.join(GESTOS)})")
            continue
        if a.get("mano") not in ("dch", "izq"):
            errores.append(f"{donde}.mano debe ser dch o izq (cada extremidad se cuenta por separado)")
            continue
        if a.get("confianza") not in CONFIANZAS:
            errores.append(f"{donde}.confianza debe ser alta, media o baja")
            continue
        try:
            t = float(a["t"])
        except (KeyError, TypeError, ValueError):
            errores.append(f"{donde}.t (segundo de inicio) es obligatorio")
            continue
        if c_fin is not None and not (c_ini - 0.05 <= t <= c_fin + 0.05):
            errores.append(f"{donde}.t = {t} s fuera del ciclo ({c_ini}–{c_fin} s)")
            continue
        unidad, regla, cond = GESTOS[g]
        rep = a.get("repeticiones", 1)
        if not isinstance(rep, int) or rep < 1:
            errores.append(f"{donde}.repeticiones debe ser un entero ≥ 1")
            continue
        if rep > 1 and cond != "repeticiones":
            errores.append(f"{donde}.repeticiones solo vale para girar, accionar herramienta, golpear o pasadas: "
                           "anota cada gesto en su entrada")
            continue
        propone = a.get("cuenta", True) is not False
        n = unidad * rep
        estado, motivo = None, regla
        if cond == "distancia":
            dist = a.get("distancia_m")
            if dist is None:
                estado, motivo = "dudosa", regla + " Falta distancia_m: cuenta 0–1."
                n = 1
            elif float(dist) < DISTANCIA_TRANSPORTE_M:
                n = 0
                motivo = regla + f" Distancia {float(dist):g} m < 1 m."
        if cond == "esfuerzo":
            ce = a.get("con_esfuerzo_o_precision")
            if ce is False:
                n = 0
                motivo = regla + " Sin esfuerzo ni precisión: forma parte de posicionar o de soltar."
            elif ce is None and estado is None:
                estado, motivo = "dudosa", regla + " No consta si hay esfuerzo o precisión: cuenta 0–1."
        if n == 0:
            estado = "rechazada" if propone else "no_es_at"
            if propone:
                motivo = "No es AT: " + motivo
        elif estado is None:
            estado = "dudosa" if a["confianza"] == "baja" else "valida"
            if estado == "dudosa":
                motivo = regla + " Confianza baja: cuenta solo en el extremo alto del rango."
        if n > 0 and not propone:
            # El revisor no la contaba pero la regla dice que es AT: se cuenta (la regla manda) y se señala.
            motivo = "La regla la cuenta aunque el revisor no la marcó: " + motivo
        salida.append(dict(i=i, t=t, mano=a["mano"], gesto=g, tipo=TIPO_GESTO.get(g, "otro"), objeto=a.get("objeto", ""),
                           confianza=a["confianza"], at=n, estado=estado, motivo=motivo, propuesta=propone,
                           regla_revisor=a.get("regla", ""), nota=a.get("nota", "")))
    # Introducir o encajar justo después de posicionar el mismo objeto con la misma mano: solo si es otro gesto.
    for x in salida:
        if x["gesto"] in ("introducir", "encajar") and x["at"] > 0 and x["estado"] == "valida":
            previo = [y for y in salida if y["mano"] == x["mano"] and y["gesto"] == "posicionar" and y["at"] > 0
                      and y["objeto"] == x["objeto"] and 0 <= x["t"] - y["t"] <= VENTANA_DUPLICADO_S]
            if previo and not acciones[x["i"]].get("gesto_distinto"):
                x["estado"] = "dudosa"
                x["motivo"] = ("Sigue a «posicionar» del mismo objeto: solo cuenta aparte si es un gesto distinto "
                               "(marca gesto_distinto: true). Cuenta 0–1.")
    if errores:
        raise FichaInvalida("ficha de AT no válida:\n- " + "\n- ".join(errores))
    salida.sort(key=lambda x: (x["mano"], x["t"]))
    return dict(ciclo=dict(inicio=c_ini, fin=c_fin, duracion_s=(c_fin - c_ini) if c_fin is not None else None,
                           evidencia=ciclo.get("evidencia", "")),
                acciones=salida, recuento=recuento(salida), confirmada=bool(ficha.get("confirmada")))


def recuento(acciones: list[dict]) -> dict:
    out = {}
    for m in ("dch", "izq"):
        xs = [a for a in acciones if a["mano"] == m]
        seguras = sum(a["at"] for a in xs if a["estado"] == "valida")
        dudosas = sum(a["at"] for a in xs if a["estado"] == "dudosa")
        propuestas = sum(1 for a in xs if a["propuesta"] and a["gesto"] in GESTOS)
        out[m] = dict(min=seguras, max=seguras + dudosas, nominal=seguras if not dudosas else None,
                      propuestas_revisor=propuestas,
                      rechazadas=[dict(t=a["t"], gesto=a["gesto"], objeto=a["objeto"], motivo=a["motivo"])
                                  for a in xs if a["estado"] == "rechazada"],
                      dudosas=[dict(t=a["t"], gesto=a["gesto"], objeto=a["objeto"], motivo=a["motivo"])
                               for a in xs if a["estado"] == "dudosa"],
                      por_tipo=_por_tipo(xs))
    return out


def _por_tipo(xs: list[dict]) -> dict:
    d = {}
    for a in xs:
        if a["at"] > 0 and a["estado"] in ("valida", "dudosa"):
            d[a["tipo"]] = d.get(a["tipo"], 0) + a["at"]
    return d


def misma_accion(acciones: list[dict], mano: str) -> float | None:
    """Fracción de AT del ciclo que son el mismo gesto (aproximación por recuento, no por tiempo)."""
    xs = [a for a in acciones if a["mano"] == mano and a["at"] > 0 and a["estado"] == "valida"]
    tot = sum(a["at"] for a in xs)
    if not tot:
        return None
    por = {}
    for a in xs:
        por[a["gesto"]] = por.get(a["gesto"], 0) + a["at"]
    return max(por.values()) / tot


def at_ciclo_valor(rec: dict, origen: str) -> dict:
    """Valor de entrada para ocra.calcular a partir del recuento de una mano."""
    v = rec["nominal"] if rec["nominal"] is not None else [rec["min"], rec["max"]]
    return dict(valor=v, origen=origen, nota=f"ficha de AT validada en código ({rec['min']}–{rec['max']})"
                if rec["min"] != rec["max"] else "ficha de AT validada en código")
