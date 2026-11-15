#!/usr/bin/env python3
"""
Smoke test del riesgo #1 del plan: ¿qwen3.5:9b hace tool calling de verdad?

Las notas del .env de itzae registran que este modelo produjo "8428 caracteres
de pensamiento y 0 de respuesta, y subir el techo a 8192 no lo arregla". Si eso
le pasa cuando hay tools en juego, el taller entero no existe: los pasos
2 al 5 asumen que el modelo devuelve `message.tool_calls` bien formado.

Hay que correrlo ANTES de escribir el resto del material. Si falla, el plan B
es qwen3:8b o llama3.1:8b.

    python scripts/smoke_test_tools.py
    python scripts/smoke_test_tools.py --modelo qwen3:8b
    python scripts/smoke_test_tools.py --url http://192.168.1.100:11434

Prueba cuatro cosas, en orden de qué rompe más:

  1. El modelo responde algo (no solo piensa).
  2. Pide la tool cuando debe, con argumentos bien formados.
  3. Usa el resultado que le devolvemos en vez de inventar.
  4. NO pide tool cuando la pregunta no la necesita.

La 4 importa tanto como la 2: un modelo que llama tools para todo hace
el bucle infinito del bloque 5 sin que nadie se lo pida.
"""

import argparse
import json
import os
import sys
import time

import requests

# La consola de Windows usa cp1252 por omision y destroza los acentos. En el
# proyector del aula eso se ve. Esto lo arregla sin pedirle nada al asistente.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TIMEOUT = 180  # un 9B cargando desde disco por primera vez no es rapido

HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_stock",
            "description": (
                "Devuelve las existencias actuales de un producto. "
                "Úsala siempre que te pregunten cuántas unidades hay: "
                "no adivines ni estimes cantidades."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "Clave del producto, por ejemplo 'CAFE-500'",
                    }
                },
                "required": ["sku"],
            },
        },
    }
]


def chat(url, modelo, mensajes, con_herramientas=True):
    """Una llamada a /api/chat. Sin librerías de agentes: esto es todo lo que hay."""
    cuerpo = {
        "model": modelo,
        "messages": mensajes,
        "stream": False,
        # La clave del riesgo #1. Ollama acepta `think` en modelos de
        # razonamiento; en los que no lo son, lo ignora sin quejarse.
        "think": False,
        "options": {"temperature": 0},
    }
    if con_herramientas:
        cuerpo["tools"] = HERRAMIENTAS

    t0 = time.time()
    r = requests.post(f"{url}/api/chat", json=cuerpo, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json(), time.time() - t0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=None,
                   help="por omision, el destino activo del .env (OLLAMA_DESTINO)")
    p.add_argument("--modelo", default=None,
                   help="por omision, el modelo activo del .env (CHAT_MODEL)")
    args = p.parse_args()
    # Sin --url, la direccion sale del .env igual que para todo lo demas.
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
    from agentlib.ollama import _config, base_url
    cfg = _config()
    url = args.url.rstrip("/") if args.url else base_url()
    modelo = args.modelo or cfg["OLLAMA_MODEL"]

    print(f"Ollama : {url}")
    print(f"Modelo : {modelo}\n")

    fallas = []

    # ---- 0. Esta arriba y tiene el modelo? ---------------------------------
    try:
        tags = requests.get(f"{url}/api/tags", timeout=10).json()
    except Exception as e:
        print(f"FALLA  Ollama no responde en {url}")
        print(f"       {e}")
        carpeta = ("win", "aula-firewall.ps1") if sys.platform == "win32" else (
            ("mac", "aula-firewall.sh") if sys.platform == "darwin"
            else ("linux", "aula-firewall.sh"))
        print(f"\n       Si es LAN: puede faltar la regla de firewall ->"
              f" scripts/{carpeta[0]}/{carpeta[1]}")
        return 1

    disponibles = [m["name"] for m in tags.get("models", [])]
    print(f"Modelos disponibles: {', '.join(disponibles) or '(ninguno)'}")
    if modelo not in disponibles:
        print(f"\nFALLA  '{modelo}' no está descargado.")
        print(f"       docker exec agenticai_ollama ollama pull {modelo}")
        return 1
    print()

    # ---- 1. Responde algo, o solo piensa? ---------------------------------
    print("[1/4] ¿Produce respuesta (y no solo pensamiento)?")
    r, dt = chat(url, modelo, [{"role": "user", "content": "Di 'listo' y nada más."}],
                 con_herramientas=False)
    msg = r.get("message", {})
    contenido = (msg.get("content") or "").strip()
    pensamiento = (msg.get("thinking") or "")
    print(f"      respuesta   : {len(contenido)} chars -> {contenido[:60]!r}")
    print(f"      pensamiento : {len(pensamiento)} chars")
    print(f"      latencia    : {dt:.1f}s")
    if not contenido:
        print("      FALLA — justo el modo descrito en el .env de itzae: piensa y no responde.")
        fallas.append("respuesta vacía")
    else:
        print("      OK")
    print()

    # ---- 2. Pide la tool, bien formada? ----------------------------
    print("[2/4] ¿Pide la tool con argumentos bien formados?")
    r, dt = chat(url, modelo,
                 [{"role": "user", "content": "¿Cuántas unidades hay del producto CAFE-500?"}])
    msg = r.get("message", {})
    llamadas = msg.get("tool_calls") or []
    print(f"      tool_calls  : {len(llamadas)}")
    print(f"      latencia    : {dt:.1f}s")
    if not llamadas:
        print(f"      FALLA — no pidió nada. Contestó: {(msg.get('content') or '')[:120]!r}")
        print("      Sin esto no hay taller: los pasos 2 al 5 dependen de tool_calls.")
        fallas.append("no emite tool_calls")
        primera = None
    else:
        primera = llamadas[0]["function"]
        argumentos = primera.get("arguments")
        print(f"      nombre      : {primera.get('name')}")
        print(f"      argumentos  : {argumentos!r} (tipo {type(argumentos).__name__})")
        if primera.get("name") != "consultar_stock":
            print("      FALLA — inventó el nombre de la tool.")
            fallas.append("nombre de tool inventado")
        # Ollama suele devolver dict; algunos modelos devuelven string JSON.
        # Vale la pena saber cual, porque el paso 2 tiene que normalizarlo.
        if isinstance(argumentos, str):
            print("      NOTA — argumentos como string JSON: el bucle debe hacer json.loads.")
            try:
                argumentos = json.loads(argumentos)
            except json.JSONDecodeError:
                print("      FALLA — y además no es JSON válido.")
                fallas.append("argumentos no parseables")
                argumentos = {}
        if isinstance(argumentos, dict) and "sku" not in argumentos:
            print("      FALLA — falta el parámetro requerido 'sku'.")
            fallas.append("argumentos incompletos")
        if not fallas:
            print("      OK")
    print()

    # ---- 3. Usa el resultado que le devolvemos? ---------------------------
    print("[3/4] ¿Usa el resultado de la tool en vez de inventar?")
    if primera is None:
        print("      SALTADO (no hubo tool_call en el paso 2)")
    else:
        historial = [
            {"role": "user", "content": "¿Cuántas unidades hay del producto CAFE-500?"},
            msg,
            {"role": "tool", "content": json.dumps({"sku": "CAFE-500", "existencias": 17})},
        ]
        r, dt = chat(url, modelo, historial)
        final = (r.get("message", {}).get("content") or "").strip()
        print(f"      respuesta   : {final[:200]!r}")
        print(f"      latencia    : {dt:.1f}s")
        if "17" in final:
            print("      OK — citó el número que le dimos.")
        else:
            print("      FALLA — ignoró el resultado de la tool.")
            fallas.append("ignora el resultado de la tool")
    print()

    # ---- 4. Se abstiene cuando no hace falta? -----------------------------
    print("[4/4] ¿Se abstiene cuando la pregunta no necesita tool?")
    r, dt = chat(url, modelo, [{"role": "user", "content": "Hola, ¿cómo estás?"}])
    msg = r.get("message", {})
    llamadas = msg.get("tool_calls") or []
    print(f"      tool_calls  : {len(llamadas)}")
    print(f"      latencia    : {dt:.1f}s")
    if llamadas:
        print("      FALLA — llamó tool para un saludo.")
        print("      Esto es el bucle infinito del bloque 5 pasando sin que nadie lo provoque.")
        fallas.append("llama tools sin necesidad")
    else:
        print("      OK")
    print()

    # ---- Veredicto ---------------------------------------------------------
    print("=" * 68)
    if fallas:
        print(f"RESULTADO: {len(fallas)} falla(s) — {', '.join(fallas)}")
        print(f"\n'{modelo}' no sirve para este taller tal como está.")
        print("Probar el plan B antes de escribir más material:")
        print("    python scripts/smoke_test_tools.py --modelo qwen3:8b")
        print("    python scripts/smoke_test_tools.py --modelo llama3.1:8b")
        return 1
    print(f"RESULTADO: las 4 pruebas pasan. '{modelo}' sirve para el taller.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
