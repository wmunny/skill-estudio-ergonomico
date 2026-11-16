"""Índice OCRA (ISO 11228-3, tablas clásicas) por mano, con varias tareas repetitivas en el turno.

    ATA = Σ_j frecuencia_j × minutos_j
    RTA = Σ_j (30 × FoM_j × PoM_j × ReM_j × AdM_j × minutos_j) × RcM × DuM
    índice = ATA / RTA

Se usa sin vídeo (datos manuales o un JSON) o con lo que aportan el vídeo y la revisión visual. Cada dato puede ser:
- un número (valor puntual);
- una lista [mín, máx] (rango);
- null o ausente (desconocido: se recorre todo su recorrido posible, nunca el valor favorable);
- un objeto {"valor": <lo anterior>, "origen": "medido|revisión visual|declarado|supuesto", "nota": "..."}.

El resultado es un rango [mín, máx] del índice y, si todo es puntual, un valor nominal. Las constantes están en
`tablas_ocra.py`. Todo se calcula en código.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import tablas_ocra as T

MANOS = ("dch", "izq")
NOMBRE_MANO = {"dch": "derecha", "izq": "izquierda"}
ORIGENES = ("medido", "revisión visual", "revisión visual, confirmada", "declarado", "supuesto", "calculado",
            "desconocido")


class DatosOcraInvalidos(ValueError):
    pass


# ------------------------------------------------------------------ valores con rango y origen

@dataclass
class V:
    lo: float
    hi: float
    nom: float | None
    origen: str = "declarado"
    nota: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def puntual(self) -> bool:
        return self.nom is not None and abs(self.hi - self.lo) < 1e-12

    def dict(self) -> dict:
        return dict(min=self.lo, max=self.hi, nominal=self.nom, origen=self.origen, nota=self.nota, **self.extra)


def leer(x, recorrido: tuple[float, float] | None, origen: str = "declarado", nombre: str = "") -> V:
    """Convierte un dato de entrada en V. `recorrido`: lo que se recorre si es desconocido (None → obligatorio)."""
    nota = ""
    if isinstance(x, dict) and "valor" in x:
        origen = x.get("origen", origen)
        nota = x.get("nota", "")
        x = x["valor"]
    if x is None:
        if recorrido is None:
            raise DatosOcraInvalidos(f"{nombre}: dato obligatorio")
        return V(recorrido[0], recorrido[1], None, "desconocido", nota or "no se sabe: se recorre todo el rango")
    if isinstance(x, (list, tuple)):
        if len(x) != 2 or not all(isinstance(v, (int, float)) for v in x) or x[0] > x[1]:
            raise DatosOcraInvalidos(f"{nombre}: un rango es [mín, máx]")
        a, b = float(x[0]), float(x[1])
        return V(a, b, a if a == b else None, origen, nota)
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise DatosOcraInvalidos(f"{nombre}: número, [mín, máx], null u objeto con «valor»")
    return V(float(x), float(x), float(x), origen, nota)


def _prod(*vs: V) -> tuple[float, float, float | None]:
    lo = math.prod(v.lo for v in vs)
    hi = math.prod(v.hi for v in vs)
    nom = math.prod(v.nom for v in vs) if all(v.nom is not None for v in vs) else None
    return lo, hi, nom


def _dentro(v: V, a: float, b: float, nombre: str):
    if v.lo < a - 1e-9 or v.hi > b + 1e-9:
        raise DatosOcraInvalidos(f"{nombre}: fuera de [{a}, {b}]")


# ------------------------------------------------------------------ RcM desde el horario

def _min(h) -> float:
    if isinstance(h, (int, float)):
        return float(h) * 60.0
    hh, mm = str(h).replace(".", ":").split(":")
    return int(hh) * 60.0 + int(mm)


def rcm_desde_horario(turno: dict) -> dict:
    """Horas sin recuperación adecuada a partir del horario real (inicio, fin, pausas con su hora y duración).

    Criterio (Colombini et al., 2002): proporción trabajo/recuperación 5:1. Cada periodo de trabajo continuo queda
    cubierto, al final, por la recuperación que le sigue: una pausa de R min cubre hasta 5·R min (máx. 60); la comida y
    el final del turno cubren la hora anterior; una pausa de menos de 8 min no cuenta. Lo no cubierto suma horas sin
    recuperación. Las tareas no repetitivas solo cuentan como recuperación si se marcan así.
    """
    ini, fin = _min(turno["inicio"]), _min(turno["fin"])
    if fin <= ini:
        fin += 24 * 60
    recs = []
    for p in turno.get("pausas", []):
        a = _min(p["hora"])
        if a < ini:
            a += 24 * 60
        recs.append(dict(inicio=a, min=float(p["min"]), tipo=p.get("tipo", "pausa"), etiqueta=p.get("hora")))
    for p in turno.get("no_repetitivas", []):
        if p.get("cuenta_como_recuperacion"):
            a = _min(p["hora"])
            if a < ini:
                a += 24 * 60
            recs.append(dict(inicio=a, min=float(p["min"]), tipo="no repetitiva", etiqueta=p.get("hora")))
    recs.sort(key=lambda r: r["inicio"])
    for r in recs:
        if not (ini <= r["inicio"] < fin):
            raise DatosOcraInvalidos(f"turno: la pausa de las {r['etiqueta']} está fuera del turno")
    tramos, t = [], ini
    for r in recs + [dict(inicio=fin, min=math.inf, tipo="fin del turno", etiqueta=turno["fin"])]:
        w = max(0.0, r["inicio"] - t)
        if r["tipo"] in ("comida", "fin del turno"):
            cubre = min(w, 60.0)
            adecuada = True
        elif r["min"] >= T.RECUPERACION_MINIMA_MIN:
            cubre = min(w, 60.0, r["min"] * T.PROPORCION_TRABAJO_RECUPERACION)
            adecuada = True
        else:
            cubre, adecuada = 0.0, False
        if w > 0:
            tramos.append(dict(desde=_hhmm(t), hasta=_hhmm(r["inicio"]), trabajo_min=w, recuperacion=r["tipo"],
                               recuperacion_min=None if math.isinf(r["min"]) else r["min"], adecuada=adecuada,
                               cubierto_min=cubre, sin_recuperacion_min=w - cubre))
        t = r["inicio"] + (0 if math.isinf(r["min"]) else r["min"])
    horas = sum(x["sin_recuperacion_min"] for x in tramos) / 60.0
    r = T.rcm(horas)
    return dict(horas=r["horas"], nominal=r["nominal"], min=r["min"], max=r["max"], tramos=tramos,
                trabajo_min=sum(x["trabajo_min"] for x in tramos))


def _hhmm(m: float) -> str:
    m = int(round(m)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


# ------------------------------------------------------------------ resolución de los datos de entrada

def _fom(d: dict, nombre: str) -> V:
    if "fom" in d:
        v = leer(d["fom"], (T.FOM_MIN, T.FOM_MAX), nombre=f"{nombre}.fom")
        _dentro(v, 0, 1, f"{nombre}.fom")
        return v
    b = d.get("borg")
    origen = "declarado"
    if isinstance(b, dict) and "valor" in b:
        origen, b = b.get("origen", origen), b["valor"]
    if b is None:
        return V(T.FOM_MIN, T.FOM_MAX, None, "desconocido", "Borg no se sabe: se recorre de 0,01 a 1")
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        fases = [dict(borg=float(b), s=1.0)]
    elif isinstance(b, list):
        fases = b
    else:
        raise DatosOcraInvalidos(f"{nombre}.borg: número, lista de fases o null")
    tot = sum(float(f.get("s", 0)) for f in fases)
    if tot <= 0:
        raise DatosOcraInvalidos(f"{nombre}.borg: cada fase necesita su duración «s» > 0")
    conocido = sum(float(f["s"]) * float(f["borg"]) for f in fases if f.get("borg") is not None)
    desconocido = sum(float(f["s"]) for f in fases if f.get("borg") is None)
    for f in fases:
        if f.get("borg") is not None and not (0 <= float(f["borg"]) <= 10):
            raise DatosOcraInvalidos(f"{nombre}.borg: escala CR-10 (0–10)")
    b_lo, b_hi = conocido / tot, (conocido + 10 * desconocido) / tot
    f_lo, f_hi = T.fom(b_hi), T.fom(b_lo)
    if desconocido:
        return V(f_lo["nominal"], f_hi["nominal"], None, "desconocido",
                 f"Borg medio entre {b_lo:.2f} y {b_hi:.2f} (fases sin Borg)", dict(borg_medio=[b_lo, b_hi]))
    f = T.fom(b_lo)
    nota = f"Borg medio ponderado {b_lo:.2f} → escalón {f['borg_escalon']:g}"
    return V(f["nominal"], f["nominal"], f["nominal"], origen, nota,
             dict(borg_medio=round(b_lo, 3), fom_alternativa=f["alternativa"]))


def _pom(d: dict, nombre: str) -> tuple[V, dict]:
    if "pom" in d:
        v = leer(d["pom"], (T.POM_MIN, 1.0), nombre=f"{nombre}.pom")
        _dentro(v, 0, 1, f"{nombre}.pom")
        return v, {}
    pos = d.get("posturas")
    if pos is None:
        return V(T.POM_MIN, 1.0, None, "desconocido", "posturas no evaluadas: se recorre todo el rango"), {}
    if "estereotipia" in pos:
        raise DatosOcraInvalidos(f"{nombre}.posturas: la estereotipia va en ReM (misma_accion o ciclo), no en PoM")
    detalle, los, his, noms, origenes = {}, [], [], [], set()
    for art in T.ARTICULACIONES:
        fr = leer(pos.get(art), (0.0, 1.0), nombre=f"{nombre}.posturas.{art}")
        _dentro(fr, 0, 1, f"{nombre}.posturas.{art}")
        p_lo, p_hi = T.pom_articulacion(fr.hi), T.pom_articulacion(fr.lo)
        p_nom = T.pom_articulacion(fr.nom) if fr.nom is not None else (p_lo if p_lo == p_hi else None)
        detalle[art] = dict(fraccion=fr.dict(), pom=[p_lo, p_hi], nominal=p_nom)
        los.append(p_lo)
        his.append(p_hi)
        noms.append(p_nom)
        origenes.add(fr.origen)
    nom = min(noms) if all(n is not None for n in noms) else None
    if nom is None and min(los) == min(his):
        nom = min(los)
    origen = next(iter(origenes)) if len(origenes) == 1 else "varios: " + ", ".join(sorted(origenes))
    peor = min(detalle, key=lambda a: detalle[a]["pom"][0])
    return V(min(los), min(his), nom, origen, f"el factor más bajo de hombro, codo, muñeca y agarre ({peor})"), detalle


def _rem(d: dict, ciclo: V, nombre: str) -> V:
    if "rem" in d:
        v = leer(d["rem"], (T.REM_VALOR, 1.0), nombre=f"{nombre}.rem")
        _dentro(v, 0, 1, f"{nombre}.rem")
        return v
    ma = leer(d.get("misma_accion"), (0.0, 1.0), nombre=f"{nombre}.misma_accion")
    vals = {T.rem(c, m) for c in (ciclo.lo, ciclo.hi) for m in (ma.lo, ma.hi)}
    lo, hi = min(vals), max(vals)
    nota = ("ciclo desconocido" if math.isinf(ciclo.hi) else
            f"ciclo {ciclo.lo:g}–{ciclo.hi:g} s" if ciclo.lo != ciclo.hi else f"ciclo {ciclo.lo:g} s") + \
           (f"; misma acción {ma.lo:.0%}–{ma.hi:.0%} del ciclo" if ma.lo != ma.hi else f"; misma acción {ma.lo:.0%}")
    return V(lo, hi, lo if lo == hi else None, "calculado" if lo == hi else "desconocido", nota)


def _adm(d: dict, nombre: str) -> tuple[V, list]:
    if "adm" in d:
        v = leer(d["adm"], (T.ADM_MIN, 1.0), nombre=f"{nombre}.adm")
        _dentro(v, 0, 1, f"{nombre}.adm")
        return v, []
    ad = d.get("adicionales")
    if ad is None:
        return V(T.ADM_MIN, 1.0, None, "desconocido", "factores adicionales no declarados: se recorre todo el rango"), []
    los, his, det = [1.0], [1.0], []
    for i, x in enumerate(ad):
        if x.get("factor") not in T.FACTORES_ADICIONALES:
            raise DatosOcraInvalidos(f"{nombre}.adicionales[{i}].factor: {', '.join(T.FACTORES_ADICIONALES)}")
        fr = leer(x.get("fraccion"), (0.0, 1.0), nombre=f"{nombre}.adicionales[{i}].fraccion")
        _dentro(fr, 0, 1, f"{nombre}.adicionales[{i}].fraccion")
        los.append(T.adm_factor(fr.hi))
        his.append(T.adm_factor(fr.lo))
        det.append(dict(factor=x["factor"], fraccion=fr.dict(), adm=[T.adm_factor(fr.hi), T.adm_factor(fr.lo)]))
    lo, hi = min(los), min(his)
    return V(lo, hi, lo if lo == hi else None, "declarado", ", ".join(x["factor"] for x in det) or "ninguno"), det


def resolver(datos: dict) -> dict:
    """Valida los datos y los convierte en valores con rango y origen (sin calcular aún el índice)."""
    tareas_in = datos.get("tareas")
    if not tareas_in:
        raise DatosOcraInvalidos("tareas: al menos una tarea repetitiva")
    tareas = []
    for j, t in enumerate(tareas_in):
        nt = f"tareas[{j}]"
        minutos = leer(t.get("minutos"), None, nombre=f"{nt}.minutos")
        _dentro(minutos, 0, 24 * 60, f"{nt}.minutos")
        if "ciclo_s" in t:
            ciclo = leer(t["ciclo_s"], None, nombre=f"{nt}.ciclo_s")
        elif t.get("piezas"):
            piezas = float(t["piezas"])
            ciclo = V(minutos.lo * 60 / piezas, minutos.hi * 60 / piezas,
                      minutos.nom * 60 / piezas if minutos.nom is not None else None, "calculado",
                      f"{minutos.nom or minutos.lo:g} min / {piezas:g} piezas")
        else:
            ciclo = None
        if ciclo is not None and ciclo.lo <= 0:
            raise DatosOcraInvalidos(f"{nt}.ciclo_s debe ser > 0")
        manos = {}
        for m in MANOS:
            d = (t.get("manos") or {}).get(m)
            if d is None:
                continue
            nm = f"{nt}.manos.{m}"
            if "frecuencia" in d:
                frec = leer(d["frecuencia"], None, nombre=f"{nm}.frecuencia")
                at = None
            else:
                at = leer(d.get("at_ciclo"), None, nombre=f"{nm}.at_ciclo")
                if ciclo is None:
                    raise DatosOcraInvalidos(f"{nt}: falta ciclo_s (o piezas) para pasar de AT por ciclo a frecuencia")
                lo, hi = at.lo * 60 / ciclo.hi, at.hi * 60 / ciclo.lo
                nom = at.nom * 60 / ciclo.nom if at.nom is not None and ciclo.nom is not None else None
                frec = V(lo, hi, nom, "calculado", "AT por ciclo × 60 / tiempo de ciclo")
            fom = _fom(d, nm)
            pom, pom_det = _pom(d, nm)
            rem = _rem(d, ciclo or V(0.0, math.inf, None, "desconocido"), nm)
            adm, adm_det = _adm(d, nm)
            manos[m] = dict(at=at, frecuencia=frec, fom=fom, pom=pom, rem=rem, adm=adm, pom_detalle=pom_det,
                            adm_detalle=adm_det, ficha=d.get("ficha"))
        if not manos:
            raise DatosOcraInvalidos(f"{nt}.manos: datos de la mano derecha («dch»), la izquierda («izq») o ambas")
        tareas.append(dict(nombre=t.get("nombre", f"Tarea {j + 1}"), minutos=minutos, ciclo=ciclo, manos=manos))
    turno = datos.get("turno") or {}
    horario = None
    if "rcm" in datos:
        rcm = leer(datos["rcm"], (0.0, 1.0), nombre="rcm")
        _dentro(rcm, 0, 1, "rcm")
    elif turno.get("inicio") and turno.get("fin"):
        horario = rcm_desde_horario(turno)
        rcm = V(horario["min"], horario["max"], horario["nominal"], "calculado",
                f"{horario['horas']:g} h sin recuperación adecuada según el horario".replace(".", ","),
                dict(horas=horario["horas"]))
    else:
        rcm = V(0.0, 1.0, None, "desconocido", "sin horario de pausas: se recorre de 0 a 1")
    tot = V(sum(t["minutos"].lo for t in tareas), sum(t["minutos"].hi for t in tareas),
            sum(t["minutos"].nom for t in tareas) if all(t["minutos"].nom is not None for t in tareas) else None,
            "calculado")
    if "dum" in datos:
        dum = leer(datos["dum"], (T.DUM_MAS, 2.0), nombre="dum")
    else:
        a, b = T.dum(tot.lo), T.dum(tot.hi)
        dum = V(min(a, b), max(a, b), T.dum(tot.nom) if tot.nom is not None else None, "calculado",
                f"{tot.nom if tot.nom is not None else f'{tot.lo:g}–{tot.hi:g}'} min netos repetitivos")
    esquema = datos.get("clasificacion", T.CLASIFICACION_DEFECTO)
    if esquema not in T.CLASIFICACIONES:
        raise DatosOcraInvalidos(f"clasificacion: {', '.join(T.CLASIFICACIONES)}")
    return dict(tareas=tareas, rcm=rcm, dum=dum, minutos=tot, horario=horario, esquema=esquema,
                lateralidad=datos.get("lateralidad"), turno=turno)


# ------------------------------------------------------------------ cálculo

def _indice(r: dict, mano: str) -> dict | None:
    ts = [t for t in r["tareas"] if mano in t["manos"]]
    if not ts:
        return None
    ata_lo = sum(t["manos"][mano]["frecuencia"].lo * t["minutos"].lo for t in ts)
    ata_hi = sum(t["manos"][mano]["frecuencia"].hi * t["minutos"].hi for t in ts)
    noms = all(t["manos"][mano]["frecuencia"].nom is not None and t["minutos"].nom is not None for t in ts)
    ata_nom = sum(t["manos"][mano]["frecuencia"].nom * t["minutos"].nom for t in ts) if noms else None
    parciales = []
    rta_lo = rta_hi = 0.0
    rta_nom = 0.0 if noms else None
    for t in ts:
        m = t["manos"][mano]
        lo, hi, nom = _prod(m["fom"], m["pom"], m["rem"], m["adm"], t["minutos"])
        rta_lo += T.FRECUENCIA_REFERENCIA * lo
        rta_hi += T.FRECUENCIA_REFERENCIA * hi
        if rta_nom is not None:
            rta_nom = None if nom is None else rta_nom + T.FRECUENCIA_REFERENCIA * nom
        parciales.append(dict(tarea=t["nombre"], minutos=t["minutos"].dict(),
                              ciclo_s=t["ciclo"].dict() if t["ciclo"] else None,
                              at_ciclo=m["at"].dict() if m["at"] else None, frecuencia=m["frecuencia"].dict(),
                              fom=m["fom"].dict(), pom=m["pom"].dict(), pom_detalle=m["pom_detalle"],
                              rem=m["rem"].dict(), adm=m["adm"].dict(), adm_detalle=m["adm_detalle"],
                              ficha=m.get("ficha")))
    rc, du = r["rcm"], r["dum"]
    rta_lo *= rc.lo * du.lo
    rta_hi *= rc.hi * du.hi
    if rta_nom is not None:
        rta_nom = None if rc.nom is None or du.nom is None else rta_nom * rc.nom * du.nom
    div = lambda a, b: math.inf if b <= 0 else a / b  # noqa: E731
    i_lo, i_hi = div(ata_lo, rta_hi), div(ata_hi, rta_lo)
    i_nom = div(ata_nom, rta_nom) if ata_nom is not None and rta_nom is not None else None
    if i_nom is None and abs(i_hi - i_lo) < 1e-12:
        i_nom = i_lo
    esq = r["esquema"]
    peor = T.clasificar(i_hi, esq)
    # Frecuencia de referencia efectiva (acciones/min que el puesto «admite») y frecuencia real media por minuto.
    min_nom = r["minutos"].nom or r["minutos"].hi
    ref_ef = None if rta_nom is None else rta_nom / min_nom
    frec_media = None if ata_nom is None else ata_nom / min_nom
    m_lo = sum(t["minutos"].lo for t in ts) or 1e-9
    m_hi = sum(t["minutos"].hi for t in ts) or 1e-9
    frec_rango = [ata_lo / m_hi, ata_hi / m_lo]
    return dict(mano=mano, nombre=NOMBRE_MANO[mano], indice=i_nom, indice_min=i_lo, indice_max=i_hi,
                ata=dict(min=ata_lo, max=ata_hi, nominal=ata_nom), rta=dict(min=rta_lo, max=rta_hi, nominal=rta_nom),
                clase=T.clasificar(i_nom, esq) if i_nom is not None else peor,
                clase_min=T.clasificar(i_lo, esq), clase_max=peor, tareas=parciales,
                referencia_efectiva=ref_ef, frecuencia_media=frec_media, frecuencia_rango=frec_rango)


def calcular(datos: dict) -> dict:
    """Índice OCRA por mano. Devuelve un dict serializable a JSON."""
    r = resolver(datos)
    manos = {m: x for m in MANOS if (x := _indice(r, m))}
    peor = max(manos.values(), key=lambda x: (x["indice_max"], x["indice"] or 0))
    out = dict(
        metodo="OCRA", edicion=T.EDICION_TABLAS, aviso_normativo=T.AVISO_NORMATIVO,
        clasificacion=r["esquema"], clasificacion_nombre=T.CLASIFICACIONES[r["esquema"]]["nombre"],
        bandas=[dict(hasta=None if math.isinf(b[0]) else b[0], color=b[1], nivel=b[2], accion=b[3])
                for b in T.CLASIFICACIONES[r["esquema"]]["bandas"]],
        manos=manos, peor_mano=peor["mano"], rcm=r["rcm"].dict(), dum=r["dum"].dict(), minutos=r["minutos"].dict(),
        horario=r["horario"], lateralidad=r["lateralidad"], frecuencia_referencia=T.FRECUENCIA_REFERENCIA,
        urgencia=T.URGENCIA_COLOR[peor["clase_max"]["color"]],
    )
    out["trazabilidad"] = trazabilidad(r)
    out["sensibilidad"] = sensibilidad(datos, r)
    return out


def trazabilidad(r: dict) -> list[dict]:
    filas = []

    def fila(dato, v: V | None, mano=""):
        if v is None:
            return
        val = (f"{v.nom:.4g}" if v.nom is not None else f"{v.lo:.4g}–{v.hi:.4g}").replace(".", ",")
        filas.append(dict(dato=dato, mano=mano, valor=val, origen=v.origen, nota=v.nota))
    for t in r["tareas"]:
        fila(f"{t['nombre']}: minutos por turno", t["minutos"])
        fila(f"{t['nombre']}: tiempo de ciclo (s)", t["ciclo"])
        for m, d in t["manos"].items():
            mn = NOMBRE_MANO[m]
            fila(f"{t['nombre']}: AT por ciclo", d["at"], mn)
            fila(f"{t['nombre']}: frecuencia (AT/min)", d["frecuencia"], mn)
            fila(f"{t['nombre']}: FoM (fuerza)", d["fom"], mn)
            fila(f"{t['nombre']}: PoM (postura)", d["pom"], mn)
            fila(f"{t['nombre']}: ReM (repetitividad)", d["rem"], mn)
            fila(f"{t['nombre']}: AdM (factores adicionales)", d["adm"], mn)
    fila("RcM (recuperación)", r["rcm"])
    fila("DuM (duración)", r["dum"])
    return filas


# ------------------------------------------------------------------ sensibilidad y escenarios

def _nominal_o_peor(x: dict) -> float:
    return x["indice"] if x["indice"] is not None else x["indice_max"]


def sensibilidad(datos: dict, r: dict | None = None) -> list[dict]:
    """Cómo cambia el índice de cada mano si se cuenta una AT más o menos, con el otro escalón de Borg o con una hora
    más o menos sin recuperación. Se calcula sobre los valores resueltos (nominal o, si es rango, el peor caso)."""
    r = r or resolver(datos)
    base = {m: _indice(r, m) for m in MANOS}
    out = []

    def caso(nombre, cambio):
        r2 = copy.deepcopy(r)
        aplicado = cambio(r2)
        if not aplicado:
            return
        fila = dict(caso=nombre)
        for m in MANOS:
            if base[m] is None:
                continue
            x = _indice(r2, m)
            fila[m] = dict(indice=_nominal_o_peor(x), base=_nominal_o_peor(base[m]),
                           clase=T.clasificar(_nominal_o_peor(x), r["esquema"])["color"])
        out.append(fila)

    def at(delta):
        def f(r2):
            hecho = False
            for t in r2["tareas"]:
                for m, d in t["manos"].items():
                    if d["at"] is None or t["ciclo"] is None:
                        continue
                    a = d["at"]
                    nv = V(max(0, a.lo + delta), max(0, a.hi + delta), None if a.nom is None else max(0, a.nom + delta))
                    d["at"] = nv
                    d["frecuencia"] = V(nv.lo * 60 / t["ciclo"].hi, nv.hi * 60 / t["ciclo"].lo,
                                        None if nv.nom is None or t["ciclo"].nom is None else nv.nom * 60 / t["ciclo"].nom)
                    hecho = True
            return hecho
        return f
    caso("1 AT menos por ciclo", at(-1))
    caso("1 AT más por ciclo", at(+1))

    def borg_alt(r2):
        hecho = False
        for t in r2["tareas"]:
            for d in t["manos"].values():
                alt = d["fom"].extra.get("fom_alternativa")
                if alt is not None and alt != d["fom"].nom:
                    d["fom"] = V(alt, alt, alt)
                    hecho = True
        return hecho
    caso("Borg en el escalón inferior (FoM menos conservador)", borg_alt)

    def borg_mas(r2):
        hecho = False
        for t in r2["tareas"]:
            for d in t["manos"].values():
                b = d["fom"].extra.get("borg_medio")
                if isinstance(b, (int, float)):
                    f = T.fom(min(10.0, b + 0.5))["nominal"]
                elif d["fom"].nom is not None:
                    # FoM declarado directamente: el siguiente escalón de la tabla (más esfuerzo).
                    menores = [v for _, v in T.FOM_BORG if v < d["fom"].nom - 1e-9]
                    if not menores:
                        continue
                    f = max(menores)
                else:
                    continue
                d["fom"] = V(f, f, f)
                hecho = True
        return hecho
    caso("Borg +0,5 (un escalón más de esfuerzo)", borg_mas)

    h = r["rcm"].extra.get("horas")
    if h is not None:
        for dh, nombre in ((-1, "1 hora menos sin recuperación"), (+1, "1 hora más sin recuperación")):
            def f(r2, dh=dh):
                v = T.rcm(min(8.0, max(0.0, h + dh)))["nominal"]
                r2["rcm"] = V(v, v, v)
                return True
            caso(nombre, f)
    else:
        rc = r["rcm"]
        if rc.nom is not None:
            pasos = sorted(T.RCM_HORAS.values())
            k = min(range(len(pasos)), key=lambda i: abs(pasos[i] - rc.nom))
            for j, nombre in ((k + 1, "RcM un escalón mejor (1 hora menos sin recuperación)"),
                              (k - 1, "RcM un escalón peor (1 hora más sin recuperación)")):
                if 0 <= j < len(pasos):
                    caso(nombre, lambda r2, v=pasos[j]: r2.__setitem__("rcm", V(v, v, v)) or True)
    return out


def _fusionar(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = _fusionar(a.get(k), v) if k in a else v
        return out
    if isinstance(a, list) and isinstance(b, list) and b and all(isinstance(x, dict) for x in b) \
            and len(a) == len(b) and all(isinstance(x, dict) for x in a):
        return [_fusionar(x, y) for x, y in zip(a, b)]
    return b


def escenario(datos: dict, cambios: dict) -> dict:
    """Índice recalculado con los cambios propuestos (fusión de `cambios` sobre `datos`). Es una PROYECCIÓN."""
    nuevo = _fusionar(copy.deepcopy(datos), cambios)
    res = calcular(nuevo)
    return dict(proyeccion=True, datos=nuevo, resultado=res)


def cargar(ruta: str | Path) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise DatosOcraInvalidos(f"{ruta}: JSON no válido ({e})") from e


def fmt(x: float | None, d: int = 2) -> str:
    if x is None:
        return "—"
    if math.isinf(x):
        return "∞"
    return f"{x:.{d}f}".replace(".", ",")


def texto_indice(m: dict) -> str:
    if m["indice"] is not None and abs(m["indice_max"] - m["indice_min"]) < 0.005:
        return fmt(m["indice"])
    base = f"{fmt(m['indice_min'])}–{fmt(m['indice_max'])}"
    return base + (f" (nominal {fmt(m['indice'])})" if m["indice"] is not None else "")
