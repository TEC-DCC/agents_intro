#!/usr/bin/env bash
# ============================================================================
# Abre el puerto 11434 para el salon. Linux. REQUIERE sudo.
# ============================================================================
# Publicar el puerto en Docker no siempre basta: el firewall del sistema puede
# bloquear la entrada, y desde localhost todo parece correcto. Es el problema
# de logistica que se descubre tarde, porque el instructor prueba en su propia
# maquina.
#
#   ./scripts/linux/aula-firewall.sh
#   ./scripts/linux/aula-firewall.sh --subred 192.168.1.0/24
#   ./scripts/linux/aula-firewall.sh --quitar
#
# Linux puede tener tres gestores de firewall distintos, asi que el script
# detecta cual esta activo en lugar de asumir uno.
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

PUERTO=11434
QUITAR=0
SUBRED=""

while [ $# -gt 0 ]; do
  case "$1" in
    --quitar) QUITAR=1; shift ;;
    --subred) SUBRED="${2:?--subred necesita un valor, ej: 192.168.1.0/24}"; shift 2 ;;
    *) echo "Opcion desconocida: $1" >&2; exit 2 ;;
  esac
done

sudo -v 2>/dev/null || { echo "Hace falta sudo." >&2; exit 1; }

if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  if [ "$QUITAR" -eq 1 ]; then
    sudo ufw delete allow "$PUERTO/tcp" 2>/dev/null || true
    if [ -n "$SUBRED" ]; then
      sudo ufw delete allow from "$SUBRED" to any port "$PUERTO" proto tcp 2>/dev/null || true
    fi
    echo "Regla de ufw eliminada."
  elif [ -n "$SUBRED" ]; then
    sudo ufw allow from "$SUBRED" to any port "$PUERTO" proto tcp
    echo "ufw: puerto $PUERTO abierto para $SUBRED."
  else
    sudo ufw allow "$PUERTO/tcp"
    echo "ufw: puerto $PUERTO abierto."
  fi

elif command -v firewall-cmd >/dev/null 2>&1 && sudo firewall-cmd --state >/dev/null 2>&1; then
  if [ "$QUITAR" -eq 1 ]; then
    sudo firewall-cmd --remove-port="$PUERTO/tcp"
    echo "Regla de firewalld eliminada."
  else
    # Sin --permanent a proposito: una regla de taller no deberia sobrevivir a
    # un reinicio sin que nadie se acuerde de que quedo abierta.
    sudo firewall-cmd --add-port="$PUERTO/tcp"
    echo "firewalld: puerto $PUERTO abierto (hasta el proximo reinicio)."
  fi

elif command -v iptables >/dev/null 2>&1; then
  origen=()
  [ -n "$SUBRED" ] && origen=(-s "$SUBRED")
  # ${a[@]+"${a[@]}"} y no "${a[@]:-}": el segundo pasa UN argumento vacio
  # cuando el array esta vacio, e iptables lo rechaza. Y esta forma funciona
  # en el bash 3.2 que todavia trae macOS.
  if [ "$QUITAR" -eq 1 ]; then
    sudo iptables -D INPUT ${origen[@]+"${origen[@]}"} -p tcp --dport "$PUERTO" -j ACCEPT 2>/dev/null || true
    echo "Regla de iptables eliminada."
  else
    sudo iptables -I INPUT ${origen[@]+"${origen[@]}"} -p tcp --dport "$PUERTO" -j ACCEPT
    echo "iptables: puerto $PUERTO abierto (no persiste al reiniciar)."
  fi

else
  echo "No detecte ufw, firewalld ni iptables."
  echo "Puede que no haya firewall activo: pruébalo desde otra laptop."
fi

if [ "$QUITAR" -eq 0 ]; then
  echo
  echo "Verifícalo DESDE OTRA LAPTOP, no desde esta:"
  exec "$(dirname "${BASH_SOURCE[0]}")/aula-ip.sh"
fi
