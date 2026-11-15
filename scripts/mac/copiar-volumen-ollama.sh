#!/usr/bin/env bash
# ============================================================================
# Copia el volumen de Ollama de itzae a uno propio del taller. OPCIONAL.
# ============================================================================
# Por omision, infra/aula/docker-compose.yml usa el volumen de itzae como
# externo: ahorra bajar 6.6 GB, al costo de compartirlo. Si no quieres que un
# `ollama pull` del taller toque lo de itzae, corre esto UNA VEZ y cambia el
# `name:` del compose a `agenticai_ollama_data`.
#
# Son ~10 GB: tarda unos minutos y los ocupa en disco dos veces.
# ============================================================================
set -euo pipefail

ORIGEN="itzae_itzae_ollama_data"
DESTINO="agenticai_ollama_data"

# Las anclas del filtro importan: sin ellas, "ollama_data" matchea los volumenes
# de los otros proyectos y el script creeria que ya existe.
if [ -n "$(docker volume ls --quiet --filter "name=^${DESTINO}$")" ]; then
  echo "El volumen '$DESTINO' ya existe. Nada que hacer."
  exit 0
fi

if [ -z "$(docker volume ls --quiet --filter "name=^${ORIGEN}$")" ]; then
  echo "No encontre el volumen de origen '$ORIGEN'." >&2
  echo "Si no tienes el proyecto itzae, no hace falta copiar nada: deja el" >&2
  echo "compose como esta y Ollama va a descargar el modelo la primera vez." >&2
  exit 1
fi

echo "Creando '$DESTINO' y copiando ~10 GB desde '$ORIGEN'..."
docker volume create "$DESTINO" >/dev/null

docker run --rm \
  -v "${ORIGEN}:/origen:ro" \
  -v "${DESTINO}:/destino" \
  alpine sh -c 'cp -a /origen/. /destino/ && du -sh /destino'

echo ""
echo "Listo. Ahora edita infra/aula/docker-compose.yml:"
echo "    name: $DESTINO"
