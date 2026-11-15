#!/usr/bin/env bash
# ============================================================================
# La IP de LAN que hay que dictarle al salon. Linux.
# ============================================================================
# Imprime la linea exacta que cada asistente pega en su .env. Dictar una IP a
# veinte personas genera erratas; dictar una linea para copiar, menos.
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
# Las interfaces de Docker, de las VM, de Kubernetes y los tuneles no sirven:
# el salon no las alcanza. Es el error que cuesta diez minutos de taller.
while read -r iface direccion; do
  case "$iface" in
    lo|docker*|br-*|veth*|virbr*|tun*|tap*|cni*|flannel*|kube*|zt*|wg*) continue ;;
  esac
  ips+=("${direccion%%/*}|$iface")
done < <(ip -o -4 addr show scope global | awk '{print $2, $4}')

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
