from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "knowledge_graph" / "experimento_grafo_5_perguntas.json"
LOG_PATH = ROOT / "logs" / "experimento_grafo_5_perguntas.log"
BASE_URL = os.getenv("RAG_BASE_URL", "http://127.0.0.1:8765").rstrip("/")

QUESTIONS = [
    {
        "position": 1,
        "question": "Quais foram os trabalhos apresentados por Breno Gonçalves Piropo?",
        "expected_intent": "works_by_author",
    },
    {
        "position": 2,
        "question": "Quais trabalhos foram orientados por Gesil Sampaio Amarante Segundo?",
        "expected_intent": "works_by_advisor",
    },
    {
        "position": 3,
        "question": "Quais trabalhos estão relacionados ao curso de Ciência da Computação?",
        "expected_intent": "works_by_course",
    },
    {
        "position": 4,
        "question": "Quantos trabalhos foram apresentados em cada edição da SIC/UESC?",
        "expected_intent": "works_per_edition",
    },
    {
        "position": 5,
        "question": "Quais cursos apresentam mais trabalhos?",
        "expected_intent": "top_courses",
    },
]


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
    )


def main() -> None:
    configure_logging()
    results = []
    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{BASE_URL}/api/health")
        health.raise_for_status()
        for item in QUESTIONS:
            response = client.post(
                f"{BASE_URL}/api/answer",
                json={"query": item["question"], "top_k": 5},
            )
            response.raise_for_status()
            data = response.json()
            route = data["route"]
            answer = data["answer"]
            if route["route"] != "structural" or route["intent"] != item["expected_intent"]:
                raise RuntimeError(
                    f"Pergunta {item['position']} roteada como "
                    f"{route['route']}/{route['intent']}"
                )
            row = {
                **item,
                "route": route["route"],
                "intent": route["intent"],
                "routing_version": route["routing_version"],
                "query_identifier": route["query_identifier"],
                "route_run_id": route["route_run_id"],
                "duration_ms": route["duration_ms"],
                "answer_provider": answer["provider"],
                "answer_model": answer["model"],
                "answer_text": answer["text"],
                "source_count": len(answer.get("sources", [])),
                "sources": answer.get("sources", []),
                "result_rows": answer.get("rows", []),
            }
            results.append(row)
            logging.info(
                "PERGUNTA %d | intent=%s | consulta=%s | fontes=%d | ms=%.2f",
                item["position"],
                route["intent"],
                route["query_identifier"],
                row["source_count"],
                route["duration_ms"],
            )

    artifact = {
        "created_at": datetime.now().astimezone().isoformat(),
        "experiment": "graph-structural-5-questions-v1",
        "status": "valid",
        "base_url": BASE_URL,
        "corpus": {
            "documents": health.json()["documents"],
            "graph_entities": health.json()["graph_entities"],
            "graph_relations": health.json()["graph_relations"],
        },
        "methodological_note": (
            "As cinco perguntas são estruturais. As respostas foram produzidas por consultas "
            "determinísticas ao grafo no PostgreSQL, sem geração de conteúdo pela LLM."
        ),
        "results": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logging.info("EXPERIMENTO CONCLUÍDO | %s", OUTPUT)
    print(json.dumps(artifact, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
