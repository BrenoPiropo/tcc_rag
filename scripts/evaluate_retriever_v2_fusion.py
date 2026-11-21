from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "artifacts"
    / "human_evaluation"
    / "retriever_v2_cross_encoder_evaluation.json"
)
OUTPUT = (
    ROOT
    / "artifacts"
    / "human_evaluation"
    / "retriever_v2_fusion_evaluation.json"
)
ALPHAS = (0.0, 0.25, 0.50, 0.75, 0.90, 1.0)
FINAL_K = 5
DEVELOPMENT_QUESTIONS = {1, 2, 3, 4, 5}
TEST_QUESTIONS = {6, 7, 8, 9, 10}


def minmax(values: list[float]) -> list[float]:
    low = min(values)
    high = max(values)
    if high == low:
        return [0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def rerank(question: dict, alpha: float) -> list[dict]:
    candidates = sorted(question["v2_selection"], key=lambda row: row["original_rank"])
    dense = minmax([float(row["query_similarity"]) for row in candidates])
    cross = minmax([float(row["cross_encoder_score"]) for row in candidates])
    fused: list[dict] = []
    for index, candidate in enumerate(candidates):
        fused.append(
            {
                **candidate,
                "dense_normalized": dense[index],
                "cross_encoder_normalized": cross[index],
                "fusion_score": alpha * dense[index] + (1.0 - alpha) * cross[index],
            }
        )
    return sorted(
        fused,
        key=lambda row: (-row["fusion_score"], row["original_rank"]),
    )[:FINAL_K]


def question_metrics(question: dict, selected: list[dict]) -> dict:
    relevant_pool = int(question["v1"]["relevant_pool20"])
    relevant_selected = sum(row["label"] == "relevant" for row in selected)
    first_relevant = next(
        (rank for rank, row in enumerate(selected, start=1) if row["label"] == "relevant"),
        None,
    )
    return {
        "relevant_selected": relevant_selected,
        "relevant_pool20": relevant_pool,
        "recall_at_5_pool20": relevant_selected / relevant_pool if relevant_pool else 0.0,
        "first_relevant_rank": first_relevant,
        "reciprocal_rank": 1.0 / first_relevant if first_relevant else 0.0,
    }


def aggregate(rows: list[dict], key: str) -> float:
    return sum(float(row[key]) for row in rows) / len(rows)


def evaluate(questions: list[dict], alpha: float, question_numbers: set[int]) -> dict:
    details = []
    for question in questions:
        number = int(question["question_number"])
        if number not in question_numbers:
            continue
        selected = rerank(question, alpha)
        details.append(
            {
                "question_number": number,
                **question_metrics(question, selected),
                "selected": selected,
            }
        )
    return {
        "macro_recall_at_5_pool20": aggregate(details, "recall_at_5_pool20"),
        "mrr": aggregate(details, "reciprocal_rank"),
        "questions": details,
    }


def baseline(questions: list[dict], question_numbers: set[int]) -> dict:
    rows = [
        question["v1"]
        for question in questions
        if int(question["question_number"]) in question_numbers
    ]
    return {
        "macro_recall_at_5_pool20": aggregate(rows, "recall_at_5_pool20"),
        "mrr": aggregate(rows, "reciprocal_rank"),
    }


def main() -> None:
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    questions = source["questions"]
    development = {
        str(alpha): evaluate(questions, alpha, DEVELOPMENT_QUESTIONS) for alpha in ALPHAS
    }
    selected_alpha = max(
        ALPHAS,
        key=lambda alpha: (
            development[str(alpha)]["macro_recall_at_5_pool20"],
            development[str(alpha)]["mrr"],
            alpha,
        ),
    )
    result = {
        "version": "retriever-v2-dense-cross-encoder-fusion",
        "created_at": datetime.now().astimezone().isoformat(),
        "method": (
            "Normalização min-max por pergunta e combinação linear: "
            "alpha * similaridade_densa + (1-alpha) * escore_cross_encoder."
        ),
        "alpha_candidates": list(ALPHAS),
        "development_questions": sorted(DEVELOPMENT_QUESTIONS),
        "test_questions": sorted(TEST_QUESTIONS),
        "selected_alpha_on_development": selected_alpha,
        "development": development,
        "test": {
            "v1": baseline(questions, TEST_QUESTIONS),
            "v2": evaluate(questions, selected_alpha, TEST_QUESTIONS),
        },
        "full_set_exploratory": {
            "v1": baseline(questions, DEVELOPMENT_QUESTIONS | TEST_QUESTIONS),
            "v2": evaluate(
                questions, selected_alpha, DEVELOPMENT_QUESTIONS | TEST_QUESTIONS
            ),
        },
        "interpretation_limit": (
            "O parâmetro foi escolhido apenas nas perguntas 1 a 5. A comparação principal "
            "usa as perguntas 6 a 10, mantidas fora da seleção do parâmetro."
        ),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "selected_alpha": selected_alpha,
        "test_v1": result["test"]["v1"],
        "test_v2": {
            key: value for key, value in result["test"]["v2"].items() if key != "questions"
        },
        "full_v1": result["full_set_exploratory"]["v1"],
        "full_v2": {
            key: value
            for key, value in result["full_set_exploratory"]["v2"].items()
            if key != "questions"
        },
    }, ensure_ascii=False, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()

