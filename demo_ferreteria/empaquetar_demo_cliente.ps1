# Genera la carpeta DEMO_FERRETERIA_ERP (al mismo nivel que sistema_ventas) lista para entregar.
# Ejecutar: clic derecho -> Ejecutar con PowerShell, o desde PowerShell:
#   Set-ExecutionPolicy -Scope Process Bypass; .\empaquetar_demo_cliente.ps1

$ErrorActionPreference = 'Stop'
$KitDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $KitDir '..')).Path
$Parent = Split-Path -Parent $ProjectRoot
$OutDir = Join-Path $Parent 'DEMO_FERRETERIA_ERP'

Write-Host "Origen:  $ProjectRoot"
Write-Host "Destino: $OutDir"

if (Test-Path $OutDir) {
  Write-Host "Eliminando carpeta anterior..."
  Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Path $OutDir | Out-Null

$files = @(
  'app.py',
  'requirements.txt',
  'bootstrap_admin_local.py',
  'importar_catalogo_categorias.py'
)
foreach ($f in $files) {
  $p = Join-Path $ProjectRoot $f
  if (Test-Path $p) {
    Copy-Item -Path $p -Destination (Join-Path $OutDir $f) -Force
  }
}

$optionalSql = Join-Path $ProjectRoot 'bdferreteria.sql'
if (Test-Path $optionalSql) {
  Copy-Item $optionalSql (Join-Path $OutDir 'bdferreteria.sql') -Force
}

function Invoke-RobocopyMirror {
  param([string]$Src, [string]$Dst)
  & robocopy $Src $Dst /E /XD __pycache__ .git /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy fallo ($Src -> $Dst) codigo $LASTEXITCODE" }
}
Invoke-RobocopyMirror (Join-Path $ProjectRoot 'templates') (Join-Path $OutDir 'templates')
Invoke-RobocopyMirror (Join-Path $ProjectRoot 'static') (Join-Path $OutDir 'static')
Invoke-RobocopyMirror (Join-Path $ProjectRoot 'sql') (Join-Path $OutDir 'sql')

$fromKit = @(
  'instalar_demo_windows.bat',
  'iniciar_demo_windows.bat',
  'post_instalacion_demo.bat',
  'LEEME_INSTALACION_DEMO.txt',
  'env.demo.ejemplo',
  'crear_mysql_bd_demo.sql',
  'crear_tablas_demo.py'
)
foreach ($k in $fromKit) {
  Copy-Item (Join-Path $KitDir $k) (Join-Path $OutDir $k) -Force
}

Write-Host ""
Write-Host "LISTO. Carpeta entregable:" -ForegroundColor Green
Write-Host $OutDir
Write-Host "Comprime DEMO_FERRETERIA_ERP en .zip para el cliente si lo necesitas."
