#!/usr/bin/env bash
# Disparar recálculo masivo Customer 360 (misma noche que cron).
# Requiere: BASE_URL, C360_CRON_SECRET (o COBRANZA_DISPATCH_CRON_SECRET en .env del servidor).

set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
SECRET="${C360_CRON_SECRET:-${COBRANZA_DISPATCH_CRON_SECRET:-}}"

if [[ -z "$SECRET" ]]; then
  echo "Defina C360_CRON_SECRET o COBRANZA_DISPATCH_CRON_SECRET" >&2
  exit 1
fi

curl -sS -X POST "${BASE_URL}/api/c360/worker-noche" \
  -H "Authorization: Bearer ${SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"max":400}' | python -m json.tool
