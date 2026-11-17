# notebooks/

Las demostraciones del taller. **Están escritos para leerse y correrse solo**,
sin el instructor al lado: cada sección dice qué vas a ver, cuánto tarda y qué
revisar si algo falla. El instructor proyecta estos mismos archivos, y lo que es
solo para él va marcado como `> **Para quien lo proyecta.**`.

El estilo de la prosa está fijado en
[`planeacion/estilo.md`](../planeacion/estilo.md).

Antes: el ambiente virtual y las dependencias, según los pasos 1 a 3 del
[README de la raíz](../README.md). Después, **con el ambiente activado**:

```
jupyter lab
```

Si lo lanzas sin activar el ambiente, las celdas fallan en `import requests` sin
decir por qué. Es el tropiezo más común del minuto 0.

| Notebook | Bloque | Min | Estado |
|---|---|---|---|
| `00_localhost.ipynb` | 0 | 10 | completo. Trabajas solo: el modelo, el backend y la página en tu máquina |
| `00_aula.ipynb` | 0 | 10 | completo. El modelo en la laptop del instructor. **Dos partes: instructor y asistente** |
| `00_tec.ipynb` | 0 | 10 | completo. El modelo en el servidor del Tec, por la VPN. **Dos partes** |
| `00_verificacion_ambiente.ipynb` | 0 | 10 | **lo reemplazan los tres de arriba.** Se puede borrar |
| `01_del_prompt_al_agente.ipynb` | 1 | 40 | completo |
| `02_primer_bucle_agentico.ipynb` | 2 | 30 | completo |
| `03_herramientas_reales.ipynb` | 3 | 25 | completo |
| `04_guardrails.ipynb` | 3 | 20 | completo. Cuatro celdas sin salida guardada: son las que borran y reinician |
| `05_multiagente.ipynb` | 4 | 50 | completo. **Caso propio**: consolidar dos listas de clientes, con los datos y la respuesta en [`../src/mdm/`](../src/mdm/) |
| `06_que_sale_mal.ipynb` | 5 | 30 | completo. **Usa los dos dominios**: tres demos sobre el inventario y dos sobre los clientes. Necesita el backend arriba |
| `07_nas_agente.ipynb` | — | — | completo. **Caso de estudio aparte**: cuatro agentes buscando predictores para NAS |
| `08_ventana_y_memoria.ipynb` | — | — | completo. **Laboratorio aparte**: hasta dónde crece la ventana de contexto y qué cuesta |
| `09_langchain.ipynb` | — | — | completo. **Comparación aparte**: el agente del paso 4 rehecho en LangChain. Necesita [`../requirements-frameworks.txt`](../requirements-frameworks.txt) |

**Hay tres notebooks 00, uno por escenario**, y se elige por dónde corre el
modelo: en tu máquina (`localhost`), en la laptop del instructor (`aula`) o en
el servidor del Tec (`tec`). Cada uno es lineal y se corre de arriba abajo; los
de `aula` y `tec` están partidos en **lo que corre el instructor** y **lo que
corre cada asistente**. La elección tiene que coincidir con `OLLAMA_DESTINO` del
`.env`, y la primera celda de configuración lo comprueba y lo dice.

Los tres últimos no son bloques del taller y no entran en las cuatro horas. El
07 es uno de los dos casos de estudio que sí se pueden *calificar*, porque su
respuesta está publicada; el otro es el 05. El 08 mide la restricción que
explica el diseño de todos los demás, y es el único que grafica — necesita
`matplotlib`, que por eso está en el `requirements.txt`.

**El 09 se lee al final, o nunca.** Compara el agente del paso 4 contra el mismo
agente escrito con LangChain, y solo tiene sentido después de haber escrito el
bucle a mano. Es el único notebook con dependencias propias.

**El 08 no se corre durante el taller:** carga y descarga el modelo siete veces
y pide hasta 15 GB.

## Notebook o archivo `.py`: cuál para qué

Los dos existen y no se duplican, porque hacen cosas distintas.

**El notebook es para exponer.** Una celda, un resultado, una idea. Sirve para
mostrar que la misma pregunta con temperatura 1.2 da tres respuestas distintas:
eso en un `.py` es un `print` en una pared de texto, y en una celda es evidente.

**El `.py` es para construir.** Un agente es un programa: tiene un bucle, un
criterio de terminación, módulos que se importan entre sí. Eso no se escribe en
celdas sin aprender un modelo mental equivocado — y el modelo mental es lo único
que el asistente se lleva.

Así que: el bloque 1 y el 5 viven en notebooks, porque son exposición. Los
bloques 2, 3 y 4 son `.py` en [`../src/`](../src/), y el notebook del bloque
correspondiente **importa desde ahí** en lugar de copiar el código.

Eso último no es un detalle de estilo. Si el notebook copiara el código, las dos
versiones se desincronizarían en la primera corrección, y el instructor acabaría
proyectando algo distinto de lo que el asistente tiene abierto en su editor. Con
`importlib.reload`, lo que se ve en el proyector es exactamente el archivo que
se está editando.
