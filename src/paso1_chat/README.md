# Paso 1 — Hablar con el modelo

**Bloque 2, ~15 min.** Todavia no hay agente.

```
python src/paso1_chat/chat.py
```

| Demo | Qué muestra |
|---|---|
| 1 | Una llamada a un LLM es un `POST`. |
| 2 | El system prompt cambia el comportamiento; el user prompt no manda. |
| 3 | Con temperatura > 0 la misma entrada da salidas distintas. |
| 4 | **El modelo inventa cuando no sabe.** |
| 5 | Token por token, para que "predice el siguiente token" deje de ser una frase. |

La demo 4 es la que importa. Es el momento en que el taller justifica todo lo
que sigue: las tools no se agregan porque sean elegantes, se agregan porque
sin ellas el modelo produce una cifra inventada, con el mismo tono con el que
daría la correcta.

Lee esa respuesta entera antes de pasar al paso 2, y compárala con el
inventario real. No hay nada en el texto que delate cuál de los dos es.

**TODO del asistente:** `demo_6_tu_turno`.
