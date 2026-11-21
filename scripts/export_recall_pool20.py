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
INPUT = ROOT / "artifacts" / "human_evaluation" / "recall_pool20_runs.json"
OUTPUT_JSON = ROOT / "artifacts" / "human_evaluation" / "recall_pool20_results.json"
OUTPUT_CSV = ROOT / "artifacts" / "human_evaluation" / "recall_pool20_results.csv"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def main() -> None:
    protocol = json.loads(INPUT.read_text(encoding="utf-8"))
    questions: list[dict] = []
    audit_rows: list[dict] = []

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        for item in protocol["questions"]:
            run_id = int(item["pool20_run_id"])
            rows = conn.execute(
                """
                SELECT rr.rank,
                       rr.chunk_id,
                       1 - rr.cosine_distance AS cosine_similarity,
                       j.label,
                       j.judged_at
                FROM retrieval_results rr
                LEFT JOIN relevance_judgments j
                  ON j.run_id = rr.run_id AND j.rank = rr.rank
                WHERE rr.run_id = %s
                ORDER BY rr.rank
                """,
                (run_id,),
            ).fetchall()
            if len(rows) != 20:
                raise RuntimeError(f"Pergunta {item['question_number']}: esperados 20 resultados")
            if any(row["label"] is None for row in rows):
                missing = [row["rank"] for row in rows if row["label"] is None]
                raise RuntimeError(
                    f"Pergunta {item['question_number']}: posições sem julgamento: {missing}"
                )

            relevant = [row for row in rows if row["label"] == "relevant"]
            relevant_top5 = [row for row in relevant if row["rank"] <= 5]
            first_relevant = min((row["rank"] for row in relevant), default=None)
            counts = Counter(row["label"] for row in rows)
            recall_at_5 = len(relevant_top5) / len(relevant) if relevant else 0.0
            reciprocal_rank = 1.0 / first_relevant if first_relevant else 0.0

            question_result = {
                "question_number": int(item["question_number"]),
                "query": item["query"],
                "run_id": run_id,
                "pool_depth": 20,
                "relevant_top5": len(relevant_top5),
                "relevant_pool20": len(relevant),
                "partial_pool20": counts["partial"],
                "not_relevant_pool20": counts["not_relevant"],
                "recall_at_5_pool20": recall_at_5,
                "first_relevant_rank": first_relevant,
                "reciprocal_rank": reciprocal_rank,
            }
            questions.append(question_result)

            for row in rows:
                audit_rows.append(
                    {
                        "question_number": int(item["question_number"]),
                        "run_id": run_id,
                        "rank": int(row["rank"]),
                        "chunk_id": str(row["chunk_id"]),
                        "cosine_similarity": float(row["cosine_similarity"]),
                        "label": row["label"],
                        "judged_at": row["judged_at"].isoformat(),
                    }
                )

    total_top5 = sum(row["relevant_top5"] for row in questions)
    total_pool20 = sum(row["relevant_pool20"] for row in questions)
    aggregate = {
        "macro_recall_at_5_pool20": sum(
            row["recall_at_5_pool20"] for row in questions
        )
        / len(questions),
        "micro_recall_at_5_pool20": total_top5 / total_pool20,
        "mrr": sum(row["reciprocal_rank"] for row in questions) / len(questions),
        "relevant_top5_total": total_top5,
        "relevant_pool20_total": total_pool20,
        "questions": len(questions),
        "judgments": len(audit_rows),
    }
    output = {
        "protocol": "Recall@5 estimado sobre pool@20 com julgamento humano",
        "positive_label": "relevant",
        "interpretation_limit": (
            "O denominador contém os itens relevantes encontrados nas 20 primeiras posições; "
            "não representa todos os itens relevantes dos 7.276 fragmentos do corpus."
        ),
        "generated_at": datetime.now().astimezone().isoformat(),
        "aggregate": aggregate,
        "questions": questions,
        "judgments": audit_rows,
    }
    OUTPUT_JSON.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)

    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    print(OUTPUT_JSON)
    print(OUTPUT_CSV)


if __name__ == "__main__":
    main()
