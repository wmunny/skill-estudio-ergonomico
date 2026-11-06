# Roadmap

Estado a 06/11/2026: skill funcional (OWAS, REBA y RULA), auditada documentalmente, con revisión visual y 1.274 pruebas. Demostración no validada. Siguiente fase: probarla con vídeos reales del usuario y recoger mejoras.

## Hecho (06/11/2026): revisión visual y contexto de la tarea

Lo aprendido en postura-poc con Gemini Argon, ahora con Claude como revisor: láminas original/esqueleto (`revisar`),
`revision.json` con contexto, fases, muñecas por fase y veredictos con evidencia; política de decisión en código
(ocultaciones largas y mal colocadas se quitan, cortas y aproximadas se conservan con más margen, lados solo con
confirmación de la profundidad); el usuario confirma el contexto; el informe distingue el origen de cada dato y compara
sin y con revisión. Sentado o de pie cierran las piernas que no se ven. Primera prueba: MTR-juguetes (REBA de 2–15 a
4–7; OWAS de 0 % a 97 % de observaciones codificadas). Pendiente: consenso entre varias revisiones y validarlo con
vídeos anotados.

## Próximo: varias tomas no simultáneas del mismo puesto (paso 1)

Caso habitual: varios vídeos del mismo trabajador y la misma tarea, **grabados en momentos distintos** y desde puntos distintos (p. ej., uno ve mejor el lado derecho y otro el izquierdo). No se pueden fusionar por instante: combinar el brazo de una toma con el de otra fabricaría una postura que no ha ocurrido.

Propuesta (sin inventar posturas):

- **RULA:** para cada lado, la peor postura de todas las tomas, usando solo los fotogramas en que ese lado se ve. El informe indica de qué vídeo y segundo sale cada lado.
- **OWAS:** ya funciona con `--modo combinar` (las tomas suman observaciones y duración).
- **REBA:** cada toma se puntúa como ahora (el brazo oculto da rango); el REBA del puesto es la peor de las tomas. Si en todas falta un brazo, el rango será amplio y se dirá.
- **Tabla de cobertura:** qué toma ve qué lado y qué región del cuerpo, para saber si falta alguna vista.
- Nuevo modo de la CLI (p. ej. `--modo tomas`) y sección «Evaluación del puesto» en el informe; pruebas con tomas sintéticas que vean lados distintos.

## Después (si los rangos de REBA salen demasiado amplios): alinear tomas por fases (paso 2)

Emparejar cada momento de una toma con el equivalente de otra (alineamiento temporal, p. ej. DTW, sobre lo que ven ambas: tronco y piernas) y acotar el brazo oculto de una toma con el de la otra en la misma fase. Sería una estimación: marcarla como tal, informar de la calidad del emparejamiento y validarla con vídeos reales.

## Pendiente del experto (ver `docs/REVISION_METODOS.md`, «Puntos abiertos»)

- P2/P3: criterios de detección de torsión/inclinación (20°) y abducción (30°).
- P6: extensión del tronco en RULA.
- P8: antebrazo a un lado o cruzando la línea media.
- P15: heurísticas OWAS de andar, sentado y arrodillado.
- P19: verificar las notas de McAtamney (2024) sobre fronteras de RULA.
- P20: márgenes de medida por zona.
- Verificar el DOI de la versión publicada de Aghazadeh y Xiong.

## Validación

- Piloto con 10–20 vídeos reales anotados por un ergónomo (personas y vídeos distintos para calibrar y para probar).
- Medir error angular, matriz de confusión por código OWAS, acuerdo por nivel de actuación y subestimaciones; calibrar márgenes y umbrales de detección.

## Mejoras técnicas (tras validar)

- Muñeca con un modelo de manos (MediaPipe Hands) en lugar de los tres puntos del modelo de cuerpo.
- Fusión de cámaras simultáneas también en REBA y RULA (por instante y elemento, la cámara que mejor ve).
- Sincronización automática de vídeos simultáneos por el movimiento.
