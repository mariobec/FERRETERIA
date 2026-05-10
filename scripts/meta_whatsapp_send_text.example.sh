#!/usr/bin/env bash
# Prueba directa contra Graph API (sin pasar por el ERP).
# Documentación: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages
#
# export WHATSAPP_CLOUD_ACCESS_TOKEN="EAAG..."
# export WHATSAPP_CLOUD_PHONE_NUMBER_ID="123456789012345"
# export WHATSAPP_TO="56912345678"   # E.164 sin +
# ./meta_whatsapp_send_text.example.sh "Hola, mensaje de prueba"

set -euo pipefail
TOKEN="${WHATSAPP_CLOUD_ACCESS_TOKEN:-}"
PHONE_ID="${WHATSAPP_CLOUD_PHONE_NUMBER_ID:-}"
TO="${WHATSAPP_TO:-}"
VER="${WHATSAPP_CLOUD_API_VERSION:-v21.0}"
TEXT="${1:-Mensaje de prueba desde curl}"

if [[ -z "$TOKEN" || -z "$PHONE_ID" || -z "$TO" ]]; then
  echo "Defina WHATSAPP_CLOUD_ACCESS_TOKEN, WHATSAPP_CLOUD_PHONE_NUMBER_ID y WHATSAPP_TO" >&2
  exit 1
fi

PAYLOAD="$(python -c "import json,sys; print(json.dumps({'messaging_product':'whatsapp','to':sys.argv[1],'type':'text','text':{'preview_url':False,'body':sys.argv[2]}}))" "$TO" "$TEXT")"

curl -sS -X POST "https://graph.facebook.com/${VER}/${PHONE_ID}/messages" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

echo
