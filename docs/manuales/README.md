# Manuales y capacitación — LhexIA ERP

Documentación para **operadores de piso** (cajera, vendedor, bodega, administrador).  
La versión **en vivo dentro del ERP** está en **Menú → Ayuda** (`/ayuda`).

## Documento principal

| Documento | Descripción |
|-----------|-------------|
| **[MANUAL_GENERAL_ERP.md](MANUAL_GENERAL_ERP.md)** | **Manual general consolidado** — entregar al equipo o convertir a PDF |

## Índice de documentos

| Documento | Audiencia | Duración | Estado |
|-----------|-----------|----------|--------|
| [PLAN_CAPACITACION.md](PLAN_CAPACITACION.md) | Coordinador / dueño | — | ✅ Plan base |
| [CURSO_01_PRODUCTOS_RECEPCIONES.md](CURSO_01_PRODUCTOS_RECEPCIONES.md) | Bodega + admin | 60–90 min | ✅ Borrador listo |
| [CURSO_02_POS_CAJA.md](CURSO_02_POS_CAJA.md) | Vendedor + cajera | 60 min | 🟡 Esqueleto |
| [CURSO_03_KARDEX_BI.md](CURSO_03_KARDEX_BI.md) | Supervisor | 45 min | ⬜ Pendiente |
| [CURSO_04_ADMIN_SEGURIDAD.md](CURSO_04_ADMIN_SEGURIDAD.md) | Administrador | 30 min | ⬜ Pendiente |

## Manuales de referencia (existentes)

| Archivo | Ubicación | Uso |
|---------|-----------|-----|
| Manual operativo por módulos | `MANUAL_OPERATIVO_MODULOS.md` (raíz) | Fuente maestra FAQ |
| Enrolamiento inventario | `MANUALES DE OPERACIÓN/MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` | Pistola + códigos |
| Carga masiva productos | `MANUALES DE OPERACIÓN/GUIA_CARGA_5000_PRODUCTOS.md` | Go-live inventario |
| Instalación cliente | `MANUALES DE OPERACIÓN/GUIA_INSTALACION_CLIENTE.md` | IT / despliegue |

## Dónde está la ayuda en el ERP

1. **Centro de ayuda** — `/ayuda` (sidebar, hub, móvil)
2. **Enlaces contextuales** — botón `?` en POS, caja, enrolamiento, cierre
3. **Tooltips** — icono `?` en KPIs de gerencia, BI, créditos
4. **LhexIA Academy** — hub `/academy` + Mentor contextual en POS/caja (doc técnica: [`../planes/02-producto-lhexia/LHEXIA_ACADEMY_MENTOR.md`](../planes/02-producto-lhexia/LHEXIA_ACADEMY_MENTOR.md))

## Ciclo operativo que debe dominar el equipo

```
Producto → Recepción → POS (vale) → Caja (cobro) → Kardex → Reporte
```

## Próximos pasos (Gemini / equipo)

Ver [BRIEF_GEMINI_CAPACITACION.md](BRIEF_GEMINI_CAPACITACION.md) para generar videos, PDFs o slides a partir de estos borradores.
