"""
PASO 4 — Guardrails y confirmación humana. Bloque 3, ~20 min.

    python src/paso4_guardrails/agente.py

El paso 3 dejó un agente que funciona. Este lo deja en condiciones de que
alguien lo conecte a algo que importa.

**Aquí el bucle SÍ cambia**, y es la primera vez. En los pasos 2 y 3 `correr()`
era idéntico carácter por carácter; ahora crecen unas veinte líneas, y todas
hacen lo mismo: **decidir si una petición del modelo se ejecuta o no.**

Los cinco guardrails, en orden de cuándo actúan:

  1. LISTA BLANCA          ya estaba. Lo que no está en DISPONIBLES, no corre.
  2. TOPE DE VUELTAS       ya estaba. Corta el bucle infinito.
  3. ANTIRREPETICION       nuevo. La misma tool con los mismos argumentos dos
                           veces seguidas no se ejecuta la segunda.
  4. VALIDACION            nuevo. Los argumentos se revisan ANTES de ejecutar.
  5. CONFIRMACION HUMANA   nuevo. Lo destructivo se detiene y pregunta.

Ninguno de los cinco es "de IA". Son lista blanca, límite de recursos,
validación de entrada y control de acceso: las mismas cuatro cosas de siempre.
Lo único nuevo es que la entrada en la que no se puede confiar ahora la genera
el propio sistema.
"""

import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlib import chat, normalizar_argumentos  # noqa: E402

MAX_VUELTAS = 8
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 10


# ---------------------------------------------------------------------------
# 1. Las funciones. Las tres del paso 3, mas una que BORRA.
# ---------------------------------------------------------------------------
def _pedir(metodo, ruta, **kwargs):
    try:
        r = requests.request(metodo, f"{BACKEND}{ruta}", timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError:
        return {"error": f"no pude hablar con el backend en {BACKEND}",
                "sugerencia": "esta levantado? -> scripts/<tu-sistema>/taller-up"}
    except requests.exceptions.Timeout:
        return {"error": f"el backend no contesto en {TIMEOUT} segundos"}
    if r.status_code >= 400:
        detalle = r.json().get("detail", r.text) if r.content else r.reason
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
    params = {"categoria": categoria} if categoria else None
    return _sin_existencias(_pedir("GET", "/api/inventario", params=params))


def consultar_stock(sku):
    return _pedir("GET", f"/api/inventario/{sku}")


def actualizar_existencias(sku, existencias):
    return _pedir("PUT", f"/api/inventario/{sku}", json={"existencias": existencias})


def borrar_producto(sku):
    """
    Borra un producto del inventario. NO HAY PAPELERA.

    Esta es la tool que justifica todo el paso. Un guardrail sobre algo
    reversible no ensena nada: si deshacer es gratis, confirmar sobra.
    """
    return _pedir("DELETE", f"/api/inventario/{sku}")


DISPONIBLES = {
    "consultar_catalogo": consultar_catalogo,
    "consultar_stock": consultar_stock,
    "actualizar_existencias": actualizar_existencias,
    "borrar_producto": borrar_producto,
}

# GUARDRAIL 5: que tools no se ejecutan sin permiso explicito.
#
# Es una decision de diseno, no una propiedad del modelo: lo decides tu,
# mirando que hace cada tool. Leer nunca; escribir, depende; borrar, siempre.
DESTRUCTIVAS = {"borrar_producto"}


# ---------------------------------------------------------------------------
# 2. GUARDRAIL 4: validar los argumentos ANTES de ejecutar
# ---------------------------------------------------------------------------
# El backend ya valida. Esto valida otra vez, antes, y a proposito:
#
#   - El error llega mas claro y mas barato: sin viaje de red.
#   - Lo que el backend NO sabe, aqui si: "no borres mas de uno por peticion",
#     "no toques productos de esta categoria". Son reglas del agente, no del
#     dominio.
#   - Y lo principal: el backend es UN consumidor. Si manana el agente llama a
#     otra cosa, la regla viaja con el agente.
def validar(nombre, argumentos):
    """Devuelve None si esta bien, o un texto explicando que falla."""
    if "__error__" in argumentos:
        return argumentos["__error__"]

    sku = argumentos.get("sku")
    if sku is not None:
        if not isinstance(sku, str) or not sku.strip():
            return "el sku tiene que ser un texto no vacio"
        # Los SKU del sistema son MAYUSCULAS con guiones. Un 'CAFE' pelado o un
        # 'cafe molido' no lo son, y vale avisarlo antes de gastar una llamada.
        if not all(c.isalnum() or c in "-_" for c in sku):
            return f"'{sku}' no parece un sku: solo letras, numeros y guiones"

    if nombre == "actualizar_existencias":
        n = argumentos.get("existencias")
        if not isinstance(n, int) or isinstance(n, bool):
            return f"existencias tiene que ser un entero, llego {n!r}"
        if n < 0:
            return "existencias no puede ser negativo"
        if n > 10000:
            # Un tope arbitrario, y por eso mismo util de discutir: de donde
            # sale el numero? De conocer el negocio, no de conocer el modelo.
            return f"{n} unidades es demasiado; el tope es 10000"

    return None


# ---------------------------------------------------------------------------
# 3. GUARDRAIL 5: la confirmacion humana
# ---------------------------------------------------------------------------
def confirmar_en_consola(nombre, argumentos):
    """
    Se detiene y pregunta. Devuelve True si el humano autoriza.

    Es `input()` a proposito: que el programa se DETENGA es la mitad de la
    leccion. Un guardrail que solo registra en un log no detiene nada.
    """
    print()
    print("  " + "!" * 60)
    print(f"  !!  El agente quiere ejecutar una accion DESTRUCTIVA:")
    print(f"  !!      {nombre}({argumentos})")
    print("  " + "!" * 60)
    respuesta = input("  ¿Autorizas? [s/N] ").strip().lower()
    return respuesta.startswith("s")


def aprobar_todo(nombre, argumentos):
    """Para la demo de falla: el guardrail apagado. NO usar de verdad."""
    print(f"  [confirmacion DESACTIVADA, ejecutando {nombre}]")
    return True


def rechazar_todo(nombre, argumentos):
    """Para probar el camino del 'no' sin tener que teclearlo."""
    print(f"  [rechazado automaticamente: {nombre}]")
    return False


# ---------------------------------------------------------------------------
# 4. Los esquemas
# ---------------------------------------------------------------------------
HERRAMIENTAS = [
    {"type": "function", "function": {
        "name": "consultar_catalogo",
        "description": ("Lista los productos con su clave, nombre y precio. NO "
                        "devuelve existencias: para saber cuantas unidades hay de "
                        "algo, usa consultar_stock con la clave. Usala cuando no "
                        "sepas la clave exacta de un producto. Acepta una "
                        "categoria opcional para filtrar."),
        "parameters": {"type": "object", "properties": {
            "categoria": {"type": "string",
                          "description": "Opcional: cafe, te, endulzante, lacteo, desechable"}}}}},
    {"type": "function", "function": {
        "name": "consultar_stock",
        "description": ("Devuelve las existencias y el precio de UN producto. "
                        "El sku debe salir de consultar_catalogo: nunca lo inventes."),
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "description": "Clave exacta, por ejemplo 'CAFE-500'"}},
            "required": ["sku"]}}},
    {"type": "function", "function": {
        "name": "actualizar_existencias",
        "description": ("Cambia las existencias de un producto. MODIFICA EL SISTEMA: "
                        "usala solo cuando te lo pidan explicitamente."),
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "description": "Clave del producto"},
            "existencias": {"type": "integer", "description": "El nuevo numero de unidades"}},
            "required": ["sku", "existencias"]}}},
    {"type": "function", "function": {
        "name": "borrar_producto",
        "description": ("ELIMINA un producto del inventario de forma permanente. "
                        "No se puede deshacer. Requiere autorizacion de la persona."),
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "description": "Clave del producto a eliminar"}},
            "required": ["sku"]}}},
]

SYSTEM = (
    "Eres el asistente de la mesa de pedidos. Respondes en espanol, breve. "
    "Cuando necesites datos del sistema, usa las tools: no inventes numeros "
    "ni claves de producto. Si una accion se rechaza, explicaselo a la persona "
    "y no insistas."
)


# ---------------------------------------------------------------------------
# 5. EL BUCLE, ahora con los guardrails. Compara con el del paso 3.
# ---------------------------------------------------------------------------
def correr(peticion, confirmar=confirmar_en_consola, validando=True):
    """
    Igual que el del paso 3, mas las comprobaciones antes de cada ejecucion.

        confirmar   funcion (nombre, argumentos) -> bool, para lo destructivo.
                    aprobar_todo o rechazar_todo para demos sin teclear.
        validando   False apaga la validacion, para ver que pasa sin ella.
    """
    mensajes = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": peticion},
    ]
    vistas = []   # GUARDRAIL 3: peticiones ya ejecutadas, para detectar repeticion

    for vuelta in range(1, MAX_VUELTAS + 1):
        print(f"\n  --- vuelta {vuelta} ---")
        respuesta = chat(mensajes, herramientas=HERRAMIENTAS)
        mensajes.append(respuesta)

        pedidos = respuesta.get("tool_calls") or []
        if not pedidos:
            print(f"  responde: {respuesta.get('content', '')[:200]}")
            return respuesta.get("content", "")

        for pedido in pedidos:
            nombre = pedido["function"]["name"]
            argumentos = normalizar_argumentos(pedido)
            print(f"  pide: {nombre}({argumentos})")

            resultado = None
            firma = (nombre, json.dumps(argumentos, sort_keys=True))

            # --- 1. LISTA BLANCA --------------------------------------------
            if nombre not in DISPONIBLES:
                resultado = {"error": f"no existe la tool '{nombre}'",
                             "disponibles": list(DISPONIBLES)}
                print(f"  [BLOQUEADO por lista blanca]")

            # --- 3. ANTIRREPETICION -----------------------------------------
            # Si ya hizo exactamente esto, el resultado seria el mismo. Repetir
            # es la forma mas comun de bucle infinito, y el tope de vueltas la
            # corta tarde y sin explicar por que.
            elif firma in vistas:
                resultado = {"error": "ya ejecutaste esta misma peticion y el "
                                      "resultado fue el mismo. Usa lo que ya tienes "
                                      "o prueba algo distinto."}
                print(f"  [BLOQUEADO por repeticion]")

            # --- 4. VALIDACION ----------------------------------------------
            elif validando and (falla := validar(nombre, argumentos)):
                resultado = {"error": f"argumentos invalidos: {falla}"}
                print(f"  [BLOQUEADO por validacion: {falla}]")

            # --- 5. CONFIRMACION HUMANA -------------------------------------
            elif nombre in DESTRUCTIVAS and not confirmar(nombre, argumentos):
                resultado = {"error": "la persona NO autorizo esta accion",
                             "accion": f"{nombre}({argumentos})"}
                print(f"  [RECHAZADO por la persona]")

            # --- ejecutar ----------------------------------------------------
            if resultado is None:
                vistas.append(firma)
                try:
                    resultado = DISPONIBLES[nombre](**argumentos)
                except TypeError as e:
                    resultado = {"error": f"argumentos invalidos: {e}"}

            print(f"  resultado: {resultado}")
            mensajes.append({"role": "tool",
                             "content": json.dumps(resultado, ensure_ascii=False)})

    print(f"  BLOQUEADO: {MAX_VUELTAS} vueltas sin respuesta.")
    return "Me quede sin vueltas. No pude resolverlo."


# TODO (taller) 1: `actualizar_existencias` escribe y NO pide confirmacion.
#   Agregala a DESTRUCTIVAS y vuelve a correr. Te parece bien el resultado?
#   Cuantas confirmaciones de mas aparecen?
#
# TODO (taller) 2: escribe un confirmador que apruebe solo si el producto tiene
#   0 existencias. Es un guardrail mejor que preguntar siempre?
#
# TODO (taller) 3: el tope de 10000 unidades de validar() es arbitrario. De
#   donde deberia salir ese numero?
#
# TODO (taller) 4: apaga la validacion (validando=False) y pide algo invalido.
#   Quien lo atrapa ahora, y que tan claro es el error que llega?


if __name__ == "__main__":
    print("=" * 68)
    print("  Con confirmacion: te va a preguntar antes de borrar.")
    print("=" * 68)
    correr("Borra el te verde del inventario, ya no lo vamos a vender")
