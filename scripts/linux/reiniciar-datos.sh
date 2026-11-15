#!/usr/bin/env bash
# ============================================================================
# Devuelve el dominio a su estado inicial.
# ============================================================================
# Se usa seguido: entre practica y practica, y despues de cada demo de falla
# del bloque 5 (sobre todo la que cancela el pedido equivocado).
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if curl -fsS -X POST --max-time 10 http://localhost:8000/api/admin/reiniciar >/dev/null 2>&1; then
  echo "Datos reiniciados."
else
  echo "El endpoint no respondio; reinicio el contenedor."
  cd "$RAIZ/infra/taller"
  docker compose restart backend
fi
