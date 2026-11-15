#!/usr/bin/env bash
# ============================================================================
# El firewall de macOS y el puerto 11434.
# ============================================================================
# Aviso importante: en macOS NO hay un equivalente de la regla de puerto de
# Windows o de ufw. El firewall de macOS filtra por APLICACION, no por puerto.
# Asi que este script no "abre un puerto": informa el estado y dice que hacer
# si el salon no te alcanza.
#
#   ./scripts/mac/aula-firewall.sh
#   ./scripts/mac/aula-firewall.sh --quitar
# ============================================================================
set -euo pipefail

# Si alguien en Windows corrio esto en Git Bash, el mensaje deberia mandarlo al
# script que si funciona en su sistema, no fallar de forma confusa.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    echo "Estas en Windows (Git Bash). Usa la version de PowerShell:" >&2
    echo "    .\\scripts\\win\\aula-firewall.ps1" >&2
    exit 1
    ;;
esac

QUITAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --quitar) QUITAR=1; shift ;;
    --subred) echo "macOS no filtra por subred: su firewall es por aplicacion." >&2; shift 2 ;;
    *) echo "Opcion desconocida: $1" >&2; exit 2 ;;
  esac
done

FW=/usr/libexec/ApplicationFirewall/socketfilterfw
DOCKER_BIN=/Applications/Docker.app/Contents/MacOS/com.docker.backend

estado="$("$FW" --getglobalstate 2>/dev/null || echo "desconocido")"
echo "Firewall de macOS: $estado"

if echo "$estado" | grep -qi "disabled"; then
  echo
  echo "Esta apagado: no hay nada que abrir."
  echo "Si el salon no te alcanza, el problema es la red o la IP, no el firewall."

elif [ "$QUITAR" -eq 1 ]; then
  echo
  echo "Este script no agrega reglas de puerto, asi que no hay nada que quitar."
  echo "Si permitiste Docker a mano, quítalo desde:"
  echo "    Ajustes del Sistema > Red > Firewall > Opciones"

else
  echo
  echo "El firewall de macOS es por aplicacion. Si el salon no te alcanza,"
  echo "permiti conexiones entrantes para Docker:"
  echo
  echo "    Ajustes del Sistema > Red > Firewall > Opciones"
  echo
  echo "O desde la terminal:"
  echo "    sudo $FW --add $DOCKER_BIN"
  echo "    sudo $FW --unblockapp $DOCKER_BIN"
fi

if [ "$QUITAR" -eq 0 ]; then
  echo
  echo "Verifícalo DESDE OTRA LAPTOP, no desde esta:"
  exec "$(dirname "${BASH_SOURCE[0]}")/aula-ip.sh"
fi
