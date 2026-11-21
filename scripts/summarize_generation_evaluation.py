from __future__ import annotations

import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "artifacts" / "human_evaluation"
JSON_OUTPUT = OUTPUT_DIR / "generation_evaluation_v1_results.json"
CSV_OUTPUT = OUTPUT_DIR / "generation_evaluation_v1_results.csv"
SET_KEY = "rag-v1-10-questions"
CRITERIA = (
    "faithfulness",
    "citation_correctness",
    "completeness",
    "source_separation",
)


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def main() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        rows = conn.execute(
            """
            SELECT i.position,
                   a.answer_id,
                   a.run_id,
                   r.query_text,
                   a.generator_provider,
                   a.generator_model,
                   a.model_digest,
                   a.prompt_version,
                   a.temperature,
                   a.seed,
                   j.faithfulness,
                   j.citation_correctness,
                   j.completeness,
                   j.source_separation,
                   j.refusal_appropriateness,
                   j.notes,
                   j.judged_at
            FROM generation_evaluation_sets s
            JOIN generation_evaluation_items i
              ON i.evaluation_set_id = s.evaluation_set_id
            JOIN generated_answers a ON a.answer_id = i.answer_id
            JOIN retrieval_runs r ON r.run_id = a.run_id
            LEFT JOIN answer_generation_judgments j
              ON j.evaluation_set_id = i.evaluation_set_id
             AND j.answer_id = i.answer_id
            WHERE s.set_key = %s
            ORDER BY i.position
            """,
            (SET_KEY,),
        ).fetchall()

    if len(rows) != 10:
        raise RuntimeError(f"Esperadas 10 respostas; encontradas {len(rows)}")
    pending = [int(row["position"]) for row in rows if row["judged_at"] is None]
    if pending:
        raise RuntimeError(f"Avaliações pendentes nas perguntas: {pending}")

    serialized_rows = []
    for row in rows:
        serialized_rows.append(
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in dict(row).items()
            }
        )

    aggregates = {}
    for criterion in CRITERIA:
        values = [int(row[criterion]) for row in rows]
        distribution = Counter(values)
        aggregates[criterion] = {
            "mean": sum(values) / len(values),
            "minimum": min(values),
            "maximum": max(values),
            "distribution": {str(score): distribution.get(score, 0) for score in range(3)},
        }

    refusal_counts = Counter(str(row["refusal_appropriateness"]) for row in rows)
    result = {
        "evaluation_set": SET_KEY,
        "created_at": datetime.now().astimezone().isoformat(),
        "sample_size": len(rows),
        "scale": {
            "criteria": list(CRITERIA),
            "minimum": 0,
            "maximum": 2,
            "composite_score_calculated": False,
        },
        "aggregates": aggregates,
        "refusal_appropriateness": {
            key: refusal_counts.get(key, 0)
            for key in ("not_applicable", "appropriate", "inappropriate")
        },
        "answers_with_notes": sum(bool(str(row["notes"]).strip()) for row in rows),
        "items": serialized_rows,
        "interpretation_limit": (
            "Avaliação humana inicial com dez perguntas e um avaliador; "
            "os resultados não estimam concordância entre avaliadores."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with CSV_OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(serialized_rows[0]))
        writer.writeheader()
        writer.writerows(serialized_rows)

    print(json.dumps({
        "sample_size": result["sample_size"],
        "aggregates": result["aggregates"],
        "refusal_appropriateness": result["refusal_appropriateness"],
        "answers_with_notes": result["answers_with_notes"],
    }, ensure_ascii=False, indent=2))
    print(JSON_OUTPUT)
    print(CSV_OUTPUT)


if __name__ == "__main__":
    main()

