# ============================================================================
# Levanta Ollama para todo el salón. Solo en la máquina del instructor.
# ============================================================================
#   .\scripts\win\aula-up.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
# La raiz del repo: dos niveles arriba de scripts/win/
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$aula = Join-Path $raiz "infra\aula"

if (-not (Test-Path (Join-Path $aula ".env"))) {
    Write-Host "Creando infra\aula\.env desde el ejemplo..." -ForegroundColor Yellow
    Copy-Item (Join-Path $aula ".env.example") (Join-Path $aula ".env")
}

Write-Host "Levantando Ollama..." -ForegroundColor Cyan
Push-Location $aula
try {
    docker compose up -d
    if (-not $?) { throw "docker compose falló" }
}
finally {
    Pop-Location
}

# El healthcheck declara start_period de 120s: la primera carga de un 9B desde
# disco no es rápida. Esperamos a que la API conteste antes de dar el OK.
Write-Host "`nEsperando a que la API responda (hasta 3 min)..." -ForegroundColor Cyan
$listo = $false
for ($i = 1; $i -le 36; $i++) {
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
        $listo = $true
        break
    }
    catch {
        Start-Sleep -Seconds 5
        Write-Host "." -NoNewline
    }
}
Write-Host ""

if (-not $listo) {
    Write-Host "La API no respondió. Revisa los registros:" -ForegroundColor Red
    Write-Host "    docker logs agenticai_ollama --tail 50"
    exit 1
}

Write-Host "Ollama arriba. Modelos:" -ForegroundColor Green
foreach ($m in $r.models) {
    $gb = [math]::Round($m.size / 1GB, 1)
    Write-Host ("    {0}  ({1} GB)" -f $m.name, $gb)
}

# Fija OLLAMA_URL_AULA en el .env con la IP de ESTA maquina, que es la que
# sirve el modelo. La asigna el DHCP y cambia sola, asi que escribirla a mano
# envejece mal.
Write-Host "`nLa dirección para el salón:" -ForegroundColor Cyan
# El ambiente virtual puede llamarse .venv o .venvw. Si no hay ninguno, el
# python del sistema alcanza: este script solo usa la libreria estandar.
$py = "python"
foreach ($amb in ".venv", ".venvw") {
    $cand = Join-Path $PSScriptRoot "..\..\$amb\Scripts\python.exe"
    if (Test-Path $cand) { $py = $cand; break }
}
& $py (Join-Path $PSScriptRoot "..\fijar_ip_aula.py")
