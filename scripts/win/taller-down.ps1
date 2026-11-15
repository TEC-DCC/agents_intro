# ============================================================================
# Baja el backend y el frontend. Los datos sobreviven (viven en datos/).
# ============================================================================
# Informa qué hizo. `docker compose down` sobre un proyecto que no está arriba
# devuelve 0 y no imprime nada, así que sin este aviso el script parece roto
# cuando en realidad hizo lo correcto.
# ============================================================================

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Push-Location (Join-Path $raiz "infra\taller")
try {
    $corriendo = @(docker compose ps --quiet).Where({ $_ -ne "" }).Count

    if ($corriendo -eq 0) {
        Write-Host "No habia nada arriba: nada que bajar." -ForegroundColor Yellow
        Write-Host "Para levantarlo:  .\scripts\win\taller-up.ps1" -ForegroundColor Cyan
    }
    else {
        docker compose down
        Write-Host "`nBajados $corriendo contenedor(es)." -ForegroundColor Green
        Write-Host "Los datos siguen en datos/ y las imagenes no se borraron." -ForegroundColor DarkGray
    }
}
finally {
    Pop-Location
}
