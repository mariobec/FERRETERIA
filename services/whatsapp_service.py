"""Fase 2 — salida WhatsApp Cloud (siempre post-commit desde flujos de dominio)."""


def enviar_texto_cloud(destino, texto):
    import app as m

    return m._whatsapp_cloud_send_text(destino, texto)
