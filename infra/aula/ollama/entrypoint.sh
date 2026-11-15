#!/bin/bash
# ============================================================================
# Ollama Entrypoint - Auto-start server and pull configured model
# Used as the Docker entrypoint for the Ollama service.
# ============================================================================

MODEL="${OLLAMA_MODEL:-mistral}"

echo "============================================"
echo "  Ollama - Starting server"
echo "  Model: $MODEL"
echo "============================================"

# Start Ollama server in the background
ollama serve &
SERVER_PID=$!

# Wait for the API to be ready
echo "[1/2] Waiting for Ollama API..."
MAX_RETRIES=60
RETRY=0
until ollama list > /dev/null 2>&1; do
  RETRY=$((RETRY + 1))
  if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
    echo "ERROR: Ollama server did not start after ${MAX_RETRIES} attempts."
    exit 1
  fi
  sleep 2
done
echo "  Ollama API is ready."

# Pull the model (no-op if already downloaded)
echo "[2/2] Pulling model '$MODEL'..."
ollama pull "$MODEL"

echo "============================================"
echo "  Ollama is ready!"
echo "  Model:  $MODEL"
echo "  API:    http://localhost:11434"
echo "============================================"

# Keep the server in the foreground
wait $SERVER_PID
