"""Fronteras de cada regla: a − ε, a y a + ε, con el valor esperado escrito a mano a partir del método.

Convenciones (decididas el 06/11/2026 y versionadas en reglas.CONVENCIONES):
- OWAS y REBA: lectura literal de Ergonautas.
- RULA: en la frontera, la puntuación mayor.
- Carga OWAS: INSST (10 kg → tramo 1).
Aquí se prueba sin margen de medida (intervalo de anchura cero) para aislar la regla.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import reglas as R  # noqa: E402
from ergovideo.config import Config  # noqa: E402

U = Config().umbrales
E = 0.01


def iv(x):
    return (x, x)


def uno(s):
    assert len(s) == 1, s
    return next(iter(s))


# ------------------------------------------------------------------ OWAS

@pytest.mark.parametrize("x,esperado", [(20 - E, 1), (20, 1), (20 + E, 2)])
def test_owas_espalda_flexion(x, esperado):
    assert uno(R.owas_espalda(iv(x), iv(0), iv(0), U)) == esperado


@pytest.mark.parametrize("x,esperado", [(20 - E, 1), (20, 1), (20 + E, 3)])
def test_owas_espalda_giro_y_lateral(x, esperado):
    assert uno(R.owas_espalda(iv(0), iv(x), iv(0), U)) == esperado
    assert uno(R.owas_espalda(iv(0), iv(0), iv(x), U)) == esperado


@pytest.mark.parametrize("x,esperado", [(-E, 1), (0, 2), (E, 2)])
def test_owas_brazo_al_nivel_del_hombro_cuenta_como_elevado(x, esperado):
    assert uno(R.owas_brazos(iv(x), iv(-0.5), U)) == esperado


@pytest.mark.parametrize("x,esperado", [(30 - E, False), (30, True), (30 + E, True)])
def test_owas_rodilla_flexionada_desde_30(x, esperado):
    # Ergonautas: piernas flexionadas con ángulo muslo-pantorrilla ≤ 150° (flexión ≥ 30°).
    assert uno(R.owas_rodilla_flexionada(iv(x), U)) == esperado


# ------------------------------------------------------------------ REBA (literal)

@pytest.mark.parametrize("x,esperado", [(-20 - E, 3), (-20, 2), (-E, 2), (0, 1), (E, 2), (20, 2), (20 + E, 3),
                                        (60, 3), (60 + E, 4)])
def test_reba_tronco(x, esperado):
    assert uno(R.reba_tronco_base(iv(x))) == esperado


@pytest.mark.parametrize("x,esperado", [(-E, 2), (0, 1), (20, 1), (20 + E, 2)])
def test_reba_cuello(x, esperado):
    assert uno(R.reba_cuello_base(iv(x))) == esperado


@pytest.mark.parametrize("x,esperado", [(-20 - E, 2), (-20, 1), (20, 1), (20 + E, 2), (45, 2), (45 + E, 3), (90, 3), (90 + E, 4)])
def test_reba_brazo(x, esperado):
    assert uno(R.reba_brazo_base(iv(x))) == esperado


@pytest.mark.parametrize("x,esperado", [(60 - E, 2), (60, 1), (100, 1), (100 + E, 2)])
def test_reba_antebrazo(x, esperado):
    assert uno(R.reba_antebrazo(iv(x))) == esperado


@pytest.mark.parametrize("x,esperado", [(15, 1), (15 + E, 2)])
def test_reba_muneca(x, esperado):
    assert uno(R.reba_muneca(iv(x), None, False)) == esperado


@pytest.mark.parametrize("x,sentado,esperado", [(30 - E, False, 0), (30, False, 1), (60, False, 1), (60 + E, False, 2),
                                                (45, True, 1), (60 + E, True, 0)])
def test_reba_rodillas(x, sentado, esperado):
    # Lectura literal: +2 «salvo postura sedente»; el +1 de 30–60° se mantiene sentado.
    assert uno(R.reba_rodillas(iv(x), frozenset({sentado}))) == esperado


@pytest.mark.parametrize("kg,esperado", [(5 - E, 0), (5, 1), (10, 1), (10 + E, 2)])
def test_reba_carga(kg, esperado):
    assert uno(R.reba_carga(kg, False)) == esperado


# ------------------------------------------------------------------ RULA (en la frontera, la mayor)

@pytest.mark.parametrize("x,esperado", [(-20 - E, 2), (-20, 2), (-20 + E, 1), (20 - E, 1), (20, 2), (45 - E, 2), (45, 3),
                                        (90 - E, 3), (90, 4)])
def test_rula_brazo(x, esperado):
    assert uno(R.rula_brazo_base(iv(x))) == esperado


@pytest.mark.parametrize("x,esperado", [(60, 2), (60 + E, 1), (100 - E, 1), (100, 2)])
def test_rula_antebrazo(x, esperado):
    assert uno(R.rula_antebrazo(iv(x), iv(1.0), U)) == esperado


@pytest.mark.parametrize("x,esperado", [(0, 1), (E, 2), (15 - E, 2), (15, 3)])
def test_rula_muneca(x, esperado):
    assert uno(R.rula_muneca(iv(x), None, False)) == esperado


@pytest.mark.parametrize("x,esperado", [(-E, 4), (0, 1), (10 - E, 1), (10, 2), (20 - E, 2), (20, 3)])
def test_rula_cuello(x, esperado):
    assert uno(R.rula_cuello(iv(x), False, False)) == esperado


@pytest.mark.parametrize("x,esperado", [(0, 1), (E, 2), (20 - E, 2), (20, 3), (60 - E, 3), (60, 4)])
def test_rula_tronco(x, esperado):
    assert uno(R.rula_tronco(iv(x), iv(0), iv(0), U)) == esperado


@pytest.mark.parametrize("x,esperado", [(-E, 1), (0, 1), (E, 0), (2 - E, 0), (2, 1)])
def test_rula_antebrazo_linea_media(x, esperado):
    assert uno(R.rula_antebrazo(iv(80), iv(x), U)) - 1 == esperado


@pytest.mark.parametrize("kg,sost,esperado", [(2 - E, False, 0), (2, False, 1), (10 - E, False, 1), (10, False, 2),
                                              (10 - E, True, 2), (10, True, 3)])
def test_rula_fuerza(kg, sost, esperado):
    assert uno(R.rula_fuerza(kg, {"estatica": sost, "repetitiva": False}, False)) == esperado
