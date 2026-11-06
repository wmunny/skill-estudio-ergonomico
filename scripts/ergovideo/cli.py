"""Línea de órdenes: inspeccionar vídeos y hacer el estudio OWAS, REBA y RULA."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

from . import ergo, grabacion, informe, medidas, muestreo, pose, visual
from .config import MEDIDAS, Config
from .reglas import CONVENCIONES
from .tablas import CONVENCION_CARGA_OWAS, codigo_carga


def _json(o):
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)


def leer_tramos(ruta: str | None) -> list[dict]:
    """CSV `video;inicio_s;fin_s;kg` (video vacío = todos)."""
    if not ruta:
        return []
    with open(ruta, encoding="utf-8-sig") as fh:
        filas = list(csv.DictReader(fh, delimiter=";"))
    return [dict(video=(f.get("video") or "").strip(), inicio=float(f["inicio_s"].replace(",", ".")),
                 fin=float(f["fin_s"].replace(",", ".")), kg=float(f["kg"].replace(",", "."))) for f in filas]


def funcion_carga(kg: float | None, tramos: list[dict]):
    """kg declarados en un instante (o None si no se han declarado)."""
    def carga_en(t: float, video: str | None) -> float | None:
        for tr in tramos:
            if (not tr["video"] or video is None or tr["video"] == video) and tr["inicio"] <= t < tr["fin"]:
                return tr["kg"]
        return kg
    return carga_en


AGARRE = {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 3}
SI_NO = {"si": True, "sí": True, "no": False, None: None}


def construir_tarea(args) -> ergo.Tarea:
    """Datos declarados. Lo que no se declara queda desconocido (None) y se puntúa como rango."""
    actividad = {}
    if args.actividad is not None:
        elegidos = {x.strip().lower() for x in args.actividad.split(",") if x.strip()}
        for a in elegidos - {"ninguna"}:
            if a not in ergo.INDICADORES:
                raise SystemExit(f"--actividad: valor no válido «{a}» (estatica, repetitiva, cambios o ninguna)")
        actividad = {k: (k in elegidos) for k in ergo.INDICADORES}
    return ergo.Tarea(
        carga_kg=args.carga_kg if not args.tramos_carga else None, fuerza_brusca=SI_NO[args.fuerza_brusca],
        agarre=AGARRE[args.agarre] if args.agarre else None, actividad=actividad,
        muneca=None if args.muneca == "auto" else args.muneca,
        muneca_desviada=SI_NO[args.muneca_desviada], muneca_giro_extremo=SI_NO[args.muneca_giro_extremo],
        hombro_elevado=SI_NO[args.hombro_elevado], brazo_apoyado=SI_NO[args.brazo_apoyado],
        brazo_rotado=SI_NO[args.brazo_rotado], cuello_girado=SI_NO[args.cuello_girado],
        cuello_inclinado=SI_NO[args.cuello_inclinado], apoyo_piernas=args.apoyo_piernas)


def inspeccionar(args) -> int:
    out = []
    for v in args.video:
        i = pose.info_video(v)
        consejos = []
        if i["duracion"] < 20 * 60:
            consejos.append(f"Dura {i['duracion'] / 60:.1f} min: OWAS pide 20–40 min; el % de tiempo tendrá un margen amplio.")
        if i["alto"] < 720:
            consejos.append("Resolución por debajo de 1280×720.")
        out.append(dict(video=v, **i, consejos=consejos,
                        tiempo_estimado_min=round(i["duracion"] * min(args.fps_analisis, i["fps"]) * 0.04 / 60, 1)))
    print(json.dumps(out, ensure_ascii=False, indent=2, default=_json))
    return 0


def _rango(a, b) -> str:
    return f"{a}" if a == b else f"{a}–{b}"


def analizar(args) -> int:
    cfg = Config()
    cfg.muestreo.intervalo_s = args.intervalo
    cfg.muestreo.sin_margen = args.sin_margen
    cfg.modo_angulos = args.angulos
    cfg.postura_base = args.postura_base
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "capturas").mkdir(exist_ok=True)

    videos = [Path(v) for v in args.video]
    nombres = [v.name for v in videos]
    if len(set(nombres)) != len(nombres):
        nombres = [f"{k + 1}_{v.name}" for k, v in enumerate(videos)]
    desfases = [float(x) for x in args.desfases.split(",")] if args.desfases else [0.0] * len(videos)
    if len(desfases) != len(videos):
        print("--desfases debe tener un valor por vídeo", file=sys.stderr)
        return 2
    modo = args.modo if len(videos) > 1 else "combinar"
    metodos = [m.strip().lower() for m in args.metodos.split(",")]

    fuentes, poses = [], []
    for v, nom, des in zip(videos, nombres, desfases):
        print(f"MediaPipe: {v.name}…", file=sys.stderr)
        p = pose.estimar(v, args.fps_analisis, args.modelo, cache_dir=salida / "cache")
        if p.detectado.mean() == 0:
            print(f"No se detecta ninguna persona en {v.name}.", file=sys.stderr)
            return 3
        res = medidas.calcular(p, cfg)
        poses.append(p)
        fuentes.append(dict(nombre=nom, res=res, duracion=p.duracion, desfase=des))

    tramos = leer_tramos(args.tramos_carga)
    carga_en = funcion_carga(args.carga_kg, tramos)
    obs = muestreo.observar(fuentes, cfg, carga_en, modo)
    if not obs:
        print("No hay observaciones (¿vídeos demasiado cortos o sin solape?).", file=sys.stderr)
        return 3
    print("Estadística OWAS…", file=sys.stderr)
    resumen = muestreo.resumir(obs, fuentes, cfg)
    diags = [grabacion.diagnostico(p, f["res"], cfg.filtros.visibilidad) for p, f in zip(poses, fuentes)]

    # REBA y RULA (los dos lados de RULA), por vídeo.
    tarea = construir_tarea(args)
    ergos = {}
    if "reba" in metodos or "rula" in metodos:
        print("REBA y RULA…", file=sys.stderr)
        for f in fuentes:
            fs = ergo.serie(f["res"], cfg, tarea)
            d = dict(serie=fs)
            if "reba" in metodos:
                d["reba"] = ergo.peor_postura(fs, "reba")
                d["reba_val"] = ergo.validar_pico(d["reba"], "reba")
                if d["reba"].get("evaluable"):
                    d["reba"]["trazabilidad"] = ergo.trazabilidad(f["res"], d["reba"]["indice_pico"], ergo.CLAVES_REBA + [
                        "brazo_abd_I", "brazo_abd_D", "muneca_I", "muneca_D", "tronco_giro", "tronco_lat"], cfg)
            if "rula" in metodos:
                d["rula"] = {s: ergo.peor_postura(fs, "rula", s) for s in "ID"}
                d["rula_val"] = {s: ergo.validar_pico(d["rula"][s], "rula") for s in "ID"}
                d["rula_lado"] = ergo.resumen_rula(d["rula"])
                for s in "ID":
                    if d["rula"][s].get("evaluable"):
                        d["rula"][s]["trazabilidad"] = ergo.trazabilidad(f["res"], d["rula"][s]["indice_pico"], ergo.claves_rula(s) + [
                            f"brazo_abd_{s}", f"muneca_{s}", f"antebrazo_lat_{s}", "tronco_giro", "tronco_lat"], cfg)
            ergos[f["nombre"]] = d

    # Salidas gráficas
    imagenes = visual.graficos(obs, resumen, fuentes, salida, cfg.umbrales)
    capturas, videos_out = [], []
    for p, f in zip(poses, fuentes):
        nom = f["nombre"]
        mis = [o for o in obs if nom in o["indice"] and o["categoria"] is not None]
        elegidas = []
        for cat in (4, 3, 2, 1):
            cand = [o for o in mis if o["categoria"] == cat]
            if cand:
                elegidas.append(max(cand, key=lambda o: sum(o["calidad"].values())))
        for o in elegidas[: args.capturas] if "owas" in metodos else []:
            k = o["indice"][nom]
            tv = o["t_video"][nom]
            ruta = salida / "capturas" / f"{visual._seguro(nom)}_{tv:07.1f}s_owas{o['categoria']}.jpg"
            visual.captura(p, f["res"], k, o, ruta, cfg.filtros.visibilidad, not args.sin_difuminar)
            cod = f"{o['espalda']}{o['brazos']}{o['piernas']}{o['carga']}"
            capturas.append(dict(titulo=f"{nom} · {f'{tv:.1f}'.replace('.', ',')} s · OWAS {cod} · categoría {o['categoria']}",
                                 ruta=str(ruta.relative_to(salida)).replace("\\", "/"), metodo="owas"))
        e = ergos.get(nom, {})
        picos = []
        if e.get("reba", {}).get("evaluable"):
            pk = e["reba"]
            picos.append(("reba", "REBA", pk["indice_pico"], pk["pico"], pk["pico_max"], "peor postura sostenida"))
            if pk.get("breve") and pk["breve"]["indice"] != pk["indice_pico"] and pk["breve"]["pico"] > pk["pico"]:
                b = pk["breve"]
                picos.append(("reba", "REBA", b["indice"], b["pico"], b["pico_max"], "pico breve"))
        for s in "ID":
            pk = e.get("rula", {}).get(s, {})
            if pk.get("evaluable"):
                lado = "izq." if s == "I" else "dch."
                picos.append(("rula", f"RULA {lado}", pk["indice_pico"], pk["pico"], pk["pico_max"], "peor postura sostenida"))
        for met, etiqueta, k, a, b, que in picos[: max(2, args.capturas)]:
            seg = f"{p.times[k]:.1f}".replace(".", ",")
            titulo = f"{nom} · {seg} s · {etiqueta} {_rango(a, b)} ({que})"
            ruta = salida / "capturas" / f"{visual._seguro(nom)}_{p.times[k]:07.1f}s_{etiqueta.replace(' ', '').replace('.', '')}{a}.jpg"
            visual.captura_lineas(p, f["res"], k, [f"t = {p.times[k]:.1f} s   {etiqueta} {_rango(a, b)}", "DEMOSTRACION NO VALIDADA"],
                                  None, ruta, cfg.filtros.visibilidad, not args.sin_difuminar)
            capturas.append(dict(titulo=titulo, ruta=str(ruta.relative_to(salida)).replace("\\", "/"), metodo=met))
        if not args.sin_video:
            print(f"Vídeo con esqueleto: {nom}…", file=sys.stderr)
            rv = visual.video_esqueleto(p, f["res"], obs, nom, salida / f"esqueleto_{visual._seguro(nom)}.mp4",
                                        cfg.filtros.visibilidad, not args.sin_difuminar, ergo_fs=e.get("serie"))
            videos_out.append(rv.name)

    # Datos por observación
    with open(salida / "observaciones.csv", "w", newline="", encoding="utf-8-sig") as fh:
        cols = ["t", "fuente", "t_fotograma", "espalda", "brazos", "piernas", "carga", "categoria", "espalda_posibles",
                "brazos_posibles", "piernas_posibles", "carga_posibles", "categoria_posibles", "vista", "modo",
                "camara_espalda", "camara_brazos", "camara_piernas", "notas"] + list(MEDIDAS) + ["velocidad"]
        wr = csv.writer(fh, delimiter=";")
        wr.writerow(cols)
        for o in obs:
            pos = lambda k: "|".join(map(str, o[k]))  # noqa: E731
            wr.writerow([f"{o['t']:.2f}", o["fuente"], ";".join(f"{v:.2f}" for v in o["t_video"].values()),
                         o["espalda"], o["brazos"], o["piernas"], o["carga"], o["categoria"],
                         pos("espalda_posibles"), pos("brazos_posibles"), pos("piernas_posibles"), pos("carga_posibles"),
                         pos("categoria_posibles"), f"{o['vista']:.0f}" if o["vista"] == o["vista"] else "", o["modo"],
                         o["camara"]["espalda"], o["camara"]["brazos"], o["camara"]["piernas"], ",".join(o["notas"])]
                        + [("" if math.isnan(o["medidas"][k]) else f"{o['medidas'][k]:.3f}") for k in list(MEDIDAS) + ["velocidad"]])

    if tramos:
        carga_texto = "por tramos (" + "; ".join(f"{t['video'] or 'todos'} {t['inicio']:g}–{t['fin']:g} s: {t['kg']:g} kg" for t in tramos) + \
                      (f"), {args.carga_kg:g} kg el resto" if args.carga_kg is not None else "), no declarada el resto (rango)")
    elif args.carga_kg is not None:
        carga_texto = f"{args.carga_kg:g} kg durante todo el vídeo (OWAS código {codigo_carga(args.carga_kg)})"
    else:
        carga_texto = "no declarada: se recorren todos los tramos (rango)"
    modo_texto = ("un solo vídeo" if len(videos) == 1 else
                  "se combinan las observaciones de todos (tomas distintas)" if modo == "combinar" else
                  f"misma tarea grabada a la vez; por instante y región se usa la cámara que mejor ve (desfases {desfases})")
    ergo_ctx = {n: {k: v for k, v in d.items() if k != "serie"} for n, d in ergos.items()}
    ctx = dict(resumen=resumen, diagnosticos=diags, imagenes={k: v.name for k, v in imagenes.items()},
               capturas=capturas, videos=videos_out, umbrales=cfg.umbrales, ventana_s=cfg.muestreo.ventana_s,
               nombres_medidas={k: v["nombre"] for k, v in MEDIDAS.items()}, nombres_fuentes=nombres,
               metodos=metodos, tarea=tarea, ergo=ergo_ctx, sin_margen=args.sin_margen,
               args=dict(carga_texto=carga_texto, turno_h=args.turno_h, modo_texto=modo_texto, modo=modo,
                         postura_base=args.postura_base, angulos=args.angulos))
    md = informe.markdown(ctx)
    (salida / "informe.md").write_text(md, encoding="utf-8")
    (salida / "informe.html").write_text(informe.a_html(md, salida), encoding="utf-8")

    datos = dict(aviso="Demostración no validada", convenciones=dict(CONVENCIONES, carga_owas=CONVENCION_CARGA_OWAS),
                 videos=diags, resumen=resumen, capturas=capturas, videos_esqueleto=videos_out, reba_rula=ergo_ctx,
                 tarea=dict(vars(tarea), no_declarados=tarea.no_declarados()),
                 parametros=dict(intervalo_s=args.intervalo, fps_analisis=args.fps_analisis, modelo=args.modelo, modo=modo,
                                 desfases=desfases, carga_kg=args.carga_kg, tramos_carga=tramos, turno_h=args.turno_h,
                                 postura_base=args.postura_base, angulos=args.angulos, sin_margen=args.sin_margen,
                                 umbrales=vars(cfg.umbrales), filtros=vars(cfg.filtros)))
    (salida / "resumen.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=_json), encoding="utf-8")

    def corto_pico(p, val):
        if not p.get("evaluable"):
            return dict(evaluable=False, validez=val["nivel"])
        return dict(peor_postura=_rango(p["pico"], p["pico_max"]), estado=p["estado"], t=round(p["t_pico"], 1),
                    nivel=_rango(p["nivel"][1], p["nivel_max"][1]), validez=val["nivel"],
                    pico_breve=(_rango(p["breve"]["pico"], p["breve"]["pico_max"]) if p.get("breve") else None))
    corto = dict(
        informe=str(salida / "informe.html"), observaciones=resumen["n_observaciones"],
        duracion_s=round(resumen["duracion_s"], 1), n_efectiva_min=round(resumen["n_efectiva_min"], 1),
        owas_categorias_nominales={c: round(v["porcentaje"], 1) for c, v in resumen["combinaciones"]["por_categoria"].items()},
        owas_categoria_max=resumen["combinaciones"]["categoria_max"],
        owas_categoria_max_posible=resumen["combinaciones"]["categoria_max_posible"],
        owas_cobertura_nominal={r: round(x["cobertura"], 1) for r, x in resumen["regiones"].items()},
        owas_porcentajes={r: {c: dict(nominal=round(d["porcentaje"], 1), rango=[round(x) for x in d["rango"]],
                                      categoria=d["categoria"], categorias_posibles=d["categoria_rango"])
                              for c, d in x["codigos"].items() if d["rango"][1] > 0}
                          for r, x in resumen["regiones"].items()},
        reba={n: corto_pico(d["reba"], d["reba_val"]) for n, d in ergos.items() if "reba" in d},
        rula={n: dict({s: corto_pico(d["rula"][s], d["rula_val"][s]) for s in "ID"}, peor_lado=d["rula_lado"])
              for n, d in ergos.items() if "rula" in d},
        avisos=resumen["avisos"], consejos=[c for d in diags for c in d["consejos"]],
        no_declarados=tarea.no_declarados())
    print(json.dumps(corto, ensure_ascii=False, indent=2, default=_json))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="estudio_video", description="Estudio ergonómico (OWAS, REBA, RULA) a partir de vídeo con MediaPipe Pose (demostración no validada).")
    sub = ap.add_subparsers(dest="orden", required=True)

    a = sub.add_parser("inspeccionar", help="Datos básicos de los vídeos (sin MediaPipe)")
    a.add_argument("--video", action="append", required=True)
    a.add_argument("--fps-analisis", type=float, default=10.0)
    a.set_defaults(func=inspeccionar)

    b = sub.add_parser("analizar", help="Estudio OWAS, REBA y RULA")
    b.add_argument("--video", action="append", required=True, help="Vídeo (repetible)")
    b.add_argument("--salida", required=True)
    b.add_argument("--metodos", default="owas,reba,rula", help="Métodos, separados por comas: owas, reba, rula")
    b.add_argument("--carga-kg", type=float, default=None, help="Carga o fuerza (kg) durante todo el vídeo; sin declarar = rango")
    b.add_argument("--tramos-carga", default=None, help="CSV video;inicio_s;fin_s;kg (OWAS por tramos)")
    b.add_argument("--fuerza-brusca", choices=["si", "no"], default=None, help="Cargas o fuerzas aplicadas bruscamente")
    b.add_argument("--agarre", choices=list(AGARRE), default=None, help="REBA: calidad del agarre")
    b.add_argument("--actividad", default=None, help="estatica, repetitiva, cambios (separadas por comas) o ninguna")
    b.add_argument("--muneca", choices=["auto", "neutra", "menos15", "mas15"], default="auto",
                   help="auto: medir con los puntos de la mano (poco fiable); o declarar la flexión de la muñeca")
    for nombre, ayuda in (("muneca-desviada", "REBA: torsión o desviación; RULA: desviación radial o cubital"),
                          ("muneca-giro-extremo", "RULA: pronación o supinación extrema"),
                          ("hombro-elevado", "hombro elevado"), ("brazo-apoyado", "brazo apoyado o a favor de la gravedad"),
                          ("brazo-rotado", "REBA: brazo rotado"), ("cuello-girado", "cabeza rotada"),
                          ("cuello-inclinado", "cabeza inclinada lateralmente")):
        b.add_argument(f"--{nombre}", choices=["si", "no"], default=None, help=ayuda)
    b.add_argument("--apoyo-piernas", choices=["bilateral", "unilateral"], default=None,
                   help="REBA/RULA: apoyo de las piernas observado por el técnico")
    b.add_argument("--turno-h", type=float, default=None, help="Duración del turno (h), para expresar minutos por turno")
    b.add_argument("--intervalo", type=float, default=1.0, help="Segundos entre observaciones OWAS")
    b.add_argument("--fps-analisis", type=float, default=10.0, help="Fotogramas por segundo analizados con MediaPipe")
    b.add_argument("--modelo", choices=["full", "heavy"], default="full")
    b.add_argument("--modo", choices=["combinar", "mejor-camara"], default="combinar",
                   help="combinar: tomas distintas; mejor-camara: cámaras sincronizadas de la misma toma")
    b.add_argument("--desfases", default=None, help="Con mejor-camara: segundos a sumar a cada vídeo, separados por comas")
    b.add_argument("--postura-base", choices=["auto", "de_pie", "sentado"], default="auto")
    b.add_argument("--angulos", choices=["auto", "2d", "3d"], default="auto")
    b.add_argument("--sin-margen", action="store_true", help="Aplicar los umbrales sin margen de medida (solo para comparar)")
    b.add_argument("--capturas", type=int, default=4, help="Capturas por vídeo y método")
    b.add_argument("--sin-video", action="store_true", help="No generar el vídeo con el esqueleto")
    b.add_argument("--sin-difuminar", action="store_true", help="No difuminar la cara (solo con consentimiento)")
    b.set_defaults(func=analizar)

    args = ap.parse_args(argv)
    return args.func(args)
