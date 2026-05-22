-- Estado archivado tributario (RCV histórico fuera de cola bodega). Neon PG 15+.
ALTER TYPE recepciones_estado_enum ADD VALUE IF NOT EXISTS 'Archivado RCV';
