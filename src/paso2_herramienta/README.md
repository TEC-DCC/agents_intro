# Paso 2 — El bucle agéntico, a mano

**Bloque 2, ~30 min. Este es el paso que importa.**

```
python src/paso2_herramienta/agente.py
```

Si alguien se lleva una sola cosa del taller, que sea el `while` de la función
`correr`. Debajo de LangChain, de CrewAI, de los Agents SDK y de Claude Code
hay esto — más pulido, con más casos borde, pero esto.

```
mensaje → el modelo pide tool → tu código ejecuta
       → le devuelves el resultado → el modelo sigue
       → hasta que responde sin pedir nada
```

Tres cosas que mirar mientras corre:

1. **El modelo nunca ejecuta nada.** Pide. Tu código decide. El diccionario
   `DISPONIBLES` es el puente, y es también el primer guardrail: lo que no está
   ahí, no corre. Nunca un `eval` ni un `getattr` sobre un nombre que vino del
   modelo.
2. **La `description` de una tool es prompt, no documentación.** Es donde
   más rinde el tiempo de ajuste y donde casi nadie lo invierte.
3. **Un error no es una excepción, es información.** Un SKU inexistente vuelve
   al modelo como texto y el modelo se corrige. O no — y eso también enseña.

Todavía sin backend: las tools leen de un diccionario. Primero el bucle,
después la plomería.

**TODOs del asistente:** 4, al final del archivo. El 3 (borrar "no inventes
números" del system prompt) es el que suele producir la mejor discusión.
