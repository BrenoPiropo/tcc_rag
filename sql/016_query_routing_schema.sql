CREATE TABLE IF NOT EXISTS query_route_runs (
    route_run_id bigserial PRIMARY KEY,
    query_text text NOT NULL,
    routing_version text NOT NULL,
    route text NOT NULL CHECK (route IN ('semantic', 'structural', 'hybrid')),
    intent text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    explanation text NOT NULL,
    query_identifier text,
    executed_sql text,
    result_count integer CHECK (result_count IS NULL OR result_count >= 0),
    duration_ms double precision CHECK (duration_ms IS NULL OR duration_ms >= 0),
    retrieval_run_id bigint REFERENCES retrieval_runs(run_id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'planned' CHECK (
        status IN ('planned', 'completed', 'failed')
    ),
    error_text text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS query_route_runs_created_idx
    ON query_route_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS query_route_runs_route_idx
    ON query_route_runs (route, intent);

COMMENT ON TABLE query_route_runs IS
    'Auditoria reproduzível do roteamento entre recuperação semântica, consulta estrutural e fluxo híbrido.';
