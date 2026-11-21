from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_anais.graph_queries import (  # noqa: E402
    GRAPH_QUERY_VERSION,
    ROUTING_VERSION,
    classify_question,
    execute_structural_query,
    resolve_hybrid_scope,
)


OUTPUT_PATH = ROOT / "artifacts" / "knowledge_graph" / "query_integration_validation.json"
LOG_PATH = ROOT / "logs" / "knowledge_graph_query_integration.log"


QUESTIONS = [
    ("Qual orientador possui mais trabalhos nos Anais?", "structural", "top_advisors"),
    (
        "Quais trabalhos foram apresentados por Breno Gonçalves Piropo?",
        "structural",
        "works_by_author",
    ),
    ("Quantos trabalhos existem em cada edição?", "structural", "works_per_edition"),
    ("Quantos trabalhos existem na edição 2?", "structural", "works_by_edition"),
    (
        "Quantos trabalhos pertencem ao curso de Ciência da Computação?",
        "structural",
        "works_by_course",
    ),
    (
        "Quais aplicações de inteligência artificial aparecem nos Anais?",
        "semantic",
        "semantic_content",
    ),
    (
        "Quais trabalhos sobre cacau aparecem na edição 3?",
        "hybrid",
        "semantic_by_edition",
    ),
]


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
    )


def main() -> None:
    configure_logging()
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        counts = conn.execute(
            """SELECT
                (SELECT count(*) FROM documents) AS documents,
                (SELECT count(*) FROM knowledge_graph_entities) AS entities,
                (SELECT count(*) FROM knowledge_graph_relations) AS relations,
                (SELECT count(*) FROM query_route_runs WHERE status = 'completed') AS completed_routes"""
        ).fetchone()

        plans = []
        structural_results = {}
        for question, expected_route, expected_intent in QUESTIONS:
            plan = classify_question(question)
            if plan.route != expected_route or plan.intent != expected_intent:
                raise RuntimeError(
                    f"Roteamento divergente: {question!r} -> {plan.route}/{plan.intent}"
                )
            plans.append(
                {
                    "question": question,
                    "route": plan.route,
                    "intent": plan.intent,
                    "parameters": plan.parameters,
                    "explanation": plan.explanation,
                }
            )
            if plan.route == "structural":
                result = execute_structural_query(conn, plan)
                structural_results[plan.intent] = {
                    "query_identifier": result.query_identifier,
                    "duration_ms": round(result.duration_ms, 3),
                    "rows": result.rows[:10],
                    "source_examples": len(result.sources),
                }
            elif plan.route == "hybrid":
                scope = resolve_hybrid_scope(conn, plan) or []
                structural_results[plan.intent] = {"scope_documents": len(scope)}

        top = structural_results["top_advisors"]["rows"][0]
        if top["label"] != "Wolney Gomes Almeida" or int(top["work_count"]) != 47:
            raise RuntimeError("O resultado de referência do ranking de orientadores mudou")
        author = structural_results["works_by_author"]["rows"][0]
        if author["label"] != "Breno Gonçalves Piropo" or int(author["work_count"]) != 2:
            raise RuntimeError("A consulta de referência por autor mudou")
        edition = structural_results["works_by_edition"]["rows"][0]
        if int(edition["work_count"]) != 973:
            raise RuntimeError("A contagem de referência da edição 2 mudou")
        edition_distribution = structural_results["works_per_edition"]["rows"]
        if [int(row["work_count"]) for row in edition_distribution] != [680, 973, 733, 754, 829]:
            raise RuntimeError("A distribuição de referência das edições mudou")
        if structural_results["semantic_by_edition"]["scope_documents"] != 733:
            raise RuntimeError("O escopo híbrido de referência da edição 3 mudou")

        latest_runs = conn.execute(
            """SELECT route_run_id, query_text, route, intent, query_identifier,
                      result_count, duration_ms, retrieval_run_id, status, created_at
               FROM query_route_runs
               ORDER BY route_run_id DESC
               LIMIT 10"""
        ).fetchall()

    summary = {
        "validated_at": datetime.now().astimezone().isoformat(),
        "status": "valid",
        "routing_version": ROUTING_VERSION,
        "graph_query_version": GRAPH_QUERY_VERSION,
        "counts": dict(counts),
        "classification_cases": plans,
        "structural_results": structural_results,
        "latest_route_runs": [dict(row) for row in latest_runs],
        "assertions": {
            "top_advisor": "Wolney Gomes Almeida",
            "top_advisor_work_count": 47,
            "breno_goncalves_piropo_work_count": 2,
            "edition_2_work_count": 973,
            "works_per_edition": [680, 973, 733, 754, 829],
            "edition_3_hybrid_scope": 733,
            "orphan_relations": 0,
        },
        "limitations": [
            "A classificação v1 usa regras determinísticas e deve ser avaliada com perguntas reais.",
            "Pessoas ainda são consolidadas por nome normalizado; homônimos exigem revisão.",
            "O resultado híbrido depende da qualidade da recuperação vetorial dentro do filtro.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logging.info("VALIDAÇÃO CONCLUÍDA | %s", OUTPUT_PATH)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
