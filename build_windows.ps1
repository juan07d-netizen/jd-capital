$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python no está instalado. Instalá Python 3.13 x64.'
}
$Python = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }

if (Test-Path .venv) { Remove-Item .venv -Recurse -Force }
& $Python -3.13 -m venv .venv
$VenvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt pyinstaller

# Build a Windows folder containing the executable and all runtime dependencies.
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
& $VenvPython -m PyInstaller --noconfirm --clean --onedir --windowed --name JD-Capital `
    --collect-submodules keyring.backends `
    --collect-all keyring `
    --collect-all argon2 `
    --collect-all openai `
    main.py

$IsccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$ISCC = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ISCC) {
    throw 'PyInstaller terminó correctamente, pero Inno Setup 6 no está instalado. Instalalo y volvé a ejecutar este script para crear el instalador.'
}

& $ISCC (Join-Path $PSScriptRoot 'JD-Capital.iss')
Write-Host ''
Write-Host 'INSTALADOR GENERADO:'
Get-ChildItem (Join-Path $PSScriptRoot 'installer') -Filter 'JD_Capital_Setup.exe' | Select-Object FullName, Length
