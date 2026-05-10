# Ejemplo PowerShell: probar dispatch de cobranza (dry_run).
# Requiere: BASE_URL, COBRANZA_DISPATCH_CRON_SECRET en el entorno o edítelos abajo.

$ErrorActionPreference = 'Stop'
$BaseUrl = if ($env:BASE_URL) { $env:BASE_URL } else { 'http://127.0.0.1:5000' }
$Secret = $env:COBRANZA_DISPATCH_CRON_SECRET
if (-not $Secret) {
    Write-Error 'Defina la variable de entorno COBRANZA_DISPATCH_CRON_SECRET'
}

$uri = "$BaseUrl/api/creditos/cobranza/dispatch-cloud"
$body = @{ dry_run = $true; max = 20; dias = 7 } | ConvertTo-Json
$headers = @{
    Authorization = "Bearer $Secret"
    'Content-Type' = 'application/json'
}

Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body | ConvertTo-Json -Depth 8
