#!/usr/bin/env python3
"""
Lo primero que corre cada asistente, en el minuto 0 del taller.

En Python y no en PowerShell a propósito: el salón va a tener Windows, macOS y
Linux, y Python es el único requisito que ya les pedimos. Imprime un diagnóstico
con la acción concreta para cada falla, porque un "no me funciona" sin más
detalle cuesta cinco minutos de taller por persona.

    python scripts/verificar_ambiente.py
"""

import os
import sys

# La consola de Windows usa cp1252 por omision y destroza los acentos. En el
# proyector del aula eso se ve. Esto lo arregla sin pedirle nada al asistente.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def script(nombre):
    """
    La ruta del script segun el sistema de quien esta corriendo esto.

    Los scripts estan separados en scripts/win, scripts/linux y scripts/mac, y
    decirle a alguien en una Mac que corra un .ps1 es peor que no decirle nada.
    """
    if sys.platform == "win32":
        return f"scripts\\win\\{nombre}.ps1"
    carpeta = "mac" if sys.platform == "darwin" else "linux"
    return f"./scripts/{carpeta}/{nombre}.sh"


OK = "  OK   "
MAL = " FALLA "
AVISO = " AVISO "

fallas = 0


def resultado(estado, titulo, detalle="", accion=""):
    global fallas
    print(f"[{estado}] {titulo}")
    if detalle:
        print(f"         {detalle}")
    if accion:
        print(f"         -> {accion}")
    if estado == MAL:
        fallas += 1


def leer_env():
    """Lee el .env de la raíz sin depender de python-dotenv."""
    valores = {}
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta = os.path.join(raiz, ".env")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    valores[k.strip()] = v.strip()
    # Las variables del entorno pisan al archivo.
    for k in ("OLLAMA_DESTINO", "OLLAMA_BASE_URL", "CHAT_MODEL",
              "OLLAMA_MODEL", "BACKEND_URL"):
        if os.getenv(k):
            valores[k] = os.getenv(k)
    return valores, ruta


def modelo_de_ollama(env):
    """
    Que modelo se le va a pedir, con la misma regla que agentlib/ollama.py.

    CHAT_MODEL manda cuando nombra un modelo de ollama; si apunta a otro
    proveedor, ese no lo sirve Ollama y vale OLLAMA_MODEL. Duplicado a
    proposito: este script corre antes de que exista src/.
    """
    chat_model = (env.get("CHAT_MODEL") or "").strip()
    if chat_model.startswith("ollama:"):
        return chat_model.split(":", 1)[1]
    return env.get("OLLAMA_MODEL", "qwen3.5:9b")


def url_de_ollama(env):
    """
    La direccion activa, con la misma regla que agentlib/ollama.py.

    Esta duplicada a proposito, y es la unica duplicacion del repositorio que
    vale la pena: este script tiene que correr ANTES de que `requests` o
    `agentlib` esten instalados, asi que no puede importar nada de src/.
    """
    suelta = os.getenv("OLLAMA_BASE_URL")
    destino = (env.get("OLLAMA_DESTINO") or "").strip().lower()

    if destino:
        url = env.get(f"OLLAMA_URL_{destino.upper()}")
        if url:
            url = url.rstrip("/")
            motivo = f"OLLAMA_DESTINO={destino}"
            if suelta and suelta.rstrip("/") != url:
                motivo += f"; se ignora OLLAMA_BASE_URL={suelta.rstrip('/')} del entorno"
            return url, motivo
        # Vacia no es lo mismo que ausente: el .env.example las trae vacias.
        clave = f"OLLAMA_URL_{destino.upper()}"
        con_valor = sorted(k[len("OLLAMA_URL_"):].lower()
                           for k, v in env.items()
                           if k.startswith("OLLAMA_URL_") and (v or "").strip())
        falta = "esta vacia" if clave in env else "no esta"
        return None, (f"OLLAMA_DESTINO dice '{destino}' y {clave} {falta} en el "
                      f".env. Ponle  http://<ip>:11434 . Con direccion ahora: "
                      f"{', '.join(con_valor) or 'ninguno'}")

    if suelta:
        return suelta.rstrip("/"), "la variable de entorno OLLAMA_BASE_URL"

    return env.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"), "OLLAMA_BASE_URL"


def main():
    print("=" * 68)
    print("  Verificación de ambiente — Más allá del prompt")
    print("=" * 68 + "\n")

    # ---- Python ------------------------------------------------------------
    v = sys.version_info
    if v >= (3, 10):
        resultado(OK, f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        resultado(MAL, f"Python {v.major}.{v.minor}", "Hace falta 3.10 o superior.",
                  "Instalar desde python.org")

    # ---- Ambiente virtual --------------------------------------------------
    # El tropiezo mas comun del minuto 0: `pip install` sin activar el ambiente
    # instala en el Python del sistema, y despues el notebook falla en
    # `import requests` sin decir por que. Aviso y no falla, porque instalar
    # global funciona — simplemente es peor.
    en_venv = sys.prefix != sys.base_prefix
    if en_venv:
        resultado(OK, "Ambiente virtual activado", os.path.basename(sys.prefix))
    else:
        resultado(AVISO, "No estás en un ambiente virtual",
                  "Funciona igual, pero es de donde salen los problemas raros después.",
                  "python -m venv .venv  y activarlo (ver README, paso 2)")

    # ---- Largo de la ruta (solo Windows) -----------------------------------
    # Windows corta las rutas en 260 caracteres, y jupyterlab arrastra debugpy
    # y jedi, que traen archivos con rutas de hasta 148 caracteres contando
    # desde la raiz del repo. En una carpeta profunda el `pip install` falla a
    # mitad con un OSError que no menciona la longitud de la ruta en ninguna
    # parte, asi que nadie lo diagnostica solo.
    #
    # Las dos cifras estan medidas en esta maquina, no estimadas: el archivo
    # mas largo es
    #   .venv\\Lib\\site-packages\\debugpy\\_vendored\\pydevd\\_pydevd_bundle\\
    #   _debug_adapter\\__pycache__\\__main__pydevd_gen_debug_adapter_protocol
    #   .cpython-311.pyc
    # con 148 caracteres. De ahi el presupuesto de 112 para la ruta del repo.
    SUFIJO_MAS_LARGO = 148
    PRESUPUESTO = 260 - SUFIJO_MAS_LARGO  # 112
    raiz_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform == "win32":
        largo = len(raiz_repo)
        if largo > PRESUPUESTO:
            resultado(MAL, f"La ruta del repo es demasiado profunda ({largo} chars)",
                      f"{raiz_repo}\n         El máximo aquí es {PRESUPUESTO}.",
                      "Muévelo a C:\\agenticai. Si no, pip install falla a medias "
                      "con un error que no dice que la ruta es el problema.")
        elif largo > PRESUPUESTO - 20:
            resultado(AVISO, f"La ruta del repo está cerca del límite ({largo} de {PRESUPUESTO})",
                      raiz_repo, "Si pip install falla, muévelo a C:\\agenticai")
        else:
            resultado(OK, f"Largo de la ruta ({largo} de {PRESUPUESTO} permitidos)")

    # ---- requests ----------------------------------------------------------
    try:
        import requests  # noqa: F401
        resultado(OK, "requests instalado")
    except ImportError:
        accion = "pip install -r requirements.txt"
        if not en_venv:
            accion += "   (activa primero el ambiente virtual)"
        resultado(MAL, "requests no está instalado", accion=accion)
        print("\nSin requests no puedo seguir verificando.")
        return 1

    import requests

    # ---- lo que solo necesita el notebook 07 (NAS) -------------------------
    # Aviso y no falla: los cinco pasos del taller corren sin esto. Pero si
    # falta y alguien abre el notebook 07, el error que recibe es un
    # ModuleNotFoundError pelado que no dice de donde sale ni que instalar.
    faltan_nas = []
    for modulo in ("numpy", "sklearn", "scipy"):
        try:
            __import__(modulo)
        except ImportError:
            faltan_nas.append("scikit-learn" if modulo == "sklearn" else modulo)
    if faltan_nas:
        resultado(AVISO, f"Falta {', '.join(faltan_nas)} (solo para el notebook 07)",
                  "Los pasos 1 al 5 del taller no lo necesitan.",
                  "pip install -r requirements.txt")
    else:
        resultado(OK, "numpy, scikit-learn y scipy instalados",
                  "el notebook 07 (NAS) puede correr")

    # ---- .env --------------------------------------------------------------
    env, ruta_env = leer_env()
    if os.path.exists(ruta_env):
        resultado(OK, ".env encontrado en la raíz")
    else:
        resultado(AVISO, ".env no existe; uso valores por omisión",
                  accion="copiar infra/taller/.env.example a .env en la raíz")

    url_ollama, origen = url_de_ollama(env)
    modelo = modelo_de_ollama(env)
    url_backend = env.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

    if url_ollama is None:
        resultado(MAL, "No se pudo resolver la direccion de Ollama", origen,
                  "Corrige OLLAMA_DESTINO en el .env de la raiz")
        return 1

    print(f"\n  Ollama  : {url_ollama}   (por {origen})")
    print(f"  Modelo  : {modelo}")
    print(f"  Backend : {url_backend}\n")

    # ---- Ollama ------------------------------------------------------------
    try:
        tags = requests.get(f"{url_ollama}/api/tags", timeout=10).json()
        modelos = [m["name"] for m in tags.get("models", [])]
        resultado(OK, "Ollama responde", f"{len(modelos)} modelo(s) disponible(s)")

        if modelo in modelos:
            resultado(OK, f"El modelo '{modelo}' está cargado")
        else:
            resultado(MAL, f"El modelo '{modelo}' no está en el servidor",
                      f"Hay: {', '.join(modelos) or '(ninguno)'}",
                      "Avísale al instructor; no intentes descargar otro: "
                      "la GPU del aula tiene lugar para un modelo, uno solo.")
    except Exception as e:
        es_local = "localhost" in url_ollama or "127.0.0.1" in url_ollama
        if es_local:
            accion = "El destino activo apunta a tu maquina. Si Ollama lo sirve otro, cambia OLLAMA_DESTINO en el .env."
        else:
            accion = "Avísale al instructor: puede ser la IP, el firewall, o la red del aula."
        resultado(MAL, "Ollama no responde", str(e)[:120], accion)

    # ---- Backend -----------------------------------------------------------
    try:
        r = requests.get(f"{url_backend}/api/health", timeout=5)
        if r.status_code == 200:
            resultado(OK, "El backend responde")
        else:
            resultado(MAL, f"El backend contestó HTTP {r.status_code}",
                      accion="docker logs agenticai_backend --tail 30")
    except Exception as e:
        resultado(MAL, "El backend no responde", str(e)[:120],
                  f"{script('taller-up')}   (o: cd infra/taller && docker compose up -d)")

    # ---- Frontend ----------------------------------------------------------
    try:
        r = requests.get("http://localhost:4200", timeout=5)
        if r.status_code == 200:
            resultado(OK, "El frontend responde", "http://localhost:4200")
        else:
            resultado(AVISO, f"El frontend contestó HTTP {r.status_code}")
    except Exception:
        resultado(AVISO, "El frontend no responde",
                  "No bloquea los pasos 1 y 2; sí hace falta desde el paso 3.",
                  script("taller-up"))

    # ---- Veredicto ---------------------------------------------------------
    print("\n" + "=" * 68)
    if fallas:
        print(f"  {fallas} falla(s). Resuélvelas antes de empezar.")
        print("=" * 68)
        return 1
    print("  Todo listo. Abre el notebook 00 de tu escenario: 00_localhost, 00_aula o 00_tec")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
