from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.graph_metadata import (  # noqa: E402
    EXTRACTION_VERSION,
    canonical_key,
    deterministic_entity_id,
    deterministic_relation_id,
    extract_graph_metadata,
)


OUTPUT_DIR = ROOT / "artifacts" / "knowledge_graph"
LOG_PATH = ROOT / "logs" / "knowledge_graph_build.log"
WARNINGS_CSV = OUTPUT_DIR / "knowledge_graph_warnings.csv"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def add_entity(
    entities: dict[str, dict],
    entity_type: str,
    canonical_value: str,
    label: str,
    properties: dict,
) -> str:
    entity_id = deterministic_entity_id(entity_type, canonical_value)
    entities.setdefault(
        entity_id,
        {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "canonical_key": canonical_value,
            "label": label,
            "properties": properties,
        },
    )
    return entity_id


def add_relation(
    relations: dict[str, dict],
    source_entity_id: str,
    relation_type: str,
    target_entity_id: str,
    document_sha256: str,
) -> None:
    relation_id = deterministic_relation_id(
        source_entity_id, relation_type, target_entity_id, document_sha256
    )
    relations[relation_id] = {
        "relation_id": relation_id,
        "source_entity_id": source_entity_id,
        "relation_type": relation_type,
        "target_entity_id": target_entity_id,
        "source_document_sha256": document_sha256,
        "source_page_number": 1,
        "properties": {"extracted_from": "document_header"},
    }


def write_graph(entities: dict[str, dict], relations: dict[str, dict]) -> None:
    with psycopg.connect(database_url()) as conn:
        with conn.transaction():
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO knowledge_graph_entities (
                    entity_id, entity_type, canonical_key, label,
                    properties, extraction_version
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (entity_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    properties = EXCLUDED.properties,
                    extraction_version = EXCLUDED.extraction_version
                """,
                [
                    (
                        row["entity_id"],
                        row["entity_type"],
                        row["canonical_key"],
                        row["label"],
                        Jsonb(row["properties"]),
                        EXTRACTION_VERSION,
                    )
                    for row in entities.values()
                ],
            )
            cursor.executemany(
                """
                INSERT INTO knowledge_graph_relations (
                    relation_id, source_entity_id, relation_type,
                    target_entity_id, source_document_sha256,
                    source_page_number, properties, extraction_version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (relation_id) DO UPDATE SET
                    properties = EXCLUDED.properties,
                    extraction_version = EXCLUDED.extraction_version
                """,
                [
                    (
                        row["relation_id"],
                        row["source_entity_id"],
                        row["relation_type"],
                        row["target_entity_id"],
                        row["source_document_sha256"],
                        row["source_page_number"],
                        Jsonb(row["properties"]),
                        EXTRACTION_VERSION,
                    )
                    for row in relations.values()
                ],
            )


def main(write: bool) -> None:
    configure_logging()
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        documents = conn.execute(
            """
            SELECT d.sha256,
                   d.edition,
                   d.site_user_id,
                   d.participant_name,
                   p.normalized_text
            FROM documents d
            JOIN pages p
              ON p.document_sha256 = d.sha256 AND p.page_number = 1
            WHERE p.extraction_status = 'extracted'
            ORDER BY d.edition, d.site_user_id
            """
        ).fetchall()

    entities: dict[str, dict] = {}
    relations: dict[str, dict] = {}
    warning_rows = []
    warning_counts = Counter()
    person_label_variants: dict[str, set[str]] = defaultdict(set)

    for index, document in enumerate(documents, start=1):
        document_sha256 = document["sha256"].strip()
        metadata = extract_graph_metadata(
            str(document["normalized_text"]), str(document["participant_name"])
        )
        warning_counts.update(metadata.warnings)
        if metadata.warnings:
            warning_rows.append(
                {
                    "document_sha256": document_sha256,
                    "edition": int(document["edition"]),
                    "site_user_id": int(document["site_user_id"]),
                    "participant_name": document["participant_name"],
                    "warnings": " | ".join(metadata.warnings),
                }
            )

        work_id = add_entity(
            entities,
            "work",
            document_sha256,
            metadata.title or f"Trabalho {document['edition']}/{document['site_user_id']}",
            {
                "document_sha256": document_sha256,
                "edition": int(document["edition"]),
                "site_user_id": int(document["site_user_id"]),
                "metadata_complete": not metadata.warnings,
            },
        )
        author_key = canonical_key(metadata.author)
        person_label_variants[author_key].add(metadata.author)
        author_id = add_entity(entities, "person", author_key, metadata.author, {})
        add_relation(relations, work_id, "AUTHORED_BY", author_id, document_sha256)

        edition_key = str(int(document["edition"]))
        edition_id = add_entity(
            entities,
            "edition",
            edition_key,
            f"Edição {edition_key}",
            {"edition": int(document["edition"])},
        )
        add_relation(relations, work_id, "PRESENTED_IN", edition_id, document_sha256)

        if metadata.course:
            course_key = canonical_key(metadata.course)
            course_id = add_entity(
                entities, "course", course_key, metadata.course, {}
            )
            add_relation(
                relations,
                work_id,
                "ASSOCIATED_WITH_COURSE",
                course_id,
                document_sha256,
            )

        for advisor in metadata.advisors:
            advisor_key = canonical_key(advisor)
            person_label_variants[advisor_key].add(advisor)
            advisor_id = add_entity(entities, "person", advisor_key, advisor, {})
            add_relation(relations, work_id, "ADVISED_BY", advisor_id, document_sha256)

        if index % 250 == 0 or index == len(documents):
            logging.info(
                "PROCESSADOS | documentos=%d/%d | entidades=%d | relações=%d",
                index,
                len(documents),
                len(entities),
                len(relations),
            )

    entity_counts = Counter(row["entity_type"] for row in entities.values())
    relation_counts = Counter(row["relation_type"] for row in relations.values())
    summary = {
        "created_at": datetime.now().astimezone().isoformat(),
        "mode": "write" if write else "preview",
        "extraction_version": EXTRACTION_VERSION,
        "documents": len(documents),
        "complete_documents": len(documents) - len(warning_rows),
        "coverage": {
            "title": 1 - warning_counts["title_not_found"] / len(documents),
            "advisor": 1 - warning_counts["advisor_not_found"] / len(documents),
            "course": 1 - warning_counts["course_not_found"] / len(documents),
        },
        "warning_counts": dict(sorted(warning_counts.items())),
        "entities_by_type": dict(sorted(entity_counts.items())),
        "relations_by_type": dict(sorted(relation_counts.items())),
        "person_keys_with_label_variants": sum(
            len(labels) > 1 for labels in person_label_variants.values()
        ),
        "identity_limit": (
            "Pessoas são consolidadas pelo nome normalizado; homônimos podem exigir "
            "desambiguação manual em etapa posterior."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with WARNINGS_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        fieldnames = [
            "document_sha256", "edition", "site_user_id", "participant_name", "warnings"
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(warning_rows)

    if write:
        if summary["coverage"]["title"] < 0.95 or summary["coverage"]["advisor"] < 0.90:
            raise RuntimeError("Cobertura insuficiente para gravar o grafo integral")
        logging.info("GRAVANDO GRAFO | entidades=%d | relações=%d", len(entities), len(relations))
        write_graph(entities, relations)

    output = OUTPUT_DIR / (
        "knowledge_graph_build_summary.json" if write else "knowledge_graph_build_preview.json"
    )
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("CONCLUÍDO | modo=%s | resumo=%s", summary["mode"], output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(output)
    print(WARNINGS_CSV)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help="Grava nós e relações após validar a cobertura"
    )
    arguments = parser.parse_args()
    main(arguments.write)

