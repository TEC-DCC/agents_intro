# nas_agente/

Segundo caso de estudio, aparte de los cinco pasos del taller: un **sistema
multiagente** que busca el mejor predictor de rendimiento para Neural
Architecture Search.

```
laboratorio.py   las tools: datos, codificaciones, predictores, Friedman
agentes.py       los cuatro agentes y el orquestador
datos/           el dataset de 1193 arquitecturas
```

El notebook es [`notebooks/07_nas_agente.ipynb`](../../notebooks/07_nas_agente.ipynb).

## El problema

Evaluar una arquitectura cuesta entrenarla. Generar las 1193 evaluaciones de
este dataset costó **~9500 horas de GPU**; entrenar un predictor sobre ellas
cuesta entre **0.02 y 6 segundos de CPU**. Ese desbalance es la razón de ser de
los predictores de rendimiento, y también lo que hace que el ejemplo quepa en
un taller sin tocar la GPU que ocupa Ollama.

## Los datos

De Sarmiento-Rosales, Sosa Hernández y Monroy (2026), *"Evolutionary Neural
Architecture Search for Super-Resolution"*, Swarm and Evolutionary Computation.
Dataset público, MIT:
[MoNAS-SR-Predictors-Dataset](https://github.com/SergioSarmientoRosales/MoNAS-SR-Predictors-Dataset).

Cada fila: un cromosoma de **28 tokens** (valores 0–7, códigos Gray de 3 bits)
del espacio BASS, y su **PSNR de validación** tras 5 épocas en DIV2K.

**`y` es la última columna del CSV**, no la penúltima. No es una suposición: es
lo que hace el código de los autores (`y = data.iloc[:, -1]`). Importa, porque
la otra columna tiene 41 infinitos y 34 ceros.

## Los cuatro agentes

| Agente | Responsabilidad | Tools |
|---|---|---|
| **Analista** | mira los datos y reporta problemas | solo lectura |
| **Experimentador** | entrena y evalúa predictores | el único que gasta CPU |
| **Estadístico** | dice si las diferencias son reales | solo lectura |
| **Orquestador** | reparte y concluye | **los otros tres** |

El Orquestador usa **agente-como-tool**: sus tools son los otros agentes, así
que el handoff queda explícito.

El **Estadístico** es el que gana su lugar, y es poco común: su trabajo es
desconfiar de los otros. Sin él, el sistema reporta el máximo de una lista y lo
llama ganador. El propio paper muestra que Extra Trees, SVR, XGBoost y Random
Forest son estadísticamente indistinguibles.

## Dos cosas medidas que vale conocer

**Sin una línea concreta en su system prompt, el Analista no llama ninguna
tool** —5 de 5 veces— e inventa el dataset entero. La línea que lo arregla es
*"NUNCA respondas sin haber llamado una tool primero: no conoces este dataset de
memoria"*. La otra hipótesis, que la tool no se llamara por no tener parámetros,
se probó y quedó descartada.

**Las codificaciones alternativas son peores**, aunque el paper las deja como
trabajo futuro:

| codificación | C-index |
|---|---|
| entero (la del paper) | **0.6679** |
| onehot (224 columnas) | 0.6516 |
| binario (Gray → 84 bits) | 0.6227 |

Los árboles parten por umbrales y aíslan cualquier valor, así que el orden
numérico les importa poco; y el one-hot sufre con 224 columnas para 1193 filas.

## Calificable

Lo raro de este caso: **tenemos la respuesta publicada**. La Tabla 3 del paper
reporta C-index y MSE de once predictores, y `laboratorio.comparar_con_el_paper()`
los devuelve. Se puede *calificar* al agente, que es lo que el bloque 5 del
taller pide hacer y casi nunca se puede.
