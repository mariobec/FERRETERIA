# Roadmap — Observabilidad Comercial, Producto y SEO (LhexIA 2026–2030)

**Versión:** 1.0 · **Fecha referencia:** mayo 2026  
**Stack actual del ERP:** Python / Flask / SQLAlchemy / Jinja2 / Bootstrap / PostgreSQL  
**Estado actual:** Ya existe una base funcional de observabilidad con:

- `gerencia/analitica-web` para sesiones, pageviews, CTA, conversiones y tiempo activo.
- `gerencia/seo-rankings` para snapshots SEO técnicos, keywords y salud orgánica.
- Tracking first-party propio, snapshots locales, retención/purga de telemetría y aislamiento de APIs externas.

**Objetivo 2026–2030:** Convertir LhexIA en una plataforma con observabilidad premium de negocio, marketing, producto y crecimiento, donde la gerencia pueda responder en minutos:

1. qué canal trae tráfico de calidad,  
2. qué contenido convierte,  
3. qué señales anteceden una oportunidad comercial,  
4. qué está dañando posicionamiento, margen o adopción,  
5. y qué acción conviene ejecutar ahora.

---

## Principios no negociables

1. **First-party por defecto.** La data crítica debe vivir en LhexIA y no depender solo de terceros.
2. **Dashboards de baja latencia.** La UI de gerencia consume snapshots y tablas locales; no llama APIs externas en tiempo real.
3. **Privacidad y minimización.** Retención, agregación, purga, validación de origen y separación entre dato crudo y dato ejecutivo.
4. **Observabilidad accionable.** No solo mostrar métricas; priorizar alertas, oportunidades y decisiones sugeridas.
5. **Atribución conectada al negocio.** Visita, lead, WhatsApp, venta, cobranza y margen deben poder conversar.
6. **Arquitectura evolutiva.** Empezar en el monolito Flask, extraer workers y servicios solo cuando el volumen lo justifique.

---

## Norte estratégico

### Horizonte 2026

Consolidar una **torre de control first-party** para marketing y SEO con trazabilidad suficiente para detectar:

- qué páginas atraen tráfico de calidad,
- qué CTA convierten mejor,
- qué keywords sostienen crecimiento,
- y qué fricción impide transformar visitas en diagnósticos y oportunidades.

### Horizonte 2027

Unir marketing, operación comercial y CRM ligero para pasar de “medición” a **atribución comercial real**:

- origen del lead,
- calidad del lead,
- velocidad de respuesta,
- y conversión a oportunidad o venta.

### Horizonte 2028

Entrar en **observabilidad predictiva**, donde el sistema detecta anomalías, caídas de conversión, fatiga de contenido, fuga de margen o deterioro SEO antes de que el equipo lo note tarde.

### Horizonte 2029–2030

Convertir LhexIA en una capa de **Growth Intelligence** para retail especializado:

- SEO clásico + GEO / AI search readiness,
- scoring de intención comercial,
- experimentación controlada,
- y automatizaciones con auditoría completa.

---

## Fase 1 — 2026 H1/H2: consolidación de la base propia

**Objetivo:** robustecer lo ya implementado y pasar de “módulo nuevo” a “sistema confiable de gerencia”.

### Entregables

- Endurecer calidad de datos en analítica web:
  - deduplicación básica de eventos,
  - whitelist/normalización de eventos y CTAs,
  - etiquetado consistente por página, cluster y objetivo.
- Completar snapshots SEO operativos:
  - histórico diario,
  - más checks técnicos,
  - score por plantilla / cluster / landing.
- Integrar una vista ejecutiva mínima de embudo:
  - visita,
  - CTA,
  - lead,
  - conversación iniciada por WhatsApp.
- Programar tareas periódicas:
  - snapshot SEO diario,
  - consolidación y purga de telemetría,
  - futura sincronización desacoplada con Search Console.
- Instrumentar alertas internas:
  - caída brusca de conversiones,
  - página crítica con score SEO bajo,
  - CTA importante sin interacción en ventana definida.

### KPI objetivo

- > 95 % de eventos válidos sobre el total recibido.
- 100 % de páginas estratégicas dentro del snapshot diario.
- Latencia de dashboard de gerencia estable y sin dependencia externa.

### Resultado esperado

LhexIA queda con una base seria para confiar en la data y usarla en decisiones semanales de marketing y crecimiento.

---

## Fase 2 — 2027: atribución comercial y revenue observability

**Objetivo:** conectar adquisición digital con negocio real.

### Entregables

- Modelo unificado de embudo:
  - `visitante -> sesión -> lead -> oportunidad -> venta -> cobranza`
- Relación entre origen de tráfico y resultado comercial:
  - canal,
  - campaña,
  - landing,
  - keyword,
  - vendedor asignado,
  - tiempo a primer contacto.
- Score de lead operativo:
  - urgencia,
  - rubro,
  - tamaño,
  - engagement,
  - fuente de origen.
- Dashboard de gerencia comercial:
  - CAC aproximado,
  - tasa lead -> reunión,
  - lead -> oportunidad,
  - oportunidad -> venta.
- Trazabilidad de WhatsApp:
  - clic,
  - conversación iniciada,
  - resultado comercial posterior.

### KPI objetivo

- Atribución clara para al menos 80 % de leads entrantes.
- Tiempo de respuesta comercial visible por canal y responsable.
- Ranking de landings por calidad de lead, no solo por volumen.

### Resultado esperado

La gerencia deja de medir “visitas bonitas” y empieza a medir qué contenido y qué canal traen negocio de verdad.

---

## Fase 3 — 2028: observabilidad predictiva y alertas inteligentes

**Objetivo:** pasar de reporting histórico a detección anticipada.

### Entregables

- Motor de anomalías simples:
  - caída anormal de sesiones orgánicas,
  - baja de CTR interno en CTA clave,
  - deterioro de conversión por landing,
  - pérdida de posiciones en keywords prioritarias.
- Alertas priorizadas para gerencia:
  - “subió tráfico pero bajó intención”,
  - “aumentó CTA pero no aumentó lead”,
  - “mejoró SEO pero no mejoró resultado comercial”.
- Health score por cluster:
  - money pages,
  - comparativas,
  - artículos,
  - páginas institucionales.
- Primer modelo de propensión:
  - qué sesiones tienen mayor probabilidad de terminar en lead,
  - qué leads tienen mayor probabilidad de avanzar a oportunidad.

### KPI objetivo

- Detectar variaciones relevantes antes del cierre semanal.
- Reducir tiempo de diagnóstico de crecimiento de horas a minutos.
- Priorizar automáticamente páginas y campañas que requieren intervención.

### Resultado esperado

LhexIA opera con una “mesa de control” predictiva y no solo descriptiva.

---

## Fase 4 — 2029: experimentación y growth operating system

**Objetivo:** institucionalizar mejora continua y aprendizaje medible.

### Entregables

- Framework interno para experimentos:
  - CTA,
  - hero,
  - formularios,
  - copy por vertical,
  - landings satélite.
- Registro auditable de hipótesis:
  - cambio propuesto,
  - fecha,
  - responsable,
  - impacto esperado,
  - resultado real.
- Panel de experimentación:
  - uplift por variante,
  - efecto en CTA,
  - efecto en lead,
  - efecto en calidad comercial.
- Recomendador de backlog:
  - qué landing conviene optimizar primero,
  - qué keyword atacar,
  - qué funnel tiene mayor fuga.

### KPI objetivo

- Ciclos de optimización más cortos.
- Menos decisiones guiadas por intuición.
- Más foco en mejoras con retorno comprobable.

### Resultado esperado

La observabilidad deja de ser pasiva y se transforma en un sistema operativo de crecimiento.

---

## Fase 5 — 2030: GEO, AI search y observabilidad multinivel

**Objetivo:** preparar LhexIA para el escenario 2030, donde el descubrimiento no depende solo de Google tradicional.

### Entregables

- Capa de monitoreo “GEO / AI discovery”:
  - presencia de marca en respuestas generativas,
  - temas donde LhexIA aparece o no aparece,
  - páginas con mayor probabilidad de ser citadas por motores con IA.
- Observabilidad por entidad de negocio:
  - vertical,
  - región,
  - segmento,
  - tipo de cliente.
- Score unificado de crecimiento:
  - adquisición,
  - engagement,
  - intención,
  - lead quality,
  - eficiencia comercial.
- Integración opcional con CDP / warehouse si el volumen lo exige, sin romper la operación base del ERP.

### KPI objetivo

- Preparación para buscadores híbridos y asistentes generativos.
- Visibilidad ejecutiva por segmento y no solo por página.
- Capacidad de decidir crecimiento con criterio de negocio, no solo con métricas de marketing.

### Resultado esperado

LhexIA se posiciona no solo como ERP, sino como plataforma de inteligencia operativa y crecimiento para retail especializado.

---

## Arquitectura recomendada por capas

### Capa 1 — Captura

- Tracker first-party web
- eventos de CTA / scroll / engagement
- leads y señales de WhatsApp
- snapshots SEO internos

### Capa 2 — Persistencia

- tablas crudas acotadas por retención
- tablas agregadas ejecutivas
- snapshots diarios para score y tendencia
- logs auditables de sincronización externa

### Capa 3 — Procesamiento

- jobs nocturnos / periódicos
- consolidación y purga
- scoring
- detección de anomalías
- sincronización desacoplada con providers externos

### Capa 4 — Explotación

- dashboards de gerencia
- alertas
- recomendaciones priorizadas
- backlog de optimización

---

## Backlog recomendado para los próximos 90 días

1. Automatizar snapshot SEO diario y consolidación de telemetría.
2. Añadir taxonomía estable de eventos y CTAs.
3. Crear vista ejecutiva de embudo `visita -> lead -> WhatsApp`.
4. Agregar alertas básicas sobre caída de conversión o score SEO.
5. Diseñar el contrato local para futura sync con Search Console.
6. Definir catálogo de KPIs de gerencia con nombres estables y fórmulas explícitas.

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Mucha métrica y poca acción | Priorizar dashboards con hallazgos y siguientes pasos, no solo tablas |
| Dependencia de APIs externas | Mantener sincronizaciones asíncronas y snapshots persistidos |
| Ruido por eventos mal etiquetados | Taxonomía cerrada, validación de payload y catálogos por evento |
| Exceso de complejidad temprana | Mantener fase 2026–2027 dentro del monolito y extraer después |
| Problemas de privacidad y volumen | Retención, agregación, purga y minimización por diseño |

---

## Próximo paso sugerido

La siguiente iteración con mejor retorno es **cerrar Fase 1 de verdad**:

1. cron / scheduler para snapshots y purga,  
2. taxonomía estable de eventos,  
3. alertas gerenciales mínimas,  
4. embudo ejecutivo `visita -> lead -> WhatsApp`.

---

*Documento vivo: actualizar al cerrar cada hito relevante o cuando cambie el modelo operativo de adquisición/comercial.*
