"""
El endpoint de chat. Es el único lugar por donde pasan las claves de API.

Por qué el navegador no llama al proveedor directo, aunque sería más corto:
la página es estática y cualquiera puede leer su código. Una clave de Azure
ahí es una clave publicada. Así que el navegador habla con el backend, y el
backend —que corre en un servidor— habla con el proveedor.

Para Ollama local da igual, no hay clave. Para Azure, Foundry o Mistral no es
negociable, y vale decirlo en el taller: es el mismo razonamiento del paso 4
—qué puede tocar quién— aplicado a secretos en vez de a tools.
"""

import sys
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

# agentlib vive un nivel arriba de backend/ dentro de la imagen. Ver el
# Dockerfile: el contexto de build es src/, para que exista UNA sola
# implementacion de la capa de proveedores y no dos que se desincronizan.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentlib import proveedores  # noqa: E402

router = APIRouter()

SYSTEM_POR_OMISION = (
    "Eres un asistente útil y conciso. Respondes en español."
)


class Mensaje(BaseModel):
    role: str
    content: str


class PeticionChat(BaseModel):
    mensajes: list[Mensaje]
    modelo: str | None = None          # "proveedor:nombre"; None usa el del .env
    system: str | None = None
    temperatura: float | None = None
    pensar: bool = False               # el modo de razonamiento, para mostrarlo
    # Solo tienen efecto con ollama. Recortan la lista de candidatos antes de
    # que la temperatura elija entre lo que quedo; qwen3.5:9b trae top_k=20 y
    # top_p=0.95 en su Modelfile. Su efecto es menor de lo que parece: lo que
    # de verdad hace visible el no determinismo es pedir una respuesta larga.
    # Medido en planeacion/hallazgos.md
    top_k: int | None = None
    top_p: float | None = None


@router.get("/api/modelos")
def listar_modelos():
    """
    Qué modelos hay configurados, para poblar el selector de la página.

    No devuelve ninguna clave: solo el id, una etiqueta y si está listo. El
    campo `listo` en false significa "configurado pero sin clave" o "no
    responde", que es información útil y no un secreto.
    """
    return {"modelos": proveedores.modelos_disponibles(),
            "por_omision": proveedores.modelo_por_omision()}


@router.post("/api/chat")
def chat(p: PeticionChat):
    mensajes = [{"role": "system", "content": p.system or SYSTEM_POR_OMISION}]
    mensajes += [m.model_dump() for m in p.mensajes]

    modelo = p.modelo or proveedores.modelo_por_omision()
    t0 = time.time()
    try:
        respuesta = proveedores.chat(
            mensajes, modelo=modelo, temperatura=p.temperatura, pensar=p.pensar,
            top_k=p.top_k, top_p=p.top_p)
    except Exception as e:
        # El error vuelve como dato, no como 500: la pagina lo muestra en el
        # chat y el asistente ve que paso. Es la misma idea que en el paso 3,
        # donde un error de tool vuelve al modelo en vez de reventar.
        return {"error": str(e), "modelo": modelo,
                "segundos": round(time.time() - t0, 1)}

    return {
        "contenido": respuesta.get("content", ""),
        "pensamiento": respuesta.get("thinking") or "",
        "modelo": modelo,
        "segundos": round(time.time() - t0, 1),
    }
