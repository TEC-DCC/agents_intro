# frontend/

Una página, tres paneles, servida por Nginx. Sin framework y sin paso de build:
tres archivos que se editan y se recargan.

```
index.html   la estructura
app.js       habla con el backend
estilo.css   claro y oscuro, y se apila debajo de 1100px
```

## Los tres paneles

| Panel | Qué muestra | Estado |
|---|---|---|
| izquierda | el **chat** y los parámetros | funcionando |
| centro | el **tablero**: el efecto, que cambia solo | pendiente del caso de estudio |
| derecha | la **traza**: el cómo, paso por paso | sondea `/api/trazas` cada segundo |

Los tres hacen falta. Sin el centro, un agente es indistinguible de un chatbot.
Sin la derecha, es una caja negra. Que las tres cosas se vean al mismo tiempo es
lo que produce el momento que la gente recuerda.

## La página no habla con el modelo

```
navegador → nginx :4200 → backend :8000 → proveedor
                              ↑ las claves de API viven solo aquí
```

La página es estática y cualquiera puede leer su código: una clave de Azure aquí
sería una clave publicada. Con Ollama local da igual, no hay clave; con Azure,
Foundry o Mistral no es negociable.

Es el mismo razonamiento del paso 4 del taller —qué puede tocar quién— aplicado
a secretos en vez de a tools, y vale señalarlo cuando se muestre la
página.

## El panel de parámetros

Plegado arriba del chat. **Un campo vacío no se manda**, y entonces el backend
usa el valor del `.env` o el que trae el modelo. El `placeholder` de cada campo
dice cuál es ese valor.

| Control | Vacío significa |
|---|---|
| `system prompt` | el que trae el backend |
| `temperatura` | `TEMPERATURE` del `.env` |
| `top_k` | el del modelo (20 en `qwen3.5:9b`) |
| `top_p` | el del modelo (0.95) |

La temperatura tiene deslizador *y* casilla numérica: el deslizador para
arrastrarlo en vivo, la casilla para poder dejarla vacía.

**El botón "cargar la demo"** pone `temperatura 1.5`, `top_k 100`, `top_p 1.0`.
Esos valores no son arbitrarios: son los que hacen visible el no determinismo.
Subir la temperatura sola **no cambia nada**, porque el `top_k 20` y el
`top_p 0.95` del modelo recortan los candidatos antes de que la temperatura
entre en juego. Está medido en [`hallazgos.md`](../../planeacion/hallazgos.md).

Con eso el panel da dos lecciones del bloque 1 en lugar de una:

1. "Temperatura = creatividad" es folclore. El muestreo es una cadena de filtros
   y la temperatura es solo uno.
2. Con los filtros abiertos y temperatura 1.5, el modelo produce galimatías.
   Temperatura alta no es creatividad, es degradación.

Los valores se guardan en `localStorage`, así que sobreviven a un refresco a
mitad de clase. La casilla **razonar** vive en la cabecera y no en el panel,
porque se enciende y apaga seguido durante las demos.

Cada respuesta muestra abajo con qué se generó: modelo, segundos y los
parámetros que se mandaron. En una clase donde se cambian valores en vivo, saber
qué produjo cada respuesta importa más que la respuesta.

## Decisiones que parecen descuidos y no lo son

**`textContent`, nunca `innerHTML`**, para lo que devuelve el modelo. Es texto,
no marcado confiable.

**Sondeo cada segundo en vez de WebSockets.** Veinte líneas contra cien, y en
una página de taller nadie nota la diferencia. Elegir la opción simple donde no
importa es parte de lo que el taller debería modelar.

**El historial vive en el navegador**, y cada petición le manda la conversación
completa al backend. No es una limitación del ejemplo: es cómo funciona un LLM.
La ventana de contexto es su única memoria, y lo que parece "recordar" es que
alguien le reenvía el historial —y lo paga en tokens— cada vez. El contador
abajo del chat muestra cuántos mensajes van en el contexto, justamente para que
eso se vea crecer.

**Los errores se muestran en el chat**, no en la consola del navegador. Si algo
falla durante el taller, el asistente tiene que poder leerlo sin abrir las
tools de desarrollo.
