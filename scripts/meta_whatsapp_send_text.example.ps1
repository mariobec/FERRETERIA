# Prueba directa contra Graph API (Meta). Requiere token y Phone Number ID en el entorno.
param(
    [string]$Texto = 'Mensaje de prueba desde PowerShell'
)

$ErrorActionPreference = 'Stop'
$token = $env:WHATSAPP_CLOUD_ACCESS_TOKEN
$phoneId = $env:WHATSAPP_CLOUD_PHONE_NUMBER_ID
$to = $env:WHATSAPP_TO
$ver = if ($env:WHATSAPP_CLOUD_API_VERSION) { $env:WHATSAPP_CLOUD_API_VERSION } else { 'v21.0' }

if (-not $token -or -not $phoneId -or -not $to) {
    Write-Error 'Defina WHATSAPP_CLOUD_ACCESS_TOKEN, WHATSAPP_CLOUD_PHONE_NUMBER_ID y WHATSAPP_TO (E.164 sin +).'
}

$uri = "https://graph.facebook.com/$ver/$phoneId/messages"
$bodyObj = @{
    messaging_product = 'whatsapp'
    to                = $to
    type              = 'text'
    text              = @{ preview_url = $false; body = $Texto }
}
$body = $bodyObj | ConvertTo-Json -Depth 5
$headers = @{
    Authorization  = "Bearer $token"
    'Content-Type' = 'application/json'
}

Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body | ConvertTo-Json -Depth 6
