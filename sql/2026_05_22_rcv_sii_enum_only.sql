-- Solo enum (ejecutar si falló el paso 9 del archivo completo). Neon PG 15+.
ALTER TYPE recepciones_estado_enum ADD VALUE IF NOT EXISTS 'Pendiente de Items';
