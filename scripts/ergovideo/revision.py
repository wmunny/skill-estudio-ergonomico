"""Revisión visual del esqueleto y del contexto de la tarea (Claude hace de revisor, como Argon en postura-poc).

Flujo:
1. `hoja_revision` genera láminas con cada instante dos veces, lado a lado: el fotograma original (cara difuminada) y
   el mismo con el esqueleto de MediaPipe (AZUL = lado izquierdo del trabajador, NARANJA = derecho, blanco = tronco).
2. Claude mira las láminas y escribe `revision.json` (esquema en docs/REVISION_VISUAL.md): contexto de la tarea, fases
   con su riesgo, muñecas por fase y lado, y veredictos por articulación y tramo, con evidencia.
3. El usuario confirma o corrige el contexto. Lo confirmado se marca en `contexto.confirmado`.
4. `politica` decide en código qué se hace con cada veredicto. Claude informa; no decide. Lo aprendido en la PoC:
   - «mal_colocada» → se quita el punto;
   - «no_visible» larga (> 1,5 s) → se quita (MediaPipe se la inventa); corta → se conserva como «aproximada»
     (el lado lejano en un giro suele estar bien estimado) y su margen de medida se amplía;
   - «aproximada» → se conserva con el margen ampliado (posición aproximada, postura correcta);
   - «lado_invertido» → solo se intercambian izquierda y derecha si la profundidad de MediaPipe lo confirma;
     si no, el tramo queda «en disputa» y no se toca (la IA también se equivoca de lado).
La IA es buen auditor y mal filtro automático: nunca tiene la última palabra sobre los datos medidos.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from .config import ESQUELETO

PUNTOS = {
    "oreja_izq": 7, "oreja_dch": 8, "hombro_izq": 11, "hombro_dch": 12, "codo_izq": 13, "codo_dch": 14,
    "muneca_izq": 15, "muneca_dch": 16, "cadera_izq": 23, "cadera_dch": 24, "rodilla_izq": 25, "rodilla_dch": 26,
    "tobillo_izq": 27, "tobillo_dch": 28,
}
MANO = {15: [17, 19, 21], 16: [18, 20, 22], 27: [29, 31], 28: [30, 32]}
VEREDICTOS = ("mal_colocada", "no_visible", "aproximada", "lado_invertido")
OCULTACION_CORTA_S = 1.5
PROFUNDIDAD_MINIMA = 0.05       # diferencia de z normalizada de MediaPipe entre lados para confirmar el lado cercano
FACTOR_APROXIMADA = 1.5         # el margen de medida de una medida con un punto aproximado se multiplica por esto

CONTEXTO_CAMPOS = {
    "postura_base": ("sentado", "de_pie", "no_se_sabe"),
    "apoyo_piernas": ("bilateral", "unilateral", "no_se_sabe"),
    "rodillas": ("menos30", "30a60", "mas60", "no_se_sabe"),
    "agarre": ("bueno", "regular", "malo", "inaceptable", "no_se_sabe"),
}
CONTEXTO_BOOLEANOS = ("fuerza_brusca", "hombro_elevado", "brazo_apoyado", "brazo_rotado", "cuello_girado",
                      "cuello_inclinado")
MUNECA_FLEXION = ("neutra", "hasta_15", "mas_15", "no_visible")


# ------------------------------------------------------------------ láminas

AZUL, NARANJA, BLANCO = (220, 120, 30), (0, 140, 255), (255, 255, 255)  # BGR


def _color(a: int, b: int):
    if a in (11, 12, 23, 24) and b in (11, 12, 23, 24):
        return BLANCO
    return AZUL if a % 2 == 1 else NARANJA


def dibujar_lados(img, lm, vis_min: float) -> None:
    h, w = img.shape[:2]
    if np.isnan(lm[0, 0]):
        return
    gro = max(2, w // 300)
    P = lambda i: (int(lm[i, 0] * w), int(lm[i, 1] * h))  # noqa: E731
    for a, b in ESQUELETO:
        if lm[a, 3] >= vis_min and lm[b, 3] >= vis_min:
            cv2.line(img, P(a), P(b), _color(a, b), gro, cv2.LINE_AA)
    for i in list(PUNTOS.values()):
        if lm[i, 3] >= vis_min:
            cv2.circle(img, P(i), gro * 2, BLANCO, -1, cv2.LINE_AA)


def instantes_revision(duracion: float, intervalo: float, extra: list[float], maximo: int) -> list[float]:
    base = list(np.arange(intervalo / 2, duracion, intervalo))
    if len(base) > maximo - len(extra):
        paso = max(1, int(math.ceil(len(base) / max(1, maximo - len(extra)))))
        base = base[::paso]
    extra = [x for x in extra if 0 <= x <= duracion and all(abs(x - y) > 0.3 for y in base)]
    return sorted({round(float(t), 2) for t in base + extra})


def hoja_revision(pose, salida: Path, instantes: list[float], vis_min: float, filas: int = 4,
                  ancho_mitad: int = 480) -> list[Path]:
    """Láminas JPG: por fila, el fotograma original y el mismo con el esqueleto, con el tiempo impreso."""
    from .visual import _difuminar_cara
    salida.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(pose.video)
    pares = []
    for t in instantes:
        k = int(np.argmin(np.abs(pose.times - t)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(pose.frames[k]))
        ok, img = cap.read()
        if not ok:
            continue
        lm = pose.lm[k]
        if not np.isnan(lm[0, 0]):
            _difuminar_cara(img, lm, img.shape[1], img.shape[0])
        esq = img.copy()
        dibujar_lados(esq, lm, vis_min)
        alto = int(img.shape[0] * ancho_mitad / img.shape[1])
        a = cv2.resize(img, (ancho_mitad, alto))
        b = cv2.resize(esq, (ancho_mitad, alto))
        for im in (a, b):
            cv2.rectangle(im, (0, 0), (150, 34), (0, 0, 0), -1)
            cv2.putText(im, f"{pose.times[k]:.1f} s", (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        pares.append(np.hstack([a, np.full((alto, 6, 3), 40, np.uint8), b]))
    cap.release()
    rutas = []
    for i in range(0, len(pares), filas):
        bloque = pares[i:i + filas]
        sep = np.full((6, bloque[0].shape[1], 3), 40, np.uint8)
        lam = np.vstack([x for p in bloque for x in (p, sep)][:-1])
        ruta = salida / f"revision_{i // filas + 1:02d}.jpg"
        cv2.imwrite(str(ruta), lam, [cv2.IMWRITE_JPEG_QUALITY, 85])
        rutas.append(ruta)
    return rutas


def plantilla(video: str, duracion: float) -> dict:
    return {
        "version": 1, "video": Path(video).name, "duracion_s": round(duracion, 2), "revisor": "Claude",
        "resumen": "",
        "contexto": {
            "tarea": "", "postura_base": "no_se_sabe", "apoyo_piernas": "no_se_sabe", "rodillas": "no_se_sabe",
            "carga_kg_estimada": None, "carga_evidencia": "", "agarre": "no_se_sabe",
            "actividad": {"estatica": None, "repetitiva": None, "cambios": None}, "ciclos_observados": None,
            "fuerza_brusca": None, "hombro_elevado": None, "brazo_apoyado": None, "brazo_rotado": None,
            "cuello_girado": None, "cuello_inclinado": None, "observaciones": "", "confirmado": [],
        },
        "fases": [], "munecas": [], "revisiones": [],
    }


def plantilla_ocra(inicio: float | None = None, fin: float | None = None, candidatos: dict | None = None) -> dict:
    """Bloque «ocra» de revision.json: ficha de acciones técnicas del ciclo representativo (ver REVISION_VISUAL.md)."""
    return {
        "ciclo": {"inicio": inicio, "fin": fin, "evidencia": ""},
        "manos_visibles": None,
        "acciones": [],
        "posturas": {"dch": {"agarre": None}, "izq": {"agarre": None}},
        "candidatos_mediapipe": candidatos or {},
        "confirmada": False,
    }


# ------------------------------------------------------------------ carga y validación

class RevisionInvalida(ValueError):
    pass


def cargar(ruta: str | Path, duracion: float | None = None) -> dict:
    """Lee y valida revision.json. Los errores dicen qué campo corregir."""
    try:
        r = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RevisionInvalida(f"{ruta}: JSON no válido ({e})") from e
    errores = []
    ctx = r.setdefault("contexto", {})
    for k, valores in CONTEXTO_CAMPOS.items():
        v = ctx.get(k, "no_se_sabe")
        if v is None:
            ctx[k] = "no_se_sabe"
        elif v not in valores:
            errores.append(f"contexto.{k} = {v!r}; valores posibles: {', '.join(valores)}")
    for k in CONTEXTO_BOOLEANOS:
        if ctx.get(k) not in (None, True, False):
            errores.append(f"contexto.{k} debe ser true, false o null")
    act = ctx.setdefault("actividad", {})
    for k in ("estatica", "repetitiva", "cambios"):
        if act.get(k) not in (None, True, False):
            errores.append(f"contexto.actividad.{k} debe ser true, false o null")
    kg = ctx.get("carga_kg_estimada")
    if kg is not None and (not isinstance(kg, (int, float)) or kg < 0):
        errores.append("contexto.carga_kg_estimada debe ser un número ≥ 0 o null")
    if not isinstance(ctx.get("confirmado", []), list):
        errores.append("contexto.confirmado debe ser una lista de nombres de campo")

    def tramo(x, donde):
        try:
            a, b = float(x["inicio"]), float(x["fin"])
        except (KeyError, TypeError, ValueError):
            errores.append(f"{donde}: inicio y fin numéricos obligatorios")
            return
        if b < a:
            errores.append(f"{donde}: fin < inicio")
        if duracion and (a < -0.5 or b > duracion + 1.0):
            errores.append(f"{donde}: tramo {a}–{b} s fuera del vídeo (0–{duracion:.1f} s)")
    for i, f in enumerate(r.setdefault("fases", [])):
        tramo(f, f"fases[{i}]")
        if f.get("riesgo") not in ("alto", "medio", "bajo"):
            errores.append(f"fases[{i}].riesgo debe ser alto, medio o bajo")
    for i, m in enumerate(r.setdefault("munecas", [])):
        tramo(m, f"munecas[{i}]")
        if m.get("lado") not in ("izq", "dch"):
            errores.append(f"munecas[{i}].lado debe ser izq o dch")
        if m.get("flexion") not in MUNECA_FLEXION:
            errores.append(f"munecas[{i}].flexion debe ser {', '.join(MUNECA_FLEXION)}")
        if m.get("confianza") not in ("alta", "media", "baja"):
            errores.append(f"munecas[{i}].confianza debe ser alta, media o baja")
    for i, v in enumerate(r.setdefault("revisiones", [])):
        tramo(v, f"revisiones[{i}]")
        if v.get("articulacion") not in PUNTOS:
            errores.append(f"revisiones[{i}].articulacion {v.get('articulacion')!r} no válida ({', '.join(PUNTOS)})")
        if v.get("veredicto") not in VEREDICTOS:
            errores.append(f"revisiones[{i}].veredicto debe ser {', '.join(VEREDICTOS)}")
        if not str(v.get("evidencia", "")).strip():
            errores.append(f"revisiones[{i}].evidencia es obligatoria")
    oc = r.get("ocra")
    if oc and oc.get("acciones"):
        from .ocra_at import FichaInvalida, validar as validar_ficha
        try:
            r["_ocra_ficha"] = validar_ficha(oc, duracion)
        except FichaInvalida as e:
            errores.append(str(e))
    if oc:
        if oc.get("manos_visibles") not in (None, True, False):
            errores.append("ocra.manos_visibles debe ser true, false o null")
        for m in ("dch", "izq"):
            ag = ((oc.get("posturas") or {}).get(m) or {}).get("agarre")
            if ag is not None and not isinstance(ag, (int, float, list, dict)):
                errores.append(f"ocra.posturas.{m}.agarre: fracción del ciclo (0–1), [mín, máx], objeto con «valor» o null")
    if errores:
        raise RevisionInvalida("revision.json no válido:\n- " + "\n- ".join(errores))
    return r


# ------------------------------------------------------------------ política de decisión (en código)

def _unir(revisiones: list[dict], dt: float) -> list[dict]:
    """Une tramos consecutivos de la misma articulación y veredicto."""
    grupos = {}
    for r in revisiones:
        grupos.setdefault((r["articulacion"], r["veredicto"]), []).append(dict(r, inicio=float(r["inicio"]), fin=float(r["fin"])))
    out = []
    for lista in grupos.values():
        lista.sort(key=lambda x: x["inicio"])
        cur = None
        for r in lista:
            if cur and r["inicio"] - cur["fin"] <= dt + 1e-6:
                cur["fin"] = max(cur["fin"], r["fin"])
            else:
                if cur:
                    out.append(cur)
                cur = dict(r)
        if cur:
            out.append(cur)
    return out


def politica(rev: dict, pose) -> dict:
    """Máscaras por fotograma y punto: quitar, aproximado; intercambios de lado confirmados; registro de decisiones."""
    n = len(pose.times)
    quitar = np.zeros((n, 33), bool)
    aprox = np.zeros((n, 33), bool)
    intercambiar = np.zeros(n, bool)
    decisiones = []
    dt = float(np.median(np.diff(pose.times))) if n > 1 else 0.1
    for r in _unir(rev.get("revisiones", []), dt):
        i = PUNTOS[r["articulacion"]]
        idx = [i] + MANO.get(i, [])
        sel = (pose.times >= r["inicio"] - 1e-6) & (pose.times <= r["fin"] + 1e-6)
        dur = r["fin"] - r["inicio"]
        v = r["veredicto"]
        if v == "mal_colocada":
            accion = "se quita"
            quitar[np.ix_(sel, idx)] = True
        elif v == "no_visible":
            if dur > OCULTACION_CORTA_S:
                accion = f"se quita (ocultación larga, {dur:.1f} s)"
                quitar[np.ix_(sel, idx)] = True
            else:
                accion = f"se conserva como aproximada (ocultación corta, {dur:.1f} s)"
                aprox[np.ix_(sel, idx)] = True
        elif v == "aproximada":
            accion = "se conserva como aproximada (margen ampliado)"
            aprox[np.ix_(sel, idx)] = True
        else:  # lado_invertido
            cercano = r.get("lado_cercano", "no_se_sabe")
            z = pose.lm[sel][:, [11, 12], 2]
            z = z[~np.isnan(z).any(axis=1)]
            if cercano in ("izq", "dch") and len(z):
                # MediaPipe: z menor = más cerca de la cámara. Etiqueta de MediaPipe del lado que tiene más cerca:
                dif = float(np.median(z[:, 0] - z[:, 1]))  # < 0: el «izquierdo» de MediaPipe está más cerca
                mp_cercano = "izq" if dif < -PROFUNDIDAD_MINIMA else "dch" if dif > PROFUNDIDAD_MINIMA else None
                if mp_cercano and mp_cercano != cercano:
                    accion = "se intercambian izquierda y derecha (la profundidad de MediaPipe lo confirma)"
                    intercambiar |= sel
                else:
                    accion = "en disputa: la profundidad de MediaPipe no lo confirma; no se toca"
            else:
                accion = "en disputa: sin lado cercano fiable; no se toca"
        decisiones.append(dict(articulacion=r["articulacion"], veredicto=v, inicio=r["inicio"], fin=r["fin"],
                               accion=accion, motivo=r.get("motivo", ""), evidencia=r.get("evidencia", "")))
    return dict(quitar=quitar, aprox=aprox, intercambiar=intercambiar, decisiones=decisiones)


PARES_LADO = [(7, 8), (9, 10), (11, 12), (13, 14), (15, 16), (17, 18), (19, 20), (21, 22), (23, 24), (25, 26),
              (27, 28), (29, 30), (31, 32), (1, 4), (2, 5), (3, 6)]


def aplicar_intercambio(pose, mascara: np.ndarray):
    """Copia de la pose con izquierda y derecha intercambiadas en los fotogramas indicados."""
    import copy
    p = copy.copy(pose)
    p.lm, p.wlm = pose.lm.copy(), pose.wlm.copy()
    for a, b in PARES_LADO:
        for arr in (p.lm, p.wlm):
            tmp = arr[mascara, a].copy()
            arr[mascara, a] = arr[mascara, b]
            arr[mascara, b] = tmp
    return p


# ------------------------------------------------------------------ contexto → datos de la tarea

def origen(campo: str, rev: dict | None, declarado_usuario: bool) -> str:
    if declarado_usuario:
        return "declarado"
    if rev is None:
        return "desconocido"
    return "IA, confirmado" if campo in rev.get("contexto", {}).get("confirmado", []) else "estimado por IA"


def completar_tarea(tarea, rev: dict | None, postura_usuario: str) -> tuple:
    """Rellena con el contexto de la revisión lo que el usuario no ha declarado. Devuelve (tarea, postura_base, origenes)."""
    import copy
    t = copy.deepcopy(tarea)
    origenes = {}
    ctx = (rev or {}).get("contexto", {})

    def poner(campo, valor_ia, actual, fijar):
        if actual is not None:
            origenes[campo] = "declarado"
        elif valor_ia is not None:
            fijar(valor_ia)
            origenes[campo] = origen(campo, rev, False)
        else:
            origenes[campo] = "desconocido"

    pb = ctx.get("postura_base", "no_se_sabe")
    if postura_usuario != "auto":
        postura, origenes["postura_base"] = postura_usuario, "declarado"
    elif pb in ("sentado", "de_pie"):
        postura, origenes["postura_base"] = pb, origen("postura_base", rev, False)
    else:
        postura, origenes["postura_base"] = "auto", "medido (heurística)"
    sn = lambda v: None if v in (None, "no_se_sabe") else v  # noqa: E731
    poner("carga_kg", ctx.get("carga_kg_estimada"), t.carga_kg, lambda v: setattr(t, "carga_kg", float(v)))
    poner("agarre", {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 3}.get(ctx.get("agarre")), t.agarre,
          lambda v: setattr(t, "agarre", v))
    poner("apoyo_piernas", sn(ctx.get("apoyo_piernas")), t.apoyo_piernas, lambda v: setattr(t, "apoyo_piernas", v))
    poner("rodillas", sn(ctx.get("rodillas")), t.rodillas, lambda v: setattr(t, "rodillas", v))
    for k in CONTEXTO_BOOLEANOS:
        poner(k, ctx.get(k), getattr(t, k), lambda v, k=k: setattr(t, k, bool(v)))
    act = dict(t.actividad)
    for k in ("estatica", "repetitiva", "cambios"):
        if act.get(k) is not None:
            origenes[f"actividad_{k}"] = "declarado"
        elif ctx.get("actividad", {}).get(k) is not None:
            act[k] = bool(ctx["actividad"][k])
            origenes[f"actividad_{k}"] = origen(f"actividad_{k}", rev, False) if f"actividad_{k}" in ctx.get("confirmado", []) \
                else origen("actividad", rev, False)
        else:
            origenes[f"actividad_{k}"] = "desconocido"
    t.actividad = act
    return t, postura, origenes


def munecas_en(rev: dict | None, t: float) -> dict:
    """Muñeca estimada por la IA en el instante t, por lado (solo confianza alta o media y visible)."""
    out = {}
    for m in (rev or {}).get("munecas", []):
        if m["confianza"] == "baja" or m["flexion"] == "no_visible":
            continue
        if float(m["inicio"]) - 1e-6 <= t <= float(m["fin"]) + 1e-6:
            out["I" if m["lado"] == "izq" else "D"] = dict(
                flexion={"neutra": "neutra", "hasta_15": "menos15", "mas_15": "mas15"}[m["flexion"]],
                desviada=m.get("desviada"), girada=m.get("girada"))
    return out


def fase_en(rev: dict | None, t: float) -> dict | None:
    for f in (rev or {}).get("fases", []):
        if float(f["inicio"]) - 1e-6 <= t <= float(f["fin"]) + 1e-6:
            return f
    return None
