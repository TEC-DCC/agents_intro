# `src/mdm/` — El caso de datos maestros

El caso del **bloque 4**. Dos listas de clientes que se traslapan, y hay que
dejar un registro por persona. El problema se llama MDM (*master data
management*) y el notebook es
[`notebooks/05_multiagente.ipynb`](../../notebooks/05_multiagente.ipynb).

Es un caso autocontenido, como [`nas_agente/`](../nas_agente/): no usa el
backend, ni la página, ni el inventario de los pasos 2 a 4.

| Archivo | Qué es |
|---|---|
| [`maestro.py`](maestro.py) | la capa determinista. Normaliza, agrupa en candidatos, compara, fusiona y califica |
| [`agentes.py`](agentes.py) | los tres agentes, sus tools y el guardrail de la fusión |
| [`datos/`](datos/) | las dos fuentes, las personas reales y la respuesta. Ver su [README](datos/README.md) |

## El reparto

Lo que decide el archivo y lo que decide un agente está separado a propósito.

| | dónde vive |
|---|---|
| normalizar, agrupar, comparar campo por campo, fusionar, calificar | `maestro.py` |
| si dos registros son la misma persona, y qué valor sobrevive | los agentes |

`comparar()` es el centro. **Devuelve evidencia, no veredicto.** Si devolviera
"son la misma persona", el agente no tendría nada que decidir y el bloque 4 no
tendría argumento.

## Dónde vive el estado de una corrida

En `maestro`, no en `agentes`:

| | |
|---|---|
| `maestro.PLATA` | la capa plata viva, con las correcciones del Normalizador |
| `maestro.DICTAMENES` | lo que decidió el Emparejador |
| `maestro._ORO` | los golden records |

**`agentes.py` no guarda nada entre llamadas**, y es a propósito.
`importlib.reload(agentes)` reejecuta ese módulo: si el estado estuviera ahí,
cada recarga lo dejaría vacío. Editar el system prompt de un agente y volver a
probarlo es la operación más común del taller, y no puede costar una corrida de
tres minutos. Es el mismo reparto que `nas_agente`, donde el pizarrón vive en
`laboratorio`.

Dos formas de limpiar, y la diferencia importa:

| | qué borra |
|---|---|
| `maestro.reiniciar_oro()` | solo los golden records. Conserva plata y dictámenes |
| `maestro.reiniciar()` | las tres capas. Es lo que llama `agentes.reiniciar()` |

Y una trampa que el refactor quitó: las funciones que reciben `plata=None`
—`comparar`, `generar_candidatos`, `fusionar`— ahora usan la capa **viva**. Antes
reconstruían una desde el CSV, así que una llamada sin `plata` explícita no veía
las correcciones del Normalizador y nadie se enteraba.

## Los tres agentes

| Agente | Etapa | Qué decide | Permiso |
|---|---|---|---|
| **Normalizador** | bronce a plata | las iniciales y abreviaturas que la normalización automática no pudo | escribe el borrador |
| **Emparejador** | plata a dictámenes | si dos registros son la misma persona | **solo lectura** |
| **Fusionador** | dictámenes a oro | qué valor gana, y crea el golden record | **el destructivo** |

**Fusionar es irreversible**, y por eso el Fusionador es el único que pasa por
una confirmación. En un MDM de verdad los merges dudosos van a una persona: el
guardrail del paso 4 aquí no es un requisito inventado.

## Por qué el modelo ve un par a la vez

Comparar 85 registros contra 85 son 3 570 pares, y la ventana de contexto real
de `qwen3.5:9b` en el aula son 4 096 tokens. `generar_candidatos()` baja esos
pares a 47 con cuatro llaves deterministas — la raíz del RFC, el teléfono, el
correo y el apellido con la inicial — y el Emparejador recibe un par, que son
dos renglones.

No es una optimización: es lo que hace que el caso quepa.

## Cómo correrlo sin el notebook

```python
import sys; sys.path.insert(0, "src")
from agentlib import cargar_env; cargar_env()
from mdm import agentes, maestro

agentes.reiniciar()
agentes.emparejador("C041", "F021")          # una de las cinco trampas
agentes.emparejar_candidatos(limite=5)        # los primeros 5 pares
```

La corrida completa son 47 pares, 94 llamadas al modelo y unos tres minutos.

## Lo medido

**2026-11-16**, contra `qwen3.5:9b` en el servidor del Tec. Está en
[`planeacion/hallazgos.md`](../../planeacion/hallazgos.md) con el detalle.

| | |
|---|---|
| registros de entrada | 85 |
| que la normalización determinista no resolvió | 11 |
| pares candidatos | 47, con recall de 34/34 |
| aciertos del Emparejador | 46 de 47 |
| golden records | **56**, contra 55 correctos |
| fusiones de más | **0** — libró las 5 trampas |

La línea base sin agentes, que fusiona todo par candidato, da 49 golden records,
cae en las 5 trampas y encadena tres personas en un solo registro.
