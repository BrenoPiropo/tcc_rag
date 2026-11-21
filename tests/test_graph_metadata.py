from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.graph_metadata import (
    canonical_key,
    deterministic_entity_id,
    extract_graph_metadata,
)


PAGE = """CURSO: Ciência da Computação
CÓDIGO: 20261234 ISSN: 1809-5283
UM SISTEMA REPRODUZÍVEL PARA CONSULTA A DOCUMENTOS
Ana Júlia Souza 1 , Bruno Lima 2
1 Discente do curso de Ciência da Computação, 2 Docente do Departamento, Orientador(a)
Introdução: O trabalho apresenta um sistema.
"""


class GraphMetadataTests(unittest.TestCase):
    def test_extracts_header_entities(self) -> None:
        metadata = extract_graph_metadata(PAGE, "Ana Júlia Souza")
        self.assertEqual(metadata.title, "UM SISTEMA REPRODUZÍVEL PARA CONSULTA A DOCUMENTOS")
        self.assertEqual(metadata.course, "Ciência da Computação")
        self.assertEqual(metadata.author, "Ana Júlia Souza")
        self.assertEqual(metadata.advisors, ("Bruno Lima",))
        self.assertEqual(metadata.warnings, ())

    def test_canonical_key_ignores_case_accents_and_spacing(self) -> None:
        self.assertEqual(canonical_key("  Júlia   D'Ávila "), "julia d avila")

    def test_entity_id_is_deterministic(self) -> None:
        first = deterministic_entity_id("person", "ana julia souza")
        second = deterministic_entity_id("person", "ana julia souza")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_missing_metadata_is_reported(self) -> None:
        metadata = extract_graph_metadata("Texto sem cabeçalho", "Pessoa Ausente")
        self.assertEqual(
            metadata.warnings,
            ("title_not_found", "course_not_found", "advisor_not_found"),
        )


if __name__ == "__main__":
    unittest.main()

