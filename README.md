# Skill: estudio ergonómico (OWAS, REBA, RULA y OCRA) a partir de vídeo

Demostración de lo que un asistente de IA (Claude) puede hacer con una skill y librerías abiertas: a partir de **uno o varios vídeos de un puesto de trabajo**, evalúa la carga postural con **OWAS**, **REBA** y **RULA** usando **MediaPipe Pose**, y los movimientos repetitivos de la extremidad superior con **OCRA** (ISO 11228-3, tablas clásicas). Antes de puntuar comprueba, método a método, si el vídeo sirve. Después entrega un informe para la dirección con los problemas, en qué se basan y las medidas preventivas, y el detalle técnico aparte.

> [!CAUTION]
> **Solo para investigación. Se desaconseja totalmente su uso profesional.**
> Esta herramienta **no está validada**. Faltan ensayos con ergónomos validadores que fijen sus capacidades y sus limitaciones. Sus resultados **no son una evaluación de riesgos** ni sirven para tomar decisiones sobre trabajadores o puestos reales. Los autores **no responden** de ningún uso distinto de la investigación. Lee el [aviso legal](#aviso-legal-y-exención-de-responsabilidad) antes de usarla.

Nace de las lecciones de la PoC [postura-poc](https://github.com/wmunny/postura-poc). MediaPipe mide, pero se inventa las articulaciones ocultas. Las reglas mecánicas detectan lo imposible. El % de tiempo de OWAS necesita grabaciones largas. Hay que elegir 2D o 3D según la orientación de la cámara y calcular con el lado visible. Las puntuaciones se calculan siempre en código, nunca con un modelo de lenguaje.

## Cuatro métodos, dos caminos

| Método | Pregunta | Qué necesita del vídeo |
| --- | --- | --- |
| OWAS | ¿Cuánto tiempo pasa en cada postura? | Grabación larga (20–40 min o varios ciclos) |
| REBA | ¿Cuál es la peor postura de todo el cuerpo? | Ver las posturas exigentes con los dos brazos |
| RULA | ¿Cuál es la peor postura de la extremidad superior? | Ver las posturas exigentes del lado evaluado |
| OCRA | ¿Cuántas acciones técnicas hace cada mano frente a las que admite el puesto? | ≥ 3 ciclos, manos visibles, ≥ 25 fps. No necesita cuerpo entero: es observacional y MediaPipe es opcional |

- **Estudio completo** («hazme un estudio ergonómico»): todos los métodos para los que sirva el vídeo, con una sola pasada de MediaPipe y un informe integrado con un semáforo por método (`--metodos todos`, por defecto).
- **Un método concreto** («hazme un OCRA», «solo RULA»): solo ese o esos métodos (`--metodos ocra`, `--metodos rula`…).

En el vídeo sintético de paletizado del ejemplo (30 s, cuerpo entero a 45°), REBA y RULA salen en verde. OWAS sale en rojo, porque 30 s no bastan para estimar porcentajes de tiempo.

## Qué entra y qué sale

| Entrada | Formato |
| --- | --- |
| Vídeos | MP4/MOV/AVI legibles por OpenCV. Varias tomas (se combinan) o varias cámaras sincronizadas (OWAS elige la mejor por instante y región) |
| Carga | `--carga-kg 12`, o un CSV `video;inicio_s;fin_s;kg` por tramos (se aplica por instante en OWAS, REBA y RULA; fuera de los tramos, `--carga-kg` o la de la revisión, y si no hay, rango); `--fuerza-brusca` |
| Datos de REBA/RULA que la cámara no ve | `--agarre`, `--actividad`, `--muneca`, `--muneca-desviada`, `--muneca-giro-extremo`, `--hombro-elevado`, `--brazo-apoyado`, `--brazo-rotado`, `--cuello-girado`, `--cuello-inclinado`, `--fuerza-brusca`, `--apoyo-piernas`. Sin declarar → rango |
| Turno | `--turno-h 8`, para expresar minutos por turno en OWAS |
| OCRA | `--datos-ocra datos.json`: tareas repetitivas y minutos, turno y pausas con su hora, ciclo o producción, Borg por fase y mano, factores adicionales, lateralidad. Más la **ficha de acciones técnicas** del bloque `ocra` de la revisión. Sin declarar → rango. `--clasificacion-ocra iso2007\|colombini5` |

| Salida | Contenido |
| --- | --- |
| `informe.html` | Dos pestañas: informe para la dirección (semáforos, problemas, medidas; en OCRA, índice por mano, línea de tiempo del ciclo con las AT, multiplicadores, mapa de brazos, escenario proyectado y sensibilidad) y detalle técnico |
| `informe_tecnico.md` | Validez por método, peor postura de REBA y RULA con sus elementos, % del tiempo observable OWAS (nominal, intervalo aproximado y rango), categorías, capturas, recomendaciones de grabación, método y limitaciones |
| `esqueleto_<vídeo>.mp4` | Vídeo con el esqueleto, la cara difuminada, el código OWAS y las puntuaciones REBA y RULA de cada momento |
| `capturas/*.jpg` | Peores posturas de REBA y RULA y una captura por categoría OWAS |
| `porcentajes.png`, `cronograma_<vídeo>.png` | Frecuencia de cada código OWAS; medidas y códigos en el tiempo |
| `resumen.json`, `observaciones.csv` | Todos los números |

Los informes, capturas y vídeos que genera la herramienta no se versionan: se guardan en local en `estudios/` o `ejemplos/` (ambas en `.gitignore`).

## Instalación

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\descargar_modelos.py
```

Los modelos (`pose_landmarker_full.task`, de 9 MB, y `heavy`, de 30 MB) se descargan del repositorio oficial de MediaPipe a `modelos/`. Para recodificar el vídeo a H.264 hace falta `ffmpeg`.

## Uso

```bash
# Datos básicos y avisos previos (sin MediaPipe)
.venv\Scripts\python scripts\estudio_video.py inspeccionar --video tarea.mp4

# OWAS, REBA y RULA con los datos de la tarea
.venv\Scripts\python scripts\estudio_video.py analizar --video tarea.mp4 --salida salida_tarea --carga-kg 12 --agarre regular --actividad repetitiva --turno-h 8

# Solo REBA y RULA, con la muñeca declarada
.venv\Scripts\python scripts\estudio_video.py analizar --video tarea.mp4 --salida salida_tarea --metodos reba,rula --muneca mas15 --muneca-desviada si

# Solo OCRA: láminas del ciclo (a 6 fotogramas/s) para la ficha de acciones técnicas, y estudio
.venv\Scripts\python scripts\estudio_video.py revisar --video tarea.mp4 --salida salida_tarea --metodos ocra --ciclo-inicio 10 --ciclo-fin 20
.venv\Scripts\python scripts\estudio_video.py analizar --video tarea.mp4 --salida salida_tarea --metodos ocra --revision salida_tarea\revision_tarea.json --datos-ocra datos_ocra.json

# OCRA sin vídeo (datos manuales o un JSON)
.venv\Scripts\python scripts\estudio_video.py ocra --datos-ocra datos_ocra.json --salida salida_ocra

# Dos cámaras sincronizadas (la segunda empezó 1,5 s antes)
.venv\Scripts\python scripts\estudio_video.py analizar --video izq.mp4 --video dch.mp4 --modo mejor-camara --desfases 0,1.5 --salida salida_2cam
```

Ejemplo de `datos_ocra.json` (cada dato admite un número, `[mín, máx]`, `null` o `{"valor": …, "origen": "declarado", "nota": "…"}`):

```json
{
  "clasificacion": "iso2007",
  "lateralidad": "diestra",
  "turno": {"inicio": "08:00", "fin": "16:00",
            "pausas": [{"hora": "10:00", "min": 10}, {"hora": "12:00", "min": 30, "tipo": "comida"}]},
  "tareas": [{"nombre": "Montaje", "minutos": 400, "ciclo_s": 10,
              "manos": {"dch": {"borg": [{"fase": "atornillar", "s": 3, "borg": 2}, {"fase": "resto", "s": 7, "borg": 0.5}],
                                "adicionales": [{"factor": "guantes", "fraccion": 1.0}]},
                        "izq": {"borg": null, "adicionales": []}}}]
}
```

Las AT por ciclo, el ciclo y la estereotipia salen de la ficha de la revisión; PoM, de las posturas medidas (si hay MediaPipe) y del agarre de la revisión, o se declara (`"pom": 0.7`). RcM se calcula desde el horario.

### Como skill de Claude

Enlaza esta carpeta en `~/.claude/skills/estudio-ergonomico-video/` (o en `.claude/skills/` de un proyecto):

```bash
cmd /c mklink /D "%USERPROFILE%\.claude\skills\estudio-ergonomico-video" "%CD%"
```

Claude seguirá [SKILL.md](SKILL.md): elegirá el camino (estudio completo o métodos concretos) y te preguntará la carga, el agarre, la actividad, cómo se grabaron los vídeos y, para OCRA, el turno, las pausas, el ciclo, el esfuerzo (Borg) y la lateralidad. Después analiza, revisa las capturas y te explica los resultados con su validez y sus limitaciones.

## Cómo funciona

1. **Pose** ([pose.py](scripts/ergovideo/pose.py)): MediaPipe Pose Landmarker (API Tasks) en modo vídeo, a 10 fps por defecto, con caché.
2. **Medidas** ([medidas.py](scripts/ergovideo/medidas.py)):
   - **Tronco:** flexión o extensión con signo, inclinación lateral y torsión.
   - **Cuello:** eje hombros→orejas respecto al tronco.
   - **Brazo:** flexión o extensión respecto al tronco y abducción.
   - **Codo:** siempre en 3D.
   - **Muñeca:** con los puntos del índice y el meñique, si se ven.
   - **Antebrazo respecto a la línea media** (para RULA).
   - **Altura del codo o la mano sobre el hombro** (para OWAS).
   - **Rodillas, orientación de muslo y pantorrilla, tobillos y velocidad de la cadera.**

   El cálculo es en 2D cuando el trabajador está de perfil y en 3D en el resto. Si un lado está tapado, se usa el visible.
3. **Filtros** ([filtros.py](scripts/ergovideo/filtros.py)): longitud de huesos constante y coherencia 2D–3D por punto. En cada serie: rango fisiológico, Hampel, saltos imposibles y relleno solo de huecos cortos.
4. **OWAS** ([clasificar.py](scripts/ergovideo/clasificar.py), [muestreo.py](scripts/ergovideo/muestreo.py)): códigos con los umbrales del método (los de Ergonautas, que cita a Mattila et al., 1999), categorías por combinación y por frecuencia, un fotograma real por observación, % del tiempo observable con intervalo aproximado (Wilson con muestra efectiva por código; cobertura no verificada) y rango con margen y datos que faltan.
5. **REBA y RULA** ([ergo.py](scripts/ergovideo/ergo.py)): tablas A, B y C con todos los modificadores. Cada fotograma se puntúa como rango (lo que no se mide se recorre entero). La peor postura es el máximo de la puntuación mínima en ventanas de 0,5 s, de modo que un fotograma mal estimado no la fija. También se dan las posturas críticas y la distribución por niveles.
6. **Validez por método:**
   - **OWAS:** cobertura, margen del % de tiempo y duración.
   - **REBA y RULA:** fotogramas evaluables (REBA con los dos brazos) y si la peor postura es un rango, solo tiene un brazo, se ve de frente o de espaldas, o queda junto a un hueco largo.
7. **OCRA** ([tablas_ocra.py](scripts/ergovideo/tablas_ocra.py), [ocra.py](scripts/ergovideo/ocra.py), [ocra_at.py](scripts/ergovideo/ocra_at.py), [ocra_video.py](scripts/ergovideo/ocra_video.py)): Claude rellena una ficha de acciones técnicas por mano mirando el ciclo a 4–8 fotogramas por segundo; el código aplica los criterios de recuento (rechaza «soltar herramienta», «sujetar» con la mano de apoyo…) y da rango si hay gestos dudosos. Índice por mano: ATA / RTA con FoM (Borg), PoM (el factor más bajo de hombro, codo, muñeca y agarre), ReM, AdM, RcM (desde el horario real) y DuM; varias tareas; sensibilidad; escenario proyectado. MediaPipe, si ve al trabajador, propone el ciclo por periodicidad, las fracciones de postura forzada y los instantes candidatos a AT.
   **Aviso normativo:** tablas clásicas (ISO 11228-3:2007 y Colombini y Occhipinti). ISO 11228-3:2026 (08/05/2026) sustituye a la de 2007 y **no se ha verificado** la conformidad con ella; cada constante lleva la marca `verificar_iso_2026`.
8. **Tablas** ([tablas.py](scripts/ergovideo/tablas.py)): OWAS, REBA y RULA transcritas de las ayudas de [Ergonautas](https://www.ergonautas.upv.es/) (UPV), con algunas convenciones del INSST. Detalle en [Fuentes](#fuentes).

## Cómo colocar la cámara

Resumen de Aghazadeh y Xiong (KAIST, [SSRN 6035502](https://ssrn.com/abstract=6035502), preprint sin revisión por pares), que comparan MediaPipe y MMPose con captura óptica de movimiento desde tres vistas:

| Vista | Error angular medio (ambos modelos) | ICC REBA (MediaPipe) | ICC RULA (MediaPipe) |
| --- | --- | --- | --- |
| Frontal | 18,4° | 0,91 | 0,96 |
| 45° | 14,7° | 0,85 | 0,95 |
| Lateral | 13,5° | 0,75 | 0,69 |

- **45° es el mejor compromiso** para MediaPipe entre ángulos y puntuaciones. La vista frontal da la mejor concordancia de REBA y RULA, pero el peor ángulo. La lateral da el mejor ángulo, pero la peor concordancia.
- **La oclusión manda:** la tarea tras un obstáculo tuvo el mayor error (29,8°).
- Cámara fija y nivelada, cuerpo entero en el encuadre y resolución de 1280×720 o más. Colócala del lado de la mano que más trabaja y añade una segunda cámara si un brazo queda tapado.

## Pruebas

```bash
.venv\Scripts\python -m pytest -q
```

1.462 pruebas:

- **Tablas:** las 904 celdas de OWAS, REBA y RULA frente a una copia extraída de Ergonautas (`tests/fixtures`), no frente al propio código.
- **Fronteras:** cada umbral en a − ε, a y a + ε con el valor esperado escrito a mano.
- **OWAS:** posturas sintéticas de frente, a 45° y de perfil; datos que faltan (nunca favorables); margen; filtros, muestreo y elección de cámara.
- **OCRA:** cada tabla (FoM, PoM, ReM, AdM, RcM, DuM, bandas) en a − ε, a y a + ε; cálculo por mano a mano; multitarea; RcM desde el horario; rangos con datos desconocidos; sensibilidad y escenario; cada regla de la ficha de AT con casos que deben rechazarse; regresión MTR-juguetes (9,78 y 5,57; la ficha de 17/14 AT se queda en 11/8); ciclo y posturas con series sintéticas; orden `ocra` e informe.
- **REBA y RULA:** celdas de las tablas A, B y C y niveles. Posturas sintéticas calculadas a mano en tres vistas: neutra, exigente con carga, brazo abducido, extensiones, antebrazo cruzando la línea media y muñeca. También rangos cuando falta un dato, datos declarados, carga de RULA, peor postura sostenida frente a un fotograma erróneo y validez con un brazo tapado.

## Fuentes

Qué se tomó de cada fuente. El detalle, regla a regla, está en [docs/REVISION_METODOS.md](docs/REVISION_METODOS.md).

| Fuente | Qué se tomó | Cómo se usó |
| --- | --- | --- |
| **Ergonautas** (Universitat Politècnica de València): ayudas de [OWAS](https://www.ergonautas.upv.es/metodos/owas/owas-ayuda.php), [REBA](https://www.ergonautas.upv.es/metodos/reba/reba-ayuda.php) y [RULA](https://www.ergonautas.upv.es/metodos/rula/rula-ayuda.php), leídas el 06/11/2026 | Las 904 celdas de las tablas de los tres métodos, los umbrales de los elementos y la tabla de error de OWAS según el número de observaciones | **Fuente principal** de las tablas ([tablas.py](scripts/ergovideo/tablas.py)) y de la copia con la que se prueban ([tests/fixtures/tablas_ergonautas.json](tests/fixtures/tablas_ergonautas.json)). En OWAS y REBA, los valores en el límite entre dos tramos siguen su lectura literal |
| **INSST** (antes INSHT): *Posturas de trabajo: evaluación del riesgo* (2015), figuras 5 y 6 (OWAS) | Carga en OWAS: ≤ 10 kg → 1; > 10 y ≤ 20 kg → 2; > 20 kg → 3. Brazo elevado si está «al nivel del hombro o por encima» | **Convenciones** que se aplican en lugar de las de Ergonautas (que pone 10 kg en el tramo 2) y **contraste**: con su figura 6 se corrigió la combinación OWAS 3143 (categoría 3, no 4) |
| **INSST**: NTP 601, *Evaluación de las condiciones de trabajo: carga postural. Método REBA* | Tablas y modificadores de REBA | **Contraste** de REBA |
| **Artículos originales**: Karhu, Kansi y Kuorinka (1977), OWAS; Hignett y McAtamney (2000), REBA; McAtamney y Corlett (1993), RULA | Definición de los métodos | **Referencia** de cada método. En RULA, el apoyo del brazo (−1) sigue el original de 1993. Las tablas no se han contrastado celda a celda con los originales |
| **McAtamney (2024)**, notas para usar RULA, citadas por la auditoría de métodos | En el límite entre dos puntuaciones, la mayor; evaluar el lado más exigente | Criterio adoptado en RULA. **Documento pendiente de verificar** |
| **OCRA**: Occhipinti (1998), *Ergonomics* 41(9); Colombini, Occhipinti y Grieco (2002); ISO 11228-3:2007, anexo C; UNE-EN 1005-5:2007; INSST (movimientos repetitivos) | Fórmula del índice, multiplicadores, bandas de clasificación y criterios de recuento de acciones técnicas | Tablas **clásicas** en [tablas_ocra.py](scripts/ergovideo/tablas_ocra.py), cada constante con su fuente y `verificar_iso_2026`. **ISO 11228-3:2026** (08/05/2026) sustituye a la de 2007: no verificada. Puntos abiertos O1–O11 en [docs/REVISION_METODOS.md](docs/REVISION_METODOS.md) |
| **Aghazadeh y Xiong**, KAIST ([SSRN 6035502](https://ssrn.com/abstract=6035502), preprint sin revisión por pares) | Error de MediaPipe y concordancia de REBA y RULA según la vista de la cámara | Recomendaciones de grabación y margen de medida provisional |
| **MediaPipe Pose Landmarker** (Google) | Modelos `full` y `heavy` | Estimación de la pose |

Las pruebas comparan el código con la copia de Ergonautas, no con el INSST ni con los originales. Un error que tenga Ergonautas pasaría las pruebas. Antes de cualquier uso fuera de la investigación habría que contrastar las tablas celda a celda con las publicaciones originales y con el INSST (ver [docs/LIMITACIONES.md](docs/LIMITACIONES.md)).

## Aviso legal y exención de responsabilidad

**Léelo entero antes de usar la herramienta.** Usar, copiar, instalar o ejecutar este software, o sus resultados, supone aceptar estas condiciones. Si no las aceptas, no lo uses.

### 1. Finalidad: solo investigación

Este software es un **prototipo experimental de investigación**. Sirve para explorar qué puede hacer un asistente de IA con estimación de pose y métodos de carga postural. Su único uso permitido es la **investigación y la experimentación** (estudios piloto, comparación de métodos, docencia, pruebas técnicas), con datos y personas que participen sabiéndolo.

### 2. No validado

La herramienta **no ha sido validada**. Para validarla hacen falta ensayos controlados en los que **ergónomos validadores** comparen sus resultados con evaluaciones hechas por expertos. Esos ensayos todavía no se han hecho. Hasta entonces no se conocen con rigor su exactitud, su fiabilidad, sus capacidades ni sus limitaciones.

Hay errores conocidos que pueden cambiar el resultado. MediaPipe estima mal las articulaciones tapadas y puede inventarlas. Los ángulos medidos en vídeo tienen un error de varios grados que depende de la cámara. Algunos datos que piden los métodos no se ven en la imagen. El modelo de IA que guía la skill puede equivocarse al revisar el vídeo o al redactar el informe. Ver [docs/LIMITACIONES.md](docs/LIMITACIONES.md).

### 3. Uso profesional desaconsejado

**Se desaconseja totalmente su uso profesional.** En particular, **no debe usarse** para:

- hacer, sustituir o completar una **evaluación de riesgos laborales**, ni la de un puesto concreto;
- cumplir obligaciones legales de prevención de riesgos laborales (en España, la Ley 31/1995 de Prevención de Riesgos Laborales y el Real Decreto 39/1997, Reglamento de los Servicios de Prevención, o su equivalente en otros países);
- tomar decisiones sobre trabajadores concretos: aptitud, vigilancia de la salud, asignación de tareas, retribución, disciplina o despido;
- diagnósticos, valoraciones médicas, periciales, informes para inspección, juzgados, mutuas o aseguradoras;
- diseñar o aprobar puestos, equipos o medidas preventivas sin la revisión de un técnico competente.

La evaluación de riesgos ergonómicos corresponde a **técnicos de prevención cualificados**, que observan el puesto en persona y aplican su criterio profesional. Ningún resultado de esta herramienta sustituye ese criterio. Las puntuaciones, los «problemas identificados» y las «medidas preventivas» del informe son **ejemplos generados automáticamente**, no recomendaciones profesionales.

### 4. Sin garantías

El software y sus resultados se ofrecen **«tal cual» (*as is*) y «según disponibilidad»**, **sin garantía de ningún tipo**, expresa o implícita. Esto incluye, entre otras, las garantías de exactitud, fiabilidad, integridad, actualidad, idoneidad para un fin concreto, comerciabilidad, cumplimiento normativo y no infracción de derechos de terceros. Nada garantiza que funcione sin errores ni que sus resultados coincidan con los de un ergónomo.

### 5. Limitación de responsabilidad

**En la máxima medida que permita la ley aplicable**, los autores, colaboradores y las entidades a las que pertenezcan **no serán responsables** de ningún daño o perjuicio, directo o indirecto, incidental, especial, consecuente o punitivo, que derive de usar o de no poder usar el software o sus resultados, ni de confiar en ellos. Esto incluye, entre otros, lesiones o daños a la salud de trabajadores, accidentes, enfermedades profesionales, sanciones administrativas, reclamaciones de terceros, decisiones laborales, pérdida de datos, lucro cesante o daño reputacional. La exclusión se aplica sea cual sea el fundamento de la reclamación (contrato, responsabilidad extracontractual, negligencia u otro) y aunque se hubiera advertido de la posibilidad del daño.

Esta cláusula no excluye la responsabilidad que, por ley, no pueda excluirse (por ejemplo, la derivada de dolo o culpa grave).

### 6. Responsabilidad de quien la usa

Quien use el software, o sus resultados, lo hace **por su cuenta y riesgo** y asume toda la responsabilidad de ese uso, incluido cualquier uso profesional en contra de este aviso. En particular, quien la use es responsable de:

- comprobar cualquier resultado con un técnico de prevención cualificado antes de darle cualquier uso;
- informar a las personas que aparezcan en los vídeos y obtener su consentimiento o la base jurídica que corresponda, y cumplir la normativa de protección de datos (RGPD y LOPDGDD en España). Los vídeos de trabajadores son datos personales y pueden contener datos de salud. **Quien graba y analiza es el responsable del tratamiento**, no los autores de este software, que no reciben ni tratan esos datos;
- cumplir la normativa laboral, la de prevención, la de inteligencia artificial que le sea aplicable y los derechos de representación de los trabajadores;
- dejar a los autores libres de cualquier reclamación de terceros que derive de su uso.

### 7. Terceros

El software usa componentes y datos de terceros (entre otros, MediaPipe de Google, las tablas de los métodos transcritas de [Ergonautas](https://www.ergonautas.upv.es/), UPV, y criterios del INSST; ver [Fuentes](#fuentes)), sujetos a sus propias licencias y condiciones. Los autores no responden de esos componentes. OWAS, REBA, RULA y OCRA son métodos publicados por sus autores; esta implementación no está avalada por ellos.

### 8. Sin relación profesional

Ni el software ni su documentación constituyen asesoramiento profesional en ergonomía, prevención de riesgos laborales, medicina del trabajo ni derecho. Usarlo no crea ninguna relación profesional, contractual ni de servicio con los autores.

### Disclaimer (English summary)

**Research use only. Professional use is strongly discouraged.** This software is an unvalidated experimental prototype; its capabilities and limitations have not been established through trials with expert ergonomist validators. It is not a risk assessment tool and must not be used to make or replace occupational risk assessments, or to make decisions about real workers or workplaces. It is provided "AS IS", without warranty of any kind. To the maximum extent permitted by applicable law, the authors and contributors accept no liability for any damage arising from its use or from reliance on its results. Users act at their own risk and are solely responsible for any use, including compliance with data protection law for any video they process. The Spanish text above prevails.
