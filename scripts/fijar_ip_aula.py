#!/usr/bin/env python3
"""
Escribe en el `.env` la IP de LAN de esta máquina, como `OLLAMA_URL_AULA`.

**Solo tiene sentido en la máquina que sirve el modelo**, porque escribe *su*
dirección. Un asistente que lo corra se apuntaría a sí mismo. Por eso lo llaman
los `aula-up`, que ya son solo del instructor, y no los `taller-up`.

    python scripts/fijar_ip_aula.py            # detecta y escribe en el .env
    python scripts/fijar_ip_aula.py --mostrar  # solo dice qué encontró

Existe porque esa IP la asigna el DHCP y cambia sola. En la máquina donde se
preparó el material cambió dos veces en una sola sesión de trabajo, y una IP
vieja en el `.env` se diagnostica como "no me funciona Ollama".

Corre en Windows, Linux y macOS: le pregunta al sistema con su propia
herramienta en vez de adivinar.

Lo que descarta, y por qué:

  - **127.0.0.1 y las link-local (169.254).** No las alcanza nadie.
  - **Las interfaces virtuales** de Docker, WSL, Hyper-V, VirtualBox y los
    puentes. Dictar la de Docker es el error que cuesta diez minutos de taller,
    porque *parece* una IP de red local.
  - **Las direcciones con máscara /32**, que es como se ven los clientes de
    VPN. Es el filtro que los `aula-ip` no tenían: con la VPN conectada, una
    /32 aparecía primero en la lista y es la peor candidata posible, porque
    cambia en cada reconexión.
"""

import argparse
import ipaddress
import os
import re
import subprocess
import sys

PUERTO = 11434
CLAVE = "OLLAMA_URL_AULA"

# Nombres de interfaz que nunca sirven para el aula.
VIRTUALES = re.compile(
    r"loopback|docker|wsl|hyper-?v|vethernet|veth|virbr|vmnet|vbox|"
    r"bridge|tun|tap|wg|zt|cni|flannel|kube|vpn|anyconnect|tailscale",
    re.I)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _correr(comando):
    return subprocess.run(comando, capture_output=True, text=True,
                          timeout=30).stdout


def _windows():
    salida = _correr([
        "powershell", "-NoProfile", "-Command",
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Select-Object IPAddress,InterfaceAlias,PrefixLength | ConvertTo-Csv -NoTypeInformation"])
    encontradas = []
    for linea in salida.splitlines()[1:]:
        partes = [p.strip('"') for p in linea.strip().split('","')]
        if len(partes) == 3:
            partes[0] = partes[0].lstrip('"')
            partes[2] = partes[2].rstrip('"')
            encontradas.append((partes[0], partes[1], int(partes[2])))
    return encontradas


def _linux():
    encontradas = []
    for linea in _correr(["ip", "-o", "-4", "addr", "show", "scope", "global"]).splitlines():
        campos = linea.split()
        if len(campos) >= 4 and "/" in campos[3]:
            direccion, prefijo = campos[3].split("/")
            encontradas.append((direccion, campos[1], int(prefijo)))
    return encontradas


def _mac():
    encontradas = []
    actual = None
    for linea in _correr(["ifconfig"]).splitlines():
        if linea and not linea[0].isspace():
            actual = linea.split(":")[0]
        elif "inet " in linea and actual:
            campos = linea.split()
            direccion = campos[campos.index("inet") + 1]
            # En macOS la mascara viene en hexadecimal: 0xffffff00 -> /24
            prefijo = 24
            if "netmask" in campos:
                try:
                    cruda = campos[campos.index("netmask") + 1]
                    prefijo = bin(int(cruda, 16)).count("1")
                except ValueError:
                    pass
            encontradas.append((direccion, actual, prefijo))
    return encontradas


def candidatas():
    """Las direcciones que el salón podría alcanzar, la mejor primero."""
    if sys.platform == "win32":
        crudas = _windows()
    elif sys.platform == "darwin":
        crudas = _mac()
    else:
        crudas = _linux()

    buenas = []
    for direccion, interfaz, prefijo in crudas:
        try:
            ip = ipaddress.IPv4Address(direccion)
        except ipaddress.AddressValueError:
            continue
        if ip.is_loopback or ip.is_link_local or not ip.is_private:
            continue
        if prefijo == 32:                      # cliente de VPN
            continue
        if VIRTUALES.search(interfaz):
            continue
        buenas.append((direccion, interfaz, prefijo))

    # Wi-Fi y Ethernet primero: en un aula, el cable y el inalambrico son las
    # dos que el salon alcanza de verdad.
    def rango(entrada):
        return 0 if re.search(r"wi-?fi|wireless|wlan|ethernet|^en|^eth", entrada[1], re.I) else 1

    return sorted(buenas, key=rango)


def escribir(url):
    """Deja `OLLAMA_URL_AULA` en el .env sin tocar nada más."""
    ruta = os.path.join(RAIZ, ".env")
    if not os.path.exists(ruta):
        ejemplo = os.path.join(RAIZ, ".env.example")
        if not os.path.exists(ejemplo):
            raise SystemExit("No hay .env ni .env.example en la raíz del repo.")
        with open(ejemplo, encoding="utf-8", newline="") as f:
            texto = f.read()
        print(f"  (no había .env; lo creé desde .env.example)")
    else:
        with open(ruta, encoding="utf-8", newline="") as f:
            texto = f.read()

    linea = f"{CLAVE}={url}"
    patron = re.compile(rf"^{CLAVE}=.*$", re.M)
    if patron.search(texto):
        anterior = patron.search(texto).group(0)
        texto = patron.sub(linea, texto, count=1)
        cambio = "sin cambios" if anterior == linea else f"antes: {anterior}"
    else:
        texto = texto.rstrip("\n") + f"\n\n# Puesta por scripts/fijar_ip_aula.py\n{linea}\n"
        cambio = "la clave no existía; la agregué al final"

    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(texto)
    return cambio


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--mostrar", action="store_true",
                   help="solo imprime lo que detectó, sin tocar el .env")
    args = p.parse_args()

    encontradas = candidatas()
    if not encontradas:
        print("No encontré una IP de LAN utilizable.")
        print("¿Estás conectado a la red del aula por cable o wifi?")
        return 1

    direccion, interfaz, prefijo = encontradas[0]
    url = f"http://{direccion}:{PUERTO}"

    print(f"  IP del aula : {direccion}/{prefijo}   via {interfaz}")
    if len(encontradas) > 1:
        print("  Otras candidatas, por si la de arriba no es la del aula:")
        for d, i, pre in encontradas[1:]:
            print(f"      {d}/{pre}   via {i}")

    if args.mostrar:
        print(f"\n  {CLAVE}={url}")
        return 0

    cambio = escribir(url)
    print(f"\n  {CLAVE}={url}")
    print(f"  escrito en el .env de la raíz  ({cambio})")
    print(f"\n  Los asistentes ponen esa línea y OLLAMA_DESTINO=aula.")
    print(f"  Verifícalo desde OTRA laptop: curl {url}/api/tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
