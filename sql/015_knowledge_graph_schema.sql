CREATE TABLE IF NOT EXISTS knowledge_graph_entities (
    entity_id char(64) PRIMARY KEY CHECK (entity_id ~ '^[0-9a-f]{64}$'),
    entity_type text NOT NULL CHECK (
        entity_type IN ('work', 'person', 'edition', 'course')
    ),
    canonical_key text NOT NULL,
    label text NOT NULL,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_type, canonical_key)
);

CREATE TABLE IF NOT EXISTS knowledge_graph_relations (
    relation_id char(64) PRIMARY KEY CHECK (relation_id ~ '^[0-9a-f]{64}$'),
    source_entity_id char(64) NOT NULL
        REFERENCES knowledge_graph_entities(entity_id) ON DELETE CASCADE,
    relation_type text NOT NULL CHECK (
        relation_type IN ('AUTHORED_BY', 'ADVISED_BY', 'PRESENTED_IN', 'ASSOCIATED_WITH_COURSE')
    ),
    target_entity_id char(64) NOT NULL
        REFERENCES knowledge_graph_entities(entity_id) ON DELETE CASCADE,
    source_document_sha256 char(64) NOT NULL
        REFERENCES documents(sha256) ON DELETE CASCADE,
    source_page_number integer NOT NULL CHECK (source_page_number > 0),
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (
        source_entity_id, relation_type, target_entity_id,
        source_document_sha256, source_page_number
    )
);

CREATE INDEX IF NOT EXISTS knowledge_graph_entities_type_idx
    ON knowledge_graph_entities (entity_type);
CREATE INDEX IF NOT EXISTS knowledge_graph_relations_source_idx
    ON knowledge_graph_relations (source_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS knowledge_graph_relations_target_idx
    ON knowledge_graph_relations (target_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS knowledge_graph_relations_document_idx
    ON knowledge_graph_relations (source_document_sha256);

COMMENT ON TABLE knowledge_graph_entities IS
    'Nós tipados da projeção de conhecimento derivada dos Anais da SIC/UESC.';
COMMENT ON TABLE knowledge_graph_relations IS
    'Arestas direcionadas com proveniência no PDF e versão do extrator.';

CREATE OR REPLACE VIEW knowledge_graph_advisor_work_counts AS
SELECT p.entity_id AS advisor_entity_id,
       p.label AS advisor_name,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities p
  ON p.entity_id = r.target_entity_id
WHERE r.relation_type = 'ADVISED_BY'
GROUP BY p.entity_id, p.label;

COMMENT ON VIEW knowledge_graph_advisor_work_counts IS
    'Contagem determinística de trabalhos por orientador no grafo.';

