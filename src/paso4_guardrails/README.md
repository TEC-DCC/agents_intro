# Paso 4 — Guardrails y confirmación humana

**Bloque 3, ~20 min. PENDIENTE del caso de estudio.**

El paso 3 deja un agente que funciona. Este lo deja en condiciones de que
alguien lo conecte a algo que importa.

| Guardrail | Contra qué | Dónde |
|---|---|---|
| Tope de iteraciones | el bucle infinito | ya está en el paso 2 (`MAX_VUELTAS`) |
| Lista blanca de tools | nombres inventados | el dict `DISPONIBLES`, ya está |
| Validación de argumentos **antes** de ejecutar | SKU inventado, cantidad negativa, id de otro cliente | nuevo aquí |
| Confirmación humana en lo destructivo | cancelar lo que no debía | nuevo aquí |
| Tope de presupuesto / tiempo | la cuenta a fin de mes | nuevo aquí |

El que produce la mejor discusión es el de la confirmación humana, porque obliga
a una pregunta de diseño que no tiene respuesta única: **¿qué acciones merecen
una pausa?** Si se confirma todo, nadie lee las confirmaciones y el guardrail no
sirve. Si no se confirma nada, el agente borra algo un martes.

Al final del paso conviene volver a la lista y preguntar cuáles de estos
guardrails son *de IA*. Ninguno. Son validación de entrada, control de acceso y
límites de recursos — las mismas tres cosas de siempre. Lo único nuevo es que la
entrada que no se puede confiar ahora la genera el propio sistema.

**Depende de:** el endpoint destructivo del dominio (ver `caso-de-estudio.md`).
Sin una acción que de verdad duela deshacer, este paso se siente inventado.
