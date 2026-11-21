from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.reranking import maximal_marginal_relevance  # noqa: E402


INPUT = ROOT / "artifacts" / "human_evaluation" / "recall_pool20_runs.json"
OUTPUT = (
    ROOT
    / "artifacts"
    / "human_evaluation"
    / "retriever_v2_mmr_evaluation.json"
)
CANDIDATE_K = 20
FINAL_K = 5
LAMBDA_MULT = 0.70
VERSION = "retriever-v2-mmr-lambda-0.70"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def parse_vector(value: str) -> np.ndarray:
    vector = np.fromstring(value.strip("[]"), sep=",", dtype=np.float32)
    if vector.size != 1024:
        raise ValueError(f"Embedding com dimensão inesperada: {vector.size}")
    return vector


def metrics(selected: list[dict], all_candidates: list[dict]) -> dict[str, float | int]:
    relevant_pool = sum(row["label"] == "relevant" for row in all_candidates)
    relevant_selected = sum(row["label"] == "relevant" for row in selected)
    first_relevant = next(
        (index for index, row in enumerate(selected, start=1) if row["label"] == "relevant"),
        None,
    )
    return {
        "relevant_selected": relevant_selected,
        "relevant_pool20": relevant_pool,
        "recall_at_5_pool20": relevant_selected / relevant_pool if relevant_pool else 0.0,
        "first_relevant_rank": first_relevant,
        "reciprocal_rank": 1.0 / first_relevant if first_relevant else 0.0,
        "unique_documents": len({row["document_sha256"] for row in selected}),
    }


def aggregate(rows: list[dict], metric_key: str) -> float:
    return sum(row[metric_key] for row in rows) / len(rows)


def main() -> None:
    protocol = json.loads(INPUT.read_text(encoding="utf-8"))
    questions: list[dict] = []
    run_ids = [int(question["pool20_run_id"]) for question in protocol["questions"]]

    print(
        f"Carregando {len(run_ids) * CANDIDATE_K} candidatos da avaliação humana...",
        flush=True,
    )

    with psycopg.connect(
        database_url(), row_factory=dict_row, connect_timeout=5
    ) as conn:
        rows = conn.execute(
            """
            SELECT rr.run_id,
                   rr.rank,
                   rr.chunk_id,
                   1 - rr.cosine_distance AS query_similarity,
                   j.label,
                   c.document_sha256,
                   e.embedding::text AS embedding_text
            FROM retrieval_results rr
            JOIN relevance_judgments j
              ON j.run_id = rr.run_id AND j.rank = rr.rank
            JOIN chunks c ON c.chunk_id = rr.chunk_id
            JOIN retrieval_runs run ON run.run_id = rr.run_id
            JOIN chunk_embeddings e
              ON e.chunk_id = rr.chunk_id AND e.model_key = run.model_key
            WHERE rr.run_id = ANY(%s)
              AND rr.rank <= %s
            ORDER BY rr.run_id, rr.rank
            """,
            (run_ids, CANDIDATE_K),
        ).fetchall()

        candidates_by_run: dict[int, list[dict]] = {run_id: [] for run_id in run_ids}
        for row in rows:
            candidates_by_run[int(row["run_id"])].append(row)

        for question in protocol["questions"]:
            run_id = int(question["pool20_run_id"])
            candidates = candidates_by_run[run_id]
            if len(candidates) != CANDIDATE_K:
                raise RuntimeError(
                    f"Pergunta {question['question_number']}: esperados {CANDIDATE_K} candidatos"
                )

            print(
                f"Reranqueando pergunta {question['question_number']}/10...",
                flush=True,
            )

            embeddings = np.vstack(
                [parse_vector(row["embedding_text"]) for row in candidates]
            )
            selections = maximal_marginal_relevance(
                [float(row["query_similarity"]) for row in candidates],
                embeddings,
                final_k=FINAL_K,
                lambda_mult=LAMBDA_MULT,
            )

            v1_selected = [dict(row) for row in candidates[:FINAL_K]]
            v2_selected: list[dict] = []
            selection_audit: list[dict] = []
            for selection in selections:
                candidate = dict(candidates[selection.candidate_index])
                v2_selected.append(candidate)
                selection_audit.append(
                    {
                        "reranked_rank": selection.reranked_rank,
                        "original_rank": selection.original_rank,
                        "chunk_id": candidate["chunk_id"],
                        "document_sha256": candidate["document_sha256"],
                        "label": candidate["label"],
                        "query_similarity": selection.query_similarity,
                        "redundancy": selection.redundancy,
                        "mmr_score": selection.mmr_score,
                    }
                )

            questions.append(
                {
                    "question_number": int(question["question_number"]),
                    "query": question["query"],
                    "source_pool_run_id": run_id,
                    "v1": metrics(v1_selected, candidates),
                    "v2": metrics(v2_selected, candidates),
                    "v2_selection": selection_audit,
                }
            )

    v1_rows = [row["v1"] for row in questions]
    v2_rows = [row["v2"] for row in questions]
    result = {
        "version": VERSION,
        "created_at": datetime.now().astimezone().isoformat(),
        "configuration": {
            "candidate_k": CANDIDATE_K,
            "final_k": FINAL_K,
            "lambda_mult": LAMBDA_MULT,
            "positive_label": "relevant",
            "unchanged_components": [
                "corpus",
                "segmentation",
                "BAAI/bge-m3 embeddings",
                "pgvector cosine candidate retrieval",
                "human judgments",
            ],
        },
        "aggregate": {
            "v1_macro_recall_at_5_pool20": aggregate(v1_rows, "recall_at_5_pool20"),
            "v2_macro_recall_at_5_pool20": aggregate(v2_rows, "recall_at_5_pool20"),
            "v1_mrr": aggregate(v1_rows, "reciprocal_rank"),
            "v2_mrr": aggregate(v2_rows, "reciprocal_rank"),
            "v1_mean_unique_documents_at_5": aggregate(v1_rows, "unique_documents"),
            "v2_mean_unique_documents_at_5": aggregate(v2_rows, "unique_documents"),
        },
        "questions": questions,
        "interpretation_limit": (
            "Avaliação retrospectiva sobre o mesmo pool@20 julgado na V1. "
            "Os resultados medem o efeito do reranqueamento nesse pool e não recall exaustivo do corpus."
        ),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
