from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class CrossEncoderSelection:
    reranked_rank: int
    original_rank: int
    candidate_index: int
    score: float


def rerank_with_cross_encoder(
    query: str,
    passages: Sequence[str],
    model: Any,
    *,
    final_k: int = 5,
    batch_size: int = 4,
) -> list[CrossEncoderSelection]:
    """Ordena passagens pela relevância direta do par pergunta–passagem."""
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("A pergunta não pode estar vazia")
    if not passages:
        return []
    if final_k < 1 or final_k > len(passages):
        raise ValueError("final_k deve estar entre 1 e a quantidade de passagens")
    if batch_size < 1:
        raise ValueError("batch_size deve ser positivo")

    pairs = [(normalized_query, passage) for passage in passages]
    predicted = model.predict(
        pairs,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    scores = np.asarray(predicted, dtype=np.float64).reshape(-1)
    if scores.size != len(passages):
        raise RuntimeError("O cross-encoder retornou uma pontuação incompatível")
    if not np.all(np.isfinite(scores)):
        raise RuntimeError("O cross-encoder retornou pontuação não finita")

    ordered_indexes = sorted(range(len(passages)), key=lambda index: (-scores[index], index))
    return [
        CrossEncoderSelection(
            reranked_rank=reranked_rank,
            original_rank=index + 1,
            candidate_index=index,
            score=float(scores[index]),
        )
        for reranked_rank, index in enumerate(ordered_indexes[:final_k], start=1)
    ]

