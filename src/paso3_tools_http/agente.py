"""
PASO 3 — Las mismas tools, contra un sistema de verdad. Bloque 3, ~25 min.

    python src/paso3_tools_http/agente.py

**Compara este archivo con el del paso 2.** Lo único que cambió es el cuerpo de
las funciones: donde había `INVENTARIO.get(sku)` ahora hay un `requests.get()`.
Y eso es todo.

El bucle `correr()` es idéntico, carácter por carácter. El esquema de las tools
es idéntico. El modelo no se entera de nada: pide `consultar_stock("CAFE-500")`
exactamente igual que antes.

Ese es el punto del paso 3: **lo que había debajo era un detalle.** Una tool es
un contrato —un nombre, unos parámetros, un resultado— y lo que pase del otro
lado es asunto tuyo.

Lo nuevo que sí hay que explicar:

  - **Latencia.** Ahora cada vuelta cuesta una llamada al modelo MÁS una al
    backend. Se siente.
  - **El error de red** vuelve al modelo como cualquier otro resultado.
  - **El efecto se ve.** Abre datos/inventario.csv al lado: cuando el agente
    actualiza existencias, el archivo cambia.
  - **Leer y escribir no son lo mismo.** `consultar_stock` se puede repetir sin
    consecuencias; `actualizar_existencias` no. El paso 4 vive de esta
    distinción.
"""

import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlib import chat, normalizar_argumentos  # noqa: E402

MAX_VUELTAS = 8  # el guardrail del paso 4, adelantado: sin esto, bucle infinito

# El backend corre en TU laptop. Sale del .env de la raiz.
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 10


# ---------------------------------------------------------------------------
# 1. Las funciones. Compara con el paso 2: cambio el cuerpo, nada mas.
# ---------------------------------------------------------------------------
def _pedir(metodo, ruta, **kwargs):
    """
    Una llamada al backend, con los errores convertidos en datos.

    Esto es la mitad del paso 3. Un timeout, un 404 o un backend caido NO son
    excepciones que revientan el agente: son resultados que le devolvemos al
    modelo para que decida que hacer. Un 404 con la lista de SKU validos le
    permite corregirse solo; un stack trace lo deja sin nada.
    """
    try:
        r = requests.request(metodo, f"{BACKEND}{ruta}", timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError:
        return {"error": f"no pude hablar con el backend en {BACKEND}",
                "sugerencia": "esta levantado? -> scripts/<tu-sistema>/taller-up"}
    except requests.exceptions.Timeout:
        return {"error": f"el backend no contesto en {TIMEOUT} segundos"}

    if r.status_code >= 400:
        detalle = r.json().get("detail", r.text) if r.content else r.reason
        # El detalle del 404 trae la lista de SKU validos. Se la pasamos tal
        # cual: es lo que le permite al modelo corregir el SKU y reintentar.
        return {"error": detalle} if not isinstance(detalle, dict) else detalle
    return r.json()


def _sin_existencias(respuesta):
    """
    Recorta las existencias del catalogo. Para eso esta consultar_stock.

    El recorte va aqui y no en el backend a proposito: /api/inventario las
    devuelve, y el agente de inventario del paso 5 las necesita. La tool es un
    adaptador sobre la API, no la API. Y es este recorte el que hace que el
    paso 2 y el paso 3 contesten IGUAL a la misma pregunta: lo unico que cambia
    entre un paso y otro es COMO se llega al dato.
    """
    if "productos" not in respuesta:
        return respuesta          # un error del backend vuelve tal cual
    return {**respuesta,
            "productos": [{k: v for k, v in p.items() if k != "existencias"}
                          for p in respuesta["productos"]]}


def consultar_catalogo(categoria=None):
    # paso 2:  return {"productos": [...]}  leyendo un dict
    # paso 3:  una peticion HTTP. El modelo no nota la diferencia.
    params = {"categoria": categoria} if categoria else None
    return _sin_existencias(_pedir("GET", "/api/inventario", params=params))


def consultar_stock(sku):
    # paso 2:  INVENTARIO.get(sku)
    return _pedir("GET", f"/api/inventario/{sku}")


def actualizar_existencias(sku, existencias):
    """
    La primera tool que ESCRIBE. Hasta aqui el agente solo miraba.

    Abre datos/inventario.csv mientras corres esto: el archivo cambia.
    """
    return _pedir("PUT", f"/api/inventario/{sku}", json={"existencias": existencias})


# ---------------------------------------------------------------------------
# 2. Los esquemas. Los dos primeros son IDENTICOS a los del paso 2.
# ---------------------------------------------------------------------------
HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_catalogo",
            "description": (
                "Lista los productos con su clave, nombre y precio. NO devuelve "
                "existencias: para saber cuantas unidades hay de algo, usa "
                "consultar_stock con la clave. Usala cuando no sepas la clave "
                "exacta de un producto que te mencionaron. Acepta una categoria "
                "opcional para filtrar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {
                        "type": "string",
                        "description": "Opcional: cafe, te, endulzante, lacteo, desechable",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_stock",
            "description": (
                "Devuelve las existencias y el precio de UN producto. Usala "
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
            "name": "actualizar_existencias",
            "description": (
                "Cambia las existencias de un producto. MODIFICA EL SISTEMA: "
                "usala solo cuando te lo pidan explicitamente, nunca para "
                "'corregir' algo por tu cuenta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Clave del producto"},
                    "existencias": {"type": "integer",
                                    "description": "El nuevo numero de unidades"},
                },
                "required": ["sku", "existencias"],
            },
        },
    },
]

DISPONIBLES = {
    "consultar_catalogo": consultar_catalogo,
    "consultar_stock": consultar_stock,
    "actualizar_existencias": actualizar_existencias,
}

SYSTEM = (
    "Eres el asistente de la mesa de pedidos. Respondes en espanol, breve. "
    "Cuando necesites datos del sistema, usa las tools: no inventes "
    "numeros ni claves de producto."
)


# ---------------------------------------------------------------------------
# 3. EL BUCLE. Copiado del paso 2 sin tocar una coma.
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


# TODO (taller) 1: agrega una tool `buscar_por_nombre(texto)` que use
#   consultar_catalogo y filtre del lado del cliente. Conviene mas como tool
#   aparte o como parametro de consultar_catalogo?
#
# TODO (taller) 2: apaga el backend (scripts/<tu-sistema>/taller-down) y vuelve
#   a preguntar. Que hace el modelo con el error? Se rinde o lo reintenta?
#
# TODO (taller) 3: pidele que ponga el stock de CAFE-500 en -5. El backend lo
#   rechaza (existencias >= 0). Como se entera el modelo, y que hace?
#
# TODO (taller) 4: compara este archivo con src/paso2_tool/agente.py:
#       git diff --no-index src/paso2_herramienta/agente.py src/paso3_tools_http/agente.py
#   Cuantas lineas del bucle cambiaron?


if __name__ == "__main__":
    for peticion in [
        "Cuanto cafe tenemos?",                      # tres cafes: ambiguo
        "Hay te verde disponible?",                  # existencias en 0
        "Cuantos tornillos tienes?",                  # no existe: inventa o avisa?
        "Acaban de llegar 50 unidades mas de leche entera, actualizalo",  # ESCRIBE
    ]:
        print(f"\n{'='*68}\n> {peticion}")
        correr(peticion)
