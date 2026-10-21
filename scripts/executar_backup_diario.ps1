[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$raizProjeto = Split-Path -Parent $PSScriptRoot
$pythonProjeto = Join-Path $raizProjeto ".venv\Scripts\python.exe"
$managePy = Join-Path $raizProjeto "manage.py"

if (-not (Test-Path -LiteralPath $pythonProjeto -PathType Leaf)) {
    throw "Python do ambiente virtual não encontrado: $pythonProjeto"
}

$codigoSaida = 1
Push-Location -LiteralPath $raizProjeto
try {
    & $pythonProjeto $managePy executar_backup_diario
    $codigoSaida = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $codigoSaida
