# Paso 5 — Varios agentes

**Bloque 4, ~50 min.**

El código de este paso **no vive aquí**: vive en [`../mdm/`](../mdm/), porque el
bloque 4 usa un caso propio y no el inventario de los pasos 2 a 4.

| | |
|---|---|
| el código | [`../mdm/maestro.py`](../mdm/maestro.py) y [`../mdm/agentes.py`](../mdm/agentes.py) |
| el notebook | [`../../notebooks/05_multiagente.ipynb`](../../notebooks/05_multiagente.ipynb) |
| los datos y la respuesta | [`../mdm/datos/`](../mdm/datos/) |

## Por qué el caso cambió de dominio

El plan original repartía el inventario en tres agentes: Recepción entendía la
petición, Inventario consultaba y Pedidos escribía. **Ese reparto era
decoración.** Consultar existencias, actualizar y borrar es un solo trabajo
partido en tres, y el asistente se iba con la idea de que multiagente es algo
que se le hace a un sistema porque se puede.

El caso de datos maestros no tiene ese problema: decidir si dos registros son la
misma persona es juicio, y no hay regla que lo resuelva porque la evidencia se
contradice entre sí. Ahí un modelo aporta algo que una función no.

## El reparto

| Agente | Responsabilidad | Permiso |
|---|---|---|
| **Normalizador** | las iniciales y abreviaturas que la normalización automática no pudo | escribe el borrador |
| **Emparejador** | si dos registros son la misma persona | **solo lectura** |
| **Fusionador** | qué valor sobrevive, y crea el golden record | **el destructivo** |

**El reparto es la lección.** El agente que puede romper cosas es uno solo, y es
el que tiene las reglas más estrictas. Eso no es una decisión de IA: es diseño
de permisos, y es tan viejo como los sistemas multiusuario.

Y aquí lo destructivo no es un requisito inventado: **fusionar es
irreversible**, porque al crear el golden record se destruye la distinción entre
los registros que lo formaron. En un MDM de verdad los merges dudosos van a una
persona.

## Lo que hay que explicar aquí y en ningún otro lado

- **Qué viaja en el handoff.** Entre el Emparejador y el Fusionador viaja un
  dictamen: dos ids, un veredicto y una línea. No viaja el razonamiento, así que
  el Fusionador no puede dudar del veredicto que recibe. Es la falla 3 del
  bloque 5. Mandar el historial completo tampoco es gratis.
- **Patrones de orquestación**: router, supervisor, pipeline. Este caso es un
  pipeline, y el del notebook 07 es un supervisor. Treinta segundos cada uno.
- **El costo.** La corrida completa son 47 pares, 94 llamadas al modelo y unos
  tres minutos, contra los milisegundos de la línea base sin agentes. Medido:
  171 y 184 segundos en dos corridas.

## La pregunta con la que se cierra el bloque

> Comparado con el agente único del paso 4, **¿esto mejoró algo, o solo se
> volvió más caro?**

Para este caso la respuesta es que sí mejoró, y se puede decir en qué: **cero
fusiones de más contra cinco**. Pero el reparto en *tres* agentes es más
discutible que la decisión de usar un agente, y el Normalizador es el más débil
de los tres. Decirlo es lo que le da credibilidad al resto.

Los números están medidos en
[`planeacion/hallazgos.md`](../../planeacion/hallazgos.md).

**Depende de:** los pasos 3 y 4. Ya no depende del caso de estudio del
inventario.
