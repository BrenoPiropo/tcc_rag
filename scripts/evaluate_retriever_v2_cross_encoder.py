from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from sentence_transformers import CrossEncoder


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.cross_encoder_reranking import rerank_with_cross_encoder  # noqa: E402


INPUT = ROOT / "artifacts" / "human_evaluation" / "recall_pool20_runs.json"
OUTPUT = (
    ROOT
    / "artifacts"
    / "human_evaluation"
    / "retriever_v2_cross_encoder_evaluation.json"
)
LOG_PATH = ROOT / "logs" / "retriever_v2_cross_encoder.log"
MODEL_NAME = "BAAI/bge-reranker-v2-m3"
MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
MODEL_CACHE = ROOT / "models" / "huggingface"
CANDIDATE_K = 20
FINAL_K = 5
MAX_LENGTH = 1024
BATCH_SIZE = 4
VERSION = "retriever-v2-cross-encoder-bge-reranker-v2-m3"


def configure_logging() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("retriever_v2_cross_encoder")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    return logger


LOGGER = configure_logging()


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def metrics(selected: list[dict], all_candidates: list[dict]) -> dict[str, float | int | None]:
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
    return sum(float(row[metric_key]) for row in rows) / len(rows)


def save_checkpoint(questions: list[dict], *, status: str, started_at: str) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "version": VERSION,
                "status": status,
                "started_at": started_at,
                "updated_at": datetime.now().astimezone().isoformat(),
                "model": {"name": MODEL_NAME, "revision": MODEL_REVISION},
                "configuration": {
                    "candidate_k": CANDIDATE_K,
                    "final_k": FINAL_K,
                    "max_length": MAX_LENGTH,
                    "batch_size": BATCH_SIZE,
                    "device": "cpu",
                    "positive_label": "relevant",
                },
                "questions": questions,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    started_at = datetime.now().astimezone().isoformat()
    protocol = json.loads(INPUT.read_text(encoding="utf-8"))
    run_ids = [int(question["pool20_run_id"]) for question in protocol["questions"]]
    questions: list[dict] = []
    save_checkpoint(questions, status="running", started_at=started_at)

    LOGGER.info("CARREGANDO CANDIDATOS | quantidade=%d", len(run_ids) * CANDIDATE_K)
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        rows = conn.execute(
            """
            SELECT rr.run_id,
                   rr.rank,
                   rr.chunk_id,
                   1 - rr.cosine_distance AS query_similarity,
                   j.label,
                   c.document_sha256,
                   c.chunk_text
            FROM retrieval_results rr
            JOIN relevance_judgments j
              ON j.run_id = rr.run_id AND j.rank = rr.rank
            JOIN chunks c ON c.chunk_id = rr.chunk_id
            WHERE rr.run_id = ANY(%s)
              AND rr.rank <= %s
            ORDER BY rr.run_id, rr.rank
            """,
            (run_ids, CANDIDATE_K),
        ).fetchall()

    candidates_by_run: dict[int, list[dict]] = {run_id: [] for run_id in run_ids}
    for row in rows:
        candidates_by_run[int(row["run_id"])].append(dict(row))

    model_started = time.perf_counter()
    LOGGER.info("CARREGANDO MODELO | nome=%s | revisão=%s", MODEL_NAME, MODEL_REVISION)
    model = CrossEncoder(
        MODEL_NAME,
        revision=MODEL_REVISION,
        device="cpu",
        cache_folder=str(MODEL_CACHE),
        trust_remote_code=False,
        local_files_only=True,
        max_length=MAX_LENGTH,
    )
    model_load_seconds = time.perf_counter() - model_started
    LOGGER.info("MODELO CARREGADO | segundos=%.3f", model_load_seconds)

    evaluation_started = time.perf_counter()
    for question in protocol["questions"]:
        question_number = int(question["question_number"])
        run_id = int(question["pool20_run_id"])
        candidates = candidates_by_run[run_id]
        if len(candidates) != CANDIDATE_K:
            raise RuntimeError(
                f"Pergunta {question_number}: esperados {CANDIDATE_K} candidatos, "
                f"obtidos {len(candidates)}"
            )

        rerank_started = time.perf_counter()
        selections = rerank_with_cross_encoder(
            question["query"],
            [str(row["chunk_text"]) for row in candidates],
            model,
            final_k=CANDIDATE_K,
            batch_size=BATCH_SIZE,
        )
        rerank_seconds = time.perf_counter() - rerank_started
        v1_selected = candidates[:FINAL_K]
        v2_selected = [
            candidates[item.candidate_index] for item in selections[:FINAL_K]
        ]
        audit = [
            {
                "reranked_rank": item.reranked_rank,
                "original_rank": item.original_rank,
                "chunk_id": candidates[item.candidate_index]["chunk_id"],
                "document_sha256": candidates[item.candidate_index]["document_sha256"],
                "label": candidates[item.candidate_index]["label"],
                "query_similarity": float(
                    candidates[item.candidate_index]["query_similarity"]
                ),
                "cross_encoder_score": item.score,
            }
            for item in selections
        ]
        questions.append(
            {
                "question_number": question_number,
                "query": question["query"],
                "source_pool_run_id": run_id,
                "reranking_seconds": rerank_seconds,
                "v1": metrics(v1_selected, candidates),
                "v2": metrics(v2_selected, candidates),
                "v2_selection": audit,
            }
        )
        save_checkpoint(questions, status="running", started_at=started_at)
        LOGGER.info(
            "PERGUNTA CONCLUÍDA | numero=%d/10 | segundos=%.3f | relevantes_v1=%d | relevantes_v2=%d",
            question_number,
            rerank_seconds,
            questions[-1]["v1"]["relevant_selected"],
            questions[-1]["v2"]["relevant_selected"],
        )

    evaluation_seconds = time.perf_counter() - evaluation_started
    v1_rows = [row["v1"] for row in questions]
    v2_rows = [row["v2"] for row in questions]
    aggregate_result = {
        "v1_macro_recall_at_5_pool20": aggregate(v1_rows, "recall_at_5_pool20"),
        "v2_macro_recall_at_5_pool20": aggregate(v2_rows, "recall_at_5_pool20"),
        "v1_mrr": aggregate(v1_rows, "reciprocal_rank"),
        "v2_mrr": aggregate(v2_rows, "reciprocal_rank"),
        "v1_mean_unique_documents_at_5": aggregate(v1_rows, "unique_documents"),
        "v2_mean_unique_documents_at_5": aggregate(v2_rows, "unique_documents"),
    }
    result = json.loads(OUTPUT.read_text(encoding="utf-8"))
    result.update(
        {
            "status": "completed",
            "completed_at": datetime.now().astimezone().isoformat(),
            "model_load_seconds": model_load_seconds,
            "evaluation_seconds": evaluation_seconds,
            "aggregate": aggregate_result,
            "questions": questions,
            "unchanged_components": [
                "corpus",
                "segmentation",
                "BAAI/bge-m3 embeddings",
                "pgvector cosine candidate retrieval",
                "human judgments",
            ],
            "interpretation_limit": (
                "Avaliação retrospectiva sobre o mesmo pool@20 julgado na V1. "
                "Os resultados medem o reranqueamento nesse pool, não o recall exaustivo do corpus."
            ),
        }
    )
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("AVALIAÇÃO CONCLUÍDA | %s", json.dumps(aggregate_result))
    LOGGER.info("ARTEFATO | caminho=%s", OUTPUT)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOGGER.exception("FALHA NA AVALIAÇÃO")
        raise

