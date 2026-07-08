# Ejecutar EN LHEXIA (este PC) despues de habilitar en Ferreteria-01
$ErrorActionPreference = 'Continue'
$ip = '192.168.1.10'
$unc = "\\$ip\ZDesigner GX420d"
$cola = 'ZDesigner GX420d Red'

Write-Host 'Limpiando conexiones SMB...'
cmd /c 'net use * /delete /y' 2>$null | Out-Null
cmd /c "net use \\$ip\IPC$ /user:guest `"`"" 2>&1

Write-Host "Agregando cola: $unc"
try {
    $net = New-Object -ComObject WScript.Network
    $net.AddWindowsPrinterConnection($unc)
    Write-Host 'OK cola de red'
} catch {
    Write-Host "GUI/COM: $($_.Exception.Message)"
    Write-Host 'Si falla, use Configuracion -> Impresoras -> Agregar -> compartida:'
    Write-Host "  $unc"
}

if (-not (Get-Printer -Name $cola -ErrorAction SilentlyContinue)) {
    Write-Host 'Intentando cola local con driver (requiere admin)...'
    try {
        if (-not (Get-PrinterPort -Name $unc -ErrorAction SilentlyContinue)) { Add-PrinterPort -Name $unc }
        Add-Printer -Name $cola -DriverName 'ZDesigner GX420d' -PortName $unc
        Write-Host "OK $cola"
    } catch {
        Write-Host $_.Exception.Message
    }
}

$target = if (Get-Printer -Name $cola -ErrorAction SilentlyContinue) { $cola }
          elseif (Get-Printer -Name 'ZDesigner GX420d' -ErrorAction SilentlyContinue) { 'ZDesigner GX420d' }
          else { $unc }

Write-Host "Prueba ZPL -> $target"
$zpl = '^XA^FO20,20^A0N,40,40^FDPRUEBA RED OK^FS^XZ'
$tmp = Join-Path $env:TEMP 'zebra_ok.zpl'
Set-Content $tmp $zpl -NoNewline
cmd /c "copy /b `"$tmp`" `"$target`""
Write-Host "copy exit=$LASTEXITCODE"

Get-Printer | Where-Object { $_.Name -match 'GX420' } | Format-Table Name, PortName, PrinterStatus -AutoSize
