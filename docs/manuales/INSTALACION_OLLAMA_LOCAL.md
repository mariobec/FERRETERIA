# Instalación Ollama — PC sucursal (LhexIA Operador v0.2)

**Hardware de referencia:** Core i5, 16 GB RAM, SSD 500 GB.  
**Rol:** inferencia local (Qwen 7B Q4) + worker de enriquecimiento de alertas. El ERP sigue en **Render + Neon**.

---

## 1. Red e IP fija

1. En el router, asignar **IP fija** al PC (DHCP reservado) o IP estática en Windows, por ejemplo `192.168.1.50`.
2. Anotar la IP: será `OLLAMA_BASE_URL=http://192.168.1.50:11434` si otro equipo llama a Ollama (opcional).

---

## 2. Instalar Ollama (Windows)

1. Descargar desde [https://ollama.com](https://ollama.com) e instalar.
2. Abrir PowerShell **como administrador** (solo si necesitas exponer la LAN):

```powershell
# Variable de entorno de usuario (reiniciar terminal después)
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
```

3. Reiniciar el servicio Ollama (bandeja del sistema → Quit → volver a abrir Ollama).

4. Descargar el modelo cuantizado (recomendado):

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Alternativa: `ollama pull llama3.1:8b-instruct-q4_K_M`

5. Probar:

```powershell
ollama run qwen2.5:7b-instruct-q4_K_M "Responde OK si escuchas."
curl http://127.0.0.1:11434/api/tags
```

---

## 3. Variables en el PC (worker)

Crear o editar `.env.local` en la carpeta del ERP (clon del repo):

```env
DATABASE_URL=postgresql://...@...neon.tech/neondb?sslmode=require
AGENTE_OLLAMA_ENABLED=1
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
AGENTE_ENRICH_BATCH_SIZE=5
```

| Variable | Descripción |
|----------|-------------|
| `AGENTE_OLLAMA_ENABLED` | `1` en el PC; **`0` en Render** (no inferir en la nube). |
| `OLLAMA_BASE_URL` | URL del daemon Ollama en este PC. |
| `OLLAMA_MODEL` | Tag exacto del modelo (`ollama list`). |
| `AGENTE_ENRICH_BATCH_SIZE` | Máx. alertas por pasada (1–10, default 5). |

---

## 4. Tarea programada (cron Windows)

**Escaneo SQL** (opcional, si no usa Render/cron remoto):

```text
python D:\ruta\sistema_ventas_limpio\scripts\agente_operador_scan.py
```

**Enriquecimiento IA** (cada 10 minutos):

```text
python D:\ruta\sistema_ventas_limpio\scripts\agente_operador_enrich.py
```

Programador de tareas → Acción → `python.exe` con argumentos la ruta del script; directorio de inicio = raíz del repo.

---

## 5. Migración pgvector (Neon, una vez)

Desde PC con `psql` o consola Neon SQL:

```bash
psql "%DATABASE_URL%" -f sql/2026_05_21_lhexia_vector.sql
```

Habilita `vector` y tabla `lhexia_vector_chunks` para Comercial/Guía (indexación de productos en fase siguiente).

---

## 6. Flujo operativo

```text
Render/cron  →  agente_operador_scan.py  →  alertas v0.1 en Neon
PC sucursal  →  agente_operador_enrich.py  →  Ollama enriquece cuerpo (máx. 5–10/lote)
Gerente      →  /admin/control-center  →  lee análisis + reconoce/cierra
```

Si **internet cae**: el POS en Render sigue; el worker reintenta cuando vuelva la red. Las alertas permanecen con texto v0.1 hasta enriquecerse.

---

## 7. Seguridad

- Preferir `OLLAMA_HOST=127.0.0.1:11434` si solo el worker corre en el mismo PC.
- Si usa `0.0.0.0`, restringir en firewall Windows a la subred LAN.
- No exponer el puerto 11434 a Internet sin VPN.

---

## 8. Solución de problemas

| Síntoma | Acción |
|---------|--------|
| Worker `ollama_no_disponible` | Verificar `ollama serve` / app Ollama activa y `AGENTE_OLLAMA_ENABLED=1`. |
| Timeout 30 s | Reducir `AGENTE_ENRICH_BATCH_SIZE` a 3; cerrar apps pesadas. |
| Alertas sin IA | Normal si Ollama caído; texto v0.1 sigue visible. |
| CPU al 100 % | Bajar batch; espaciar cron a 15–30 min. |

---

*LhexIA ERP — www.lhexia.cl · SD-1 Santo Domingo*
