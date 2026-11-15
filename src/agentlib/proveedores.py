"""
Un `chat()` que habla con cualquier proveedor, elegido desde el .env.

La convención viene del proyecto de traducción del Corpus: **un string nombra
proveedor y modelo**.

    ollama:qwen3.5:9b
    ollama:mistral:latest
    azure:dataset-frontierscience-gpt41mini
    foundry:dataset-frontierscience-mistral-large
    mistral:mistral-large-latest

Es una buena convención y vale explicarla en el taller: cambiar de modelo —y de
proveedor— es cambiar una línea del .env, no tocar código. Esa separación entre
"qué modelo" y "cómo se llama al modelo" es la misma idea que hace que una
tool sea intercambiable.

Tres de los cuatro proveedores hablan el formato de OpenAI, así que comparten
una sola función. Ollama tiene su propio formato y vive en `ollama.py`, que es
además el archivo que el taller usa para enseñar: ahí la llamada se ve entera,
sin capas.

**Las claves se leen del entorno y nunca salen de aquí.** El navegador habla con
el backend; el backend habla con el proveedor. Si la página llamara a Azure
directo, la clave estaría en el código fuente que cualquiera puede leer.
"""

import os

import requests

from . import ollama as _ollama

TIMEOUT = 180


def _cfg():
    """Lee el .env de la raíz del repo. El entorno pisa al archivo."""
    valores = {}
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for ruta in (os.path.join(raiz, ".env"), "/app/.env"):
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if linea and not linea.startswith("#") and "=" in linea:
                        k, v = linea.split("=", 1)
                        valores[k.strip()] = v.strip().strip('"').strip("'")
            break
    valores.update({k: v for k, v in os.environ.items() if k in _CONOCIDAS or k.startswith(
        ("OLLAMA_", "AZURE_", "FOUNDRY_", "MISTRAL_"))})
    return valores


_CONOCIDAS = {"CHAT_MODEL", "TEMPERATURE", "NUM_CTX", "NUM_PREDICT"}


def modelo_por_omision():
    cfg = _cfg()
    if cfg.get("CHAT_MODEL"):
        return cfg["CHAT_MODEL"]
    # Compatibilidad con el .env viejo, que solo tenia OLLAMA_MODEL.
    return f"ollama:{cfg.get('OLLAMA_MODEL', 'qwen3.5:9b')}"


def modelos_disponibles():
    """
    Qué proveedores están configurados. Lo usa la página para poblar el
    selector, y a propósito **no devuelve ninguna clave**: solo si hay o no.
    """
    cfg = _cfg()
    salida = []

    base = _ollama.base_url(cfg)
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        for m in r.json().get("models", []):
            salida.append({"id": f"ollama:{m['name']}", "etiqueta": f"{m['name']} (local)",
                           "proveedor": "ollama", "listo": True})
    except Exception:
        salida.append({"id": "ollama:qwen3.5:9b", "etiqueta": "qwen3.5:9b (local, sin responder)",
                       "proveedor": "ollama", "listo": False})

    for clave_modelo in ("AZURE_DEPLOYMENT", "FOUNDRY_MISTRAL_DEPLOYMENT", "MISTRAL_MODEL"):
        nombre = cfg.get(clave_modelo)
        if not nombre:
            continue
        prov = {"AZURE_DEPLOYMENT": "azure",
                "FOUNDRY_MISTRAL_DEPLOYMENT": "foundry",
                "MISTRAL_MODEL": "mistral"}[clave_modelo]
        listo = bool(cfg.get({"azure": "AZURE_API_KEY",
                              "foundry": "FOUNDRY_MISTRAL_KEY",
                              "mistral": "MISTRAL_API_KEY"}[prov]))
        salida.append({"id": f"{prov}:{nombre}", "etiqueta": f"{nombre} ({prov})",
                       "proveedor": prov, "listo": listo})
    return salida


def url_ollama():
    """
    La dirección de Ollama, leída del .env y corregida si corremos en Docker.

    Existe para que nadie más tenga que combinar `_cfg()` con `base_url()`: el
    backend necesita esta URL para los endpoints de diagnóstico, y una segunda
    copia de esas dos líneas es una segunda copia que se desincroniza.
    """
    return _ollama.base_url(_cfg())


# ---------------------------------------------------------------------------
# El formato de OpenAI, que comparten azure, foundry y mistral
# ---------------------------------------------------------------------------
def _openai_compatible(url, cabeceras, modelo, mensajes, herramientas, temperatura, max_tokens):
    cuerpo = {"messages": mensajes, "temperature": temperatura}
    if modelo:
        cuerpo["model"] = modelo
    if max_tokens:
        cuerpo["max_tokens"] = max_tokens
    if herramientas:
        cuerpo["tools"] = herramientas
        cuerpo["tool_choice"] = "auto"

    r = requests.post(url, json=cuerpo, headers=cabeceras, timeout=TIMEOUT)
    if r.status_code >= 400:
        # El cuerpo del error dice mucho mas que el codigo, y es lo que hace
        # falta para distinguir "clave mala" de "deployment que no existe".
        raise RuntimeError(f"HTTP {r.status_code} de {url}\n{r.text[:500]}")

    msg = r.json()["choices"][0]["message"]
    # Devolvemos la forma de Ollama, que es la que usa el bucle del taller.
    # `tool_calls` de OpenAI trae function.name y function.arguments igual que
    # Ollama, solo que arguments es un string JSON: normalizar_argumentos lo
    # resuelve.
    return {"role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls") or []}


def _azure(cfg, deployment, mensajes, herramientas, temperatura, max_tokens):
    endpoint = (cfg.get("AZURE_ENDPOINT") or "").rstrip("/")
    clave = cfg.get("AZURE_API_KEY")
    version = cfg.get("AZURE_API_VERSION", "2025-01-01-preview")
    if not endpoint or not clave:
        raise RuntimeError("Faltan AZURE_ENDPOINT o AZURE_API_KEY en el .env.")
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={version}"
    # Azure OpenAI usa la cabecera `api-key`, no `Authorization: Bearer`.
    return _openai_compatible(url, {"api-key": clave}, None,
                              mensajes, herramientas, temperatura, max_tokens)


def _foundry(cfg, deployment, mensajes, herramientas, temperatura, max_tokens):
    endpoint = (cfg.get("FOUNDRY_MISTRAL_ENDPOINT") or "").rstrip("/")
    clave = cfg.get("FOUNDRY_MISTRAL_KEY")
    if not endpoint or not clave:
        raise RuntimeError("Faltan FOUNDRY_MISTRAL_ENDPOINT o FOUNDRY_MISTRAL_KEY en el .env.")
    # Los endpoints serverless de Foundry ya traen /v1 o no, segun como se
    # copien de la consola. Lo normalizamos para que las dos formas funcionen.
    url = endpoint if endpoint.endswith("/chat/completions") else f"{endpoint}/v1/chat/completions"
    return _openai_compatible(url, {"Authorization": f"Bearer {clave}"}, deployment,
                              mensajes, herramientas, temperatura, max_tokens)


def _mistral(cfg, modelo, mensajes, herramientas, temperatura, max_tokens):
    clave = cfg.get("MISTRAL_API_KEY")
    if not clave:
        raise RuntimeError("Falta MISTRAL_API_KEY en el .env.")
    base = (cfg.get("MISTRAL_BASE_URL") or "https://api.mistral.ai").rstrip("/")
    return _openai_compatible(f"{base}/v1/chat/completions",
                              {"Authorization": f"Bearer {clave}"}, modelo,
                              mensajes, herramientas, temperatura, max_tokens)


# ---------------------------------------------------------------------------
# El despacho
# ---------------------------------------------------------------------------
def chat(mensajes, herramientas=None, modelo=None, temperatura=None, pensar=False,
         top_k=None, top_p=None):
    """
    Una llamada de chat al proveedor que diga el modelo.

        modelo   "proveedor:nombre". Si es None, usa CHAT_MODEL del .env.
        resto    igual que agentlib.ollama.chat

    Devuelve siempre la forma de Ollama: {"content": ..., "tool_calls": [...]},
    que es la que usa el bucle agéntico del taller. Un proveedor distinto no
    cambia el bucle — y eso es exactamente lo que el taller quiere mostrar.
    """
    cfg = _cfg()
    modelo = modelo or modelo_por_omision()
    if temperatura is None:
        temperatura = float(cfg.get("TEMPERATURE", "0") or 0)
    max_tokens = int(cfg.get("NUM_PREDICT", "0") or 0) or None

    if ":" not in modelo:
        raise RuntimeError(
            f"El modelo '{modelo}' no dice proveedor. Usá 'proveedor:nombre', "
            f"por ejemplo 'ollama:qwen3.5:9b' o 'azure:mi-deployment'.")

    proveedor, nombre = modelo.split(":", 1)
    proveedor = proveedor.lower()

    if proveedor == "ollama":
        # Esta rama va al archivo que el taller usa para ensenar. Una sola
        # implementacion de la llamada a Ollama, no dos que se desincronizan.
        return _ollama.chat(mensajes, herramientas=herramientas,
                            temperatura=temperatura, pensar=pensar, modelo=nombre,
                            top_k=top_k, top_p=top_p)
    if proveedor == "azure":
        return _azure(cfg, nombre, mensajes, herramientas, temperatura, max_tokens)
    if proveedor == "foundry":
        return _foundry(cfg, nombre, mensajes, herramientas, temperatura, max_tokens)
    if proveedor == "mistral":
        return _mistral(cfg, nombre, mensajes, herramientas, temperatura, max_tokens)

    raise RuntimeError(
        f"Proveedor desconocido: '{proveedor}'. "
        f"Hay ollama, azure, foundry y mistral.")
