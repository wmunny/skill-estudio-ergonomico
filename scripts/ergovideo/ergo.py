"""Puntuaciones REBA y RULA por fotograma y peor postura. Reglas y tablas en código, sin IA.

Cada elemento se puntúa con las reglas de `reglas.py` sobre el intervalo «medida ± margen». Lo que no se mide
(muñeca tapada, torsión no medible, un brazo oculto) y lo que no se declara (agarre, actividad, rotaciones…) es
desconocido: se recorren todos sus valores posibles y la puntuación sale como rango. Nunca se toma el valor favorable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from functools import lru_cache

import numpy as np

from . import reglas as R
from . import tablas as T
from .clasificar import piernas_posibles
from .config import Config, margen

nan = math.nan
INDICADORES = ("estatica", "repetitiva", "cambios")


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


@dataclass
class Tarea:
    """Datos de la tarea que la cámara no ve. None = desconocido (no declarado)."""
    carga_kg: float | None = None
    fuerza_brusca: bool | None = None
    agarre: int | None = None                      # REBA: 0 bueno, 1 regular, 2 malo, 3 inaceptable
    actividad: dict = field(default_factory=dict)  # {"estatica": bool|None, "repetitiva": …, "cambios": …}
    muneca: str | None = None                      # None = medir; "neutra" | "menos15" | "mas15"
    muneca_desviada: bool | None = None            # REBA: torsión o desviación; RULA: desviación radial/cubital
    muneca_giro_extremo: bool | None = None        # RULA: pronación o supinación extrema
    hombro_elevado: bool | None = None
    brazo_apoyado: bool | None = None
    brazo_rotado: bool | None = None               # REBA
    cuello_girado: bool | None = None
    cuello_inclinado: bool | None = None
    apoyo_piernas: str | None = None               # "bilateral" | "unilateral" | None
    rodillas: str | None = None                    # si no se ven: "menos30" | "30a60" | "mas60" | None

    def no_declarados(self) -> list[str]:
        nombres = {
            "carga_kg": "carga o fuerza (kg)", "fuerza_brusca": "fuerzas o cargas bruscas", "agarre": "agarre (REBA)",
            "muneca_desviada": "desviación o torsión de la muñeca", "muneca_giro_extremo": "pronación/supinación extrema (RULA)",
            "hombro_elevado": "hombro elevado", "brazo_apoyado": "brazo apoyado", "brazo_rotado": "brazo rotado (REBA)",
            "cuello_girado": "cuello rotado", "cuello_inclinado": "cuello inclinado lateralmente",
            "apoyo_piernas": "apoyo de las piernas",
        }
        faltan = [v for k, v in nombres.items() if getattr(self, k) is None]
        faltan += [f"actividad {k}" for k in INDICADORES if self.actividad.get(k) is None]
        return faltan


# ------------------------------------------------------------------ combinación de tablas (con caché)

@lru_cache(maxsize=None)
def _reba_a(tronco, cuello, piernas, carga):
    return frozenset(T.reba_tabla_a(min(t, 5), min(c, 3), min(p, 4)) + l
                     for t in tronco for c in cuello for p in piernas for l in carga)


@lru_cache(maxsize=None)
def _reba_b(brazo, antebrazo, muneca, agarre):
    return frozenset(T.reba_tabla_b(min(b, 6), a, min(w, 3)) + g for b in brazo for a in antebrazo for w in muneca for g in agarre)


@lru_cache(maxsize=None)
def _reba_final(a, b, act):
    return frozenset(T.reba_tabla_c(x, y) + z for x in a for y in b for z in act)


@lru_cache(maxsize=None)
def _rula_a(brazo, antebrazo, muneca, giro):
    return frozenset(T.rula_tabla_a(min(b, 6), min(a, 3), min(w, 4), g) for b in brazo for a in antebrazo for w in muneca for g in giro)


@lru_cache(maxsize=None)
def _rula_b(cuello, tronco, piernas):
    return frozenset(T.rula_tabla_b(min(c, 6), min(t, 6), p) for c in cuello for t in tronco for p in piernas)


@lru_cache(maxsize=None)
def _rula_final(ta, tb, pares):
    c = frozenset(x + mu + fu for x in ta for mu, fu in pares)
    d = frozenset(y + mu + fu for y in tb for mu, fu in pares)
    final = frozenset(T.rula_tabla_c(x + mu + fu, y + mu + fu) for x in ta for y in tb for mu, fu in pares)
    return c, d, final


def _r(s) -> tuple:
    return (min(s), max(s))


# ------------------------------------------------------------------ un fotograma

FACTOR_APROXIMADA = 1.5


def _intervalos(m: dict, cfg: Config, vista, modo):
    aprox = m.get("_aprox", frozenset())
    mg = (lambda k: 0.0) if cfg.muestreo.sin_margen else \
        (lambda k: margen(k, vista, modo) * (FACTOR_APROXIMADA if k in aprox else 1.0))  # noqa: E731

    def iv(k, minimo=None):
        return R.intervalo(m.get(k, nan), mg(k), minimo)
    return iv


RODILLAS_DECLARADAS = {"menos30": (10.0, 10.0), "30a60": (45.0, 45.0), "mas60": (90.0, 90.0)}


def _max_rodilla(iv, declaradas: str | None = None):
    a, b = iv("rodilla_I", 0.0), iv("rodilla_D", 0.0)
    if a is None or b is None:
        return RODILLAS_DECLARADAS.get(declaradas) if declaradas else None
    return (max(a[0], b[0]), max(a[1], b[1]))


def reba(m: dict, cfg: Config, tarea: Tarea, vista=None, modo="") -> dict:
    """REBA de un fotograma con los dos lados. Devuelve rango, elementos posibles y lo que falta."""
    u = cfg.umbrales
    iv = _intervalos(m, cfg, vista, modo)
    falta = [k for k in ("tronco_sag", "cuello", "brazo_flex_I", "brazo_flex_D", "codo_I", "codo_D", "muneca_I",
                         "muneca_D", "tronco_giro", "tronco_lat", "rodilla_I", "rodilla_D") if not _ok(m.get(k, nan))]
    tronco = frozenset(b + int(g or l) for b in R.reba_tronco_base(iv("tronco_sag"))
                       for g in R.presente(iv("tronco_giro", 0.0), u.giro_presente)
                       for l in R.presente(iv("tronco_lat", 0.0), u.giro_presente))
    cuello = frozenset(b + int(g or i) for b in R.reba_cuello_base(iv("cuello"))
                       for g in R.booleano(tarea.cuello_girado) for i in R.booleano(tarea.cuello_inclinado))
    pos = piernas_posibles(m, cfg, cfg.postura_base, vista, modo)
    sentado = frozenset(p == 1 for p in pos)
    piernas = frozenset(a + k for a in R.apoyo_reba(pos, tarea.apoyo_piernas)
                        for k in R.reba_rodillas(_max_rodilla(iv, tarea.rodillas), sentado))
    carga = R.reba_carga(tarea.carga_kg, tarea.fuerza_brusca)
    a = _reba_a(tronco, cuello, piernas, carga)
    lados = {}
    for s in "ID":
        brazo = R.reba_brazo(iv(f"brazo_flex_{s}"), iv(f"brazo_abd_{s}", 0.0), tarea.brazo_rotado,
                             tarea.hombro_elevado, tarea.brazo_apoyado, u)
        ante = R.reba_antebrazo(iv(f"codo_{s}", 0.0))
        ia = m.get("_mun", {}).get(s)
        if tarea.muneca or not ia:
            mun = R.reba_muneca(iv(f"muneca_{s}", 0.0), tarea.muneca, tarea.muneca_desviada)
        else:  # REBA: +1 si hay torsión o desviación
            d = tarea.muneca_desviada
            if d is None and ia.get("desviada") is not None and ia.get("girada") is not None:
                d = bool(ia["desviada"] or ia["girada"])
            elif d is None and (ia.get("desviada") or ia.get("girada")):
                d = True
            mun = R.reba_muneca(None, ia["flexion"], d)
        lados[s] = dict(brazo=sorted(brazo), antebrazo=sorted(ante), muneca=sorted(mun),
                        B=_r(_reba_b(brazo, ante, mun, R.reba_agarre(tarea.agarre))))
    b = frozenset(max(x, y) for x in _reba_b(*[frozenset(lados["I"][k]) for k in ("brazo", "antebrazo", "muneca")],
                                                R.reba_agarre(tarea.agarre))
                  for y in _reba_b(*[frozenset(lados["D"][k]) for k in ("brazo", "antebrazo", "muneca")],
                                   R.reba_agarre(tarea.agarre)))
    act = R.actividad(tarea.actividad)
    final = _reba_final(a, b, act)
    completo = _ok(m.get("brazo_flex_I", nan)) and _ok(m.get("brazo_flex_D", nan)) and _ok(m.get("tronco_sag", nan))
    return dict(rango=_r(final), completo=completo, A=_r(a), B=_r(b), falta=falta,
                elementos=dict(tronco=sorted(tronco), cuello=sorted(cuello), piernas=sorted(piernas),
                               carga=sorted(carga), actividad=sorted(act), lados=lados))


def rula(m: dict, cfg: Config, tarea: Tarea, lado: str, vista=None, modo="") -> dict:
    """RULA de un fotograma para un lado (I o D)."""
    u = cfg.umbrales
    iv = _intervalos(m, cfg, vista, modo)
    falta = [k for k in (f"brazo_flex_{lado}", f"codo_{lado}", f"muneca_{lado}", f"antebrazo_lat_{lado}", "cuello",
                         "tronco_sag", "tronco_giro", "tronco_lat") if not _ok(m.get(k, nan))]
    brazo = R.rula_brazo(iv(f"brazo_flex_{lado}"), iv(f"brazo_abd_{lado}", 0.0), tarea.hombro_elevado,
                         tarea.brazo_apoyado, u)
    ante = R.rula_antebrazo(iv(f"codo_{lado}", 0.0), iv(f"antebrazo_lat_{lado}"), u)
    ia = m.get("_mun", {}).get(lado)
    if tarea.muneca or not ia:
        mun = R.rula_muneca(iv(f"muneca_{lado}", 0.0), tarea.muneca, tarea.muneca_desviada)
        giro = R.rula_giro(tarea.muneca_giro_extremo)
    else:
        d = tarea.muneca_desviada if tarea.muneca_desviada is not None else ia.get("desviada")
        mun = R.rula_muneca(None, ia["flexion"], d)
        giro = R.rula_giro(tarea.muneca_giro_extremo if tarea.muneca_giro_extremo is not None else ia.get("girada"))
    cuello = R.rula_cuello(iv("cuello"), tarea.cuello_girado, tarea.cuello_inclinado)
    tronco = R.rula_tronco(iv("tronco_sag"), iv("tronco_giro", 0.0), iv("tronco_lat", 0.0), u)
    piernas = R.apoyo_rula(piernas_posibles(m, cfg, cfg.postura_base, vista, modo), tarea.apoyo_piernas)
    # Actividad muscular y fuerza dependen de los mismos indicadores: se recorren juntos.
    pares = set()
    for est in R.booleano(tarea.actividad.get("estatica")):
        for rep in R.booleano(tarea.actividad.get("repetitiva")):
            ind = {"estatica": est, "repetitiva": rep}
            for fu in R.rula_fuerza(tarea.carga_kg, ind, tarea.fuerza_brusca):
                pares.add((int(est or rep), fu))
    pares = frozenset(pares)
    ta = _rula_a(brazo, ante, mun, giro)
    tb = _rula_b(cuello, tronco, piernas)
    c, d, final = _rula_final(ta, tb, pares)
    completo = _ok(m.get(f"brazo_flex_{lado}", nan)) and _ok(m.get("tronco_sag", nan))
    return dict(rango=_r(final), completo=completo, C=_r(c), D=_r(d), lado=lado, falta=falta,
                elementos=dict(brazo=sorted(brazo), antebrazo=sorted(ante), muneca=sorted(mun), giro=sorted(giro),
                               cuello=sorted(cuello), tronco=sorted(tronco), piernas=sorted(piernas),
                               musculo=sorted({p[0] for p in pares}), fuerza=sorted({p[1] for p in pares})))


# ------------------------------------------------------------------ serie y peor postura

CLAVES_REBA = ["tronco_sag", "cuello", "brazo_flex_I", "brazo_flex_D", "codo_I", "codo_D", "rodilla_I", "rodilla_D"]


def claves_rula(lado):
    return ["tronco_sag", "cuello", f"brazo_flex_{lado}", f"codo_{lado}"]


def serie(res: dict, cfg: Config, tarea: Tarea, rev: dict | None = None, carga_en=None,
          video: str | None = None) -> list[dict]:
    """REBA y RULA (los dos lados) en cada fotograma analizado. `rev`: revisión visual (muñecas por fase).
    `carga_en(t, video)`: kg declarados en cada instante (tramos de carga, como en OWAS) o None si no se sabe;
    sin ella se usa `tarea.carga_kg` en todo el vídeo."""
    from .revision import munecas_en
    tareas: dict = {}

    def tarea_en(t: float) -> Tarea:
        if carga_en is None:
            return tarea
        kg = carga_en(t, video)
        if kg not in tareas:
            tareas[kg] = replace(tarea, carga_kg=kg)
        return tareas[kg]
    out = []
    aproximado = res.get("aproximado", {})
    claves = list(res["series"])
    interp = res.get("interpolado", {})
    for i in range(len(res["t"])):
        m = {k: float(res["series"][k][i]) for k in claves}
        m["velocidad"] = float(res["velocidad"][i])
        m["_aprox"] = frozenset(k for k, v in aproximado.items() if v[i])
        m["_mun"] = munecas_en(rev, float(res["t"][i]))
        vista, modo = float(res["vista"][i]), str(res["modo"][i])
        fiable = lambda ks: not any(bool(interp.get(k, np.zeros(1, bool))[i]) if k in interp else False for k in ks)  # noqa: E731
        if not res["detectado"][i]:
            out.append(dict(t=float(res["t"][i]), vista=vista, modo=modo, reba=None,
                            rula={"I": None, "D": None}, fiable={"reba": False, "I": False, "D": False}))
            continue
        ti = tarea_en(float(res["t"][i]))
        out.append(dict(t=float(res["t"][i]), vista=vista, modo=modo,
                        reba=reba(m, cfg, ti, vista, modo),
                        rula={s: rula(m, cfg, ti, s, vista, modo) for s in "ID"},
                        fiable={"reba": fiable(CLAVES_REBA), "I": fiable(claves_rula("I")), "D": fiable(claves_rula("D"))}))
    return out


def _obtener(f: dict, metodo: str, lado: str | None):
    return f["reba"] if metodo == "reba" else f["rula"][lado]


def estado(lo: int, hi: int, metodo: str) -> str:
    """concluyente: un solo nivel de actuación · acotada: dos niveles contiguos · incompleta: más amplio."""
    nv = T.reba_nivel if metodo == "reba" else T.rula_nivel
    d = nv(hi)[1] - nv(lo)[1]
    return "concluyente" if d == 0 else "acotada" if d == 1 else "incompleta"


def trazabilidad(res: dict, i: int, claves: list[str], cfg: Config) -> list[dict]:
    """Medidas usadas en un fotograma: valor, margen y origen (medido, interpolado o desconocido)."""
    vista, modo = float(res["vista"][i]), str(res["modo"][i])
    out = []
    for k in claves:
        v = float(res["series"][k][i])
        interp = bool(res.get("interpolado", {}).get(k, np.zeros(len(res["t"]), bool))[i])
        out.append(dict(medida=k, valor=None if math.isnan(v) else round(v, 1),
                        margen=0.0 if cfg.muestreo.sin_margen else margen(k, vista, modo),
                        origen="desconocido" if math.isnan(v) else "interpolado" if interp else "medido"))
    return out


def peor_postura(fs: list[dict], metodo: str, lado: str | None = None, sostener_s: float = 0.5,
                 separacion_s: float = 3.0, n_criticas: int = 3, hueco_s: float = 1.0) -> dict:
    """Dos resúmenes de la peor postura:
    - sostenida: máximo de la puntuación mínima en ventanas de `sostener_s` (un fotograma suelto no la fija);
    - pico breve fiable: máximo de la puntuación mínima en fotogramas sin valores interpolados, con su duración.
    Además, las posturas críticas separadas, la distribución por nivel y los huecos que podrían ocultar el pico.
    """
    t = np.array([f["t"] for f in fs])
    det = [_obtener(f, metodo, lado) for f in fs]
    lo = np.array([d["rango"][0] if d else np.nan for d in det], float)
    hi = np.array([d["rango"][1] if d else np.nan for d in det], float)
    completo = np.array([bool(d and d["completo"]) for d in det])
    clave_f = "reba" if metodo == "reba" else lado
    fiable = np.array([f["fiable"][clave_f] for f in fs])
    n = len(t)
    if n == 0 or np.isnan(lo).all():
        return dict(evaluable=False, cobertura=0.0, completo=0.0)
    lo_c = np.where(completo, lo, np.nan)  # solo fotogramas con la parte del cuerpo evaluada visible
    if np.isnan(lo_c).all():
        lo_c = lo
    semi = sostener_s / 2
    sost = np.full(n, np.nan)
    sost_hi = np.full(n, np.nan)
    for i in range(n):
        v = (t >= t[i] - semi - 1e-9) & (t <= t[i] + semi + 1e-9)
        if np.isnan(lo_c[v]).any():
            continue
        sost[i] = lo_c[v].min()
        sost_hi[i] = hi[v].min()
    if np.isnan(sost).all():
        sost, sost_hi = lo_c.copy(), hi.copy()
    i_p = int(np.nanargmax(sost))
    pico = int(sost[i_p])
    # Pico breve fiable
    lo_f = np.where(fiable & ~np.isnan(lo_c), lo_c, np.nan)
    breve = None
    if not np.isnan(lo_f).all():
        j = int(np.nanargmax(lo_f))
        a = b = j
        while a > 0 and not np.isnan(lo_c[a - 1]) and lo_c[a - 1] >= lo_f[j]:
            a -= 1
        while b < n - 1 and not np.isnan(lo_c[b + 1]) and lo_c[b + 1] >= lo_f[j]:
            b += 1
        dt = float(np.median(np.diff(t))) if n > 1 else 0.1
        breve = dict(t=float(t[j]), indice=j, pico=int(lo_f[j]), pico_max=int(hi[j]), duracion_s=float((b - a + 1) * dt),
                     detalle=det[j])
    orden = np.argsort(-np.nan_to_num(sost, nan=-1), kind="stable")
    criticas = []
    for i in orden:
        if np.isnan(sost[i]) or len(criticas) >= n_criticas:
            break
        if all(abs(t[i] - t[k]) >= separacion_s for k in criticas):
            criticas.append(int(i))
    dt = float(np.median(np.diff(t))) if n > 1 else 0.1
    huecos = []
    i = 0
    while i < n:
        if not np.isnan(lo_c[i]):
            i += 1
            continue
        e = i
        while e < n and np.isnan(lo_c[e]):
            e += 1
        bordes = [lo_c[k] for k in (i - 1, e) if 0 <= k < n and not np.isnan(lo_c[k])]
        if (e - i) * dt > hueco_s and (not bordes or max(bordes) >= pico - 1):
            huecos.append((float(t[i]), float(t[min(e, n - 1)])))
        i = e
    nv = T.reba_nivel if metodo == "reba" else T.rula_nivel
    validos = lo_c[~np.isnan(lo_c)]
    dist = {}
    for v in validos:
        k = nv(int(v))[1]
        dist[k] = dist.get(k, 0) + 1
    pico_max = int(sost_hi[i_p]) if not np.isnan(sost_hi[i_p]) else pico
    falta = {}
    for d in det:
        for k in (d or {}).get("falta", []):
            falta[k] = falta.get(k, 0) + 1
    return dict(
        evaluable=True, lado=lado, pico=pico, pico_max=pico_max, t_pico=float(t[i_p]), indice_pico=i_p,
        nivel=nv(pico), nivel_max=nv(pico_max), estado=estado(pico, pico_max, metodo),
        vista_pico=fs[i_p]["vista"], modo_pico=fs[i_p]["modo"], detalle=det[i_p], breve=breve,
        criticas=[dict(t=float(t[k]), indice=k, pico=int(sost[k]), pico_max=int(sost_hi[k]), detalle=det[k]) for k in criticas],
        cobertura=float(100 * np.mean(~np.isnan(lo))), completo=float(100 * np.mean(completo)),
        huecos=huecos, distribucion={k: 100 * v / len(validos) for k, v in sorted(dist.items())}, falta=falta,
    )


def cobertura_fases(fs: list[dict], metodo: str, lado: str | None, fases: list[dict]) -> list[dict]:
    """Por fase de la tarea: % de fotogramas con la parte evaluada visible y la peor puntuación (mínimo del rango)."""
    out = []
    for f in fases:
        a, b = float(f["inicio"]), float(f["fin"])
        dentro = [x for x in fs if a - 1e-6 <= x["t"] <= b + 1e-6]
        dets = [_obtener(x, metodo, lado) for x in dentro]
        comp = [d for d in dets if d and d["completo"]]
        out.append(dict(inicio=a, fin=b, descripcion=f.get("descripcion", ""), riesgo=f.get("riesgo"),
                        cobertura=100 * len(comp) / len(dentro) if dentro else 0.0,
                        peor=(max(d["rango"][0] for d in comp), max(d["rango"][1] for d in comp)) if comp else None))
    return out


def validar_pico(p: dict, metodo: str, fases_cob: list[dict] | None = None) -> dict:
    """Semáforo de un método de peor postura. Mide cobertura y certeza del resultado, no su exactitud."""
    if not p.get("evaluable"):
        return dict(nivel="rojo", motivos=["No hay ningún fotograma evaluable."])
    motivos, niveles = [], []
    for f in fases_cob or []:
        if f["cobertura"] < 50 and f["riesgo"] in ("alto", "medio"):
            niveles.append("rojo" if f["riesgo"] == "alto" else "ambar")
            motivos.append(f"La fase «{f['descripcion']}» ({f['inicio']:.1f}–{f['fin']:.1f} s, riesgo {f['riesgo']}) solo es "
                           f"evaluable en el {f['cobertura']:.0f} % de sus fotogramas: su peor postura podría faltar.".replace(".", ",", 2))
    cob = p["completo"]
    niveles.append("verde" if cob >= 70 else "ambar" if cob >= 40 else "rojo")
    if niveles[-1] != "verde":
        que = "con los dos brazos visibles (REBA usa los dos lados)" if metodo == "reba" else "con el brazo de ese lado visible"
        motivos.append(f"Solo el {cob:.0f} % de los fotogramas es evaluable {que}.")
    if p["estado"] == "incompleta":
        niveles.append("rojo")
        motivos.append(f"La peor postura puntúa entre {p['pico']} y {p['pico_max']}, más de dos niveles de actuación: "
                       "evaluación incompleta. Declara los datos que faltan o mejora la grabación.")
    elif p["estado"] == "acotada":
        niveles.append("ambar")
        motivos.append(f"La peor postura puntúa entre {p['pico']} y {p['pico_max']} (dos niveles de actuación): depende "
                       "de datos no medidos o no declarados, o del margen de medida.")
    elif p["pico_max"] > p["pico"]:
        motivos.append(f"Rango {p['pico']}–{p['pico_max']} dentro del mismo nivel de actuación.")
    vista = p.get("vista_pico", nan)
    if p.get("modo_pico") == "3d" and _ok(vista) and vista < 25:
        niveles.append("ambar")
        motivos.append(f"La peor postura se ve de frente o de espaldas (giro respecto a la cámara {vista:.0f}°): los ángulos "
                       "salen de la profundidad estimada por MediaPipe. Confírmala con una cámara a 45° o de lado.")
    if p["huecos"]:
        niveles.append("ambar")
        motivos.append("Huecos largos junto a posturas exigentes: la peor postura podría estar oculta ("
                       + "; ".join(f"{a:.1f}–{b:.1f} s".replace(".", ",") for a, b in p["huecos"][:4]) + ").")
    if p.get("breve") and p["breve"]["pico"] > p["pico"]:
        tb, du = f"{p['breve']['t']:.1f}".replace(".", ","), f"{p['breve']['duracion_s']:.1f}".replace(".", ",")
        motivos.append(f"Hay un pico breve fiable de {p['breve']['pico']} a los {tb} s (dura {du} s) por encima de la "
                       "peor postura sostenida: revísalo en el vídeo.")
    nivel = "rojo" if "rojo" in niveles else "ambar" if "ambar" in niveles else "verde"
    return dict(nivel=nivel, motivos=motivos)


def resumen_rula(por_lado: dict) -> str | None:
    """Lado con la peor postura de RULA (sostenida; a igualdad, el máximo del rango)."""
    ev = {s: p for s, p in por_lado.items() if p.get("evaluable")}
    if not ev:
        return None
    return max(ev, key=lambda s: (ev[s]["pico"], ev[s]["pico_max"], ev[s]["completo"]))
