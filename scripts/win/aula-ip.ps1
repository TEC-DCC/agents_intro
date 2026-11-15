# ============================================================================
# La IP de LAN que hay que dictarle al salón.
# ============================================================================
# Imprime la línea exacta que cada asistente pega en su .env. Dictar una IP
# a 20 personas genera erratas; dictar una línea para copiar, menos.
# ============================================================================

$candidatas = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -ne "127.0.0.1" -and
        $_.PrefixOrigin -ne "WellKnown" -and
        # Las interfaces virtuales de Docker/WSL/Hyper-V no sirven: el salón
        # no las alcanza. Es el error que cuesta diez minutos de taller.
        $_.InterfaceAlias -notmatch "Loopback|WSL|Hyper-V|vEthernet|Docker"
    } |
    Sort-Object -Property @{ Expression = { $_.InterfaceAlias -match "Wi-Fi|Wireless" } }

if (-not $candidatas) {
    Write-Host "No encontré una IP de LAN. ¿Estás conectado a la red del aula?" -ForegroundColor Red
    exit 1
}

Write-Host ""
foreach ($ip in $candidatas) {
    Write-Host ("  OLLAMA_URL_AULA=http://{0}:11434" -f $ip.IPAddress) -ForegroundColor Green
    Write-Host ("      via {0}" -f $ip.InterfaceAlias) -ForegroundColor DarkGray
}

Write-Host "`n  Esa linea va en el .env de cada asistente, junto con OLLAMA_DESTINO=aula." -ForegroundColor DarkGray
Write-Host "  Si hay varias, es la de la interfaz conectada a la red del aula." -ForegroundColor DarkGray
Write-Host "  Verifícalo desde OTRA laptop antes de empezar:" -ForegroundColor Yellow
Write-Host ("      curl http://{0}:11434/api/tags" -f $candidatas[0].IPAddress) -ForegroundColor Yellow
Write-Host "  Desde localhost siempre funciona: eso no prueba nada.`n" -ForegroundColor DarkGray
