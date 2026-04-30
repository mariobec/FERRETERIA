# QA Checklist - ERP Ferretería (Primera pasada)

## A. Preparación
- [ ] Ejecutar migraciones SQL necesarias.
- [ ] Levantar app con `iniciar_pruebas_windows.bat`.
- [ ] Confirmar login y acceso a `Inicio`.

## B. Productos
- [ ] Alta manual de producto.
- [ ] Carga masiva CSV (`seed_productos_prueba_recepcion.csv`).
- [ ] Verificar columnas nuevas: ubicación y unidades compuestas.
- [ ] Confirmar búsquedas por nombre/código.

## C. Punto de venta + Caja
- [ ] Agregar producto al POS y emitir vale.
- [ ] Validar cliente normal y cliente final.
- [ ] Cobrar en caja (efectivo/débito/crédito).
- [ ] Verificar estado de vale y actualización de stock.

## D. Recepción de mercadería
- [ ] Crear recepción nueva (Factura/Guía).
- [ ] Registrar al menos 2 líneas (con costo unitario).
- [ ] Confirmar alerta por subida de costo.
- [ ] Finalizar recepción y revisar etiquetas.
- [ ] Probar `Modo Tablet` (`/recepciones/tablet`).

## E. Kardex e inventario
- [ ] Ver movimiento ENTRADA por recepción.
- [ ] Ver movimiento SALIDA por ventas/cobros.
- [ ] Filtrar por producto y por tipo.

## F. Créditos y caja
- [ ] Registrar abono crédito y reimpresión ticket.
- [ ] Registrar movimiento de caja con responsable.
- [ ] Cierre de caja con detalle de ventas.

## G. BI y reportes
- [ ] Abrir `/bi` y validar KPIs + gráficos.
- [ ] Exportar CSV desde BI.
- [ ] Abrir `/ia_abastecimiento` y validar sugerencias.

## H. Criterio de salida QA (Go/No-Go)
- [ ] Sin errores 500 en rutas principales.
- [ ] Sin fallas de integridad en BD durante flujos críticos.
- [ ] Usuario cliente puede ejecutar flujo completo:
  - producto -> recepción -> venta -> cobro -> kardex -> BI.
