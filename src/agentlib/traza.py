"""
Manda al backend lo que el agente va haciendo, para que la pagina lo muestre.

Es infraestructura, no pedagogia: el asistente no gana nada escribiendo un POST.
Lo que si gana es VER la traza. Un agente sin traza es una caja negra, y depurar
una caja negra no determinista es imposible — esa es la leccion del bloque 5.
"""

import os

import requests


def _url():
    base = os.getenv("BACKEND_URL", "http://localhost:8000")
    return base.rstrip("/") + "/api/trazas"


def registrar(agente, evento, detalle=None):
    """
    Registra un paso del agente.

        agente   quien lo hizo: "recepcion", "inventario", "pedidos"
        evento   que paso: "pensando", "pide_herramienta", "ejecuta",
                 "resultado", "delega", "responde", "bloqueado"
        detalle  dict con lo que sea relevante

    Falla en silencio a proposito. Si el backend esta caido, el agente debe
    seguir funcionando: perder la traza es molesto, que se caiga el ejercicio
    de alguien a mitad del taller es peor.
    """
    try:
        requests.post(
            _url(),
            json={"agente": agente, "evento": evento, "detalle": detalle or {}},
            timeout=2,
        )
    except Exception:
        pass
