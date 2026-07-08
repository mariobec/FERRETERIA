# Acceso directo escritorio -> LhexIA Control (INSTALACION\LhexIA_Centro_Control.exe)
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$InstalacionDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'INSTALACION'),
    [string]$Desktop = [Environment]::GetFolderPath('Desktop'),
    [string]$ShortcutName = 'LhexIA Control.lnk'
)

$exe = Join-Path $InstalacionDir 'LhexIA_Centro_Control.exe'
$pyScript = Join-Path $RepoRoot 'scripts\lhexia_centro_control.py'
$venvPy = Join-Path $RepoRoot '.venv\Scripts\pythonw.exe'

$target = $null
$workDir = $InstalacionDir
$args = ''

if (Test-Path -LiteralPath $exe) {
    $target = $exe
} elseif (Test-Path -LiteralPath $venvPy) {
    $target = $venvPy
    $args = "`"$pyScript`""
    $workDir = $RepoRoot
} elseif (Get-Command pythonw -ErrorAction SilentlyContinue) {
    $target = (Get-Command pythonw).Source
    $args = "`"$pyScript`""
    $workDir = $RepoRoot
} else {
    Write-Error "No se encontro LhexIA_Centro_Control.exe ni Python. Ejecute INSTALACION\COMPILAR_CENTRO_CONTROL.bat"
    exit 1
}

$lnk = Join-Path $Desktop $ShortcutName
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $target
$shortcut.Arguments = $args
$shortcut.WorkingDirectory = $workDir
$shortcut.Description = 'LhexIA Control — PostgreSQL, ERP y servicios'
$shortcut.Save()
Write-Host "[OK] Acceso directo creado: $lnk"
Write-Host "     Destino: $target $args"
