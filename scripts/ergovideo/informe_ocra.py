"""OCRA en el informe: hallazgos para el plan de medidas, bloque visual (pestaña de dirección) y sección técnica.

Todo lo que se pinta sale de `ocra.calcular` (código). El escenario proyectado se recalcula también en código a partir de
los cambios que Claude propone en adaptacion.json («escenario_ocra») y se marca siempre como PROYECCIÓN.
"""

from __future__ import annotations

import html
import math

from . import ocra
from . import tablas_ocra as T
from .catalogo import CATALOGO

COLOR = {"verde": "var(--r0)", "amarillo": "var(--r2)", "rojo_bajo": "var(--r3)", "rojo": "var(--r4)",
         "morado": "var(--morado)", None: "var(--g-no)"}
TIPOS = {  # tipo de gesto → (nombre, color)
    "coger": ("Coger", "#2f7fb5"), "posicionar": ("Posicionar", "#3aa17e"), "encajar": ("Introducir o encajar", "#8c6bb1"),
    "herramienta": ("Herramienta", "#e08a2b"), "fuerza": ("Empujar, tirar, presionar, golpear", "#c8432f"),
    "girar": ("Girar", "#d4b02c"), "transportar": ("Transportar", "#6b7f8a"), "otro": ("Otro", "#999"),
}
ARTIC = {"hombro": "Hombro", "codo": "Codo", "muneca": "Muñeca", "agarre": "Mano (agarre)"}
SIGLA = {"fom": "FoM", "pom": "PoM", "rem": "ReM", "adm": "AdM"}
MULT = [("fom", "Fuerza (FoM)"), ("pom", "Postura (PoM)"), ("rem", "Repetitividad (ReM)"), ("adm", "Factores adicionales (AdM)")]


def _e(x) -> str:
    return html.escape(str(x), quote=True)


f2 = ocra.fmt


def _v(d: dict, dec: int = 2) -> str:
    if d is None:
        return "—"
    if d.get("nominal") is not None and abs(d["max"] - d["min"]) < 1e-9:
        return f2(d["nominal"], dec)
    return f"{f2(d['min'], dec)}–{f2(d['max'], dec)}"


# ------------------------------------------------------------------ hallazgos (para el plan de medidas)

def hallazgos(res: dict) -> list[dict]:
    out = []
    manos = res["manos"]

    def add(tipo, gravedad, lado, detalle, evidencia):
        c = CATALOGO[tipo]
        region = c["region"]
        out.append(dict(id=tipo, tipo=tipo, lado=lado, region=region, titulo=c["titulo"], riesgo=c["riesgo"],
                        gravedad=gravedad, detalle=detalle, evidencia=evidencia, porcentaje=None, episodios=None,
                        fases=[], metodo="ocra"))

    def lado_de(ms):
        return None if len(ms) != 1 else ("D" if ms[0] == "dch" else "I")
    # Frecuencia
    # Frecuencia: se detecta con el valor seguro (mínimo del rango) y se informa el rango.
    fr = {m: x["frecuencia_rango"] for m, x in manos.items()}
    txt = lambda r: f2(r[0], 0) if abs(r[1] - r[0]) < 0.5 else f"{f2(r[0], 0)}–{f2(r[1], 0)}"  # noqa: E731
    altas = [m for m, r in fr.items() if r[0] > T.FRECUENCIA_REFERENCIA]
    if altas:
        peor = max(fr[m][0] for m in altas)
        add("ocra_frecuencia", "alta" if peor > 40 else "media", lado_de(altas),
            "; ".join(f"mano {ocra.NOMBRE_MANO[m]}: {txt(fr[m])} acciones por minuto" for m in altas) + ".",
            [f"OCRA: frecuencia de {txt(fr[m])} AT/min (mano {ocra.NOMBRE_MANO[m]}) frente a {T.FRECUENCIA_REFERENCIA:g} "
             "de referencia" for m in altas])
    rc = res["rcm"]
    if rc["max"] < 1:
        g = "alta" if rc["max"] <= 0.6 else "media" if rc["max"] <= 0.8 else "baja"
        horas = rc.get("horas")
        add("ocra_recuperacion", g, None,
            (f"{f2(horas, 1)} horas del turno sin recuperación adecuada." if horas is not None else
             f"Recuperación insuficiente (RcM {_v(rc)})."),
            [f"OCRA: RcM {_v(rc)} ({rc.get('origen')})"])
    for tipo, clave, umbrales in (("ocra_fuerza", "fom", (0.65, 0.85)), ("ocra_postura", "pom", (0.6, 0.7)),
                                  ("ocra_estereotipia", "rem", (0.0, 0.7)), ("ocra_adicionales", "adm", (0.8, 0.9))):
        afect, ev, peor = [], [], 1.0
        for m, x in manos.items():
            for t in x["tareas"]:
                v = t[clave]
                if v["max"] < 1:
                    afect.append(m)
                    peor = min(peor, v["max"])
                    ev.append(f"OCRA {SIGLA[clave]} {_v(v)} (mano {ocra.NOMBRE_MANO[m]}"
                              + (f", {t['tarea']}" if len(x["tareas"]) > 1 else "") + ")")
        if not afect:
            continue
        g = "alta" if peor <= umbrales[0] else "media" if peor <= umbrales[1] else "baja"
        afect = list(dict.fromkeys(afect))
        detalle = {"ocra_fuerza": "Esfuerzo con la mano en parte del ciclo (escala de Borg).",
                   "ocra_postura": "Postura forzada de hombro, codo, muñeca o agarre durante buena parte del ciclo.",
                   "ocra_estereotipia": "Ciclo corto o la misma acción durante más de la mitad del ciclo.",
                   "ocra_adicionales": "Factores adicionales presentes en el ciclo."}[tipo]
        add(tipo, g, lado_de(afect), detalle, ev)
        if tipo == "ocra_postura":
            # La zona del mapa corporal es la articulación más penalizada.
            peor_art = None
            for x in manos.values():
                for t in x["tareas"]:
                    for a, d in (t.get("pom_detalle") or {}).items():
                        if d["pom"][1] < 1 and (peor_art is None or d["pom"][1] < peor_art[1]):
                            peor_art = (a, d["pom"][1])
            if peor_art and peor_art[0] != "hombro":
                out[-1]["region"] = "muneca"
    return out


def adjuntar_capturas(hall: list[dict], oc: dict) -> None:
    """La captura del primer instante clave ilustra el hallazgo de frecuencia."""
    if oc.get("capturas"):
        for h in hall:
            if h["id"] == "ocra_frecuencia":
                h["captura"], h["t_ejemplo"] = oc["capturas"][0]["ruta"], oc["capturas"][0]["t"]


def indicador(res: dict) -> dict:
    m = res["manos"][res["peor_mano"]]
    c = m["clase_max"]
    otra = [x for k, x in res["manos"].items() if k != res["peor_mano"]]
    detalle = f"mano {m['nombre']}: {ocra.texto_indice(m)}"
    if otra:
        detalle += f"; mano {otra[0]['nombre']}: {ocra.texto_indice(otra[0])}"
    return dict(metodo="OCRA", que="Movimientos repetitivos (índice OCRA)", nivel=c["nivel"], urgencia=res["urgencia"],
                accion=c["accion"], detalle=detalle, color_ocra=c["color"])


# ------------------------------------------------------------------ piezas SVG

def _escala_max(res: dict) -> float:
    vals = [x["indice_max"] for x in res["manos"].values() if not math.isinf(x["indice_max"])]
    return max(12.0, math.ceil(max(vals + [0]) * 1.1))


def medidor(m: dict, res: dict, escala: float) -> str:
    """Barra horizontal con las bandas de la clasificación, el rango del índice y el valor nominal."""
    W, x0, ancho = 520, 10, 500
    X = lambda v: x0 + ancho * min(v, escala) / escala  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} 62" class="medidor" role="img" aria-label="Índice OCRA mano {m["nombre"]}">']
    a = 0.0
    for b in res["bandas"]:
        hasta = escala if b["hasta"] is None else min(b["hasta"] + 0.05, escala)
        out.append(f'<rect x="{X(a):.1f}" y="18" width="{max(0, X(hasta) - X(a)):.1f}" height="16" fill="{COLOR[b["color"]]}" opacity=".85"/>')
        a = hasta
    lo, hi = m["indice_min"], m["indice_max"]
    if hi - lo > 0.01:
        out.append(f'<rect x="{X(lo):.1f}" y="13" width="{max(2, X(hi) - X(lo)):.1f}" height="26" class="m-rango"/>')
    v = m["indice"] if m["indice"] is not None else hi
    out.append(f'<path d="M{X(v):.1f} 12 l-6 -9 h12 z" class="m-marca"/><line x1="{X(v):.1f}" y1="12" x2="{X(v):.1f}" y2="40" class="m-linea"/>')
    for k in range(0, int(escala) + 1, 2 if escala <= 16 else 4):
        out.append(f'<text x="{X(k):.1f}" y="54" class="svg-t" text-anchor="middle">{k}</text>')
    out.append("</svg>")
    return "".join(out)


def linea_ciclo(ficha: dict, base_capturas: dict | None = None) -> str:
    """Línea de tiempo del ciclo representativo: una fila por mano con las AT coloreadas por tipo de gesto."""
    c = ficha["ciclo"]
    ini, fin = c["inicio"], c["fin"] or max([a["t"] for a in ficha["acciones"]] + [1])
    dur = max(fin - ini, 1e-6)
    W, x0, ancho = 900, 90, 790
    X = lambda t: x0 + ancho * (t - ini) / dur  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} 128" class="linea" role="img" aria-label="Acciones técnicas a lo largo del ciclo">']
    for fila, (m, nombre) in enumerate((("dch", "Mano dch."), ("izq", "Mano izq."))):
        y = 10 + fila * 46
        out.append(f'<text x="{x0 - 8}" y="{y + 22}" class="svg-et" text-anchor="end">{nombre}</text>'
                   f'<rect x="{x0}" y="{y}" width="{ancho}" height="34" rx="3" class="fase"/>')
        for a in [a for a in ficha["acciones"] if a["mano"] == m]:
            x = X(a["t"])
            tit = _e(f"{f2(a['t'], 1)} s · {a['gesto'].replace('_', ' ')} · {a['objeto']} · {a['estado']}: {a['motivo']}")
            if a["estado"] in ("valida", "dudosa") and a["at"] > 0:
                col = TIPOS.get(a["tipo"], TIPOS["otro"])[1]
                trazo = ' stroke-dasharray="3 2" fill-opacity=".35"' if a["estado"] == "dudosa" else ""
                out.append(f'<rect x="{x - 6:.1f}" y="{y + 4}" width="12" height="26" rx="2" fill="{col}" stroke="{col}"{trazo}>'
                           f'<title>{tit}</title></rect>')
                if a["at"] > 1:
                    out.append(f'<text x="{x:.1f}" y="{y + 22}" class="svg-n" text-anchor="middle">{a["at"]}</text>')
            else:
                cls = "at-no" if a["estado"] == "no_es_at" else "at-rech"
                out.append(f'<g class="{cls}"><title>{tit}</title><line x1="{x - 4:.1f}" y1="{y + 13}" x2="{x + 4:.1f}" y2="{y + 21}"/>'
                           f'<line x1="{x + 4:.1f}" y1="{y + 13}" x2="{x - 4:.1f}" y2="{y + 21}"/></g>')
    paso = 1 if dur <= 15 else 2 if dur <= 30 else 5
    t = math.ceil(ini)
    while t <= fin + 1e-6:
        out.append(f'<text x="{X(t):.1f}" y="122" class="svg-t" text-anchor="middle">{t:g} s</text>')
        t += paso
    out.append("</svg>")
    return "".join(out)


def leyenda_tipos(ficha: dict) -> str:
    usados = {a["tipo"] for a in ficha["acciones"] if a["at"] > 0}
    it = "".join(f'<span><i style="background:{c}"></i>{_e(n)}</span>' for k, (n, c) in TIPOS.items() if k in usados)
    return (f'<div class="leyenda">{it}<span><i class="i-dudosa"></i>Dudosa (cuenta solo en el máximo)</span>'
            f'<span><b class="x-rech">×</b>No es AT (rechazada o registrada)</span></div>')


def cascada(m: dict) -> str:
    """De la frecuencia de referencia (30) a la frecuencia que admite el puesto, factor a factor; y la real."""
    if len(m["tareas"]) != 1:
        return ""
    t = m["tareas"][0]
    pasos = [("Referencia", T.FRECUENCIA_REFERENCIA, None)]
    val, val_hi, completo = T.FRECUENCIA_REFERENCIA, T.FRECUENCIA_REFERENCIA, True
    for clave, nombre in MULT:
        d = t[clave]
        val *= d["min"]
        val_hi *= d["max"]
        pasos.append((nombre, val, d))
    for clave, nombre in (("rcm", "Recuperación (RcM)"), ("dum", "Duración (DuM)")):
        d = m["_rcm"] if clave == "rcm" else m["_dum"]
        val *= d["min"] if clave == "rcm" else d["max"]  # DuM > 1 sube la referencia: el peor caso es el más bajo
        val_hi *= d["max"] if clave == "rcm" else d["min"]
        pasos.append((nombre, val, d))
    frec = t["frecuencia"]
    tope = max(T.FRECUENCIA_REFERENCIA, frec["max"]) * 1.05
    W, x0, ancho, h = 700, 190, 400, 22
    X = lambda v: x0 + ancho * min(v, tope) / tope  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {(len(pasos) + 1) * (h + 6) + 26}" class="cascada" role="img" '
           f'aria-label="Cómo reduce cada factor la frecuencia de referencia">']
    y = 4
    prev = T.FRECUENCIA_REFERENCIA
    for nombre, v, d in pasos:
        etq = nombre if d is None else f"{nombre} × {_v(d)}"
        out.append(f'<text x="{x0 - 8}" y="{y + 15}" class="svg-et" text-anchor="end">{_e(etq)}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{X(v) - x0:.1f}" height="{h}" class="c-barra"/>')
        if d is not None and prev - v > 0.05:
            out.append(f'<rect x="{X(v):.1f}" y="{y}" width="{X(prev) - X(v):.1f}" height="{h}" class="c-perdida"/>')
        out.append(f'<text x="{X(max(v, prev)) + 6:.1f}" y="{y + 15}" class="svg-et">{f2(v, 1)}</text>')
        prev = v
        y += h + 6
    fr_v = frec["nominal"] if frec["nominal"] is not None else frec["max"]
    out.append(f'<text x="{x0 - 8}" y="{y + 15}" class="svg-et" text-anchor="end"><tspan font-weight="700">Frecuencia real</tspan></text>'
               f'<rect x="{x0}" y="{y}" width="{X(fr_v) - x0:.1f}" height="{h}" class="c-real"/>'
               f'<text x="{X(fr_v) + 6:.1f}" y="{y + 15}" class="svg-et" font-weight="700">{_e(_v(frec, 0))} AT/min</text>')
    out.append(f'<line x1="{X(T.FRECUENCIA_REFERENCIA):.1f}" y1="0" x2="{X(T.FRECUENCIA_REFERENCIA):.1f}" y2="{y + h + 4}" class="c-ref"/>')
    out.append("</svg>")
    return "".join(out)


def _col_pom(p):
    if p is None:
        return "var(--g-no)"
    return {1.0: "var(--r0)", 0.7: "var(--r2)", 0.6: "var(--r3)", 0.5: "var(--r4)"}.get(round(p, 2), "var(--r3)")


def mapa_brazos(res: dict, medido: dict | None = None) -> str:
    """Silueta de los brazos con hombro, codo, muñeca y mano coloreados por el multiplicador de postura (peor caso).
    Si el PoM se declaró en bloque, se colorea con lo medido por MediaPipe como referencia (se dice en el título)."""
    def art(mano, a):
        x = res["manos"].get(mano)
        if not x:
            return None, "sin datos"
        vals = [t.get("pom_detalle", {}).get(a) for t in x["tareas"]]
        vals = [v for v in vals if v]
        if not vals:
            fr = ((medido or {}).get(mano) or {}).get(a)
            if fr and fr["cobertura"] >= 50:
                lo, hi = T.pom_articulacion(fr["max"]), T.pom_articulacion(fr["min"])
                return (lo if lo == hi else None), (f"{ARTIC[a]}: {100 * fr['min']:.0f}–{100 * fr['max']:.0f} % del tiempo en "
                                                     "postura forzada (MediaPipe, solo referencia: el PoM usado es el declarado)")
            return None, f"{ARTIC[a]}: PoM declarado en bloque ({_v(x['tareas'][0]['pom'])})"
        lo = min(v["pom"][0] for v in vals)
        hi = min(v["pom"][1] for v in vals)
        fr = vals[0]["fraccion"]
        txt = (f"{ARTIC[a]}: sin dato (se recorre todo el rango)" if fr["origen"] == "desconocido" else
               f"{ARTIC[a]}: {100 * fr['min']:.0f}–{100 * fr['max']:.0f} % del ciclo en postura forzada ({fr['origen']})")
        return (lo if lo == hi else None), txt
    partes = ['<rect x="78" y="40" width="64" height="120" rx="14" fill="var(--g-no)"/><circle cx="110" cy="22" r="18" fill="var(--g-no)"/>']
    for mano, sx in (("dch", -1), ("izq", 1)):
        cx = 110 + sx * 40
        hm, th = art(mano, "hombro")
        co, tc = art(mano, "codo")
        mu, tm = art(mano, "muneca")
        ag, ta = art(mano, "agarre")
        ex, ey = 110 + sx * 58, 112
        wx, wy = 110 + sx * 66, 180
        partes += [
            f'<line x1="{cx}" y1="52" x2="{ex}" y2="{ey}" stroke="var(--g-no)" stroke-width="16" stroke-linecap="round"/>',
            f'<line x1="{ex}" y1="{ey}" x2="{wx}" y2="{wy}" stroke="var(--g-no)" stroke-width="13" stroke-linecap="round"/>',
            f'<circle cx="{cx}" cy="52" r="13" fill="{_col_pom(hm)}"><title>{_e(th)}</title></circle>',
            f'<circle cx="{ex}" cy="{ey}" r="11" fill="{_col_pom(co)}"><title>{_e(tc)}</title></circle>',
            f'<circle cx="{wx}" cy="{wy}" r="10" fill="{_col_pom(mu)}"><title>{_e(tm)}</title></circle>',
            f'<ellipse cx="{wx + sx * 2}" cy="{wy + 20}" rx="10" ry="13" fill="{_col_pom(ag)}"><title>{_e(ta)}</title></ellipse>',
        ]
    partes.append('<text x="40" y="232" class="svg-et">dch.</text><text x="180" y="232" class="svg-et" text-anchor="end">izq.</text>')
    return f'<svg viewBox="0 0 220 240" class="brazos" role="img" aria-label="Postura por articulación">{"".join(partes)}</svg>'


# ------------------------------------------------------------------ bloque HTML (pestaña de dirección)

def _img(base, rel):
    from .informe_puesto import _img as img
    return img(base, rel)


def bloque(oc: dict, base, escenario: dict | None) -> str:
    res = oc["resultado"]
    ficha = oc.get("ficha")
    escala = _escala_max(res)
    for x in res["manos"].values():
        x["_rcm"], x["_dum"] = res["rcm"], res["dum"]
    tarjetas = []
    for m in ("dch", "izq"):
        x = res["manos"].get(m)
        if not x:
            continue
        c = x["clase_max"]
        puntual = x["indice"] is not None and abs(x["indice_max"] - x["indice_min"]) < 0.005
        if puntual:
            num, rango = f2(x["indice"], 1), ""
        else:
            # Sin valor único se da el rango: nunca se elige un punto dentro de él.
            num = f'{f2(x["indice_min"], 1)}<span class="o-guion">–</span>{f2(x["indice_max"], 1)}'
            cmin = x["clase_min"]
            rango = (f'<div class="o-rango">rango del índice; '
                     + (f'puede ir de «{_e(cmin["nivel"].lower())}» a «{_e(c["nivel"].lower())}»'
                        if cmin["color"] != c["color"] else f'todo él en «{_e(c["nivel"].lower())}»') + "</div>")
        frec = x["tareas"][0]["frecuencia"] if len(x["tareas"]) == 1 else None
        tarjetas.append(
            f'<div class="o-mano" style="--c:{COLOR[c["color"]]}"><div class="m">Mano {_e(x["nombre"])}</div>'
            f'<div class="o-num">{num}</div>{rango}'
            f'<div class="o-niv"><span class="pill" style="--c:{COLOR[c["color"]]}">{_e(c["nivel"])}'
            f'{"" if puntual or x["clase_min"]["color"] == c["color"] else " (peor caso)"}</span></div>'
            f'{medidor(x, res, escala)}'
            f'<div class="a">{_e(c["accion"])}</div>'
            + (f'<div class="a" style="color:var(--suave)">{_e(_v(frec, 0))} acciones técnicas por minuto frente a '
               f'{T.FRECUENCIA_REFERENCIA:g} de referencia</div>' if frec else "") + "</div>")
    partes = [f'<div class="o-manos">{"".join(tarjetas)}</div>',
              f'<p class="nota-o">Clasificación: {_e(res["clasificacion_nombre"])}. {_e(res["aviso_normativo"])}</p>']
    if ficha:
        caps = "".join(
            f'<figure><img src="{src}" alt="{_e(c["titulo"])}"><figcaption>{_e(c["titulo"])}</figcaption></figure>'
            for c in oc.get("capturas", []) if (src := _img(base, c["ruta"])))
        conf = "confirmada por el usuario" if ficha.get("confirmada") else "pendiente de confirmar por el usuario"
        rec = ficha["recuento"]
        rtxt = "; ".join(
            f"mano {ocra.NOMBRE_MANO[m]}: {r['nominal'] if r['nominal'] is not None else str(r['min']) + '–' + str(r['max'])} AT"
            + (f" ({len(r['rechazadas'])} propuestas rechazadas por las reglas)" if r["rechazadas"] else "")
            for m, r in rec.items() if r["max"] or r["rechazadas"])
        partes.append(
            f'<h3 style="margin-top:1.4rem">Acciones técnicas en un ciclo ({f2(ficha["ciclo"]["duracion_s"] or 0, 1)} s)</h3>'
            f'{linea_ciclo(ficha)}{leyenda_tipos(ficha)}'
            f'<p style="font-size:.85rem;color:var(--suave)">{_e(rtxt)}. Ficha de la revisión visual, validada en código, {conf}. '
            f'Pasa el puntero por cada marca para ver el gesto y la regla aplicada.</p>'
            + (f'<div class="o-caps">{caps}</div>' if caps else ""))
    cas = "".join(f'<div><h3>Mano {_e(x["nombre"])}</h3>{cascada(x)}</div>' for x in res["manos"].values())
    if cas.strip():
        partes.append(f'<h3 style="margin-top:1.4rem">Qué reduce la frecuencia admisible</h3><div class="o-cascadas">{cas}</div>'
                      '<p style="font-size:.85rem;color:var(--suave)">Cada barra parte de las 30 acciones por minuto de '
                      'referencia y se acorta con cada factor (en gris, lo que resta). La barra oscura es la frecuencia real: '
                      'cuanto más la supera, más alto el índice. Con rangos se dibuja el peor caso.</p>')
    partes.append(f'<div class="resumen" style="margin-top:1rem">{mapa_brazos(res, (oc.get("mediapipe") or {}).get("posturas"))}<div><h3>Postura por articulación</h3>'
                  '<p style="font-size:.9rem">Color de cada articulación según el multiplicador de postura: '
                  '<span class="pill" style="--c:var(--r0)">sin penalizar</span> <span class="pill" style="--c:var(--r2)">0,70</span> '
                  '<span class="pill" style="--c:var(--r3)">0,60</span> <span class="pill" style="--c:var(--r4)">0,50</span> '
                  '<span class="pill" style="--c:var(--g-no);color:var(--tinta)">sin dato o rango</span></p>'
                  + "".join(f'<p style="font-size:.85rem;color:var(--suave)">Mano {_e(x["nombre"])}: {_e(x["tareas"][0]["pom"]["nota"])} '
                            f'(PoM {_e(_v(x["tareas"][0]["pom"]))}, {_e(x["tareas"][0]["pom"]["origen"])}).</p>'
                            for x in res["manos"].values())
                  + ('<p style="font-size:.85rem;color:var(--suave)">Con el PoM declarado en bloque, los colores muestran lo '
                     'medido por MediaPipe solo como referencia (gris donde no se ve bastante).</p>'
                     if (oc.get("mediapipe") or {}).get("posturas") and any(
                         not t.get("pom_detalle") for x in res["manos"].values() for t in x["tareas"]) else "")
                  + "</div></div>")
    if escenario:
        partes.append(bloque_escenario(res, escenario))
    partes.append(tabla_sensibilidad(res))
    partes.append('<details class="o-traz"><summary>De dónde sale cada dato</summary><div class="envoltura"><table class="tabla">'
                  '<thead><tr><th>Dato</th><th>Mano</th><th>Valor</th><th>Origen</th><th>Nota</th></tr></thead><tbody>'
                  + "".join(f'<tr><td>{_e(f["dato"])}</td><td>{_e(f["mano"])}</td><td>{_e(f["valor"])}</td>'
                            f'<td>{_e(f["origen"])}</td><td style="color:var(--suave)">{_e(f["nota"])}</td></tr>'
                            for f in res["trazabilidad"]) + "</tbody></table></div></details>")
    return "".join(partes)


def bloque_escenario(res: dict, esc: dict) -> str:
    r2 = esc["resultado"]
    escala = max(_escala_max(res), _escala_max(r2))
    filas = []
    for m in ("dch", "izq"):
        a, b = res["manos"].get(m), r2["manos"].get(m)
        if not a or not b:
            continue
        va = a["indice"] if a["indice"] is not None else a["indice_max"]
        vb = b["indice"] if b["indice"] is not None else b["indice_max"]
        ta = ocra.texto_indice(a).split(" (")[0]
        tb = ocra.texto_indice(b).split(" (")[0]
        W, x0, ancho = 620, 120, 330
        X = lambda v: ancho * min(v, escala) / escala  # noqa: E731
        ca, cb = COLOR[a["clase_max"]["color"]], COLOR[b["clase_max"]["color"]]
        filas.append(
            f'<svg viewBox="0 0 {W} 70" class="esc" role="img" aria-label="Antes y después, mano {a["nombre"]}">'
            f'<text x="{x0 - 8}" y="22" class="svg-et" text-anchor="end">Hoy · mano {a["nombre"][:3]}.</text>'
            f'<rect x="{x0}" y="8" width="{X(va):.1f}" height="20" fill="{ca}"/>'
            f'<text x="{x0 + X(va) + 6:.1f}" y="23" class="svg-et">{_e(ta)}</text>'
            f'<text x="{x0 - 8}" y="56" class="svg-et" text-anchor="end">Proyección</text>'
            f'<rect x="{x0}" y="42" width="{X(vb):.1f}" height="20" fill="{cb}" fill-opacity=".55" stroke="{cb}" stroke-dasharray="4 3"/>'
            f'<text x="{x0 + X(vb) + 6:.1f}" y="57" class="svg-et">{_e(tb)} · {_e(b["clase_max"]["nivel"].lower())}</text></svg>')
    medidas = "".join(f"<li>{_e(x)}</li>" for x in esc.get("medidas", []))
    return (f'<div class="o-esc"><div class="etq">Escenario proyectado — no es un resultado</div>'
            f'<h3>{_e(esc.get("titulo") or "Índice recalculado con las medidas propuestas")}</h3>'
            + (f"<ul>{medidas}</ul>" if medidas else "") + "".join(filas)
            + '<p style="font-size:.85rem;color:var(--suave)">Las barras llegan al peor caso de cada rango. Proyección calculada en código con los mismos multiplicadores, '
              'cambiando solo lo que modifican las medidas. Habrá que medir de nuevo el puesto una vez implantadas.</p></div>')


def tabla_sensibilidad(res: dict) -> str:
    if not res["sensibilidad"]:
        return ""
    manos = [m for m in ("dch", "izq") if m in res["manos"]]
    cab = "".join(f"<th>Mano {ocra.NOMBRE_MANO[m]}</th>" for m in manos)
    base = "".join(f"<td><b>{f2(res['sensibilidad'][0][m]['base'])}</b></td>" for m in manos if m in res["sensibilidad"][0])
    filas = [f"<tr><td>Valor de partida (el peor caso, si es un rango)</td>{base}</tr>"]
    for s in res["sensibilidad"]:
        celdas = "".join(
            f'<td><span class="dot" style="background:{COLOR[s[m]["clase"]]}"></span>{f2(s[m]["indice"])}</td>'
            for m in manos if m in s)
        filas.append(f"<tr><td>{_e(s['caso'])}</td>{celdas}</tr>")
    return (f'<h3 style="margin-top:1.4rem">Sensibilidad</h3><div class="envoltura"><table class="tabla"><thead><tr><th>Si…</th>'
            f'{cab}</tr></thead><tbody>{"".join(filas)}</tbody></table></div>'
            '<p style="font-size:.85rem;color:var(--suave)">Cuánto cambia el índice con un error de recuento o de los datos '
            'declarados. Si el color no cambia, la conclusión es robusta.</p>')


CSS = """
:root{--morado:#7a3e9d}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--morado:#b07ad6}}
:root[data-theme="dark"]{--morado:#b07ad6}
.sintesis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:1rem}
.semaforo{display:flex;gap:12px;align-items:flex-start;background:var(--tarjeta);border:1px solid var(--linea);border-radius:6px;padding:.7rem .9rem;font-family:var(--f-tit)}
.luces{display:flex;flex-direction:column;gap:4px;background:#222;border-radius:10px;padding:5px;flex:none}
.luces i{width:14px;height:14px;border-radius:50%;background:#444;display:block}
.luces i.on{box-shadow:0 0 6px var(--c);background:var(--c)}
.semaforo .m{font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.semaforo .n{font-weight:700}
.o-manos{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.o-mano{background:var(--tarjeta);border:1px solid var(--linea);border-top:6px solid var(--c);border-radius:6px;padding:.8rem 1rem;font-family:var(--f-tit)}
.o-mano .m{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.o-num{font-size:2.6rem;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}.o-guion{font-weight:400;color:var(--suave);margin:0 .15em}
.o-rango{font-size:.85rem;color:var(--suave)}.o-niv{margin:.3rem 0}.o-mano .a{font-size:.88rem;margin-top:.2rem}
.medidor{width:100%;height:auto;display:block;margin:.4rem 0}.m-rango{fill:none;stroke:var(--tinta);stroke-width:2}
.m-marca{fill:var(--tinta)}.m-linea{stroke:var(--tinta);stroke-width:2}
.nota-o{font-size:.8rem;color:var(--suave);margin:.5rem 0 0}
.at-rech line{stroke:var(--g-alta);stroke-width:2}.at-no line{stroke:var(--suave);stroke-width:1.5}
.i-dudosa{border:1.5px dashed var(--suave);background:transparent!important}.x-rech{color:var(--g-alta);margin-right:4px}
.o-caps{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin-top:.6rem}
.o-caps figure{margin:0}.o-caps img{width:100%;border-radius:4px;display:block}
.o-caps figcaption{font:12px var(--f-tit);color:var(--suave);margin-top:2px}
.o-cascadas{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.cascada{width:100%;height:auto;display:block}.esc{width:100%;max-width:620px;height:auto;display:block;margin:.3rem 0}.c-barra{fill:var(--acento);opacity:.75}.c-perdida{fill:var(--g-no)}
.c-real{fill:var(--tinta)}.c-ref{stroke:var(--suave);stroke-dasharray:3 3}
.brazos{width:100%;max-width:200px;height:auto}
.o-esc{background:var(--tarjeta);border:1px dashed var(--acento);border-radius:6px;padding:1rem 1.2rem;margin-top:1.4rem}
.o-esc h3{margin:.2rem 0 .4rem}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:0}
.o-traz{margin-top:1rem;font-family:var(--f-tit);font-size:.9rem}.o-traz summary{cursor:pointer;color:var(--acento)}
"""


def semaforos(indicadores: list[dict]) -> str:
    """Portada de síntesis: un semáforo por método."""
    out = []
    for i in indicadores:
        u = i["urgencia"]
        luz = 2 if u >= 3 else 1 if u == 2 else 0
        col = ["var(--r0)", "var(--r2)", "var(--r4)"]
        if i.get("color_ocra") == "morado":
            col[2] = "var(--morado)"
        luces = "".join(f'<i class="{"on" if k == luz else ""}" style="--c:{col[k]}"></i>' for k in (2, 1, 0))
        out.append(f'<div class="semaforo"><div class="luces" aria-hidden="true">{luces}</div><div>'
                   f'<div class="m">{_e(i["metodo"])}</div><div class="n">{_e(i["nivel"])}</div>'
                   f'<div style="font-size:.85rem;color:var(--suave)">{_e(i["que"])}</div>'
                   f'<div style="font-size:.85rem">{_e(i.get("accion", ""))}</div>'
                   f'<div style="font-size:.8rem;color:var(--suave)">{_e(i.get("detalle", ""))}</div></div></div>')
    return f'<div class="sintesis">{"".join(out)}</div>'


# ------------------------------------------------------------------ sección técnica (Markdown)

def markdown(oc: dict) -> str:
    res = oc["resultado"]
    L = []
    w = L.append
    w("## OCRA (movimientos repetitivos de la extremidad superior)")
    w("")
    w(f"> **Aviso normativo.** {res['aviso_normativo']} Constantes en `scripts/ergovideo/tablas_ocra.py`, cada una con su "
      "fuente y la marca `verificar_iso_2026`.")
    w("")
    w(f"Clasificación usada: **{res['clasificacion_nombre']}**. ATA = Σ frecuencia × minutos; RTA = Σ (30 × FoM × PoM × ReM × "
      "AdM × minutos) × RcM × DuM; índice = ATA / RTA. Lo desconocido se recorre entero (rango).")
    w("")
    w("| Mano | Índice | Rango | Nivel (peor caso) | ATA | RTA |")
    w("|---|---|---|---|---|---|")
    for x in res["manos"].values():
        w(f"| {x['nombre']} | {f2(x['indice'])} | {f2(x['indice_min'])}–{f2(x['indice_max'])} | {x['clase_max']['nivel']} | "
          f"{_v(x['ata'], 0)} | {_v(x['rta'], 0)} |")
    w("")
    w("### Multiplicadores por tarea y mano")
    w("")
    w("| Tarea | Mano | Min | Ciclo (s) | AT/ciclo | Frecuencia | FoM | PoM | ReM | AdM |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for x in res["manos"].values():
        for t in x["tareas"]:
            w(f"| {t['tarea']} | {x['nombre']} | {_v(t['minutos'], 0)} | {_v(t['ciclo_s'], 1)} | {_v(t['at_ciclo'], 0)} | "
              f"{_v(t['frecuencia'], 1)} | {_v(t['fom'])} | {_v(t['pom'])} | {_v(t['rem'])} | {_v(t['adm'])} |")
    w("")
    w(f"RcM = {_v(res['rcm'])} ({res['rcm']['origen']}; {res['rcm']['nota']}). DuM = {_v(res['dum'])} ({res['dum']['nota']}).")
    w("")
    if res.get("horario"):
        w("**Recuperación según el horario** (proporción 5:1; la comida y el final del turno cubren la hora anterior):")
        w("")
        w("| Desde | Hasta | Trabajo (min) | Seguido de | Cubierto (min) | Sin recuperación (min) |")
        w("|---|---|---|---|---|---|")
        for tr in res["horario"]["tramos"]:
            rec = tr["recuperacion"] + (f" ({tr['recuperacion_min']:g} min)" if tr["recuperacion_min"] else "")
            w(f"| {tr['desde']} | {tr['hasta']} | {tr['trabajo_min']:g} | {rec} | {tr['cubierto_min']:g} | {tr['sin_recuperacion_min']:g} |")
        w("")
    ficha = oc.get("ficha")
    if ficha:
        w(f"### Ficha de acciones técnicas (ciclo {f2(ficha['ciclo']['inicio'], 1)}–{f2(ficha['ciclo']['fin'], 1)} s)")
        w("")
        w("Rellenada por Claude mirando el ciclo a 4–8 fotogramas por segundo; el código aplica las reglas de recuento; "
          + ("**confirmada por el usuario**." if ficha.get("confirmada") else "**pendiente de confirmar por el usuario**."))
        w("")
        w("| s | Mano | Gesto | Objeto | Confianza | AT | Estado | Regla |")
        w("|---|---|---|---|---|---|---|---|")
        for a in sorted(ficha["acciones"], key=lambda a: a["t"]):
            w(f"| {f2(a['t'], 1)} | {a['mano']} | {a['gesto'].replace('_', ' ')} | {a['objeto']} | {a['confianza']} | {a['at']} | "
              f"{a['estado'].replace('_', ' ')} | {a['motivo']} |")
        w("")
        for m, r in ficha["recuento"].items():
            w(f"- Mano {ocra.NOMBRE_MANO[m]}: {r['min']}–{r['max']} AT por ciclo"
              + (f"; rechazadas: {', '.join(x['gesto'].replace('_', ' ') for x in r['rechazadas'])}" if r["rechazadas"] else ""))
        w("")
    v = oc.get("validez")
    if v:
        w("### Validez del vídeo para OCRA")
        w("")
        w(f"Resultado: **{ {'verde': 'sí', 'ambar': 'con reservas', 'rojo': 'no recomendable'}[v['nivel']] }**. "
          f"Ciclo: {f2(v['ciclo_s'], 1) if v.get('ciclo_s') else '—'} s ({v.get('ciclo_fuente') or 'sin determinar'}).")
        w("")
        for mo in v["motivos"]:
            w(f"- {mo}")
        for mo in v["como_mejorar"]:
            w(f"- Cómo mejorar: {mo}")
        w("")
    mp = oc.get("mediapipe")
    if mp:
        w("### Lo que aporta MediaPipe (opcional en OCRA)")
        w("")
        per = mp.get("periodicidad") or {}
        if per.get("ciclo_s"):
            w(f"- Ciclo por periodicidad de brazos: {f2(per['ciclo_s'], 1)} s (autocorrelación {f2(per['confianza'])}, "
              f"{f2(per['ciclos'], 1)} ciclos en el vídeo){'' if per.get('fiable') else ' — poco fiable'}.")
        else:
            w(f"- Ciclo por periodicidad: no determinado ({per.get('motivo', 'sin datos')}).")
        for m, d in (mp.get("posturas") or {}).items():
            w(f"- Mano {ocra.NOMBRE_MANO[m]}: " + "; ".join(
                f"{ARTIC[a].lower()} {100 * x['min']:.0f}–{100 * x['max']:.0f} % del tiempo en postura forzada (medido el "
                f"{x['cobertura']:.0f} %)" for a, x in d.items()) + ".")
        n = sum(len(x) for x in (mp.get("candidatos") or {}).values())
        if n:
            w(f"- {n} instantes candidatos a acción técnica (paradas o cambios de velocidad de la mano), marcados en las láminas.")
        w("")
    w("### Sensibilidad")
    w("")
    manos = [m for m in ("dch", "izq") if m in res["manos"]]
    w("| Caso | " + " | ".join(f"Mano {ocra.NOMBRE_MANO[m]}" for m in manos) + " |")
    w("|---|" + "---|" * len(manos))
    for s in res["sensibilidad"]:
        w(f"| {s['caso']} | " + " | ".join(f"{f2(s[m]['indice'])}" for m in manos if m in s) + " |")
    w("")
    w("### Trazabilidad")
    w("")
    w("| Dato | Mano | Valor | Origen | Nota |")
    w("|---|---|---|---|---|")
    for f in res["trazabilidad"]:
        w(f"| {f['dato']} | {f['mano']} | {f['valor']} | {f['origen']} | {f['nota']} |")
    w("")
    return "\n".join(L)
