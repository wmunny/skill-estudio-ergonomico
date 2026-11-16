# Investigación: rediseño ergonómico de un puesto a partir de una foto

**Estado: APARCADO** (16-11-2026). Investigación de viabilidad archivada para retomarla más adelante. No hay código escrito.

## Idea

Fotografiar un puesto de trabajo (p. ej. un banco de montaje en línea con cubetas), proyectar sobre él un humanoide hombre/mujer de un percentil determinado con sus rangos de alcance, comprobar si los elementos quedan dentro o fuera de alcance, y poder modificar el puesto para obtener uno corregido. Equivalente a lo que hacían ManneQuinPRO y similares, pero partiendo del puesto real en lugar de un CAD, y empaquetado como skill para Claude o ChatGPT.

## Conclusión

Es factible con la tecnología actual, pero no como «foto → veredicto de la IA». La foto sirve para reconstruir el puesto en 3D con medidas; la verificación de alcances debe hacerla un cálculo geométrico determinista, no el modelo de lenguaje.

Las cifras de precisión de foto única que aparecen abajo son una estimación, no un dato medido. Las de LiDAR proceden de los fabricantes.

## Arquitectura propuesta

1. **Captura con escala real.** Una foto sola no tiene escala fiable.
   - Foto única + IA de profundidad métrica (Depth Pro de Apple, MoGe-2): 3D con escala absoluta sin datos de cámara, con un error esperable del orden del 5-15 %. A 60 cm de alcance son varios centímetros, justo el margen que decide si una cubeta está dentro o fuera.
   - Foto + referencia conocida (marcador impreso tipo ArUco o una medida tomada con cinta): corrige la escala a 1-2 cm aproximadamente. **Opción recomendada para empezar.**
   - Escaneo con LiDAR de iPhone/iPad (Polycam, RoomPlan) o varias fotos (Depth Anything 3): en torno a 1-3 cm según el fabricante, y capta lo que una foto oculta.
2. **Puesto simplificado y editable.** Extraer los elementos relevantes (plano de trabajo, cubetas, estanterías) como cajas con posición y dimensiones. La IA de visión identifica y etiqueta cada elemento.
3. **Humanoide por percentil.** Anny (Naver Labs): modelo paramétrico abierto, licencia Apache 2.0 con uso comercial permitido, controlable por sexo, edad, estatura y peso. Se alimenta con tablas antropométricas (ISO 7250 o datos de población laboral española) para generar P5 mujer, P50, P95 hombre, etc. Alternativa: familia SMPL-X, con licencia comercial restringida.
4. **Verificación de alcances.** Envolventes de alcance desde el hombro del maniquí (zona cómoda y zona máxima, según UNE-EN ISO 14738) y comprobación de cada elemento: dentro, límite o fuera. Geometría pura, repetible y auditable.
5. **Rediseño interactivo.** Visor web 3D (three.js) donde mover cubetas, cambiar la altura del plano o el percentil, con recálculo inmediato. La foto original puede quedar de fondo con el maniquí y las zonas superpuestos.

## Papel de la IA y de la skill

- **El LLM hace bien:** interpretar la foto, etiquetar elementos, proponer rediseños, redactar el informe y orquestar el proceso.
- **El LLM no debe:** medir ni decidir alcances «a ojo»; se equivoca y no es defendible en un informe técnico.
- **Formato:** skill de Claude con scripts de Python (como la de evacuación IFC): recibe foto y referencia de escala, devuelve visor e informe. En ChatGPT se puede replicar como GPT con acciones, con el cálculo igualmente en código.

## Frente al software clásico

RAMSIS, Siemens Jack y ema Work Designer siguen vigentes y lo hacen con rigor, pero exigen modelar el puesto en CAD y licencias caras. No se encontró información actual sobre ManneQuinPRO. La aportación de la IA actual es saltarse el CAD: del puesto real al modelo en minutos.

## Límites

- Una foto no ve lo que queda oculto; para puestos complejos hacen falta dos o tres fotos, o escaneo.
- Cubre alcances y alturas (estático). Posturas, fuerzas o repetitividad (RULA, OCRA) serían otro módulo.
- El resultado sería orientativo hasta validarlo contra medidas reales en varios puestos.

## Plan de prototipo y esfuerzo estimado

| Fase | Qué incluye | Esfuerzo estimado |
|---|---|---|
| 1. Visor con verificación | Puesto como cajas editables, maniquí P5/P50/P95 hombre/mujer de pie o sentado, zonas de alcance y semáforo por cubeta que se recalcula al mover elementos | Una sesión (1-2 h) |
| 2. Foto → puesto | Foto con marcador o medida conocida; la IA de visión identifica los elementos y los coloca a escala, con la foto de fondo | Una sesión más |
| 3. Reconstrucción 3D automática | Modelos de profundidad (MoGe-2, Depth Pro) o importación de escaneo LiDAR | Una o dos sesiones, con incertidumbre |

- La fase 1 ya valida la idea central: con las medidas de un puesto conocido metidas a mano se puede comprobar si los alcances coinciden con la realidad.
- En la fase 1 el maniquí sería simplificado (segmentos articulados dimensionados con tablas antropométricas), no la malla realista de Anny.
- La fase 3 es la incierta: necesita Python con librerías pesadas y preferiblemente GPU; sin ella, servicio en la nube o escaneo con iPhone.

## Para retomarlo

Hace falta: una o dos fotos de un puesto real con un marcador o una medida conocida, y cinco o seis medidas tomadas con cinta para contrastar. Empezar por la fase 1.

## Fuentes

- [Depth Pro (Apple)](https://arxiv.org/pdf/2410.02073)
- [MoGe-2](https://arxiv.org/html/2507.02546v1)
- [Depth Anything 3 (ICLR 2026)](https://proceedings.iclr.cc/paper_files/paper/2026/file/e4cd50120b6d7e8daff1749d6bbaa889-Paper-Conference.pdf)
- [Anny body model (paper)](https://arxiv.org/abs/2511.03589v2)
- [Anny (Naver Labs blog)](https://europe.naverlabs.com/blog/anny-a-free-to-use-3d-human-parametric-model-for-all-ages/)
- [RAMSIS (Humanetics)](https://www.humaneticsgroup.com/products/ergonomic-software/ramsis)
- [Siemens Jack](https://software.umich.edu/titles/jack)
- [Digital workplace design / ema (KIT)](https://www.ifab.kit.edu/english/1752.php)
- [Precisión de Polycam](https://learn.poly.cam/hc/en-us/articles/27488763119892)
- [Test independiente de RoomPlan](https://www.lidar3d.io/post/testing-the-precision-of-apple-s-ios-roomplan-api-a-polycam-lidar-3d-scanning-app-feature-review)
