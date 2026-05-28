# Liz + Ollama en producción (lhexia.cl)

Render **no** puede ejecutar Ollama (modelo en RAM/GPU de la PC). El diseño es:

| Componente | Dónde corre |
|------------|-------------|
| ERP + vitrina | Render (`www.lhexia.cl`) |
| Ollama | PC Ferretería Santo Domingo (siempre encendida en horario tienda) |
| Enlace | Túnel HTTPS (Cloudflare) o red privada (Tailscale) |

El **Operador** (`agente_operador_enrich`) sigue en la PC con `AGENTE_OLLAMA_ENABLED=1` local.  
**Liz** en la web usa variables `VITRINA_OLLAMA_*` sin activar Ollama del Operador en Render.

---

## 1. PC sucursal — Ollama

```powershell
cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_sd.ps1
```

Dejar la app **Ollama** abierta. Probar:

```powershell
python scripts\verificar_operador_ollama.py
python scripts\verificar_vitrina_ollama.py
```

---

## 2. Túnel HTTPS hacia Render (Cloudflare)

### Prueba rápida (URL cambia al reiniciar)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\iniciar_ollama_tunnel_vitrina.ps1
```

Copiar la URL `https://….trycloudflare.com` a **Render** → Environment:

| Variable | Valor |
|----------|--------|
| `VITRINA_OLLAMA_ENABLED` | `1` |
| `VITRINA_OLLAMA_BASE_URL` | `https://….trycloudflare.com` (sin `/` final) |
| `VITRINA_OLLAMA_MODEL` | `qwen2.5:7b-instruct-q4_K_M` |
| `VITRINA_OLLAMA_TIMEOUT_SEC` | `120` |

**Manual Deploy** → verificar `https://www.lhexia.cl/healthz` → `liz_ollama.disponible: true`.

Mantener la ventana del túnel abierta.

### Producción estable

Túnel Cloudflare nombrado (subdominio fijo, p. ej. `ollama-sd.lhexia.cl`) o **Tailscale Funnel**: `tailscale funnel 11434`.

---

## 3. Seguridad

No exponer Ollama sin túnel autenticado. Opcional: `VITRINA_OLLAMA_API_KEY` como Bearer en el proxy.

---

## 4. Si cae el túnel

Liz sigue con reglas + catálogo; `ia_local_disponible: false` en el chat.
