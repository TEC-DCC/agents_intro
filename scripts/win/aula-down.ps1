# ============================================================================
# Baja Ollama. Solo la maquina del instructor.
# ============================================================================
# El volumen NO se toca: es externo y lo comparte itzae. `down -v` aqui
# borraria los 10 GB de modelos de los dos proyectos.
# La raiz del repo: dos niveles arriba de scripts/win/
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location (Join-Path $raiz "infra\aula")
try { docker compose down } finally { Pop-Location }

Write-Host "`nOllama abajo. El volumen de modelos quedo intacto." -ForegroundColor Green
Write-Host "Acuérdate de cerrar el firewall si ya no lo necesitas:" -ForegroundColor DarkGray
Write-Host "    .\scripts\win\aula-firewall.ps1 -Quitar" -ForegroundColor DarkGray
