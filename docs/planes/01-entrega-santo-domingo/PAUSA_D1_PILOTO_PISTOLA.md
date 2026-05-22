# Pausa → D1 Piloto pistola (lunes)

**D0 cerrado:** maestro ~4.913 SKU en Neon (`productos_homologados_sd.csv`).  
**Recepciones:** RCV importado, UI Pareto + archivar 2025 + folio en producción.

---

## Antes de salir al piso (5 min)

1. [www.lhexia.cl/productos](https://www.lhexia.cl/productos) — confirmar catálogo visible.
2. [www.lhexia.cl/recepciones](https://www.lhexia.cl/recepciones) — filtro 2026 → **Pareto (monto)** (cola D2).
3. Pistola en modo **teclado (HID)**; probar en enrolamiento.

---

## D1 — Enrolamiento TIENDA

**Ruta:** `/inventario/enrolamiento` → almacén **TIENDA** → **Nueva sesión**.

| Paso | Acción |
|------|--------|
| 1 | Lista 50–80 SKU alta rotación (anotar `codigo_chilemat`) |
| 2 | Escanear **EAN del envase** (no código portal Chilemat) |
| 3 | Caso A: reconocido → +1 conteo |
| 4 | Caso B: buscar nombre o Chilemat → vincular → cantidad 1 (piloto) |
| 5 | Verificar que `codigo_barra` deja de ser `PEND-*` |

**Meta D1:** operador domina Caso B; si >30 % no encuentra → completar nombres en matriz.

---

## Comandos de respaldo (PC control)

```powershell
cd "d:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"

# RCV mes nuevo (dedup automático)
python scripts/importar_rcv_sii.py --neon -i "datos_rcv\RCV_COMPRA_REGISTRO_....csv" --dry-run
python scripts/importar_rcv_sii.py --neon -i "datos_rcv\RCV_COMPRA_REGISTRO_....csv"

# Documentación completa RCV/PDF/Render
# → docs/planes/01-entrega-santo-domingo/IMPORTAR_RCV_SII.md
```

---

## Después de D1 (sin apurar)

- **D2:** Pareto recepciones — PDF manual + líneas (IA cuando `OPENAI_API_KEY` en Render).
- Propuesta comercial IA aprobada ($305.000 incl. recarga API) → activar en Render cuando firmen.
