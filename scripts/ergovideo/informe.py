"""Informe del estudio OWAS, REBA y RULA en Markdown y en HTML autocontenido (mismo contenido)."""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime
from pathlib import Path

from . import tablas as T
from .config import FACTOR_FRONTAL, MARGENES
from .grabacion import GENERALES
from .reglas import CONVENCIONES
from .tablas import BRAZOS, CARGA, CATEGORIAS, CONVENCION_CARGA_OWAS, ESPALDA, PIERNAS

LUZ = {"verde": "🟢", "ambar": "🟠", "rojo": "🔴"}
NOMBRES = {"espalda": ESPALDA, "brazos": BRAZOS, "piernas": PIERNAS}
NOTAS = {
    "giro_no_medido": "torsión no medible (entra en el rango)",
    "lateral_no_medida": "inclinación lateral no medible (entra en el rango)",
    "un_brazo_no_visible": "un brazo no visible (entra en el rango)",
    "una_pierna_no_visible": "una pierna no visible (entra en el rango)",
    "sentado_declarado": "sentado (declarado o estimado en la revisión)",
    "rodillas_supuestas": "rodillas no visibles: se usa la flexión declarada o estimada",
    "apoyo_supuesto": "pies no visibles: se usa el apoyo declarado o estimado",
    "espalda_no_visible": "espalda no visible",
    "brazos_no_visibles": "brazos no visibles",
    "piernas_no_visibles": "piernas no visibles",
}
MEDIDA_TXT = {
    "tronco_sag": "tronco (flexión + / extensión −)", "cuello": "cuello", "brazo_flex_I": "brazo izq.", "brazo_flex_D": "brazo dch.",
    "codo_I": "codo izq.", "codo_D": "codo dch.", "rodilla_I": "rodilla izq.", "rodilla_D": "rodilla dch.",
    "brazo_abd_I": "abducción brazo izq.", "brazo_abd_D": "abducción brazo dch.", "muneca_I": "muñeca izq. (estimada)",
    "muneca_D": "muñeca dch. (estimada)", "tronco_giro": "torsión del tronco", "tronco_lat": "inclinación lateral del tronco",
    "antebrazo_lat_I": "muñeca izq. respecto a la línea media", "antebrazo_lat_D": "muñeca dch. respecto a la línea media",
}
AVISO = ("**Demostración no validada.** Las posturas salen de un modelo de visión artificial (MediaPipe Pose) aplicado a "
         "vídeo de una sola cámara por toma, con reglas y umbrales que no se han contrastado con observaciones de un "
         "ergónomo. Este informe no sustituye a una evaluación de riesgos ni al criterio de un técnico de prevención.")


def _f(x, d=0):
    return "—" if x is None or x != x else f"{x:.{d}f}".replace(".", ",")


def _seg(s):
    m, s = divmod(int(round(s)), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def _r(v) -> str:
    if isinstance(v, (list, tuple, set, frozenset)):
        v = list(v)
        return str(v[0]) if min(v) == max(v) else f"{min(v)}–{max(v)}"
    return str(v)


ELEMENTOS = {
    "reba": [("tronco", "Tronco"), ("cuello", "Cuello"), ("piernas", "Piernas"), ("carga", "Carga/fuerza"),
             ("actividad", "Actividad")],
    "rula": [("brazo", "Brazo"), ("antebrazo", "Antebrazo"), ("muneca", "Muñeca"), ("giro", "Giro de muñeca"),
             ("cuello", "Cuello"), ("tronco", "Tronco"), ("piernas", "Piernas"), ("musculo", "Actividad muscular"),
             ("fuerza", "Carga/fuerza")],
}
ESTADO = {"concluyente": "concluyente (un nivel de actuación)", "acotada": "acotada (dos niveles contiguos)",
          "incompleta": "incompleta (más de dos niveles)"}


def _nivel_owas(r: dict) -> tuple[str, list[str]]:
    orden = ["verde", "ambar", "rojo"]
    niveles = [x["nivel_cobertura"] for x in r["regiones"].values()] + [x["nivel_muestra"] for x in r["regiones"].values()]
    nivel = max(niveles, key=orden.index) if niveles else "rojo"
    motivos = []
    margen = max(x["margen_max"] for x in r["regiones"].values())
    if margen > 10:
        motivos.append(f"intervalo aproximado del % de tiempo de ±{_f(margen)} puntos")
    if r["duracion_s"] < 20 * 60:
        motivos.append(f"grabación de {_seg(r['duracion_s'])} (OWAS pide 20–40 min)")
        if nivel == "verde":
            nivel = "ambar"
    for reg, x in r["regiones"].items():
        if x["nivel_cobertura"] != "verde":
            motivos.append(f"{reg}: código nominal conocido en el {_f(x['cobertura'])} % de las observaciones")
    return nivel, motivos


def _pico_txt(pk: dict) -> str:
    return _r((pk["pico"], pk["pico_max"]))


def markdown(ctx: dict) -> str:
    r, diags, a = ctx["resumen"], ctx["diagnosticos"], ctx["args"]
    metodos = ctx.get("metodos", ["owas"])
    ergo_v = ctx.get("ergo", {})
    L = []
    w = L.append
    w("# Estudio ergonómico a partir de vídeo: " + ", ".join(m.upper() for m in metodos))
    w("")
    w(f"> {AVISO}")
    w("")
    w(f"Generado el {datetime.now():%d/%m/%Y %H:%M} con la skill *estudio-ergonomico-video* "
      f"(MediaPipe Pose, modelo «{diags[0]['modelo']}»).")
    w("")

    # ---------------------------------------------------------------- resumen
    w("## Resumen")
    w("")
    w("**Cómo leer este informe.** Las puntuaciones se calculan con reglas y tablas en código. Cada ángulo lleva un margen "
      "de medida provisional; si el margen cruza un umbral, o falta un dato (no se ve o no se ha declarado), la puntuación "
      "se da como **rango**. Lo desconocido nunca se sustituye por el valor favorable. Los semáforos miden cobertura y "
      "certeza del cálculo, no la exactitud de la medida.")
    w("")
    w("| Método | Qué evalúa | Vídeo | Validez técnica (provisional) | Por qué |")
    w("|---|---|---|---|---|")
    if "owas" in metodos:
        nv, mot = _nivel_owas(r)
        w(f"| OWAS | % del tiempo observable en cada postura | todos | {LUZ[nv]} | {'; '.join(mot) or 'cobertura y muestra suficientes'} |")
    for nombre, d in ergo_v.items():
        if "reba" in d:
            v = d["reba_val"]
            w(f"| REBA | peor postura (dos lados) | {nombre} | {LUZ[v['nivel']]} | {' '.join(v['motivos']) or 'peor postura visible, medida y acotada'} |")
        if "rula" in d:
            for s in "ID":
                v = d["rula_val"][s]
                w(f"| RULA | peor postura, lado {'izq.' if s == 'I' else 'dch.'} | {nombre} | {LUZ[v['nivel']]} | "
                  f"{' '.join(v['motivos']) or 'peor postura visible, medida y acotada'} |")
    w("")
    for nombre, d in ergo_v.items():
        if "reba" in d:
            pk = d["reba"]
            if pk.get("evaluable"):
                w(f"- **REBA · {nombre}:** peor postura sostenida **{_pico_txt(pk)}** a los {_f(pk['t_pico'], 1)} s → nivel "
                  f"{_r((pk['nivel'][1], pk['nivel_max'][1]))} ({pk['nivel'][2].lower()}"
                  f"{'' if pk['nivel'] == pk['nivel_max'] else ' a ' + pk['nivel_max'][2].lower()}); {ESTADO[pk['estado']]}.")
            else:
                w(f"- **REBA · {nombre}:** no evaluable.")
        if "rula" in d and d.get("rula_lado"):
            s = d["rula_lado"]
            pk = d["rula"][s]
            w(f"- **RULA · {nombre}:** peor lado {'izquierdo' if s == 'I' else 'derecho'}, peor postura sostenida "
              f"**{_pico_txt(pk)}** a los {_f(pk['t_pico'], 1)} s → nivel {_r((pk['nivel'][1], pk['nivel_max'][1]))}; "
              f"{ESTADO[pk['estado']]}.")
    if "owas" in metodos:
        comb = r["combinaciones"]
        cats = comb["por_categoria"]
        w(f"- **OWAS · observaciones:** {r['n_observaciones']} cada {_f(r['intervalo_s'], 1)} s sobre {_seg(r['duracion_s'])}; "
          f"{comb['codificables']} ({_f(comb['cobertura'])} %) con código nominal completo; {comb['inciertas']} con categoría "
          "incierta por el margen o por datos que faltan.")
        if comb["codificables"]:
            w("- **OWAS · categorías de las combinaciones (nominal; rango):** " + "; ".join(
                f"{c} {_f(cats[c]['porcentaje'])} % ({_f(cats[c]['rango'][0])}–{_f(cats[c]['rango'][1])} %)" for c in (1, 2, 3, 4)) + ".")
        w(f"- **OWAS · categoría más alta:** nominal {comb['categoria_max'] or '—'}; posible {comb['categoria_max_posible'] or '—'}.")
    w("")
    if r["avisos"] and "owas" in metodos:
        w("**Avisos de OWAS**")
        w("")
        for x in r["avisos"]:
            w(f"- ⚠️ {x}")
        w("")
    tarea = ctx.get("tarea")
    if tarea is not None and ("reba" in metodos or "rula" in metodos):
        faltan = tarea.no_declarados()
        if faltan:
            w("**Datos desconocidos (se recorren todos sus valores):** " + "; ".join(faltan) + ".")
            w("")
        ia = [k for k, v in (ctx.get("origenes") or {}).items() if v == "estimado por IA"]
        if ia:
            w("**Datos estimados por la revisión visual sin confirmar:** " + ", ".join(ia).replace("_", " ") + ".")
            w("")

    # ---------------------------------------------------------------- datos
    w("## Datos de partida")
    w("")
    w("| Vídeo | Duración | Resolución | Análisis | Persona detectada | Vista (mediana) | De frente · 45° · de perfil | De espaldas | Ángulos en 2D |")
    w("|---|---|---|---|---|---|---|---|---|")
    for d in diags:
        w(f"| {Path(d['video']).name} | {_seg(d['duracion_s'])} | {d['ancho']}×{d['alto']} | {_f(d['fps_analisis'])} fps | "
          f"{_f(d['deteccion'])} % | {_f(d['vista_mediana'])}° | {_f(d['vista_frontal'])} · {_f(d['vista_45'])} · "
          f"{_f(d['vista_lateral'])} % | {_f(d['de_espaldas'])} % | {_f(d['modo_2d'])} % |")
    w("")
    w(f"- **Carga:** {a.get('carga_texto')}.")
    if a.get("turno_h"):
        w(f"- **Duración del turno:** {_f(a['turno_h'], 1)} h.")
    w(f"- **Varios vídeos:** {a['modo_texto']}.")
    w(f"- **Ángulos:** {a['angulos']} (auto: 2D de perfil, 3D en el resto).")
    w("- **Margen de medida:** " + ("ninguno (comparación sin margen)." if ctx.get("sin_margen") else
      "provisional por zona: " + ", ".join(f"{k.replace('_', ' ')} ±{_f(v, 2 if v < 1 else 0)}" for k, v in MARGENES.items())
      + f"; ×{_f(FACTOR_FRONTAL, 1)} de frente o de espaldas."))
    w("- **Convenciones de frontera:** " + " ".join(f"{k}: {v}" for k, v in CONVENCIONES.items()) +
      f" Carga OWAS: {CONVENCION_CARGA_OWAS}.")
    w("")

    _seccion_tarea(w, ctx)
    _seccion_revision(w, ctx)

    # ---------------------------------------------------------------- REBA y RULA
    if "reba" in metodos or "rula" in metodos:
        _seccion_ergo(w, ctx)

    # ---------------------------------------------------------------- OWAS
    if "owas" in metodos:
        _seccion_owas(w, ctx)

    # ---------------------------------------------------------------- capturas OWAS y vídeo
    caps = [c for c in ctx["capturas"] if c.get("metodo") == "owas"]
    if caps or ctx["videos"]:
        w("## Esqueleto superpuesto")
        w("")
        w("Verde: puntos usados; rojo: segmento con un punto rechazado; aspa roja: punto rechazado por los filtros; gris: "
          "visibilidad baja. La cara está difuminada. Si el esqueleto no coincide con el cuerpo, la observación no vale.")
        w("")
        for v in ctx["videos"]:
            w(f"- Vídeo: [{Path(v).name}]({v})")
        w("")
        for cap in caps:
            w(f"**{cap['titulo']}**")
            w("")
            w(f"![{cap['titulo']}]({cap['ruta']})")
            w("")

    # ---------------------------------------------------------------- recomendaciones
    w("## Recomendaciones de grabación")
    w("")
    especificos = [(Path(d["video"]).name, c) for d in diags for c in d["consejos"]]
    if especificos:
        w("**Para estos vídeos:**")
        w("")
        for v, c in especificos:
            w(f"- *{v}*: {c}")
        w("")
    w("**En general:**")
    w("")
    for c in GENERALES:
        w(f"- {c}")
    w("")

    # ---------------------------------------------------------------- método
    w("## Método y limitaciones")
    w("")
    u = ctx["umbrales"]
    w("- **Cálculo determinista:** reglas por elemento en `reglas.py` y tablas en `tablas.py`. El modelo de lenguaje no puntúa.")
    w("- **Margen de medida y datos desconocidos:** cada regla recibe el intervalo «medida ± margen» o «desconocido» y "
      "devuelve todas las puntuaciones posibles; las tablas se consultan con todas las combinaciones. Los márgenes son "
      "provisionales hasta calibrarlos con vídeos anotados.")
    w(f"- **OWAS:** una observación cada {_f(r['intervalo_s'], 1)} s con un único fotograma real (el más cercano con más "
      "regiones medidas). Porcentajes sobre el tiempo observable; el intervalo es aproximado (Wilson con una muestra "
      "efectiva por código estimada con el tiempo de decorrelación); su cobertura del 95 % no está verificada.")
    w(f"- **Criterios de detección propios (no del método):** torsión o inclinación lateral presente (REBA/RULA) > "
      f"{_f(u.giro_presente)}°; brazo abducido > {_f(u.brazo_abducido)}°; antebrazo en la línea media ≤ {_f(u.antebrazo_cruza, 1)} "
      f"o a un lado ≥ {_f(u.antebrazo_fuera, 1)} semianchos de hombros; OWAS andando > {_f(u.andando_velocidad, 1)} troncos/s, "
      f"arrodillado (pantorrilla > {_f(u.arrodillado_pierna)}°), sentado (muslo ≥ {_f(u.sentado_muslo)}°, pantorrilla ≤ "
      f"{_f(u.sentado_pierna)}°), pie levantado (> {_f(u.pie_levantado_m * 100)} cm).")
    w("- **Apoyo de las piernas en REBA y RULA:** desde los códigos OWAS posibles, con rango donde no se puede saber "
      "(arrodillado, sentado sin ver los pies, andando). Se puede declarar con `--apoyo-piernas`.")
    w("- **Peor postura (REBA, RULA):** dos resúmenes: la sostenida (máximo de la puntuación mínima en ventanas de 0,5 s) y "
      "el pico breve fiable (fotogramas sin valores interpolados, con su duración). Ninguno sustituye a revisar el vídeo.")
    w("- **RULA:** se evalúan los dos lados y se resume con el peor, sin mezclar segmentos de lados distintos.")
    w("- **Muñeca:** MediaPipe Pose solo da tres puntos toscos de la mano; su ángulo mezcla flexión y desviación. Para "
      "cerrar el rango, declárala.")
    w("- **Filtros mecánicos:** longitud de huesos, coherencia 2D–3D, rango, atípicos, saltos y relleno de huecos de hasta "
      "0,3 s. Son parámetros de filtrado pendientes de calibración, no umbrales de exactitud.")
    w("- **Lo que no mide:** el peso real y las fuerzas (se declaran), la duración de cada postura mantenida y la "
      "repetitividad. La torsión del tronco con una sola cámara es la medida menos fiable.")
    w("")
    w(f"> {AVISO}")
    w("")
    return "\n".join(L)


CAMPOS_TAREA = [
    ("postura_base", "Postura de base"), ("carga_kg", "Carga o fuerza (kg)"), ("fuerza_brusca", "Fuerzas bruscas"),
    ("agarre", "Agarre"), ("actividad_estatica", "Postura estática > 1 min"), ("actividad_repetitiva", "Repetitiva > 4/min"),
    ("actividad_cambios", "Cambios bruscos o base inestable"), ("apoyo_piernas", "Apoyo de las piernas"),
    ("rodillas", "Rodillas (si no se ven)"), ("hombro_elevado", "Hombro elevado"), ("brazo_apoyado", "Brazo apoyado"),
    ("brazo_rotado", "Brazo rotado (REBA)"), ("cuello_girado", "Cuello rotado"), ("cuello_inclinado", "Cuello inclinado"),
]
AGARRES = {0: "bueno", 1: "regular", 2: "malo", 3: "inaceptable"}


def _valor_tarea(campo, tarea, postura):
    if campo == "postura_base":
        return {"auto": "detectada en cada fotograma", "sentado": "sentado", "de_pie": "de pie"}.get(postura, postura)
    if campo.startswith("actividad_"):
        v = tarea.actividad.get(campo[10:])
    elif campo == "agarre":
        v = AGARRES.get(tarea.agarre) if tarea.agarre is not None else None
    elif campo == "carga_kg":
        v = None if tarea.carga_kg is None else _f(tarea.carga_kg, 1)
    else:
        v = getattr(tarea, campo)
    return "—" if v is None else ("sí" if v is True else "no" if v is False else str(v))


def _seccion_tarea(w, ctx: dict) -> None:
    tarea, orig = ctx.get("tarea"), ctx.get("origenes") or {}
    if tarea is None:
        return
    w("### Datos de la tarea y su origen")
    w("")
    w("«Declarado»: lo indicó el usuario. «IA, confirmado»: lo propuso la revisión visual y el usuario lo confirmó. "
      "«Estimado por IA»: propuesto por la revisión visual sin confirmar (revísalo). «Desconocido»: se recorren todos "
      "sus valores.")
    w("")
    w("| Dato | Valor | Origen |")
    w("|---|---|---|")
    for campo, etiqueta in CAMPOS_TAREA:
        w(f"| {etiqueta} | {_valor_tarea(campo, tarea, ctx.get('postura_base', 'auto'))} | {orig.get(campo, 'desconocido')} |")
    w("")
    sin = [e for c, e in CAMPOS_TAREA if orig.get(c) == "estimado por IA"]
    if sin:
        w(f"> ⚠️ Datos estimados por la IA sin confirmar: {', '.join(sin)}. Las puntuaciones dependen de ellos.")
        w("")


def _seccion_revision(w, ctx: dict) -> None:
    revs = ctx.get("revision") or []
    if not revs:
        return
    w("## Revisión visual del esqueleto y de la tarea")
    w("")
    w("Claude ha revisado láminas con cada instante dos veces (original y con el esqueleto) y ha propuesto el contexto "
      "de la tarea, sus fases, las muñecas y dónde el esqueleto no corresponde al cuerpo. **No decide qué se corrige:** "
      "la política está en código (quitar lo mal colocado y las ocultaciones de más de 1,5 s; conservar como aproximadas "
      "las ocultaciones cortas y lo «aproximado», con el margen de medida ampliado ×1,5; intercambiar lados solo si la "
      "profundidad de MediaPipe lo confirma).")
    w("")
    for r in revs:
        c = r["contexto"]
        w(f"### {r['video']}")
        w("")
        if r.get("resumen"):
            w(f"**Calidad del esqueleto:** {r['resumen']}")
            w("")
        if c.get("tarea"):
            w(f"**Tarea:** {c['tarea']}")
            w("")
        extra = [x for x in (c.get("carga_evidencia"), c.get("observaciones")) if x]
        if c.get("ciclos_observados"):
            extra.append(f"ciclos observados: {c['ciclos_observados']}")
        if extra:
            w("**Observaciones de la revisión:** " + "; ".join(extra) + ".")
            w("")
        ergo_v = (ctx.get("ergo") or {}).get(r["video"], {})
        if r["fases"]:
            w("**Fases de la tarea** (cobertura = % de fotogramas con la parte evaluada visible; peor = rango de la peor postura de la fase):")
            w("")
            w("| Fase | Tramo | Riesgo (IA) | REBA cobertura · peor | RULA izq. cobertura · peor | RULA dch. cobertura · peor |")
            w("|---|---|---|---|---|---|")
            for i, f in enumerate(r["fases"]):
                def celda(lista):
                    if not lista or i >= len(lista):
                        return "—"
                    x = lista[i]
                    return f"{_f(x['cobertura'])} % · {_r(x['peor']) if x['peor'] else '—'}"
                w(f"| {f.get('descripcion', '')} | {_f(f['inicio'], 1)}–{_f(f['fin'], 1)} s | {f.get('riesgo')} | "
                  f"{celda(ergo_v.get('reba_fases'))} | {celda((ergo_v.get('rula_fases') or {}).get('I'))} | "
                  f"{celda((ergo_v.get('rula_fases') or {}).get('D'))} |")
            w("")
        if r["munecas"]:
            w("**Muñecas estimadas por la IA** (solo se usan las de confianza alta o media, si no se han declarado):")
            w("")
            w("| Tramo | Lado | Flexión | Desviada | Girada | Confianza | Motivo |")
            w("|---|---|---|---|---|---|---|")
            sn = lambda v: "—" if v is None else ("sí" if v else "no")  # noqa: E731
            for m in r["munecas"]:
                w(f"| {_f(float(m['inicio']), 1)}–{_f(float(m['fin']), 1)} s | {m['lado']} | {m['flexion'].replace('_', ' ')} | "
                  f"{sn(m.get('desviada'))} | {sn(m.get('girada'))} | {m['confianza']} | {m.get('motivo', '')} |")
            w("")
        if r["decisiones"]:
            w("**Veredictos sobre el esqueleto y decisión aplicada:**")
            w("")
            w("| Articulación | Tramo | Veredicto (IA) | Decisión (código) | Evidencia |")
            w("|---|---|---|---|---|")
            for d in r["decisiones"]:
                w(f"| {d['articulacion'].replace('_', ' ')} | {_f(d['inicio'], 1)}–{_f(d['fin'], 1)} s | "
                  f"{d['veredicto'].replace('_', ' ')} | {d['accion']} | {d['evidencia']} |")
            w("")
        else:
            w("La revisión no señala problemas en el esqueleto.")
            w("")
    comp = ctx.get("comparativa")
    if comp:
        w("### Efecto de la revisión")
        w("")
        w("| Resultado | Sin revisión | Con revisión |")
        w("|---|---|---|")
        for k, a, b in comp:
            fa = f"{a[0]} {LUZ.get(a[1], '')}".strip()
            fb = f"{b[0]} {LUZ.get(b[1], '')}".strip()
            w(f"| {k} | {fa} | {fb} |")
        w("")


def _seccion_ergo(w, ctx: dict) -> None:
    metodos = ctx["metodos"]
    w("## REBA y RULA: peor postura")
    w("")
    w("REBA y RULA puntúan la postura más exigente, no el % del tiempo. Se puntúa cada fotograma analizado.")
    w("")
    for met in ("reba", "rula"):
        if met not in metodos:
            continue
        w(f"### {met.upper()}")
        w("")
        w("| Vídeo | Lado | Peor postura sostenida | Estado | Nivel | Actuación | Momento | Pico breve fiable | Fotogramas evaluables | Validez |")
        w("|---|---|---|---|---|---|---|---|---|---|")
        filas = []
        for nombre, d in ctx["ergo"].items():
            if met not in d:
                continue
            if met == "reba":
                filas.append((nombre, "ambos", d["reba"], d["reba_val"]))
            else:
                for s in "ID":
                    filas.append((nombre, ("izq." if s == "I" else "dch.") + (" (peor)" if d.get("rula_lado") == s else ""),
                                  d["rula"][s], d["rula_val"][s]))
        for nombre, lado, pk, val in filas:
            if not pk.get("evaluable"):
                w(f"| {nombre} | {lado} | — | — | — | — | — | — | 0 % | {LUZ['rojo']} |")
                continue
            n0, n1 = pk["nivel"], pk["nivel_max"]
            act = n0[3] if n0 == n1 else f"{n0[3]} / {n1[3]}"
            br = pk.get("breve")
            breve = f"{_r((br['pico'], br['pico_max']))} a {_f(br['t'], 1)} s ({_f(br['duracion_s'], 1)} s)" if br else "—"
            w(f"| {nombre} | {lado} | **{_pico_txt(pk)}** | {pk['estado']} | {_r((n0[1], n1[1]))} | {act} | {_f(pk['t_pico'], 1)} s | "
              f"{breve} | {_f(pk['completo'])} % | {LUZ[val['nivel']]} |")
        w("")
        for nombre, lado, pk, val in filas:
            if not pk.get("evaluable"):
                continue
            det = pk["detalle"]
            el = det["elementos"]
            partes = [f"{et} {_r(el[k])}" for k, et in ELEMENTOS[met] if k in el]
            if met == "reba":
                for s, v in el["lados"].items():
                    partes.append(f"lado {'izq.' if s == 'I' else 'dch.'}: brazo {_r(v['brazo'])}, antebrazo {_r(v['antebrazo'])}, "
                                  f"muñeca {_r(v['muneca'])}, B {_r(v['B'])}")
                partes.append(f"A (con carga) {_r(det['A'])}, B (con agarre, peor lado) {_r(det['B'])}")
            else:
                partes.append(f"C {_r(det['C'])}, D {_r(det['D'])} (antes de limitar a 8+ y 7+)")
            w(f"**{nombre}, {lado}, peor postura ({_f(pk['t_pico'], 1)} s):** " + "; ".join(partes) + ".")
            w("")
            traz = pk.get("trazabilidad")
            if traz:
                w("Trazabilidad (fotograma de la peor postura): " + "; ".join(
                    f"{MEDIDA_TXT.get(x['medida'], x['medida'])} {('desconocido' if x['valor'] is None else _f(x['valor'], 1))}"
                    + ("" if x["valor"] is None else f" ± {_f(x['margen'], 2 if x['margen'] < 1 else 0)}")
                    + ("" if x["origen"] == "medido" or x["valor"] is None else f" ({x['origen']})") for x in traz) + ".")
                w("")
            if len(pk["criticas"]) > 1:
                w("Otras posturas críticas: " + "; ".join(
                    f"{_f(c['t'], 1)} s → {_r((c['pico'], c['pico_max']))}" for c in pk["criticas"][1:]) + ".")
                w("")
            dist = pk.get("distribucion", {})
            if dist:
                w("Fotogramas por nivel (mínimo del rango): " + "; ".join(f"nivel {k} {_f(v)} %" for k, v in sorted(dist.items())) + ".")
                w("")
            for m_ in val["motivos"]:
                w(f"- ⚠️ {m_}")
            if val["motivos"]:
                w("")
        for cap in [c for c in ctx["capturas"] if c.get("metodo") == met]:
            w(f"**{cap['titulo']}**")
            w("")
            w(f"![{cap['titulo']}]({cap['ruta']})")
            w("")


def _seccion_owas(w, ctx: dict) -> None:
    r = ctx["resumen"]
    a = ctx["args"]
    w("## OWAS: % del tiempo observable")
    w("")
    w("### Validación del muestreo")
    w("")
    w("| Región | Código nominal conocido | Tiempo de decorrelación | Muestra efectiva (aprox.) | Intervalo máx. (aprox.) | Duración para ±10 puntos | Cobertura | Muestra |")
    w("|---|---|---|---|---|---|---|---|")
    for reg, x in r["regiones"].items():
        w(f"| {reg.capitalize()} | {_f(x['cobertura'])} % | {_f(x['tau_s'], 1)} s | {_f(x['n_efectiva'])} | ±{_f(x['margen_max'])} | "
          f"{_seg(x['duracion_necesaria_s'])} | {LUZ[x['nivel_cobertura']]} | {LUZ[x['nivel_muestra']]} |")
    w("")
    notas = {k: v for reg in r["regiones"].values() for k, v in reg["notas"].items()}
    if notas:
        w("**Datos que faltan en las observaciones:** " + "; ".join(
            f"{NOTAS.get(k, k)}: {v} ({_f(100 * v / max(1, r['n_observaciones']))} %)" for k, v in sorted(notas.items())) + ".")
        w("")
    w("### Frecuencia de cada código")
    w("")
    w("«Nominal»: % sobre las observaciones con código nominal conocido, con su intervalo aproximado. «Rango»: % mínimo y "
      "máximo sobre todas las observaciones, contando el margen de medida y lo que no se ve. La categoría por frecuencia "
      "se da para el nominal y, entre paréntesis, todas las posibles con el intervalo y el rango.")
    w("")
    turno = a.get("turno_h")
    w("| Región | Código | Postura | Nominal | Intervalo aprox. | Rango | Categoría |" + (" Min/turno (nominal) |" if turno else ""))
    w("|---|---|---|---|---|---|---|" + ("---|" if turno else ""))
    for reg in NOMBRES:
        for c, d in r["regiones"][reg]["codigos"].items():
            cat = d["categoria"]
            cat_txt = ("—" if cat is None else f"{cat}") + (f" ({'–'.join(map(str, [min(d['categoria_rango']), max(d['categoria_rango'])]))})"
                                                           if d["categoria_incierta"] else "")
            fila = (f"| {reg.capitalize()} | {c} | {d['nombre']} | {_f(d['porcentaje'])} % | {_f(d['ic_aprox'][0])}–{_f(d['ic_aprox'][1])} % | "
                    f"{_f(d['rango'][0])}–{_f(d['rango'][1])} % | {cat_txt} |")
            if turno:
                fila += f" {_f(d['porcentaje'] / 100 * turno * 60)} |"
            w(fila)
    w("")
    if turno:
        w("*Min/turno: extrapolación lineal del % nominal; solo vale si el vídeo representa el turno.*")
        w("")
    if "porcentajes" in ctx["imagenes"]:
        w(f"![Frecuencia de cada código]({ctx['imagenes']['porcentajes']})")
        w("")
    comb = r["combinaciones"]
    cats = comb["por_categoria"]
    w("### Combinaciones (espalda · brazos · piernas · carga)")
    w("")
    w("| Categoría | Significado | Observaciones (nominal) | % nominal | Rango |")
    w("|---|---|---|---|---|")
    for c in (1, 2, 3, 4):
        w(f"| {c} | {CATEGORIAS[c][0]}: {CATEGORIAS[c][1].lower()} | {cats[c]['n']} | {_f(cats[c]['porcentaje'])} % | "
          f"{_f(cats[c]['rango'][0])}–{_f(cats[c]['rango'][1])} % |")
    w("")
    if comb["frecuentes"]:
        w("Códigos nominales más frecuentes:")
        w("")
        w("| Código | Espalda | Brazos | Piernas | Carga | % | Categoría |")
        w("|---|---|---|---|---|---|---|")
        for x in comb["frecuentes"]:
            e, b, p, cg = map(int, x["codigo"])
            w(f"| {x['codigo']} | {ESPALDA[e]} | {BRAZOS[b]} | {PIERNAS[p]} | {CARGA[cg]} | {_f(x['porcentaje'])} % | {x['categoria']} |")
        w("")
    for nombre, ruta in ctx["imagenes"].items():
        if nombre.startswith("cronograma_"):
            w(f"![Cronograma {nombre[11:]}]({ruta})")
            w("")


# ---------------------------------------------------------------- HTML

CSS = """
:root{--fg:#1d2329;--bg:#fff;--muted:#5d6b78;--line:#dde3e8;--head:#f3f6f8;--warn:#fff4e0;--accent:#1f5fa8}
@media (prefers-color-scheme: dark){:root{--fg:#e6eaee;--bg:#15191d;--muted:#9aa7b3;--line:#2c343b;--head:#1e252b;--warn:#3a2e12;--accent:#7fb2ec}}
body{font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg);max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:1.7em;margin:.2em 0 .4em}h2{border-bottom:2px solid var(--line);padding-bottom:4px;margin-top:2em}h3{margin-top:1.4em}
blockquote{background:var(--warn);border-left:4px solid #e0a020;margin:1em 0;padding:.6em 1em;border-radius:4px}
table{border-collapse:collapse;width:100%;margin:.6em 0 1.2em;font-size:.88em;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:4px 7px;text-align:left;vertical-align:top}th{background:var(--head)}
img{max-width:100%;border:1px solid var(--line);border-radius:4px}a{color:var(--accent)}code{background:var(--head);padding:0 3px;border-radius:3px}
li{margin:.2em 0}
"""


def _inline(t: str, base: Path, incrustar: bool) -> str:
    t = html.escape(t, quote=False)

    def img(m):
        alt, src = m.group(1), m.group(2)
        p = base / src
        tipo = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}.get(p.suffix.lower())
        if incrustar and tipo and p.exists():
            src = f"data:image/{tipo};base64," + base64.b64encode(p.read_bytes()).decode()
        return f'<img alt="{alt}" src="{src}">'
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img, t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def a_html(md: str, base: Path, titulo: str = "Estudio OWAS", incrustar: bool = True) -> str:
    out, lista, tabla = [], False, []

    def cerrar_tabla():
        nonlocal tabla
        if tabla:
            filas = [[c.strip() for c in f.strip().strip("|").split("|")] for f in tabla if not re.match(r"^\|[-|\s]+\|$", f)]
            h = "".join(f"<th>{_inline(c, base, incrustar)}</th>" for c in filas[0])
            b = "".join("<tr>" + "".join(f"<td>{_inline(c, base, incrustar)}</td>" for c in f) + "</tr>" for f in filas[1:])
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")
            tabla = []

    for linea in md.splitlines():
        if linea.startswith("|"):
            tabla.append(linea)
            continue
        cerrar_tabla()
        if linea.startswith("- "):
            if not lista:
                out.append("<ul>")
                lista = True
            out.append(f"<li>{_inline(linea[2:], base, incrustar)}</li>")
            continue
        if lista:
            out.append("</ul>")
            lista = False
        if m := re.match(r"^(#{1,3}) (.*)", linea):
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2), base, incrustar)}</h{n}>")
        elif linea.startswith("> "):
            out.append(f"<blockquote>{_inline(linea[2:], base, incrustar)}</blockquote>")
        elif linea.strip():
            out.append(f"<p>{_inline(linea, base, incrustar)}</p>")
    cerrar_tabla()
    if lista:
        out.append("</ul>")
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{html.escape(titulo)}</title><style>{CSS}</style></head>'
            f'<body>{"".join(out)}</body></html>')
