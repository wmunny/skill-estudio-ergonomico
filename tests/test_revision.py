"""Revisión visual: validación del JSON, política de decisión en código, origen de los datos y su efecto."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import ergo, revision  # noqa: E402
from ergovideo.clasificar import piernas  # noqa: E402
from ergovideo.config import Config  # noqa: E402
from ergovideo.medidas import calcular  # noqa: E402
from ergovideo.sintetico import pose_sintetica  # noqa: E402

nan = math.nan


def escribir(tmp_path, rev):
    p = tmp_path / "rev.json"
    p.write_text(json.dumps(rev), encoding="utf-8")
    return p


def rev_base(**cambios):
    r = revision.plantilla("v.mp4", 10.0)
    r.update(cambios)
    return r


def veredicto(art, a, b, v, lado="no_se_sabe"):
    return dict(articulacion=art, inicio=a, fin=b, veredicto=v, motivo="m", evidencia="se ve", lado_cercano=lado)


# ------------------------------------------------------------------ carga y validación

def test_plantilla_es_valida(tmp_path):
    assert revision.cargar(escribir(tmp_path, rev_base()), 10.0)["contexto"]["postura_base"] == "no_se_sabe"


@pytest.mark.parametrize("cambio,texto", [
    (lambda r: r["contexto"].update(postura_base="tumbado"), "postura_base"),
    (lambda r: r["revisiones"].append(dict(veredicto("codo_dch", 1, 2, "no_visible"), evidencia="")), "evidencia"),
    (lambda r: r["revisiones"].append(veredicto("dedo", 1, 2, "no_visible")), "articulacion"),
    (lambda r: r["fases"].append(dict(inicio=0, fin=50, descripcion="x", riesgo="alto")), "fuera del vídeo"),
    (lambda r: r["munecas"].append(dict(inicio=0, fin=2, lado="izq", flexion="mucha", confianza="alta")), "flexion"),
    (lambda r: r["contexto"]["actividad"].update(repetitiva="sí"), "actividad.repetitiva"),
])
def test_errores_de_validacion(tmp_path, cambio, texto):
    r = rev_base()
    cambio(r)
    with pytest.raises(revision.RevisionInvalida, match=texto):
        revision.cargar(escribir(tmp_path, r), 10.0)


# ------------------------------------------------------------------ política de decisión

@pytest.fixture
def pose():
    return pose_sintetica([{} for _ in range(100)], vista=40, fps=10)


def test_no_visible_larga_se_quita_corta_se_aproxima(pose):
    r = rev_base(revisiones=[veredicto("codo_dch", 1.0, 4.0, "no_visible"), veredicto("codo_izq", 5.0, 6.0, "no_visible")])
    pol = revision.politica(r, pose)
    t = pose.times
    assert pol["quitar"][(t >= 1) & (t <= 4), 14].all() and not pol["quitar"][(t >= 1) & (t <= 4), 13].any()
    assert pol["aprox"][(t >= 5) & (t <= 6), 13].all() and not pol["quitar"][:, 13].any()
    assert "larga" in pol["decisiones"][0]["accion"] or "larga" in pol["decisiones"][1]["accion"]


def test_mal_colocada_se_quita_con_la_mano(pose):
    pol = revision.politica(rev_base(revisiones=[veredicto("muneca_izq", 2.0, 2.5, "mal_colocada")]), pose)
    sel = (pose.times >= 2.0) & (pose.times <= 2.5)
    assert pol["quitar"][np.ix_(sel, [15, 17, 19, 21])].all()


def test_lado_invertido_sin_confirmar_queda_en_disputa(pose):
    # Profundidad de los hombros casi igual: MediaPipe no confirma qué lado está más cerca.
    pose.lm[:, [11, 12], 2] = 0.0
    pol = revision.politica(rev_base(revisiones=[veredicto("hombro_izq", 1, 3, "lado_invertido", "izq")]), pose)
    assert not pol["intercambiar"].any() and "disputa" in pol["decisiones"][0]["accion"]


def test_lado_invertido_confirmado_se_intercambia(pose):
    pose.lm[:, 11, 2], pose.lm[:, 12, 2] = 0.3, -0.3  # MediaPipe: el «derecho» está más cerca
    pol = revision.politica(rev_base(revisiones=[veredicto("hombro_izq", 1, 3, "lado_invertido", "izq")]), pose)
    assert pol["intercambiar"][(pose.times >= 1) & (pose.times <= 3)].all()
    p2 = revision.aplicar_intercambio(pose, pol["intercambiar"])
    k = int(np.argmin(np.abs(pose.times - 2)))
    assert p2.lm[k, 11, 2] == pytest.approx(-0.3) and pose.lm[k, 11, 2] == pytest.approx(0.3)


def test_politica_se_aplica_en_las_medidas(pose):
    cfg = Config()
    pol = revision.politica(rev_base(revisiones=[veredicto("codo_dch", 1.0, 4.0, "no_visible"),
                                                 veredicto("codo_izq", 5.0, 6.0, "aproximada")]), pose)
    res = calcular(pose, cfg, pol)
    t = res["t"]
    assert np.isnan(res["series"]["codo_D"][(t > 1.5) & (t < 3.5)]).all()
    assert res["aproximado"]["codo_I"][(t >= 5) & (t <= 6)].all()


def test_aproximada_amplia_el_margen():
    cfg = Config()
    m = dict(tronco_sag=0.0, tronco_flex=0.0, tronco_giro=0.0, tronco_lat=0.0, cuello=0.0, brazo_flex_I=38.0, brazo_flex_D=0.0,
             brazo_abd_I=0.0, brazo_abd_D=0.0, codo_I=80.0, codo_D=80.0, muneca_I=nan, muneca_D=nan, antebrazo_lat_I=1.0,
             antebrazo_lat_D=1.0, rodilla_I=0.0, rodilla_D=0.0, muslo_I=0.0, muslo_D=0.0, pierna_I=0.0, pierna_D=0.0,
             tobillos=0.0, velocidad=0.0)
    t = ergo.Tarea(muneca="neutra", hombro_elevado=False, brazo_apoyado=False)  # declarado: solo cambia el margen
    normal = ergo.rula(m, cfg, t, "I", 45, "3d")["elementos"]["brazo"]
    aprox = ergo.rula(dict(m, _aprox=frozenset({"brazo_flex_I"})), cfg, t, "I", 45, "3d")["elementos"]["brazo"]
    assert set(normal) <= set(aprox)
    m2 = dict(m, brazo_flex_I=33.0)  # 33 ± 10 = 23–43: solo 2; 33 ± 15 = 18–48: cruza 20 y 45
    assert ergo.rula(m2, cfg, t, "I", 45, "3d")["elementos"]["brazo"] == [2]
    assert ergo.rula(dict(m2, _aprox=frozenset({"brazo_flex_I"})), cfg, t, "I", 45, "3d")["elementos"]["brazo"] == [1, 2, 3]


# ------------------------------------------------------------------ contexto y origen de los datos

def test_usuario_manda_sobre_la_ia():
    r = rev_base()
    r["contexto"].update(carga_kg_estimada=0.5, agarre="regular", postura_base="sentado", confirmado=["agarre"])
    t, postura, orig = revision.completar_tarea(ergo.Tarea(carga_kg=3.0), r, "auto")
    assert t.carga_kg == 3.0 and orig["carga_kg"] == "declarado"
    assert t.agarre == 1 and orig["agarre"] == "IA, confirmado"
    assert postura == "sentado" and orig["postura_base"] == "estimado por IA"
    assert orig["brazo_rotado"] == "desconocido"
    t2, postura2, orig2 = revision.completar_tarea(ergo.Tarea(), r, "de_pie")
    assert postura2 == "de_pie" and orig2["postura_base"] == "declarado"


def test_sin_revision_todo_desconocido():
    t, postura, orig = revision.completar_tarea(ergo.Tarea(), None, "auto")
    assert t.carga_kg is None and postura == "auto" and orig["agarre"] == "desconocido"


# ------------------------------------------------------------------ piernas que no se ven

PIERNAS_OCULTAS = dict(rodilla_I=nan, rodilla_D=nan, muslo_I=nan, muslo_D=nan, pierna_I=nan, pierna_D=nan, tobillos=nan,
                       velocidad=0.0)


def test_sentado_cierra_las_piernas_aunque_no_se_vean():
    s, notas = piernas(PIERNAS_OCULTAS, Config().umbrales, "sentado", lambda k: 0.0)
    assert s == {1} and "piernas_no_visibles" not in notas


def test_de_pie_con_supuestos():
    u = Config().umbrales
    assert len(piernas(PIERNAS_OCULTAS, u, "auto", lambda k: 0.0)[0]) > 1
    from ergovideo.config import margen
    s, notas = piernas(PIERNAS_OCULTAS, u, "de_pie", lambda k: margen(k, 45, "3d"), dict(rodillas="menos30", apoyo="bilateral"))
    assert s == {2} and "rodillas_supuestas" in notas


def test_rodillas_supuestas_no_sustituyen_a_una_medida():
    m = dict(PIERNAS_OCULTAS, rodilla_I=50.0, rodilla_D=50.0, tobillos=0.0)
    s, _ = piernas(m, Config().umbrales, "de_pie", lambda k: 0.0, dict(rodillas="menos30", apoyo="bilateral"))
    assert s == {4}


# ------------------------------------------------------------------ muñecas por fase y cobertura por fase

def test_munecas_de_la_ia_por_fase():
    r = rev_base(munecas=[dict(inicio=0, fin=5, lado="izq", flexion="mas_15", desviada=True, girada=False, confianza="alta"),
                          dict(inicio=0, fin=5, lado="dch", flexion="hasta_15", desviada=None, girada=None, confianza="baja")])
    assert revision.munecas_en(r, 2.0) == {"I": dict(flexion="mas15", desviada=True, girada=False)}
    assert revision.munecas_en(r, 7.0) == {}
    cfg = Config()
    cfg.muestreo.sin_margen = True
    m = dict(tronco_sag=0.0, tronco_flex=0.0, tronco_giro=0.0, tronco_lat=0.0, cuello=0.0, brazo_flex_I=0.0, brazo_flex_D=0.0,
             brazo_abd_I=0.0, brazo_abd_D=0.0, codo_I=80.0, codo_D=80.0, muneca_I=nan, muneca_D=nan, antebrazo_lat_I=1.0,
             antebrazo_lat_D=1.0, rodilla_I=0.0, rodilla_D=0.0, muslo_I=0.0, muslo_D=0.0, pierna_I=0.0, pierna_D=0.0,
             tobillos=0.0, velocidad=0.0, _mun=revision.munecas_en(r, 2.0))
    t = ergo.Tarea()
    assert ergo.rula(m, cfg, t, "I", 45, "3d")["elementos"]["muneca"] == [4]       # 3 + desviada
    assert ergo.reba(m, cfg, t, 45, "3d")["elementos"]["lados"]["I"]["muneca"] == [3]  # 2 + desviada
    assert ergo.rula(m, cfg, t, "D", 45, "3d")["elementos"]["muneca"] == [1, 2, 3, 4]  # confianza baja: desconocida
    assert ergo.rula(m, cfg, ergo.Tarea(muneca="neutra", muneca_desviada=False), "I", 45, "3d")["elementos"]["muneca"] == [1]


def test_fase_de_riesgo_sin_ver_pone_rojo():
    pose = pose_sintetica([{} for _ in range(60)], vista=90)
    pose.lm[30:, [12, 14, 16], 3] = 0.1  # brazo dch. oculto en la segunda mitad
    cfg = Config()
    res = calcular(pose, cfg)
    fs = ergo.serie(res, cfg, ergo.Tarea())
    fases = [dict(inicio=0, fin=3, descripcion="a", riesgo="bajo"), dict(inicio=3, fin=6, descripcion="b", riesgo="alto")]
    cob = ergo.cobertura_fases(fs, "rula", "D", fases)
    assert cob[0]["cobertura"] > 90 and cob[1]["cobertura"] < 10
    v = ergo.validar_pico(ergo.peor_postura(fs, "rula", "D"), "rula", cob)
    assert v["nivel"] == "rojo" and any("«b»" in m for m in v["motivos"])
