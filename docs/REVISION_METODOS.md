# Revisión de OWAS, REBA y RULA

Skill *estudio-ergonomico-video* · documento generado el 06/11/2026 a partir del código (`scripts/informe_revision.py`). Versión 2: incorpora la auditoría documental del 06/11/2026 y las decisiones del usuario sobre fronteras, carga, datos desconocidos y margen de medida.

> **Demostración no validada.** Este documento describe lo que hace el programa para que un experto compruebe que las tablas y las reglas son correctas. No es una evaluación de riesgos.

## Cambios desde la versión 1

| Hallazgo de la auditoría | Cambio | Estado |
|---|---|---|
| 01 · OWAS 3143 debía ser 3 | Corregida. Las 904 celdas se prueban contra una copia extraída de Ergonautas (`tests/fixtures/tablas_ergonautas.json`), no contra el propio código: 904 coincidencias. | Resuelto |
| 02 · Rodilla a 30° y brazo al nivel del hombro | Pierna flexionada si flexión ≥ 30°; brazo elevado si codo o mano están al nivel del hombro o por encima. 10 kg en OWAS: tramo 1 (convención INSST). | Resuelto |
| 03 · Cuello en RULA: giro e inclinación | Dos entradas separadas (`--cuello-girado`, `--cuello-inclinado`): +1 y +1 en RULA; +1 único en REBA. | Resuelto |
| 04 · REBA: rotación de brazo y actividad | Nueva entrada `--brazo-rotado`; la torsión de muñeca va en `--muneca-desviada` (REBA: torsión o desviación). Tres indicadores de actividad acumulables (hasta +3), solo declarados; andar no activa «repetitiva». | Resuelto |
| 05 · Tolerancias de 5° dentro de las reglas | Eliminadas. Las reglas aplican los umbrales del método; la incertidumbre va aparte como margen de medida (sección 2.1) y produce rangos. | Resuelto |
| 06 · Fronteras de RULA | En la frontera, la puntuación mayor (decisión del usuario, según las notas de McAtamney 2024 citadas por la auditoría). REBA y OWAS: lectura literal de Ergonautas. | Resuelto (falta verificar el documento de 2024) |
| 07 · Piernas de REBA/RULA | Apoyo propio de cada método con rango donde no se puede saber (arrodillado, sentado sin ver los pies, andando) y entrada `--apoyo-piernas`. Sentado: solo se suprime el +2 (lectura literal). | Provisional |
| 08 · Desconocido ≠ favorable | Tres estados (sí, no, desconocido) en todo lo declarable; lo desconocido o no visible se recorre entero y la puntuación sale como rango. Muñeca y desviación desconocidas: REBA 1–3, RULA 1–4. | Resuelto |
| 09 · Lado de RULA | Se evalúan los dos lados y se resume con el peor, sin mezclar segmentos. Se retira la cita a la NTP 601 (es de REBA). | Resuelto |
| 10 · Caso RULA neutro | Corregido: brazos colgando con codo 0° → C 2, D 1, RULA 2. Los casos completos fijan ahora todas las entradas. | Resuelto |
| Captura y estadística | OWAS usa un fotograma real por observación; «% del tiempo observable»; intervalo «aproximado» con muestra efectiva por código; pico breve fiable además del sostenido; valores interpolados marcados; semáforos como validez técnica provisional. | Resuelto en el cálculo; validación pendiente |

## Cómo se calcula: reglas en Python, no en el modelo de lenguaje

Toda la valoración es determinista. El modelo de lenguaje (Claude) solo pregunta los datos de la tarea, lanza los scripts y explica el informe; no mide, no clasifica y no puntúa.

| Paso | Qué hace | Dónde |
|---|---|---|
| 1. Pose | MediaPipe Pose Landmarker: 33 puntos 2D y 3D por fotograma (10 por segundo) | `pose.py` |
| 2. Medidas | Ángulos con fórmulas geométricas (sección 2) | `medidas.py` |
| 3. Filtros | Longitud de huesos, coherencia 2D–3D, rango, atípicos, saltos; marca lo interpolado | `filtros.py` |
| 4. Intervalos | Cada medida pasa a «valor ± margen» o «desconocido» (sección 2.1) | `config.py` |
| 5. Reglas por elemento | Cada regla devuelve el conjunto de puntuaciones posibles en el intervalo | `reglas.py` |
| 6. Tablas | Se consultan con todas las combinaciones posibles → rango [mínimo, máximo] | `tablas.py`, `ergo.py`, `clasificar.py` |
| 7. Validación | Estado del rango y semáforo de validez técnica (sección 6) | `ergo.py`, `muestreo.py` |

**Pruebas automáticas:** 1.254 pruebas. Las 904 celdas de las tablas se comparan con la copia independiente; cada umbral se prueba en a − ε, a y a + ε con el valor esperado escrito a mano; además, las pruebas de aceptación de la auditoría y posturas sintéticas calculadas a mano en tres vistas.

## Medidas

Puntos de MediaPipe: 0 nariz, 7/8 orejas, 11/12 hombros, 13/14 codos, 15/16 muñecas, 17/18 meñiques, 19/20 índices, 23/24 caderas, 25/26 rodillas, 27/28 tobillos (impar = izquierdo del trabajador). «2D» = plano de la imagen; «3D» = coordenadas *world* de MediaPipe en metros (profundidad estimada).

**2D o 3D por fotograma:** a partir de 55° de giro respecto a la cámara (de perfil) se usa 2D en tronco, cuello, brazo y rodilla; por debajo, 3D. Torsión, inclinación lateral, abducción, codo y muñeca: siempre 3D.

| Medida | Definición | Cálculo | Se usa en |
|---|---|---|---|
| Tronco | Ángulo hombros−caderas con la vertical en el plano sagital; + flexión, − extensión. OWAS usa su magnitud (rango del filtro 0–130°); REBA/RULA, el valor con signo (−60 a 130°) | 2D de perfil / 3D | OWAS, REBA, RULA |
| Inclinación lateral / torsión | Eje del tronco fuera del plano sagital / línea de hombros frente a caderas en el horizontal | 3D | OWAS, REBA, RULA |
| Cuello | Orejas − hombros respecto al eje del tronco (indicador geométrico, no anatómico) | 2D / 3D | REBA, RULA |
| Brazo | Codo − hombro respecto al tronco; − si va detrás y por debajo de 90°; abducción fuera del plano sagital | 2D / 3D | REBA, RULA |
| Codo | 180° − ángulo interno | 3D | REBA, RULA |
| Muñeca (estimada) | Ángulo antebrazo–mano con índice y meñique; mezcla flexión y desviación | 3D | REBA, RULA |
| Antebrazo/línea media | Posición lateral de la muñeca en semianchos de hombros | 3D | RULA |
| Altura del brazo | Codo o muñeca (el más alto) sobre el hombro, en longitudes de tronco | 2D | OWAS |
| Rodilla, muslo, pantorrilla, tobillos, velocidad | Flexión; ángulos con la vertical; diferencia de altura; desplazamiento de la cadera | 2D / 3D | OWAS, apoyo REBA/RULA |

### 2.1 Margen de medida (provisional)

Decisión del usuario: márgenes provisionales por zona hasta calibrarlos con vídeos anotados. Si «valor ± margen» cruza un umbral, la regla devuelve las dos puntuaciones. De frente o de espaldas (3D con giro < 25°) el margen se multiplica por 1,5. Las reglas no llevan tolerancias propias.

| Medida | Margen |
|---|---|
| tronco flex | 5 |
| tronco sag | 5 |
| tronco lat | 5 |
| tronco giro | 5 |
| cuello | 5 |
| brazo flex | 10 |
| brazo abd | 10 |
| codo | 10 |
| rodilla | 10 |
| muslo | 10 |
| pierna | 10 |
| muneca | 15 |
| brazo alt | 0,15 |
| antebrazo lat | 0,3 |
| tobillos | 0,03 |
| velocidad | 0,2 |

## OWAS

Tablas: Ergonautas (UPV), [método OWAS](https://www.ergonautas.upv.es/metodos/owas/owas-ayuda.php). Original: Karhu, Kansi y Kuorinka (1977). Fronteras literales de Ergonautas; pierna flexionada si flexión ≥ 30° (muslo-pantorrilla ≤ 150°); brazo elevado si codo o muñeca están al nivel del hombro o por encima; carga según INSST (≤ 10 kg → 1).

### 3.1 Codificación

| Región | Código | Descripción | Regla del programa | Origen |
|---|---|---|---|---|
| Espalda | 2 | Espalda doblada | \|flexión\| > 20° | Método |
| Espalda | 3 | Espalda con giro | torsión > 20° o inclinación lateral > 20° | Método |
| Espalda | 4 | Espalda doblada con giro | 2 y 3 a la vez | Método |
| Brazos | 1–3 | 1 + brazos elevados | Elevado si codo o muñeca ≥ nivel del hombro | Método (INSST: «al nivel o por encima») |
| Piernas | 2 · 3 · 4 · 5 | De pie | Flexionada si flexión ≥ 30°; 5 si las dos flexionadas y difieren > 30° o se apoya en una flexionada con el otro pie levantado (> 8 cm) | Método + heurística propia (peso) |
| Piernas | 1 · 6 · 7 | Sentado · arrodillado · andando | Sentado: muslo ≥ 55°, pantorrilla ≤ 35°, rodillas ≤ 120°; arrodillado: pantorrilla > 60° y rodilla > 60°; andando: > 0,6 troncos/s | Heurística propia, provisional |
| Carga | 1–3 | INSST: ≤ 10 kg → 1; > 10 y ≤ 20 kg → 2; > 20 kg → 3 | Declarada; sin declarar → 1–3 | Método (convención INSST) |

**Lo que no se ve** (un brazo, una pierna, la torsión, la carga) ya no se rellena: la observación tiene un código nominal desconocido y un conjunto de códigos posibles que entra en los rangos.

### 3.2 Tabla 6: categoría por combinación

| Espalda · brazos | P1·C1 | P1·C2 | P1·C3 | P2·C1 | P2·C2 | P2·C3 | P3·C1 | P3·C2 | P3·C3 | P4·C1 | P4·C2 | P4·C3 | P5·C1 | P5·C2 | P5·C3 | P6·C1 | P6·C2 | P6·C3 | P7·C1 | P7·C2 | P7·C3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1 · B1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 1 | 1 | 1 | 1 | 1 |
| E1 · B2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 1 | 1 | 1 | 1 | 1 |
| E1 · B3 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 3 | 2 | 2 | 3 | 1 | 1 | 1 | 1 | 1 | 2 |
| E2 · B1 | 2 | 2 | 3 | 2 | 2 | 3 | 2 | 2 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 2 | 2 | 2 | 3 | 3 |
| E2 · B2 | 2 | 2 | 3 | 2 | 2 | 3 | 2 | 3 | 3 | 3 | 4 | 4 | 3 | 4 | 4 | 3 | 3 | 4 | 2 | 3 | 4 |
| E2 · B3 | 3 | 3 | 4 | 2 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 4 |
| E3 · B1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 1 | 1 | 1 | 1 | 1 | 1 |
| E3 · B2 | 2 | 2 | 3 | 1 | 1 | 1 | 1 | 1 | 2 | 4 | 4 | 4 | 4 | 4 | 4 | 3 | 3 | 3 | 1 | 1 | 1 |
| E3 · B3 | 2 | 2 | 3 | 1 | 1 | 1 | 2 | 3 | 3 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 1 | 1 | 1 |
| E4 · B1 | 2 | 3 | 3 | 2 | 2 | 3 | 2 | 2 | 3 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 4 |
| E4 · B2 | 3 | 3 | 4 | 2 | 3 | 4 | 3 | 3 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 4 |
| E4 · B3 | 4 | 4 | 4 | 2 | 3 | 4 | 3 | 3 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 4 |

*E = espalda, B = brazos, P = piernas, C = carga. Celda E3·B1·P4·C3 corregida a 3.*

### 3.3 Tabla 7: categoría por frecuencia

| Código | ≤ 10 % | ≤ 20 % | ≤ 30 % | ≤ 40 % | ≤ 50 % | ≤ 60 % | ≤ 70 % | ≤ 80 % | ≤ 90 % | ≤ 100 % |
|---|---|---|---|---|---|---|---|---|---|---|
| Espalda 1 · Espalda derecha | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Espalda 2 · Espalda doblada | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 3 | 3 |
| Espalda 3 · Espalda con giro | 1 | 1 | 2 | 2 | 2 | 3 | 3 | 3 | 3 | 3 |
| Espalda 4 · Espalda doblada con giro | 1 | 2 | 2 | 3 | 3 | 3 | 3 | 4 | 4 | 4 |
| Brazos 1 · Los dos brazos bajos | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Brazos 2 · Un brazo bajo y el otro elevado | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 3 | 3 |
| Brazos 3 · Los dos brazos elevados | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 3 | 3 | 3 |
| Piernas 1 · Sentado | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |
| Piernas 2 · De pie con las dos piernas rectas | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 |
| Piernas 3 · De pie con una pierna recta y la otra flexionada | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 3 | 3 |
| Piernas 4 · De pie o en cuclillas, piernas flexionadas, peso equilibrado | 1 | 2 | 2 | 3 | 3 | 3 | 3 | 4 | 4 | 4 |
| Piernas 5 · De pie o en cuclillas, piernas flexionadas, peso desequilibrado | 1 | 2 | 2 | 3 | 3 | 3 | 3 | 4 | 4 | 4 |
| Piernas 6 · Arrodillado | 1 | 1 | 2 | 2 | 2 | 3 | 3 | 3 | 3 | 3 |
| Piernas 7 · Andando | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 |

### 3.4 Categorías de acción

| Categoría | Carga postural | Acción |
|---|---|---|
| 1 | Postura normal | No requiere acción. |
| 2 | Posible daño musculoesquelético | Se requieren acciones correctivas en un futuro cercano. |
| 3 | Efectos dañinos | Se requieren acciones correctivas lo antes posible. |
| 4 | Efectos sumamente dañinos | Se requieren acciones correctivas inmediatamente. |

*Descripción limitada a la carga postural evaluada; una categoría 1 no acredita la ausencia de otros riesgos.*

### 3.5 Muestreo y estadística

- Una observación cada 1 s con **un fotograma real** (el más cercano con más regiones medidas, dentro de ±0,2 s).
- **% nominal del tiempo observable:** sobre las observaciones con código nominal conocido.
- **Intervalo aproximado:** Wilson con una muestra efectiva por código (duración con datos / 2 × tiempo de decorrelación de la serie indicadora de ese código). Su cobertura del 95 % no está verificada.
- **Rango:** % mínimo (observaciones donde el código es seguro) y máximo (donde es posible) sobre todas las observaciones, con margen y datos que faltan.

### 3.6 Comprobaciones de frontera (reglas reales, sin margen)

| Región | Entrada | Resultado del programa |
|---|---|---|
| Espalda | flexión 19,99° | 1 |
| Espalda | flexión 20° | 1 |
| Espalda | flexión 20,01° | 2 |
| Espalda | torsión 20° | 1 |
| Espalda | torsión 20,01° | 3 |
| Brazos | altura -0,01 troncos (un brazo) | 1 |
| Brazos | altura 0 troncos (un brazo) | 2 |
| Pierna | flexión 29,99° | recta |
| Pierna | flexión 30° | flexionada |
| Piernas | rodillas 30° y 30°, de pie, pies a la misma altura | 4 |
| Carga | 10 kg | 1 |
| Carga | 10,01 kg | 2 |
| Carga | 20 kg | 2 |
| Carga | 20,01 kg | 3 |
| Brazo izq. oculto | dch. bajo | 1–2 |
| Torsión no medible | flexión 30° | 2–4 |

## REBA

Tablas: Ergonautas (UPV), [método REBA](https://www.ergonautas.upv.es/metodos/reba/reba-ayuda.php), y NTP 601. Original: Hignett y McAtamney (2000). Fronteras literales de Ergonautas/NTP 601 (el valor límite va en el tramo que lo incluye con «≤»).

### 4.1 Elementos

| Elemento | Método | Regla del programa | Si se desconoce |
|---|---|---|---|
| Tronco | 1 erguido · 2 flex./ext. 0–20° · 3 flex. 20–60° o ext. > 20° · 4 > 60° | 0° → 1; −20° a 20° → 2; < −20° o ≤ 60° → 3; > 60° → 4 | 1–4 |
| Tronco +1 | Inclinación lateral o rotación | Presente si > 20° (criterio de detección provisional) | +0 o +1 |
| Cuello | 1 flexión 0–20° · 2 > 20° o extensión | 0° a 20° → 1; resto (incluida cualquier extensión) → 2 | 1–2 |
| Cuello +1 | Rotado o inclinado | Declarados por separado; +1 si cualquiera | +0 o +1 |
| Piernas | 1 sentado, andando o bilateral · 2 unilateral o inestable | Apoyo declarado o desde OWAS: 3, 5 → 2; 6 → 1–2; resto → 1 | 1–2 |
| Rodillas | +1 30–60° · +2 > 60° (salvo sentado) | ≥ 30° y ≤ 60° → +1; > 60° → +2; sentado y > 60° → 0 | 0–2 |
| Carga | < 5 kg 0 · 5–10 +1 · > 10 +2; brusca +1 | Declarada | 0–3 |
| Brazo | 1 −20° a 20° · 2 ext. > 20° o 20–45° · 3 45–90° · 4 > 90° | −20° ≤ x ≤ 20° → 1; < −20° o ≤ 45° → 2; ≤ 90° → 3; > 90° → 4 | 1–4 |
| Brazo ± | +1 abducido o rotado · +1 hombro elevado · −1 apoyo | Abducción > 30° (criterio provisional) o rotación declarada | rango |
| Antebrazo | 1 60–100° · 2 resto | 60° ≤ x ≤ 100° → 1 | 1–2 |
| Muñeca | 1 ≤ 15° · 2 > 15°; +1 torsión o desviación | Declarada o estimada | 1–3 (con desviación desconocida) |
| Agarre | 0–3 | Declarado | 0–3 |
| Actividad | +1 estática · +1 repetitiva · +1 cambios bruscos | Declarada; acumulable hasta +3 | 0–3 |

**Lados:** se calcula el grupo B de los dos brazos y se toma el peor; un brazo oculto se recorre entero. **Final** = tabla C(A + carga, B + agarre) + actividad, con A y B por encima de 12 en la fila o columna 12.

### 4.2 Tabla A (tronco × cuello × piernas)

| Tronco | Cu1·P1 | Cu1·P2 | Cu1·P3 | Cu1·P4 | Cu2·P1 | Cu2·P2 | Cu2·P3 | Cu2·P4 | Cu3·P1 | Cu3·P2 | Cu3·P3 | Cu3·P4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 2 | 3 | 4 | 1 | 2 | 3 | 4 | 3 | 3 | 5 | 6 |
| 2 | 2 | 3 | 4 | 5 | 3 | 4 | 5 | 6 | 4 | 5 | 6 | 7 |
| 3 | 2 | 4 | 5 | 6 | 4 | 5 | 6 | 7 | 5 | 6 | 7 | 8 |
| 4 | 3 | 5 | 6 | 7 | 5 | 6 | 7 | 8 | 6 | 7 | 8 | 9 |
| 5 | 4 | 6 | 7 | 8 | 6 | 7 | 8 | 9 | 7 | 8 | 9 | 9 |

### 4.3 Tabla B (brazo × antebrazo × muñeca)

| Brazo | A1·M1 | A1·M2 | A1·M3 | A2·M1 | A2·M2 | A2·M3 |
|---|---|---|---|---|---|---|
| 1 | 1 | 2 | 2 | 1 | 2 | 3 |
| 2 | 1 | 2 | 3 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 | 4 | 5 | 5 |
| 4 | 4 | 5 | 5 | 5 | 6 | 7 |
| 5 | 6 | 7 | 8 | 7 | 8 | 8 |
| 6 | 7 | 8 | 8 | 8 | 9 | 9 |

### 4.4 Tabla C (A × B)

| A \ B | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 2 | 3 | 3 | 4 | 5 | 6 | 7 | 7 | 7 |
| 2 | 1 | 2 | 2 | 3 | 4 | 4 | 5 | 6 | 6 | 7 | 7 | 8 |
| 3 | 2 | 3 | 3 | 3 | 4 | 5 | 6 | 7 | 7 | 8 | 8 | 8 |
| 4 | 3 | 4 | 4 | 4 | 5 | 6 | 7 | 8 | 8 | 9 | 9 | 9 |
| 5 | 4 | 4 | 4 | 5 | 6 | 7 | 8 | 8 | 9 | 9 | 9 | 9 |
| 6 | 6 | 6 | 6 | 7 | 8 | 8 | 9 | 9 | 10 | 10 | 10 | 10 |
| 7 | 7 | 7 | 7 | 8 | 9 | 9 | 9 | 10 | 10 | 11 | 11 | 11 |
| 8 | 8 | 8 | 8 | 9 | 10 | 10 | 10 | 10 | 10 | 11 | 11 | 11 |
| 9 | 9 | 9 | 9 | 10 | 10 | 10 | 11 | 11 | 11 | 12 | 12 | 12 |
| 10 | 10 | 10 | 10 | 11 | 11 | 11 | 11 | 12 | 12 | 12 | 12 | 12 |
| 11 | 11 | 11 | 11 | 11 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |

### 4.5 Niveles de actuación

| Puntuación desde | Nivel | Riesgo | Actuación |
|---|---|---|---|
| 1 | 0 | Inapreciable | No es necesaria actuación. |
| 2 | 1 | Bajo | Puede ser necesaria la actuación. |
| 4 | 2 | Medio | Es necesaria la actuación. |
| 8 | 3 | Alto | Es necesaria la actuación cuanto antes. |
| 11 | 4 | Muy alto | Es necesaria la actuación de inmediato. |

*Se rechazan puntuaciones fuera de 1–15.*

### 4.6 Comprobaciones de frontera (reglas reales, sin margen)

| Elemento | Entrada | Puntuación del programa |
|---|---|---|
| Tronco | -20,01° | 3 |
| Tronco | -20° | 2 |
| Tronco | -0,01° | 2 |
| Tronco | 0° | 1 |
| Tronco | 0,01° | 2 |
| Tronco | 20° | 2 |
| Tronco | 20,01° | 3 |
| Tronco | 60° | 3 |
| Tronco | 60,01° | 4 |
| Cuello | -0,01° | 2 |
| Cuello | 0° | 1 |
| Cuello | 20° | 1 |
| Cuello | 20,01° | 2 |
| Brazo | -20,01° | 2 |
| Brazo | -20° | 1 |
| Brazo | 20° | 1 |
| Brazo | 20,01° | 2 |
| Brazo | 45° | 2 |
| Brazo | 45,01° | 3 |
| Brazo | 90° | 3 |
| Brazo | 90,01° | 4 |
| Antebrazo | codo 59,99° | 2 |
| Antebrazo | codo 60° | 1 |
| Antebrazo | codo 100° | 1 |
| Antebrazo | codo 100,01° | 2 |
| Muñeca | 15° | 1 |
| Muñeca | 15,01° | 2 |
| Rodillas | 29,99° | 0 |
| Rodillas | 30° | 1 |
| Rodillas | 60° | 1 |
| Rodillas | 60,01° | 2 |
| Rodillas | 45° sentado | 1 |
| Rodillas | 60,01° sentado | 0 |
| Carga | 4,99 kg | 0 |
| Carga | 5 kg | 1 |
| Carga | 10 kg | 1 |
| Carga | 10,01 kg | 2 |
| Muñeca y desviación | desconocidas | 1–3 |

## RULA

Tablas: Ergonautas (UPV), [método RULA](https://www.ergonautas.upv.es/metodos/rula/rula-ayuda.php). Original: McAtamney y Corlett (1993). En la frontera entre dos puntuaciones, la mayor (McAtamney, 2024, según la auditoría; pendiente de verificar el documento).

### 5.1 Elementos

| Elemento | Método | Regla del programa (en la frontera, la mayor) | Si se desconoce |
|---|---|---|---|
| Brazo | 1 −20° a 20° · 2 ext. > 20° o 20–45° · 3 45–90° · 4 > 90° | −20° < x < 20° → 1; ≤ −20° o < 45° → 2; < 90° → 3; ≥ 90° → 4 | 1–4 |
| Brazo ± | +1 hombro elevado · +1 abducido · −1 apoyo (original 1993) | Abducción > 30° (provisional); la rotación de Ergonautas no se suma | rango |
| Antebrazo | 1 60–100° · 2 resto; +1 a un lado o cruza la línea media | 60° < x < 100° → 1; +1 si muñeca ≤ 0 o ≥ 2 semianchos (provisional) | 1–3 |
| Muñeca | 1 neutra · 2 0–15° · 3 > 15°; +1 desviación | 0° → 1; < 15° → 2; ≥ 15° → 3 | 1–4 (con desviación desconocida) |
| Giro de muñeca | 1 medio · 2 extremo | Declarado | 1–2 |
| Cuello | 1 0–10° · 2 10–20° · 3 > 20° · 4 extensión; +1 rotado; +1 inclinado | < 0° → 4; < 10° → 1; < 20° → 2; ≥ 20° → 3; +1 y +1 declarados | 1–6 |
| Tronco | 1 erguido · 2 0–20° · 3 20–60° · 4 > 60°; +1 rotado; +1 inclinado | 0° → 1; < 20° → 2; < 60° → 3; ≥ 60° → 4; extensión por magnitud (adaptación); +1 y +1 si > 20° | 1–6 |
| Piernas | 1 bien apoyadas y peso simétrico · 2 no | Apoyo declarado o desde OWAS: 2, 4 → 1; 3, 5 → 2; 1, 6, 7 → 1–2 | 1–2 |
| Actividad muscular | +1 estática > 1 min o repetitiva > 4/min | Declarada | 0–1 |
| Carga/fuerza | 0 < 2 kg · 1 2–10 kg interm. · 2 2–10 estát./rep. o > 10 interm. · 3 > 10 estát./rep. o golpes | 2 kg y 10 kg suben de tramo | 0–3 |

**Lados:** se evalúan los dos y se resume con el peor. **Final** = tabla C(C, D) con C ≥ 8 en la fila 8+ y D ≥ 7 en la columna 7+; se conservan C y D originales.

### 5.2 Tabla A

| Brazo · antebrazo | M1·G1 | M1·G2 | M2·G1 | M2·G2 | M3·G1 | M3·G2 | M4·G1 | M4·G2 |
|---|---|---|---|---|---|---|---|---|
| 1 · 1 | 1 | 2 | 2 | 2 | 2 | 3 | 3 | 3 |
| 1 · 2 | 2 | 2 | 2 | 2 | 3 | 3 | 3 | 3 |
| 1 · 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 4 |
| 2 · 1 | 2 | 3 | 3 | 3 | 3 | 4 | 4 | 4 |
| 2 · 2 | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 4 |
| 2 · 3 | 3 | 4 | 4 | 4 | 4 | 4 | 5 | 5 |
| 3 · 1 | 3 | 3 | 4 | 4 | 4 | 4 | 5 | 5 |
| 3 · 2 | 3 | 4 | 4 | 4 | 4 | 4 | 5 | 5 |
| 3 · 3 | 4 | 4 | 4 | 4 | 4 | 5 | 5 | 5 |
| 4 · 1 | 4 | 4 | 4 | 4 | 4 | 5 | 5 | 5 |
| 4 · 2 | 4 | 4 | 4 | 4 | 4 | 5 | 5 | 5 |
| 4 · 3 | 4 | 4 | 4 | 5 | 5 | 5 | 6 | 6 |
| 5 · 1 | 5 | 5 | 5 | 5 | 5 | 6 | 6 | 7 |
| 5 · 2 | 5 | 6 | 6 | 6 | 6 | 7 | 7 | 7 |
| 5 · 3 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 |
| 6 · 1 | 7 | 7 | 7 | 7 | 7 | 8 | 8 | 9 |
| 6 · 2 | 8 | 8 | 8 | 8 | 8 | 9 | 9 | 9 |
| 6 · 3 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 |

### 5.3 Tabla B

| Cuello | T1·P1 | T1·P2 | T2·P1 | T2·P2 | T3·P1 | T3·P2 | T4·P1 | T4·P2 | T5·P1 | T5·P2 | T6·P1 | T6·P2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 3 | 2 | 3 | 3 | 4 | 5 | 5 | 6 | 6 | 7 | 7 |
| 2 | 2 | 3 | 2 | 3 | 4 | 5 | 5 | 5 | 6 | 7 | 7 | 7 |
| 3 | 3 | 3 | 3 | 4 | 4 | 5 | 5 | 6 | 6 | 7 | 7 | 7 |
| 4 | 5 | 5 | 5 | 6 | 6 | 7 | 7 | 7 | 7 | 7 | 8 | 8 |
| 5 | 7 | 7 | 7 | 7 | 7 | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| 6 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 9 | 9 | 9 | 9 | 9 |

### 5.4 Tabla C

| C \ D | 1 | 2 | 3 | 4 | 5 | 6 | 7+ |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 2 | 3 | 3 | 4 | 5 | 5 |
| 2 | 2 | 2 | 3 | 4 | 4 | 5 | 5 |
| 3 | 3 | 3 | 3 | 4 | 4 | 5 | 6 |
| 4 | 3 | 3 | 3 | 4 | 5 | 6 | 6 |
| 5 | 4 | 4 | 4 | 5 | 6 | 7 | 7 |
| 6 | 4 | 4 | 5 | 6 | 6 | 7 | 7 |
| 7 | 5 | 5 | 6 | 6 | 7 | 7 | 7 |
| 8+ | 5 | 5 | 6 | 7 | 7 | 7 | 7 |

### 5.5 Niveles de actuación

| Puntuación desde | Nivel | Etiqueta | Actuación |
|---|---|---|---|
| 1 | 1 | Nivel 1 | Postura aceptable si no se mantiene ni se repite durante largos periodos. |
| 3 | 2 | Nivel 2 | Pueden requerirse cambios en la tarea; conviene profundizar en el estudio. |
| 5 | 3 | Nivel 3 | Se requiere el rediseño de la tarea. |
| 7 | 4 | Nivel 4 | Se requieren cambios urgentes en la tarea. |

*Sin etiquetas de riesgo propias: solo nivel y actuación. Se rechazan puntuaciones fuera de 1–7.*

### 5.6 Comprobaciones de frontera (reglas reales, sin margen)

| Elemento | Entrada | Puntuación del programa |
|---|---|---|
| Brazo | -20,01° | 2 |
| Brazo | -20° | 2 |
| Brazo | 19,99° | 1 |
| Brazo | 20° | 2 |
| Brazo | 44,99° | 2 |
| Brazo | 45° | 3 |
| Brazo | 89,99° | 3 |
| Brazo | 90° | 4 |
| Antebrazo (muñeca en 1 semiancho) | codo 60° | 2 |
| Antebrazo (muñeca en 1 semiancho) | codo 60,01° | 1 |
| Antebrazo (muñeca en 1 semiancho) | codo 99,99° | 1 |
| Antebrazo (muñeca en 1 semiancho) | codo 100° | 2 |
| Antebrazo (codo 80°) | muñeca a 0 semianchos | 2 |
| Antebrazo (codo 80°) | muñeca a 0,01 semianchos | 1 |
| Antebrazo (codo 80°) | muñeca a 2 semianchos | 2 |
| Muñeca | 0° | 1 |
| Muñeca | 0,01° | 2 |
| Muñeca | 14,99° | 2 |
| Muñeca | 15° | 3 |
| Cuello | -0,01° | 4 |
| Cuello | 0° | 1 |
| Cuello | 9,99° | 1 |
| Cuello | 10° | 2 |
| Cuello | 19,99° | 2 |
| Cuello | 20° | 3 |
| Cuello | 5°, rotado e inclinado | 3 |
| Tronco | 0° | 1 |
| Tronco | 0,01° | 2 |
| Tronco | 19,99° | 2 |
| Tronco | 20° | 3 |
| Tronco | 59,99° | 3 |
| Tronco | 60° | 4 |
| Tronco | -25° | 3 |
| Carga/fuerza | 1,99 kg, intermitente | 0 |
| Carga/fuerza | 2 kg, intermitente | 1 |
| Carga/fuerza | 9,99 kg, intermitente | 1 |
| Carga/fuerza | 10 kg, intermitente | 2 |
| Carga/fuerza | 9,99 kg, estática | 2 |
| Carga/fuerza | 10 kg, estática | 3 |
| Muñeca y desviación | desconocidas | 1–4 |

### 5.7 Casos completos (todas las entradas fijadas)

| Postura (lado izq. en RULA) | REBA A | REBA B | REBA | RULA C | RULA D | RULA |
|---|---|---|---|---|---|---|
| De pie; tronco, cuello y brazos a 0°; codos 0° (colgando); muñeca neutra declarada; sin carga, agarre bueno, sin actividad; nada rotado ni elevado | 1 | 1 | 1 | 2 | 1 | 2 |
| Tronco 50°, cuello 30°, rodillas 50° (pies a la misma altura), brazos 50° respecto al tronco, codos 90°, muñeca neutra; 12 kg, agarre regular, repetitiva; resto declarado «no» | 7 | 4 | 9 | 7 | 8 | 7 |
| Brazo izq. a 100° abducido (80° fuera del plano sagital), codo 0°, muñeca a 3,7 semianchos; resto como el primero | 1 | 7 | 4 | 6 | 1 | 4 |
| Como el primero, pero sin declarar nada (todo desconocido) | 1–4 | 1–8 | 1–11 | 2–7 | 1–7 | 2–7 |

## Estado del resultado y validez técnica

Los colores miden cobertura y certeza del cálculo con convenciones provisionales, no la exactitud de la medida ni el nivel de riesgo.

| Método | Comprobación | Verde | Ámbar | Rojo |
|---|---|---|---|---|
| REBA, RULA | Estado del rango de la peor postura | un nivel de actuación (concluyente) | dos niveles contiguos (acotada) | más (incompleta) |
| REBA | Fotogramas con los dos brazos y el tronco medidos | ≥ 70 % | ≥ 40 % | < 40 % |
| RULA | Fotogramas con el brazo del lado y el tronco medidos | ≥ 70 % | ≥ 40 % | < 40 % |
| REBA, RULA | Peor postura de frente o de espaldas (3D, giro < 25°) | — | sí | — |
| REBA, RULA | Hueco > 1 s junto a una postura a 1 punto del pico | — | sí | — |
| OWAS | Observaciones con código nominal conocido | ≥ 80 % | ≥ 50 % | menos |
| OWAS | Intervalo aproximado del % de tiempo | ≤ ±10 | ≤ ±20 | más |
| OWAS | Duración | ≥ 20 min | < 20 min | — |

**Peor postura (REBA, RULA):** sostenida (máximo de la puntuación mínima en ventanas de 0,5 s) y pico breve fiable (máximo en fotogramas sin valores interpolados, con su duración). Si el pico breve supera a la sostenida, se avisa para revisarlo en el vídeo.

## Filtros mecánicos (parámetros pendientes de calibración)

| Filtro | Valor |
|---|---|
| Visibilidad mínima de un punto (probabilidad de MediaPipe) | 0,5 |
| Visibilidad mínima para la torsión (prevalece sobre la general solo en esa medida) | 0,3 |
| Longitud de huesos 3D: variación máxima respecto a la mediana | 30 % |
| Atípicos (Hampel): semiventana · MAD · mínimo | 0,5 s · 3 · 12° |
| Saltos imposibles: tramo mínimo entre saltos | 0,4 s |
| Relleno de huecos (se marca como interpolado) | hasta 0,3 s |

| Medida | Rango | Velocidad máxima |
|---|---|---|
| Flexión del tronco | 0 a 130 ° | 300 °/s |
| Inclinación lateral del tronco | 0 a 60 ° | 300 °/s |
| Torsión del tronco | 0 a 90 ° | 300 °/s |
| Altura mano/codo izq. sobre el hombro | -4 a 3 tronco | 8 tronco/s |
| Altura mano/codo dch. sobre el hombro | -4 a 3 tronco | 8 tronco/s |
| Flexión rodilla izq. | 0 a 165 ° | 400 °/s |
| Flexión rodilla dch. | 0 a 165 ° | 400 °/s |
| Muslo izq. respecto a la vertical | 0 a 160 ° | 400 °/s |
| Muslo dch. respecto a la vertical | 0 a 160 ° | 400 °/s |
| Pantorrilla izq. respecto a la vertical | 0 a 120 ° | 400 °/s |
| Pantorrilla dch. respecto a la vertical | 0 a 120 ° | 400 °/s |
| Flexión (+) o extensión (−) del tronco | -60 a 130 ° | 300 °/s |
| Flexión (+) o extensión (−) del cuello | -60 a 90 ° | 300 °/s |
| Flexión del brazo izq. | -90 a 190 ° | 600 °/s |
| Flexión del brazo dch. | -90 a 190 ° | 600 °/s |
| Abducción del brazo izq. | 0 a 90 ° | 600 °/s |
| Abducción del brazo dch. | 0 a 90 ° | 600 °/s |
| Flexión del codo izq. | 0 a 165 ° | 700 °/s |
| Flexión del codo dch. | 0 a 165 ° | 700 °/s |
| Flexión de la muñeca izq. (estimada) | 0 a 100 ° | 800 °/s |
| Flexión de la muñeca dch. (estimada) | 0 a 100 ° | 800 °/s |
| Muñeca izq. respecto a la línea media | -3 a 5 semiancho | 12 semiancho/s |
| Muñeca dch. respecto a la línea media | -3 a 5 semiancho | 12 semiancho/s |
| Altura tobillo izq. − dch. | -0,7 a 0,7 m | 4 m/s |

## Puntos abiertos

| Ref. | Decisión | Estado | Valor actual |
|---|---|---|---|
| P1, P4, P5 | Tolerancias de neutralidad | Resuelto | Sin tolerancias en las reglas; margen de medida aparte |
| P2, P3 | Detección de torsión/inclinación y abducción (REBA/RULA) | Pendiente del experto | > 20° y > 30°, provisionales |
| P6 | Extensión del tronco en RULA | Pendiente del experto | Adaptación: por magnitud (≤ 20° → 2; < 60° → 3) |
| P7 | Brazo elevado en OWAS | Resuelto | Codo o muñeca al nivel del hombro o por encima |
| P8 | Antebrazo a un lado o cruzando (RULA) | Pendiente del experto | ≤ 0 / ≥ 2 semianchos |
| P9 | Piernas REBA/RULA | Provisional | Apoyo con rango y declaración; falta validar con vídeos |
| P10 | Rodillas sentado (REBA) | Resuelto (lectura literal) | Solo se suprime el +2 |
| P11 | Datos no declarados | Resuelto | Rango completo |
| P12 | Peor postura | Resuelto | Sostenida + pico breve fiable |
| P13 | REBA con un brazo oculto | Resuelto | El brazo oculto se recorre entero (rango) |
| P14 | Lado de RULA | Resuelto | Los dos lados; resumen con el peor |
| P15 | Heurísticas OWAS de andar, sentado, arrodillado | Pendiente de validación | Provisionales |
| P16 | Intervalo y muestra efectiva OWAS | Provisional | 1 s; intervalo «aproximado» |
| P17 | Semáforos | Resuelto en la presentación | «Validez técnica provisional» |
| P18 | Etiquetas de RULA | Resuelto | Solo nivel y actuación |
| P19 | Fronteras de RULA (notas de 2024) | Pendiente de verificar el documento | En la frontera, la mayor |
| P20 | Márgenes de medida | Provisional | Sección 2.1; calibrar con vídeos anotados |

**Validación propuesta:** vídeos reales independientes (personas y vídeos distintos para calibrar y para probar), con oclusiones y distintas cámaras, anotados por un ergónomo. Informar error angular, matriz de confusión por código OWAS, acuerdo por nivel de actuación y, sobre todo, las subestimaciones. Kappa sin ponderar para los códigos OWAS de piernas (nominales); para REBA y RULA, además del ICC, acuerdo ordinal por nivel.

## Fuentes

- Ergonautas (UPV): ayudas de OWAS, REBA y RULA (tablas extraídas el 06/11/2026 a `tests/fixtures`).
- INSST. NTP 601: método REBA. INSHT (2015), *Posturas de trabajo: evaluación del riesgo* (OWAS, figuras 5 y 6).
- Karhu, Kansi y Kuorinka (1977), OWAS. Hignett y McAtamney (2000), REBA. McAtamney y Corlett (1993), RULA.
- McAtamney (2024), notas para usar RULA, citadas por la auditoría (selección de lado y fronteras): pendiente de verificar.
- Aghazadeh y Xiong: preprint SSRN 6035502; la auditoría cita una versión publicada (DOI 10.1016/j.ergon.2026.104061), pendiente de verificar.
- Auditoría documental de OWAS, REBA y RULA, 06/11/2026.
