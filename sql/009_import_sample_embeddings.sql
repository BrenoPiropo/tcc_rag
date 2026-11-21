\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE embedding_models_stage (
    model_key text, provider text, model_name text, revision char(40), dimension integer,
    max_sequence_length integer, pooling text, normalized boolean, library text,
    library_version text, framework text, framework_version text, device text,
    created_at timestamptz
);

CREATE TEMP TABLE chunk_embeddings_stage (
    chunk_id char(64), model_key text, model_token_count integer, truncated boolean,
    l2_norm double precision, embedding_text text, created_at timestamptz
);

\copy embedding_models_stage FROM '/tmp/sample_embedding_model.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy chunk_embeddings_stage FROM '/tmp/sample_embeddings.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

INSERT INTO embedding_models (
    model_key, provider, model_name, revision, dimension, max_sequence_length,
    pooling, normalized, library, library_version, framework,
    framework_version, device, created_at
)
SELECT model_key, provider, model_name, revision, dimension, max_sequence_length,
       pooling, normalized, library, library_version, framework,
       framework_version, device, created_at
FROM embedding_models_stage
ON CONFLICT (model_key) DO UPDATE SET
    dimension = EXCLUDED.dimension,
    max_sequence_length = EXCLUDED.max_sequence_length,
    pooling = EXCLUDED.pooling,
    normalized = EXCLUDED.normalized,
    library_version = EXCLUDED.library_version,
    framework_version = EXCLUDED.framework_version,
    device = EXCLUDED.device,
    created_at = EXCLUDED.created_at;

INSERT INTO chunk_embeddings (
    chunk_id, model_key, embedding, model_token_count, truncated, l2_norm, created_at
)
SELECT chunk_id, model_key, embedding_text::vector(1024), model_token_count,
       truncated, l2_norm, created_at
FROM chunk_embeddings_stage
ON CONFLICT (chunk_id, model_key) DO UPDATE SET
    embedding = EXCLUDED.embedding,
    model_token_count = EXCLUDED.model_token_count,
    truncated = EXCLUDED.truncated,
    l2_norm = EXCLUDED.l2_norm,
    created_at = EXCLUDED.created_at;

COMMIT;
