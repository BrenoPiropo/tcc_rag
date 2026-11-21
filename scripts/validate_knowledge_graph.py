from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "artifacts" / "knowledge_graph"
JSON_OUTPUT = OUTPUT_DIR / "knowledge_graph_validation.json"
ADVISORS_CSV = OUTPUT_DIR / "top_advisors_by_work_count.csv"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def main() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        entity_counts = conn.execute(
            """
            SELECT entity_type, count(*) AS count
            FROM knowledge_graph_entities
            GROUP BY entity_type ORDER BY entity_type
            """
        ).fetchall()
        relation_counts = conn.execute(
            """
            SELECT relation_type, count(*) AS count
            FROM knowledge_graph_relations
            GROUP BY relation_type ORDER BY relation_type
            """
        ).fetchall()
        integrity = conn.execute(
            """
            SELECT
                (SELECT count(*) FROM documents) AS documents,
                (SELECT count(*) FROM knowledge_graph_entities
                 WHERE entity_type = 'work') AS work_nodes,
                (SELECT count(*) FROM knowledge_graph_relations r
                 LEFT JOIN knowledge_graph_entities s
                   ON s.entity_id = r.source_entity_id
                 LEFT JOIN knowledge_graph_entities t
                   ON t.entity_id = r.target_entity_id
                 LEFT JOIN documents d
                   ON d.sha256 = r.source_document_sha256
                 WHERE s.entity_id IS NULL OR t.entity_id IS NULL OR d.sha256 IS NULL
                ) AS orphan_relations,
                (SELECT count(*) FROM (
                    SELECT source_entity_id
                    FROM knowledge_graph_relations
                    WHERE relation_type = 'AUTHORED_BY'
                    GROUP BY source_entity_id HAVING count(*) <> 1
                ) x) AS works_with_invalid_author_count,
                (SELECT count(*) FROM (
                    SELECT source_entity_id
                    FROM knowledge_graph_relations
                    WHERE relation_type = 'PRESENTED_IN'
                    GROUP BY source_entity_id HAVING count(*) <> 1
                ) x) AS works_with_invalid_edition_count
            """
        ).fetchone()
        top_advisors = conn.execute(
            """
            SELECT advisor_entity_id AS entity_id,
                   advisor_name AS advisor,
                   work_count AS works
            FROM knowledge_graph_advisor_work_counts
            ORDER BY works DESC, advisor
            LIMIT 20
            """
        ).fetchall()
        works_by_edition = conn.execute(
            """
            SELECT e.label AS edition,
                   count(DISTINCT r.source_document_sha256) AS works
            FROM knowledge_graph_relations r
            JOIN knowledge_graph_entities e
              ON e.entity_id = r.target_entity_id
            WHERE r.relation_type = 'PRESENTED_IN'
            GROUP BY e.label, e.canonical_key
            ORDER BY e.canonical_key::integer
            """
        ).fetchall()

    if int(integrity["documents"]) != int(integrity["work_nodes"]):
        raise RuntimeError("A quantidade de nós de trabalho difere do corpus")
    if any(int(integrity[key]) != 0 for key in (
        "orphan_relations",
        "works_with_invalid_author_count",
        "works_with_invalid_edition_count",
    )):
        raise RuntimeError(f"Falha de integridade no grafo: {dict(integrity)}")

    result = {
        "validated_at": datetime.now().astimezone().isoformat(),
        "status": "valid",
        "entity_counts": {row["entity_type"]: row["count"] for row in entity_counts},
        "relation_counts": {
            row["relation_type"]: row["count"] for row in relation_counts
        },
        "integrity": dict(integrity),
        "works_by_edition": [dict(row) for row in works_by_edition],
        "top_advisors": [dict(row) for row in top_advisors],
        "ranking_limit": (
            "Pessoas são agrupadas pelo nome normalizado. O ranking deve ser interpretado "
            "após revisão de homônimos e variantes de nome."
        ),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with ADVISORS_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["entity_id", "advisor", "works"])
        writer.writeheader()
        writer.writerows([dict(row) for row in top_advisors])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(JSON_OUTPUT)
    print(ADVISORS_CSV)


if __name__ == "__main__":
    main()

