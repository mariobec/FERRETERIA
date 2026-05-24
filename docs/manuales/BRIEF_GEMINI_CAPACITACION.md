# Brief para Gemini — Materiales de capacitación LhexIA ERP

Usa este documento como **prompt maestro** para generar videos, PDFs, presentaciones o guías ilustradas.

---

## Contexto del producto

- **Nombre:** LhexIA ERP — sistema para ferreterías y retail especializado (Chile).
- **Stack:** aplicación web Flask, pantallas en español, Bootstrap.
- **Usuarios:** cajera, vendedor mostrador, bodeguero, administrador, dueño.
- **Go-live referencia:** ferretería Santo Domingo (inventario + pistola + POS + caja).

## Fuentes oficiales (leer antes de generar)

1. `MANUAL_OPERATIVO_MODULOS.md` — flujo completo por módulo
2. `docs/manuales/PLAN_CAPACITACION.md` — 4 sesiones
3. `docs/manuales/CURSO_01_PRODUCTOS_RECEPCIONES.md` — curso 1 detallado
4. `docs/manuales/CURSO_02_POS_CAJA.md` — curso 2 (completar)
5. `MANUALES DE OPERACIÓN/MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` — pistola
6. Centro de ayuda en app: `/ayuda` (pestañas por rol + capacitación)

## Qué generar (prioridad)

### Prioridad 1 — PDF operador (8–12 páginas c/u)

| PDF | Basado en | Incluir |
|-----|-----------|---------|
| Guía rápida cajera | `/ayuda` pestaña Cajera | Abrir/cerrar caja, cobrar, vuelto, errores |
| Guía rápida vendedor | `/ayuda` pestaña Vendedor | POS, descuentos, anular vale |
| Guía enrolamiento pistola | Manual enrolamiento | Casos A/B/C, recepción sin duplicar stock |

### Prioridad 2 — Presentaciones (Google Slides / PPTX)

- 1 deck por sesión del `PLAN_CAPACITACION.md`
- Máximo 15 slides por sesión
- 1 slide = 1 acción concreta + captura de pantalla (placeholder si no hay imagen)

### Prioridad 3 — Videos cortos (2–4 min c/u)

- "Cómo emitir un vale en 60 segundos"
- "Cómo cobrar en caja"
- "Enrolamiento: primer escaneo"
- "Cierre de caja sin sorpresas"

## Reglas de estilo

1. **Idioma:** español chileno (usted/tú según ferretería — preferir **tú** en piso).
2. **Sin tecnicismos:** no decir "endpoint", "API", "JSON".
3. **Pasos numerados** siempre que haya procedimiento.
4. **Tablas de errores frecuentes** al final de cada guía.
5. **Checklist** al cierre de cada módulo.
6. **Marcar permisos:** "Si no ves este menú, pide permiso a administrador".

## Ciclo operativo (diagrama sugerido)

```
Mañana: Abrir caja → (Recepciones si hay camión) → POS emite vales
Tarde: Caja cobra vales → Bodega despacha si aplica
Noche: Kardex spot check → Cerrar caja → Cerrar sesión
```

## Pantallas clave para capturas

| Módulo | Ruta ERP |
|--------|----------|
| POS | `/punto_venta` |
| Caja | `/caja/pendientes` |
| Cerrar caja | `/cerrar_caja` |
| Productos | `/productos` |
| Recepciones | `/recepciones` |
| Enrolamiento | `/inventario/enrolamiento` |
| Kardex | `/kardex` |
| Ayuda | `/ayuda` |

## Formato de entrega esperado

Por cada material:

```
docs/manuales/salida/
  pdf/
    guia_cajera_v1.pdf
    guia_vendedor_v1.pdf
  slides/
    sesion_01_productos.pptx
  guiones/
    video_pos_60s.md
```

## Prompt sugerido (copiar/pegar en Gemini)

```
Eres instructor de sistemas para ferreterías en Chile. 
Genera [TIPO: PDF / slides / guión video] sobre [TEMA] usando exclusivamente 
el contenido de los archivos adjuntos del ERP LhexIA.

Requisitos:
- Pasos numerados, lenguaje simple
- Tabla de errores frecuentes
- Checklist final
- Referencia a /ayuda#[ancla] cuando aplique
- No inventes funciones que no estén en el manual

Archivos adjuntos: [listar]
```

## Lo que NO debe incluir Gemini

- Configuración de servidor, Docker, PostgreSQL
- Planes internos de desarrollo (`docs/planes/`)
- Marketing público (landing pages)
- Certificación SII / DTE (salvo módulo facturación explícito)

## Validación

Todo material generado debe ser revisado por el equipo LhexIA contra:

1. Pantalla real en staging
2. `tests/test_routes.py` (rutas existentes)
3. Permisos RBAC del rol objetivo

---

*Documento creado para coordinar capacitación humano + IA. Actualizar versión al cambiar `/ayuda`.*
