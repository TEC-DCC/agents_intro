"""
PASO 2 — El bucle agéntico, escrito a mano. Bloque 2 del taller, 30 minutos.

**Este es el archivo que importa.** De todo el taller, lo que conviene llevarse
es el bucle `while` de la función `correr`. Debajo de LangChain, de CrewAI, de
los Agents SDK y de Claude Code hay esto: más pulido y con más casos borde,
pero esto.

    python src/paso2_herramienta/agente.py

Son unas sesenta líneas, y cada vuelta se imprime entera. Ver el ciclo girar es
lo que hace concreta la idea; un agente que solo devuelve el resultado final se
parece demasiado a una llamada a función.

Todavía sin backend: las tools leen de un diccionario declarado más abajo. El
paso 3 las conecta por HTTP. Primero el bucle, después la plomería.

El texto que imprime va sin acentos, por consistencia con los otros tres pasos.
No es una restricción técnica: medido en esta máquina, Python imprime acentos
bien incluso con la consola en cp850.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlib import chat, normalizar_argumentos  # noqa: E402

MAX_VUELTAS = 8  # el guardrail del paso 4, adelantado: sin esto, bucle infinito

# ---------------------------------------------------------------------------
# El "sistema" del paso 2: el MISMO archivo que usa el backend, pero leido
# directo del disco. Sin HTTP, sin Docker, sin red.
# ---------------------------------------------------------------------------
# Antes esto era un diccionario escrito a mano aqui, y se desincronizo del CSV
# en la primera semana: cinco productos contra diez. Un solo origen evita que
# el paso 2 y el paso 3 muestren inventarios distintos en la misma clase.
#
# Lo que NO cambia respecto de tener el dict a mano: esto sigue siendo Python
# leyendo un archivo local. El backend no hace falta hasta el paso 3, y ahi
# esta la frontera del ejercicio.

DATOS = Path(__file__).resolve().parents[2] / "datos"


def cargar_inventario():
    """
    Lee datos/inventario.csv y devuelve el mismo dict de siempre.

    Si el archivo vivo no existe todavia -porque nadie levanto el backend-
    cae a la semilla. Asi el paso 2 corre en una maquina recien clonada, que
    es justo lo que queremos: el bucle primero, la plomeria despues.
    """
    ruta = DATOS / "inventario.csv"
    if not ruta.exists():
        ruta = DATOS / "inventario.semilla.csv"

    inventario = {}
    with open(ruta, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            inventario[fila["sku"]] = {
                "nombre": fila["nombre"],
                "existencias": int(fila["existencias"]),
                "precio": float(fila["precio"]),
            }
    return inventario


# Se carga UNA vez, al importar. Es un dict comun: puedes modificarlo en
# memoria para probar algo (p2.INVENTARIO["CAFE-500"]["existencias"] = 999) sin
# tocar el archivo.
#
# Los diez productos no son una lista cualquiera. Hay TRES cafes, asi que
# "cuanto cafe hay?" no tiene una sola respuesta y obliga al modelo a
# desambiguar; un te en CERO, que no es lo mismo que "no existe"; y una leche
# escasa, para preguntas del tipo "alcanza para cinco pedidos?".
INVENTARIO = cargar_inventario()


# ---------------------------------------------------------------------------
# 1. Las funciones. Python comun: el modelo no tiene nada que ver con esto.
# ---------------------------------------------------------------------------
def consultar_stock(sku):
    producto = INVENTARIO.get(sku)
    if not producto:
        # Un SKU inexistente NO es una excepcion. Es un hecho que le devolvemos
        # al modelo para que se corrija. Que un error vuelva como informacion en
        # vez de reventar el programa es la mitad del paso 3.
        return {"error": f"no existe el producto '{sku}'",
                "disponibles": list(INVENTARIO.keys())}
    return {"sku": sku, **producto}


def consultar_catalogo():
    # Clave, nombre y precio. Las existencias NO: para saber cuantas unidades
    # hay de algo, el modelo tiene que pedir consultar_stock con la clave.
    #
    # Eso es lo que obliga a COMPONER dos tools, y es la razon de que esta
    # funcion no devuelva el producto entero. Medido el 2026-11-15 contra
    # qwen3.5:9b: cuando devolvia tambien las existencias, "cuantas unidades
    # tenemos de cafe y te?" se resolvia en UNA llamada -el catalogo entregaba
    # la respuesta completa- y el `for pedido in pedidos` de abajo no se
    # ejercitaba en ninguna celda del notebook 02. Sin existencias, el modelo
    # pide el catalogo y despues CINCO consultar_stock en una sola vuelta.
    #
    # El precio se queda. Sin el, en el mismo caso el modelo pidio DOS de los
    # cinco productos y contesto como si fueran todos: quitarlo lo vuelve mas
    # flojo, no mas trabajador.
    return {"productos": [{"sku": k, "nombre": v["nombre"], "precio": v["precio"]}
                          for k, v in INVENTARIO.items()]}


# ---------------------------------------------------------------------------
# 2. La descripcion para el modelo. ESTO ES PROMPT, NO DOCUMENTACION.
# ---------------------------------------------------------------------------
# El modelo decide si llamar una tool leyendo su `description`. Una
# descripcion vaga produce un agente que no la usa, o que la usa de mas. Es el
# lugar donde mas rinde el tiempo de ajuste, y el que casi nadie ajusta.
HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_stock",
            "description": (
                "Devuelve las existencias y el precio de un producto. Usala "
                "siempre que te pregunten cuantas unidades hay o cuanto cuesta "
                "algo: nunca estimes ni adivines cantidades."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string",
                            "description": "Clave del producto, por ejemplo 'CAFE-500'"},
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_catalogo",
            "description": (
                "Lista todos los productos con su clave, nombre y precio. NO devuelve "
                "existencias: para saber cuantas unidades hay de algo, usa "
                "consultar_stock con la clave. Usala cuando no sepas la "
                "clave exacta de un producto que te mencionaron."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# El puente entre el nombre que dice el modelo y la funcion que corre.
# Es un diccionario, y es tambien un guardrail: si el modelo pide algo que no
# esta aca, no se ejecuta. Nunca un `eval`, nunca un `getattr` sobre el nombre
# que vino del modelo.
DISPONIBLES = {
    "consultar_stock": consultar_stock,
    "consultar_catalogo": consultar_catalogo,
}

SYSTEM = (
    "Eres el asistente de la mesa de pedidos. Respondes en espanol, breve. "
    "Cuando necesites datos del sistema, usa las tools: no inventes "
    "numeros ni claves de producto."
)


# ---------------------------------------------------------------------------
# 3. EL BUCLE. Lo que hace que esto sea un agente y no una llamada a funcion.
# ---------------------------------------------------------------------------
def correr(peticion):
    """
    mensaje -> el modelo pide tool -> ejecutamos -> le devolvemos
    el resultado -> el modelo sigue. Hasta que responde sin pedir nada.
    """
    mensajes = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": peticion},
    ]

    for vuelta in range(1, MAX_VUELTAS + 1):
        print(f"\n  --- vuelta {vuelta} ---")
        respuesta = chat(mensajes, herramientas=HERRAMIENTAS)
        mensajes.append(respuesta)

        pedidos = respuesta.get("tool_calls") or []

        # Sin tool_calls, el modelo considera que ya tiene todo: terminamos.
        # Este es el criterio de terminacion, y es el unico que hay.
        if not pedidos:
            print(f"  responde: {respuesta.get('content', '')[:200]}")
            return respuesta.get("content", "")

        # Hay pedidos: los ejecutamos NOSOTROS y le devolvemos los resultados.
        # El modelo nunca toco el sistema. Solo pidio.
        for pedido in pedidos:
            nombre = pedido["function"]["name"]
            argumentos = normalizar_argumentos(pedido)
            print(f"  pide: {nombre}({argumentos})")

            funcion = DISPONIBLES.get(nombre)
            if funcion is None:
                # El modelo invento un nombre de tool. Pasa. Se lo
                # decimos y sigue: no hay por que abortar.
                resultado = {"error": f"no existe la tool '{nombre}'",
                             "disponibles": list(DISPONIBLES)}
            else:
                try:
                    resultado = funcion(**argumentos)
                except TypeError as e:
                    resultado = {"error": f"argumentos invalidos: {e}"}

            print(f"  resultado: {resultado}")
            mensajes.append({"role": "tool", "content": json.dumps(resultado, ensure_ascii=False)})

    # Se agotaron las vueltas. Que esto exista es lo que separa un agente de un
    # proceso que hay que matar a mano. -> demo de falla 1, bloque 5.
    print(f"  BLOQUEADO: {MAX_VUELTAS} vueltas sin respuesta.")
    return "Me quede sin vueltas. No pude resolverlo."


# TODO (taller) 1: agregar una tool `buscar_producto(texto)` que busque
#   por nombre en vez de por clave, y ver si el modelo la prefiere sobre
#   consultar_catalogo. Cambia la respuesta si mejoras su `description`?
#
# TODO (taller) 2: preguntar "cuanto te tengo que pagar por 3 cafes y 2 azucares".
#   Cuantas vueltas da? Sabe sumar o pide ayuda?
#
# TODO (taller) 3: borrar la frase "no inventes numeros" del SYSTEM y volver a
#   correr. Que cambia?
#
# TODO (taller) 4: bajar MAX_VUELTAS a 1 y preguntar algo que necesite dos
#   tools. Que contesta?


if __name__ == "__main__":
    for peticion in [
        "Cuantas unidades hay de cafe?",            # necesita el catalogo y luego el stock
        "Hay te verde disponible?",                 # existencias en 0: como lo dice?
        "Cuantos tornillos tienes?",                 # no existe: inventa o avisa?
        "Hola, como estas?",                        # no deberia llamar nada
    ]:
        print(f"\n{'='*68}\n> {peticion}")
        correr(peticion)
