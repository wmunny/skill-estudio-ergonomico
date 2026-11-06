# Skill: estudio ergonómico (OWAS, REBA, RULA) a partir de vídeo

Demostración de lo que un asistente de IA (Claude) puede hacer con una skill y librerías abiertas: a partir de **uno o varios vídeos de un puesto de trabajo**, evalúa la carga postural con **OWAS**, **REBA** y **RULA** usando **MediaPipe Pose**. Antes de puntuar comprueba, método a método, si el vídeo sirve. Después entrega un informe con las puntuaciones, las capturas de las peores posturas y recomendaciones de grabación.

> **Aviso.** Resultados **no validados** frente a la observación de un ergónomo. No sustituyen a una evaluación de riesgos ni al criterio de un técnico de prevención. Ver [docs/LIMITACIONES.md](docs/LIMITACIONES.md).

Nace de las lecciones de la PoC [postura-poc](https://github.com/wmunny/postura-poc). MediaPipe mide, pero se inventa las articulaciones ocultas. Las reglas mecánicas detectan lo imposible. El % de tiempo de OWAS necesita grabaciones largas. Hay que elegir 2D o 3D según la orientación de la cámara y calcular con el lado visible. Las puntuaciones se calculan siempre en código, nunca con un modelo de lenguaje.

## Tres métodos, dos preguntas

| Método | Pregunta | Qué necesita del vídeo |
| --- | --- | --- |
| OWAS | ¿Cuánto tiempo pasa en cada postura? | Grabación larga (20–40 min o varios ciclos) |
| REBA | ¿Cuál es la peor postura de todo el cuerpo? | Ver las posturas exigentes con los dos brazos |
| RULA | ¿Cuál es la peor postura de la extremidad superior? | Ver las posturas exigentes del lado evaluado |

En el vídeo sintético de paletizado del ejemplo (30 s, cuerpo entero a 45°), REBA y RULA salen en verde. OWAS sale en rojo, porque 30 s no bastan para estimar porcentajes de tiempo.

## Qué entra y qué sale

| Entrada | Formato |
| --- | --- |
| Vídeos | MP4/MOV/AVI legibles por OpenCV. Varias tomas (se combinan) o varias cámaras sincronizadas (OWAS elige la mejor por instante y región) |
| Carga | `--carga-kg 12`, o un CSV `video;inicio_s;fin_s;kg` por tramos (se aplica por instante en OWAS, REBA y RULA; fuera de los tramos, `--carga-kg` o la de la revisión, y si no hay, rango); `--fuerza-brusca` |
| Datos de REBA/RULA que la cámara no ve | `--agarre`, `--actividad`, `--muneca`, `--muneca-desviada`, `--muneca-giro-extremo`, `--hombro-elevado`, `--brazo-apoyado`, `--brazo-rotado`, `--cuello-girado`, `--cuello-inclinado`, `--fuerza-brusca`, `--apoyo-piernas`. Sin declarar → rango |
| Turno | `--turno-h 8`, para expresar minutos por turno en OWAS |

| Salida | Contenido |
| --- | --- |
| `informe.html` / `informe.md` | Validez por método, peor postura de REBA y RULA con sus elementos, % del tiempo observable OWAS (nominal, intervalo aproximado y rango), categorías, capturas, recomendaciones de grabación, método y limitaciones |
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

# Dos cámaras sincronizadas (la segunda empezó 1,5 s antes)
.venv\Scripts\python scripts\estudio_video.py analizar --video izq.mp4 --video dch.mp4 --modo mejor-camara --desfases 0,1.5 --salida salida_2cam
```

### Como skill de Claude

Enlaza esta carpeta en `~/.claude/skills/estudio-ergonomico-video/` (o en `.claude/skills/` de un proyecto):

```bash
cmd /c mklink /D "%USERPROFILE%\.claude\skills\estudio-ergonomico-video" "%CD%"
```

Claude seguirá [SKILL.md](SKILL.md): te preguntará la carga, el agarre, la actividad y cómo se grabaron los vídeos. Después analiza, revisa las capturas y te explica los resultados con su validez y sus limitaciones.

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
4. **OWAS** ([clasificar.py](scripts/ergovideo/clasificar.py), [muestreo.py](scripts/ergovideo/muestreo.py)): códigos con los umbrales del método (Mattila et al., 1999), categorías por combinación y por frecuencia, un fotograma real por observación, % del tiempo observable con intervalo aproximado (Wilson con muestra efectiva por código; cobertura no verificada) y rango con margen y datos que faltan.
5. **REBA y RULA** ([ergo.py](scripts/ergovideo/ergo.py)): tablas A, B y C con todos los modificadores. Cada fotograma se puntúa como rango (lo que no se mide se recorre entero). La peor postura es el máximo de la puntuación mínima en ventanas de 0,5 s, de modo que un fotograma mal estimado no la fija. También se dan las posturas críticas y la distribución por niveles.
6. **Validez por método:**
   - **OWAS:** cobertura, margen del % de tiempo y duración.
   - **REBA y RULA:** fotogramas evaluables (REBA con los dos brazos) y si la peor postura es un rango, solo tiene un brazo, se ve de frente o de espaldas, o queda junto a un hueco largo.
7. **Tablas** ([tablas.py](scripts/ergovideo/tablas.py)): OWAS, REBA y RULA leídas de las tablas HTML de [Ergonautas](https://www.ergonautas.upv.es/) (UPV), con pruebas que fijan celdas comprobadas a mano.

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

1.254 pruebas:

- **Tablas:** las 904 celdas de OWAS, REBA y RULA frente a una copia extraída de Ergonautas (`tests/fixtures`), no frente al propio código.
- **Fronteras:** cada umbral en a − ε, a y a + ε con el valor esperado escrito a mano.
- **OWAS:** posturas sintéticas de frente, a 45° y de perfil; datos que faltan (nunca favorables); margen; filtros, muestreo y elección de cámara.
- **REBA y RULA:** celdas de las tablas A, B y C y niveles. Posturas sintéticas calculadas a mano en tres vistas: neutra, exigente con carga, brazo abducido, extensiones, antebrazo cruzando la línea media y muñeca. También rangos cuando falta un dato, datos declarados, carga de RULA, peor postura sostenida frente a un fotograma erróneo y validez con un brazo tapado.
