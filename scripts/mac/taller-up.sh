#!/usr/bin/env bash
# ============================================================================
# Levanta el backend y el frontend en TU laptop. Cada asistente corre esto.
# ============================================================================
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# UN solo .env, el de la raiz: lo leen el codigo de src/paso*, los notebooks y
# el contenedor del backend. Antes habia dos y era una trampa.
[ -f "$RAIZ/.env" ] || {
  cp "$RAIZ/.env.example" "$RAIZ/.env"
  echo "Cree .env en la raiz. Edítalo: OLLAMA_DESTINO y CHAT_MODEL."
}

cd "$RAIZ/infra/taller"
docker compose up -d --build

echo ""
echo "Backend  http://localhost:8000/docs"
echo "Frontend http://localhost:4200"
echo ""
echo "Verificar todo:  python scripts/verificar_ambiente.py"
