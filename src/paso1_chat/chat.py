"""
PASO 1 — Hablar con el modelo. Bloque 2 del taller, 15 minutos.

Todavía no hay agente. Hay un modelo que recibe texto y devuelve texto. Antes
de construir encima conviene ver el piso.

    python src/paso1_chat/chat.py

Cuatro demostraciones, en este orden:

  1. Una llamada a un modelo de lenguaje es un POST. Nada más.
  2. El system prompt cambia el comportamiento; el user prompt no manda.
  3. Con temperatura mayor que 0, la misma entrada da salidas distintas. De ahí
     sale que un agente no se pruebe como se prueba una función (bloque 5).
  4. El modelo produce cifras inventadas cuando no tiene de dónde sacarlas.
     Esa demostración justifica el paso 2: las tools no se agregan porque sean
     elegantes, se agregan porque sin ellas la respuesta se ve igual de segura
     y es falsa.

El texto que imprime va sin acentos, por consistencia con los otros tres pasos.
No es una restricción técnica: medido en esta máquina, Python imprime acentos
bien incluso con la consola en cp850.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlib import chat, streaming  # noqa: E402


def demo_1_lo_minimo():
    print("\n--- 1. La llamada mas corta posible ---")
    respuesta = chat([{"role": "user", "content": "Explicame que es un token en una oracion."}])
    print(respuesta["content"])


def demo_2_system_prompt():
    print("\n--- 2. El system prompt manda ---")
    # Misma pregunta del usuario, dos identidades. La diferencia no la pone el
    # modelo: la pone quien escribe el system prompt. Es decir, tu.
    for identidad in [
        "Eres un profesor de secundaria. Responde en una oracion simple.",
        "Eres un investigador. Responde con precision tecnica y menciona la arquitectura.",
    ]:
        respuesta = chat([
            {"role": "system", "content": identidad},
            {"role": "user", "content": "Que es un LLM?"},
        ])
        print(f"\n[{identidad[:35]}...]")
        print(respuesta["content"][:300])


def demo_3_no_determinismo():
    print("\n--- 3. La misma entrada, salidas distintas ---")

    UNA_PALABRA = "Di una fruta. Solo el nombre."
    UNA_ORACION = "Escribe UNA oracion de unas diez palabras sobre el mar."

    def tres(prompt, **opciones):
        return [chat([{"role": "user", "content": prompt}], **opciones)["content"].strip()
                for _ in range(3)]

    # Primero la demo que NO funciona, porque ensena mas que la que si.
    # Una palabra es UNA decision de muestreo, y si un candidato domina
    # -"Manzana" lo hace- gana casi siempre. Medido: 8 muestras dan de 1 a 3
    # salidas distintas, segun la temperatura. Ver planeacion/hallazgos.md
    print("\n  UNA PALABRA, donde casi no se ve:")
    print("    temp 0.0:", tres(UNA_PALABRA, temperatura=0.0))
    print("    temp 0.8:", tres(UNA_PALABRA, temperatura=0.8))

    # Una oracion son unas doce decisiones y las divergencias se acumulan:
    # basta que una salga distinta para que cambie la frase entera. Medido:
    # 8 de 8 distintas a cualquier temperatura > 0.
    print("\n  UNA ORACION, con largo suficiente para que se vea:")
    for t in (0.0, 0.8):
        print(f"\n    temperatura {t}:")
        for salida in tres(UNA_ORACION, temperatura=t):
            print(f"      {salida}")

    print("\n  El no determinismo se acumula con el largo. Por eso se nota en un")
    print("  agente -que genera mucho, muchas veces- y no en un clasificador que")
    print("  responde una palabra.")
    print("  Y por eso un agente no se prueba comparando cadenas. -> bloque 5, evals/")

def demo_4_la_mentira():
    print("\n--- 4. Sin tools, el modelo INVENTA ---")
    # El momento mas importante del bloque 2. El modelo no tiene forma de saber
    # esto: no hay base de datos, no hay internet, no hay nada. Y aun asi
    # contesta un numero, con seguridad, sin avisar que lo invento.
    respuesta = chat([
        {"role": "system", "content": "Eres el asistente de la mesa de pedidos."},
        {"role": "user", "content": "Cuantas unidades hay del producto CAFE-500?"},
    ])
    print(respuesta["content"])
    print("\nNo pregunto. No dudo. Contesto. Eso es lo que arregla el paso 2.")


def demo_5_streaming():
    print("\n--- 5. Token por token ---")
    for pedazo in streaming([{"role": "user", "content": "Cuenta del 1 al 15."}]):
        print(pedazo, end="", flush=True)
    print()


# TODO (taller): escribe un system prompt que haga que el modelo responda
# SIEMPRE en forma de pregunta, y pruebalo. Cuanto cuesta que lo desobedezca?
def demo_6_tu_turno():
    pass


if __name__ == "__main__":
    demo_1_lo_minimo()
    demo_2_system_prompt()
    demo_3_no_determinismo()
    demo_4_la_mentira()
    demo_5_streaming()
