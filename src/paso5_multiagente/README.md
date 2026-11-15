# Paso 5 — Varios agentes

**Bloque 4, ~50 min. PENDIENTE del caso de estudio.**

Tres agentes con una responsabilidad clara cada uno, y un orquestador que
reparte.

| Agente | Responsabilidad | Tools |
|---|---|---|
| **Recepción** | Entiende la petición y decide a quién le toca. | ninguna |
| **Inventario** | Responde sobre el estado del sistema. Solo lectura. | las de consulta |
| **Pedidos** | Crea y cancela. El único que escribe. | las de escritura + la destructiva |

**El reparto es la lección.** El agente que puede romper cosas es uno solo, y es
el que tiene las reglas más estrictas. Eso no es una decisión de IA: es diseño
de permisos, y es tan viejo como los sistemas multiusuario.

Lo que hay que explicar aquí y en ningún otro lado:

- **Qué viaja en el handoff.** Si Recepción le pasa a Pedidos un resumen, se
  pierde información y aparece la demo de falla 3. Si le pasa todo el historial,
  se paga el contexto completo en cada salto. No hay opción gratis.
- **La traza con nombres.** El panel derecho de la página ahora dice *quién*
  hizo cada cosa. Sin eso, depurar tres agentes no determinista es imposible.
- **Patrones de orquestación**: router (lo que hacemos), supervisor, pipeline.
  Treinta segundos cada uno, no más.

Y la pregunta con la que hay que cerrar el bloque, en serio y no de adorno:

> Comparado con el agente único del paso 4, **¿esto mejoró algo, o solo se
> volvió más caro?**

Para varias de las peticiones de prueba la respuesta honesta es "solo más caro".
Decirlo es lo que le da credibilidad al resto. Un taller que vende multiagente
como la respuesta a todo deja a la gente peor de lo que llegó.

**Depende de:** los pasos 3 y 4, y del caso de estudio.
