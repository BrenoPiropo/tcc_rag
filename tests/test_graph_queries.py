from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.graph_queries import classify_question


class QueryRoutingTests(unittest.TestCase):
    def test_top_advisor_is_structural(self) -> None:
        plan = classify_question("Qual orientador possui mais trabalhos nos Anais?")
        self.assertEqual((plan.route, plan.intent), ("structural", "top_advisors"))

    def test_content_question_is_semantic(self) -> None:
        plan = classify_question("Quais aplicações de inteligência artificial aparecem nos Anais?")
        self.assertEqual((plan.route, plan.intent), ("semantic", "semantic_content"))

    def test_edition_topic_is_hybrid(self) -> None:
        plan = classify_question("Quais trabalhos sobre cacau aparecem na edição 3?")
        self.assertEqual((plan.route, plan.intent), ("hybrid", "semantic_by_edition"))
        self.assertEqual(plan.parameters["edition"], 3)

    def test_edition_count_is_structural(self) -> None:
        plan = classify_question("Quantos trabalhos existem na edição 2?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_edition"))

    def test_distribution_across_editions_is_structural(self) -> None:
        plan = classify_question("Quantos trabalhos existem em cada edição?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_per_edition"))

    def test_largest_edition_is_structural(self) -> None:
        plan = classify_question("Qual edição possui mais trabalhos?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_per_edition"))

    def test_advisor_filter_is_structural(self) -> None:
        plan = classify_question("Quais trabalhos foram orientados por Wolney Gomes Almeida?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_advisor"))
        self.assertEqual(plan.parameters["advisor_name"], "wolney gomes almeida")

    def test_explicit_advisor_label_is_structural(self) -> None:
        plan = classify_question("Quais trabalhos são do orientador Wolney Gomes Almeida?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_advisor"))

    def test_advisor_name_preserves_preposition(self) -> None:
        plan = classify_question("Quais trabalhos foram orientados por Reinaldo Joaquim dos Santos Dórea?")
        self.assertEqual(
            plan.parameters["advisor_name"], "reinaldo joaquim dos santos dorea"
        )

    def test_presented_works_are_routed_by_author(self) -> None:
        plan = classify_question(
            "Quais trabalhos foram apresentados por Breno Gonçalves Piropo?"
        )
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_author"))
        self.assertEqual(plan.parameters["author_name"], "breno goncalves piropo")

    def test_presented_by_student_is_routed_by_author(self) -> None:
        plan = classify_question(
            "Quais trabalhos foram apresentados pelo aluno Breno Gonçalves Piropo?"
        )
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_author"))
        self.assertEqual(plan.parameters["author_name"], "breno goncalves piropo")

    def test_author_topic_question_is_hybrid(self) -> None:
        plan = classify_question(
            "Quais trabalhos apresentados por Breno Gonçalves Piropo tratam de tecnologia?"
        )
        self.assertEqual((plan.route, plan.intent), ("hybrid", "semantic_by_author"))

    def test_course_count_is_structural(self) -> None:
        plan = classify_question("Quantos trabalhos pertencem ao curso de Ciência da Computação?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_course"))
        self.assertEqual(plan.parameters["course_name"], "ciencia da computacao")

    def test_course_work_list_is_structural(self) -> None:
        plan = classify_question("Quais trabalhos são do curso de Ciência da Computação?")
        self.assertEqual((plan.route, plan.intent), ("structural", "works_by_course"))

    def test_course_topic_question_is_hybrid(self) -> None:
        plan = classify_question(
            "Quais trabalhos do curso de Ciência da Computação tratam de inteligência artificial?"
        )
        self.assertEqual((plan.route, plan.intent), ("hybrid", "semantic_by_course"))

    def test_corpus_summary_is_structural(self) -> None:
        plan = classify_question("Quantos trabalhos existem na base dos Anais?")
        self.assertEqual((plan.route, plan.intent), ("structural", "corpus_summary"))


if __name__ == "__main__":
    unittest.main()
