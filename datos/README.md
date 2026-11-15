# datos/

El sistema que las tools del agente manipulan. Se monta en el backend como
`/datos` (ver `infra/taller/docker-compose.yml`), así que sobrevive a un
`docker compose down`.

| Archivo | Qué es | ¿Se versiona? |
|---|---|---|
| `inventario.semilla.csv` | El estado inicial: 10 productos | **sí** |
| `inventario.csv` | El estado vivo. Lo modifican los endpoints | no |

El archivo vivo **se crea solo** desde la semilla la primera vez que alguien
consulta el inventario. Hay tres formas de rehacerlo, y la que convenga depende
de qué esté arriba:

| cómo | qué necesita | cuándo |
|---|---|---|
| la celda *"Y el inventario, desde la semilla"* del notebook 00 | nada, es Python puro | al empezar el día, antes de levantar el backend |
| `scripts/<tu-sistema>/reiniciar-datos` | el backend arriba | entre práctica y práctica, y después de cada demo de falla del bloque 5 |
| `POST /api/admin/reiniciar` | el backend arriba | desde un notebook, como lo hace el 03 |

La primera existe porque las otras dos piden el backend, y al arrancar todavía
no está. **Y porque un archivo vivo sucio de una corrida anterior hace que los
notebooks del 02 al 06 arranquen con números que no son los que su texto
describe**, que cuesta más de depurar que un archivo que falta.

## Por qué un CSV y no una base de datos

Para que el asistente pueda **abrirlo y verlo cambiar** mientras el agente
trabaja. Es la mitad de la demo: en una pantalla el chat, en la otra el archivo,
y la relación entre lo que se pide y lo que pasa queda a la vista. Una base de
datos esconde exactamente lo que queremos mostrar, y además obliga a explicar un
motor que no es el tema de estas cuatro horas.

Tiene un costo honesto: un CSV no tiene transacciones. El backend escribe a un
temporal y renombra —así un fallo a mitad no deja el archivo truncado— y
serializa las escrituras con un candado. Con un backend por asistente eso
alcanza de sobra. En producción no serviría, y conviene tenerlo presente
antes de copiar este patrón a otro lado.

## Los endpoints

| Verbo | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/inventario` | Todo. Acepta `?categoria=` y `?con_existencias=` |
| `GET` | `/api/inventario/{sku}` | Uno. El 404 devuelve la lista de SKU válidos |
| `POST` | `/api/inventario` | Crea. 409 si el SKU ya existe |
| `PUT` | `/api/inventario/{sku}` | Actualiza solo los campos que vengan |
| `DELETE` | `/api/inventario/{sku}` | **Borra. Sin papelera.** |

Dos decisiones que no son casuales:

**El 404 devuelve los SKU válidos.** Cuando ese error le vuelve al modelo como
resultado de una tool, puede corregirse solo. Un "no encontrado" a secas lo deja
adivinando, y entonces inventa. Es la idea del paso 3: un error que vuelve al
modelo es información, no una excepción.

**El `DELETE` es el endpoint destructivo del taller.** Es lo que justifica el
guardrail de confirmación humana del paso 4, y lo que la demo de falla 4 ejecuta
sin red para mostrar qué pasa. Un guardrail sobre algo reversible no enseña
nada.

## Los diez productos, y por qué estos

La semilla no es una lista cualquiera: cada grupo provoca un comportamiento.

| | Para qué |
|---|---|
| **Tres cafés** (`CAFE-500`, `CAFE-250`, `CAFE-GRANO-1K`) | "¿Cuánto café hay?" **no tiene una sola respuesta.** Obliga al modelo a desambiguar, a preguntar, o a equivocarse en silencio. Es el caso más útil de los diez. |
| **Dos tés**, uno en **cero** (`TE-200`) | Un cero no es lo mismo que "no existe". Ver cómo lo redacta. |
| **Dos leches**, una **escasa** (`LECHE-1L`, 3 unidades) | "¿Alcanza para cinco pedidos?" obliga a comparar, no solo a consultar. |
| `AZUCAR-1K`, `MIEL-500`, `VASO-360` | Relleno con categorías distintas, para que los filtros tengan algo que filtrar. |

## Qué usa cada paso

| Paso | De dónde saca los datos |
|---|---|
| **2** | Un **diccionario de Python** dentro de `agente.py`. No toca esto. |
| **3 en adelante** | Estos endpoints, por HTTP. |

Que el paso 2 no use el backend es deliberado: ahí se enseña el bucle, y
agregarle HTTP al mismo tiempo mezcla dos cosas. En el paso 3 cambia **el cuerpo
de dos funciones** y el bucle no se toca — ese contraste *es* la lección del
paso 3.
