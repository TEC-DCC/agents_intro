# -*- coding: utf-8 -*-
"""
Saca de las SALIDAS GUARDADAS de los notebooks lo que no debe ser publico.

    python scripts/redactar_salidas.py            # redacta y dice que cambio
    python scripts/redactar_salidas.py --revisar   # solo revisa, no escribe

Correrlo antes de cada commit. Y hay que correrlo, no solo una vez: **volver a
ejecutar un notebook reintroduce los dos datos**, porque los imprime la celda
de imports.

Lo que redacta, y de donde saca que redactar:

  - **Las direcciones de Ollama que no son locales.** Las lee del `.env` de la
    raiz, de las claves OLLAMA_URL_*, y se salta localhost y 127.0.0.1. Asi el
    script no trae ninguna IP escrita y sigue sirviendo cuando cambien.

  - **La carpeta del usuario.** `cargar_env()` imprime la ruta del `.env`, y en
    Windows eso es C:\\Users\\<nombre>\\... El nombre de usuario no tiene por
    que viajar.

Solo toca `outputs`. La fuente de las celdas no se modifica nunca: si una IP
esta escrita en el codigo o en el markdown, este script la reporta y te deja
arreglarla a mano, porque ahi casi siempre lo correcto es reescribir la frase,
no sustituir la cadena.
"""
import argparse
import glob
import io
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LOCALES = ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")


def direcciones_a_redactar():
    """Las URL de Ollama del `.env` que no son locales, mas su reemplazo."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return {}
    pares = {}
    for linea in io.open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = (x.strip() for x in linea.split("=", 1))
        if not clave.startswith("OLLAMA_URL_") or not valor:
            continue
        ip = re.sub(r"^https?://", "", valor).split(":")[0].rstrip("/")
        if not ip or any(ip.startswith(l) for l in LOCALES):
            continue
        octetos = ip.split(".")
        if len(octetos) == 4 and all(o.isdigit() for o in octetos):
            # Se conservan los dos primeros octetos y se tapan los otros
            # dos: queda la forma de la direccion, no el destino.
            pares[ip] = f"{octetos[0]}.{octetos[1]}.x.x"
        else:
            pares[ip] = "<servidor>"
    return pares


def carpetas_a_redactar():
    """La carpeta del usuario, en las dos formas en que Jupyter la imprime."""
    casa = str(Path.home())
    pares = {}
    for forma in (casa, casa.replace("\\", "/"), casa.replace("\\", "\\\\")):
        if forma and forma not in pares:
            pares[forma] = "<HOME>"
    # Y la variante con la unidad en minuscula, que es como la imprime Jupyter.
    if len(casa) > 1 and casa[1] == ":":
        otra = casa[0].swapcase() + casa[1:]
        pares[otra] = "<HOME>"
        pares[otra.replace("\\", "/")] = "<HOME>"
    return pares


def redactar_texto(texto, pares):
    for viejo, nuevo in pares.items():
        texto = texto.replace(viejo, nuevo)
    return texto


def redactar_salida(salida, pares):
    """Devuelve True si cambio algo de esta salida."""
    cambio = False
    for campo in ("text", "evalue", "traceback"):
        v = salida.get(campo)
        if isinstance(v, str):
            nuevo = redactar_texto(v, pares)
            if nuevo != v:
                salida[campo] = nuevo
                cambio = True
        elif isinstance(v, list):
            nuevo = [redactar_texto(x, pares) if isinstance(x, str) else x for x in v]
            if nuevo != v:
                salida[campo] = nuevo
                cambio = True
    datos = salida.get("data")
    if isinstance(datos, dict):
        for k, v in list(datos.items()):
            if isinstance(v, str):
                nuevo = redactar_texto(v, pares)
                if nuevo != v:
                    datos[k] = nuevo
                    cambio = True
            elif isinstance(v, list):
                nuevo = [redactar_texto(x, pares) if isinstance(x, str) else x for x in v]
                if nuevo != v:
                    datos[k] = nuevo
                    cambio = True
    return cambio


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--revisar", action="store_true",
                   help="solo dice que encontro; no escribe nada")
    args = p.parse_args()

    pares = {**direcciones_a_redactar(), **carpetas_a_redactar()}
    if not pares:
        print("No hay nada que redactar: el .env no declara direcciones remotas.")
        return 0

    print("Se redacta:")
    for viejo, nuevo in pares.items():
        print(f"  {viejo}  ->  {nuevo}")
    print()

    tocados, en_fuente = 0, []
    for ruta in sorted(glob.glob(str(RAIZ / "notebooks" / "*.ipynb"))):
        nb = json.load(io.open(ruta, encoding="utf-8"))
        celdas = []
        for i, c in enumerate(nb["cells"]):
            # La fuente NO se toca: se reporta para arreglarla a mano.
            fuente = "".join(c["source"])
            for viejo in pares:
                if viejo in fuente and viejo != str(Path.home()):
                    en_fuente.append(f"{os.path.basename(ruta)} [{i}] {viejo}")
            # Lista, NO generador: `any(...)` con un generador corta al primer
            # True y deja las demas salidas de la celda sin redactar. Asi se
            # escapo la ruta del repr de un modulo, que es la SEGUNDA salida de
            # la celda de imports.
            cambios = [redactar_salida(o, pares) for o in c.get("outputs", [])]
            if any(cambios):
                celdas.append(i)
        if celdas:
            tocados += 1
            marca = "encontrado en" if args.revisar else "redactado en"
            print(f"  {marca} {os.path.basename(ruta)}: celdas {celdas}")
            if not args.revisar:
                json.dump(nb, io.open(ruta, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)

    if en_fuente:
        print("\nY esto esta en la FUENTE de una celda, que este script no toca:")
        for x in sorted(set(en_fuente)):
            print(f"  {x}")
        print("  Reescribe la frase a mano: sustituir la cadena suele dejarla rara.")

    if not tocados:
        print("  Las salidas ya estan limpias.")
    elif args.revisar:
        print("\nCorre el script sin --revisar para redactarlas.")
    return 1 if (args.revisar and (tocados or en_fuente)) else 0


if __name__ == "__main__":
    sys.exit(main())
