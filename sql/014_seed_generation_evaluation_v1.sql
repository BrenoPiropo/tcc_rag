INSERT INTO generation_evaluation_sets (set_key, description)
VALUES (
    'rag-v1-10-questions',
    'Dez respostas da linha de base com prompt rag-baseline-v1.5, avaliadas separadamente da recuperação.'
)
ON CONFLICT (set_key) DO NOTHING;

WITH selected(position, answer_id) AS (
    VALUES
        (1, 19::bigint),
        (2, 20::bigint),
        (3, 22::bigint),
        (4, 23::bigint),
        (5, 24::bigint),
        (6, 25::bigint),
        (7, 26::bigint),
        (8, 27::bigint),
        (9, 28::bigint),
        (10, 29::bigint)
)
INSERT INTO generation_evaluation_items (evaluation_set_id, position, answer_id)
SELECT evaluation_set_id, selected.position, selected.answer_id
FROM generation_evaluation_sets
CROSS JOIN selected
WHERE set_key = 'rag-v1-10-questions'
ON CONFLICT (evaluation_set_id, position) DO NOTHING;

