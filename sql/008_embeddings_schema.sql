CREATE TABLE IF NOT EXISTS embedding_models (
    model_key text PRIMARY KEY,
    provider text NOT NULL,
    model_name text NOT NULL,
    revision char(40) NOT NULL CHECK (revision ~ '^[0-9a-f]{40}$'),
    dimension integer NOT NULL CHECK (dimension = 1024),
    max_sequence_length integer NOT NULL CHECK (max_sequence_length > 0),
    pooling text NOT NULL,
    normalized boolean NOT NULL,
    library text NOT NULL,
    library_version text NOT NULL,
    framework text NOT NULL,
    framework_version text NOT NULL,
    device text NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (model_name, revision)
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id char(64) NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    model_key text NOT NULL REFERENCES embedding_models(model_key) ON DELETE RESTRICT,
    embedding vector(1024) NOT NULL,
    model_token_count integer NOT NULL CHECK (model_token_count > 0),
    truncated boolean NOT NULL,
    l2_norm double precision NOT NULL CHECK (l2_norm > 0),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (chunk_id, model_key)
);

CREATE INDEX IF NOT EXISTS chunk_embeddings_model_idx ON chunk_embeddings(model_key);

COMMENT ON TABLE embedding_models IS
    'Versões exatas e parâmetros dos modelos usados para gerar embeddings.';
COMMENT ON TABLE chunk_embeddings IS
    'Vetores densos normalizados e rastreáveis até o fragmento textual de origem.';
