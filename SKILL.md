---
name: estudio-ergonomico-video
description: Hace estudios ergonómicos de carga postural OWAS, REBA y RULA a partir de uno o varios vídeos de un puesto de trabajo, con MediaPipe Pose. Valida el vídeo por método antes de puntuar (OWAS necesita grabación larga para el % del tiempo; REBA y RULA, ver bien la peor postura), calcula las puntuaciones con las tablas originales en código y entrega informe HTML/Markdown, capturas y vídeo con el esqueleto y recomendaciones de grabación. Úsala cuando el usuario aporte vídeos de una tarea y pida un OWAS, un REBA, un RULA, el % de tiempo en posturas forzadas o la peor postura de un puesto (también si escribe «OWASP» refiriéndose a posturas). Es una demostración NO validada.
---

# Estudio ergonómico (OWAS, REBA, RULA) a partir de vídeo

Herramienta de **demostración**: enseña lo que un asistente de IA puede hacer combinando visión artificial clásica (MediaPipe Pose) con reglas y tablas en código. Sus resultados **no están validados** frente a un ergónomo. Dilo siempre al presentar resultados.

Si el usuario escribe «OWASP», se refiere a OWAS (posturas), no a la seguridad web: basta con usar el nombre correcto.

## Qué evalúa cada método

| Método | Qué mide | Qué necesita del vídeo |
| --- | --- | --- |
| OWAS | % del tiempo en cada postura de espalda, brazos y piernas, con la carga | Grabación larga (20–40 min o varios ciclos) y unas 100 observaciones independientes |
| REBA | Peor postura de todo el cuerpo (los dos lados), con carga, agarre y actividad | Ver bien las posturas más exigentes, con los dos brazos |
| RULA | Peor postura centrada en la extremidad superior, de un lado | Ver bien el lado evaluado en las posturas más exigentes |

Un mismo vídeo puede servir para REBA y RULA y no para OWAS. El informe da un semáforo por método.

## Qué hace

1. Extrae 33 puntos del cuerpo por fotograma con MediaPipe Pose Landmarker (local, sin enviar el vídeo a ningún servicio).
2. Mide tronco (flexión/extensión, inclinación lateral, torsión), cuello, brazo (flexión/extensión y abducción), codo, muñeca (con los puntos de la mano, si se ven), posición del antebrazo respecto a la línea media, altura de codos y manos, rodillas y apoyo de los pies. Usa 2D de perfil y 3D en el resto, y el lado visible.
3. Filtros mecánicos: longitud de huesos constante, coherencia 2D–3D, rango fisiológico, atípicos, saltos imposibles; solo rellena huecos de hasta 0,3 s.
4. **OWAS**: observaciones a intervalo fijo (1 s), códigos de espalda, brazos, piernas y carga, categoría por combinación (tabla 6) y por frecuencia (tabla 7), con un fotograma real por observación; % del tiempo observable con intervalo aproximado y rango.
5. **REBA y RULA**: puntuación de cada fotograma con las tablas A, B y C y los modificadores; peor postura **sostenida** (0,5 s), **pico breve fiable** y posturas críticas. RULA se evalúa en los **dos lados** y se resume con el peor.
6. **Nada desconocido se rellena con el valor favorable.** Cada ángulo lleva un margen de medida provisional; si cruza un umbral, o falta un dato (no se ve o no se declara), la puntuación sale como **rango** y el estado de la evaluación es concluyente, acotada o incompleta.
7. Con varios vídeos, OWAS combina las observaciones o elige por instante y región la cámara que mejor ve; REBA y RULA se puntúan por vídeo.
8. Entrega `informe.html` (autocontenido), `informe.md`, `resumen.json`, `observaciones.csv`, gráficos, capturas de las peores posturas y vídeo con el esqueleto, la cara difuminada y las puntuaciones.

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

### 2. Entender la tarea y revisar el esqueleto (obligatorio antes de puntuar)

No puntúes sin saber qué hace la persona: si está sentada, no hay que pedir las piernas; si un brazo no se ve, hay que saberlo. Como en la PoC postura-poc (donde lo hacía Gemini Argon), **tú haces de revisor visual**:

```bash
.venv\Scripts\python scripts\estudio_video.py revisar --video <a.mp4> --salida <carpeta>
```

Genera láminas (`<carpeta>/revision/<vídeo>/revision_NN.jpg`) con cada instante dos veces, original y con el esqueleto (AZUL = lado izquierdo del trabajador, NARANJA = derecho), y una plantilla `revision_<vídeo>.json`. **Mira todas las láminas** y rellena la plantilla siguiendo [docs/REVISION_VISUAL.md](docs/REVISION_VISUAL.md): contexto (de pie o sentado, apoyo, carga, agarre, actividad, rotaciones), fases con su riesgo, muñecas por fase y lado, y veredictos sobre el esqueleto con evidencia.

Tú informas; **la política la aplica el código** (lo mal colocado y las ocultaciones de más de 1,5 s se quitan; las cortas y lo «aproximado» se conservan con más margen; los lados solo se intercambian si la profundidad lo confirma). Lo aprendido en la PoC: la IA es buen auditor y mal filtro automático.

### 3. Confirmar el contexto con el usuario

Enséñale en lenguaje llano lo que has visto y pídele que confirme o corrija, de una vez:

- **Postura y piernas**: de pie o sentado; apoyo de los pies; rodillas si no se ven.
- **Carga** (kg) y si hay **fuerzas bruscas**; **agarre** (bueno, regular, malo, inaceptable).
- **Actividad**: estática más de 1 min, repetitiva más de 4 veces por minuto, cambios bruscos o base inestable.
- **Muñecas** por fase, **hombro elevado**, **brazo apoyado o rotado**, **cuello rotado o inclinado**.
- **Métodos** (por defecto los tres), **turno** (h) y, si hay varios vídeos, si son tomas distintas (combinar) o cámaras simultáneas (mejor-cámara, con desfases).

Corrige el JSON con sus respuestas y pon en `contexto.confirmado` los campos que confirme. Lo que diga el usuario en la línea de órdenes (`--carga-kg`, `--agarre`…) manda sobre la revisión. Lo que nadie sabe queda desconocido y se recorre entero (rango). No inventes respuestas.

### 4. Analizar

```bash
.venv\Scripts\python scripts\estudio_video.py analizar --video <a.mp4> [--video <b.mp4>] --salida <carpeta>
    --revision <carpeta>\revision_<vídeo>.json
    [--metodos owas,reba,rula] [--carga-kg 12 | --tramos-carga t.csv] [--agarre regular]
    [--actividad repetitiva] [--muneca auto|neutra|menos15|mas15] [--muneca-desviada si|no] [--muneca-giro-extremo si|no]
    [--hombro-elevado si|no] [--brazo-apoyado si|no] [--brazo-rotado si|no] [--cuello-girado si|no]
    [--cuello-inclinado si|no] [--fuerza-brusca si|no] [--apoyo-piernas bilateral|unilateral] [--rodillas menos30|30a60|mas60]
    [--turno-h 8] [--modo combinar|mejor-camara] [--desfases 0,1.5] [--postura-base auto|de_pie|sentado]
    [--intervalo 1] [--fps-analisis 10] [--modelo full|heavy] [--sin-video]
```

Con varios vídeos, `--revision` va una vez por vídeo (en el mismo orden) o una para todos. Tarda aproximadamente lo que dura el vídeo; la pose queda en caché (`<carpeta>/cache`). Con revisión, el programa evalúa también sin ella y el informe compara los dos resultados.

Devuelve un JSON corto: peor postura REBA y RULA por vídeo con su estado, nivel y validez, OWAS, avisos, datos desconocidos, **datos estimados por la IA sin confirmar** y la comparativa sin y con revisión.

### 5. Revisar antes de concluir

- **Mira las capturas** de la peor postura de REBA y RULA y las de categoría OWAS alta. Si el esqueleto no coincide con el cuerpo, esa postura no vale: dilo. MediaPipe inventa las articulaciones tapadas con valores plausibles.
- Si la peor postura sale **de frente o de espaldas**, los ángulos vienen de la profundidad estimada: el informe lo marca en ámbar. Trátala como orientativa.
- Si la puntuación es un **rango**, explica de qué depende (muñeca, torsión, cuello, un brazo) y qué dato lo cerraría.

### 6. Presentar resultados

Enlaza `informe.html` y resume:

- **Validez por método primero** (semáforo y motivo).
- **REBA y RULA**: peor postura (o rango) y su **estado** (concluyente, acotada, incompleta), nivel de actuación, en qué momento, qué elementos la explican y la trazabilidad (medidas, márgenes y origen); el pico breve si lo supera; RULA de los dos lados.
- **OWAS**: % nominal del tiempo **observable** con su intervalo aproximado y su rango, categorías por frecuencia (marca las inciertas) y distribución de categorías de las combinaciones.
- **Origen de los datos de la tarea** (declarado, confirmado, estimado por la IA, desconocido) y supuestos aplicados.
- **Qué ha cambiado la revisión visual** (tabla «sin revisión / con revisión») y qué veredictos se aplicaron.
- Si una **fase de riesgo** no se ve (p. ej. el brazo que trabaja queda tapado), dilo como conclusión principal y propón la toma que falta.
- **Recomendaciones de grabación**, sobre todo si algún método está en rojo.
- Puedes proponer medidas preventivas generales a partir de los elementos que más puntúan, pero distingue lo que calcula la herramienta de tu interpretación.
- Termina con el aviso: demostración no validada; no sustituye a una evaluación de riesgos.

## Cómo colocar la cámara

Según Aghazadeh y Xiong (KAIST, preprint SSRN 6035502, sin revisión por pares), con MediaPipe frente a captura óptica de movimiento (ICC REBA 0,87, RULA 0,92):

- **A 45° entre el frente y el lateral** es el mejor compromiso: error angular medio 14,7° (18,4° de frente, 13,5° de perfil) y buena concordancia de puntuaciones (ICC REBA 0,85; RULA 0,95). La vista frontal da la mejor concordancia de REBA y RULA (0,91 y 0,96) pero el peor ángulo; la lateral, el mejor ángulo pero la peor concordancia (0,75 y 0,69).
- **La oclusión es la principal fuente de error** (29,8° trabajando tras un obstáculo): nada entre la cámara y el trabajador, cuerpo entero en el encuadre.
- Cámara fija, nivelada, a la altura de la cadera o el pecho, 1280×720 como mínimo, del lado de la mano que más trabaja; una segunda cámara en el otro lado si un brazo queda tapado (REBA necesita los dos).
- Para la muñeca, acerca la cámara o graba un plano de detalle de las manos; aun así, decláralas si las conoces.
- Para OWAS, graba 20–40 min o varios ciclos completos.

## Reglas

- Los números salen de los scripts. No inventes, redondees a conveniencia ni «corrijas» códigos o puntuaciones.
- Las puntuaciones se calculan con las tablas de `scripts/ergovideo/tablas.py`. Nunca las estimes tú ni con otro modelo.
- No conviertas un rango en un número: si REBA da 8–9, es 8–9 hasta que se declare lo que falta.
- No supongas datos para estrechar un rango: pregunta al usuario. `--sin-margen` solo sirve para comparar.
- Convenciones fijadas (ver `reglas.CONVENCIONES`): OWAS y REBA, lectura literal de Ergonautas; RULA, en la frontera la puntuación mayor; carga OWAS según INSST (10 kg → tramo 1).
- Todo se ejecuta en local. No uses `--sin-difuminar` sin consentimiento del trabajador ni publiques capturas de personas reales sin revisarlas.

## Archivos

- `scripts/estudio_video.py`: punto de entrada.
- `scripts/ergovideo/`: `pose.py` (MediaPipe), `medidas.py` (ángulos 2D/3D, lado visible), `filtros.py`, `reglas.py` (reglas deterministas por elemento sobre intervalos), `revision.py` (láminas, `revision.json` y política de decisión de la revisión visual), `clasificar.py` (códigos OWAS), `ergo.py` (REBA, RULA y peor postura), `tablas.py` (tablas OWAS, REBA y RULA), `muestreo.py` (observaciones OWAS, cámaras, estadística), `grabacion.py` (diagnóstico y consejos), `visual.py`, `informe.py`.
- `scripts/ergovideo/sintetico.py`: esqueletos sintéticos para las pruebas.
- `tests/`: `test_tablas.py` (904 celdas frente a `fixtures/tablas_ergonautas.json`), `test_fronteras.py` (cada umbral en a − ε, a y a + ε), `test_owas.py`, `test_reba_rula.py` (posturas sintéticas, desconocidos, márgenes, pruebas de aceptación de la auditoría) y `test_revision.py` (validación del JSON, política de decisión, origen de los datos).
- `docs/REVISION_VISUAL.md`: instrucciones para la revisión visual (contexto, fases, muñecas, veredictos).
- `scripts/informe_revision.py`: genera `docs/REVISION_METODOS.md` y `docs/revision_metodos.html` desde el código, para la revisión experta.
- `estudios/` y `ejemplos/`: salidas locales (informes, capturas, vídeos). Están en `.gitignore` y nunca se suben al repositorio; guarda cada análisis en `estudios/<nombre-del-vídeo>/`.
- `docs/LIMITACIONES.md`: qué no hace la herramienta y por qué no está validada.
- `docs/ROADMAP.md`: próximos pasos (varias tomas no simultáneas del mismo puesto, validación, mejoras).
