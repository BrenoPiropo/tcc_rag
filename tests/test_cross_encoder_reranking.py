from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.cross_encoder_reranking import rerank_with_cross_encoder


class FakeCrossEncoder:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.received_pairs: list[tuple[str, str]] = []

    def predict(self, pairs, **_) -> np.ndarray:
        self.received_pairs = list(pairs)
        return np.asarray(self.scores, dtype=np.float32)


class CrossEncoderRerankingTests(unittest.TestCase):
    def test_orders_by_cross_encoder_score(self) -> None:
        model = FakeCrossEncoder([0.1, 0.9, 0.5])
        result = rerank_with_cross_encoder(
            "pergunta", ["a", "b", "c"], model, final_k=2
        )
        self.assertEqual([item.original_rank for item in result], [2, 3])

    def test_tie_preserves_original_order(self) -> None:
        model = FakeCrossEncoder([0.8, 0.8, 0.4])
        result = rerank_with_cross_encoder(
            "pergunta", ["a", "b", "c"], model, final_k=2
        )
        self.assertEqual([item.original_rank for item in result], [1, 2])

    def test_builds_query_passage_pairs(self) -> None:
        model = FakeCrossEncoder([0.5])
        rerank_with_cross_encoder("  uma   pergunta ", ["passagem"], model, final_k=1)
        self.assertEqual(model.received_pairs, [("uma pergunta", "passagem")])

    def test_rejects_incompatible_scores(self) -> None:
        with self.assertRaises(RuntimeError):
            rerank_with_cross_encoder(
                "pergunta", ["a", "b"], FakeCrossEncoder([0.5]), final_k=1
            )


if __name__ == "__main__":
    unittest.main()

