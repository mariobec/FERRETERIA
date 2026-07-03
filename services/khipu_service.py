"""Khipu — pasarela de transferencia bancaria para vitrina e-commerce.

API v3: https://payment-api.khipu.com
Autenticación: header x-api-key

Flujo:
  1. crear_pago()     → retorna payment_url para redirect
  2. usuario paga en banco
  3. Khipu redirige a return_url con ?notification_token=xxx
  4. verificar_pago() → confirma estado "done"
"""
from __future__ import annotations

import os
from typing import Any

import requests


# ── config ─────────────────────────────────────────────────────────────────

_KHIPU_BASE = "https://payment-api.khipu.com"
_KHIPU_TIMEOUT = 20


def khipu_habilitado() -> bool:
    v = (os.getenv("KHIPU_ENABLED") or "0").strip().lower()
    if v not in ("1", "true", "si", "yes", "on"):
        return False
    return bool((os.getenv("KHIPU_API_KEY") or "").strip())


def _api_key() -> str:
    return (os.getenv("KHIPU_API_KEY") or "").strip()


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "x-api-key": _api_key(),
    }


# ── crear pago ──────────────────────────────────────────────────────────────

def crear_pago(
    *,
    subject: str,
    amount: int,
    return_url: str,
    cancel_url: str,
    notify_url: str | None = None,
    custom: str = "",
    payer_name: str = "",
) -> dict[str, Any]:
    """Crea una orden de pago Khipu.

    Returns dict con: ok, payment_id, payment_url, error (si falla).
    """
    if not khipu_habilitado():
        return {"ok": False, "error": "khipu_disabled"}
    if amount < 1:
        return {"ok": False, "error": "monto_invalido", "mensaje": "Monto mínimo Khipu: $1."}

    payload: dict[str, Any] = {
        "subject": str(subject)[:255],
        "currency": "CLP",
        "amount": int(amount),
        "return_url": return_url,
        "cancel_url": cancel_url,
    }
    if notify_url:
        payload["notify_url"] = notify_url
    if custom:
        payload["custom"] = str(custom)[:255]
    if payer_name:
        payload["payer_name"] = str(payer_name)[:255]

    try:
        res = requests.post(
            f"{_KHIPU_BASE}/v3/payments",
            json=payload,
            headers=_headers(),
            timeout=_KHIPU_TIMEOUT,
        )
        data: dict = res.json() if res.content else {}
        if res.status_code >= 400:
            return {
                "ok": False,
                "error": "khipu_create_failed",
                "mensaje": (data.get("message") or data.get("error") or res.text or "Error Khipu")[:200],
                "status": res.status_code,
            }
        payment_url = (data.get("payment_url") or data.get("simplified_transfer_url") or "").strip()
        payment_id = (data.get("payment_id") or "").strip()
        if not payment_url or not payment_id:
            return {"ok": False, "error": "khipu_sin_url", "mensaje": "Respuesta Khipu incompleta."}
        return {
            "ok": True,
            "payment_id": payment_id,
            "payment_url": payment_url,
            "simplified_transfer_url": data.get("simplified_transfer_url", ""),
            "app_url": data.get("app_url", ""),
        }
    except requests.RequestException as ex:
        return {"ok": False, "error": "khipu_red", "mensaje": str(ex)[:200]}


# ── verificar pago ──────────────────────────────────────────────────────────

def verificar_pago(payment_id: str) -> dict[str, Any]:
    """Consulta el estado de un pago Khipu.

    Returns dict con: ok, approved (bool), status, payment_id.
    """
    if not khipu_habilitado():
        return {"ok": False, "error": "khipu_disabled"}
    pid = (payment_id or "").strip()
    if not pid:
        return {"ok": False, "error": "payment_id_vacio"}

    try:
        res = requests.get(
            f"{_KHIPU_BASE}/v3/payments/{pid}",
            headers=_headers(),
            timeout=_KHIPU_TIMEOUT,
        )
        data: dict = res.json() if res.content else {}
        if res.status_code >= 400:
            return {
                "ok": False,
                "error": "khipu_verify_failed",
                "mensaje": (data.get("message") or res.text or "Error verificación Khipu")[:200],
            }
        status = (data.get("status") or "").strip().lower()
        approved = status == "done"
        return {
            "ok": True,
            "approved": approved,
            "status": status,
            "payment_id": pid,
            "amount": data.get("amount"),
            "subject": data.get("subject"),
            "custom": data.get("custom", ""),
            "raw": data,
        }
    except requests.RequestException as ex:
        return {"ok": False, "error": "khipu_red", "mensaje": str(ex)[:200]}
