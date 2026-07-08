# Conectar impresora Zebra en red (DESKTOP-7IVP42A / 192.168.1.10)
# Ejecutar en LHEXIA: clic derecho PowerShell -> Ejecutar como administrador (recomendado)
param(
    [string]$HostPc = 'DESKTOP-7IVP42A',
    [string]$HostIp = '192.168.1.10',
    [string]$ShareName = 'ZDesigner GX420d',
    [string]$UsuarioRemoto = '',
    [string]$ClaveRemota = ''
)

$ErrorActionPreference = 'Stop'
$unc = "\\$HostPc\$ShareName"
$uncIp = "\\$HostIp\$ShareName"
$colaLocal = 'ZDesigner GX420d Red'

Write-Host "Conectando a $unc ..."

if (-not $UsuarioRemoto) {
    $UsuarioRemoto = Read-Host "Usuario en $HostPc (ej. DESKTOP-7IVP42A\mario)"
}
if (-not $ClaveRemota) {
    $sec = Read-Host "Clave de $UsuarioRemoto" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    $ClaveRemota = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

cmd /c "net use \\$HostPc\IPC$ /user:$UsuarioRemoto $ClaveRemota" | Out-Host

$net = New-Object -ComObject WScript.Network
try {
    $net.AddWindowsPrinterConnection($unc)
    Write-Host "OK: cola de red agregada ($unc)"
} catch {
    Write-Host "COM fallo, intentando puerto + driver local ..."
    if (-not (Get-PrinterPort -Name $uncIp -ErrorAction SilentlyContinue)) {
        Add-PrinterPort -Name $uncIp
    }
    if (-not (Get-Printer -Name $colaLocal -ErrorAction SilentlyContinue)) {
        Add-Printer -Name $colaLocal -DriverName 'ZDesigner GX420d' -PortName $uncIp
    }
    Write-Host "OK: $colaLocal"
}

$w = Get-WmiObject Win32_Printer -Filter "Name='$colaLocal'" -ErrorAction SilentlyContinue
if (-not $w) {
    $w = Get-WmiObject Win32_Printer -Filter "Name='$ShareName'" -ErrorAction SilentlyContinue
}
if ($w -and $w.WorkOffline) {
    $w.WorkOffline = $false
    $w.Put() | Out-Null
}

Write-Host "`nColas Zebra:"
Get-Printer | Where-Object { $_.Name -match 'GX420|Zebra' } |
    Format-Table Name, PortName, PrinterStatus -AutoSize

Write-Host "`nPrueba ZPL..."
$zpl = '^XA^FO20,20^A0N,40,40^FDPRUEBA RED OK^FS^XZ'
$tmp = Join-Path $env:TEMP 'zebra_red_ok.zpl'
Set-Content $tmp $zpl -NoNewline
$target = if (Get-Printer -Name $colaLocal -ErrorAction SilentlyContinue) { $colaLocal } else { $ShareName }
cmd /c "copy /b `"$tmp`" `"$target`""
Write-Host "copy exit=$LASTEXITCODE -> $target"
Write-Host "`nConfigure en ERP: ZEBRA_IMPRESORA_NOMBRE=$target"
