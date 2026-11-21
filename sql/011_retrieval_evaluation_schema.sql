CREATE TABLE IF NOT EXISTS retrieval_runs (
    run_id bigserial PRIMARY KEY,
    query_text text NOT NULL CHECK (char_length(query_text) BETWEEN 3 AND 1000),
    model_key text NOT NULL REFERENCES embedding_models(model_key) ON DELETE RESTRICT,
    top_k smallint NOT NULL CHECK (top_k BETWEEN 1 AND 20),
    query_embedding vector(1024) NOT NULL,
    embedding_duration_ms double precision NOT NULL CHECK (embedding_duration_ms >= 0),
    retrieval_duration_ms double precision NOT NULL CHECK (retrieval_duration_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval_results (
    run_id bigint NOT NULL REFERENCES retrieval_runs(run_id) ON DELETE CASCADE,
    rank smallint NOT NULL CHECK (rank > 0),
    chunk_id char(64) NOT NULL REFERENCES chunks(chunk_id) ON DELETE RESTRICT,
    cosine_distance double precision NOT NULL CHECK (cosine_distance BETWEEN 0 AND 2),
    PRIMARY KEY (run_id, rank),
    UNIQUE (run_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS relevance_judgments (
    run_id bigint NOT NULL,
    rank smallint NOT NULL,
    chunk_id char(64) NOT NULL,
    label text NOT NULL CHECK (label IN ('relevant', 'partial', 'not_relevant')),
    notes text NOT NULL DEFAULT '' CHECK (char_length(notes) <= 2000),
    judged_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, rank),
    FOREIGN KEY (run_id, rank)
        REFERENCES retrieval_results(run_id, rank) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id)
        REFERENCES chunks(chunk_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS retrieval_runs_created_at_idx
    ON retrieval_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS relevance_judgments_label_idx
    ON relevance_judgments (label);

COMMENT ON TABLE retrieval_runs IS
    'Consultas semânticas reproduzíveis, incluindo vetor e tempos medidos.';
COMMENT ON TABLE retrieval_results IS
    'Ranking exato por distância cosseno retornado para cada consulta.';
COMMENT ON TABLE relevance_judgments IS
    'Avaliações humanas de relevância dos fragmentos recuperados.';

