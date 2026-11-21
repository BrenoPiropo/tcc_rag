CREATE TABLE IF NOT EXISTS generation_evaluation_sets (
    evaluation_set_id bigserial PRIMARY KEY,
    set_key text NOT NULL UNIQUE,
    description text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generation_evaluation_items (
    evaluation_set_id bigint NOT NULL
        REFERENCES generation_evaluation_sets(evaluation_set_id) ON DELETE CASCADE,
    position smallint NOT NULL CHECK (position > 0),
    answer_id bigint NOT NULL
        REFERENCES generated_answers(answer_id) ON DELETE RESTRICT,
    PRIMARY KEY (evaluation_set_id, position),
    UNIQUE (evaluation_set_id, answer_id)
);

CREATE TABLE IF NOT EXISTS answer_generation_judgments (
    evaluation_set_id bigint NOT NULL,
    answer_id bigint NOT NULL,
    faithfulness smallint NOT NULL CHECK (faithfulness BETWEEN 0 AND 2),
    citation_correctness smallint NOT NULL CHECK (citation_correctness BETWEEN 0 AND 2),
    completeness smallint NOT NULL CHECK (completeness BETWEEN 0 AND 2),
    source_separation smallint NOT NULL CHECK (source_separation BETWEEN 0 AND 2),
    refusal_appropriateness text NOT NULL CHECK (
        refusal_appropriateness IN ('not_applicable', 'appropriate', 'inappropriate')
    ),
    notes text NOT NULL DEFAULT '' CHECK (char_length(notes) <= 4000),
    judged_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (evaluation_set_id, answer_id),
    FOREIGN KEY (evaluation_set_id, answer_id)
        REFERENCES generation_evaluation_items(evaluation_set_id, answer_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE generation_evaluation_sets IS
    'Conjuntos congelados de respostas submetidas à avaliação humana da geração.';
COMMENT ON TABLE generation_evaluation_items IS
    'Ordem e respostas pertencentes a cada protocolo de avaliação da geração.';
COMMENT ON TABLE answer_generation_judgments IS
    'Julgamentos humanos da qualidade das respostas produzidas pelo LLM.';

