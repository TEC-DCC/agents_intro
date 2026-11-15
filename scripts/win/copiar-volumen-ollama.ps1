# ============================================================================
# Copia el volumen de Ollama de itzae a uno propio del taller. OPCIONAL.
# ============================================================================
# Por omision, infra/aula/docker-compose.yml usa el volumen de itzae como
# externo: ahorra bajar 6.6 GB, al costo de compartirlo. Si no quieres que un
# `ollama pull` del taller toque lo de itzae, ejecuta esto UNA VEZ y cambia el
# `name:` del compose a `agenticai_ollama_data`.
#
# Son ~10 GB: tarda unos minutos y los ocupa en disco dos veces.
# ============================================================================
$ErrorActionPreference = "Stop"
$origen = "itzae_itzae_ollama_data"
$destino = "agenticai_ollama_data"

$existe = docker volume ls --quiet --filter "name=^$destino$"
if ($existe) {
    Write-Host "El volumen '$destino' ya existe. Nada que hacer." -ForegroundColor Yellow
    exit 0
}

Write-Host "Creando '$destino' y copiando ~10 GB desde '$origen'..." -ForegroundColor Cyan
docker volume create $destino | Out-Null

$env:MSYS_NO_PATHCONV = "1"
docker run --rm -v "${origen}:/origen:ro" -v "${destino}:/destino" alpine `
    sh -c "cp -a /origen/. /destino/ && du -sh /destino"
if (-not $?) { throw "la copia fallo" }

Write-Host "`nListo. Ahora edita infra/aula/docker-compose.yml:" -ForegroundColor Green
Write-Host "    name: $destino" -ForegroundColor Green
