"""Las 904 celdas de las tablas frente a una copia independiente extraída de las fuentes (tests/fixtures).

Los valores esperados NO se generan con el código que se prueba: vienen de la extracción de las tablas HTML de
Ergonautas guardada en tablas_ergonautas.json.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ergovideo import tablas as T  # noqa: E402

F = json.loads((Path(__file__).parent / "fixtures" / "tablas_ergonautas.json").read_text(encoding="utf-8"))


def celdas():
    for i, (e, b) in enumerate((e, b) for e in range(1, 5) for b in range(1, 4)):
        for j, (p, c) in enumerate((p, c) for p in range(1, 8) for c in range(1, 4)):
            yield "owas6", (e, b, p, c), F["owas6"][i][j], lambda e=e, b=b, p=p, c=c: T.categoria_combinacion(e, b, p, c)
    for reg in ("espalda", "brazos", "piernas"):
        for c, fila in enumerate(F["owas7"][reg], 1):
            for k, v in enumerate(fila, 1):
                # Columna k: (10·(k−1) %, 10·k %]; se prueba el extremo superior y un valor interior.
                yield "owas7", (reg, c, k * 10), v, lambda reg=reg, c=c, k=k: T.categoria_frecuencia(reg, c, k * 10)
                yield "owas7", (reg, c, k * 10 - 5), v, lambda reg=reg, c=c, k=k: T.categoria_frecuencia(reg, c, k * 10 - 5)
    for t in range(5):
        for j in range(12):
            yield "rebaA", (t + 1, j // 4 + 1, j % 4 + 1), F["rebaA"][t][j], lambda t=t, j=j: T.reba_tabla_a(t + 1, j // 4 + 1, j % 4 + 1)
    for b in range(6):
        for j in range(6):
            yield "rebaB", (b + 1, j // 3 + 1, j % 3 + 1), F["rebaB"][b][j], lambda b=b, j=j: T.reba_tabla_b(b + 1, j // 3 + 1, j % 3 + 1)
    for a in range(12):
        for b in range(12):
            yield "rebaC", (a + 1, b + 1), F["rebaC"][a][b], lambda a=a, b=b: T.reba_tabla_c(a + 1, b + 1)
    for i in range(18):
        for j in range(8):
            yield "rulaA", (i // 3 + 1, i % 3 + 1, j // 2 + 1, j % 2 + 1), F["rulaA"][i][j], \
                lambda i=i, j=j: T.rula_tabla_a(i // 3 + 1, i % 3 + 1, j // 2 + 1, j % 2 + 1)
    for c in range(6):
        for j in range(12):
            yield "rulaB", (c + 1, j // 2 + 1, j % 2 + 1), F["rulaB"][c][j], lambda c=c, j=j: T.rula_tabla_b(c + 1, j // 2 + 1, j % 2 + 1)
    for c in range(8):
        for d in range(7):
            yield "rulaC", (c + 1, d + 1), F["rulaC"][c][d], lambda c=c, d=d: T.rula_tabla_c(c + 1, d + 1)


CELDAS = list(celdas())


def test_numero_de_celdas():
    n = sum(len(f) * len(f[0]) for k, f in F.items() if k.startswith(("owas6", "reba", "rula")))
    n += sum(len(f) * len(f[0]) for f in F["owas7"].values())
    assert n == 904


@pytest.mark.parametrize("tabla,clave,esperado,fn", CELDAS, ids=[f"{t}-{k}" for t, k, _, _ in CELDAS])
def test_celda(tabla, clave, esperado, fn):
    assert fn() == esperado


def test_owas_3143_corregida():
    # Error detectado por la auditoría del 06/11/2026 (Ergonautas tabla 6 e INSST figura 6): 3, no 4.
    assert T.categoria_combinacion(3, 1, 4, 3) == 3


def test_rula_c_limita_a_8_y_7():
    assert T.rula_tabla_c(11, 9) == T.rula_tabla_c(8, 7) == 7
    assert T.rula_tabla_c(9, 3) == T.rula_tabla_c(8, 3)


def test_reba_c_limita_a_12():
    assert T.reba_tabla_c(14, 13) == 12


@pytest.mark.parametrize("p", [0, 16])
def test_reba_nivel_rechaza_fuera_de_rango(p):
    with pytest.raises(ValueError):
        T.reba_nivel(p)


@pytest.mark.parametrize("p", [0, 8])
def test_rula_nivel_rechaza_fuera_de_rango(p):
    with pytest.raises(ValueError):
        T.rula_nivel(p)


@pytest.mark.parametrize("p,nivel", [(1, 0), (2, 1), (3, 1), (4, 2), (7, 2), (8, 3), (10, 3), (11, 4), (15, 4)])
def test_reba_niveles(p, nivel):
    assert T.reba_nivel(p)[1] == nivel


@pytest.mark.parametrize("p,nivel", [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4)])
def test_rula_niveles(p, nivel):
    assert T.rula_nivel(p)[1] == nivel


@pytest.mark.parametrize("kg,codigo", [(0, 1), (9.99, 1), (10, 1), (10.01, 2), (20, 2), (20.01, 3)])
def test_carga_owas_convencion_insst(kg, codigo):
    assert T.codigo_carga(kg) == codigo
