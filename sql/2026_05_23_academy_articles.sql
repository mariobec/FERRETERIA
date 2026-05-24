-- LhexIA Academy — artículos persistidos (PostgreSQL QA)
CREATE TABLE IF NOT EXISTS academy_articles (
    id SERIAL PRIMARY KEY,
    dedupe_key VARCHAR(128) NOT NULL UNIQUE,
    category VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    content_markdown TEXT,
    video_url VARCHAR(512),
    permissions_required VARCHAR(120) NOT NULL DEFAULT 'vendedor',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_academy_articles_category ON academy_articles (category);
CREATE INDEX IF NOT EXISTS ix_academy_articles_dedupe_key ON academy_articles (dedupe_key);
