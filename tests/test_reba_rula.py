"""Pruebas de REBA y RULA con posturas sintéticas calculadas a mano y las pruebas de aceptación de la auditoría."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import reglas as R  # noqa: E402
from ergovideo import tablas as T  # noqa: E402
from ergovideo.config import Config  # noqa: E402
from ergovideo.ergo import Tarea, estado, peor_postura, reba, rula, serie, validar_pico  # noqa: E402
from ergovideo.medidas import calcular, medidas_fotograma  # noqa: E402
from ergovideo.sintetico import fotograma, pose_sintetica  # noqa: E402

VISTAS = [0, 45, 90]


def cfg_(sin_margen=True):
    c = Config()
    c.muestreo.sin_margen = sin_margen
    return c


CFG = cfg_()


def tarea(**kw):
    """Todo declarado (neutro, sin carga ni actividad) salvo lo que se indique."""
    base = dict(carga_kg=0.0, fuerza_brusca=False, agarre=0, actividad=dict(estatica=False, repetitiva=False, cambios=False),
                muneca="neutra", muneca_desviada=False, muneca_giro_extremo=False, hombro_elevado=False, brazo_apoyado=False,
                brazo_rotado=False, cuello_girado=False, cuello_inclinado=False, apoyo_piernas=None)
    base.update(kw)
    return Tarea(**base)


def medir(vista=0, ocultar=(), **postura):
    p2, w, usable = fotograma(vista=vista, **postura)
    usable[list(ocultar)] = False
    m = medidas_fotograma(p2, w, usable, CFG)
    m["velocidad"] = 0.0
    return m


def puntuar(vista=0, t=None, lado="I", cfg=CFG, ocultar=(), **postura):
    m = medir(vista, ocultar, **postura)
    t = t or tarea()
    return reba(m, cfg, t, vista, m["modo"]), rula(m, cfg, t, lado, vista, m["modo"])


# ------------------------------------------------------------------ posturas sintéticas (sin margen)

@pytest.mark.parametrize("vista", VISTAS)
def test_neutro_brazos_colgando(vista):
    # Prueba de aceptación de la auditoría: codo 0° → antebrazo 2; RULA: A = 2, C = 2, D = 1, final 2.
    r, u = puntuar(vista)
    assert r["rango"] == (1, 1)
    assert u["C"] == (2, 2) and u["D"] == (1, 1) and u["rango"] == (2, 2)


@pytest.mark.parametrize("vista", VISTAS)
def test_postura_exigente(vista):
    # Tronco 50°, cuello 30°, rodillas 50°, codos 90°, 12 kg, agarre regular, tarea repetitiva.
    # REBA: tronco 3, cuello 2, piernas 1+1 → tabla A(3,2,2) = 5 + 2 = 7; brazo 50° respecto al tronco → 3,
    #       antebrazo 1, muñeca 1 → tabla B(3,1,1) = 3 + 1 = 4; C(7,4) = 8 + 1 = 9.
    # RULA: brazo 3, antebrazo 1, muñeca 1, giro 1 → A 3 + 1 + 3 = 7; cuello 3, tronco 3, piernas 1 → B 4 + 1 + 3 = 8;
    #       tabla C(7, 8→7) = 7.
    t = tarea(carga_kg=12.0, agarre=1, actividad=dict(estatica=False, repetitiva=True, cambios=False))
    r, u = puntuar(vista, t, flexion=50, cuello=30, muslo_I=40, rodilla_I=50, muslo_D=40, rodilla_D=50, codo_I=90, codo_D=90)
    assert r["A"] == (7, 7) and r["B"] == (4, 4) and r["rango"] == (9, 9)
    assert u["C"] == (7, 7) and u["D"] == (8, 8) and u["rango"] == (7, 7)


@pytest.mark.parametrize("vista", VISTAS)
def test_brazo_abducido_elevado(vista):
    # Brazo izq. 100° hacia fuera: REBA brazo 4 + 1 = 5; B = tabla B(5, 2, 1) = 7; C(1, 7) = 4.
    # RULA: brazo 4 + 1 = 5; antebrazo 2 + 1 (a un lado) = 3; A(5, 3, 1, 1) = 6; C(6, 1) = 4.
    r, u = puntuar(vista, abd_I=100)
    assert r["elementos"]["lados"]["I"]["B"] == (7, 7) and r["rango"] == (4, 4)
    assert u["elementos"]["brazo"] == [5] and u["elementos"]["antebrazo"] == [3] and u["rango"] == (4, 4)


@pytest.mark.parametrize("vista", VISTAS)
def test_extensiones(vista):
    r, u = puntuar(vista, flexion=-30, cuello=-20)
    assert r["elementos"]["tronco"] == [3] and r["elementos"]["cuello"] == [2]
    assert u["elementos"]["cuello"] == [4]


@pytest.mark.parametrize("vista", VISTAS)
def test_antebrazo_cruza_linea_media(vista):
    _, u = puntuar(vista, codo_I=80, cruzar_I=90)
    assert u["elementos"]["antebrazo"] == [2]


@pytest.mark.parametrize("vista", VISTAS)
def test_muneca_medida(vista):
    t = tarea(muneca=None)
    assert puntuar(vista, t, codo_I=90, muneca_I=30)[1]["elementos"]["muneca"] == [3]
    assert puntuar(vista, t, codo_I=90, muneca_I=10)[1]["elementos"]["muneca"] == [2]


# ------------------------------------------------------------------ pruebas de aceptación de la auditoría

def test_cuello_rotado_e_inclinado():
    base_reba = puntuar(0)[0]["elementos"]["cuello"][0]
    base_rula = puntuar(0)[1]["elementos"]["cuello"][0]
    r, u = puntuar(0, tarea(cuello_girado=True, cuello_inclinado=True))
    assert r["elementos"]["cuello"] == [base_reba + 1]    # REBA: un único +1
    assert u["elementos"]["cuello"] == [base_rula + 2]    # RULA: +1 y +1 independientes


def test_extension_cervical_sin_tolerancia():
    m = {"cuello": -3.0}
    assert R.reba_cuello_base((m["cuello"],) * 2) == {2}
    assert R.rula_cuello((m["cuello"],) * 2, False, False) == {4}


def test_rula_cuello_frontera_mayor():
    assert R.rula_cuello((10.0, 10.0), False, False) == {2}
    assert R.rula_cuello((20.0, 20.0), False, False) == {3}


def test_muneca_y_desviacion_desconocidas():
    t = tarea(muneca=None, muneca_desviada=None, muneca_giro_extremo=None)
    r, u = puntuar(45, t, ocultar=(17, 19), brazo_I=60, codo_I=90)
    assert r["elementos"]["lados"]["I"]["muneca"] == [1, 2, 3]
    assert u["elementos"]["muneca"] == [1, 2, 3, 4]
    assert u["elementos"]["giro"] == [1, 2]


def test_rula_c_mayor_de_8_conserva_la_original():
    t = tarea(carga_kg=15.0, actividad=dict(estatica=True, repetitiva=True, cambios=False), hombro_elevado=True,
              muneca="mas15", muneca_desviada=True, muneca_giro_extremo=True)
    _, u = puntuar(45, t, flexion=70, cuello=40, abd_I=120, codo_I=120)
    assert u["C"][0] > 8 and u["rango"] == (T.rula_tabla_c(8, u["D"][0]), T.rula_tabla_c(8, u["D"][1]))


def test_rodillas_30_de_pie_equilibrado_es_owas_4():
    from ergovideo.clasificar import codigo_piernas
    m = dict(rodilla_I=30.0, rodilla_D=30.0, muslo_I=15.0, muslo_D=15.0, pierna_I=15.0, pierna_D=15.0, tobillos=0.0, velocidad=0.0)
    assert codigo_piernas(m, CFG.umbrales)[0] == 4


# ------------------------------------------------------------------ desconocidos y márgenes

def test_brazo_oculto_no_es_favorable():
    r, u = puntuar(90, ocultar=(12, 14, 16))  # brazo dch. tapado
    assert not r["completo"]
    assert r["rango"][1] > r["rango"][0]  # el brazo oculto podría puntuar alto
    _, ud = puntuar(90, lado="D", ocultar=(12, 14, 16))
    assert ud["elementos"]["brazo"] == [1, 2, 3, 4, 5]


def test_nada_declarado_da_rango():
    r, u = puntuar(45, Tarea())
    assert r["rango"][1] > r["rango"][0] and u["rango"][1] > u["rango"][0]


def test_margen_que_cruza_umbral_da_rango():
    cfg = cfg_(sin_margen=False)
    r, _ = puntuar(45, cfg=cfg, flexion=18)  # 18° ± 5° cruza 20°
    assert r["elementos"]["tronco"] == [2, 3]
    r, _ = puntuar(45, cfg=cfg, flexion=40)  # 40° ± 5° no cruza nada
    assert r["elementos"]["tronco"] == [3]


def test_margen_frontal_mas_amplio():
    from ergovideo.config import margen
    assert margen("tronco_sag", 10, "3d") > margen("tronco_sag", 45, "3d")


@pytest.mark.parametrize("lo,hi,met,esperado", [(4, 7, "reba", "concluyente"), (7, 8, "reba", "acotada"),
                                                (4, 11, "reba", "incompleta"), (3, 4, "rula", "concluyente"),
                                                (4, 6, "rula", "acotada"), (2, 7, "rula", "incompleta")])
def test_estado(lo, hi, met, esperado):
    assert estado(lo, hi, met) == esperado


# ------------------------------------------------------------------ peor postura

def _rampa(desde, hasta, n=4):
    return [{k: desde.get(k, 0) + (hasta.get(k, 0) - desde.get(k, 0)) * i / (n + 1) for k in set(desde) | set(hasta)}
            for i in range(1, n + 1)]


def test_peor_postura_ignora_un_fotograma():
    exigente = dict(flexion=70, brazo_D=90)
    post = [{} for _ in range(46)] + _rampa({}, exigente) + [exigente] * 20 + _rampa(exigente, {}) + [{} for _ in range(30)]
    post[20] = dict(flexion=90, abd_I=120, abd_D=120)  # un fotograma imposible
    pose = pose_sintetica(post, vista=40)
    res = calcular(pose, CFG)
    p = peor_postura(serie(res, CFG, tarea()), "reba")
    assert 5.0 <= p["t_pico"] <= 7.0
    assert p["pico"] == puntuar(40, flexion=70, brazo_D=90)[0]["rango"][0]
    assert validar_pico(p, "reba")["nivel"] == "verde"


def test_pico_breve_no_desaparece():
    # Pico real de 0,3 s: la postura sostenida (0,5 s) no lo recoge, pero el pico breve fiable sí.
    exigente = dict(flexion=80, abd_I=110, abd_D=110)
    post = ([{} for _ in range(40)] + _rampa({}, exigente) + [exigente] * 3 + _rampa(exigente, {})
            + [{} for _ in range(40)])
    pose = pose_sintetica(post, vista=40)
    res = calcular(pose, CFG)
    p = peor_postura(serie(res, CFG, tarea()), "reba")
    assert p["breve"] is not None and p["breve"]["pico"] > p["pico"]
    assert any("pico breve" in m for m in validar_pico(p, "reba")["motivos"])


def test_validacion_con_brazo_tapado():
    pose = pose_sintetica([{} for _ in range(60)], vista=90)
    pose.lm[:, [12, 14, 16], 3] = 0.1
    res = calcular(pose, CFG)
    fs = serie(res, CFG, tarea())
    assert validar_pico(peor_postura(fs, "reba"), "reba")["nivel"] == "rojo"
    assert validar_pico(peor_postura(fs, "rula", "I"), "rula")["nivel"] == "verde"
    assert not peor_postura(fs, "rula", "D").get("completo")


def test_rula_dos_lados_y_peor():
    from ergovideo.ergo import resumen_rula
    pose = pose_sintetica([dict(brazo_D=100, codo_D=30)] * 30, vista=30)
    res = calcular(pose, CFG)
    fs = serie(res, CFG, tarea())
    por_lado = {s: peor_postura(fs, "rula", s) for s in "ID"}
    assert por_lado["D"]["pico"] > por_lado["I"]["pico"]
    assert resumen_rula(por_lado) == "D"
