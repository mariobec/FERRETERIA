-- LhexIA v0.2c — pgvector para catálogo y RAG (Neon / PostgreSQL local)
-- Ejecutar con rol que permita CREATE EXTENSION (Neon: habilitar en consola si falla).

CREATE EXTENSION IF NOT EXISTS vector;

-- Chunks indexables (productos hoy; docs ERP / Guía en fase siguiente)
CREATE TABLE IF NOT EXISTS lhexia_vector_chunks (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL,
    source_id INTEGER,
    chunk_key VARCHAR(128) NOT NULL,
    titulo VARCHAR(255),
    contenido TEXT NOT NULL,
    metadata_json TEXT,
    embedding vector(768),
    modelo_embedding VARCHAR(64) DEFAULT 'nomic-embed-text',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lhexia_vector_chunk_key
    ON lhexia_vector_chunks (chunk_key);

CREATE INDEX IF NOT EXISTS ix_lhexia_vector_source
    ON lhexia_vector_chunks (source_type, source_id);

-- Índice ANN: crear tras poblar datos (≥100 filas recomendado para IVFFlat)
-- CREATE INDEX ix_lhexia_vector_embedding_cosine
--     ON lhexia_vector_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

COMMENT ON TABLE lhexia_vector_chunks IS 'Embeddings LhexIA: productos (Comercial/Guía); dim 768 = nomic-embed-text vía Ollama';
COMMENT ON COLUMN lhexia_vector_chunks.source_type IS 'producto | doc_erp | manual_operativo';
COMMENT ON COLUMN lhexia_vector_chunks.chunk_key IS 'Ej: producto:123, doc_erp:maestro:sec-3';
