from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class MMRSelection:
    candidate_index: int
    original_rank: int
    reranked_rank: int
    query_similarity: float
    redundancy: float
    mmr_score: float


def _normalized_rows(embeddings: np.ndarray) -> np.ndarray:
    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("candidate_embeddings deve ser uma matriz não vazia")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("embeddings candidatos não podem ter norma zero")
    return matrix / norms


def maximal_marginal_relevance(
    query_similarities: Sequence[float],
    candidate_embeddings: np.ndarray,
    *,
    final_k: int = 5,
    lambda_mult: float = 0.70,
) -> list[MMRSelection]:
    """Seleciona candidatos relevantes e não redundantes por MMR.

    A pontuação é lambda * sim(consulta, candidato) menos
    (1 - lambda) * maior_similaridade(candidato, itens_já_selecionados).
    Empates são resolvidos pela posição original para garantir reprodutibilidade.
    """
    similarities = np.asarray(query_similarities, dtype=np.float32)
    embeddings = _normalized_rows(candidate_embeddings)
    if similarities.ndim != 1 or len(similarities) != len(embeddings):
        raise ValueError("similaridades e embeddings devem ter o mesmo tamanho")
    if not 0.0 <= lambda_mult <= 1.0:
        raise ValueError("lambda_mult deve estar entre 0 e 1")
    if not 1 <= final_k <= len(similarities):
        raise ValueError("final_k deve estar entre 1 e o total de candidatos")

    pairwise = embeddings @ embeddings.T
    selected: list[int] = []
    remaining = set(range(len(similarities)))
    output: list[MMRSelection] = []

    for reranked_rank in range(1, final_k + 1):
        scored: list[tuple[float, int, float]] = []
        for index in remaining:
            redundancy = (
                max(float(pairwise[index, chosen]) for chosen in selected)
                if selected
                else 0.0
            )
            score = (
                lambda_mult * float(similarities[index])
                - (1.0 - lambda_mult) * redundancy
            )
            scored.append((score, index, redundancy))

        score, chosen, redundancy = max(scored, key=lambda item: (item[0], -item[1]))
        selected.append(chosen)
        remaining.remove(chosen)
        output.append(
            MMRSelection(
                candidate_index=chosen,
                original_rank=chosen + 1,
                reranked_rank=reranked_rank,
                query_similarity=float(similarities[chosen]),
                redundancy=redundancy,
                mmr_score=score,
            )
        )

    return output
