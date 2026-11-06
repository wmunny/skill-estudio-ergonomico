r"""Genera el informe de revisión de los métodos OWAS, REBA y RULA a partir del propio código.

Las tablas se construyen celda a celda llamando a las mismas funciones que puntúan, y las comprobaciones de
umbral pasan valores de ángulo por las reglas reales. Así el revisor ve lo que se ejecuta, no una descripción.

Uso: .venv\Scripts\python scripts\informe_revision.py [--salida docs]
Escribe REVISION_METODOS.md y revision_metodos.html (página autocontenida).
"""

from __future__ import annotations

import argparse
import html
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ergovideo import reglas as R  # noqa: E402
from ergovideo import tablas as T  # noqa: E402
from ergovideo.clasificar import codigo_piernas  # noqa: E402
from ergovideo.config import FACTOR_FRONTAL, MARGENES, MEDIDAS, Config  # noqa: E402
from ergovideo.ergo import Tarea, reba, rula  # noqa: E402
from ergovideo.reglas import CONVENCIONES  # noqa: E402

CFG = Config()
CFG.muestreo.sin_margen = True  # las comprobaciones aíslan la regla
U = CFG.umbrales
F = CFG.filtros
M = CFG.muestreo


# ------------------------------------------------------------------ bloques (se pintan en Markdown y en HTML)

class Doc:
    def __init__(self):
        self.b = []

    def h(self, n, t, ancla=None):
        self.b.append(("h", n, t, ancla))

    def p(self, t):
        self.b.append(("p", t))

    def ul(self, items):
        self.b.append(("ul", items))

    def nota(self, t):
        self.b.append(("nota", t))

    def tabla(self, cab, filas, calor=False, ancha=False, pie=None):
        self.b.append(("tabla", cab, filas, calor, ancha, pie))

    # -------------------------------------------------- Markdown
    def md(self) -> str:
        out = []
        for blk in self.b:
            k = blk[0]
            if k == "h":
                out += ["#" * blk[1] + " " + blk[2], ""]
            elif k == "p":
                out += [blk[1], ""]
            elif k == "nota":
                out += ["> " + blk[1], ""]
            elif k == "ul":
                out += [f"- {x}" for x in blk[1]] + [""]
            elif k == "tabla":
                cab, filas, pie = blk[1], blk[2], blk[5]
                out.append("| " + " | ".join(map(str, cab)) + " |")
                out.append("|" + "---|" * len(cab))
                out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in f) + " |" for f in filas]
                out.append("")
                if pie:
                    out += [f"*{pie}*", ""]
        return "\n".join(out)

    # -------------------------------------------------- HTML
    def html(self) -> str:
        out, toc = [], []
        for blk in self.b:
            k = blk[0]
            if k == "h":
                n, t, ancla = blk[1], blk[2], blk[3]
                a = f' id="{ancla}"' if ancla else ""
                if n == 2 and ancla:
                    toc.append(f'<a href="#{ancla}">{_inl(t)}</a>')
                out.append(f"<h{n}{a}>{_inl(t)}</h{n}>")
            elif k == "p":
                out.append(f"<p>{_inl(blk[1])}</p>")
            elif k == "nota":
                out.append(f'<aside class="nota">{_inl(blk[1])}</aside>')
            elif k == "ul":
                out.append("<ul>" + "".join(f"<li>{_inl(x)}</li>" for x in blk[1]) + "</ul>")
            elif k == "tabla":
                cab, filas, calor, ancha, pie = blk[1:]
                th = "".join(f"<th>{_inl(str(c))}</th>" for c in cab)
                trs = []
                for f in filas:
                    tds = []
                    for j, c in enumerate(f):
                        cls = ""
                        if calor and j > 0 and str(c).isdigit():
                            cls = f' class="s s{min(int(c), 12)}"'
                        tds.append(f"<td{cls}>{_inl(str(c))}</td>")
                    trs.append("<tr>" + "".join(tds) + "</tr>")
                clase = "tabla ancha" if ancha else "tabla"
                out.append(f'<div class="{clase}"><table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>')
                if pie:
                    out.append(f'<p class="pie">{_inl(pie)}</p>')
        return "\n".join(out), toc


def _inl(t: str) -> str:
    import re
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def r_(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        v = list(v)
        return str(v[0]) if min(v) == max(v) else f"{min(v)}–{max(v)}"
    return str(v)


def g(x) -> str:
    """Número con coma decimal."""
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return str(x).replace(".", ",")


def neutro(**kw) -> dict:
    m = dict(tronco_flex=0.0, tronco_sag=0.0, tronco_lat=0.0, tronco_giro=0.0, cuello=0.0,
             brazo_alt_I=-0.6, brazo_alt_D=-0.6, brazo_flex_I=0.0, brazo_flex_D=0.0, brazo_abd_I=0.0, brazo_abd_D=0.0,
             codo_I=0.0, codo_D=0.0, muneca_I=0.0, muneca_D=0.0, antebrazo_lat_I=1.0, antebrazo_lat_D=1.0,
             rodilla_I=0.0, rodilla_D=0.0, muslo_I=0.0, muslo_D=0.0, pierna_I=0.0, pierna_D=0.0, tobillos=0.0,
             velocidad=0.0)
    m.update(kw)
    return m


def tarea(**kw) -> Tarea:
    """Todo declarado (neutro, sin carga ni actividad) salvo lo indicado."""
    base = dict(carga_kg=0.0, fuerza_brusca=False, agarre=0, actividad=dict(estatica=False, repetitiva=False, cambios=False),
                muneca="neutra", muneca_desviada=False, muneca_giro_extremo=False, hombro_elevado=False,
                brazo_apoyado=False, brazo_rotado=False, cuello_girado=False, cuello_inclinado=False, apoyo_piernas=None)
    base.update(kw)
    return Tarea(**base)


def puntua(m: dict, t: Tarea | None = None, lado="I"):
    t = t or tarea()
    return reba(m, CFG, t, 45.0, "3d"), rula(m, CFG, t, lado, 45.0, "3d")


def iv(x):
    return (x, x)


def s_(conj) -> str:
    return r_(sorted(conj))


ESTADO_P = {"resuelto": "Resuelto", "pendiente": "Pendiente del experto", "provisional": "Provisional"}


def construir() -> Doc:
    d = Doc()
    d.h(1, "Revisión de OWAS, REBA y RULA")
    d.p(f"Skill *estudio-ergonomico-video* · documento generado el {date.today():%d/%m/%Y} a partir del código "
        "(`scripts/informe_revision.py`). Versión 2: incorpora la auditoría documental del 06/11/2026 y las decisiones "
        "del usuario sobre fronteras, carga, datos desconocidos y margen de medida.")
    d.nota("**Demostración no validada.** Este documento describe lo que hace el programa para que un experto "
           "compruebe que las tablas y las reglas son correctas. No es una evaluación de riesgos.")

    # 0 -----------------------------------------------------------------
    d.h(2, "Cambios desde la versión 1", "cambios")
    d.tabla(["Hallazgo de la auditoría", "Cambio", "Estado"], [
        ["01 · OWAS 3143 debía ser 3", "Corregida. Las 904 celdas se prueban contra una copia extraída de Ergonautas "
         "(`tests/fixtures/tablas_ergonautas.json`), no contra el propio código: 904 coincidencias.", "Resuelto"],
        ["02 · Rodilla a 30° y brazo al nivel del hombro", "Pierna flexionada si flexión ≥ 30°; brazo elevado si codo o mano "
         "están al nivel del hombro o por encima. 10 kg en OWAS: tramo 1 (convención INSST).", "Resuelto"],
        ["03 · Cuello en RULA: giro e inclinación", "Dos entradas separadas (`--cuello-girado`, `--cuello-inclinado`): +1 y +1 "
         "en RULA; +1 único en REBA.", "Resuelto"],
        ["04 · REBA: rotación de brazo y actividad", "Nueva entrada `--brazo-rotado`; la torsión de muñeca va en "
         "`--muneca-desviada` (REBA: torsión o desviación). Tres indicadores de actividad acumulables (hasta +3), solo "
         "declarados; andar no activa «repetitiva».", "Resuelto"],
        ["05 · Tolerancias de 5° dentro de las reglas", "Eliminadas. Las reglas aplican los umbrales del método; la "
         "incertidumbre va aparte como margen de medida (sección 2.1) y produce rangos.", "Resuelto"],
        ["06 · Fronteras de RULA", "En la frontera, la puntuación mayor (decisión del usuario, según las notas de McAtamney "
         "2024 citadas por la auditoría). REBA y OWAS: lectura literal de Ergonautas.", "Resuelto (falta verificar el documento de 2024)"],
        ["07 · Piernas de REBA/RULA", "Apoyo propio de cada método con rango donde no se puede saber (arrodillado, sentado "
         "sin ver los pies, andando) y entrada `--apoyo-piernas`. Sentado: solo se suprime el +2 (lectura literal).", "Provisional"],
        ["08 · Desconocido ≠ favorable", "Tres estados (sí, no, desconocido) en todo lo declarable; lo desconocido o no "
         "visible se recorre entero y la puntuación sale como rango. Muñeca y desviación desconocidas: REBA 1–3, RULA "
         "1–4.", "Resuelto"],
        ["09 · Lado de RULA", "Se evalúan los dos lados y se resume con el peor, sin mezclar segmentos. Se retira la cita "
         "a la NTP 601 (es de REBA).", "Resuelto"],
        ["10 · Caso RULA neutro", "Corregido: brazos colgando con codo 0° → C 2, D 1, RULA 2. Los casos completos fijan "
         "ahora todas las entradas.", "Resuelto"],
        ["Captura y estadística", "OWAS usa un fotograma real por observación; «% del tiempo observable»; intervalo "
         "«aproximado» con muestra efectiva por código; pico breve fiable además del sostenido; valores interpolados "
         "marcados; semáforos como validez técnica provisional.", "Resuelto en el cálculo; validación pendiente"],
    ])

    # 1 -----------------------------------------------------------------
    d.h(2, "Cómo se calcula: reglas en Python, no en el modelo de lenguaje", "principio")
    d.p("Toda la valoración es determinista. El modelo de lenguaje (Claude) solo pregunta los datos de la tarea, lanza "
        "los scripts y explica el informe; no mide, no clasifica y no puntúa.")
    d.tabla(["Paso", "Qué hace", "Dónde"], [
        ["1. Pose", "MediaPipe Pose Landmarker: 33 puntos 2D y 3D por fotograma (10 por segundo)", "`pose.py`"],
        ["2. Medidas", "Ángulos con fórmulas geométricas (sección 2)", "`medidas.py`"],
        ["3. Filtros", "Longitud de huesos, coherencia 2D–3D, rango, atípicos, saltos; marca lo interpolado", "`filtros.py`"],
        ["4. Intervalos", "Cada medida pasa a «valor ± margen» o «desconocido» (sección 2.1)", "`config.py`"],
        ["5. Reglas por elemento", "Cada regla devuelve el conjunto de puntuaciones posibles en el intervalo", "`reglas.py`"],
        ["6. Tablas", "Se consultan con todas las combinaciones posibles → rango [mínimo, máximo]", "`tablas.py`, `ergo.py`, `clasificar.py`"],
        ["7. Validación", "Estado del rango y semáforo de validez técnica (sección 6)", "`ergo.py`, `muestreo.py`"],
    ])
    d.p("**Pruebas automáticas:** 1.254 pruebas. Las 904 celdas de las tablas se comparan con la copia independiente; "
        "cada umbral se prueba en a − ε, a y a + ε con el valor esperado escrito a mano; además, las pruebas de "
        "aceptación de la auditoría y posturas sintéticas calculadas a mano en tres vistas.")

    # 2 -----------------------------------------------------------------
    d.h(2, "Medidas", "medidas")
    d.p("Puntos de MediaPipe: 0 nariz, 7/8 orejas, 11/12 hombros, 13/14 codos, 15/16 muñecas, 17/18 meñiques, 19/20 "
        "índices, 23/24 caderas, 25/26 rodillas, 27/28 tobillos (impar = izquierdo del trabajador). «2D» = plano de la "
        "imagen; «3D» = coordenadas *world* de MediaPipe en metros (profundidad estimada).")
    d.p(f"**2D o 3D por fotograma:** a partir de {g(F.vista_lateral)}° de giro respecto a la cámara (de perfil) se usa 2D "
        "en tronco, cuello, brazo y rodilla; por debajo, 3D. Torsión, inclinación lateral, abducción, codo y muñeca: "
        "siempre 3D.")
    d.tabla(["Medida", "Definición", "Cálculo", "Se usa en"], [
        ["Tronco", "Ángulo hombros−caderas con la vertical en el plano sagital; + flexión, − extensión. OWAS usa su "
         "magnitud (rango del filtro 0–130°); REBA/RULA, el valor con signo (−60 a 130°)", "2D de perfil / 3D", "OWAS, REBA, RULA"],
        ["Inclinación lateral / torsión", "Eje del tronco fuera del plano sagital / línea de hombros frente a caderas en el horizontal", "3D", "OWAS, REBA, RULA"],
        ["Cuello", "Orejas − hombros respecto al eje del tronco (indicador geométrico, no anatómico)", "2D / 3D", "REBA, RULA"],
        ["Brazo", "Codo − hombro respecto al tronco; − si va detrás y por debajo de 90°; abducción fuera del plano sagital", "2D / 3D", "REBA, RULA"],
        ["Codo", "180° − ángulo interno", "3D", "REBA, RULA"],
        ["Muñeca (estimada)", "Ángulo antebrazo–mano con índice y meñique; mezcla flexión y desviación", "3D", "REBA, RULA"],
        ["Antebrazo/línea media", "Posición lateral de la muñeca en semianchos de hombros", "3D", "RULA"],
        ["Altura del brazo", "Codo o muñeca (el más alto) sobre el hombro, en longitudes de tronco", "2D", "OWAS"],
        ["Rodilla, muslo, pantorrilla, tobillos, velocidad", "Flexión; ángulos con la vertical; diferencia de altura; desplazamiento de la cadera", "2D / 3D", "OWAS, apoyo REBA/RULA"],
    ])
    d.h(3, "2.1 Margen de medida (provisional)")
    d.p("Decisión del usuario: márgenes provisionales por zona hasta calibrarlos con vídeos anotados. Si «valor ± margen» "
        "cruza un umbral, la regla devuelve las dos puntuaciones. De frente o de espaldas (3D con giro < 25°) el margen se "
        f"multiplica por {g(FACTOR_FRONTAL)}. Las reglas no llevan tolerancias propias.")
    d.tabla(["Medida", "Margen"], [[k.replace("_", " "), g(v)] for k, v in MARGENES.items()])

    # 3 OWAS -------------------------------------------------------------
    d.h(2, "OWAS", "owas")
    d.p("Tablas: Ergonautas (UPV), [método OWAS](https://www.ergonautas.upv.es/metodos/owas/owas-ayuda.php). Original: "
        "Karhu, Kansi y Kuorinka (1977). " + CONVENCIONES["OWAS"])
    d.h(3, "3.1 Codificación")
    d.tabla(["Región", "Código", "Descripción", "Regla del programa", "Origen"], [
        ["Espalda", "2", T.ESPALDA[2], f"|flexión| > {g(U.espalda_flexion)}°", "Método"],
        ["Espalda", "3", T.ESPALDA[3], f"torsión > {g(U.espalda_giro)}° o inclinación lateral > {g(U.espalda_lateral)}°", "Método"],
        ["Espalda", "4", T.ESPALDA[4], "2 y 3 a la vez", "Método"],
        ["Brazos", "1–3", "1 + brazos elevados", "Elevado si codo o muñeca ≥ nivel del hombro", "Método (INSST: «al nivel o por encima»)"],
        ["Piernas", "2 · 3 · 4 · 5", "De pie", "Flexionada si flexión ≥ 30°; 5 si las dos flexionadas y difieren > "
         f"{g(U.asimetria_rodillas)}° o se apoya en una flexionada con el otro pie levantado (> {g(U.pie_levantado_m * 100)} cm)",
         "Método + heurística propia (peso)"],
        ["Piernas", "1 · 6 · 7", "Sentado · arrodillado · andando", f"Sentado: muslo ≥ {g(U.sentado_muslo)}°, pantorrilla ≤ "
         f"{g(U.sentado_pierna)}°, rodillas ≤ 120°; arrodillado: pantorrilla > {g(U.arrodillado_pierna)}° y rodilla > 60°; "
         f"andando: > {g(U.andando_velocidad)} troncos/s", "Heurística propia, provisional"],
        ["Carga", "1–3", T.CONVENCION_CARGA_OWAS, "Declarada; sin declarar → 1–3", "Método (convención INSST)"],
    ])
    d.p("**Lo que no se ve** (un brazo, una pierna, la torsión, la carga) ya no se rellena: la observación tiene un código "
        "nominal desconocido y un conjunto de códigos posibles que entra en los rangos.")
    d.h(3, "3.2 Tabla 6: categoría por combinación")
    cab = ["Espalda · brazos"] + [f"P{p}·C{c}" for p in range(1, 8) for c in range(1, 4)]
    d.tabla(cab, [[f"E{e} · B{b}"] + [T.categoria_combinacion(e, b, p, c) for p in range(1, 8) for c in range(1, 4)]
                  for e in range(1, 5) for b in range(1, 4)], calor=True, ancha=True,
            pie="E = espalda, B = brazos, P = piernas, C = carga. Celda E3·B1·P4·C3 corregida a 3.")
    d.h(3, "3.3 Tabla 7: categoría por frecuencia")
    filas = []
    for reg, nombres in (("espalda", T.ESPALDA), ("brazos", T.BRAZOS), ("piernas", T.PIERNAS)):
        for c, n in nombres.items():
            filas.append([f"{reg.capitalize()} {c} · {n}"] + [T.categoria_frecuencia(reg, c, k * 10 - 5) for k in range(1, 11)])
    d.tabla(["Código"] + [f"≤ {k * 10} %" for k in range(1, 11)], filas, calor=True, ancha=True)
    d.h(3, "3.4 Categorías de acción")
    d.tabla(["Categoría", "Carga postural", "Acción"], [[k, v[0], v[1]] for k, v in T.CATEGORIAS.items()],
            pie="Descripción limitada a la carga postural evaluada; una categoría 1 no acredita la ausencia de otros riesgos.")
    d.h(3, "3.5 Muestreo y estadística")
    d.ul([
        f"Una observación cada {g(M.intervalo_s)} s con **un fotograma real** (el más cercano con más regiones medidas, dentro "
        f"de ±{g(M.ventana_s / 2)} s).",
        "**% nominal del tiempo observable:** sobre las observaciones con código nominal conocido.",
        "**Intervalo aproximado:** Wilson con una muestra efectiva por código (duración con datos / 2 × tiempo de "
        "decorrelación de la serie indicadora de ese código). Su cobertura del 95 % no está verificada.",
        "**Rango:** % mínimo (observaciones donde el código es seguro) y máximo (donde es posible) sobre todas las "
        "observaciones, con margen y datos que faltan.",
    ])
    d.h(3, "3.6 Comprobaciones de frontera (reglas reales, sin margen)")
    filas = []
    for x in (19.99, 20.0, 20.01):
        filas.append(["Espalda", f"flexión {g(x)}°", s_(R.owas_espalda(iv(x), iv(0), iv(0), U))])
    for x in (20.0, 20.01):
        filas.append(["Espalda", f"torsión {g(x)}°", s_(R.owas_espalda(iv(0), iv(x), iv(0), U))])
    for x in (-0.01, 0.0):
        filas.append(["Brazos", f"altura {g(x)} troncos (un brazo)", s_(R.owas_brazos(iv(x), iv(-0.5), U))])
    for x in (29.99, 30.0):
        filas.append(["Pierna", f"flexión {g(x)}°", "flexionada" if True in R.owas_rodilla_flexionada(iv(x), U) else "recta"])
    filas.append(["Piernas", "rodillas 30° y 30°, de pie, pies a la misma altura",
                  codigo_piernas(neutro(rodilla_I=30.0, rodilla_D=30.0, muslo_I=15.0, muslo_D=15.0, pierna_I=15.0, pierna_D=15.0), U)[0]])
    for kg in (10.0, 10.01, 20.0, 20.01):
        filas.append(["Carga", f"{g(kg)} kg", T.codigo_carga(kg)])
    filas.append(["Brazo izq. oculto", "dch. bajo", s_(R.owas_brazos(None, iv(-0.5), U))])
    filas.append(["Torsión no medible", "flexión 30°", s_(R.owas_espalda(iv(30), None, iv(0), U))])
    d.tabla(["Región", "Entrada", "Resultado del programa"], filas)

    # 4 REBA --------------------------------------------------------------
    d.h(2, "REBA", "reba")
    d.p("Tablas: Ergonautas (UPV), [método REBA](https://www.ergonautas.upv.es/metodos/reba/reba-ayuda.php), y NTP 601. "
        "Original: Hignett y McAtamney (2000). " + CONVENCIONES["REBA"])
    d.h(3, "4.1 Elementos")
    d.tabla(["Elemento", "Método", "Regla del programa", "Si se desconoce"], [
        ["Tronco", "1 erguido · 2 flex./ext. 0–20° · 3 flex. 20–60° o ext. > 20° · 4 > 60°", "0° → 1; −20° a 20° → 2; < −20° o ≤ 60° → 3; > 60° → 4", "1–4"],
        ["Tronco +1", "Inclinación lateral o rotación", f"Presente si > {g(U.giro_presente)}° (criterio de detección provisional)", "+0 o +1"],
        ["Cuello", "1 flexión 0–20° · 2 > 20° o extensión", "0° a 20° → 1; resto (incluida cualquier extensión) → 2", "1–2"],
        ["Cuello +1", "Rotado o inclinado", "Declarados por separado; +1 si cualquiera", "+0 o +1"],
        ["Piernas", "1 sentado, andando o bilateral · 2 unilateral o inestable", "Apoyo declarado o desde OWAS: 3, 5 → 2; 6 → 1–2; resto → 1", "1–2"],
        ["Rodillas", "+1 30–60° · +2 > 60° (salvo sentado)", "≥ 30° y ≤ 60° → +1; > 60° → +2; sentado y > 60° → 0", "0–2"],
        ["Carga", "< 5 kg 0 · 5–10 +1 · > 10 +2; brusca +1", "Declarada", "0–3"],
        ["Brazo", "1 −20° a 20° · 2 ext. > 20° o 20–45° · 3 45–90° · 4 > 90°", "−20° ≤ x ≤ 20° → 1; < −20° o ≤ 45° → 2; ≤ 90° → 3; > 90° → 4", "1–4"],
        ["Brazo ±", "+1 abducido o rotado · +1 hombro elevado · −1 apoyo", f"Abducción > {g(U.brazo_abducido)}° (criterio provisional) o rotación declarada", "rango"],
        ["Antebrazo", "1 60–100° · 2 resto", "60° ≤ x ≤ 100° → 1", "1–2"],
        ["Muñeca", "1 ≤ 15° · 2 > 15°; +1 torsión o desviación", "Declarada o estimada", "1–3 (con desviación desconocida)"],
        ["Agarre", "0–3", "Declarado", "0–3"],
        ["Actividad", "+1 estática · +1 repetitiva · +1 cambios bruscos", "Declarada; acumulable hasta +3", "0–3"],
    ])
    d.p("**Lados:** se calcula el grupo B de los dos brazos y se toma el peor; un brazo oculto se recorre entero. **Final** = "
        "tabla C(A + carga, B + agarre) + actividad, con A y B por encima de 12 en la fila o columna 12.")
    d.h(3, "4.2 Tabla A (tronco × cuello × piernas)")
    d.tabla(["Tronco"] + [f"Cu{c}·P{p}" for c in range(1, 4) for p in range(1, 5)],
            [[t] + [T.reba_tabla_a(t, c, p) for c in range(1, 4) for p in range(1, 5)] for t in range(1, 6)], calor=True)
    d.h(3, "4.3 Tabla B (brazo × antebrazo × muñeca)")
    d.tabla(["Brazo"] + [f"A{a}·M{m}" for a in range(1, 3) for m in range(1, 4)],
            [[b] + [T.reba_tabla_b(b, a, m) for a in range(1, 3) for m in range(1, 4)] for b in range(1, 7)], calor=True)
    d.h(3, "4.4 Tabla C (A × B)")
    d.tabla(["A \\ B"] + list(range(1, 13)), [[a] + [T.reba_tabla_c(a, b) for b in range(1, 13)] for a in range(1, 13)],
            calor=True, ancha=True)
    d.h(3, "4.5 Niveles de actuación")
    d.tabla(["Puntuación desde", "Nivel", "Riesgo", "Actuación"], [list(n) for n in T.REBA_NIVELES],
            pie="Se rechazan puntuaciones fuera de 1–15.")
    d.h(3, "4.6 Comprobaciones de frontera (reglas reales, sin margen)")
    filas = []
    for x in (-20.01, -20.0, -0.01, 0.0, 0.01, 20.0, 20.01, 60.0, 60.01):
        filas.append(["Tronco", f"{g(x)}°", s_(R.reba_tronco_base(iv(x)))])
    for x in (-0.01, 0.0, 20.0, 20.01):
        filas.append(["Cuello", f"{g(x)}°", s_(R.reba_cuello_base(iv(x)))])
    for x in (-20.01, -20.0, 20.0, 20.01, 45.0, 45.01, 90.0, 90.01):
        filas.append(["Brazo", f"{g(x)}°", s_(R.reba_brazo_base(iv(x)))])
    for x in (59.99, 60.0, 100.0, 100.01):
        filas.append(["Antebrazo", f"codo {g(x)}°", s_(R.reba_antebrazo(iv(x)))])
    for x in (15.0, 15.01):
        filas.append(["Muñeca", f"{g(x)}°", s_(R.reba_muneca(iv(x), None, False))])
    for x, s in ((29.99, False), (30.0, False), (60.0, False), (60.01, False), (45.0, True), (60.01, True)):
        filas.append(["Rodillas", f"{g(x)}°{' sentado' if s else ''}", s_(R.reba_rodillas(iv(x), frozenset({s})))])
    for kg in (4.99, 5.0, 10.0, 10.01):
        filas.append(["Carga", f"{g(kg)} kg", s_(R.reba_carga(kg, False))])
    filas.append(["Muñeca y desviación", "desconocidas", s_(R.reba_muneca(None, None, None))])
    d.tabla(["Elemento", "Entrada", "Puntuación del programa"], filas)

    # 5 RULA --------------------------------------------------------------
    d.h(2, "RULA", "rula")
    d.p("Tablas: Ergonautas (UPV), [método RULA](https://www.ergonautas.upv.es/metodos/rula/rula-ayuda.php). Original: "
        "McAtamney y Corlett (1993). " + CONVENCIONES["RULA"])
    d.h(3, "5.1 Elementos")
    d.tabla(["Elemento", "Método", "Regla del programa (en la frontera, la mayor)", "Si se desconoce"], [
        ["Brazo", "1 −20° a 20° · 2 ext. > 20° o 20–45° · 3 45–90° · 4 > 90°", "−20° < x < 20° → 1; ≤ −20° o < 45° → 2; < 90° → 3; ≥ 90° → 4", "1–4"],
        ["Brazo ±", "+1 hombro elevado · +1 abducido · −1 apoyo (original 1993)", f"Abducción > {g(U.brazo_abducido)}° (provisional); la rotación de Ergonautas no se suma", "rango"],
        ["Antebrazo", "1 60–100° · 2 resto; +1 a un lado o cruza la línea media", f"60° < x < 100° → 1; +1 si muñeca ≤ {g(U.antebrazo_cruza)} o ≥ {g(U.antebrazo_fuera)} semianchos (provisional)", "1–3"],
        ["Muñeca", "1 neutra · 2 0–15° · 3 > 15°; +1 desviación", "0° → 1; < 15° → 2; ≥ 15° → 3", "1–4 (con desviación desconocida)"],
        ["Giro de muñeca", "1 medio · 2 extremo", "Declarado", "1–2"],
        ["Cuello", "1 0–10° · 2 10–20° · 3 > 20° · 4 extensión; +1 rotado; +1 inclinado", "< 0° → 4; < 10° → 1; < 20° → 2; ≥ 20° → 3; +1 y +1 declarados", "1–6"],
        ["Tronco", "1 erguido · 2 0–20° · 3 20–60° · 4 > 60°; +1 rotado; +1 inclinado", f"0° → 1; < 20° → 2; < 60° → 3; ≥ 60° → 4; extensión por magnitud (adaptación); +1 y +1 si > {g(U.giro_presente)}°", "1–6"],
        ["Piernas", "1 bien apoyadas y peso simétrico · 2 no", "Apoyo declarado o desde OWAS: 2, 4 → 1; 3, 5 → 2; 1, 6, 7 → 1–2", "1–2"],
        ["Actividad muscular", "+1 estática > 1 min o repetitiva > 4/min", "Declarada", "0–1"],
        ["Carga/fuerza", "0 < 2 kg · 1 2–10 kg interm. · 2 2–10 estát./rep. o > 10 interm. · 3 > 10 estát./rep. o golpes", "2 kg y 10 kg suben de tramo", "0–3"],
    ])
    d.p("**Lados:** se evalúan los dos y se resume con el peor. **Final** = tabla C(C, D) con C ≥ 8 en la fila 8+ y D ≥ 7 en "
        "la columna 7+; se conservan C y D originales.")
    d.h(3, "5.2 Tabla A")
    d.tabla(["Brazo · antebrazo"] + [f"M{m}·G{gg}" for m in range(1, 5) for gg in range(1, 3)],
            [[f"{b} · {a}"] + [T.rula_tabla_a(b, a, m, gg) for m in range(1, 5) for gg in range(1, 3)]
             for b in range(1, 7) for a in range(1, 4)], calor=True)
    d.h(3, "5.3 Tabla B")
    d.tabla(["Cuello"] + [f"T{t}·P{p}" for t in range(1, 7) for p in range(1, 3)],
            [[c] + [T.rula_tabla_b(c, t, p) for t in range(1, 7) for p in range(1, 3)] for c in range(1, 7)], calor=True, ancha=True)
    d.h(3, "5.4 Tabla C")
    d.tabla(["C \\ D"] + [str(x) + ("+" if x == 7 else "") for x in range(1, 8)],
            [[f"{c}{'+' if c == 8 else ''}"] + [T.rula_tabla_c(c, dd) for dd in range(1, 8)] for c in range(1, 9)], calor=True)
    d.h(3, "5.5 Niveles de actuación")
    d.tabla(["Puntuación desde", "Nivel", "Etiqueta", "Actuación"], [list(n) for n in T.RULA_NIVELES],
            pie="Sin etiquetas de riesgo propias: solo nivel y actuación. Se rechazan puntuaciones fuera de 1–7.")
    d.h(3, "5.6 Comprobaciones de frontera (reglas reales, sin margen)")
    filas = []
    for x in (-20.01, -20.0, 19.99, 20.0, 44.99, 45.0, 89.99, 90.0):
        filas.append(["Brazo", f"{g(x)}°", s_(R.rula_brazo_base(iv(x)))])
    for x in (60.0, 60.01, 99.99, 100.0):
        filas.append(["Antebrazo (muñeca en 1 semiancho)", f"codo {g(x)}°", s_(R.rula_antebrazo(iv(x), iv(1.0), U))])
    for x in (0.0, 0.01, 2.0):
        filas.append(["Antebrazo (codo 80°)", f"muñeca a {g(x)} semianchos", s_(R.rula_antebrazo(iv(80), iv(x), U))])
    for x in (0.0, 0.01, 14.99, 15.0):
        filas.append(["Muñeca", f"{g(x)}°", s_(R.rula_muneca(iv(x), None, False))])
    for x in (-0.01, 0.0, 9.99, 10.0, 19.99, 20.0):
        filas.append(["Cuello", f"{g(x)}°", s_(R.rula_cuello(iv(x), False, False))])
    filas.append(["Cuello", "5°, rotado e inclinado", s_(R.rula_cuello(iv(5), True, True))])
    for x in (0.0, 0.01, 19.99, 20.0, 59.99, 60.0, -25.0):
        filas.append(["Tronco", f"{g(x)}°", s_(R.rula_tronco(iv(x), iv(0), iv(0), U))])
    for kg, est in ((1.99, False), (2.0, False), (9.99, False), (10.0, False), (9.99, True), (10.0, True)):
        filas.append(["Carga/fuerza", f"{g(kg)} kg, {'estática' if est else 'intermitente'}",
                      s_(R.rula_fuerza(kg, {"estatica": est, "repetitiva": False}, False))])
    filas.append(["Muñeca y desviación", "desconocidas", s_(R.rula_muneca(None, None, None))])
    d.tabla(["Elemento", "Entrada", "Puntuación del programa"], filas)

    # 5.7 casos completos -------------------------------------------------
    d.h(3, "5.7 Casos completos (todas las entradas fijadas)")
    casos = [
        ("De pie; tronco, cuello y brazos a 0°; codos 0° (colgando); muñeca neutra declarada; sin carga, agarre bueno, "
         "sin actividad; nada rotado ni elevado", neutro(), tarea()),
        ("Tronco 50°, cuello 30°, rodillas 50° (pies a la misma altura), brazos 50° respecto al tronco, codos 90°, muñeca "
         "neutra; 12 kg, agarre regular, repetitiva; resto declarado «no»",
         neutro(tronco_sag=50.0, tronco_flex=50.0, cuello=30.0, rodilla_I=50.0, rodilla_D=50.0, muslo_I=40.0, muslo_D=40.0,
                pierna_I=10.0, pierna_D=10.0, codo_I=90.0, codo_D=90.0, brazo_flex_I=50.0, brazo_flex_D=50.0),
         tarea(carga_kg=12.0, agarre=1, actividad=dict(estatica=False, repetitiva=True, cambios=False))),
        ("Brazo izq. a 100° abducido (80° fuera del plano sagital), codo 0°, muñeca a 3,7 semianchos; resto como el primero",
         neutro(brazo_flex_I=100.0, brazo_abd_I=80.0, antebrazo_lat_I=3.7), tarea()),
        ("Como el primero, pero sin declarar nada (todo desconocido)", neutro(), Tarea()),
    ]
    filas = []
    for nombre, m, t in casos:
        r, u_ = puntua(m, t)
        filas.append([nombre, r_(r["A"]), r_(r["B"]), r_(r["rango"]), r_(u_["C"]), r_(u_["D"]), r_(u_["rango"])])
    d.tabla(["Postura (lado izq. en RULA)", "REBA A", "REBA B", "REBA", "RULA C", "RULA D", "RULA"], filas)

    # 6 Validación --------------------------------------------------------
    d.h(2, "Estado del resultado y validez técnica", "validacion")
    d.p("Los colores miden cobertura y certeza del cálculo con convenciones provisionales, no la exactitud de la medida "
        "ni el nivel de riesgo.")
    d.tabla(["Método", "Comprobación", "Verde", "Ámbar", "Rojo"], [
        ["REBA, RULA", "Estado del rango de la peor postura", "un nivel de actuación (concluyente)", "dos niveles contiguos (acotada)", "más (incompleta)"],
        ["REBA", "Fotogramas con los dos brazos y el tronco medidos", "≥ 70 %", "≥ 40 %", "< 40 %"],
        ["RULA", "Fotogramas con el brazo del lado y el tronco medidos", "≥ 70 %", "≥ 40 %", "< 40 %"],
        ["REBA, RULA", "Peor postura de frente o de espaldas (3D, giro < 25°)", "—", "sí", "—"],
        ["REBA, RULA", "Hueco > 1 s junto a una postura a 1 punto del pico", "—", "sí", "—"],
        ["OWAS", "Observaciones con código nominal conocido", f"≥ {g(M.cobertura[0])} %", f"≥ {g(M.cobertura[1])} %", "menos"],
        ["OWAS", "Intervalo aproximado del % de tiempo", f"≤ ±{g(M.margen_objetivo)}", f"≤ ±{g(2 * M.margen_objetivo)}", "más"],
        ["OWAS", "Duración", "≥ 20 min", "< 20 min", "—"],
    ])
    d.p("**Peor postura (REBA, RULA):** sostenida (máximo de la puntuación mínima en ventanas de 0,5 s) y pico breve "
        "fiable (máximo en fotogramas sin valores interpolados, con su duración). Si el pico breve supera a la sostenida, "
        "se avisa para revisarlo en el vídeo.")

    # 7 Filtros -----------------------------------------------------------
    d.h(2, "Filtros mecánicos (parámetros pendientes de calibración)", "filtros")
    d.tabla(["Filtro", "Valor"], [
        ["Visibilidad mínima de un punto (probabilidad de MediaPipe)", g(F.visibilidad)],
        ["Visibilidad mínima para la torsión (prevalece sobre la general solo en esa medida)", g(F.visibilidad_giro)],
        ["Longitud de huesos 3D: variación máxima respecto a la mediana", f"{g(int(F.tolerancia_hueso * 100))} %"],
        ["Atípicos (Hampel): semiventana · MAD · mínimo", f"{g(F.hampel_ventana_s)} s · {g(F.hampel_sigmas)} · {g(F.hampel_minimo)}°"],
        ["Saltos imposibles: tramo mínimo entre saltos", f"{g(F.tramo_minimo_s)} s"],
        ["Relleno de huecos (se marca como interpolado)", f"hasta {g(F.hueco_maximo_s)} s"],
    ])
    d.tabla(["Medida", "Rango", "Velocidad máxima"],
            [[v["nombre"], f"{g(v['rango'][0])} a {g(v['rango'][1])} {v['unidad']}", f"{g(v['vmax'])} {v['unidad']}/s"] for v in MEDIDAS.values()])

    # 8 Puntos ------------------------------------------------------------
    d.h(2, "Puntos abiertos", "revisar")
    d.tabla(["Ref.", "Decisión", "Estado", "Valor actual"], [
        ["P1, P4, P5", "Tolerancias de neutralidad", "Resuelto", "Sin tolerancias en las reglas; margen de medida aparte"],
        ["P2, P3", "Detección de torsión/inclinación y abducción (REBA/RULA)", "Pendiente del experto", f"> {g(U.giro_presente)}° y > {g(U.brazo_abducido)}°, provisionales"],
        ["P6", "Extensión del tronco en RULA", "Pendiente del experto", "Adaptación: por magnitud (≤ 20° → 2; < 60° → 3)"],
        ["P7", "Brazo elevado en OWAS", "Resuelto", "Codo o muñeca al nivel del hombro o por encima"],
        ["P8", "Antebrazo a un lado o cruzando (RULA)", "Pendiente del experto", f"≤ {g(U.antebrazo_cruza)} / ≥ {g(U.antebrazo_fuera)} semianchos"],
        ["P9", "Piernas REBA/RULA", "Provisional", "Apoyo con rango y declaración; falta validar con vídeos"],
        ["P10", "Rodillas sentado (REBA)", "Resuelto (lectura literal)", "Solo se suprime el +2"],
        ["P11", "Datos no declarados", "Resuelto", "Rango completo"],
        ["P12", "Peor postura", "Resuelto", "Sostenida + pico breve fiable"],
        ["P13", "REBA con un brazo oculto", "Resuelto", "El brazo oculto se recorre entero (rango)"],
        ["P14", "Lado de RULA", "Resuelto", "Los dos lados; resumen con el peor"],
        ["P15", "Heurísticas OWAS de andar, sentado, arrodillado", "Pendiente de validación", "Provisionales"],
        ["P16", "Intervalo y muestra efectiva OWAS", "Provisional", "1 s; intervalo «aproximado»"],
        ["P17", "Semáforos", "Resuelto en la presentación", "«Validez técnica provisional»"],
        ["P18", "Etiquetas de RULA", "Resuelto", "Solo nivel y actuación"],
        ["P19", "Fronteras de RULA (notas de 2024)", "Pendiente de verificar el documento", "En la frontera, la mayor"],
        ["P20", "Márgenes de medida", "Provisional", "Sección 2.1; calibrar con vídeos anotados"],
    ])
    d.p("**Validación propuesta:** vídeos reales independientes (personas y vídeos distintos para calibrar y para probar), "
        "con oclusiones y distintas cámaras, anotados por un ergónomo. Informar error angular, matriz de confusión por "
        "código OWAS, acuerdo por nivel de actuación y, sobre todo, las subestimaciones. Kappa sin ponderar para los "
        "códigos OWAS de piernas (nominales); para REBA y RULA, además del ICC, acuerdo ordinal por nivel.")

    # 9 Fuentes -----------------------------------------------------------
    d.h(2, "Fuentes", "fuentes")
    d.ul([
        "Ergonautas (UPV): ayudas de OWAS, REBA y RULA (tablas extraídas el 06/11/2026 a `tests/fixtures`).",
        "INSST. NTP 601: método REBA. INSHT (2015), *Posturas de trabajo: evaluación del riesgo* (OWAS, figuras 5 y 6).",
        "Karhu, Kansi y Kuorinka (1977), OWAS. Hignett y McAtamney (2000), REBA. McAtamney y Corlett (1993), RULA.",
        "McAtamney (2024), notas para usar RULA, citadas por la auditoría (selección de lado y fronteras): pendiente de "
        "verificar.",
        "Aghazadeh y Xiong: preprint SSRN 6035502; la auditoría cita una versión publicada (DOI 10.1016/j.ergon.2026.104061), "
        "pendiente de verificar.",
        "Auditoría documental de OWAS, REBA y RULA, 06/11/2026.",
    ])
    return d


# ------------------------------------------------------------------ página

CSS = """
:root{
  /* Documento técnico de revisión: una columna de lectura y tablas anchas con su propio desplazamiento. */
  --papel:#fbfbf8; --tinta:#1c2421; --suave:#5b6862; --linea:#d9ded9; --cabecera:#eef1ec; --acento:#2f6f5e;
  --nota:#f3efe2; --nota-borde:#b9a25a;
  --s1:#e6f2ea; --s2:#cfe7d6; --s3:#f3ecc4; --s4:#f6dca6; --s5:#f4c58a; --s6:#efab74; --s7:#e8915f;
  --s8:#de7652; --s9:#d15e48; --s10:#c24a42; --s11:#b13b3c; --s12:#9e2f36; --s-tinta:#1c2421; --s-tinta-fuerte:#fff;
  --f-texto:"Source Serif 4", Georgia, "Times New Roman", serif;
  --f-titulo:"IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --f-dato:"IBM Plex Mono", ui-monospace, Consolas, monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --papel:#141917; --tinta:#e4e9e5; --suave:#9aa69f; --linea:#2c3531; --cabecera:#1c2320; --acento:#7cc4ad;
  --nota:#2a2618; --nota-borde:#8c7a3e;
  --s1:#1d3328; --s2:#24402f; --s3:#4a4523; --s4:#5a4a22; --s5:#6a4a22; --s6:#764424; --s7:#7d3d26;
  --s8:#843628; --s9:#8a302b; --s10:#8e2a2e; --s11:#912530; --s12:#952032; --s-tinta:#e4e9e5; --s-tinta-fuerte:#fff;
  color-scheme:dark}}
:root[data-theme="dark"]{
  --papel:#141917; --tinta:#e4e9e5; --suave:#9aa69f; --linea:#2c3531; --cabecera:#1c2320; --acento:#7cc4ad;
  --nota:#2a2618; --nota-borde:#8c7a3e;
  --s1:#1d3328; --s2:#24402f; --s3:#4a4523; --s4:#5a4a22; --s5:#6a4a22; --s6:#764424; --s7:#7d3d26;
  --s8:#843628; --s9:#8a302b; --s10:#8e2a2e; --s11:#912530; --s12:#952032; --s-tinta:#e4e9e5; --s-tinta-fuerte:#fff;
  color-scheme:dark}
body{background:var(--papel);color:var(--tinta);font:16px/1.6 var(--f-texto)}
.pagina{max-width:980px;margin:0 auto;padding-block:32px 64px;
  padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px))}
h1,h2,h3{font-family:var(--f-titulo);text-wrap:balance;line-height:1.25}
h1{font-size:2rem;margin:0 0 .4rem;letter-spacing:-.01em}
h2{font-size:1.4rem;margin:3rem 0 .8rem;padding-top:.6rem;border-top:2px solid var(--tinta)}
h3{font-size:1.08rem;margin:2rem 0 .6rem;color:var(--acento)}
p,li{max-width:68ch}
a{color:var(--acento)}
code{font-family:var(--f-dato);font-size:.86em;background:var(--cabecera);padding:0 .25em;border-radius:3px}
.nota{background:var(--nota);border-left:4px solid var(--nota-borde);padding:.7rem 1rem;margin:1rem 0;max-width:68ch}
nav.indice{display:flex;flex-wrap:wrap;gap:.4rem 1rem;font-family:var(--f-titulo);font-size:.9rem;margin:1.2rem 0 0;
  padding:.7rem 0;border-block:1px solid var(--linea)}
nav.indice a{text-decoration:none}
.tabla{overflow-x:auto;margin:.6rem 0 1rem;border:1px solid var(--linea);border-radius:4px}
table{border-collapse:collapse;width:100%;font-family:var(--f-titulo);font-size:.84rem;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--linea);padding:.4rem .55rem;text-align:left;vertical-align:top}
th{background:var(--cabecera);font-weight:600;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
.tabla.ancha table{width:auto}
.tabla.ancha th,.tabla.ancha td{padding:.3rem .4rem;text-align:center}
.tabla.ancha td:first-child,.tabla.ancha th:first-child{text-align:left;white-space:nowrap;position:sticky;left:0;background:var(--cabecera)}
td.s{text-align:center;font-family:var(--f-dato);color:var(--s-tinta)}
td.s1{background:var(--s1)}td.s2{background:var(--s2)}td.s3{background:var(--s3)}td.s4{background:var(--s4)}
td.s5{background:var(--s5)}td.s6{background:var(--s6)}td.s7{background:var(--s7)}td.s8{background:var(--s8);color:var(--s-tinta-fuerte)}
td.s9{background:var(--s9);color:var(--s-tinta-fuerte)}td.s10{background:var(--s10);color:var(--s-tinta-fuerte)}
td.s11{background:var(--s11);color:var(--s-tinta-fuerte)}td.s12{background:var(--s12);color:var(--s-tinta-fuerte)}
.pie{font-size:.85rem;color:var(--suave);margin-top:-.4rem}
@media (prefers-reduced-motion: reduce){*{scroll-behavior:auto}}
"""


def pagina(d: Doc) -> str:
    cuerpo, toc = d.html()
    fuentes = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500'
               '&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">')
    indice = '<nav class="indice" aria-label="Secciones">' + "".join(toc) + "</nav>"
    # El índice va justo después de la nota inicial.
    partes = cuerpo.split("</aside>", 1)
    cuerpo = partes[0] + "</aside>" + indice + partes[1] if len(partes) == 2 else indice + cuerpo
    return (f'<title>Revisión OWAS REBA RULA</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            f"{fuentes}\n<style>{CSS}</style>\n<main class=\"pagina\">\n{cuerpo}\n</main>\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=str(Path(__file__).resolve().parents[1] / "docs"))
    a = ap.parse_args()
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    d = construir()
    (out / "REVISION_METODOS.md").write_text(d.md(), encoding="utf-8")
    (out / "revision_metodos.html").write_text(pagina(d), encoding="utf-8")
    print(out / "REVISION_METODOS.md")
    print(out / "revision_metodos.html")


if __name__ == "__main__":
    main()
