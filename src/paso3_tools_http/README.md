# Paso 3 — Tools de verdad

**Bloque 3, ~25 min. PENDIENTE del caso de estudio.**

Las mismas tools del paso 2, pero ahora llamando al backend por HTTP en
lugar de leer un diccionario. El cambio es de una línea por tool, y es
exactamente el punto: **el bucle no cambia.** Lo que había debajo era un
detalle; el agente no se enteró.

Lo nuevo que sí hay que explicar:

- **Latencia.** Ahora cada vuelta cuesta una llamada al modelo *más* una al
  backend. Se siente.
- **El error de red** vuelve al modelo como cualquier otro resultado.
- **El efecto se ve en la pantalla.** Esta es la primera vez que el asistente
  escribe una frase y algo cambia en `http://localhost:4200`. Vale la pena
  pausar ahí.
- **Lectura y escritura no son lo mismo.** `consultar_stock` se puede repetir
  sin consecuencias; `crear_pedido` no. El paso 4 vive de esta distinción.

**Depende de:** los endpoints del dominio en `src/backend/app/main.py`, que
esperan el cierre de `planeacion/caso-de-estudio.md`.
