#!/usr/bin/env bash
# Ejemplo: disparar envío automático de cobranza vía el ERP (Meta Cloud API configurada en el servidor).
# Copie a cobranza_dispatch_cron.sh, rellene BASE_URL y SECRET, chmod +x y programe en crontab.
#
# Uso:
#   export BASE_URL="https://su-dominio.com"
#   export COBRANZA_DISPATCH_CRON_SECRET="su_secreto_largo"
#   ./cobranza_dispatch_cron.example.sh
#
# Primero pruebe con dry_run (no envía, solo lista candidatos dentro del tope max):

set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
SECRET="${COBRANZA_DISPATCH_CRON_SECRET:-}"

if [[ -z "$SECRET" ]]; then
  echo "Defina COBRANZA_DISPATCH_CRON_SECRET" >&2
  exit 1
fi

curl -sS -X POST "${BASE_URL}/api/creditos/cobranza/dispatch-cloud" \
  -H "Authorization: Bearer ${SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"dry_run":true,"max":20,"dias":7}' | python -m json.tool

echo
echo "--- Si el dry_run se ve bien, ejecute de nuevo con dry_run:false ---"
# curl -sS -X POST "${BASE_URL}/api/creditos/cobranza/dispatch-cloud" \
#   -H "Authorization: Bearer ${SECRET}" \
#   -H "Content-Type: application/json" \
#   -d '{"dry_run":false,"max":20,"dias":7}' | python -m json.tool
