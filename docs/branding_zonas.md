# Regla de Branding por Zonas

Esta guia define que marca usar segun el area del sistema para evitar mezclas en cambios futuros.

## Marca comercial vigente

- **Nombre**: LhexIA IA ERP
- **Tagline oficial**: "Inteligencia operativa para retail y ferreterias."
- **Paleta**: naranja corporativo `#F37021`, fondo oscuro `#0F1419`/`#0B0F14`, blanco metalico
- **Logo principal (transparente)**: `static/img/lhexia_logo_transparent.png`
- **Logo con fondo oscuro (respaldo legacy)**: `static/img/sintrel-erp-logo-dark-bg.png` (solo si se necesita fondo embebido)
- **Logo vectorial (editable, respaldo)**: `static/img/sintrel-ia-erp-logo.svg` (wordmark actualizado a LhexIA)
- **Marca anterior**: Cimentia (deprecada por colision con un ERP existente en Espana). No volver a usar.

## 1) Landing publica (marketing)
- **Marca**: LhexIA IA ERP
- **Objetivo**: captacion comercial y presentacion del producto
- **Incluye**: `templates/index.html` y estilos asociados en `static/css/style_index.css`
- **No usar**: nombre o logos de "Ferreteria Santo Domingo"

## 2) ERP Demo operativo
- **Marca**: Ferreteria Santo Domingo
- **Objetivo**: demo funcional del ERP en operacion realista (cliente piloto)
- **Incluye**: modulos internos, tickets, caja, ventas, compras, stock, reportes demo
- **Ejemplos**: `templates/catalogo_publico.html`, `templates/consulta_stock_publica.html`
- **Nota**: el sidebar interno y el topbar muestran "LhexIA IA ERP" (producto) + nombre del cliente demo (`empresa_cfg.nombre_comercial`).

## 3) LhexIA Interno (uso interno)
- **Marca**: LhexIA IA ERP
- **Objetivo**: herramientas internas comerciales/operativas (CRM mini, leads landing, backoffice)
- **Incluye**: paneles internos restringidos (por ejemplo `comercial_leads.html`)
- **Acceso**: limitado por correo (ver `_usuario_autorizado_lhexia_interno` en `app.py`).
- **Nota**: no mezclar con la narrativa del ERP demo al cliente final

## Checklist rapido antes de cerrar cambios UI
1. Confirmar zona (Landing / ERP Demo / LhexIA Interno).
2. Revisar titulos, textos, logos y fondos.
3. Verificar que el branding coincida con la zona.
4. Validar en movil y escritorio solo la zona afectada.
5. Evitar marcas legacy ("Cimentia", "SINTREL") en textos nuevos; usar "LhexIA IA ERP".
