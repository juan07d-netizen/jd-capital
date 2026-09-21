$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Invoke-Native([scriptblock]$Command, [string]$Description) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description falló con código de salida $LASTEXITCODE."
    }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python no está instalado. Instalá Python 3.13 x64.'
}
if (Test-Path .venv) { Remove-Item .venv -Recurse -Force }
if (Get-Command py -ErrorAction SilentlyContinue) {
    Invoke-Native { py -3.13 -m venv .venv } 'La creación del entorno virtual'
} else {
    Invoke-Native { python -m venv .venv } 'La creación del entorno virtual'
}
$VenvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Invoke-Native { & $VenvPython -m pip install --upgrade pip } 'La actualización de pip'
Invoke-Native { & $VenvPython -m pip install -r requirements.lock } 'La instalación de dependencias'

# Build a Windows folder containing the executable and all runtime dependencies.
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
Invoke-Native { & $VenvPython -m PyInstaller --noconfirm --clean --onedir --windowed --name JD-Capital `
    --collect-submodules keyring.backends `
    --collect-all keyring `
    --collect-all argon2 `
    --collect-all openai `
    main.py } 'PyInstaller'

$IsccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$ISCC = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ISCC) {
    throw 'PyInstaller terminó correctamente, pero Inno Setup 6 no está instalado. Instalalo y volvé a ejecutar este script para crear el instalador.'
}

Invoke-Native { & $ISCC (Join-Path $PSScriptRoot 'JD-Capital.iss') } 'Inno Setup'
Write-Host ''
Write-Host 'INSTALADOR GENERADO:'
Get-ChildItem (Join-Path $PSScriptRoot 'installer') -Filter 'JD_Capital_Setup.exe' | Select-Object FullName, Length
