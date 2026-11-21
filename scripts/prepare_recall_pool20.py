from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "human_evaluation" / "recall_pool20_runs.json"
API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8765")

QUESTIONS = [
    (1, 25, "Quais contribuições para a cadeia produtiva do cacau são descritas nos trabalhos?"),
    (2, 36, "Quais aplicações de inteligência artificial aparecem nos Anais?"),
    (3, 28, "Que problemas ambientais do sul da Bahia são investigados?"),
    (4, 29, "Quais temas de saúde pública aparecem nos trabalhos?"),
    (5, 30, "Como a agricultura familiar é abordada nas pesquisas?"),
    (6, 31, "Quais estudos tratam da biodiversidade regional?"),
    (7, 32, "Que metodologias de ensino são relatadas nos trabalhos de educação?"),
    (8, 33, "Quais soluções de inovação tecnológica foram desenvolvidas na UESC?"),
    (9, 34, "Como questões de gênero, raça e inclusão social aparecem nas pesquisas?"),
    (10, 35, "Quais relações interdisciplinares podem ser identificadas entre trabalhos de áreas diferentes?"),
]


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def create_run(query: str) -> int:
    payload = json.dumps({"query": query, "top_k": 20}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{API_URL}/api/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return int(json.load(response)["run_id"])


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    mapping = []
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        for number, source_run, query in QUESTIONS:
            existing = conn.execute(
                """
                SELECT run_id
                FROM retrieval_runs
                WHERE query_text = %s AND top_k = 20
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (query,),
            ).fetchone()
            pool_run = int(existing["run_id"]) if existing else create_run(query)

            comparison = conn.execute(
                """
                SELECT old.rank,
                       old.chunk_id AS old_chunk,
                       fresh.chunk_id AS fresh_chunk,
                       j.label,
                       j.notes
                FROM retrieval_results old
                JOIN retrieval_results fresh ON fresh.rank = old.rank
                JOIN relevance_judgments j
                  ON j.run_id = old.run_id AND j.rank = old.rank
                WHERE old.run_id = %s
                  AND fresh.run_id = %s
                  AND old.rank <= 5
                ORDER BY old.rank
                """,
                (source_run, pool_run),
            ).fetchall()
            if len(comparison) != 5 or any(row["old_chunk"] != row["fresh_chunk"] for row in comparison):
                raise RuntimeError(
                    f"Pergunta {number}: o top 5 do pool não coincide com a avaliação original"
                )
            for row in comparison:
                conn.execute(
                    """
                    INSERT INTO relevance_judgments (run_id, rank, chunk_id, label, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, rank) DO UPDATE SET
                        chunk_id = EXCLUDED.chunk_id,
                        label = EXCLUDED.label,
                        notes = EXCLUDED.notes,
                        judged_at = now()
                    """,
                    (pool_run, row["rank"], row["fresh_chunk"], row["label"], row["notes"]),
                )
            conn.commit()
            mapping.append(
                {
                    "question_number": number,
                    "query": query,
                    "source_run_id": source_run,
                    "pool20_run_id": pool_run,
                    "copied_judgments": 5,
                    "pending_judgments": 15,
                }
            )
            print(f"Pergunta {number}: consulta #{pool_run} pronta (5/20 avaliados)")

    OUTPUT.write_text(
        json.dumps(
            {
                "protocol": "Recall@5 estimado sobre pool@20",
                "created_at": datetime.now().astimezone().isoformat(),
                "positive_label": "relevant",
                "questions": mapping,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
