# Ejecutar EN Ferreteria-01 (PC con la Zebra conectada por USB)
# Clic derecho PowerShell -> Ejecutar como administrador
$ErrorActionPreference = 'Stop'
$printerName = 'ZDesigner GX420d'
$shareName = 'ZDesigner GX420d'

Write-Host "=== Habilitar impresora en red: $printerName ==="

# 1) Perfil red privada + descubrimiento
Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue
Set-NetFirewallRule -DisplayGroup 'Compartir archivos e impresoras' -Enabled True -ErrorAction SilentlyContinue

# 2) Sin proteccion por contraseña (invitado puede imprimir)
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name 'everyoneincludesanonymous' -Value 1 -Type DWord
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters' -Name 'RestrictNullSessAccess' -Value 0 -Type DWord
# LimitBlankPasswordUse=0 permite cuentas locales sin clave
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name 'LimitBlankPasswordUse' -Value 0 -Type DWord

# 3) Cuenta Invitado activa (opcional en redes locales)
$user = Get-LocalUser -Name 'Invitado' -ErrorAction SilentlyContinue
if ($user -and -not $user.Enabled) {
    Enable-LocalUser -Name 'Invitado'
    Write-Host 'Cuenta Invitado habilitada'
}

# 4) Compartir impresora
$p = Get-Printer -Name $printerName -ErrorAction Stop
if (-not $p.Shared) {
    Set-Printer -Name $printerName -Shared $true -ShareName $shareName
    Write-Host "Impresora compartida como \\$env:COMPUTERNAME\$shareName"
} else {
    Write-Host "Ya compartida: $($p.ShareName)"
}

# 5) Permisos: Todos pueden imprimir
$prn = Get-WmiObject -Class Win32_Printer -Filter "Name='$printerName'"
$sec = $prn.GetSecurityDescriptor().Descriptor
$everyone = New-Object System.Security.Principal.SecurityIdentifier('S-1-1-0')
$rule = New-Object System.Security.AccessControl.PrinterAccessRule($everyone, 'Print', 'Allow')
$sec.AddAccessRule($rule)
$prn.SetSecurityDescriptor($sec)

Write-Host ''
Write-Host 'LISTO. Desde otro PC use:'
$ips = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' }).IPAddress
foreach ($ip in $ips) { Write-Host "  \\$ip\$shareName" }
Write-Host "  \\$env:COMPUTERNAME\$shareName"
Write-Host ''
Write-Host 'Reinicie Ferreteria-01 si otro PC sigue sin conectar.'
