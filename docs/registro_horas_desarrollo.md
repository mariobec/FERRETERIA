# Registro de horas de desarrollo (proyecto ERP Lhexa)

## Propósito

Llevar un **libro de horas** del proyecto: trabajo humano, sesiones asistidas por IA (Cursor) y tareas mixtas. Sirve para planificación, costeo interno y transparencia frente a stakeholders.

## Reglas

1. **Una fila por bloque de trabajo** (idealmente 0,25 h o más; evitar micro-registros).
2. **Horas**: número decimal con punto (ej. `2.5`). Si aún no está medido, dejar vacío en el CSV o `—` en la tabla de abajo.
3. **Rol** en CSV: `desarrollador` | `ia_cursor` | `mixto` (revisión humana + generación/edición asistida).
4. **Referencia**: commit, PR, ticket o ruta de archivo relevante.
5. **La IA no tiene registro automático de duración** de chats pasados: las horas de asistencia deben anotarlas quien dirige la sesión (reloj, facturación interna o estimación honesta).

## Cómo actualizar

- Editar `docs/registro_horas_desarrollo.csv` (Excel, LibreOffice, VS Code).
- Opcional: reflejar aquí la misma información en la tabla resumen (o solo el CSV).

### Suma rápida del CSV (cuando la columna `horas` tenga números)

Desde la raíz del repo, en PowerShell o bash:

```bash
python -c "import csv; p='docs/registro_horas_desarrollo.csv'; t=sum(float(r['horas']) for r in csv.DictReader(open(p,encoding='utf-8')) if r.get('horas','').strip()); print(t)"
```

## Resumen por periodo

| Periodo   | Horas registradas (suma CSV) | Notas                          |
|-----------|------------------------------|--------------------------------|
| (editar)  | —                            | Completar al cerrar cada mes   |

## Tabla resumen (espejo manual; la fuente de verdad es el CSV)

| Fecha      | Rol        | Horas | Tema breve                         | Referencia        |
|------------|------------|-------|------------------------------------|-------------------|
| 2026-05-13 | mixto      |       | Logo sitio, branding               | `799874b`         |
| 2026-05-13 | mixto      |       | Sitio público, cierre de caja      | `6348ffa`         |
| 2026-05-13 | mixto      |       | Analítica web, SEO                 | `0097ccf`         |
| 2026-05-13 | mixto      |       | Observabilidad comercial, SEO      | `7c088f3`         |
| 2026-05-14 | mixto      |       | Customer 360, experiencia pública  | `0111306`         |
| 2026-05-14 | ia_cursor  |       | Registro de horas (este documento) | `docs/registro_*` |

---

*Última actualización de plantilla: 2026-05-14.*
