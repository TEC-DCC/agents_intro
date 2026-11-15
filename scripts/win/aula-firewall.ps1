# ============================================================================
# Abre el puerto 11434 en el firewall de Windows. REQUIERE ADMINISTRADOR.
# ============================================================================
# Publicar el puerto en Docker no basta: el firewall de Windows bloquea la
# entrada y desde localhost todo parece correcto. Es el problema de logistica
# que se descubre tarde, porque el instructor prueba en su propia maquina.
#
# Abrir PowerShell como administrador y correr:
#   .\scripts\win\aula-firewall.ps1
#
# Para cerrarlo cuando termine el taller:
#   .\scripts\win\aula-firewall.ps1 -Quitar
#
# ---------------------------------------------------------------------------
# EL PERFIL DE RED IMPORTA, Y ES LA TRAMPA DE ESTE SCRIPT
# ---------------------------------------------------------------------------
# Una regla de firewall solo aplica a los perfiles que declara. Si la red esta
# marcada como Publica y la regla es Privada, la regla se crea, el script
# reporta exito, y el salon sigue sin poder conectarse. Por eso aca se detecta
# el perfil activo antes de crear nada.
#
# Lo correcto para una red de aula es marcarla como Privada. Si no se puede,
# -IncluirRedPublica crea la regla tambien para el perfil publico: funciona,
# pero abre el puerto en cualquier red publica a la que te conectes despues,
# asi que conviene acotarla con -Subred y quitarla al terminar.
# ============================================================================

# [CmdletBinding()] hace que PowerShell RECHACE parametros desconocidos. Sin
# esto, un flag mal escrito se liga posicionalmente a -Subred: `-Quitarr` se
# convertiria en la subred de la regla, en silencio. Importa mas ahora que el
# notebook 00 arma estos argumentos por codigo.
[CmdletBinding()]
param(
    [switch]$Quitar,
    # Restringe la regla a la subred del aula en lugar de abrir a cualquiera.
    # Ejemplo: -Subred "192.168.1.0/24"
    [string]$Subred = "",
    # Incluye el perfil Publico. Solo si no se puede marcar la red como Privada.
    [switch]$IncluirRedPublica
)

$nombre = "Agenticai - Ollama taller (11434)"

$esAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $esAdmin) {
    Write-Host "Hace falta PowerShell como administrador." -ForegroundColor Red
    Write-Host "    Clic derecho en PowerShell -> Ejecutar como administrador"
    exit 1
}

$existente = Get-NetFirewallRule -DisplayName $nombre -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------------
# Quitar
# ---------------------------------------------------------------------------
if ($Quitar) {
    if ($existente) {
        Remove-NetFirewallRule -DisplayName $nombre
        Write-Host "Regla eliminada. El puerto 11434 ya no acepta conexiones externas." -ForegroundColor Green
    }
    else {
        Write-Host "No habia regla que quitar." -ForegroundColor Yellow
    }
    exit 0
}

# ---------------------------------------------------------------------------
# El perfil de la red activa
# ---------------------------------------------------------------------------
$conexiones = Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -ne "Disconnected" }

Write-Host "Redes conectadas:" -ForegroundColor Cyan
foreach ($c in $conexiones) {
    $color = if ($c.NetworkCategory -eq "Public") { "Yellow" } else { "Green" }
    Write-Host ("    {0,-22} {1}" -f $c.InterfaceAlias, $c.NetworkCategory) -ForegroundColor $color
}
Write-Host ""

$publicas = @($conexiones | Where-Object { $_.NetworkCategory -eq "Public" })
$perfiles = @("Private")

if ($publicas.Count -gt 0) {
    if ($IncluirRedPublica) {
        $perfiles += "Public"
        Write-Host "Incluyo el perfil Publico porque lo pediste explicitamente." -ForegroundColor Yellow
        Write-Host "Acuérdate de quitar la regla al terminar el taller." -ForegroundColor Yellow
        Write-Host ""
    }
    else {
        Write-Host "==========================================================" -ForegroundColor Yellow
        Write-Host " ATENCION: tu red esta marcada como PUBLICA." -ForegroundColor Yellow
        Write-Host "" -ForegroundColor Yellow
        Write-Host " Una regla de perfil Privado NO aplica en una red Publica." -ForegroundColor Yellow
        Write-Host " Si la creo asi, el script dice 'listo' y el salon igual no" -ForegroundColor Yellow
        Write-Host " se puede conectar." -ForegroundColor Yellow
        Write-Host "" -ForegroundColor Yellow
        Write-Host " Lo recomendado: marcar la red del aula como Privada." -ForegroundColor Yellow
        foreach ($c in $publicas) {
            Write-Host ("     Set-NetConnectionProfile -InterfaceAlias '{0}' -NetworkCategory Private" -f $c.InterfaceAlias) -ForegroundColor Cyan
        }
        Write-Host "" -ForegroundColor Yellow
        Write-Host " Si no puedes cambiarla, vuelve a correr esto con:" -ForegroundColor Yellow
        Write-Host "     .\scripts\win\aula-firewall.ps1 -IncluirRedPublica -Subred '192.168.1.0/24'" -ForegroundColor Cyan
        Write-Host "==========================================================" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "No cree ninguna regla. Elige una de las dos opciones de arriba." -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------
if ($existente) {
    Write-Host "La regla ya existe." -ForegroundColor Yellow
    $existente | Format-List DisplayName, Enabled, Direction, Action, Profile
    exit 0
}

$params = @{
    DisplayName = $nombre
    Direction   = "Inbound"
    LocalPort   = 11434
    Protocol    = "TCP"
    Action      = "Allow"
    Profile     = $perfiles
}
if ($Subred) { $params["RemoteAddress"] = $Subred }

New-NetFirewallRule @params | Out-Null

Write-Host ("Puerto 11434 abierto para el perfil: {0}" -f ($perfiles -join ", ")) -ForegroundColor Green
if (-not $Subred) {
    Write-Host "`nNota: la regla acepta cualquier origen en ese perfil. Para acotarla" -ForegroundColor DarkGray
    Write-Host "a la subred del aula, volve a correrla con -Quitar y luego:" -ForegroundColor DarkGray
    Write-Host '    .\scripts\win\aula-firewall.ps1 -Subred "192.168.1.0/24"' -ForegroundColor DarkGray
}

Write-Host "`nVerificalo DESDE OTRA LAPTOP, no desde esta:" -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "aula-ip.ps1")
