-- LhexIA Academy — progreso checklist por usuario (LX-ACAD-3)
CREATE TABLE IF NOT EXISTS user_academy_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES usuarios(id),
    article_id INTEGER REFERENCES academy_articles(id),
    dedupe_key VARCHAR(128) NOT NULL,
    completed_steps_json TEXT,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_academy_progress_dedupe UNIQUE (user_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS ix_user_academy_progress_user_id ON user_academy_progress (user_id);
CREATE INDEX IF NOT EXISTS ix_user_academy_progress_dedupe_key ON user_academy_progress (dedupe_key);
