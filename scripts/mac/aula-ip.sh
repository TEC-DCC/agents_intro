#!/usr/bin/env bash
# ============================================================================
# La IP de LAN que hay que dictarle al salon. macOS.
# ============================================================================
# Imprime la linea exacta que cada asistente pega en su .env. Dictar una IP a
# veinte personas genera erratas; dictar una linea para copiar, menos.
#
# En macOS no hay `ip addr`. La interfaz que importa es la de la ruta por
# omision: buscarla asi evita listar las de Docker, las VPN y los adaptadores
# Thunderbolt, que el salon no alcanza.
# ============================================================================
set -euo pipefail

# Si alguien en Windows corrio esto en Git Bash, el mensaje deberia mandarlo al
# script que si funciona en su sistema, no fallar de forma confusa.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    echo "Estas en Windows (Git Bash). Usa la version de PowerShell:" >&2
    echo "    .\\scripts\\win\\aula-ip.ps1" >&2
    exit 1
    ;;
esac

verde=$'\033[32m'; amarillo=$'\033[33m'; gris=$'\033[90m'; fin=$'\033[0m'

ips=()
principal="$(route -n get default 2>/dev/null | awk '/interface:/{print $2}' || true)"

# La principal primero; en0 y en1 como respaldo por si la ruta por omision va
# por una VPN. Sin duplicados: la principal suele ser tambien en0.
for iface in $principal en0 en1; do
  [ -n "$iface" ] || continue
  direccion="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
  [ -n "$direccion" ] || continue
  ya=0
  for e in ${ips[@]+"${ips[@]}"}; do
    [ "${e%%|*}" = "$direccion" ] && ya=1
  done
  [ "$ya" -eq 0 ] && ips+=("$direccion|$iface")
done

if [ "${#ips[@]}" -eq 0 ]; then
  echo "No encontre una IP de LAN. Estas conectado a la red del aula?" >&2
  exit 1
fi

echo
for entrada in "${ips[@]}"; do
  echo "  ${verde}OLLAMA_URL_AULA=http://${entrada%%|*}:11434${fin}"
  echo "      ${gris}via ${entrada##*|}${fin}"
done

echo
echo "  ${gris}Esa linea va en el .env de cada asistente, con OLLAMA_DESTINO=aula.${fin}"
echo "  ${gris}Si hay varias, es la de la interfaz conectada a la red del aula.${fin}"
echo "  ${amarillo}Verifícalo desde OTRA laptop antes de empezar:${fin}"
echo "  ${amarillo}    curl http://${ips[0]%%|*}:11434/api/tags${fin}"
echo "  ${gris}Desde localhost siempre funciona: eso no prueba nada.${fin}"
echo
