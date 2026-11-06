"""Muestreo OWAS (observaciones a intervalos fijos), combinación de cámaras y estadística del % de tiempo observable.

Cada observación usa UN fotograma real (el más cercano al instante con más regiones medidas), no medianas de
articulaciones tomadas en instantes distintos, para no fabricar una postura que no ha ocurrido.

Para cada código se dan:
- el % nominal sobre las observaciones en que el código nominal se conoce, con un intervalo APROXIMADO (Wilson con
  una muestra efectiva estimada; su cobertura del 95 % no está verificada);
- el rango [mínimo, máximo] sobre todas las observaciones, contando el margen de medida y lo desconocido.
"""

from __future__ import annotations

import math

import numpy as np

from .clasificar import clasificar
from .config import Config
from .tablas import BRAZOS, ESPALDA, PIERNAS, categoria_frecuencia

MEDIDAS_REGION = {
    "espalda": ["tronco_flex", "tronco_lat", "tronco_giro"],
    "brazos": ["brazo_alt_I", "brazo_alt_D"],
    "piernas": ["rodilla_I", "rodilla_D", "muslo_I", "muslo_D", "pierna_I", "pierna_D", "tobillos", "velocidad"],
}
CLAVE_REGION = {"espalda": ["tronco_flex"], "brazos": ["brazo_alt_I", "brazo_alt_D"], "piernas": ["rodilla_I", "rodilla_D"]}
PUNTOS_REGION = {"espalda": [11, 12, 23, 24], "brazos": [11, 12, 13, 14, 15, 16], "piernas": [23, 24, 25, 26, 27, 28]}
CODIGOS = {"espalda": ESPALDA, "brazos": BRAZOS, "piernas": PIERNAS}
NOTAS_REGION = {
    "espalda": {"giro_no_medido", "lateral_no_medida", "espalda_no_visible"},
    "brazos": {"un_brazo_no_visible", "brazos_no_visibles"},
    "piernas": {"una_pierna_no_visible", "piernas_no_visibles", "sentado_declarado", "rodillas_supuestas", "apoyo_supuesto"},
}


def factor_vista(region: str, vista: float) -> float:
    """Preferencia por punto de vista para elegir cámara (Aghazadeh y Xiong): la vista frontal da el mayor error
    angular con MediaPipe; 45° es el mejor compromiso."""
    if math.isnan(vista):
        return 0.5
    if region == "espalda":
        return 0.85 if vista < 25 else (0.95 if vista > 65 else 1.0)
    if region == "piernas":
        return 0.9 if vista < 25 else 1.0
    return 1.0


def _medidas_fotograma(res: dict, i: int) -> dict:
    m = {k: float(v[i]) for k, v in res["series"].items()}
    m["velocidad"] = float(res["velocidad"][i])
    m["_aprox"] = frozenset(k for k, v in res.get("aproximado", {}).items() if v[i])
    return m


def observacion_en(res: dict, t0: float, cfg: Config) -> dict:
    """Fotograma representativo de la observación y calidad por región (para elegir cámara)."""
    t = res["t"]
    semi = cfg.muestreo.ventana_s / 2
    idx = np.flatnonzero((t >= t0 - semi - 1e-9) & (t <= t0 + semi + 1e-9))
    if not len(idx):
        idx = np.array([int(np.argmin(np.abs(t - t0)))])

    def regiones_medidas(i):
        return sum(any(not np.isnan(res["series"][k][i]) for k in ks) for ks in CLAVE_REGION.values())
    i = int(max(idx, key=lambda j: (regiones_medidas(j), -abs(t[j] - t0))))
    vista = float(res["vista"][i])
    calidad = {}
    for reg, claves in CLAVE_REGION.items():
        frac = float(np.mean([not np.isnan(res["series"][k][i]) for k in claves]))
        visib = float(np.mean(res["visibilidad"][i, PUNTOS_REGION[reg]]))
        calidad[reg] = frac * visib * factor_vista(reg, vista)
    return dict(medidas=_medidas_fotograma(res, i), calidad=calidad, vista=vista, modo=str(res["modo"][i]), indice=i,
                t_fotograma=float(t[i]))


def instantes(duracion: float, intervalo: float, inicio: float = 0.0) -> np.ndarray:
    return np.arange(inicio + intervalo / 2, inicio + duracion, intervalo) if duracion > intervalo / 2 else np.array([inicio + duracion / 2])


def _clasificar(m, cfg, kg, vista, modo):
    return clasificar(m, cfg, kg, cfg.postura_base, vista, modo)


def observar(fuentes: list[dict], cfg: Config, carga_en, modo: str = "combinar") -> list[dict]:
    """Observaciones OWAS.

    fuentes: [{nombre, res, duracion, desfase}]. carga_en(t, video) → kg declarados en ese instante o None.
    «combinar»: cada vídeo es una toma distinta. «mejor-camara»: cámaras sincronizadas; en cada instante y región se
    usa la cámara que mejor ve esa región (mismo instante, distinto punto de vista).
    """
    obs = []
    if modo == "combinar":
        for f in fuentes:
            for t0 in instantes(f["duracion"], cfg.muestreo.intervalo_s):
                o = observacion_en(f["res"], t0, cfg)
                c = _clasificar(o["medidas"], cfg, carga_en(t0, f["nombre"]), o["vista"], o["modo"])
                obs.append(dict(t=float(t0), fuente=f["nombre"], camara={r: f["nombre"] for r in CLAVE_REGION},
                                vista=o["vista"], modo=o["modo"], indice={f["nombre"]: o["indice"]},
                                t_video={f["nombre"]: o["t_fotograma"]}, medidas=o["medidas"], calidad=o["calidad"], **c))
        return obs
    if modo != "mejor-camara":
        raise ValueError(f"Modo desconocido: {modo}")
    inicio = max(f.get("desfase", 0.0) for f in fuentes)
    fin = min(f.get("desfase", 0.0) + f["duracion"] for f in fuentes)
    if fin <= inicio:
        raise ValueError("Los vídeos no se solapan en el tiempo con esos desfases.")
    for tc in instantes(fin - inicio, cfg.muestreo.intervalo_s, inicio):
        por = {f["nombre"]: observacion_en(f["res"], tc - f.get("desfase", 0.0), cfg) for f in fuentes}
        medidas, camara = {}, {}
        for reg in CLAVE_REGION:
            mejor = max(por, key=lambda n: por[n]["calidad"][reg])
            camara[reg] = mejor
            for k in MEDIDAS_REGION[reg]:
                medidas[k] = por[mejor]["medidas"][k]
        esp = por[camara["espalda"]]
        c = _clasificar(medidas, cfg, carga_en(tc, None), esp["vista"], esp["modo"])
        obs.append(dict(t=float(tc), fuente="+".join(por), camara=camara, vista=esp["vista"], modo=esp["modo"],
                        indice={n: o["indice"] for n, o in por.items()},
                        t_video={n: o["t_fotograma"] for n, o in por.items()}, medidas=medidas,
                        calidad={r: por[camara[r]]["calidad"][r] for r in CLAVE_REGION}, **c))
    return obs


# ---------------------------------------------------------------- estadística

def tiempo_decorrelacion(v: np.ndarray, dt: float, maximo_s: float) -> float | None:
    """Primer desfase en que la autocorrelación baja de 1/e (s). Aproximación: no usa toda la autocorrelación."""
    ok = ~np.isnan(v)
    if ok.sum() < 10:
        return None
    mu = v[ok].mean()
    var = ((v[ok] - mu) ** 2).mean()
    if var < 1e-9:
        return None
    x = np.where(ok, v - mu, np.nan)
    max_lag = min(len(v) - 1, int(round(maximo_s / dt)))
    for lag in range(1, max_lag + 1):
        a, b = x[:-lag], x[lag:]
        m = ~np.isnan(a) & ~np.isnan(b)
        if m.sum() < 5:
            break
        if (a[m] * b[m]).mean() / var < 1 / math.e:
            return lag * dt
    return max_lag * dt


def wilson(p: float, n: float, z: float) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def codigos_por_fotograma(res: dict, cfg: Config, kg: float | None) -> dict:
    """Código nominal de cada región en cada fotograma (para estimar la dependencia temporal por código)."""
    out = {r: np.full(len(res["t"]), np.nan) for r in CODIGOS}
    for i in range(len(res["t"])):
        if not res["detectado"][i]:
            continue
        c = clasificar(_medidas_fotograma(res, i), cfg, kg, cfg.postura_base, float(res["vista"][i]), str(res["modo"][i]))
        for r in CODIGOS:
            if c[r] is not None:
                out[r][i] = c[r]
    return out


def resumir(obs: list[dict], fuentes: list[dict], cfg: Config, kg_ref: float | None = None) -> dict:
    """% del tiempo observable por código (nominal, intervalo aproximado y rango), categorías y avisos."""
    M = cfg.muestreo
    n = len(obs)
    out = dict(n_observaciones=n, intervalo_s=M.intervalo_s, regiones={}, avisos=[])
    multicam = bool(obs) and "+" in obs[0]["fuente"]
    duracion = (sum(f["duracion"] for f in fuentes) if not multicam else
                (max(o["t"] for o in obs) - min(o["t"] for o in obs) + M.intervalo_s if obs else 0.0))
    out["duracion_s"] = duracion
    por_fotograma = [(f, codigos_por_fotograma(f["res"], cfg, kg_ref)) for f in fuentes]

    for reg, nombres in CODIGOS.items():
        nom = [o[reg] for o in obs if o[reg] is not None]
        nn = len(nom)
        pos = [set(o[f"{reg}_posibles"]) for o in obs]
        codigos, taus = {}, []
        for c in nombres:
            # Dependencia temporal del indicador «código = c» en los fotogramas
            tau_c, dur_c = [], 0.0
            for f, cods in por_fotograma:
                serie = cods[reg]
                tt = f["res"]["t"]
                dt = float(np.median(np.diff(tt))) if len(tt) > 1 else 0.1
                ind = np.where(np.isnan(serie), np.nan, (serie == c).astype(float))
                tau = tiempo_decorrelacion(ind, dt, M.decorrelacion_maxima_s)
                if tau:
                    tau_c.append(tau)
                dur_c += float((~np.isnan(serie)).sum()) * dt
            if multicam:
                dur_c = nn * M.intervalo_s
            tau = max(tau_c) if tau_c else None
            taus += tau_c
            n_indep = dur_c / (2 * tau) if tau else nn
            n_ef = max(1.0, min(nn, n_indep)) if nn else 0.0
            k = sum(1 for x in nom if x == c)
            p = k / nn if nn else 0.0
            lo, hi = wilson(p, n_ef, M.z) if nn else (0.0, 1.0)
            minimo = 100 * sum(1 for s in pos if s == {c}) / n if n else 0.0
            maximo = 100 * sum(1 for s in pos if c in s) / n if n else 0.0
            cat = categoria_frecuencia(reg, c, 100 * p) if nn else None
            extremos = [x for x in (minimo, maximo, 100 * lo, 100 * hi)] + ([100 * p] if nn else [])
            cat_rango = sorted({categoria_frecuencia(reg, c, min(100.0, x)) for x in extremos})
            codigos[c] = dict(nombre=nombres[c], n=k, porcentaje=100 * p, ic_aprox=(100 * lo, 100 * hi),
                              margen=100 * (hi - lo) / 2, rango=(minimo, maximo), categoria=cat,
                              categoria_rango=cat_rango, categoria_incierta=len(cat_rango) > 1, tau_s=tau, n_efectiva=n_ef)
        cobertura = 100 * nn / n if n else 0.0
        nivel_cob = "verde" if cobertura >= M.cobertura[0] else "ambar" if cobertura >= M.cobertura[1] else "rojo"
        margen_max = max((d["margen"] for d in codigos.values()), default=100.0)
        nivel_muestra = "verde" if margen_max <= M.margen_objetivo else "ambar" if margen_max <= 2 * M.margen_objetivo else "rojo"
        tau_r = max(taus) if taus else M.intervalo_s
        n_necesaria = (M.z ** 2 * 0.25) / (M.margen_objetivo / 100) ** 2
        out["regiones"][reg] = dict(
            codificables=nn, cobertura=cobertura, nivel_cobertura=nivel_cob, tau_s=tau_r,
            n_efectiva=min((d["n_efectiva"] for d in codigos.values() if d["n_efectiva"]), default=0.0),
            margen_max=margen_max, nivel_muestra=nivel_muestra,
            duracion_necesaria_s=n_necesaria * 2 * tau_r / max(cobertura / 100, 0.05), codigos=codigos,
            notas={k: sum(1 for o in obs if k in o["notas"]) for k in {x for o in obs for x in o["notas"] if x in NOTAS_REGION[reg]}})

    comb = [o for o in obs if o["categoria"] is not None]
    out["combinaciones"] = dict(
        codificables=len(comb), cobertura=100 * len(comb) / n if n else 0.0,
        por_categoria={c: dict(n=sum(1 for o in comb if o["categoria"] == c),
                               porcentaje=100 * sum(1 for o in comb if o["categoria"] == c) / len(comb) if comb else 0.0,
                               rango=(100 * sum(1 for o in obs if o["categoria_posibles"] == [c]) / n if n else 0.0,
                                      100 * sum(1 for o in obs if c in o["categoria_posibles"]) / n if n else 0.0))
                       for c in (1, 2, 3, 4)},
        frecuentes=_frecuentes(comb),
        categoria_max=max((o["categoria"] for o in comb), default=None),
        categoria_max_posible=max((max(o["categoria_posibles"]) for o in obs), default=None),
        inciertas=sum(1 for o in obs if len(o["categoria_posibles"]) > 1))
    if n:
        cam = {}
        for reg in CLAVE_REGION:
            cnt = {}
            for o in obs:
                cnt[o["camara"][reg]] = cnt.get(o["camara"][reg], 0) + 1
            cam[reg] = {k: 100 * v / n for k, v in cnt.items()}
        out["camaras"] = cam

    n_ef_min = min((r["n_efectiva"] for r in out["regiones"].values()), default=0)
    out["n_efectiva_min"] = n_ef_min
    if duracion < M.duracion_minima_s:
        out["avisos"].append(
            f"La grabación dura {f'{duracion / 60:.1f}'.replace('.', ',')} min. OWAS pide normalmente 20–40 min de "
            "observación o varios ciclos completos: el % de tiempo observable puede no representar el puesto.")
    if n_ef_min < M.observaciones_minimas:
        out["avisos"].append(
            f"Equivale a unas {n_ef_min:.0f} observaciones independientes (estimación aproximada). OWAS da un error del "
            f"10 % con 100 observaciones; aquí el intervalo aproximado llega a ±"
            f"{max(r['margen_max'] for r in out['regiones'].values()):.0f} puntos.")
    for reg, r in out["regiones"].items():
        if r["nivel_cobertura"] != "verde":
            out["avisos"].append(f"{reg.capitalize()}: el código nominal solo se conoce en el {r['cobertura']:.0f} % de las "
                                 "observaciones; el resto entra en los rangos.")
    return out


def _frecuentes(comb: list[dict], k: int = 8) -> list[dict]:
    cnt = {}
    for o in comb:
        clave = f"{o['espalda']}{o['brazos']}{o['piernas']}{o['carga']}"
        cnt.setdefault(clave, [0, o["categoria"]])[0] += 1
    tot = len(comb) or 1
    return [dict(codigo=c, n=v[0], porcentaje=100 * v[0] / tot, categoria=v[1])
            for c, v in sorted(cnt.items(), key=lambda x: -x[1][0])[:k]]
