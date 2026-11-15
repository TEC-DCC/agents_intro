# src/

El código. Dividido entre lo que se da resuelto y lo que escribe el asistente —
una línea que vale la pena respetar, porque es la que define qué enseña el
taller.

## Los pasos

| Carpeta | Bloque | Min | Qué se aprende | Estado |
|---|---|---|---|---|
| [`paso1_chat/`](paso1_chat/) | 2 | 15 | Un LLM es un `POST`. Y miente cuando no sabe. | completo |
| [`paso2_herramienta/`](paso2_herramienta/) | 2 | 30 | **El bucle agéntico, a mano.** | completo |
| [`paso3_tools_http/`](paso3_tools_http/) | 3 | 25 | Tools contra un sistema real. El bucle no cambia. | completo |
| [`paso4_guardrails/`](paso4_guardrails/) | 3 | 20 | Validación, antirrepetición, confirmación humana. **Aquí el bucle sí cambia.** | completo |
| [`paso5_multiagente/`](paso5_multiagente/) | 4 | 50 | Tres agentes y un orquestador. | pendiente del caso |
| [`solucion/`](solucion/) | — | — | Todo resuelto, para no quedarse atorado. | pendiente |

Cada paso **corre tal cual** y tiene de 3 a 6 bloques `# TODO (taller)`. El
asistente escribe código, no infraestructura.

## Lo compartido

| Carpeta | Qué es |
|---|---|
| [`agentlib/`](agentlib/) | Transporte HTTP y la traza. **Nada más.** `ollama.py` es la llamada cruda que el taller enseña; `proveedores.py` despacha a azure/foundry/mistral según el `proveedor:modelo` del `.env`. |
| [`backend/`](backend/) | FastAPI: el sistema que el agente manipula, el chat —por donde pasan las claves— y un espejo de solo lectura de Ollama en `/api/ollama/*`. Su Swagger está en [localhost:8000/docs](http://localhost:8000/docs). |
| [`frontend/`](frontend/) | Una página: chat con panel de parámetros, tablero y traza. Ver su [README](frontend/README.md). |

## La regla de `agentlib/`

En `agentlib/` no vive el bucle agéntico, ni el enrutamiento entre agentes, ni
los guardrails. Solo `requests.post` y un emisor de trazas.

Si algo de eso termina ahí, el paquete se convirtió en el framework que el
taller promete no usar, y el asistente se va con una dependencia en lugar de un
modelo mental. El bucle se escribe en `paso2_herramienta/agente.py`, a mano,
mirándolo.

Lo que sí va en `agentlib/`: lo que es aburrido *y* fácil de equivocar. Armar el
JSON de `/api/chat` no enseña nada sobre agentes, pero una llave mal escrita
cuesta diez minutos de taller.
