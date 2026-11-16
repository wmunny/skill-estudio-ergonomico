"""OCRA: tablas, fronteras (a − ε, a, a + ε), cálculo por mano, multitarea, RcM desde el horario, sensibilidad,
escenarios, ficha de AT y lo que aporta el vídeo. Los valores esperados están escritos a mano."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import ocra, ocra_at, ocra_video  # noqa: E402
from ergovideo import tablas_ocra as T  # noqa: E402

EPS = 1e-6
FIX = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------------ tablas

@pytest.mark.parametrize("borg,esperado", [(0, 1.0), (0.5, 1.0), (1, 0.85), (1.5, 0.75), (2, 0.65), (2.5, 0.55),
                                           (3, 0.45), (3.5, 0.35), (4, 0.20), (4.5, 0.10), (5, 0.01), (7, 0.01),
                                           (10, 0.01)])
def test_fom_escalones(borg, esperado):
    assert T.fom(borg)["nominal"] == esperado


@pytest.mark.parametrize("a,abajo,arriba", [(1.0, 0.85, 0.75), (2.0, 0.65, 0.55), (3.0, 0.45, 0.35), (4.5, 0.10, 0.01)])
def test_fom_fronteras_conservador(a, abajo, arriba):
    # Sin interpolar: entre escalones se usa el superior (multiplicador más bajo) y el inferior como alternativa.
    assert T.fom(a)["nominal"] == abajo
    assert T.fom(a + EPS)["nominal"] == arriba
    assert T.fom(a + EPS)["alternativa"] == abajo
    assert T.fom(a - EPS)["nominal"] == abajo


def test_fom_rechaza_negativo():
    with pytest.raises(ValueError):
        T.fom(-1)


@pytest.mark.parametrize("f,esperado", [(0, 1.0), (1 / 3 - EPS, 1.0), (1 / 3, 0.70), (1 / 3 + EPS, 0.70),
                                        (2 / 3 - EPS, 0.70), (2 / 3, 0.60), (0.9 - EPS, 0.60), (0.9, 0.50), (1.0, 0.50)])
def test_pom_fronteras(f, esperado):
    assert T.pom_articulacion(f) == esperado


@pytest.mark.parametrize("ciclo,misma,esperado", [(15 - EPS, None, 0.70), (15, None, 1.0), (15 + EPS, None, 1.0),
                                                  (30, 0.5, 1.0), (30, 0.5 + EPS, 0.70), (30, 0.5 - EPS, 1.0),
                                                  (10, 0.1, 0.70), (None, None, 1.0)])
def test_rem_fronteras(ciclo, misma, esperado):
    assert T.rem(ciclo, misma) == esperado


@pytest.mark.parametrize("f,esperado", [(0, 1.0), (0.25 - EPS, 1.0), (0.25, 0.95), (0.51 - EPS, 0.95), (0.51, 0.90),
                                        (0.80 - EPS, 0.90), (0.80, 0.80), (1.0, 0.80)])
def test_adm_fronteras(f, esperado):
    assert T.adm_factor(f) == esperado


@pytest.mark.parametrize("h,esperado", list(T.RCM_HORAS.items()))
def test_rcm_tabla(h, esperado):
    r = T.rcm(h)
    assert r["nominal"] == r["min"] == r["max"] == esperado


def test_rcm_fraccion_da_rango():
    r = T.rcm(3.5)
    assert (r["min"], r["max"], r["nominal"]) == (0.60, 0.70, 0.60)
    r = T.rcm(3.4)
    assert (r["min"], r["max"], r["nominal"]) == (0.60, 0.70, 0.70)
    assert T.rcm(9)["nominal"] == 0.0


@pytest.mark.parametrize("m,esperado", [(0, 2.0), (120 - EPS, 2.0), (120, 1.5), (120 + EPS, 1.5), (240 - EPS, 1.5),
                                        (240, 1.0), (480, 1.0), (480 + EPS, 0.5), (600, 0.5)])
def test_dum_fronteras(m, esperado):
    assert T.dum(m) == esperado


@pytest.mark.parametrize("i,color", [(0.5, "verde"), (2.2, "verde"), (2.24, "verde"), (2.25, "amarillo"), (2.3, "amarillo"),
                                     (3.5, "amarillo"), (3.54, "amarillo"), (3.55, "rojo"), (9.78, "rojo"),
                                     (math.inf, "rojo")])
def test_clasificacion_iso2007(i, color):
    assert T.clasificar(i, "iso2007")["color"] == color


@pytest.mark.parametrize("i,color", [(2.2, "verde"), (2.3, "amarillo"), (3.5, "amarillo"), (3.6, "rojo_bajo"),
                                     (4.5, "rojo_bajo"), (4.6, "rojo"), (9.0, "rojo"), (9.04, "rojo"), (9.05, "morado"),
                                     (9.78, "morado")])
def test_clasificacion_colombini(i, color):
    assert T.clasificar(i, "colombini5")["color"] == color


def test_constantes_tienen_fuente_y_marca_iso_2026():
    for k, v in T.FUENTES.items():
        assert v["fuente"] and v["verificar_iso_2026"] is True, k
    assert "2026" in T.AVISO_NORMATIVO and "no se ha verificado" in T.AVISO_NORMATIVO


# ------------------------------------------------------------------ cálculo

MTR = {"tareas": [{"nombre": "Montaje", "minutos": 400, "ciclo_s": 10, "manos": {
    "dch": {"at_ciclo": 11, "fom": 0.85, "pom": 0.70, "rem": 0.70, "adm": 0.90},
    "izq": {"at_ciclo": 8, "fom": 0.95, "pom": 0.80, "rem": 0.70, "adm": 0.90}}}], "rcm": 0.60, "dum": 1}


def test_regresion_mtr_juguetes():
    r = ocra.calcular(MTR)
    assert round(r["manos"]["dch"]["indice"], 2) == 9.78
    assert round(r["manos"]["izq"]["indice"], 2) == 5.57
    assert r["manos"]["dch"]["frecuencia_media"] == pytest.approx(66.0)
    assert r["manos"]["izq"]["frecuencia_media"] == pytest.approx(48.0)
    assert r["peor_mano"] == "dch"
    assert r["manos"]["dch"]["clase"]["color"] == "rojo"
    r5 = ocra.calcular(dict(MTR, clasificacion="colombini5"))
    assert r5["manos"]["dch"]["clase"]["color"] == "morado"      # 9,78 > 9
    assert r5["manos"]["izq"]["clase"]["color"] == "rojo"        # 4,6–9


def test_indice_a_mano_con_dum_y_rcm_calculados():
    d = {"tareas": [{"minutos": 200, "ciclo_s": 20, "manos": {"dch": {"at_ciclo": 10, "fom": 1, "pom": 1, "rem": 1,
                                                                        "adm": 1}}}], "rcm": 1}
    r = ocra.calcular(d)
    # frecuencia 30/min; ATA = 6000; RTA = 30 × 200 × DuM(200 min → 1,5) = 9000; índice 0,667
    assert r["manos"]["dch"]["indice"] == pytest.approx(6000 / 9000)
    assert r["dum"]["nominal"] == 1.5


def test_multitarea():
    d = {"rcm": 0.8, "tareas": [
        {"nombre": "A", "minutos": 240, "ciclo_s": 12, "manos": {"dch": {"at_ciclo": 10, "fom": 0.85, "pom": 0.7, "rem": 0.7, "adm": 1}}},
        {"nombre": "B", "minutos": 120, "ciclo_s": 30, "manos": {"dch": {"at_ciclo": 15, "fom": 1, "pom": 1, "rem": 1, "adm": 0.95}}}]}
    r = ocra.calcular(d)
    ata = 50 * 240 + 30 * 120
    rta = (30 * 0.85 * 0.7 * 0.7 * 240 + 30 * 0.95 * 120) * 0.8 * 1.0   # 360 min → DuM 1
    assert r["manos"]["dch"]["indice"] == pytest.approx(ata / rta)
    assert len(r["manos"]["dch"]["tareas"]) == 2
    assert "izq" not in r["manos"]


def test_tarea_solo_de_una_mano_en_multitarea():
    d = {"rcm": 1, "tareas": [
        {"minutos": 200, "ciclo_s": 10, "manos": {"dch": {"at_ciclo": 5, "fom": 1, "pom": 1, "rem": 1, "adm": 1}}},
        {"minutos": 100, "ciclo_s": 10, "manos": {"izq": {"at_ciclo": 5, "fom": 1, "pom": 1, "rem": 1, "adm": 1}}}]}
    r = ocra.calcular(d)
    # DuM con los minutos netos repetitivos del turno (300 → 1): la mano derecha 30·200 / (30·200)
    assert r["manos"]["dch"]["indice"] == pytest.approx(1.0)
    assert r["manos"]["izq"]["indice"] == pytest.approx(1.0)


def test_desconocido_da_rango_y_nunca_el_favorable():
    d = json.loads(json.dumps(MTR))
    d["tareas"][0]["manos"]["dch"].pop("fom")
    d["tareas"][0]["manos"]["dch"]["borg"] = None
    r = ocra.calcular(d)["manos"]["dch"]
    assert r["indice"] is None
    # FoM recorre 0,01–1: el máximo del índice es 85 veces el de FoM 0,85 / 0,01 respecto al mínimo.
    assert r["indice_min"] == pytest.approx(9.7817 * 0.85, rel=1e-3)
    assert r["indice_max"] == pytest.approx(9.7817 * 0.85 / 0.01, rel=1e-3)
    assert r["clase_max"]["color"] == "rojo"


def test_sin_horario_rcm_recorre_y_el_indice_puede_ser_infinito():
    d = json.loads(json.dumps(MTR))
    d.pop("rcm")
    r = ocra.calcular(d)
    assert r["rcm"]["origen"] == "desconocido"
    assert math.isinf(r["manos"]["dch"]["indice_max"])


def test_borg_por_fases_ponderado():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 10, "manos": {"dch": {
        "at_ciclo": 5, "pom": 1, "rem": 1, "adm": 1,
        "borg": [{"fase": "coger", "s": 6, "borg": 0.5}, {"fase": "atornillar", "s": 4, "borg": 2}]}}}]}
    r = ocra.calcular(d)
    t = r["manos"]["dch"]["tareas"][0]
    assert t["fom"]["borg_medio"] == pytest.approx(1.1)      # (6·0,5 + 4·2) / 10
    assert t["fom"]["nominal"] == 0.75                        # escalón conservador 1,5
    assert t["fom"]["fom_alternativa"] == 0.85
    assert any("escalón inferior" in s["caso"] for s in r["sensibilidad"])


def test_borg_con_fase_desconocida_da_rango():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 10, "manos": {"dch": {
        "at_ciclo": 5, "pom": 1, "rem": 1, "adm": 1,
        "borg": [{"s": 6, "borg": 1}, {"s": 4, "borg": None}]}}}]}
    f = ocra.calcular(d)["manos"]["dch"]["tareas"][0]["fom"]
    assert f["nominal"] is None and f["min"] == 0.01 and f["max"] == 0.85


def test_pom_desde_posturas_toma_el_mas_bajo():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 30, "manos": {"dch": {
        "at_ciclo": 5, "fom": 1, "rem": 1, "adm": 1,
        "posturas": {"hombro": 0.2, "codo": 0.5, "muneca": 0.7, "agarre": 0.1}}}}]}
    t = ocra.calcular(d)["manos"]["dch"]["tareas"][0]
    assert t["pom"]["nominal"] == 0.60
    assert t["pom_detalle"]["codo"]["nominal"] == 0.70


def test_pom_con_agarre_desconocido_es_rango():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 30, "manos": {"dch": {
        "at_ciclo": 5, "fom": 1, "rem": 1, "adm": 1, "posturas": {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}}}}]}
    p = ocra.calcular(d)["manos"]["dch"]["tareas"][0]["pom"]
    assert (p["min"], p["max"], p["nominal"]) == (0.5, 1.0, None)


def test_estereotipia_no_se_duplica_en_pom():
    d = {"rcm": 1, "tareas": [{"minutos": 400, "ciclo_s": 10, "manos": {"dch": {
        "at_ciclo": 5, "fom": 1, "rem": 1, "adm": 1, "posturas": {"estereotipia": 0.9}}}}]}
    with pytest.raises(ocra.DatosOcraInvalidos, match="ReM"):
        ocra.calcular(d)


def test_rem_desde_ciclo_y_misma_accion():
    base = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 20, "manos": {"dch": {
        "at_ciclo": 5, "fom": 1, "pom": 1, "adm": 1}}}]}
    assert ocra.calcular(base)["manos"]["dch"]["tareas"][0]["rem"]["min"] == 0.70  # misma acción desconocida → rango
    base["tareas"][0]["manos"]["dch"]["misma_accion"] = 0.3
    assert ocra.calcular(base)["manos"]["dch"]["tareas"][0]["rem"]["nominal"] == 1.0
    base["tareas"][0]["ciclo_s"] = 10
    assert ocra.calcular(base)["manos"]["dch"]["tareas"][0]["rem"]["nominal"] == 0.70


def test_adm_por_factores():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 30, "manos": {"dch": {
        "at_ciclo": 5, "fom": 1, "pom": 1, "rem": 1,
        "adicionales": [{"factor": "guantes", "fraccion": 1.0}, {"factor": "precision", "fraccion": 0.3}]}}}]}
    assert ocra.calcular(d)["manos"]["dch"]["tareas"][0]["adm"]["nominal"] == 0.80
    d["tareas"][0]["manos"]["dch"]["adicionales"] = []
    assert ocra.calcular(d)["manos"]["dch"]["tareas"][0]["adm"]["nominal"] == 1.0
    d["tareas"][0]["manos"]["dch"]["adicionales"] = [{"factor": "magia", "fraccion": 1}]
    with pytest.raises(ocra.DatosOcraInvalidos):
        ocra.calcular(d)


def test_ciclo_desde_piezas():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "piezas": 2400, "manos": {"dch": {
        "at_ciclo": 10, "fom": 1, "pom": 1, "rem": 1, "adm": 1}}}]}
    t = ocra.calcular(d)["manos"]["dch"]["tareas"][0]
    assert t["ciclo_s"]["nominal"] == pytest.approx(10.0)
    assert t["frecuencia"]["nominal"] == pytest.approx(60.0)


def test_at_como_rango():
    d = json.loads(json.dumps(MTR))
    d["tareas"][0]["manos"]["dch"]["at_ciclo"] = [10, 12]
    m = ocra.calcular(d)["manos"]["dch"]
    assert m["indice"] is None
    assert m["indice_min"] == pytest.approx(9.7817 * 10 / 11, rel=1e-3)
    assert m["indice_max"] == pytest.approx(9.7817 * 12 / 11, rel=1e-3)


def test_origen_en_trazabilidad():
    d = json.loads(json.dumps(MTR))
    d["tareas"][0]["manos"]["dch"]["at_ciclo"] = {"valor": 11, "origen": "revisión visual", "nota": "ficha"}
    traz = ocra.calcular(d)["trazabilidad"]
    fila = next(f for f in traz if f["dato"].endswith("AT por ciclo") and f["mano"] == "derecha")
    assert fila["origen"] == "revisión visual" and fila["valor"] == "11"


def test_datos_invalidos():
    with pytest.raises(ocra.DatosOcraInvalidos):
        ocra.calcular({"tareas": []})
    with pytest.raises(ocra.DatosOcraInvalidos, match="minutos"):
        ocra.calcular({"tareas": [{"ciclo_s": 10, "manos": {"dch": {"at_ciclo": 3}}}]})
    with pytest.raises(ocra.DatosOcraInvalidos, match="ciclo"):
        ocra.calcular({"tareas": [{"minutos": 10, "manos": {"dch": {"at_ciclo": 3}}}]})
    with pytest.raises(ocra.DatosOcraInvalidos):
        ocra.calcular(dict(MTR, clasificacion="otra"))
    with pytest.raises(ocra.DatosOcraInvalidos):
        ocra.calcular({"tareas": [{"minutos": 10, "ciclo_s": 10, "manos": {"dch": {"at_ciclo": [5, 3]}}}]})


# ------------------------------------------------------------------ RcM desde el horario

def test_rcm_horario_solo_comida():
    h = ocra.rcm_desde_horario({"inicio": "08:00", "fin": "16:30", "pausas": [{"hora": "12:00", "min": 30, "tipo": "comida"}]})
    # 8–12 (240) cubre 60 → 180; 12:30–16:30 (240) cubre 60 → 180; 6 h → 0,25
    assert h["horas"] == 6 and h["nominal"] == 0.25


def test_rcm_horario_con_pausas():
    h = ocra.rcm_desde_horario({"inicio": "08:00", "fin": "16:00", "pausas": [
        {"hora": "10:00", "min": 10}, {"hora": "12:00", "min": 30, "tipo": "comida"}, {"hora": "14:00", "min": 10}]})
    # 70 + 50 + 40 + 50 = 210 min = 3,5 h → rango 0,60–0,70, nominal 0,60
    assert h["horas"] == 3.5
    assert (h["min"], h["max"], h["nominal"]) == (0.60, 0.70, 0.60)


def test_rcm_pausa_corta_no_cuenta():
    a = ocra.rcm_desde_horario({"inicio": "08:00", "fin": "10:00", "pausas": [{"hora": "09:00", "min": 8 - 0.5}]})
    b = ocra.rcm_desde_horario({"inicio": "08:00", "fin": "10:00", "pausas": [{"hora": "09:00", "min": 8}]})
    assert not a["tramos"][0]["adecuada"] and b["tramos"][0]["adecuada"]
    assert a["horas"] > b["horas"]


def test_rcm_tarea_no_repetitiva_solo_si_se_marca():
    base = {"inicio": "08:00", "fin": "12:00", "pausas": []}
    a = ocra.rcm_desde_horario(dict(base, no_repetitivas=[{"hora": "10:00", "min": 20}]))
    b = ocra.rcm_desde_horario(dict(base, no_repetitivas=[{"hora": "10:00", "min": 20, "cuenta_como_recuperacion": True}]))
    assert b["horas"] < a["horas"]


def test_rcm_pausa_fuera_del_turno():
    with pytest.raises(ocra.DatosOcraInvalidos):
        ocra.rcm_desde_horario({"inicio": "08:00", "fin": "12:00", "pausas": [{"hora": "13:00", "min": 10}]})


def test_rcm_calculado_entra_en_el_indice():
    d = json.loads(json.dumps(MTR))
    d.pop("rcm")
    d["turno"] = {"inicio": "08:00", "fin": "16:00", "pausas": [
        {"hora": "10:00", "min": 10}, {"hora": "12:00", "min": 30, "tipo": "comida"}, {"hora": "14:00", "min": 10}]}
    r = ocra.calcular(d)
    assert r["rcm"]["origen"] == "calculado" and r["rcm"]["nominal"] == 0.60
    assert round(r["manos"]["dch"]["indice"], 2) == 9.78
    assert r["manos"]["dch"]["indice_min"] == pytest.approx(9.7817 * 0.6 / 0.7, rel=1e-3)
    casos = [s["caso"] for s in r["sensibilidad"]]
    assert "1 hora menos sin recuperación" in casos


# ------------------------------------------------------------------ sensibilidad y escenario

def test_sensibilidad_at():
    s = {x["caso"]: x for x in ocra.calcular(MTR)["sensibilidad"]}
    assert s["1 AT menos por ciclo"]["dch"]["indice"] == pytest.approx(9.7817 * 10 / 11, rel=1e-4)
    assert s["1 AT más por ciclo"]["izq"]["indice"] == pytest.approx(5.5695 * 9 / 8, rel=1e-4)
    assert s["Borg +0,5 (un escalón más de esfuerzo)"]["dch"]["indice"] == pytest.approx(9.7817 * 0.85 / 0.75, rel=1e-4)


def test_escenario_proyectado():
    e = ocra.escenario(MTR, {"tareas": [{"manos": {"dch": {"at_ciclo": 8}}}], "rcm": 0.8})
    assert e["proyeccion"] is True
    assert e["resultado"]["manos"]["dch"]["indice"] == pytest.approx(9.7817 * 8 / 11 * 0.6 / 0.8, rel=1e-4)
    assert MTR["tareas"][0]["manos"]["dch"]["at_ciclo"] == 11  # no toca los datos originales


# ------------------------------------------------------------------ ficha de AT

def _a(t, mano, gesto, **kw):
    return dict(dict(t=t, mano=mano, gesto=gesto, objeto=kw.pop("objeto", "pieza"), confianza=kw.pop("confianza", "alta")), **kw)


@pytest.mark.parametrize("gesto,esperado", [
    ("alcanzar", 0), ("coger", 1), ("agarrar", 1), ("pasar_mano", 1), ("posicionar", 1), ("empujar", 1), ("tirar", 1),
    ("presionar", 1), ("girar", 1), ("coger_herramienta", 1), ("posicionar_herramienta", 1),
    ("accionar_herramienta", 1), ("devolver_herramienta", 0), ("dejar_herramienta_soporte", 1), ("soltar", 0),
    ("abrir_mano", 0), ("sujetar", 0), ("control_visual", 0), ("andar", 0), ("esperar", 0), ("golpear", 1),
    ("pasada", 1)])
def test_regla_por_gesto(gesto, esperado):
    f = ocra_at.validar({"ciclo": {"inicio": 0, "fin": 10}, "acciones": [_a(1, "dch", gesto, cuenta=bool(esperado))]})
    a = f["acciones"][0]
    assert a["at"] == esperado
    assert a["estado"] == ("valida" if esperado else "no_es_at")


@pytest.mark.parametrize("gesto", ["alcanzar", "devolver_herramienta", "soltar", "abrir_mano", "sujetar",
                                   "control_visual", "andar", "esperar"])
def test_rechaza_lo_que_no_es_at(gesto):
    f = ocra_at.validar({"ciclo": {"inicio": 0, "fin": 10}, "acciones": [_a(1, "izq", gesto, cuenta=True)]})
    assert f["acciones"][0]["estado"] == "rechazada"
    assert f["recuento"]["izq"]["min"] == f["recuento"]["izq"]["max"] == 0
    assert f["recuento"]["izq"]["rechazadas"][0]["gesto"] == gesto


def test_repeticiones_girar_accionar_golpear():
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [
        _a(1, "dch", "girar", repeticiones=3), _a(2, "dch", "accionar_herramienta", repeticiones=2),
        _a(3, "dch", "golpear", repeticiones=4)]})
    assert f["recuento"]["dch"]["nominal"] == 9


def test_repeticiones_no_valen_para_coger():
    with pytest.raises(ocra_at.FichaInvalida, match="repeticiones"):
        ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "dch", "coger", repeticiones=2)]})


@pytest.mark.parametrize("dist,at,estado", [(0.99, 0, "rechazada"), (1.0, 1, "valida"), (1.5, 1, "valida"),
                                            (None, 1, "dudosa")])
def test_transportar(dist, at, estado):
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "dch", "transportar", distancia_m=dist)]})
    assert (f["acciones"][0]["at"], f["acciones"][0]["estado"]) == (at, estado)


def test_introducir_sin_esfuerzo_ni_precision():
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [
        _a(1, "dch", "introducir", con_esfuerzo_o_precision=False),
        _a(2, "dch", "encajar", con_esfuerzo_o_precision=None),
        _a(3, "dch", "sacar", con_esfuerzo_o_precision=True)]})
    est = [a["estado"] for a in f["acciones"]]
    assert est == ["rechazada", "dudosa", "valida"]
    assert (f["recuento"]["dch"]["min"], f["recuento"]["dch"]["max"]) == (1, 2)


def test_introducir_tras_posicionar_solo_si_es_otro_gesto():
    base = [_a(1, "dch", "posicionar", objeto="tornillo"),
            _a(1.4, "dch", "introducir", objeto="tornillo", con_esfuerzo_o_precision=True)]
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": base})
    assert (f["recuento"]["dch"]["min"], f["recuento"]["dch"]["max"]) == (1, 2)
    base[1]["gesto_distinto"] = True
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": base})
    assert f["recuento"]["dch"]["nominal"] == 2


def test_confianza_baja_da_rango():
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "dch", "coger"), _a(2, "dch", "posicionar", confianza="baja")]})
    r = f["recuento"]["dch"]
    assert (r["min"], r["max"], r["nominal"]) == (1, 2, None)
    assert ocra_at.at_ciclo_valor(r, "revisión visual")["valor"] == [1, 2]


def test_regla_cuenta_aunque_el_revisor_no():
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "dch", "coger", cuenta=False)]})
    assert f["acciones"][0]["at"] == 1 and "revisor no la marcó" in f["acciones"][0]["motivo"]


def test_manos_por_separado_y_errores():
    with pytest.raises(ocra_at.FichaInvalida):
        ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "ambas", "coger")]})
    with pytest.raises(ocra_at.FichaInvalida):
        ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "dch", "teletransportar")]})
    with pytest.raises(ocra_at.FichaInvalida, match="fuera del ciclo"):
        ocra_at.validar({"ciclo": {"inicio": 0, "fin": 10}, "acciones": [_a(12, "dch", "coger")]})
    with pytest.raises(ocra_at.FichaInvalida):
        ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [_a(1, "dch", "coger", confianza="mucha")]})


def test_misma_accion():
    f = ocra_at.validar({"ciclo": {"fin": 10}, "acciones": [
        _a(1, "dch", "coger"), _a(2, "dch", "accionar_herramienta", repeticiones=3)]})
    assert ocra_at.misma_accion(f["acciones"], "dch") == pytest.approx(0.75)
    assert ocra_at.misma_accion(f["acciones"], "izq") is None


def test_mtr_ficha_de_17_14_se_queda_en_11_8():
    """Otro análisis contaba 17 AT (dch) y 14 (izq): la ficha marca como no válidas «devolver herramienta» y las
    sujeciones de la mano de apoyo, y el recuento válido queda en 11 y 8."""
    ficha = json.loads((FIX / "ocra_mtr_ficha_17_14.json").read_text(encoding="utf-8"))
    assert sum(1 for a in ficha["acciones"] if a["mano"] == "dch") == 17
    assert sum(1 for a in ficha["acciones"] if a["mano"] == "izq") == 14
    f = ocra_at.validar(ficha)
    r = f["recuento"]
    assert (r["dch"]["nominal"], r["izq"]["nominal"]) == (11, 8)
    rech_d = {x["gesto"] for x in r["dch"]["rechazadas"]}
    rech_i = {x["gesto"] for x in r["izq"]["rechazadas"]}
    assert "devolver_herramienta" in rech_d
    assert rech_i == {"sujetar"}
    assert len(r["izq"]["rechazadas"]) == 6


# ------------------------------------------------------------------ vídeo (series sintéticas)

def _res_sintetico(periodo=10.0, dur=30.0, fps=10.0, codo_alto=False):
    t = np.arange(0, dur, 1 / fps)
    n = len(t)
    onda = np.sin(2 * np.pi * t / periodo)
    s = {}
    for lado in "ID":
        s[f"brazo_alt_{lado}"] = -1 + 0.5 * onda
        s[f"codo_{lado}"] = (110 if codo_alto else 60) + 20 * onda
        s[f"brazo_flex_{lado}"] = 40 + 50 * onda          # > 80° cuando onda > 0,8
        s[f"antebrazo_lat_{lado}"] = 0.5 * onda
        s[f"brazo_abd_{lado}"] = np.full(n, 10.0)
        s[f"muneca_{lado}"] = np.full(n, np.nan)          # no medida
    return dict(t=t, series=s)


def test_ciclo_por_periodicidad():
    r = ocra_video.ciclo_periodicidad(_res_sintetico(10.0), 30.0)
    assert r["ciclo_s"] == pytest.approx(10.0, abs=0.2)
    assert r["fiable"] and r["ciclos"] == pytest.approx(3.0, abs=0.1)


def test_ciclo_sin_series():
    res = _res_sintetico()
    for k in res["series"]:
        res["series"][k][:] = np.nan
    assert ocra_video.ciclo_periodicidad(res, 30.0)["ciclo_s"] is None


def test_fracciones_postura_con_margen_y_no_medido():
    fr = ocra_video.fracciones_postura(_res_sintetico())["dch"]
    # hombro: flexión 40 + 50·sen ≥ 80 ± 10 → seguro sen ≥ 1 (casi nunca), posible sen ≥ 0,6
    assert fr["hombro"]["min"] < 0.05 and 0.25 < fr["hombro"]["max"] < 0.35
    assert fr["muneca"]["min"] == 0.0 and fr["muneca"]["max"] == 1.0 and fr["muneca"]["cobertura"] == 0.0
    ent = ocra_video.postura_como_entrada(fr["muneca"])
    assert ent["valor"] is None and ent["origen"] == "desconocido"
    ent = ocra_video.postura_como_entrada(fr["hombro"])
    assert ent["origen"] == "medido" and isinstance(ent["valor"], list)


def test_validar_ocra_sin_mediapipe():
    v = ocra_video.validar({"duracion": 30.0, "fps": 30.0}, None, None, None, ciclo_declarado=10.0)
    assert v["nivel"] == "verde" and v["ciclo_s"] == 10.0
    assert any("observacional" in m for m in v["motivos"])
    v = ocra_video.validar({"duracion": 25.0, "fps": 30.0}, None, None, None, ciclo_declarado=10.0)
    assert v["nivel"] == "ambar"
    v = ocra_video.validar({"duracion": 15.0, "fps": 30.0}, None, None, None, ciclo_declarado=10.0)
    assert v["nivel"] == "rojo"
    v = ocra_video.validar({"duracion": 60.0, "fps": 12.0}, None, None, None, ciclo_declarado=10.0)
    assert v["nivel"] == "rojo"
    v = ocra_video.validar({"duracion": 60.0, "fps": 20.0}, None, None, None, ciclo_declarado=10.0)
    assert v["nivel"] == "ambar" and any("25 fps" in m for m in v["como_mejorar"])


def test_validar_ocra_no_penaliza_piernas():
    # Mismo vídeo con y sin piernas: OCRA no las mira (solo ciclos, manos, lado y fps).
    v = ocra_video.validar({"duracion": 30.0, "fps": 30.0}, None, None, {"ciclo": {"inicio": 0, "fin": 10}})
    assert v["nivel"] == "verde" and not any("pierna" in m.lower() or "tronco" in m.lower() for m in v["motivos"])


# ------------------------------------------------------------------ integración: CLI, revisión e informe

from ergovideo import cli, cli_ocra, informe_ocra, revision  # noqa: E402


def test_leer_metodos():
    assert cli_ocra.leer_metodos(None) == ["owas", "reba", "rula", "ocra"]
    assert cli_ocra.leer_metodos("todos") == ["owas", "reba", "rula", "ocra"]
    assert cli_ocra.leer_metodos("ocra") == ["ocra"]
    assert cli_ocra.leer_metodos("OWASP, rula") == ["owas", "rula"]
    assert not cli_ocra.posturales(["ocra"]) and cli_ocra.posturales(["ocra", "rula"])
    with pytest.raises(SystemExit):
        cli_ocra.leer_metodos("niosh")


def _rev(tmp_path, acciones, **ocra_kw):
    r = revision.plantilla("v.mp4", 30.0)
    r["ocra"] = dict(revision.plantilla_ocra(10.0, 20.0), acciones=acciones, **ocra_kw)
    ruta = tmp_path / "revision.json"
    ruta.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_revision_valida_la_ficha(tmp_path):
    r = revision.cargar(_rev(tmp_path, [_a(11, "dch", "coger"), _a(12, "dch", "soltar")]), 30.0)
    assert r["_ocra_ficha"]["recuento"]["dch"]["nominal"] == 1
    with pytest.raises(revision.RevisionInvalida, match="gesto"):
        revision.cargar(_rev(tmp_path, [_a(11, "dch", "volar")]), 30.0)
    with pytest.raises(revision.RevisionInvalida, match="manos_visibles"):
        revision.cargar(_rev(tmp_path, [], manos_visibles="sí"), 30.0)


def test_hallazgo_de_frecuencia_con_rango_de_at():
    d = json.loads(json.dumps(MTR))
    d["tareas"][0]["manos"]["dch"]["at_ciclo"] = [11, 14]
    hs = {h["id"]: h for h in informe_ocra.hallazgos(ocra.calcular(d))}
    assert hs["ocra_frecuencia"]["gravedad"] == "alta"
    assert "66–84" in hs["ocra_frecuencia"]["detalle"]
    assert hs["ocra_recuperacion"]["gravedad"] == "alta"     # RcM 0,60


def test_sin_hallazgos_si_todo_es_favorable_y_conocido():
    d = {"rcm": 1, "dum": 1, "tareas": [{"minutos": 400, "ciclo_s": 30, "manos": {"dch": {
        "at_ciclo": 10, "fom": 1, "pom": 1, "rem": 1, "adm": 1}}}]}
    r = ocra.calcular(d)
    assert informe_ocra.hallazgos(r) == []
    assert informe_ocra.indicador(r)["urgencia"] == 0


def test_orden_ocra_sin_video_escribe_el_informe(tmp_path, capsys):
    datos = tmp_path / "datos.json"
    d = json.loads(json.dumps(MTR))
    d["tareas"][0]["ciclo_s"] = 10
    datos.write_text(json.dumps(d), encoding="utf-8")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "adaptacion.json").write_text(json.dumps({"escenario_ocra": {
        "titulo": "Menos AT", "medidas": ["útil"], "cambios": {"tareas": [{"manos": {"dch": {"at_ciclo": 8}}}]}}}),
        encoding="utf-8")
    assert cli.main(["ocra", "--datos-ocra", str(datos), "--salida", str(tmp_path / "out"),
                     "--clasificacion-ocra", "colombini5"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["manos"]["dch"]["indice"] == "9,78" and out["manos"]["dch"]["color"] == "morado"
    html = (tmp_path / "out" / "informe.html").read_text(encoding="utf-8")
    assert "Movimientos repetitivos de la extremidad superior (OCRA)" in html
    assert "Escenario proyectado — no es un resultado" in html
    assert "no se ha verificado la conformidad" in html
    assert "Colombini y Occhipinti (5 bandas)" in html
    assert "Prueba de concepto no validada" in html
    assert "MediaPipe" not in html.split('id="tecnico"')[0].split("Métodos: OCRA")[1][:200]


def test_orden_ocra_datos_invalidos(tmp_path, capsys):
    datos = tmp_path / "datos.json"
    datos.write_text(json.dumps({"tareas": [{"ciclo_s": 10, "manos": {"dch": {"at_ciclo": 3}}}]}), encoding="utf-8")
    assert cli.main(["ocra", "--datos-ocra", str(datos)]) == 2


def test_faltan_datos_de_organizacion():
    f = cli_ocra.faltan({"tareas": [{"ciclo_s": 10, "manos": {"dch": {"at_ciclo": 3}}}]})
    assert any("minutos" in x for x in f) and any("horario" in x for x in f) and any("Borg" in x for x in f)
