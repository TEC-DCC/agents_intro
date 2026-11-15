#!/usr/bin/env bash
# ============================================================================
# Levanta Ollama para todo el salon. Solo en la maquina del instructor.
# ============================================================================
# LEER ESTO ANTES DE DAR EL TALLER DESDE UNA MAC:
#
# Docker Desktop en macOS NO hace pasar la GPU al contenedor. No existe un
# equivalente de --gpus en la VM que Docker usa en Apple Silicon, asi que este
# compose correria qwen3.5:9b en CPU: inservible para un taller de 4 horas con
# veinte personas preguntando.
#
# En una Mac hay que usar Ollama NATIVO, que si usa Metal:
#
#     brew install ollama
#     ollama pull qwen3.5:9b
#     OLLAMA_HOST=0.0.0.0 ollama serve
#
# OLLAMA_HOST=0.0.0.0 es lo que importa: por omision Ollama escucha solo en
# localhost y el salon no lo alcanza.
# ============================================================================
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AULA="$RAIZ/infra/aula"

verde=$'\033[32m'; cian=$'\033[36m'; amarillo=$'\033[33m'; rojo=$'\033[31m'; fin=$'\033[0m'

echo "${amarillo}============================================================${fin}"
echo "${amarillo} En macOS, Docker no accede a la GPU.${fin}"
echo "${amarillo} Este compose va a correr qwen3.5:9b en CPU, y va a ser${fin}"
echo "${amarillo} inusable para un taller.${fin}"
echo "${amarillo}${fin}"
echo "${amarillo} Lo que si funciona en una Mac es Ollama nativo, con Metal:${fin}"
echo "${amarillo}     brew install ollama${fin}"
echo "${amarillo}     ollama pull qwen3.5:9b${fin}"
echo "${amarillo}     OLLAMA_HOST=0.0.0.0 ollama serve${fin}"
echo "${amarillo}============================================================${fin}"
echo
printf "Seguir igual con Docker? [s/N] "
read -r respuesta
case "$respuesta" in [sS]*) ;; *) echo "Cancelado."; exit 1 ;; esac

[ -f "$AULA/.env" ] || {
  echo "${amarillo}Creando infra/aula/.env desde el ejemplo...${fin}"
  cp "$AULA/.env.example" "$AULA/.env"
}

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
