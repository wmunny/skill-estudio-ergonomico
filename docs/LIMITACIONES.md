# Limitaciones

Esta skill (OWAS, REBA y RULA) es una **demostración**. Sus resultados no están validados y no sirven como evaluación de riesgos.

## No validada

- No se ha comparado con observaciones OWAS hechas por un ergónomo sobre los mismos vídeos. El siguiente paso sería anotar a mano 100–200 observaciones de varios vídeos reales (buenos y malos) y medir la concordancia por región (kappa) y en el % de tiempo.
- Los umbrales de OWAS (20° de flexión y de giro, 150° muslo-pantorrilla) están en la literatura; los demás (andar, sentarse, arrodillarse, pie levantado, margen del brazo) son heurísticas propias.
- Las pruebas usan esqueletos sintéticos: comprueban que el código hace lo que dice, no que MediaPipe mida bien.

## MediaPipe y una sola cámara

- MediaPipe **se inventa las articulaciones tapadas** con valores plausibles y visibilidad alta. Los filtros mecánicos solo quitan lo imposible (huesos que cambian de longitud, saltos, rangos), no lo plausible pero falso. En la PoC postura-poc, una cuarta parte de los valores de un vídeo con el trabajador de espaldas eran inventados.
- La **torsión del tronco** necesita ver los dos hombros y las dos caderas y depende de la profundidad estimada: es la medida menos fiable. Si no se puede medir, la espalda se codifica sin giro y se anota.
- La **profundidad 3D** es una estimación monocular. Por eso, de perfil se usa el 2D para la flexión.
- La vertical es la de la cámara: un móvil inclinado sesga la flexión del tronco y la altura de los brazos.
- **Sentado y en cuclillas** se confunden; para puestos sentados, indícalo.
- **Andar** se detecta por el desplazamiento de la cadera en la imagen: no ve a quien camina hacia la cámara y puede confundir un cambio de encuadre con un paso.

## OWAS

- OWAS estima la **proporción del tiempo** en cada postura. Necesita observar un periodo representativo (20–40 min o varios ciclos) y unas 100 observaciones independientes para un error del 10 %. Muestrear cada segundo no crea información: los fotogramas seguidos se parecen. Por eso el informe calcula la muestra efectiva y el margen.
- No tiene en cuenta la duración de cada postura mantenida, la repetitividad, la fuerza, las muñecas ni el cuello.
- La **carga** la declara el usuario; la herramienta no la ve.
- Las tablas 6 y 7 se transcribieron de Ergonautas (UPV). Si se usan para algo más que una demostración, contrástalas con la fuente original (Karhu, Kansi y Kuorinka, 1977) o con la NTP del INSST.

## REBA y RULA

- **Muñeca**: MediaPipe Pose solo da tres puntos toscos de cada mano (índice, meñique y pulgar). La flexión se estima con ellos cuando se ven y es poco fiable; la desviación radial o cubital y la pronosupinación no se miden. Sin declararlas, la puntuación es un rango.
- **No se miden**: hombro elevado, brazo apoyado, rotación del brazo, rotación o inclinación lateral de la cabeza, agarre, actividad estática o repetitiva, fuerzas bruscas, apoyo de las piernas. Se declaran; si no, se recorren todos sus valores y la puntuación sale como rango.
- **Margen de medida**: los márgenes por zona son provisionales (no calibrados). Un margen mal elegido estrecha o ensancha los rangos sin avisar.
- **Criterios de detección**: 20° de torsión o inclinación lateral, 30° de abducción y los límites del antebrazo respecto a la línea media son propios, no del método.
- **Cuello**: se aproxima con el eje hombros→orejas respecto al tronco; no distingue bien la flexión de la protrusión de la cabeza.
- **Peor postura**: se da la sostenida (mínimo en ventanas de 0,5 s) y el pico breve fiable (sin valores interpolados). Una postura mal estimada durante más de 0,5 s cuenta igual: revisa siempre las capturas.
- **De frente o de espaldas**, los ángulos vienen de la profundidad estimada por MediaPipe y son los menos fiables (en el vídeo del taller de la PoC, la flexión del tronco de espaldas sale probablemente sobreestimada).
- **Lado**: REBA usa el peor de los dos lados; un brazo oculto se recorre entero (rango). RULA se evalúa en los dos lados y se resume con el peor.
- Con varios vídeos, REBA y RULA se puntúan por vídeo; no se fusionan cámaras para la peor postura.

## Varias cámaras

- En el modo `mejor-camara` los vídeos deben estar sincronizados con los desfases indicados; no se sincronizan solos.
- No se fusionan los puntos de varias cámaras en 3D: por cada instante y región se usa una sola cámara.

## Privacidad

- Todo se procesa en local. Las salidas difuminan la cara a partir de los puntos de MediaPipe; si la persona no se detecta en un fotograma, ese fotograma no se difumina. Revísalo antes de compartir nada.
- Graba con el conocimiento y el consentimiento del trabajador.
