CREATE TABLE IF NOT EXISTS generated_answers (
    answer_id bigserial PRIMARY KEY,
    run_id bigint NOT NULL UNIQUE REFERENCES retrieval_runs(run_id) ON DELETE CASCADE,
    generator_provider text NOT NULL,
    generator_model text NOT NULL,
    model_digest text NOT NULL,
    prompt_version text NOT NULL,
    system_prompt_sha256 char(64) NOT NULL CHECK (system_prompt_sha256 ~ '^[0-9a-f]{64}$'),
    answer_text text NOT NULL CHECK (char_length(answer_text) > 0),
    temperature double precision NOT NULL CHECK (temperature >= 0),
    seed integer NOT NULL,
    num_ctx integer NOT NULL CHECK (num_ctx > 0),
    num_predict integer NOT NULL CHECK (num_predict > 0),
    generation_duration_ms double precision NOT NULL CHECK (generation_duration_ms >= 0),
    prompt_eval_count integer CHECK (prompt_eval_count >= 0),
    eval_count integer CHECK (eval_count >= 0),
    response_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS answer_sources (
    answer_id bigint NOT NULL REFERENCES generated_answers(answer_id) ON DELETE CASCADE,
    source_number smallint NOT NULL CHECK (source_number > 0),
    run_id bigint NOT NULL,
    rank smallint NOT NULL,
    chunk_id char(64) NOT NULL,
    PRIMARY KEY (answer_id, source_number),
    UNIQUE (answer_id, chunk_id),
    FOREIGN KEY (run_id, rank)
        REFERENCES retrieval_results(run_id, rank) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id)
        REFERENCES chunks(chunk_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS generated_answers_created_at_idx
    ON generated_answers (created_at DESC);

COMMENT ON TABLE generated_answers IS
    'Respostas produzidas pelo LLM local com configuração reproduzível.';
COMMENT ON TABLE answer_sources IS
    'Evidências numeradas fornecidas ao LLM para cada resposta RAG.';

