#!/usr/bin/env bash
# ============================================================================
# Levanta Ollama para todo el salon. Solo en la maquina del instructor.
# ============================================================================
# Necesita el NVIDIA Container Toolkit instalado, que es lo que le da acceso a
# la GPU al contenedor:
#   https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
# Sin eso, `docker compose up` falla al pedir el recurso nvidia.
# ============================================================================
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AULA="$RAIZ/infra/aula"

verde=$'\033[32m'; cian=$'\033[36m'; amarillo=$'\033[33m'; rojo=$'\033[31m'; fin=$'\033[0m'

[ -f "$AULA/.env" ] || {
  echo "${amarillo}Creando infra/aula/.env desde el ejemplo...${fin}"
  cp "$AULA/.env.example" "$AULA/.env"
}

if ! docker info 2>/dev/null | grep -qi nvidia; then
  echo "${amarillo}AVISO: Docker no reporta el runtime de nvidia.${fin}"
  # Sin backticks: dentro de comillas dobles bash los trata como sustitucion
  # de comandos, y este aviso ejecutaria un `docker compose up` de verdad.
  echo "${amarillo}Si docker compose up falla, falta el NVIDIA Container Toolkit.${fin}"
fi

echo "${cian}Levantando Ollama...${fin}"
cd "$AULA"
docker compose up -d

# El healthcheck declara start_period de 120s: la primera carga de un 9B desde
# disco no es rapida. Esperamos a que la API conteste antes de dar el OK.
echo
echo "${cian}Esperando a que la API responda (hasta 3 min)...${fin}"
listo=0
for _ in $(seq 36); do
  if curl -fsS --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
    listo=1; break
  fi
  sleep 5; printf "."
done
echo

if [ "$listo" -eq 0 ]; then
  echo "${rojo}La API no respondio. Revisa los registros:${fin}" >&2
  echo "    docker logs agenticai_ollama --tail 50" >&2
  exit 1
fi

echo "${verde}Ollama arriba. Modelos:${fin}"
# `ollama list` ya da una tabla con nombre y tamano. La version PowerShell
# parsea el JSON porque tiene Invoke-RestMethod a mano; aqui eso serian
# comillas anidadas sin ninguna ganancia.
docker exec agenticai_ollama ollama list | sed 's/^/    /'

echo
# Fija OLLAMA_URL_AULA en el .env con la IP de ESTA maquina, que es la que
# sirve el modelo. La asigna el DHCP y cambia sola, asi que escribirla a mano
# envejece mal.
echo "${cian}La direccion para el salon:${fin}"
PY="$(command -v python3 || command -v python)"
exec "$PY" "$(dirname "${BASH_SOURCE[0]}")/../fijar_ip_aula.py"
