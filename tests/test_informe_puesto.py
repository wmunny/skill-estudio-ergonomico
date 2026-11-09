"""Informe ergonómico del puesto: hallazgos (reglas), plan de medidas, indicadores y página con pestañas."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import hallazgos as H  # noqa: E402
from ergovideo.catalogo import CATALOGO, TIPOS_MEDIDA, medidas  # noqa: E402
from ergovideo.config import Config  # noqa: E402
from ergovideo.ergo import Tarea  # noqa: E402
from ergovideo.informe_puesto import render  # noqa: E402
from ergovideo.medidas import calcular  # noqa: E402
from ergovideo.sintetico import pose_sintetica  # noqa: E402

CFG = Config()


def detectar(posturas, vista=40, tarea=None, rev=None, ocultar=None):
    pose = pose_sintetica(posturas, vista=vista)
    if ocultar:
        idx, pts = ocultar
        for p in pts:
            pose.lm[idx, p, 3] = 0.1
    res = calcular(pose, CFG)
    return {h["id"]: h for h in H.detectar(res, tarea or Tarea(), rev, "v")}


def _rampa(a, b, n=4):
    return [{k: a.get(k, 0) + (b.get(k, 0) - a.get(k, 0)) * i / (n + 1) for k in set(a) | set(b)} for i in range(1, n + 1)]


def ciclo(exigente, neutro_s=4, exigente_s=4, ciclos=4, fps=10):
    out = []
    for _ in range(ciclos):
        out += [{}] * (neutro_s * fps) + _rampa({}, exigente) + [exigente] * (exigente_s * fps) + _rampa(exigente, {})
    return out


# ------------------------------------------------------------------ catálogo

def test_catalogo_completo():
    for tipo, c in CATALOGO.items():
        assert c["titulo"] and c["riesgo"] and c["medidas"], tipo
        assert all(t in TIPOS_MEDIDA for t, _ in c["medidas"]), tipo
    assert medidas("brazo_elevado")[0]["id"] == "brazo_elevado_1"


# ------------------------------------------------------------------ hallazgos posturales

def test_neutro_sin_hallazgos():
    assert detectar([{}] * 120) == {}


def test_brazo_elevado_la_mitad_del_tiempo():
    h = detectar(ciclo(dict(brazo_D=110)))
    b = h["brazo_elevado_D"]
    assert 40 <= b["porcentaje"] <= 60 and b["gravedad"] == "alta" and b["episodios"] == 4
    assert not b["minimo"] and b["captura"] if "captura" in b else True
    assert b["t_ejemplo"] is not None and "Brazo" in b["etiqueta"]


def test_tronco_y_cuello():
    h = detectar(ciclo(dict(flexion=45, cuello=35)))
    assert "tronco_flexion" in h and "cuello_flexion" in h
    assert h["tronco_flexion"]["region"] == "espalda"


def test_zona_poco_visible_da_un_minimo():
    post = ciclo(dict(brazo_D=110))
    n = len(post)
    import numpy as np
    ocultos = np.zeros(n, bool)
    ocultos[: n // 2] = True  # el brazo dch. no se ve en la primera mitad
    h = detectar(post, ocultar=(ocultos, [12, 14, 16]))
    b = h["brazo_elevado_D"]
    assert b["minimo"] and b["visible"] < 80
    assert b["porcentaje"] < 50  # sobre todo el tiempo, no sobre el visible


def test_abduccion_y_alcance_se_fusionan():
    h = detectar(ciclo(dict(abd_D=70)))
    assert not ("brazo_abducido_D" in h and "alcance_D" in h)


def test_sentado_no_genera_hallazgo_de_piernas():
    rev = {"contexto": {"postura_base": "sentado"}, "fases": []}
    h = detectar(ciclo(dict(muslo_I=90, rodilla_I=90, muslo_D=90, rodilla_D=90)), rev=rev)
    assert "piernas" not in h


# ------------------------------------------------------------------ condiciones y OWAS

def test_condiciones_de_la_tarea():
    t = Tarea(carga_kg=12.0, agarre=2, actividad=dict(estatica=True, repetitiva=True, cambios=False))
    c = {x["id"]: x for x in H.condiciones(t)}
    assert c["repetitividad"]["gravedad"] == "alta" and c["carga"]["gravedad"] == "alta"
    assert "estatica" in c and c["agarre"]["gravedad"] == "media"
    assert H.condiciones(Tarea()) == []  # lo desconocido no genera hallazgos


def test_owas_de_pie_prolongado():
    resumen = {"regiones": {"piernas": {"codigos": {2: dict(nombre="De pie", porcentaje=95.0, categoria=2),
                                                     1: dict(nombre="Sentado", porcentaje=0.0, categoria=1)}}}}
    assert [h["id"] for h in H.owas_frecuencia(resumen)] == ["de_pie"]


# ------------------------------------------------------------------ prioridad, plan e indicadores

@pytest.mark.parametrize("g,u,esperado", [("alta", 4, "Inmediata"), ("alta", 3, "Alta"), ("media", 4, "Media"), ("baja", 2, "Baja")])
def test_prioridad(g, u, esperado):
    assert H.prioridad(g, u) == esperado


def test_plan_limita_y_ordena():
    hall = [dict(id="a", tipo="brazo_elevado", gravedad="media"), dict(id="b", tipo="repetitividad", gravedad="alta")]
    p = H.plan(hall, 3)
    assert len(p) == 4 and p[0]["prioridad"] == "Alta" and p[-1]["prioridad"] == "Media"


@pytest.mark.parametrize("fn,valor,u", [(H.urgencia_reba, 1, 0), (H.urgencia_reba, 9, 3), (H.urgencia_reba, 12, 4),
                                        (H.urgencia_rula, 2, 0), (H.urgencia_rula, 4, 1), (H.urgencia_rula, 7, 4),
                                        (H.urgencia_owas, 1, 0), (H.urgencia_owas, 3, 3)])
def test_urgencias(fn, valor, u):
    assert fn(valor) == u


# ------------------------------------------------------------------ página

def _datos():
    return dict(tarea="Montaje: coge piezas y atornilla con un atornillador suspendido de un equilibrador muy largo",
                fecha="06/11/2026", video_txt="v.mp4 (30 s)", metodos=["owas", "reba", "rula"],
                indicadores=[dict(metodo="REBA", que="Peor postura", nivel="Medio", urgencia=2, accion="Es necesaria la actuación.")],
                urgencia_global=2,
                hallazgos=[dict(id="brazo_elevado_D", tipo="brazo_elevado", region="hombro", lado="D", titulo="Brazo elevado (derecho)",
                                riesgo="r", gravedad="alta", porcentaje=40.0, minimo=False, visible=100.0, episodios=4, por_minuto=8.0,
                                duracion_media_s=1.2, fases=[], t_ejemplo=3.0, evidencia=["RULA brazo ≥ 3"], video="v.mp4")],
                plan=H.plan([dict(id="brazo_elevado_D", tipo="brazo_elevado", gravedad="alta")], 2),
                series={"v.mp4": dict(t=[0.0, 1.0], reba=[1, 2], rula=[None, 3], duracion=2.0)}, fases={"v.mp4": []})


def test_pagina_con_pestanas_y_tecnico_aparte(tmp_path):
    html = render(_datos(), tmp_path, None, "<p>VALIDEZ DEL VÍDEO</p>")
    principal, tecnico = html.split('id="tecnico"')
    assert 'id="ergonomico"' in principal and "VALIDEZ DEL VÍDEO" not in principal and "VALIDEZ DEL VÍDEO" in tecnico
    assert "Medida tipo (catálogo)" in principal and "Prueba de concepto no validada" in principal
    assert "<h1>Montaje</h1>" in html  # título corto; la descripción va debajo


def test_adaptacion_sustituye_y_se_marca(tmp_path):
    ad = {"conclusion": "Hay que bajar el equilibrador.",
          "hallazgos": {"brazo_elevado_D": {"descripcion": "Coge el atornillador a la altura del hombro.",
                                            "medidas": [{"texto": "Bajar el equilibrador 20 cm.", "tipo": "ingenieria",
                                                         "sustituye": "brazo_elevado_2"}]}}}
    html = render(_datos(), tmp_path, ad, "")
    assert "Hay que bajar el equilibrador." in html and "Redactada por Claude" in html
    assert "Bajar el equilibrador 20 cm." in html and "Propuesta adaptada al puesto (Claude)" in html
    texto_sustituido = medidas("brazo_elevado")[1]["texto"]
    assert texto_sustituido not in html
    assert "Coge el atornillador a la altura del hombro." in html
