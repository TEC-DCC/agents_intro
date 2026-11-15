"""
El sistema que el agente va a manipular.

ESQUELETO. Los endpoints del dominio estan pendientes del caso de estudio
(ver planeacion/caso-de-estudio.md). Lo que ya esta resuelto es lo que NO
depende del caso: salud, trazas y reinicio.

Un recordatorio sobre el papel de este archivo en el taller: no es el tema.
Es un sistema cualquiera con una API HTTP, elegido para que el agente tenga
algo real que tocar. No hay autenticacion, no hay migraciones, el estado vive
en memoria. Cada minuto gastado explicando este backend es un minuto que no se
habla de agentes.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .chat import router as chat_router
from .diagnostico import router as diagnostico_router
from .inventario import router as inventario_router
from .inventario import reiniciar_desde_semilla

# La descripcion y las etiquetas no son adorno: este Swagger se abre en el
# taller, y la pregunta que genera es siempre la misma -"donde estan /api/ps y
# /api/show?"-. La respuesta es que son de OTRO servidor, y el mejor lugar para
# decirlo es aqui, no en un README que nadie tiene abierto en ese momento.
DESCRIPCION = """
El sistema que el agente manipula, mas el chat y el diagnostico.

**Son dos servidores, no uno.** Este backend escucha en el **:8000** y es lo
que ves aqui. El modelo vive en **Ollama, en el :11434**, con su propia API
(`/api/chat`, `/api/ps`, `/api/show`, `/api/tags`) que *no* aparece en este
Swagger porque no es de este servidor.

```
navegador -> nginx :4200 -> backend :8000 -> ollama :11434
                                 ^ las claves de API viven solo aqui
```

Lo que si hay aqui es un **espejo de solo lectura** de los endpoints de Ollama
que el taller usa, bajo `/api/ollama/*`. Existe para que la ventana de contexto
real -4096 tokens, no los 262144 que anuncia el modelo- se pueda leer sin
saber la IP de Ollama ni abrir otra terminal.
"""

ETIQUETAS = [
    {"name": "salud y trazas",
     "description": "Si el backend vive, y lo que los agentes fueron dejando "
                    "anotado. La traza la emite `agentlib.traza.registrar` y la "
                    "lee el panel derecho de la pagina."},
    {"name": "chat y modelos",
     "description": "El unico camino por el que pasan las claves de API. El "
                    "modelo se nombra `proveedor:modelo` -`ollama:qwen3.5:9b`, "
                    "`azure:mi-deployment`- y se elige en el `.env`."},
    {"name": "inventario",
     "description": "El dominio: lo que las tools del agente leen y cambian. "
                    "Sobre un CSV a proposito, para poder verlo cambiar. "
                    "**DELETE es el endpoint destructivo** que justifica la "
                    "confirmacion humana del paso 4."},
    {"name": "ollama (diagnostico)",
     "description": "Espejo de **solo lectura** de la API de Ollama, que corre "
                    "en el :11434. No se exponen `pull`, `delete` ni `create`: "
                    "un Swagger abierto en un salon es un boton al alcance de "
                    "veinte personas. Empieza por `/api/ollama/estado`."},
    {"name": "administracion",
     "description": "Volver todo al estado inicial. Se usa entre practica y "
                    "practica, y despues de cada demo de falla del bloque 5."},
]

app = FastAPI(title="Mesa de pedidos", version="0.1.0",
              description=DESCRIPCION, openapi_tags=ETIQUETAS)

# Abierto a cualquier origen: el frontend corre en :4200 y los notebooks en
# :8888, los dos contra :8000. En un taller, pelear con CORS es tiempo perdido.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# El chat y la lista de modelos. Viven aparte porque son lo unico que toca
# claves de API: ver src/backend/app/chat.py
app.include_router(chat_router, tags=["chat y modelos"])

# El inventario: el sistema que las tools del agente manipulan.
app.include_router(inventario_router, tags=["inventario"])

# Diagnostico de Ollama, de solo lectura. Es un espejo de endpoints que viven
# en OTRO servidor —ollama, en el :11434— y estan aqui porque ahi se lee la
# ventana de contexto real, que es la restriccion que define el taller.
# Ver src/backend/app/diagnostico.py
app.include_router(diagnostico_router)

# ---------------------------------------------------------------------------
# Estado. En memoria a proposito: se reinicia seguido durante el taller.
# ---------------------------------------------------------------------------
TRAZAS: list[dict] = []


# ---------------------------------------------------------------------------
# Salud y trazas — no dependen del caso de estudio
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["salud y trazas"])
def health():
    return {"estado": "ok", "trazas": len(TRAZAS)}


class Traza(BaseModel):
    agente: str
    evento: str
    detalle: dict = {}


@app.post("/api/trazas", tags=["salud y trazas"])
def crear_traza(t: Traza):
    """Lo llama agentlib.traza.registrar. Lo lee el panel derecho de la pagina."""
    entrada = t.model_dump()
    entrada["t"] = datetime.now(timezone.utc).isoformat()
    entrada["n"] = len(TRAZAS) + 1
    TRAZAS.append(entrada)
    return entrada


@app.get("/api/trazas", tags=["salud y trazas"])
def listar_trazas(desde: int = 0):
    """`desde` es el numero de la ultima traza que el frontend ya tiene."""
    return {"trazas": [x for x in TRAZAS if x["n"] > desde], "total": len(TRAZAS)}


@app.delete("/api/trazas", tags=["salud y trazas"])
def limpiar_trazas():
    TRAZAS.clear()
    return {"estado": "ok"}


@app.post("/api/admin/reiniciar", tags=["administracion"])
def reiniciar():
    """
    Vuelve todo al estado inicial. Lo llama scripts/<tu-sistema>/reiniciar-datos.

    Se usa mas de lo que parece: entre practica y practica, y despues de cada
    demo de falla del bloque 5 — sobre todo la que cancela lo que no debia.
    """
    TRAZAS.clear()
    productos = reiniciar_desde_semilla()
    return {"estado": "reiniciado", "productos": productos}


# ---------------------------------------------------------------------------
# El dominio — PENDIENTE del caso de estudio
# ---------------------------------------------------------------------------
# La forma que tiene que tener, independientemente del dominio que elijamos:
#
#   - de 2 a 4 endpoints de LECTURA     (lo que el agente averigua)
#   - de 1 a 2 endpoints de ESCRITURA   (lo que el agente cambia)
#   - exactamente 1 endpoint DESTRUCTIVO (lo que justifica la confirmacion
#     humana del paso 4)
#
# Esa tercera linea es la que no se puede negociar: sin una accion que de
# verdad duela deshacer, el guardrail del paso 4 se siente como un requisito
# inventado y nadie se lo cree.
