[CmdletBinding()]
param(
    [string]$Endereco = "0.0.0.0",
    [ValidateRange(1, 65535)]
    [int]$Porta = 8000
)

$ErrorActionPreference = "Stop"

$raizProjeto = Split-Path -Parent $PSScriptRoot
$pythonVenv = Join-Path $raizProjeto ".venv\Scripts\python.exe"
$aComTil = [char]0x00E3
$cCedilha = [char]0x00E7
$uComAgudo = [char]0x00FA

if (-not (Test-Path -LiteralPath $pythonVenv -PathType Leaf)) {
    Write-Error ("Python da .venv n{0}o encontrado em: {1}" -f $aComTil, $pythonVenv)
    exit 1
}

$enderecosLan = @(
    [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
        Where-Object {
            $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
            -not [System.Net.IPAddress]::IsLoopback($_) -and
            -not $_.IPAddressToString.StartsWith("169.254.")
        } |
        ForEach-Object { $_.IPAddressToString } |
        Sort-Object -Unique
)

if (-not $env:DJANGO_ALLOWED_HOSTS) {
    $hostsPermitidos = @("localhost", "127.0.0.1", "[::1]") + $enderecosLan
    $env:DJANGO_ALLOWED_HOSTS = $hostsPermitidos -join ","
}

Push-Location -LiteralPath $raizProjeto
try {
    Write-Host "Servidor local: http://127.0.0.1:$Porta/"
    Write-Host (
        "Verifica{0}{1}o de sa{2}de: http://127.0.0.1:{3}/saude/" -f
        $cCedilha, $aComTil, $uComAgudo, $Porta
    )
    foreach ($enderecoLan in $enderecosLan) {
        Write-Host "Rede local: http://${enderecoLan}:$Porta/"
    }
    if ($enderecosLan.Count -eq 0) {
        Write-Warning (
            "IPv4 da rede local n{0}o encontrado. Verifique com ipconfig." -f
            $aComTil
        )
    }
    & $pythonVenv manage.py runserver "${Endereco}:$Porta" --noreload
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
