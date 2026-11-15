#!/usr/bin/env bash
# ============================================================================
# Baja el backend y el frontend. Los datos sobreviven (viven en datos/).
# ============================================================================
# Informa que hizo. `docker compose down` sobre un proyecto que no esta arriba
# devuelve 0 y no imprime nada, asi que sin este aviso el script parece roto
# cuando en realidad hizo lo correcto.
# ============================================================================
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CARPETA="$(basename "$(dirname "${BASH_SOURCE[0]}")")"

cd "$RAIZ/infra/taller"

corriendo="$(docker compose ps --quiet | grep -c . || true)"

if [ "$corriendo" -eq 0 ]; then
  echo "No habia nada arriba: nada que bajar."
  echo "Para levantarlo:  ./scripts/$CARPETA/taller-up.sh"
else
  docker compose down
  echo ""
  echo "Bajados $corriendo contenedor(es)."
  echo "Los datos siguen en datos/ y las imagenes no se borraron."
fi
