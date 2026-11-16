# Revisión visual del esqueleto y de la tarea

Instrucciones para Claude cuando hace de revisor (como Gemini Argon en la PoC postura-poc). Se generan las láminas con:

```bash
.venv\Scripts\python scripts\estudio_video.py revisar --video <v.mp4> --salida <carpeta>
```

Cada lámina muestra varios instantes; en cada fila, el mismo fotograma dos veces:
- **izquierda:** el original (con la cara difuminada);
- **derecha:** el esqueleto de MediaPipe: **AZUL = lado izquierdo del trabajador**, **NARANJA = lado derecho**, blanco = tronco. Solo se dibujan las articulaciones que MediaPipe considera visibles. El tiempo (s) está arriba a la izquierda.

Mira **todas** las láminas con la herramienta de lectura de imágenes y rellena la plantilla `revision_<vídeo>.json` que deja el comando. **No decides qué se corrige: solo informas.** Un programa aplica reglas fijas a lo que digas. Lo aprendido en la PoC: la IA es buen auditor y mal filtro automático; aporta contexto y detecta lo plausible pero inventado, pero se equivoca de lado y se pasa de estricta. Por eso la política está en código y el usuario confirma el contexto.

## 1. Contexto de la tarea (`contexto`)

Usa las definiciones exactas de los métodos. Si un dato no se puede saber por el vídeo, pon `"no_se_sabe"` o `null`; **no lo supongas**.

| Campo | Valores | Criterio |
|---|---|---|
| `tarea` | texto | Qué hace, en una frase |
| `postura_base` | `sentado`, `de_pie`, `no_se_sabe` | Si está sentado todo el vídeo, di `sentado` aunque las piernas no se vean: OWAS piernas 1 y REBA/RULA no necesitan verlas |
| `apoyo_piernas` | `bilateral`, `unilateral`, `no_se_sabe` | Sentado con los pies apoyados o de pie con el peso repartido → `bilateral` |
| `rodillas` | `menos30`, `30a60`, `mas60`, `no_se_sabe` | Solo si no se ven en el vídeo pero se puede inferir (p. ej. sentado en una silla normal → `mas60`) |
| `carga_kg_estimada` | número o `null` | Peso aproximado de lo que manipula; justifícalo en `carga_evidencia` |
| `agarre` | `bueno`, `regular`, `malo`, `inaceptable`, `no_se_sabe` | Bueno: asa o agarre bien adaptado y fuerza media. Regular: aceptable pero no ideal. Malo: posible pero no aceptable. Inaceptable: incómodo o inseguro |
| `actividad.estatica` | `true`, `false`, `null` | Alguna parte del cuerpo mantenida **más de 1 minuto**. Unos segundos no es estática |
| `actividad.repetitiva` | `true`, `false`, `null` | **Más de 4 repeticiones por minuto** (sin contar andar). Solo si el vídeo muestra varios ciclos (`ciclos_observados`) |
| `actividad.cambios` | `true`, `false`, `null` | Cambios de postura importantes o rápidos, o base inestable |
| `fuerza_brusca` | `true`, `false`, `null` | Golpes o fuerzas aplicadas bruscamente |
| `hombro_elevado`, `brazo_apoyado`, `brazo_rotado` | `true`, `false`, `null` | Lo que se ve en la imagen original |
| `cuello_girado`, `cuello_inclinado` | `true`, `false`, `null` | Rotación e inclinación lateral de la cabeza, por separado |
| `observaciones` | texto | Lo útil para la evaluación que no encaje arriba |
| `confirmado` | lista | **Vacía.** Se rellena después, con los campos que el usuario confirme |

## 2. Fases (`fases`)

Divide el vídeo en fases sin huecos ni solapes, de 0 a la duración, de al menos 1 s. Cada fase: `inicio`, `fin`, `descripcion` y `riesgo` (`alto`, `medio`, `bajo`). Una fase de riesgo alto que no se ve deja la evaluación en rojo.

## 3. Muñecas (`munecas`)

MediaPipe Pose no mide bien la muñeca: la estimas tú en la imagen ORIGINAL. Una entrada por fase y por lado (`izq`, `dch`, del trabajador), con la postura más exigente de esa fase:
- `flexion`: `neutra`, `hasta_15`, `mas_15` o `no_visible`;
- `desviada` (radial o cubital) y `girada` (pronación o supinación extrema): `true`, `false` o `null`;
- `confianza`: `alta` (la mano se ve bien), `media` (en parte), `baja` (apenas). Las de confianza baja no se usan;
- `motivo`: qué ves, en una frase.

No deduzcas: si no ves la mano, `no_visible`.

## 4. Veredictos sobre el esqueleto (`revisiones`)

Compara las dos mitades y di **solo** dónde el esqueleto NO corresponde al cuerpo. Articulaciones: `oreja_izq/dch`, `hombro_*`, `codo_*`, `muneca_*`, `cadera_*`, `rodilla_*`, `tobillo_*`. Un tramo (`inicio`, `fin`) por articulación y problema, agrupando fotogramas seguidos:

- `mal_colocada`: fuera de su sitio real (más de media longitud del segmento contiguo), sobre un objeto, o dibuja una postura distinta de la que se ve. **Se quita.**
- `no_visible`: tapada o fuera del encuadre; su posición es una suposición. Marca el tramo exacto. **Se quita si dura más de 1,5 s; si no, se conserva como aproximada.**
- `aproximada`: no está exactamente en su sitio, pero la postura es la que se ve. Prefiere esta a `mal_colocada` cuando la postura general sea correcta. **Se conserva con el margen de medida ampliado.**
- `lado_invertido`: el esqueleto confunde izquierda y derecha. Solo si estás seguro, y con `lado_cercano` (`izq`, `dch`): qué lado REAL está más cerca de la cámara. **Solo se aplica si la profundidad de MediaPipe lo confirma.**

Cada veredicto lleva `motivo` y `evidencia` (qué ves en la imagen original que lo demuestra). Lo que no menciones se da por correcto. No calcules ángulos.

**Lateralidad.** Izquierda y derecha son las del trabajador. De frente, su izquierda está a la derecha de la imagen; de espaldas, a la izquierda. Razona con la cara, los pies y qué brazo queda delante del torso.

**Partes fuera del encuadre.** Si las piernas no se ven y está sentado, no hace falta un veredicto por cada articulación de las piernas: basta con `postura_base: sentado`. Si MediaPipe dibuja piernas que no están en la imagen, márcalas `no_visible`.

## 5. Después de rellenarla

1. Enseña al usuario el contexto propuesto (postura, apoyo, carga, agarre, actividad, rotaciones, muñecas) en lenguaje llano y pídele que confirme o corrija.
2. Corrige el JSON con sus respuestas y pon en `contexto.confirmado` los campos confirmados (p. ej. `["postura_base", "apoyo_piernas", "carga_kg", "agarre", "actividad"]`).
3. Analiza con `--revision <revision.json>`. El informe distingue lo declarado, lo confirmado, lo estimado por la IA y lo desconocido, y compara el resultado sin y con revisión.

## 6. Ficha de acciones técnicas (OCRA, bloque `ocra`)

Con `--metodos ocra` (o `todos`), `revisar` genera `ocra_ciclo_NN.jpg`: el ciclo representativo a 4–8 fotogramas por segundo, con el tiempo en cada fotograma y un punto naranja donde MediaPipe ve que la mano se para o cambia de velocidad (candidatos: orientan, no son AT). Mira **todas** las láminas del ciclo, en orden, y rellena el bloque `ocra`:

| Campo | Valores | Criterio |
|---|---|---|
| `ciclo.inicio`, `ciclo.fin` | segundos | Un ciclo completo y representativo (p. ej., de un alcance a la caja al siguiente). Explica en `ciclo.evidencia` cómo lo has delimitado |
| `manos_visibles` | `true`, `false`, `null` | ¿Se ven las manos y los objetos en las operaciones? Si no, OCRA queda «no recomendable» |
| `acciones` | lista | Una entrada por gesto, **por mano** y por segundo (ver abajo) |
| `posturas.dch/izq.agarre` | fracción del ciclo (0–1), `[mín, máx]` o `null` | Tiempo con agarre en pinza, en gancho o palmar forzado. `null` si no lo ves |
| `confirmada` | `false` | Se pone a `true` solo cuando el usuario confirma el recuento |

Cada acción: `t` (segundo de inicio), `mano` (`dch` o `izq`, del trabajador), `gesto`, `objeto`, `confianza` (`alta`, `media`, `baja`), `cuenta` (si propones contarla como AT; por defecto `true`) y, según el gesto, `repeticiones` (girar, accionar herramienta, golpear, pasadas), `distancia_m` (transportar), `con_esfuerzo_o_precision` (introducir, encajar, sacar) y `gesto_distinto` (introducir o encajar justo después de posicionar el mismo objeto). Añade `nota` si ayuda.

Gestos y lo que hace el código (criterios OCRA de Colombini y Occhipinti, anexo de ISO 11228-3:2007, UNE-EN 1005-5 e INSST):

| Gesto (`gesto`) | AT |
|---|---|
| `alcanzar` | 0: se valora en postura y forma parte de «coger» |
| `coger`, `agarrar` | 1 |
| `pasar_mano` | 1 por mano (anota una entrada en cada mano) |
| `posicionar` | 1 |
| `introducir`, `encajar`, `sacar` | 1 si hay esfuerzo o precisión; tras `posicionar` del mismo objeto, solo si es un gesto distinto |
| `empujar`, `tirar`, `presionar` | 1 |
| `girar` | 1 por giro |
| `coger_herramienta`, `posicionar_herramienta` | 1 cada uno |
| `accionar_herramienta` | 1 por accionamiento |
| `devolver_herramienta` (suspendida, soltándola) | 0: es soltar |
| `dejar_herramienta_soporte` (con precisión) | 1: es posicionar |
| `soltar`, `abrir_mano` | 0 |
| `transportar` | 0 a menos de 1 m; 1 a 1 m o más |
| `sujetar` (mano de apoyo, estático) | 0: se valora en postura y agarre |
| `control_visual`, `andar`, `esperar` | 0 |
| `golpear`, `pasada` | 1 cada una |

Anota también lo que **no** cuenta (con `cuenta: false`): así queda la trazabilidad. Si propones contar algo que la regla no admite, el código lo **rechaza** y lo dice. Las entradas de confianza **baja** o a las que les falta un dato de la regla quedan **dudosas**: cuentan solo en el extremo alto del rango. No deduzcas lo que no ves: si un gesto no se distingue, confianza baja.

**Lateralidad.** Mano derecha e izquierda son las del trabajador; razona como en la sección 4. Si la mano más activa queda del lado lejano, dilo en `ciclo.evidencia` (`validar` también lo avisa).
