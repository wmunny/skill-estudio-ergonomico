---
name: estudio-ergonomico-video
description: Hace estudios ergonómicos de un puesto de trabajo a partir de uno o varios vídeos, con OWAS, REBA, RULA (carga postural, con MediaPipe Pose) y OCRA (movimientos repetitivos de la extremidad superior, ISO 11228-3, observacional). Dos caminos. Si el usuario pide un «estudio ergonómico», un «informe ergonómico» o una «evaluación ergonómica» sin nombrar método, aplica todos los métodos para los que sirva el vídeo y entrega un único informe integrado. Si nombra uno o varios («hazme un OCRA», «solo RULA», «un REBA»), aplica solo esos. Primero revisa el vídeo y dice en el chat para qué métodos sirve; después entrega un informe visual para la dirección (problemas, en qué se basan, medidas priorizadas) con el detalle técnico aparte. Úsala también si pide el % de tiempo en posturas forzadas, la peor postura, el índice OCRA, las acciones técnicas por minuto o la repetitividad de un puesto (y si escribe «OWASP» refiriéndose a posturas). Es una demostración NO validada.
---

# Estudio ergonómico (OWAS, REBA, RULA y OCRA) a partir de vídeo

Herramienta de **demostración**: enseña lo que un asistente de IA puede hacer combinando visión artificial clásica (MediaPipe Pose), revisión visual y reglas y tablas en código. Sus resultados **no están validados** frente a un ergónomo. Dilo siempre al presentar resultados.

Si el usuario escribe «OWASP», se refiere a OWAS (posturas), no a la seguridad web: basta con usar el nombre correcto.

## Elige el camino

| El usuario pide… | Camino | `--metodos` |
| --- | --- | --- |
| «Estudio / informe / evaluación ergonómica» sin nombrar método | **Estudio completo**: todos los métodos para los que sirva el vídeo (según `validar`), un único informe integrado con portada de síntesis (un semáforo por método) | `todos` (por defecto) |
| Uno o varios métodos con nombre: «hazme un OCRA», «solo RULA», «REBA y RULA» | **Estudio de esos métodos**: solo ellos, con las mediciones que necesiten, informe solo de ellos | `ocra`, `rula`, `reba,rula`… |

Si `validar` dice que el vídeo no sirve para algún método del estudio completo, explícalo y sigue con los demás (o con lo que el usuario decida).

## Qué evalúa cada método

| Método | Qué mide | Qué necesita del vídeo |
| --- | --- | --- |
| OWAS | % del tiempo en cada postura de espalda, brazos y piernas, con la carga | Grabación larga (20–40 min o varios ciclos) y unas 100 observaciones independientes |
| REBA | Peor postura de todo el cuerpo (los dos lados), con carga, agarre y actividad | Ver bien las posturas más exigentes, con los dos brazos |
| RULA | Peor postura centrada en la extremidad superior, de un lado | Ver bien el lado evaluado en las posturas más exigentes |
| OCRA | Índice de riesgo por movimientos repetitivos de cada mano: acciones técnicas por minuto frente a una frecuencia de referencia reducida por fuerza, postura, repetitividad, factores adicionales, recuperación y duración | Al menos 3 ciclos completos, manos y objetos visibles, la mano más activa del lado de la cámara, ≥ 25 fps. **No** necesita cuerpo entero, ni piernas, ni vista a 45° |

OCRA es **observacional** (vídeo a cámara lenta, entrevista, datos de organización). MediaPipe es opcional: si ve al trabajador, propone el tiempo de ciclo, la fracción del tiempo con hombro, codo y muñeca en postura forzada e instantes candidatos a acción técnica. Si no sirve (plano cerrado de manos, oclusión), OCRA sigue sin él. En el estudio completo se usa **una sola pasada** de MediaPipe para todos los métodos.

## Qué hace

1. Extrae 33 puntos del cuerpo por fotograma con MediaPipe Pose Landmarker (local, sin enviar el vídeo a ningún servicio).
2. Mide tronco, cuello, brazo, codo, muñeca (si se ven los puntos de la mano), antebrazo respecto a la línea media, altura de codos y manos, rodillas y apoyo de los pies. 2D de perfil, 3D en el resto, lado visible.
3. Filtros mecánicos: longitud de huesos constante, coherencia 2D–3D, rango fisiológico, atípicos, saltos imposibles; solo rellena huecos de hasta 0,3 s.
4. **OWAS**: observaciones a intervalo fijo (1 s), categoría por combinación y por frecuencia, % del tiempo observable con intervalo aproximado y rango.
5. **REBA y RULA**: tablas A, B y C con modificadores por fotograma; peor postura **sostenida** (0,5 s), pico breve fiable y posturas críticas. RULA en los dos lados.
6. **OCRA** (`tablas_ocra.py`, `ocra.py`, `ocra_at.py`): ficha de acciones técnicas (AT) por mano y ciclo que tú rellenas y **el código valida** con los criterios de recuento; ATA = Σ frecuencia × minutos; RTA = Σ (30 × FoM × PoM × ReM × AdM × minutos) × RcM × DuM; índice por mano con su rango; RcM desde el horario real; varias tareas en el turno; clasificación de ISO 11228-3:2007 (3 bandas) o de Colombini (5 bandas); sensibilidad y escenario proyectado.
7. **Nada desconocido se rellena con el valor favorable**: sale como rango. Cada dato indica su origen (medido, revisión visual, declarado por el usuario o supuesto).
8. Detecta **problemas ergonómicos** con reglas en código y propone **medidas preventivas** de un catálogo, que tú concretas al puesto.
9. Entrega `informe.html` con dos pestañas: **Informe ergonómico** (dirección) y **Detalle técnico**. Además `informe_tecnico.md`, `informe_datos.json`, `resumen.json`, capturas y, con OWAS/REBA/RULA, `observaciones.csv` y vídeo con el esqueleto.

**Aviso normativo (OCRA).** ISO 11228-3:2026 se publicó el 08/05/2026 y sustituye a la edición de 2007. Las tablas son las **clásicas** (2007 y Colombini y Occhipinti), todas en `scripts/ergovideo/tablas_ocra.py` con su fuente y la marca `verificar_iso_2026`. **No afirmes conformidad con la edición de 2026.**

## Instalación (una vez)

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\descargar_modelos.py
```

Todos los comandos se ejecutan desde la carpeta de la skill. El vídeo de salida se recodifica a H.264 si hay `ffmpeg` en el PATH o en `FFMPEG_PATH`.

## Flujo de trabajo

### 1. Inspeccionar (rápido, sin MediaPipe)

```bash
.venv\Scripts\python scripts\estudio_video.py inspeccionar --video <a.mp4> [--video <b.mp4>]
```

### 2. Entender la tarea y revisar (obligatorio antes de puntuar)

```bash
.venv\Scripts\python scripts\estudio_video.py revisar --video <a.mp4> --salida <carpeta> --metodos <todos|ocra|…>
    [--ciclo-inicio 10 --ciclo-fin 20] [--fps-ocra 6] [--sin-pose]
```

Deja una plantilla `revision_<vídeo>.json` y láminas en `<carpeta>/revision/<vídeo>/`:

- **Posturas (OWAS, REBA, RULA)**: `revision_NN.jpg`, cada instante dos veces, original y con el esqueleto (AZUL = lado izquierdo del trabajador, NARANJA = derecho). Rellena contexto, fases, muñecas y veredictos según [docs/REVISION_VISUAL.md](docs/REVISION_VISUAL.md).
- **OCRA**: `ocra_ciclo_NN.jpg`, el ciclo representativo a 4–8 fotogramas por segundo (el punto naranja marca instantes candidatos de MediaPipe). Si el ciclo propuesto no es fiable (`aviso`), mira las láminas, decide el ciclo y repite con `--ciclo-inicio/--ciclo-fin`. Rellena el bloque `ocra` (ciclo, `manos_visibles`, **ficha de AT** y agarre por mano) según la sección 6 de [docs/REVISION_VISUAL.md](docs/REVISION_VISUAL.md): una entrada por gesto, mano y segundo, con gesto, objeto, confianza y si propones contarla. **El código decide cuántas AT cuenta** (rechaza p. ej. «soltar herramienta» o «sujetar» con la mano de apoyo y da rango si hay gestos de confianza baja).

Tú informas; **la política la aplica el código**. Lo aprendido en la PoC: la IA es buen auditor y mal filtro automático.

### 3. Confirmar el contexto con el usuario (de una vez)

Enséñale en lenguaje llano lo que has visto y pídele que confirme o corrija:

- **Posturas** (si hay OWAS, REBA o RULA): de pie o sentado, apoyo de los pies; carga (kg) y fuerzas bruscas; agarre; actividad estática, repetitiva o con cambios bruscos; muñecas por fase, hombro elevado, brazo apoyado o rotado, cuello rotado o inclinado; turno (h); si hay varios vídeos, si son tomas distintas o cámaras simultáneas.
- **OCRA** (si está en el estudio): el **recuento de AT por mano** de la ficha (y las rechazadas, con su motivo); **tareas repetitivas del turno y minutos de cada una**; **duración del turno**; **pausas con su hora y duración** (y la comida); tareas no repetitivas (y si sirven de recuperación); **tiempo de ciclo o producción**; **Borg CR-10 por fase y mano** (o «no se sabe»); guantes, herramientas, vibración, precisión, golpes, frío; **lateralidad** del trabajador.

Corrige el JSON con sus respuestas; pon en `contexto.confirmado` los campos de postura que confirme y `ocra.confirmada: true` si confirma la ficha. Los datos de organización van en un `datos_ocra.json` (formato en `scripts/ergovideo/ocra.py`; ejemplo en el README). Lo que diga el usuario manda sobre la revisión. Lo que nadie sabe queda desconocido y se recorre entero (rango). No inventes respuestas.

### 4. Validar el vídeo en el chat y decidir

```bash
.venv\Scripts\python scripts\estudio_video.py validar --video <a.mp4> --salida <carpeta> --revision <carpeta>\revision_<vídeo>.json
    --metodos <los del camino> [--datos-ocra datos_ocra.json] [mismos datos que en analizar]
```

Devuelve, método a método, si el vídeo sirve (`sí`, `con reservas`, `no recomendable`), por qué y cómo mejorar la grabación. Para OCRA: ciclos completos, fps, si la mano más activa queda del lado de la cámara, el recuento de la ficha (con rechazadas y dudosas) y `datos_ocra_que_faltan`. **Explícalo en el chat** y **pregunta si seguimos y con qué métodos**. No hagas el informe sin esa respuesta.

### 5. Analizar

```bash
.venv\Scripts\python scripts\estudio_video.py analizar --video <a.mp4> [--video <b.mp4>] --salida <carpeta>
    --revision <carpeta>\revision_<vídeo>.json --metodos <todos|los elegidos>
    [--datos-ocra datos_ocra.json] [--clasificacion-ocra iso2007|colombini5] [--sin-pose]
    [--carga-kg 12 | --tramos-carga t.csv] [--agarre regular] [--actividad repetitiva]
    [--muneca auto|neutra|menos15|mas15] [--muneca-desviada si|no] [--muneca-giro-extremo si|no]
    [--hombro-elevado si|no] [--brazo-apoyado si|no] [--brazo-rotado si|no] [--cuello-girado si|no]
    [--cuello-inclinado si|no] [--fuerza-brusca si|no] [--apoyo-piernas bilateral|unilateral] [--rodillas menos30|30a60|mas60]
    [--modo combinar|mejor-camara] [--desfases 0,1.5] [--postura-base auto|de_pie|sentado]
    [--intervalo 1] [--fps-analisis 10] [--modelo full|heavy] [--sin-video]
```

- `--tramos-carga`: CSV `video;inicio_s;fin_s;kg` (video vacío = todos) que se aplica por instante en OWAS, REBA y RULA.
- OCRA toma de `--datos-ocra` lo declarado; completa con la ficha de AT (recuento, ciclo y estereotipia) y, si hay MediaPipe, las fracciones de postura de hombro, codo y muñeca (como rango). Si en el estudio completo faltan los minutos, OCRA no se calcula y la salida lo dice (`ocra`): pregunta y repite.
- Solo OCRA: MediaPipe se intenta y, si no ve a nadie, se sigue sin él (`--sin-pose` lo evita).
- **Sin vídeo** (datos manuales o un JSON): `estudio_video.py ocra --datos-ocra datos.json [--revision revision.json] [--salida carpeta]`.

Devuelve un JSON corto con los **problemas detectados**, la urgencia, las puntuaciones (OCRA: índice por mano con su rango, color, frecuencia, datos que faltan) y la ruta de `adaptacion.json`.

### 6. Concretar el informe al puesto (`adaptacion.json`)

Mira las capturas y las láminas y escribe `<carpeta>/adaptacion.json`:

```json
{
  "titulo": "Nombre corto del puesto o tarea",
  "descripcion_tarea": "Una o dos frases: qué hace, de pie o sentado, ciclo.",
  "conclusion": "3–4 frases para la dirección: qué pasa en el puesto, qué pesa más y qué cambio sería el más eficaz.",
  "hallazgos": {
    "<id del problema>": {
      "descripcion": "Lo que se ve en este puesto.",
      "medidas": [{"texto": "Medida concreta.", "tipo": "ingenieria|organizativa|formacion", "sustituye": "<id de medida de catálogo>"}]
    }
  },
  "escenario_ocra": {
    "titulo": "Qué se cambia",
    "medidas": ["Medida 1: efecto en AT, pausas…"],
    "cambios": {"tareas": [{"manos": {"dch": {"at_ciclo": 9}}}], "rcm": 0.9}
  }
}
```

Reglas: usa los **ids** que devolvió `analizar` (los de OCRA empiezan por `ocra_`) y los de las medidas de `informe_datos.json` (`plan`); no inventes problemas ni cifras; prioriza **diseño del puesto**; sé concreto. En `escenario_ocra.cambios` pon solo lo que cambian las medidas (mismo formato que `datos_ocra.json`, se fusiona encima); **el código recalcula** el índice y lo muestra antes/después marcado como **proyección**, no como resultado. Después:

```bash
.venv\Scripts\python scripts\estudio_video.py informe --salida <carpeta>
```

### 7. Revisar antes de entregar

- **Mira las capturas**: si el esqueleto no coincide con el cuerpo, ese problema no vale; dilo y quítalo (o corrige la revisión y repite).
- Si un problema dice «al menos X %», esa zona no siempre se ve: el tiempo real es mayor.
- OCRA: si el índice es un rango, **no lo conviertas en un número**; di qué dato lo estrecharía (p. ej. confirmar 3 gestos dudosos, el horario de pausas o el Borg). Si la ficha no está confirmada, dilo.

### 8. Presentar

Enlaza `informe.html` y resume para la dirección: la urgencia, los 2–3 problemas principales y las medidas prioritarias; en OCRA, el índice por mano con su color y rango y qué lo dispara (frecuencia, recuperación…). Termina con el aviso: prueba de concepto no validada; no sustituye a la evaluación de un técnico de prevención; OCRA con tablas clásicas, sin verificar frente a ISO 11228-3:2026.

## Cómo colocar la cámara

Según Aghazadeh y Xiong (KAIST, preprint SSRN 6035502, sin revisión por pares), con MediaPipe frente a captura óptica de movimiento (ICC REBA 0,87, RULA 0,92):

- **A 45° entre el frente y el lateral** es el mejor compromiso para las posturas: error angular medio 14,7° (18,4° de frente, 13,5° de perfil); ICC REBA 0,85, RULA 0,95.
- **La oclusión es la principal fuente de error** (29,8° trabajando tras un obstáculo): nada entre la cámara y el trabajador, cuerpo entero en el encuadre.
- Cámara fija, nivelada, a la altura de la cadera o el pecho, 1280×720 como mínimo, del lado de la mano que más trabaja; una segunda cámara si un brazo queda tapado (REBA necesita los dos).
- **Para OCRA**: al menos 3 ciclos completos seguidos, ≥ 25 fps (mejor 50–60 para ver los gestos a cámara lenta), las manos y los objetos que manipulan bien visibles, la mano más activa del lado de la cámara. Vale un plano más cerrado de tronco y brazos.
- Para OWAS, graba 20–40 min o varios ciclos completos.

## Reglas

- Los números salen de los scripts. No inventes, redondees a conveniencia ni «corrijas» códigos, puntuaciones ni recuentos de AT.
- Las puntuaciones se calculan con `scripts/ergovideo/tablas.py` (OWAS, REBA, RULA) y `tablas_ocra.py` (OCRA). Nunca las estimes tú ni con otro modelo.
- No conviertas un rango en un número: si REBA da 8–9 u OCRA 9,8–12,5, es un rango hasta que se declare lo que falta.
- No supongas datos para estrechar un rango: pregunta al usuario. `--sin-margen` solo sirve para comparar.
- Convenciones fijadas (ver `reglas.CONVENCIONES`): OWAS y REBA, lectura literal de Ergonautas; RULA, en la frontera la puntuación mayor; carga OWAS según INSST (10 kg → tramo 1). OCRA: FoM por escalón conservador sin interpolar (el otro escalón va a la sensibilidad); PoM, el factor más bajo de hombro, codo, muñeca y agarre; la estereotipia solo en ReM.
- Todo se ejecuta en local. No uses `--sin-difuminar` sin consentimiento del trabajador ni publiques capturas de personas reales sin revisarlas.

## Archivos

- `scripts/estudio_video.py`: punto de entrada.
- `scripts/ergovideo/`: `pose.py` (MediaPipe), `medidas.py`, `filtros.py`, `reglas.py`, `revision.py` (láminas, `revision.json` y política de la revisión), `hallazgos.py`, `catalogo.py`, `informe_puesto.py` (informe con pestañas), `clasificar.py` (OWAS), `ergo.py` (REBA, RULA), `tablas.py`, `muestreo.py`, `grabacion.py`, `visual.py`, `informe.py`; **OCRA**: `tablas_ocra.py` (constantes con fuente), `ocra.py` (cálculo, RcM desde el horario, sensibilidad, escenarios), `ocra_at.py` (ficha de AT y reglas de recuento), `ocra_video.py` (ciclo, posturas, candidatos, validez, láminas), `informe_ocra.py` (bloque visual y sección técnica), `cli_ocra.py`.
- `tests/`: `test_tablas.py`, `test_fronteras.py`, `test_owas.py`, `test_reba_rula.py`, `test_revision.py`, `test_informe_puesto.py` y `test_ocra.py` (tablas, fronteras, cálculo por mano, multitarea, RcM desde el horario, ficha de AT, regresión MTR-juguetes, vídeo sintético e informe).
- `docs/REVISION_VISUAL.md`: instrucciones de la revisión visual (también la ficha de AT).
- `scripts/informe_revision.py`: genera `docs/REVISION_METODOS.md` y `docs/revision_metodos.html` desde el código (incluye OCRA y sus puntos abiertos).
- `estudios/` y `ejemplos/`: salidas locales, en `.gitignore`; guarda cada análisis en `estudios/<nombre-del-vídeo>/`.
- `docs/LIMITACIONES.md`, `docs/ROADMAP.md`.
