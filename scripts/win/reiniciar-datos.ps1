# ============================================================================
# Devuelve el dominio a su estado inicial.
# ============================================================================
# Se usa seguido: entre practica y practica, y despues de cada demo de falla
# del bloque 5 (sobre todo la que cancela el pedido equivocado).
# La raiz del repo: dos niveles arriba de scripts/win/
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$url = "http://localhost:8000/api/admin/reiniciar"

try {
    Invoke-RestMethod -Uri $url -Method Post -TimeoutSec 10 | Out-Null
    Write-Host "Datos reiniciados." -ForegroundColor Green
}
catch {
    Write-Host "El endpoint no respondio; reinicio el contenedor." -ForegroundColor Yellow
    Push-Location (Join-Path $raiz "infra\taller")
    try { docker compose restart backend } finally { Pop-Location }
}
