"""Informe ergonómico del puesto (HTML autocontenido con dos pestañas).

- «Informe ergonómico»: para la dirección. Qué problemas tiene el puesto, en qué se basa (OWAS, REBA, RULA) y qué
  medidas aplicar, con prioridad. Muy visual: indicadores, mapa corporal, línea de tiempo, capturas anotadas, plan.
- «Detalle técnico»: validez del vídeo, revisión visual, rangos, trazabilidad… (el informe técnico completo).

Los datos salen de `informe_datos.json` (escrito por `analizar`). Si existe `adaptacion.json` (Claude concreta las
medidas y la conclusión al puesto), se integra marcando qué es de catálogo y qué es propuesta adaptada.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from .catalogo import REGIONES, TIPOS_MEDIDA
from .hallazgos import URGENCIAS

GRAV = {"alta": "Alta", "media": "Media", "baja": "Baja"}
COLOR_URG = ["var(--r0)", "var(--r1)", "var(--r2)", "var(--r3)", "var(--r4)"]


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _num(x, d=0) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def _img(base: Path, rel: str | None) -> str:
    if not rel:
        return ""
    p = base / rel
    if not p.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


# ------------------------------------------------------------------ gráficos SVG

def mapa_corporal(hallazgos: list[dict]) -> str:
    """Silueta de frente (el lado izquierdo del trabajador queda a la derecha) coloreada por la peor gravedad."""
    peor = {}
    rango = {"alta": 3, "media": 2, "baja": 1}
    for h in hallazgos:
        if h["region"] in ("hombro", "muneca"):
            claves = [f"{h['region']}_{h['lado']}"] if h.get("lado") else [f"{h['region']}_I", f"{h['region']}_D"]
        elif h["region"] == "global":
            continue
        else:
            claves = [h["region"]]
        for k in claves:
            if rango[h["gravedad"]] > rango.get(peor.get(k), 0):
                peor[k] = h["gravedad"]
    col = lambda k: {"alta": "var(--g-alta)", "media": "var(--g-media)", "baja": "var(--g-baja)"}.get(peor.get(k), "var(--g-no)")  # noqa: E731

    def espejo(d):
        import re
        return re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", lambda m: f"{200 - float(m.group(1)):g} {m.group(2)}", d)
    brazo = "M68 84 L52 90 L44 160 L58 163 L66 104 Z"
    ante = "M44 163 L58 163 L55 232 L41 232 Z"
    partes = [
        f'<circle cx="100" cy="40" r="22" fill="var(--g-no)"/>',
        f'<rect x="90" y="62" width="20" height="16" rx="4" fill="{col("cuello")}"><title>Cuello</title></rect>',
        f'<path d="M70 80 L130 80 L126 200 L74 200 Z" fill="{col("espalda")}"><title>Espalda</title></path>',
        f'<path d="{brazo}" fill="{col("hombro_D")}"><title>Hombro y brazo derecho</title></path>',
        f'<path d="{espejo(brazo)}" fill="{col("hombro_I")}"><title>Hombro y brazo izquierdo</title></path>',
        f'<path d="{ante}" fill="{col("muneca_D")}"><title>Antebrazo y muñeca derecha</title></path>',
        f'<path d="{espejo(ante)}" fill="{col("muneca_I")}"><title>Antebrazo y muñeca izquierda</title></path>',
        f'<circle cx="48" cy="243" r="10" fill="{col("muneca_D")}"/>',
        f'<circle cx="152" cy="243" r="10" fill="{col("muneca_I")}"/>',
        f'<path d="M74 203 L98 203 L95 380 L77 380 Z" fill="{col("piernas")}"><title>Piernas</title></path>',
        f'<path d="M102 203 L126 203 L123 380 L105 380 Z" fill="{col("piernas")}"><title>Piernas</title></path>',
        '<text x="30" y="395" class="svg-et">dch.</text><text x="170" y="395" class="svg-et" text-anchor="end">izq.</text>',
    ]
    return f'<svg viewBox="0 0 200 400" class="silueta" role="img" aria-label="Zonas del cuerpo con riesgo">{"".join(partes)}</svg>'


def linea_tiempo(serie: dict, fases: list[dict], hallazgos: list[dict]) -> str:
    dur = max(serie["duracion"], 1e-6)
    W, x0, ancho = 900, 70, 820
    X = lambda t: x0 + ancho * t / dur  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} 150" class="linea" role="img" aria-label="Nivel de riesgo a lo largo de la tarea">']
    for i, f in enumerate(fases):
        a, b = X(float(f["inicio"])), X(float(f["fin"]))
        out.append(f'<rect x="{a:.1f}" y="6" width="{max(1, b - a - 2):.1f}" height="26" rx="3" class="fase"/>')
        if b - a > 46:
            out.append(f'<text x="{a + 4:.1f}" y="23" class="svg-fase">{_e(f.get("descripcion", "")[:max(4, int((b - a) / 6.5))])}</text>')
    for fila, (clave, nombre) in enumerate((("reba", "REBA"), ("rula", "RULA"))):
        y = 44 + fila * 34
        out.append(f'<text x="{x0 - 8}" y="{y + 18}" class="svg-et" text-anchor="end">{nombre}</text>')
        ts, us = serie["t"], serie[clave]
        for i, (t, u) in enumerate(zip(ts, us)):
            t2 = ts[i + 1] if i + 1 < len(ts) else dur
            colr = "var(--g-no)" if u is None else COLOR_URG[u]
            out.append(f'<rect x="{X(t):.1f}" y="{y}" width="{max(0.8, X(t2) - X(t) + 0.3):.1f}" height="26" fill="{colr}"/>')
    for n, h in enumerate(hallazgos, 1):
        if h.get("t_ejemplo") is None:
            continue
        x = X(h["t_ejemplo"])
        out.append(f'<line x1="{x:.1f}" y1="112" x2="{x:.1f}" y2="40" class="marca"/>'
                   f'<circle cx="{x:.1f}" cy="124" r="10" class="marca-c"/><text x="{x:.1f}" y="128" class="svg-n" text-anchor="middle">{n}</text>')
    for k in range(0, int(dur) + 1, max(1, int(dur / 10) or 1)):
        out.append(f'<text x="{X(k):.1f}" y="148" class="svg-t" text-anchor="middle">{k} s</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ página

CSS = """
:root{
  /* Informe para dirección: columna de lectura amplia; hallazgos en tarjetas con captura a la izquierda. */
  --papel:#f7f6f2; --tarjeta:#ffffff; --tinta:#1f2523; --suave:#5d6863; --linea:#dcdfd8; --acento:#22606b;
  --g-alta:#c8432f; --g-media:#e58a2b; --g-baja:#e9c547; --g-no:#d9ddd6;
  --r0:#4f9a63; --r1:#9cc06a; --r2:#e9c547; --r3:#e58a2b; --r4:#c8432f;
  --f-tit:"IBM Plex Sans", "Segoe UI", system-ui, sans-serif; --f-txt:"Source Serif 4", Georgia, serif;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --papel:#141817; --tarjeta:#1c2120; --tinta:#e6ebe8; --suave:#9fa9a4; --linea:#2d3533; --acento:#7cc2cc;
  --g-no:#3a423f; color-scheme:dark}}
:root[data-theme="dark"]{--papel:#141817; --tarjeta:#1c2120; --tinta:#e6ebe8; --suave:#9fa9a4; --linea:#2d3533;
  --acento:#7cc2cc; --g-no:#3a423f; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--papel);color:var(--tinta);font:16px/1.55 var(--f-txt)}
.pag{max-width:1080px;margin:0 auto;padding:24px max(16px, env(safe-area-inset-right,0px)) 64px max(16px, env(safe-area-inset-left,0px))}
h1,h2,h3,.pest button,.pill,.ind,.tabla,.datos{font-family:var(--f-tit)}
h1{font-size:1.9rem;line-height:1.2;margin:.2rem 0 .3rem;text-wrap:balance}
h2{font-size:1.3rem;margin:2.2rem 0 .8rem}
h3{font-size:1.08rem;margin:0 0 .3rem}
.sub{color:var(--suave);margin:0 0 1rem}
.pest{display:flex;gap:4px;border-bottom:2px solid var(--linea);margin:1rem 0 1.4rem}
.pest button{border:0;background:none;padding:.6rem 1rem;font-size:.95rem;color:var(--suave);cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px}
.pest button[aria-selected="true"]{color:var(--tinta);border-bottom-color:var(--acento);font-weight:600}
.pest button:focus-visible{outline:2px solid var(--acento)}
.conclusion{background:var(--tarjeta);border:1px solid var(--linea);border-left:6px solid var(--urg);border-radius:6px;padding:1rem 1.2rem}
.conclusion .urg{font-family:var(--f-tit);font-weight:700;font-size:1.15rem;color:var(--tinta)}
.inds{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:1rem}
.ind{background:var(--tarjeta);border:1px solid var(--linea);border-radius:6px;padding:.8rem 1rem;border-top:5px solid var(--c)}
.ind .m{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.ind .n{font-size:1.25rem;font-weight:700;margin:.15rem 0}
.ind .a{font-size:.88rem}
.resumen{display:grid;grid-template-columns:200px minmax(0,1fr);gap:24px;align-items:start;margin-top:.6rem}
.silueta{width:100%;max-width:200px;height:auto}
.svg-et{font:12px var(--f-tit);fill:var(--suave)}.svg-fase{font:11px var(--f-tit);fill:var(--tinta)}
.svg-t{font:10px var(--f-tit);fill:var(--suave)}.svg-n{font:bold 11px var(--f-tit);fill:#fff}
.fase{fill:var(--tarjeta);stroke:var(--linea)}.marca{stroke:var(--tinta);stroke-dasharray:2 3;opacity:.6}.marca-c{fill:var(--acento)}
.linea{width:100%;height:auto;display:block}
.leyenda{display:flex;flex-wrap:wrap;gap:12px;font:12px var(--f-tit);color:var(--suave);margin-top:.4rem}
.leyenda i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.lista-reg{display:flex;flex-wrap:wrap;gap:8px;margin:.2rem 0 0}
.hall{display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);gap:18px;background:var(--tarjeta);border:1px solid var(--linea);border-radius:6px;padding:14px;margin:14px 0}
.hall img{width:100%;border-radius:4px;display:block}
.hall .sinimg{display:grid;place-items:center;min-height:120px;background:var(--papel);border-radius:4px;color:var(--suave);font:13px var(--f-tit);padding:1rem;text-align:center}
.cab{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.nro{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--acento);color:#fff;font:700 14px var(--f-tit);flex:none}
.pill{display:inline-block;padding:.1rem .55rem;border-radius:99px;font-size:.78rem;font-weight:600;color:#fff;background:var(--c)}
.datos{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.88rem;color:var(--suave);margin:.4rem 0}
.datos b{color:var(--tinta)}
.respaldo{font-size:.85rem;color:var(--suave);margin:.5rem 0 0;padding-left:1.1rem}
.adapt{border-left:3px solid var(--acento);padding-left:.7rem;margin:.6rem 0}
.etq{font:600 11px var(--f-tit);text-transform:uppercase;letter-spacing:.05em;color:var(--acento)}
.tabla{width:100%;border-collapse:collapse;font-size:.9rem;background:var(--tarjeta)}
.tabla th,.tabla td{border-bottom:1px solid var(--linea);padding:.55rem .6rem;text-align:left;vertical-align:top}
.tabla th{font-weight:600;color:var(--suave);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em}
.envoltura{overflow-x:auto;border:1px solid var(--linea);border-radius:6px}
.pie{margin-top:2.4rem;font-size:.85rem;color:var(--suave);border-top:1px solid var(--linea);padding-top:.8rem}
.tec table{border-collapse:collapse;font:13px var(--f-tit);display:block;overflow-x:auto;margin:.6rem 0 1rem}
.tec th,.tec td{border:1px solid var(--linea);padding:4px 7px;text-align:left}.tec th{background:var(--tarjeta)}
.tec img{max-width:100%;border:1px solid var(--linea);border-radius:4px}
.tec blockquote{background:var(--tarjeta);border-left:4px solid var(--g-media);margin:1em 0;padding:.6em 1em}
@media (max-width:720px){.resumen{grid-template-columns:1fr}.silueta{max-width:160px;margin:auto}.hall{grid-template-columns:1fr}}
@media print{.pest,#tecnico{display:none!important}#ergonomico{display:block!important}body{background:#fff}}
"""

JS = """
document.querySelectorAll('.pest button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.pest button').forEach(x=>x.setAttribute('aria-selected', x===b));
  document.querySelectorAll('.panel').forEach(p=>p.hidden = p.id!==b.dataset.p);
  try{localStorage.setItem('pestana', b.dataset.p)}catch(e){}
}));
try{const p=localStorage.getItem('pestana'); if(p==='tecnico'){document.querySelector('[data-p=tecnico]').click()}}catch(e){}
"""


def render(datos: dict, base: Path, adaptacion: dict | None, tecnico_html: str) -> str:
    ad = adaptacion or {}
    ad_h = ad.get("hallazgos", {})
    hall = datos["hallazgos"]
    urg = datos["urgencia_global"]
    tarea = datos.get("tarea") or "Puesto analizado a partir de vídeo"
    titulo = ad.get("titulo") or (tarea.split(":")[0] if ":" in tarea and len(tarea) > 70 else tarea)
    descripcion = ad.get("descripcion_tarea") or (tarea.split(":", 1)[1].strip().capitalize() if titulo != tarea else "")
    n_alta = sum(1 for h in hall if h["gravedad"] == "alta")
    # Conclusión
    if ad.get("conclusion"):
        concl = f'<p>{_e(ad["conclusion"])}</p><p class="etq">Redactada por Claude a partir de los hallazgos</p>'
    else:
        principales = ", ".join(h["titulo"].lower() for h in hall[:3]) or "no se han detectado posturas de riesgo relevantes"
        concl = (f"<p>Se han identificado {len(hall)} problemas ergonómicos, {n_alta} de gravedad alta. Los principales: "
                 f"{_e(principales)}.</p>")
    from . import informe_ocra
    sintesis = informe_ocra.semaforos(datos["indicadores"]) if len(datos["metodos"]) > 1 and datos["indicadores"] else ""
    inds = "" if sintesis else "".join(
        f'<div class="ind" style="--c:{COLOR_URG[i["urgencia"]]}"><div class="m">{_e(i["metodo"])} · {_e(i["que"])}</div>'
        f'<div class="n">{_e(i["nivel"])}</div><div class="a">{_e(i["accion"])}</div>'
        f'<div class="a" style="color:var(--suave)">{_e(i.get("detalle", ""))}</div></div>' for i in datos["indicadores"])
    regiones = {}
    for h in hall:
        regiones.setdefault(h["region"], []).append(h)
    reg_txt = "".join(
        f'<span class="pill" style="--c:var(--g-{min((x["gravedad"] for x in hs), key=["alta", "media", "baja"].index)})">'
        f'{_e(REGIONES[r])}</span>' for r, hs in regiones.items())

    tarjetas = []
    for n, h in enumerate(hall, 1):
        a = ad_h.get(h["id"], {})
        datos_h = []
        if h.get("porcentaje") is not None:
            if h.get("minimo"):
                datos_h.append(f"<span>al menos el <b>{_num(h['porcentaje'])} %</b> del tiempo (esta zona solo se ve el "
                               f"{_num(h['visible'])} %)</span>")
            else:
                datos_h.append(f"<span><b>{_num(h['porcentaje'])} %</b> del tiempo de la tarea</span>")
        if h.get("por_minuto"):
            datos_h.append(f"<span><b>{_num(h['por_minuto'], 1)}</b> veces por minuto</span>")
        if h.get("duracion_media_s"):
            datos_h.append(f"<span>episodios de <b>{_num(h['duracion_media_s'], 1)} s</b> de media</span>")
        if h.get("fases"):
            unicas = list(dict.fromkeys(h["fases"]))
            todas = {f.get("descripcion") for f in datos.get("fases", {}).get(h.get("video"), [])}
            if len(todas) >= 4 and len(set(unicas)) >= 0.6 * len(todas):
                datos_h.append("<span>En <b>casi todo el ciclo</b></span>")
            else:
                datos_h.append(f"<span>Fases: <b>{_e('; '.join(unicas[:3]).lower())}</b></span>")
        img = _img(base, h.get("captura"))
        visual = (f'<img src="{img}" alt="{_e(h["titulo"])}{" a los " + _num(h["t_ejemplo"], 1) + " s" if h.get("t_ejemplo") is not None else ""}">' if img else
                  f'<div class="sinimg">{_e(h.get("detalle") or "Condición de la tarea")}</div>')
        desc = (f'<div class="adapt"><div class="etq">Lo que se ve en este puesto (Claude)</div>{_e(a["descripcion"])}</div>'
                if a.get("descripcion") else "")
        tarjetas.append(
            f'<article class="hall" id="h{n}">{visual}<div><div class="cab"><span class="nro">{n}</span><h3>{_e(h["titulo"])}</h3>'
            f'<span class="pill" style="--c:var(--g-{h["gravedad"]})">Gravedad {GRAV[h["gravedad"]].lower()}</span></div>'
            f'<div class="datos">{"".join(datos_h)}</div>{desc}<p><b>Por qué importa:</b> {_e(h["riesgo"])}</p>'
            f'<ul class="respaldo">{"".join(f"<li>{_e(x)}</li>" for x in h["evidencia"])}</ul></div></article>')

    # Plan de medidas: las adaptadas sustituyen o se añaden a las de catálogo del mismo hallazgo
    numero = {h["id"]: n for n, h in enumerate(hall, 1)}
    filas = []
    sustituidas = {m for a in ad_h.values() for x in a.get("medidas", []) for m in [x.get("sustituye")] if m}
    for m in datos["plan"]:
        if m["id"] in sustituidas:
            continue
        filas.append((m["prioridad"], m["texto"], m["tipo"], m["hallazgos"], "Medida tipo (catálogo)"))
    orden_pr = {h["id"]: m["prioridad"] for m in datos["plan"] for h in [{"id": x} for x in m["hallazgos"]]}
    for hid, a in ad_h.items():
        for x in a.get("medidas", []):
            filas.append((x.get("prioridad") or orden_pr.get(hid, "Media"), x["texto"], x.get("tipo", "ingenieria"), [hid],
                          "Propuesta adaptada al puesto (Claude)"))
    rk = {"Inmediata": 0, "Alta": 1, "Media": 2, "Baja": 3}
    tp_orden = {"ingenieria": 0, "organizativa": 1, "formacion": 2}
    filas.sort(key=lambda f: (rk.get(f[0], 2), f[4].startswith("Medida"), tp_orden.get(f[2], 3)))
    col_pr = {"Inmediata": "var(--g-alta)", "Alta": "var(--g-media)", "Media": "var(--g-baja)", "Baja": "var(--r0)"}
    plan_html = "".join(
        f'<tr><td><span class="pill" style="--c:{col_pr.get(pr, "var(--g-baja)")}">{_e(pr)}</span></td><td>{_e(t)}</td>'
        f'<td>{_e(TIPOS_MEDIDA.get(tp, tp))}</td><td>{", ".join(str(numero[x]) for x in hs if x in numero)}</td>'
        f'<td style="color:var(--suave)">{_e(o)}</td></tr>' for pr, t, tp, hs, o in filas)

    oc = datos.get("ocra")
    ocra_html = ""
    if oc:
        ocra_html = ("<h2>Movimientos repetitivos de la extremidad superior (OCRA)</h2>"
                     + informe_ocra.bloque(oc, base, datos.get("_escenario_ocra")))
    tiempos = "".join(f'<h3 style="margin-top:1rem">{_e(v)}</h3>' * (len(datos["series"]) > 1) +
                      linea_tiempo(s, datos.get("fases", {}).get(v, []), [h for h in hall if h.get("video") == v])
                      for v, s in datos["series"].items())
    leyenda = "".join(f'<span><i style="background:{COLOR_URG[k]}"></i>{_e(URGENCIAS[k])}</span>' for k in range(5))
    metodos_txt = ", ".join(datos["metodos"]).upper()
    if datos["series"]:
        riesgo_t = (f'<h3 style="margin-top:1.2rem">Riesgo a lo largo de la tarea</h3>{tiempos}'
                    f'<div class="leyenda">{leyenda}<span><i style="background:var(--g-no)"></i>Sin dato</span></div>'
                    '<p style="font-size:.85rem;color:var(--suave)">Cada franja es el nivel de actuación de REBA (cuerpo entero) '
                    'y RULA (peor brazo) en cada instante. Los números marcan dónde se ve cada problema.</p>')
    else:
        riesgo_t = ""
    medida_txt = (f"Posturas medidas con visión artificial (MediaPipe Pose) sobre {_e(datos.get('video_txt', 'vídeo'))}."
                  if datos.get("mediapipe", True) else
                  f"Análisis observacional sobre {_e(datos.get('video_txt') or 'datos declarados')} (sin captura de movimiento).")
    principal = f"""
<section class="panel" id="ergonomico">
  <div class="conclusion" style="--urg:{COLOR_URG[urg]}"><div class="urg">{_e(URGENCIAS[urg])}</div>{concl}</div>
  {sintesis}<div class="inds">{inds}</div>
  <h2>Dónde está el riesgo</h2>
  <div class="resumen">{mapa_corporal(hall)}
    <div><p>Zonas del cuerpo afectadas, por la gravedad de su peor problema:</p><div class="lista-reg">{reg_txt or "—"}</div>
    {riesgo_t}</div>
  </div>
  {ocra_html}
  <h2>Problemas identificados</h2>
  {"".join(tarjetas) or "<p>No se han identificado posturas de riesgo relevantes.</p>"}
  <h2>Qué hacer</h2>
  <div class="envoltura"><table class="tabla"><thead><tr><th>Prioridad</th><th>Medida</th><th>Tipo</th><th>Problema</th><th>Origen</th></tr></thead>
  <tbody>{plan_html}</tbody></table></div>
  <p style="font-size:.85rem;color:var(--suave)">Prioridad según la gravedad del problema y el nivel de actuación de los métodos.
  Primero las medidas de diseño del puesto, que eliminan o reducen el riesgo en su origen.</p>
  <div class="pie">Métodos: {metodos_txt} (tablas originales, calculadas en código). {medida_txt}
  <b>Prueba de concepto no validada:</b> no sustituye a la
  evaluación de un técnico de prevención. El detalle de la medida y la validez del vídeo está en la pestaña «Detalle técnico».</div>
</section>"""
    return f"""<title>Informe ergonómico del puesto</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>{CSS}{informe_ocra.CSS}</style>
<main class="pag">
  <p class="etq">Informe ergonómico del puesto</p>
  <h1>{_e(titulo)}</h1>
  <p class="sub">{(_e(descripcion) + "<br>") if descripcion else ""}{_e(datos.get("video_txt", ""))} · {_e(datos.get("fecha", ""))}</p>
  <nav class="pest" role="tablist"><button role="tab" data-p="ergonomico" aria-selected="true">Informe ergonómico</button>
  <button role="tab" data-p="tecnico" aria-selected="false">Detalle técnico</button></nav>
  {principal}
  <section class="panel tec" id="tecnico" hidden>{tecnico_html}</section>
</main>
<script>{JS}</script>"""


def escribir(salida: Path, adaptacion: Path | None = None) -> Path:
    """Genera informe.html a partir de informe_datos.json, informe_tecnico.md y, si existe, adaptacion.json."""
    from .informe import md_a_html
    datos = json.loads((salida / "informe_datos.json").read_text(encoding="utf-8"))
    ad = None
    ruta_ad = adaptacion or (salida / "adaptacion.json")
    if ruta_ad and Path(ruta_ad).exists():
        ad = json.loads(Path(ruta_ad).read_text(encoding="utf-8"))
    if datos.get("ocra") and (ad or {}).get("escenario_ocra"):
        from . import ocra
        e = ad["escenario_ocra"]
        datos["_escenario_ocra"] = dict(ocra.escenario(datos["ocra"]["datos"], e.get("cambios", {})),
                                        titulo=e.get("titulo"), medidas=e.get("medidas", []))
    tecnico = md_a_html((salida / "informe_tecnico.md").read_text(encoding="utf-8"), salida)
    pagina = render(datos, salida, ad, tecnico)
    cabeza, cuerpo = pagina.split('<main class="pag">', 1)
    destino = salida / "informe.html"
    destino.write_text('<!doctype html><html lang="es"><head><meta charset="utf-8">' + cabeza + "</head><body>"
                       '<main class="pag">' + cuerpo + "</body></html>", encoding="utf-8")
    return destino
