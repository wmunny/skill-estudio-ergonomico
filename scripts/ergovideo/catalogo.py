"""Catálogo de hallazgos ergonómicos y medidas preventivas tipo.

Cada tipo de hallazgo tiene:
- qué es y por qué importa (zona del cuerpo y trastorno musculoesquelético asociado);
- la regla que lo detecta (en hallazgos.py, con umbrales de los métodos);
- medidas tipo ordenadas por jerarquía preventiva: ingeniería (eliminar o reducir en el origen), organizativas y
  formación. Son medidas genéricas de ergonomía de puestos: Claude las concreta al puesto con lo que ve en el vídeo
  (adaptacion.json) y el informe distingue lo que es de catálogo de lo que es propuesta adaptada.
"""

from __future__ import annotations

TIPOS_MEDIDA = {"ingenieria": "Diseño del puesto", "organizativa": "Organización del trabajo", "formacion": "Formación"}

CATALOGO = {
    "tronco_flexion": dict(
        region="espalda", titulo="Espalda inclinada hacia delante",
        riesgo="Sobrecarga de la zona lumbar; con frecuencia o carga, lumbalgia y lesiones de disco.",
        medidas=[
            ("ingenieria", "Subir el plano de trabajo o la pieza a la altura de los codos (regulable si trabajan personas de distinta talla)."),
            ("ingenieria", "Acercar la pieza y los elementos al borde del puesto para no tener que inclinarse a por ellos."),
            ("ingenieria", "Inclinar contenedores y utillajes hacia el trabajador o usar mesas elevadoras o basculantes."),
            ("organizativa", "Alternar esta tarea con otras que permitan una postura erguida."),
        ]),
    "tronco_giro": dict(
        region="espalda", titulo="Tronco girado o inclinado de lado",
        riesgo="La torsión del tronco, sobre todo con carga o de forma repetida, sobrecarga la columna lumbar.",
        medidas=[
            ("ingenieria", "Colocar piezas, contenedores y herramientas delante del trabajador, dentro del área de trabajo, en lugar de a un lado o detrás."),
            ("ingenieria", "Usar plataformas o soportes giratorios para acercar el material sin girar el cuerpo."),
            ("organizativa", "Ordenar la secuencia de trabajo para que el material llegue por delante (alimentación frontal)."),
            ("formacion", "Formar en girar con los pies en lugar de con el tronco."),
        ]),
    "cuello_flexion": dict(
        region="cuello", titulo="Cabeza inclinada hacia delante",
        riesgo="Sobrecarga cervical: dolor de cuello y de la parte alta de la espalda al mantenerla o repetirla.",
        medidas=[
            ("ingenieria", "Elevar o inclinar la pieza o la zona de montaje para que quede a la altura de la vista."),
            ("ingenieria", "Mejorar la iluminación localizada para no tener que acercar la cabeza."),
            ("organizativa", "Introducir micropausas y alternar con tareas que no exijan mirar hacia abajo."),
        ]),
    "cuello_extension": dict(
        region="cuello", titulo="Cabeza echada hacia atrás",
        riesgo="La extensión del cuello sobrecarga las vértebras cervicales.",
        medidas=[
            ("ingenieria", "Bajar los elementos que obligan a mirar hacia arriba (mandos, indicadores, piezas altas)."),
            ("organizativa", "Limitar la duración de las tareas por encima de la cabeza."),
        ]),
    "brazo_elevado": dict(
        region="hombro", titulo="Brazo elevado",
        riesgo="Trabajar con el brazo separado del cuerpo o por encima del hombro sobrecarga el hombro (tendinitis del manguito rotador).",
        medidas=[
            ("ingenieria", "Bajar herramientas, mandos y puntos de trabajo a una altura entre la cintura y el pecho, con el codo cerca del cuerpo."),
            ("ingenieria", "Regular la altura del equilibrador o del soporte de la herramienta para cogerla sin levantar el brazo."),
            ("ingenieria", "Acercar la pieza al trabajador o usar utillajes que la orienten para no levantar el brazo."),
            ("organizativa", "Rotar a tareas que no exijan elevar los brazos."),
        ]),
    "brazo_abducido": dict(
        region="hombro", titulo="Brazo separado del cuerpo",
        riesgo="Separar el brazo del costado de forma repetida o mantenida sobrecarga el hombro.",
        medidas=[
            ("ingenieria", "Situar los elementos más cerca y delante del cuerpo para trabajar con los codos pegados."),
            ("ingenieria", "Reducir la anchura del área de trabajo."),
        ]),
    "alcance": dict(
        region="hombro", titulo="Alcances lejanos o fuera de la línea del cuerpo",
        riesgo="Alcanzar lejos con el brazo extendido o cruzándolo por delante del cuerpo carga el hombro y obliga a girar el tronco.",
        medidas=[
            ("ingenieria", "Llevar los contenedores de piezas a la zona de alcance cómodo (a unos 40–50 cm, delante del trabajador)."),
            ("ingenieria", "Usar contenedores inclinados o alimentación por gravedad para que la pieza llegue a la mano."),
            ("organizativa", "Reponer las piezas por delante y reducir el número de contenedores en el puesto."),
        ]),
    "muneca": dict(
        region="muneca", titulo="Muñeca doblada o desviada",
        riesgo="Doblar o desviar la muñeca con fuerza o de forma repetida se asocia a tendinitis y síndrome del túnel carpiano.",
        medidas=[
            ("ingenieria", "Orientar la pieza o el útil para trabajar con la muñeca recta."),
            ("ingenieria", "Usar herramientas con el mango adecuado (recto o acodado según la orientación del trabajo) y de buen agarre."),
            ("ingenieria", "Sustituir sujeciones manuales por utillajes o mordazas."),
            ("formacion", "Formar en técnicas de trabajo con la muñeca en posición neutra."),
        ]),
    "piernas": dict(
        region="piernas", titulo="Piernas flexionadas o apoyo en una sola pierna",
        riesgo="Trabajar en cuclillas, de rodillas o sobre una pierna sobrecarga rodillas y caderas y fatiga la espalda.",
        medidas=[
            ("ingenieria", "Elevar el punto de trabajo para no tener que agacharse o arrodillarse."),
            ("ingenieria", "Dejar espacio libre para los pies y apoyar el peso en las dos piernas; reposapiés o alfombra antifatiga si se trabaja de pie mucho tiempo."),
            ("organizativa", "Alternar posturas de pie y sentado (asiento o apoyo semisentado)."),
        ]),
    "de_pie": dict(
        region="piernas", titulo="Trabajo de pie prolongado",
        riesgo="Estar de pie casi todo el tiempo sin poder cambiar de postura fatiga piernas y espalda y dificulta el retorno venoso.",
        medidas=[
            ("ingenieria", "Facilitar un apoyo semisentado o un taburete alto para alternar de pie y sentado sin dejar el puesto."),
            ("ingenieria", "Colocar alfombras antifatiga y un reposapiés para cambiar el apoyo de las piernas."),
            ("organizativa", "Organizar pausas o rotaciones a tareas que permitan sentarse o caminar."),
        ]),
    "sentado": dict(
        region="piernas", titulo="Trabajo sentado prolongado",
        riesgo="Estar sentado casi todo el tiempo sin cambiar de postura sobrecarga la zona lumbar y el cuello.",
        medidas=[
            ("ingenieria", "Silla regulable con apoyo lumbar y reposapiés, ajustada a la altura del plano de trabajo."),
            ("organizativa", "Alternar con tareas de pie o pausas activas."),
        ]),
    "carga": dict(
        region="global", titulo="Manipulación de carga o fuerza",
        riesgo="Manipular peso o hacer fuerza aumenta la carga sobre la espalda y los miembros superiores.",
        medidas=[
            ("ingenieria", "Usar ayudas mecánicas (equilibradores, manipuladores, mesas elevadoras) o reducir el peso de cada unidad."),
            ("organizativa", "Repartir la manipulación entre más personas o más ciclos."),
            ("formacion", "Formar en manipulación manual de cargas."),
        ]),
    "repetitividad": dict(
        region="global", titulo="Movimientos repetitivos",
        riesgo="Repetir el mismo gesto muchas veces por minuto es un factor principal de trastornos de hombro, codo y muñeca.",
        medidas=[
            ("organizativa", "Rotar entre puestos con exigencias distintas para el miembro superior."),
            ("organizativa", "Introducir pausas cortas y frecuentes y revisar el ritmo de trabajo."),
            ("ingenieria", "Automatizar o mecanizar las operaciones más repetidas (atornillado, inserción)."),
        ]),
    "estatica": dict(
        region="global", titulo="Postura mantenida",
        riesgo="Mantener la misma postura más de un minuto genera fatiga muscular y molestias.",
        medidas=[
            ("organizativa", "Permitir cambios de postura y micropausas."),
            ("ingenieria", "Facilitar apoyos (para el antebrazo o semisentado) que reduzcan el esfuerzo estático."),
        ]),
    "agarre": dict(
        region="muneca", titulo="Agarre deficiente",
        riesgo="Un agarre incómodo obliga a hacer más fuerza con la mano y la muñeca.",
        medidas=[
            ("ingenieria", "Dotar a las piezas o cajas de asas o puntos de agarre adecuados."),
            ("ingenieria", "Usar guantes de la talla correcta que no reduzcan la sensibilidad."),
        ]),
}

REGIONES = {
    "cuello": "Cuello", "espalda": "Espalda", "hombro": "Hombro y brazo", "muneca": "Muñeca y mano",
    "piernas": "Piernas", "global": "Organización y carga",
}


def medidas(tipo: str) -> list[dict]:
    return [dict(id=f"{tipo}_{i + 1}", tipo=t, texto=x) for i, (t, x) in enumerate(CATALOGO[tipo]["medidas"])]
