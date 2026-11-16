"""OCRA en la línea de órdenes: métodos, datos de organización, ficha de AT, vídeo opcional e informe."""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path

from . import hallazgos as H
from . import informe_ocra, informe_puesto, medidas, ocra, ocra_at, ocra_video, pose, visual
from .config import Config

TODOS = ["owas", "reba", "rula", "ocra"]
POSTURALES = ("owas", "reba", "rula")
APTO = {"verde": "sí", "ambar": "con reservas", "rojo": "no recomendable"}
DATOS_A_PREGUNTAR = [
    "tareas repetitivas del turno y minutos de cada una",
    "duración del turno",
    "pausas con su hora y duración (y la comida)",
    "tareas no repetitivas (y si sirven de recuperación)",
    "tiempo de ciclo o producción por turno",
    "esfuerzo percibido (Borg CR-10) por fase y mano, o «no se sabe»",
    "guantes, herramientas, vibración, precisión, golpes, frío",
    "lateralidad del trabajador (diestro o zurdo)",
]


def leer_metodos(txt: str | None) -> list[str]:
    ms = []
    for m in (txt or "todos").split(","):
        m = m.strip().lower()
        if m in ("todos", "todo", "completo", ""):
            ms += TODOS
        elif m == "owasp":
            ms.append("owas")
        elif m in TODOS:
            ms.append(m)
        else:
            raise SystemExit(f"--metodos: «{m}» no válido (owas, reba, rula, ocra o todos)")
    return list(dict.fromkeys(ms))


def posturales(metodos) -> bool:
    return any(m in POSTURALES for m in metodos)


def estimar_opcional(video: Path, args, cache_dir: Path):
    """MediaPipe para OCRA: se intenta; si falla o no ve a nadie, se sigue sin él."""
    if getattr(args, "sin_pose", False):
        return None
    try:
        p = pose.estimar(video, args.fps_analisis, args.modelo, cache_dir=cache_dir)
    except Exception as e:  # noqa: BLE001 (modelo ausente, vídeo raro…): OCRA sigue por la vía observacional
        print(f"MediaPipe no disponible para {video.name} ({e}); OCRA sigue sin captura de movimiento.", file=sys.stderr)
        return None
    if p.detectado.mean() == 0:
        print(f"MediaPipe no detecta a nadie en {video.name}; OCRA sigue sin captura de movimiento.", file=sys.stderr)
        return None
    return p


def faltan(datos: dict) -> list[str]:
    """Datos de organización que faltan (se preguntan al usuario; si nadie los sabe, rango)."""
    out = []
    ts = datos.get("tareas") or []
    if not ts or any("minutos" not in t for t in ts):
        out.append("minutos de cada tarea repetitiva en el turno (obligatorio)")
    t = datos.get("turno") or {}
    if "rcm" not in datos and not (t.get("inicio") and t.get("fin")):
        out.append("horario del turno con las pausas (si no, RcM se recorre de 0 a 1)")
    for t in ts:
        for m, d in (t.get("manos") or {}).items():
            if not any(k in d for k in ("borg", "fom")):
                out.append(f"Borg por fase de la mano {ocra.NOMBRE_MANO.get(m, m)} (si no, FoM se recorre entero)")
            if not any(k in d for k in ("adicionales", "adm")):
                out.append(f"factores adicionales de la mano {ocra.NOMBRE_MANO.get(m, m)} (si no, rango)")
    if not datos.get("lateralidad"):
        out.append("lateralidad del trabajador")
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------ revisar (láminas del ciclo)

def revisar_ocra(video: Path, p, salida: Path, args, plantilla: Path) -> dict:
    info = pose.info_video(video)
    res = medidas.calcular(p, Config()) if p is not None else None
    per = ocra_video.ciclo_periodicidad(res, info["duracion"]) if res is not None else None
    ciclo = per["ciclo_s"] if per and per.get("fiable") else None
    if args.ciclo_inicio is not None:
        ini = args.ciclo_inicio
        fin = args.ciclo_fin if args.ciclo_fin is not None else ini + (ciclo or 10.0)
    elif ciclo:
        ini = round(max(0.0, (info["duracion"] - ciclo) / 2), 1)
        fin = round(ini + ciclo, 1)
    else:
        ini, fin = 0.0, min(info["duracion"], 12.0)
    fin = min(fin, info["duracion"])
    cand = ocra_video.candidatos_at(p, res, ini, fin) if p is not None else {}
    laminas = ocra_video.laminas_ciclo(video, salida / "revision" / visual._seguro(video.name), ini, fin,
                                       fps=args.fps_ocra, pose=p, candidatos=cand)
    rev = json.loads(plantilla.read_text(encoding="utf-8"))
    conocido = bool(ciclo) or args.ciclo_inicio is not None
    if "ocra" not in rev:
        from .revision import plantilla_ocra
        rev["ocra"] = plantilla_ocra(ini if conocido else None, fin if conocido else None, cand)
        plantilla.write_text(json.dumps(rev, ensure_ascii=False, indent=2), encoding="utf-8")
    elif conocido and (rev["ocra"].get("ciclo") or {}).get("inicio") is None:
        rev["ocra"]["ciclo"].update(inicio=ini, fin=fin)  # ciclo marcado después: se rellena sin tocar la ficha
        rev["ocra"]["candidatos_mediapipe"] = cand
        plantilla.write_text(json.dumps(rev, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(laminas_ocra=[str(x) for x in laminas], ciclo_laminas=[ini, fin], fps_laminas=args.fps_ocra,
                ciclo_propuesto=per, candidatos_at={m: len(v) for m, v in cand.items()},
                aviso=None if ciclo or args.ciclo_inicio is not None else
                "No se ha podido proponer el ciclo: mira las láminas, marca ocra.ciclo y repite con --ciclo-inicio/--ciclo-fin.")


# ------------------------------------------------------------------ estudio OCRA

def _nombre_tarea(revs) -> str | None:
    r = next((r for r in revs if r), None)
    return (r or {}).get("contexto", {}).get("tarea") or None


def estudio(args, videos: list[Path], poses: list, revs: list, ress: list | None = None, salida: Path | None = None,
            datos_extra: dict | None = None) -> dict:
    """Completa los datos de organización con la ficha de AT y lo medido, y calcula OCRA. Lanza DatosOcraInvalidos si
    faltan datos imprescindibles (minutos)."""
    datos = ocra.cargar(args.datos_ocra) if getattr(args, "datos_ocra", None) else {}
    datos = copy.deepcopy(datos or datos_extra or {})
    if getattr(args, "clasificacion_ocra", None):
        datos["clasificacion"] = args.clasificacion_ocra
    k = next((i for i, r in enumerate(revs) if r and r.get("_ocra_ficha")), 0)
    rev = revs[k] if revs else None
    p = poses[k] if poses else None
    video = videos[k] if videos else None
    ficha = (rev or {}).get("_ocra_ficha")
    ficha_in = (rev or {}).get("ocra")
    res = ress[k] if ress and ress[k] is not None else (medidas.calcular(p, Config()) if p is not None else None)
    tareas = datos.setdefault("tareas", [{}])
    t0 = tareas[0]
    t0.setdefault("nombre", datos.get("puesto") or _nombre_tarea(revs) or "Tarea repetitiva")
    validez = None
    if video is not None:
        validez = ocra_video.validar(pose.info_video(video), p, res, ficha_in,
                                     t0.get("ciclo_s") if isinstance(t0.get("ciclo_s"), (int, float)) else None)
    mp = None
    if res is not None:
        mp = dict(periodicidad=(validez or {}).get("periodicidad"), posturas=ocra_video.fracciones_postura(res),
                  candidatos=ocra_video.candidatos_at(p, res, *(
                      (ficha["ciclo"]["inicio"], ficha["ciclo"]["fin"]) if ficha else (None, None))))
    if "ciclo_s" not in t0 and "piezas" not in t0:
        if ficha and ficha["ciclo"]["duracion_s"]:
            t0["ciclo_s"] = dict(valor=round(ficha["ciclo"]["duracion_s"], 2), origen="revisión visual",
                                 nota="ciclo representativo marcado en la revisión")
        elif mp and (mp["periodicidad"] or {}).get("fiable"):
            t0["ciclo_s"] = dict(valor=mp["periodicidad"]["ciclo_s"], origen="medido",
                                 nota="periodicidad de las series de los brazos (MediaPipe)")
    manos = t0.setdefault("manos", {})
    origen_at = "revisión visual, confirmada" if ficha and ficha.get("confirmada") else "revisión visual"
    for m in ("dch", "izq"):
        rec = ficha["recuento"][m] if ficha else None
        if m not in manos and not (rec and rec["max"] > 0):
            continue
        d = manos.setdefault(m, {})
        if "at_ciclo" not in d and "frecuencia" not in d and rec:
            d["at_ciclo"] = ocra_at.at_ciclo_valor(rec, origen_at)
        if "pom" not in d and "posturas" not in d:
            pos = {}
            if mp:
                for a in ("hombro", "codo", "muneca"):
                    pos[a] = ocra_video.postura_como_entrada(mp["posturas"][m][a])
            ag = ((ficha_in or {}).get("posturas") or {}).get(m, {}).get("agarre")
            pos["agarre"] = ag if isinstance(ag, dict) else (
                dict(valor=ag, origen="revisión visual") if ag is not None else None)
            d["posturas"] = pos
        if "rem" not in d and "misma_accion" not in d and ficha:
            ma = ocra_at.misma_accion(ficha["acciones"], m)
            if ma is not None:
                d["misma_accion"] = dict(valor=round(ma, 3), origen="revisión visual",
                                         nota="gesto más repetido / AT del ciclo (por recuento)")
    if not manos:
        raise ocra.DatosOcraInvalidos("no hay acciones técnicas: rellena la ficha (bloque «ocra» de revision.json) o "
                                      "da at_ciclo en --datos-ocra")
    resultado = ocra.calcular(datos)
    capturas = []
    if ficha and video is not None and salida is not None:
        vistos = set()
        for a in sorted([a for a in ficha["acciones"] if a["estado"] == "valida" and a["at"] > 0],
                        key=lambda a: (a["tipo"] in vistos, a["t"])):
            if len(capturas) >= 6:
                break
            if (a["mano"], a["tipo"]) in vistos:
                continue
            vistos.add((a["mano"], a["tipo"]))
            vistos.add(a["tipo"])
            txt = f"{a['t']:.1f} s · mano {a['mano']} · {a['gesto'].replace('_', ' ')} {a['objeto']}".strip()
            ruta = salida / "capturas" / f"ocra_{visual._seguro(video.name)}_{a['t']:06.2f}s_{a['mano']}.jpg"
            if ocra_video.captura_instante(video, a["t"], ruta, txt, p):
                capturas.append(dict(titulo=txt.replace(".", ",", 1), ruta=str(ruta.relative_to(salida)).replace("\\", "/"),
                                     t=a["t"]))
        capturas.sort(key=lambda c: c["t"])
    return dict(datos=datos, resultado=resultado, ficha=ficha, validez=validez, mediapipe=mp, capturas=capturas,
                video=video.name if video is not None else None, faltan=faltan(datos))


def validar_ocra(args, videos, poses, revs, ress=None) -> dict:
    datos = ocra.cargar(args.datos_ocra) if getattr(args, "datos_ocra", None) else {}
    t0 = (datos.get("tareas") or [{}])[0]
    out = {}
    for i, v in enumerate(videos):
        p = poses[i]
        res = ress[i] if ress and ress[i] is not None else (medidas.calcular(p, Config()) if p is not None else None)
        r = revs[i]
        val = ocra_video.validar(pose.info_video(v), p, res, (r or {}).get("ocra"),
                                 t0.get("ciclo_s") if isinstance(t0.get("ciclo_s"), (int, float)) else None)
        d = dict(apto=APTO[val["nivel"]], motivos=val["motivos"], como_mejorar=val["como_mejorar"],
                 ciclo_s=val["ciclo_s"], ciclo_fuente=val["ciclo_fuente"],
                 mediapipe="sí" if p is not None else "no (vía observacional)")
        f = (r or {}).get("_ocra_ficha")
        if f:
            d["ficha_at"] = {m: dict(at=f"{x['min']}–{x['max']}" if x["min"] != x["max"] else x["min"],
                                     rechazadas=[f"{y['t']:g} s {y['gesto']}: {y['motivo']}" for y in x["rechazadas"]],
                                     dudosas=[f"{y['t']:g} s {y['gesto']}: {y['motivo']}" for y in x["dudosas"]])
                             for m, x in f["recuento"].items()}
            d["ficha_confirmada"] = f["confirmada"]
        out[v.name] = d
    return dict(por_video=out, datos_que_faltan=faltan(datos) if datos else DATOS_A_PREGUNTAR)


# ------------------------------------------------------------------ informe solo OCRA

def escribir_solo_ocra(salida: Path, oc: dict, revs: list, video_txt: str, con_mediapipe: bool) -> Path:
    from .informe import AVISO
    res = oc["resultado"]
    hall = H.ordenar(informe_ocra.hallazgos(res))
    informe_ocra.adjuntar_capturas(hall, oc)
    inds = [informe_ocra.indicador(res)]
    urg = res["urgencia"]
    datos_inf = dict(
        tarea=_nombre_tarea(revs) or oc["datos"]["tareas"][0].get("nombre"), fecha=datetime.now().strftime("%d/%m/%Y"),
        video_txt=video_txt, metodos=["ocra"], indicadores=inds, urgencia_global=urg, hallazgos=hall,
        plan=H.plan(hall, urg), series={}, fases={}, ocra=oc, mediapipe=con_mediapipe)
    (salida / "informe_datos.json").write_text(json.dumps(datos_inf, ensure_ascii=False, indent=2, default=_json),
                                               encoding="utf-8")
    md = (f"# Estudio OCRA\n\n> {AVISO}\n\nGenerado el {datetime.now():%d/%m/%Y %H:%M} con la skill "
          f"*estudio-ergonomico-video* ({'con' if con_mediapipe else 'sin'} MediaPipe).\n\n" + informe_ocra.markdown(oc))
    (salida / "informe_tecnico.md").write_text(md, encoding="utf-8")
    (salida / "resumen.json").write_text(json.dumps(dict(aviso="Demostración no validada", ocra=oc), ensure_ascii=False,
                                                    indent=2, default=_json), encoding="utf-8")
    return informe_puesto.escribir(salida)


def corto(oc: dict) -> dict:
    res = oc["resultado"]
    return dict(
        clasificacion=res["clasificacion_nombre"],
        manos={m: dict(indice=ocra.texto_indice(x), nivel_peor_caso=x["clase_max"]["nivel"],
                       color=x["clase_max"]["color"],
                       frecuencia=[round(v, 1) for v in x["frecuencia_rango"]])
               for m, x in res["manos"].items()},
        rcm=res["rcm"]["nominal"] if res["rcm"]["nominal"] is not None else [res["rcm"]["min"], res["rcm"]["max"]],
        ficha_confirmada=(oc.get("ficha") or {}).get("confirmada"),
        datos_que_faltan=oc.get("faltan"), aviso_normativo=res["aviso_normativo"])


def _json(o):
    from .cli import _json as j
    return j(o)


# ------------------------------------------------------------------ orden «ocra» (sin vídeo)

def orden_ocra(args) -> int:
    """OCRA con datos manuales o un JSON, sin vídeo (opcionalmente con una ficha de AT en un revision.json)."""
    revs = []
    if args.revision:
        from .revision import RevisionInvalida, cargar
        try:
            revs = [cargar(args.revision)]
        except RevisionInvalida as e:
            print(str(e), file=sys.stderr)
            return 2
    try:
        oc = estudio(args, [], [], revs)
    except ocra.DatosOcraInvalidos as e:
        print(f"Datos OCRA no válidos: {e}", file=sys.stderr)
        return 2
    out = corto(oc)
    if args.salida:
        salida = Path(args.salida)
        salida.mkdir(parents=True, exist_ok=True)
        out["informe"] = str(escribir_solo_ocra(salida, oc, revs, "datos declarados (sin vídeo)", False))
    print(json.dumps(out, ensure_ascii=False, indent=2, default=_json))
    return 0
