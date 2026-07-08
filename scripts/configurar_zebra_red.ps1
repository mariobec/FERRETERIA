$ErrorActionPreference = 'Continue'
$share = '\\192.168.1.10\ZDesigner GX420d'
$netName = 'ZDesigner GX420d Red'
$log = Join-Path $PSScriptRoot '_zebra_red_setup.log'

function Log($m) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $m"
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host $m
}

'' | Set-Content -Path $log -Encoding UTF8
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log "Admin=$isAdmin PC=$env:COMPUTERNAME"

# Quitar cola USB local erronea si apunta a puerto fantasma (opcional, solo si no es la red)
$localUsb = Get-Printer -Name 'ZDesigner GX420d' -ErrorAction SilentlyContinue
if ($localUsb -and $localUsb.PortName -like 'USB*') {
    Log "AVISO: cola local USB $($localUsb.PortName) status=$($localUsb.PrinterStatus) - la Zebra real esta en red"
}

Log '=== Metodo 1: puerto UNC + driver local ==='
try {
    if (-not (Get-PrinterPort -Name $share -ErrorAction SilentlyContinue)) {
        Add-PrinterPort -Name $share -ErrorAction Stop
        Log "Puerto creado: $share"
    } else {
        Log 'Puerto ya existe'
    }
} catch {
    Log "Puerto ERROR: $($_.Exception.Message)"
}

try {
    if (-not (Get-Printer -Name $netName -ErrorAction SilentlyContinue)) {
        Add-Printer -Name $netName -DriverName 'ZDesigner GX420d' -PortName $share -ErrorAction Stop
        Log "Impresora creada: $netName"
    } else {
        Log "Impresora ya existe: $netName"
    }
} catch {
    Log "Add-Printer ERROR: $($_.Exception.Message)"
}

Log '=== Metodo 2: rundll32 /in (cola de red Windows) ==='
$p = Start-Process -FilePath "$env:SystemRoot\System32\rundll32.exe" `
    -ArgumentList "printui.dll,PrintUIEntry /in /n`"$share`"" `
    -Wait -PassThru -NoNewWindow
Log "rundll32 /in exit=$($p.ExitCode)"
Start-Sleep 4

Log '=== Metodo 3: copy directo a cola compartida ==='
$zpl = "^XA^FO20,20^A0N,40,40^FDPRUEBA RED 192.168.1.10^FS^XZ`r`n"
$tmp = Join-Path $env:TEMP 'zebra_red_direct.zpl'
[System.IO.File]::WriteAllBytes($tmp, [Text.Encoding]::ASCII.GetBytes($zpl))
cmd /c "copy /b `"$tmp`" `"$share`""
Log "copy UNC exit=$LASTEXITCODE"

Log '=== Colas finales ==='
Get-Printer | Where-Object { $_.Name -match 'GX420|Zebra' -or $_.PortName -match '192\.168' } | ForEach-Object {
    Log ("  $($_.Name) | $($_.PortName) | $($_.PrinterStatus)")
}

# Poner en linea si existe cola red
foreach ($n in @($netName, 'ZDesigner GX420d')) {
    $w = Get-WmiObject Win32_Printer -Filter "Name='$n'" -ErrorAction SilentlyContinue
    if ($w -and $w.WorkOffline) {
        $w.WorkOffline = $false
        $w.Put() | Out-Null
        Log "Online: $n"
    }
}

Log 'DONE'
