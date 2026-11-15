"""
Qué está haciendo Ollama, visto desde el backend.

**Por qué existe este archivo.** `/api/ps` y `/api/show` son endpoints de
OLLAMA, que escucha en el puerto 11434. No son de este backend, que escucha en
el 8000 — así que buscarlos en su Swagger y no encontrarlos es una confusión
razonable: son dos servidores distintos.

Y vale re-exponerlos aquí, de solo lectura, porque ahí vive la cifra más
restrictiva de las cuatro horas: **la ventana de contexto con la que se cargó
el modelo son 4096 tokens, no los 262144 que anuncia su ficha**. Es la
restricción que explica el tamaño de los historiales y de los esquemas de
tools, y hasta ahora solo se podía ver con `curl` contra otro puerto.

La razón es la misma por la que el chat pasa por aquí: la página es estática, y
hablar con Ollama desde el navegador obliga a que la página sepa su IP y a
pelear con CORS. Con esto, **un solo lugar conoce esa dirección**, y es el
mismo que ya la conocía.

    navegador → nginx :4200 → backend :8000 → ollama :11434

**Nada de lo que hay aquí escribe.** No se exponen `pull` (son 6.6 GB), ni
`delete`, ni `create`, ni `copy`. Un Swagger abierto en un salón es un botón al
alcance de veinte personas, y la lista de endpoints de un servidor no tiene por
qué ser la lista de los que conviene publicar.
"""

import sys
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentlib import proveedores  # noqa: E402

# La etiqueta tiene que ser IGUAL a la de `ETIQUETAS` en main.py, byte por
# byte: si no coincide, Swagger crea dos grupos con el mismo nombre y uno de
# los dos sale sin descripcion.
router = APIRouter(prefix="/api/ollama", tags=["ollama (diagnostico)"])

# Corto a proposito. Un diagnostico que tarda tres minutos en decirte que algo
# no responde no es un diagnostico: el chat usa 180 s porque un 9B compartido
# por el salon de verdad tarda, pero esto solo lee estado.
TIMEOUT = 10


def _url():
    return proveedores.url_ollama()


def _pedir(metodo, ruta, **kwargs):
    """
    Una llamada a Ollama, con el error traducido a algo accionable.

    Si Ollama no responde devolvemos 502 y no 500: el que está caído es el
    servicio de arriba, no este backend. Y el detalle dice qué correr, porque
    el 90% de las veces la causa es una de dos y las dos tienen un comando.
    """
    url = _url()
    try:
        r = requests.request(metodo, f"{url}{ruta}", timeout=TIMEOUT, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        raise HTTPException(502, {
            "error": f"Ollama no responde en {url}",
            "si_eres_el_instructor": "levántalo con scripts/<tu-sistema>/aula-up",
            "si_eres_asistente": "revisa OLLAMA_DESTINO en el .env de la raíz: "
                                 "dice a cuál de las direcciones declaradas se habla",
        })
    except requests.exceptions.Timeout:
        raise HTTPException(504, f"Ollama en {url} no contestó en {TIMEOUT} s")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(502, {"error": f"Ollama devolvió {e.response.status_code}",
                                  "detalle": e.response.text[:400]})


class VentanaDeContexto(BaseModel):
    """Las dos cifras que no son la misma, que es el punto de todo esto."""
    real: int | None = None            # con la que se cargo la instancia
    anunciada: int | None = None       # la que declara el archivo del modelo
    veces_mas_chica: int | None = None
    nota: str


class EstadoOllama(BaseModel):
    url: str
    version: str | None = None
    modelo_cargado: str | None = None
    ventana: VentanaDeContexto
    memoria_gb: dict | None = None
    instalados: list[str] = []


@router.get("/estado", response_model=EstadoOllama)
def estado():
    """
    El resumen que contesta la pregunta del bloque 1: **cuánto contexto hay**.

    Junta en una respuesta lo que de otro modo son tres llamadas a tres
    endpoints distintos, y pone las dos cifras de la ventana una al lado de la
    otra para que la diferencia no haya que buscarla.

    `memoria_gb` sale de la misma fuente y dice algo que importa en el taller:
    el modelo **no entra entero en la GPU**, y el pedazo que queda en CPU es la
    razón de que subir la ventana no sea gratis.
    """
    url = _url()
    version = _pedir("GET", "/api/version").get("version")
    cargados = _pedir("GET", "/api/ps").get("models", [])
    instalados = [m["name"] for m in _pedir("GET", "/api/tags").get("models", [])]

    if cargados:
        vivo = cargados[0]
        modelo, real = vivo["model"], vivo.get("context_length")
        total, en_vram = vivo.get("size", 0), vivo.get("size_vram", 0)
        memoria = {
            "modelo_total": round(total / 1e9, 2),
            "en_gpu": round(en_vram / 1e9, 2),
            "en_cpu": round((total - en_vram) / 1e9, 2),
        }
        nota = ("`real` es la ventana con la que Ollama cargó esta instancia, y es "
                "la que manda. `anunciada` es lo que declara el archivo del modelo.")
    else:
        # Sin modelo cargado no hay ventana que reportar: Ollama la asigna al
        # cargar. Decimos cual se cargaria, que es lo util, y no mentimos con
        # un numero.
        modelo = proveedores.modelo_por_omision()
        modelo = modelo.split(":", 1)[1] if modelo.startswith("ollama:") else None
        real, memoria = None, None
        nota = ("ningún modelo está cargado todavía: Ollama asigna la ventana al "
                "cargarlo, con la primera petición. Manda un /api/chat y vuelve.")

    anunciada = None
    if modelo:
        ficha = _pedir("POST", "/api/show", json={"model": modelo})
        anunciada = next((v for k, v in ficha.get("model_info", {}).items()
                          if k.endswith("context_length")), None)

    return EstadoOllama(
        url=url, version=version, modelo_cargado=modelo, instalados=instalados,
        memoria_gb=memoria,
        ventana=VentanaDeContexto(
            real=real, anunciada=anunciada,
            veces_mas_chica=(anunciada // real) if (real and anunciada) else None,
            nota=nota),
    )


@router.get("/ps")
def ps():
    """
    Qué modelos tiene Ollama **cargados en memoria** ahora, tal cual.

    Es el espejo de `GET :11434/api/ps`. El campo que importa es
    `context_length`: la ventana de verdad. Lista vacía significa que nadie ha
    usado el modelo todavía — Ollama lo descarga de memoria tras unos minutos
    de inactividad, así que verla vacía no es un error.
    """
    return _pedir("GET", "/api/ps")


@router.get("/tags")
def tags():
    """
    Qué modelos están **descargados** en el disco de la máquina de Ollama.

    Es el espejo de `GET :11434/api/tags`, y es la misma llamada que alimenta
    el selector de la página: `/api/modelos` la usa y le agrega los proveedores
    de pago que estén configurados.
    """
    return _pedir("GET", "/api/tags")


@router.get("/show")
def show(modelo: str, crudo: bool = False):
    """
    La ficha de un modelo: su arquitectura, sus capacidades y su contexto.

    Es el espejo de `POST :11434/api/show`, pero aquí es un GET con el modelo
    como parámetro — en un Swagger eso se prueba con un clic, y leer no debería
    pedir un cuerpo.

    **Por omisión se recorta**, porque la respuesta cruda son ~90 KB: la
    licencia, el modelfile entero y la lista de 300 tensores. Lo que queda es
    lo que se mira en el taller, `model_info` incluido, que es donde está
    `<arquitectura>.context_length`. Con `crudo=true` vuelve completa.
    """
    ficha = _pedir("POST", "/api/show", json={"model": modelo})
    if crudo:
        return ficha
    return {k: v for k, v in ficha.items()
            if k not in ("license", "modelfile", "tensors")}


@router.get("/version")
def version():
    """La versión de Ollama. Espejo de `GET :11434/api/version`."""
    return _pedir("GET", "/api/version")
