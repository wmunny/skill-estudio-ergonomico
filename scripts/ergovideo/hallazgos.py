"""Hallazgos ergonómicos del puesto a partir de las medidas y de los métodos. Reglas fijas en código, sin IA.

Un hallazgo es una postura o condición de riesgo que se repite en la tarea: qué es, en qué zona del cuerpo, cuánto
tiempo y cuántas veces ocurre, en qué fases, su gravedad y qué indicadores de OWAS, REBA o RULA lo respaldan.
Los umbrales son los de los métodos (p. ej. brazo ≥ 45° = RULA 3; tronco > 20° = REBA 3 y OWAS espalda doblada);
los que no son de los métodos están marcados como criterio del informe.

Se usan los valores nominales (medida tal cual, sin margen): el informe describe lo que ocurre; los rangos con margen
y la validez están en el detalle técnico.
"""

from __future__ import annotations

import math

import numpy as np

from . import tablas as T
from .catalogo import CATALOGO, medidas

LADO = {"I": "izquierdo", "D": "derecho"}
EXTENSION_CUELLO = -10.0     # criterio del informe: extensión clara del cuello (el método no da grados)
MIN_EPISODIO_S = 0.3         # duración mínima de un episodio para contarlo
MIN_PORCENTAJE = 5.0         # por debajo, solo se informa si la postura es severa

URGENCIAS = ["No requiere actuación", "Conviene estudiarlo", "Actuar a medio plazo", "Actuar cuanto antes",
             "Actuar de inmediato"]


def urgencia_reba(p: int) -> int:
    return T.reba_nivel(p)[1]  # 0..4


def urgencia_rula(p: int) -> int:
    return {1: 0, 2: 1, 3: 3, 4: 4}[T.rula_nivel(p)[1]]


def urgencia_owas(c: int) -> int:
    return {1: 0, 2: 2, 3: 3, 4: 4}[c]


def _episodios(v: np.ndarray, t: np.ndarray) -> list[tuple[int, int]]:
    out, i, n = [], 0, len(v)
    dt = float(np.median(np.diff(t))) if n > 1 else 0.1
    while i < n:
        if not v[i]:
            i += 1
            continue
        e = i
        while e + 1 < n and v[e + 1]:
            e += 1
        if (e - i + 1) * dt >= MIN_EPISODIO_S - 1e-9:
            out.append((i, e))
        i = e + 1
    return out


def _fases(v: np.ndarray, t: np.ndarray, fases: list[dict]) -> list[str]:
    nombres = []
    for f in fases:
        m = (t >= float(f["inicio"])) & (t <= float(f["fin"]))
        if m.any() and v[m].mean() >= 0.3 and f.get("descripcion") not in nombres:
            nombres.append(f.get("descripcion", ""))
    return nombres


def _gravedad(pct: float, pct_severa: float, region: str, repetitiva: bool) -> str:
    sup = region in ("hombro", "muneca", "cuello")
    if (pct_severa >= 5 and pct >= 10) or pct >= 30 or (repetitiva and sup and pct >= 15):
        return "alta"
    if pct >= 10 or pct_severa >= 5 or (repetitiva and sup and pct >= 5):
        return "media"
    return "baja"


def _mun_ia(rev: dict | None, t: float, lado: str) -> dict | None:
    from .revision import munecas_en
    return munecas_en(rev, t).get(lado)


def detectar(res: dict, tarea, rev: dict | None, nombre: str) -> list[dict]:
    """Hallazgos posturales de un vídeo (sin margen) y condiciones de la tarea."""
    t = res["t"]
    s = res["series"]
    fases = (rev or {}).get("fases", [])
    repetitiva = bool(tarea.actividad.get("repetitiva"))
    out = []

    def add(tipo, cond, conocido, severa, magnitud, lado=None, punto=None, etiqueta=None, evidencia=None):
        cond = cond & conocido
        n_con = int(conocido.sum())
        if n_con == 0:
            return
        # % sobre todo el tiempo analizado (con persona detectada). Si la zona no se ve siempre, es un mínimo:
        # el % sobre el tiempo visible estaría sesgado (p. ej. un brazo que solo se ve cuando alcanza).
        n_tot = max(int(res["detectado"].sum()), n_con)
        visible = 100 * n_con / n_tot
        pct = 100 * cond.sum() / n_tot
        pct_sev = 100 * (severa & cond).sum() / n_tot
        eps = _episodios(cond, t)
        if not eps or (pct < MIN_PORCENTAJE and pct_sev < MIN_PORCENTAJE / 2):
            return
        dur_min = n_tot * (float(np.median(np.diff(t))) if len(t) > 1 else 0.1) / 60
        mag = np.where(cond, magnitud, -np.inf)
        k = int(np.argmax(mag))
        region = CATALOGO[tipo]["region"]
        out.append(dict(
            id=f"{tipo}{'_' + lado if lado else ''}", tipo=tipo, lado=lado, region=region, video=nombre,
            titulo=CATALOGO[tipo]["titulo"] + (f" ({LADO[lado]})" if lado else ""), riesgo=CATALOGO[tipo]["riesgo"],
            porcentaje=pct, porcentaje_severa=pct_sev, visible=visible, minimo=visible < 80, episodios=len(eps), por_minuto=len(eps) / dur_min if dur_min else 0,
            duracion_media_s=float(np.mean([t[e] - t[i] for i, e in eps])) + (float(np.median(np.diff(t))) if len(t) > 1 else 0.1),
            fases=_fases(cond, t, fases), indice=k, t_ejemplo=float(t[k]), valor_ejemplo=float(magnitud[k]),
            punto=punto, etiqueta=(etiqueta or "").format(v=magnitud[k]),
            gravedad=_gravedad(pct, pct_sev, region, repetitiva), evidencia=evidencia or [], _mascara=cond))

    nan = np.isnan
    # Espalda
    sag = s["tronco_sag"]
    add("tronco_flexion", np.abs(np.nan_to_num(sag)) > 20, ~nan(sag), np.nan_to_num(sag) > 60, np.abs(np.nan_to_num(sag)),
        punto=(11, 12, 23, 24), etiqueta="Tronco {v:.0f}°",
        evidencia=["REBA tronco ≥ 3 (flexión o extensión > 20°)", "RULA tronco ≥ 3 (≥ 20°)", "OWAS espalda doblada (> 20°)"])
    g, la = s["tronco_giro"], s["tronco_lat"]
    giro = np.fmax(np.nan_to_num(g, nan=-1), np.nan_to_num(la, nan=-1))
    add("tronco_giro", giro > 20, ~(nan(g) & nan(la)), giro > 45, giro, punto=(11, 12), etiqueta="Giro {v:.0f}°",
        evidencia=["REBA y RULA: +1 por torsión o inclinación lateral (> 20°, criterio de detección)", "OWAS espalda con giro (> 20°)"])
    # Cuello
    c = s["cuello"]
    add("cuello_flexion", np.nan_to_num(c) > 20, ~nan(c), np.nan_to_num(c) > 40, np.nan_to_num(c), punto=(7, 8),
        etiqueta="Cuello {v:.0f}°", evidencia=["RULA cuello 3 (flexión ≥ 20°)", "REBA cuello 2 (flexión > 20°)"])
    add("cuello_extension", np.nan_to_num(c) < EXTENSION_CUELLO, ~nan(c), np.nan_to_num(c) < -20, -np.nan_to_num(c),
        punto=(7, 8), etiqueta="Cuello −{v:.0f}°", evidencia=["RULA cuello 4 (extensión)", "REBA cuello 2 (extensión)"])
    # Miembro superior, por lado
    for lado in "ID":
        bf, abd, alt = s[f"brazo_flex_{lado}"], s[f"brazo_abd_{lado}"], s[f"brazo_alt_{lado}"]
        codo, lat = s[f"codo_{lado}"], s[f"antebrazo_lat_{lado}"]
        hombro, codo_i, muneca_i = (11, 13, 15) if lado == "I" else (12, 14, 16)
        sobre_hombro = np.nan_to_num(alt, nan=-9) >= 0
        add("brazo_elevado", (np.nan_to_num(bf) >= 45) | sobre_hombro, ~(nan(bf) & nan(alt)),
            (np.nan_to_num(bf) >= 90) | sobre_hombro, np.nan_to_num(bf), lado=lado, punto=(codo_i,),
            etiqueta="Brazo {v:.0f}°", evidencia=["RULA brazo ≥ 3 (≥ 45°); 4 a partir de 90°", "REBA brazo ≥ 3 (> 45°)",
                                                  "OWAS: brazo con codo o mano al nivel del hombro o por encima"])
        add("brazo_abducido", np.nan_to_num(abd) > 30, ~nan(abd), np.nan_to_num(abd) > 60, np.nan_to_num(abd), lado=lado,
            punto=(codo_i,), etiqueta="Separación {v:.0f}°", evidencia=["REBA y RULA: +1 por brazo abducido (> 30°, criterio de detección)"])
        lejos = ((np.nan_to_num(bf) >= 45) & (np.nan_to_num(codo, nan=90) < 60)) | \
            (np.nan_to_num(lat, nan=1) <= 0) | (np.nan_to_num(lat, nan=1) >= 2)
        add("alcance", lejos, ~nan(bf), (np.nan_to_num(bf) >= 60) & (np.nan_to_num(codo, nan=90) < 30),
            np.nan_to_num(bf), lado=lado, punto=(muneca_i,), etiqueta="Alcance",
            evidencia=["RULA antebrazo +1 (a un lado o cruzando la línea media)", "RULA antebrazo 2 (codo < 60°, brazo extendido)"])
        # Muñeca: declarada, estimada por la IA por fase o, si no hay nada, la medida tosca
        if tarea.muneca:
            mala = np.full(len(t), tarea.muneca == "mas15" or bool(tarea.muneca_desviada))
            conocida = np.ones(len(t), bool)
            origen = "declarada"
        else:
            mala, conocida = np.zeros(len(t), bool), np.zeros(len(t), bool)
            for i, ti in enumerate(t):
                ia = _mun_ia(rev, float(ti), lado)
                if ia:
                    conocida[i] = True
                    mala[i] = ia["flexion"] == "mas15" or bool(ia.get("desviada")) or bool(ia.get("girada"))
            origen = "estimada en la revisión visual"
            if not conocida.any():
                mm = s[f"muneca_{lado}"]
                mala, conocida, origen = np.nan_to_num(mm) > 15, ~nan(mm), "medida (poco fiable)"
        add("muneca", mala, conocida, mala, mala.astype(float), lado=lado, punto=(muneca_i,), etiqueta="Muñeca",
            evidencia=[f"RULA muñeca 3 (> 15°) o desviada; REBA muñeca 2 (> 15°) o +1 por desviación (muñeca {origen})"])
    # Piernas (de pie; sentado no genera hallazgo)
    if (rev or {}).get("contexto", {}).get("postura_base") != "sentado":
        rod = np.fmax(np.nan_to_num(s["rodilla_I"], nan=-1), np.nan_to_num(s["rodilla_D"], nan=-1))
        tob = np.abs(np.nan_to_num(s["tobillos"]))
        cono = ~(nan(s["rodilla_I"]) & nan(s["rodilla_D"]))
        add("piernas", (rod >= 30) | (tob > 0.08), cono, rod > 60, rod, punto=(25, 26), etiqueta="Rodilla {v:.0f}°",
            evidencia=["REBA piernas +1 (30–60°) o +2 (> 60°)", "OWAS piernas flexionadas o sobre una pierna"])
    # «Brazo separado» y «alcance» del mismo lado suelen ser el mismo gesto: si coinciden, se deja el alcance.
    quitar = set()
    for lado in "ID":
        a = next((h for h in out if h["id"] == f"brazo_abducido_{lado}"), None)
        b = next((h for h in out if h["id"] == f"alcance_{lado}"), None)
        if a and b:
            comun = (a["_mascara"] & b["_mascara"]).sum() / max(1, a["_mascara"].sum())
            if comun >= 0.7:
                quitar.add(a["id"])
                b["evidencia"] = b["evidencia"] + a["evidencia"]
    out = [h for h in out if h["id"] not in quitar]
    for h in out:
        h.pop("_mascara", None)
    return out


def condiciones(tarea) -> list[dict]:
    """Factores de la tarea declarados o confirmados: repetitividad, carga, postura estática, agarre."""
    out = []

    def add(tipo, gravedad, detalle, evidencia):
        out.append(dict(id=tipo, tipo=tipo, lado=None, region=CATALOGO[tipo]["region"], titulo=CATALOGO[tipo]["titulo"],
                        riesgo=CATALOGO[tipo]["riesgo"], gravedad=gravedad, detalle=detalle, evidencia=evidencia,
                        porcentaje=None, episodios=None, fases=[]))
    if tarea.actividad.get("repetitiva"):
        add("repetitividad", "alta", "El ciclo se repite más de 4 veces por minuto.",
            ["REBA actividad +1 (repetitiva)", "RULA actividad muscular +1 (> 4 veces/min)"])
    if tarea.actividad.get("estatica"):
        add("estatica", "media", "Alguna parte del cuerpo se mantiene en la misma postura más de 1 minuto.",
            ["REBA actividad +1 (estática)", "RULA actividad muscular +1"])
    kg = tarea.carga_kg
    if (kg is not None and kg >= 5) or tarea.fuerza_brusca:
        g = "alta" if (kg or 0) > 10 or tarea.fuerza_brusca else "media"
        add("carga", g, f"Carga o fuerza de unos {kg:g} kg" + (" con golpes o fuerzas bruscas" if tarea.fuerza_brusca else "") + ".",
            ["REBA carga/fuerza +1 (5–10 kg) o +2 (> 10 kg)", "RULA carga/fuerza ≥ 2", "OWAS carga"])
    if tarea.agarre is not None and tarea.agarre >= 2:
        add("agarre", "alta" if tarea.agarre == 3 else "media", "Agarre " + {2: "malo", 3: "inaceptable"}[tarea.agarre] + ".",
            ["REBA agarre +2 o +3"])
    return out


def owas_frecuencia(resumen: dict | None) -> list[dict]:
    """Hallazgos que salen de la tabla de frecuencias de OWAS y no tienen una postura concreta que medir:
    trabajo de pie o sentado prolongado (piernas 2 o 1 con categoría ≥ 2 por su % del tiempo)."""
    out = []
    if not resumen:
        return out
    for codigo, tipo in ((2, "de_pie"), (1, "sentado")):
        d = resumen["regiones"]["piernas"]["codigos"].get(codigo)
        if d and (d["categoria"] or 1) >= 2:
            out.append(dict(id=tipo, tipo=tipo, lado=None, region="piernas", titulo=CATALOGO[tipo]["titulo"],
                            riesgo=CATALOGO[tipo]["riesgo"], gravedad="media" if d["categoria"] == 2 else "alta",
                            detalle=f"{d['nombre']} el {d['porcentaje']:.0f} % del tiempo observado.".replace(".", ",", 1),
                            porcentaje=d["porcentaje"], episodios=None, fases=[],
                            evidencia=[f"OWAS: piernas código {codigo} («{d['nombre'].lower()}») el {d['porcentaje']:.0f} % "
                                       f"del tiempo → categoría {d['categoria']} por frecuencia"]))
    return out


def _palabras_reba(pk):
    a, b = T.reba_nivel(pk["pico"]), T.reba_nivel(pk["pico_max"])
    return a[2] if a == b else f"{a[2]} a {b[2].lower()}"


def indicadores(ergos: dict, resumen: dict | None, metodos: list[str]) -> list[dict]:
    """Un indicador por método, en palabras, priorizando el peor caso del rango."""
    out = []
    if "reba" in metodos:
        picos = [(n, d["reba"]) for n, d in ergos.items() if d.get("reba", {}).get("evaluable")]
        if picos:
            n, pk = max(picos, key=lambda x: (x[1]["pico_max"], x[1]["pico"]))
            u = urgencia_reba(pk["pico_max"])
            out.append(dict(metodo="REBA", que="Peor postura del cuerpo entero", nivel=_palabras_reba(pk), urgencia=u,
                            accion=T.reba_nivel(pk["pico_max"])[3], detalle=f"a los {pk['t_pico']:.1f} s".replace(".", ","),
                            video=n))
    if "rula" in metodos:
        picos = [(n, s, d["rula"][s]) for n, d in ergos.items() if "rula" in d for s in "ID" if d["rula"][s].get("evaluable")]
        if picos:
            n, s, pk = max(picos, key=lambda x: (x[2]["pico_max"], x[2]["pico"]))
            a, b = T.rula_nivel(pk["pico"]), T.rula_nivel(pk["pico_max"])
            out.append(dict(metodo="RULA", que=f"Peor postura del brazo {LADO[s]}",
                            nivel=a[2] if a == b else f"{a[2]} a {b[2].lower()}", urgencia=urgencia_rula(pk["pico_max"]),
                            accion=b[3], detalle=f"a los {pk['t_pico']:.1f} s".replace(".", ","), video=n))
    if "owas" in metodos and resumen:
        c = resumen["combinaciones"]
        cat = c["categoria_max"] or 1
        pct2 = sum(v["porcentaje"] for k, v in c["por_categoria"].items() if k >= 2)
        frec = [(d["categoria"] or 1, d["porcentaje"], reg, d["nombre"]) for reg, r in resumen["regiones"].items()
                for d in r["codigos"].values()]
        f_cat, f_pct, f_reg, f_nom = max(frec, key=lambda x: (x[0], x[1]))
        peor = max(cat, f_cat)
        if f_cat >= cat and f_cat >= 2:
            detalle = f"por el tiempo en «{f_nom.lower()}» ({f_pct:.0f} % del tiempo)".replace(".", ",")
        else:
            detalle = f"{pct2:.0f} % del tiempo en posturas que piden actuar".replace(".", ",")
        out.append(dict(metodo="OWAS", que="Posturas a lo largo del tiempo", nivel=T.CATEGORIAS[peor][0],
                        urgencia=urgencia_owas(peor), accion=T.CATEGORIAS[peor][1], detalle=detalle))
    return out


def prioridad(gravedad: str, urgencia_global: int) -> str:
    """Por la gravedad del problema; «Inmediata» solo si además algún método pide actuar de inmediato."""
    if gravedad == "alta":
        return "Inmediata" if urgencia_global >= 4 else "Alta"
    return "Media" if gravedad == "media" else "Baja"


def plan(hallazgos: list[dict], urgencia_global: int, por_hallazgo: int = 2) -> list[dict]:
    """Las primeras medidas del catálogo de cada hallazgo (las de diseño del puesto van primero), por prioridad."""
    orden = {"Inmediata": 0, "Alta": 1, "Media": 2, "Baja": 3}
    por_medida = {}
    for h in hallazgos:
        pr = prioridad(h["gravedad"], urgencia_global)
        for m in medidas(h["tipo"])[:por_hallazgo]:
            x = por_medida.setdefault(m["id"], dict(m, hallazgos=[], prioridad=pr, origen="catálogo"))
            x["hallazgos"].append(h["id"])
            if orden[pr] < orden[x["prioridad"]]:
                x["prioridad"] = pr
    tipos = {"ingenieria": 0, "organizativa": 1, "formacion": 2}
    return sorted(por_medida.values(), key=lambda m: (orden[m["prioridad"]], tipos[m["tipo"]]))


def ordenar(hallazgos: list[dict]) -> list[dict]:
    g = {"alta": 0, "media": 1, "baja": 2}
    return sorted(hallazgos, key=lambda h: (g[h["gravedad"]], -(h.get("porcentaje") or 0)))


def serie_riesgo(fs: list[dict], max_puntos: int = 240) -> dict:
    """Nivel de actuación por instante (REBA y peor lado de RULA, valor mínimo del rango) para la línea de tiempo."""
    t = np.array([f["t"] for f in fs])
    reba = np.array([f["reba"]["rango"][0] if f.get("reba") else np.nan for f in fs], float)
    rula = np.array([max([f["rula"][s]["rango"][0] for s in "ID" if f.get("rula") and f["rula"].get(s)] or [np.nan])
                     for f in fs], float)
    paso = max(1, int(math.ceil(len(t) / max_puntos)))
    sel = slice(None, None, paso)
    u_reba = [None if np.isnan(x) else urgencia_reba(int(x)) for x in reba[sel]]
    u_rula = [None if np.isnan(x) else urgencia_rula(int(x)) for x in rula[sel]]
    return dict(t=[float(x) for x in t[sel]], reba=u_reba, rula=u_rula, duracion=float(t[-1]) if len(t) else 0.0)
