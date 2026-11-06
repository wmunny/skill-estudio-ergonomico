"""Pruebas de la clasificación OWAS con posturas sintéticas, de los filtros y del muestreo."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import tablas  # noqa: E402
from ergovideo.clasificar import clasificar, codigo_piernas  # noqa: E402
from ergovideo.config import Config, Filtros  # noqa: E402
from ergovideo.filtros import filtrar_serie  # noqa: E402
from ergovideo.medidas import calcular, medidas_fotograma  # noqa: E402
from ergovideo.muestreo import observar, resumir, wilson  # noqa: E402
from ergovideo.sintetico import fotograma, pose_sintetica  # noqa: E402

CFG = Config()
CFG.muestreo.sin_margen = True  # la clasificación se prueba sin margen; el margen se prueba aparte
U = CFG.umbrales
VISTAS = [0, 45, 90]


def obs(vista=0, kg=5.0, base="auto", ocultar=(), cfg=CFG, **postura):
    p2, w, usable = fotograma(vista=vista, **postura)
    usable[list(ocultar)] = False
    m = medidas_fotograma(p2, w, usable, cfg)
    m["velocidad"] = 0.0
    return clasificar(m, cfg, kg, base, vista, m["modo"])


def codigos(vista=0, **postura):
    c = obs(vista, **postura)
    return c["espalda"], c["brazos"], c["piernas"]


# ------------------------------------------------------------------ posturas sintéticas

@pytest.mark.parametrize("vista", VISTAS)
def test_de_pie_neutro(vista):
    assert codigos(vista) == (1, 1, 2)


@pytest.mark.parametrize("vista", VISTAS)
@pytest.mark.parametrize("flexion,esperado", [(10, 1), (35, 2), (70, 2), (-30, 2)])
def test_espalda_flexion(vista, flexion, esperado):
    assert codigos(vista, flexion=flexion)[0] == esperado


@pytest.mark.parametrize("vista", VISTAS)
def test_espalda_giro_e_inclinacion(vista):
    assert codigos(vista, giro=35)[0] == 3
    assert codigos(vista, giro=10)[0] == 1
    assert codigos(vista, lateral=30)[0] == 3
    assert codigos(vista, flexion=45, giro=35)[0] == 4


@pytest.mark.parametrize("vista", VISTAS)
@pytest.mark.parametrize("bi,bd,esperado", [(30, 40, 1), (120, 20, 2), (20, 160, 2), (110, 170, 3)])
def test_brazos(vista, bi, bd, esperado):
    assert codigos(vista, brazo_I=bi, brazo_D=bd)[1] == esperado


@pytest.mark.parametrize("vista", VISTAS)
def test_brazos_con_tronco_doblado(vista):
    assert codigos(vista, flexion=80)[1] == 1


@pytest.mark.parametrize("vista", VISTAS)
def test_piernas(vista):
    assert codigos(vista, muslo_I=90, rodilla_I=90, muslo_D=90, rodilla_D=90)[2] == 1          # sentado
    assert codigos(vista, muslo_I=40, rodilla_I=60)[2] == 3                                     # una flexionada
    assert codigos(vista, muslo_I=45, rodilla_I=90, muslo_D=45, rodilla_D=90)[2] == 4           # cuclillas
    assert codigos(vista, muslo_I=105, rodilla_I=140, muslo_D=105, rodilla_D=140)[2] in (4, 5)  # cuclilla profunda
    assert codigos(vista, muslo_I=40, rodilla_I=50, muslo_D=60, rodilla_D=110)[2] == 5          # desequilibrado
    assert codigos(vista, muslo_I=30, rodilla_I=60, levantar_I=0.2)[2] == 3                     # pie en el aire
    assert codigos(vista, muslo_I=30, rodilla_I=60, levantar_I=0.2, muslo_D=40, rodilla_D=60)[2] == 5
    assert codigos(vista, rodilla_I=90, rodilla_D=90)[2] == 6                                   # arrodillado


def test_postura_base_de_pie_desactiva_sentado():
    assert obs(0, base="de_pie", muslo_I=90, rodilla_I=90, muslo_D=90, rodilla_D=90)["piernas"] in (4, 5)


def test_categoria_combinada():
    # Espalda 2, un brazo elevado 2, cuclillas 4, 15 kg (2) → tabla 6: 4.
    c = obs(45, kg=15.0, flexion=45, brazo_I=120, muslo_I=45, rodilla_I=90, muslo_D=45, rodilla_D=90)
    assert (c["espalda"], c["brazos"], c["piernas"], c["carga"], c["categoria"]) == (2, 2, 4, 2, 4)


# ------------------------------------------------------------------ desconocidos: nunca el valor favorable

def test_brazo_oculto_no_cuenta_como_bajo():
    c = obs(90, brazo_I=0, ocultar=(12, 14, 16))  # brazo dch. tapado
    assert c["brazos"] is None and c["brazos_posibles"] == [1, 2]
    assert "un_brazo_no_visible" in c["notas"]


def test_pierna_oculta_no_se_copia():
    c = obs(90, muslo_I=40, rodilla_I=60, muslo_D=40, rodilla_D=60, ocultar=(24, 26, 28))
    assert c["piernas"] is None and len(c["piernas_posibles"]) > 1


def test_giro_no_medible_da_rango():
    c = obs(45, flexion=30, ocultar=(23,))
    assert c["espalda"] is None and c["espalda_posibles"] == [2, 4]


def test_carga_no_declarada_da_rango():
    c = obs(0, kg=None)
    assert c["carga"] is None and c["carga_posibles"] == [1, 2, 3]
    assert c["categoria"] is None and c["categoria_posibles"] == [1]  # de pie neutro: 1 con cualquier carga


def test_margen_cruza_umbral():
    cfg = Config()
    c = obs(45, cfg=cfg, flexion=18)
    assert c["espalda"] == 1 and c["espalda_posibles"] == [1, 2]


def test_andando():
    m = dict(rodilla_I=5.0, rodilla_D=20.0, velocidad=1.5)
    assert codigo_piernas(m, U)[0] == 7


# ------------------------------------------------------------------ filtros mecánicos

def test_filtro_rango_y_saltos():
    t = np.arange(50) / 10
    v = np.full(50, 20.0)
    v[10] = 200
    v[30:32] = 90
    cuenta = {}
    out = filtrar_serie(v, t, (0, 130), 300, Filtros(), cuenta)
    assert np.isnan(out[10]) or out[10] == pytest.approx(20)
    assert np.all(np.isnan(out[30:32]) | (np.abs(out[30:32] - 20) < 1e-6))
    assert cuenta["rango"] == 1


def test_filtro_rellena_solo_huecos_cortos():
    t = np.arange(60) / 10
    v = np.linspace(0, 59, 60)
    v[10:12] = np.nan
    v[30:45] = np.nan
    out = filtrar_serie(v, t, (0, 100), 300, Filtros())
    assert not np.isnan(out[10:12]).any()
    assert np.isnan(out[30:45]).all()


def test_interpolados_marcados():
    pose = pose_sintetica([{} for _ in range(40)], vista=30)
    pose.lm[20, :, 3] = 0.0  # un fotograma sin datos: se rellena y se marca como interpolado
    res = calcular(pose, CFG)
    assert res["interpolado"]["tronco_flex"][20] and not res["interpolado"]["tronco_flex"][10]


def test_wilson():
    lo, hi = wilson(0.5, 100, 1.96)
    assert 0.39 < lo < 0.41 and 0.59 < hi < 0.61


# ------------------------------------------------------------------ de punta a punta (sin MediaPipe)

def _tarea(segundos=60, fps=10):
    """Ciclo de 10 s: 6 s de pie neutro, 4 s doblado con un brazo elevado."""
    return [({} if (i / fps) % 10 < 6 else dict(flexion=50, brazo_D=120)) for i in range(segundos * fps)]


def test_pipeline_sintetico():
    pose = pose_sintetica(_tarea(), vista=40, ruido=0.002)
    res = calcular(pose, CFG)
    fuentes = [dict(nombre="sint", res=res, duracion=pose.duracion)]
    o = observar(fuentes, CFG, lambda t, v=None: 5.0)
    r = resumir(o, fuentes, CFG)
    esp = r["regiones"]["espalda"]["codigos"]
    assert r["n_observaciones"] == 60
    assert 30 <= esp[2]["porcentaje"] <= 50
    assert esp[2]["rango"][0] <= esp[2]["porcentaje"] <= esp[2]["rango"][1]
    assert 30 <= r["regiones"]["brazos"]["codigos"][2]["porcentaje"] <= 50
    assert any("20–40 min" in a for a in r["avisos"])
    assert r["combinaciones"]["categoria_max"] == tablas.categoria_combinacion(2, 2, 2, 1)


def test_observacion_usa_un_fotograma_real():
    pose = pose_sintetica(_tarea(20), vista=40)
    res = calcular(pose, CFG)
    o = observar([dict(nombre="s", res=res, duracion=pose.duracion)], CFG, lambda t, v=None: 0.0)
    for x in o:
        i = x["indice"]["s"]
        assert x["medidas"]["tronco_flex"] == pytest.approx(res["series"]["tronco_flex"][i], nan_ok=True)


def test_salto_imposible_no_cambia_codigo():
    pose = pose_sintetica([{} for _ in range(100)], vista=30)
    from ergovideo.sintetico import esqueleto, proyectar
    pose.lm[50], pose.wlm[50] = proyectar(esqueleto(flexion=70), 30)
    res = calcular(pose, CFG)
    assert np.nanmax(res["series"]["tronco_flex"]) < 20


def test_mejor_camara_elige_la_que_ve():
    post = _tarea(30)
    a = pose_sintetica(post, vista=40)
    b = pose_sintetica(post, vista=40)
    b.lm[:, [11, 13, 15, 23, 25, 27], 3] = 0.1
    fuentes = [dict(nombre="A", res=calcular(a, CFG), duracion=a.duracion, desfase=0.0),
               dict(nombre="B", res=calcular(b, CFG), duracion=b.duracion, desfase=0.0)]
    o = observar(fuentes, CFG, lambda t, v=None: 0.0, modo="mejor-camara")
    r = resumir(o, fuentes, CFG)
    assert r["camaras"]["brazos"].get("A", 0) > 90


def test_informe_sintetico(tmp_path):
    from ergovideo import ergo, grabacion, informe
    from ergovideo.config import MEDIDAS
    pose = pose_sintetica(_tarea(), vista=40)
    res = calcular(pose, CFG)
    fuentes = [dict(nombre="sint", res=res, duracion=pose.duracion)]
    o = observar(fuentes, CFG, lambda t, v=None: 15.0)
    r = resumir(o, fuentes, CFG)
    t = ergo.Tarea(carga_kg=15.0)
    fs = ergo.serie(res, CFG, t)
    d = dict(reba=ergo.peor_postura(fs, "reba"), rula={s: ergo.peor_postura(fs, "rula", s) for s in "ID"})
    d["reba_val"] = ergo.validar_pico(d["reba"], "reba")
    d["rula_val"] = {s: ergo.validar_pico(d["rula"][s], "rula") for s in "ID"}
    d["rula_lado"] = ergo.resumen_rula(d["rula"])
    ctx = dict(resumen=r, diagnosticos=[grabacion.diagnostico(pose, res)], imagenes={}, capturas=[], videos=[], umbrales=U,
               ventana_s=CFG.muestreo.ventana_s, nombres_medidas={k: v["nombre"] for k, v in MEDIDAS.items()},
               nombres_fuentes=["sint"], metodos=["owas", "reba", "rula"], tarea=t, ergo={"sint": d},
               args=dict(carga_texto="15 kg", turno_h=8, modo_texto="un solo vídeo", modo="combinar",
                         postura_base="auto", angulos="auto"))
    md = informe.markdown(ctx)
    assert md.count("Demostración no validada") == 2
    assert "Min/turno" in md and "20–40 min" in md and "Datos no declarados" in md
    assert "Postura normal" in md and "Sin riesgo" not in md
    html = informe.a_html(md, tmp_path)
    assert "<table>" in html
