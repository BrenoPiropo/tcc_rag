from __future__ import annotations

import unittest
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.reranking import maximal_marginal_relevance


class MaximalMarginalRelevanceTests(unittest.TestCase):
    def test_lambda_one_preserves_query_ranking(self) -> None:
        embeddings = np.eye(4, dtype=np.float32)
        result = maximal_marginal_relevance(
            [0.90, 0.80, 0.70, 0.60], embeddings, final_k=3, lambda_mult=1.0
        )
        self.assertEqual([item.original_rank for item in result], [1, 2, 3])

    def test_penalizes_candidate_redundant_with_first_selection(self) -> None:
        embeddings = np.asarray(
            [
                [1.00, 0.00],
                [0.99, 0.01],
                [0.00, 1.00],
            ],
            dtype=np.float32,
        )
        result = maximal_marginal_relevance(
            [0.90, 0.89, 0.80], embeddings, final_k=2, lambda_mult=0.70
        )
        self.assertEqual([item.original_rank for item in result], [1, 3])

    def test_tie_is_resolved_by_original_rank(self) -> None:
        embeddings = np.eye(3, dtype=np.float32)
        result = maximal_marginal_relevance(
            [0.80, 0.80, 0.70], embeddings, final_k=2, lambda_mult=1.0
        )
        self.assertEqual([item.original_rank for item in result], [1, 2])

    def test_rejects_invalid_lambda(self) -> None:
        with self.assertRaises(ValueError):
            maximal_marginal_relevance(
                [0.90], np.asarray([[1.0, 0.0]], dtype=np.float32), lambda_mult=1.1
            )


if __name__ == "__main__":
    unittest.main()
