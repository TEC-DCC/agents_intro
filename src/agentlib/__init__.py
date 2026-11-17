"""
Lo mínimo compartido entre los pasos: transporte HTTP y traza.

Regla del taller: aquí NO vive el bucle agéntico, ni el enrutamiento entre
agentes, ni los guardrails. Todo eso lo escribe el asistente. Si algo de eso
termina aquí, este paquete se convirtió en el framework que el taller promete
no usar.
"""

from .ollama import (base_url, cargar_env, chat,  # noqa: F401
                     llamadas_al_modelo, modelo_configurado,
                     normalizar_argumentos, origen_url, ruta_env, streaming,
                     ultima_medicion)
from .traza import registrar  # noqa: F401
