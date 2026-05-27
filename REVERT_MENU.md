# Revertir menú ERP

## Fase 2 (8 grupos + hub alineado) — actual

```powershell
cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
git checkout checkpoint/menu-pre-fase2-2026-05-27 -- app.py templates/base.html templates/partials/mobile_erp_shell_body.html tests/test_routes_criticas.py
```

## Fase 1 (6 grupos primera reestructuración)

Tag: `checkpoint/menu-pre-restruct-2026-05-27` (commit ee2d4fa)

```powershell
git checkout checkpoint/menu-pre-restruct-2026-05-27 -- app.py templates/base.html templates/partials/mobile_erp_shell_body.html templates/revision_precios.html tests/test_routes_criticas.py
```

Reiniciar el servidor Flask después de cualquier revert.
