#!/usr/bin/env bash
# ============================================================================
# Baja Ollama. Solo la maquina del instructor.
# ============================================================================
# El volumen NO se toca: es externo y lo comparte itzae. `down -v` aqui
# borraria los 10 GB de modelos de los dos proyectos.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CARPETA="$(basename "$(dirname "${BASH_SOURCE[0]}")")"

cd "$RAIZ/infra/aula"
docker compose down

echo ""
echo "Ollama abajo. El volumen de modelos quedo intacto."
echo "Acuérdate de cerrar el firewall si ya no lo necesitas:"
echo "    ./scripts/$CARPETA/aula-firewall.sh --quitar"
