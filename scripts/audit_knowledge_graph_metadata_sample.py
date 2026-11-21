from __future__ import annotations

import csv
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.graph_metadata import EXTRACTION_VERSION, extract_graph_metadata  # noqa: E402


OUTPUT_DIR = ROOT / "artifacts" / "knowledge_graph"
CSV_OUTPUT = OUTPUT_DIR / "metadata_sample.csv"
JSON_OUTPUT = OUTPUT_DIR / "metadata_sample_summary.json"
LOG_PATH = ROOT / "logs" / "knowledge_graph_metadata_sample.log"
PER_EDITION = 4


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


def main() -> None:
    configure_logging()
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT d.sha256,
                       d.edition,
                       d.site_user_id,
                       d.participant_name,
                       p.normalized_text,
                       row_number() OVER (
                           PARTITION BY d.edition ORDER BY d.site_user_id
                       ) AS position
                FROM documents d
                JOIN pages p
                  ON p.document_sha256 = d.sha256 AND p.page_number = 1
                WHERE p.extraction_status = 'extracted'
            )
            SELECT sha256, edition, site_user_id, participant_name, normalized_text
            FROM ranked
            WHERE position <= %s
            ORDER BY edition, position
            """,
            (PER_EDITION,),
        ).fetchall()

    output_rows = []
    warnings = Counter()
    for index, row in enumerate(rows, start=1):
        metadata = extract_graph_metadata(
            str(row["normalized_text"]), str(row["participant_name"])
        )
        warnings.update(metadata.warnings)
        output_rows.append(
            {
                "document_sha256": row["sha256"].strip(),
                "edition": int(row["edition"]),
                "site_user_id": int(row["site_user_id"]),
                "participant_name": row["participant_name"],
                "title": metadata.title or "",
                "advisors": " | ".join(metadata.advisors),
                "course": metadata.course or "",
                "warnings": " | ".join(metadata.warnings),
            }
        )
        logging.info(
            "DOCUMENTO %d/%d | edição=%s | id=%s | avisos=%s",
            index,
            len(rows),
            row["edition"],
            row["site_user_id"],
            ",".join(metadata.warnings) or "nenhum",
        )

    expected = PER_EDITION * 5
    if len(output_rows) != expected:
        raise RuntimeError(f"Amostra incompleta: esperados {expected}, obtidos {len(output_rows)}")

    summary = {
        "created_at": datetime.now().astimezone().isoformat(),
        "extraction_version": EXTRACTION_VERSION,
        "sample_strategy": (
            f"Primeiros {PER_EDITION} documentos por site_user_id em cada edição"
        ),
        "documents": len(output_rows),
        "complete_records": sum(not row["warnings"] for row in output_rows),
        "warning_counts": dict(sorted(warnings.items())),
        "coverage": {
            "title": sum(bool(row["title"]) for row in output_rows) / len(output_rows),
            "advisor": sum(bool(row["advisors"]) for row in output_rows) / len(output_rows),
            "course": sum(bool(row["course"]) for row in output_rows) / len(output_rows),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    JSON_OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("CONCLUÍDO | %s", json.dumps(summary, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(CSV_OUTPUT)
    print(JSON_OUTPUT)


if __name__ == "__main__":
    main()

