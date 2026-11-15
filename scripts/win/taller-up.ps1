# ============================================================================
# Levanta el backend y el frontend en TU laptop. Cada asistente corre esto.
# ============================================================================
$ErrorActionPreference = "Stop"
# La raiz del repo: dos niveles arriba de scripts/win/
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$taller = Join-Path $raiz "infra\taller"

# UN solo .env, el de la raiz: lo leen el codigo de src/paso*, los notebooks y
# el contenedor del backend. Antes habia dos y era una trampa, sobre todo ahora
# que ahi viven las claves de API.
if (-not (Test-Path (Join-Path $raiz ".env"))) {
    Copy-Item (Join-Path $raiz ".env.example") (Join-Path $raiz ".env")
    Write-Host "Cree .env en la raiz. Edítalo: OLLAMA_DESTINO y CHAT_MODEL." -ForegroundColor Yellow
}

Push-Location $taller
try {
    docker compose up -d --build
    if (-not $?) { throw "docker compose fallo" }
}
finally { Pop-Location }

Write-Host "`nBackend  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Frontend http://localhost:4200" -ForegroundColor Green
Write-Host "`nVerificar todo:  python scripts\verificar_ambiente.py" -ForegroundColor Cyan
