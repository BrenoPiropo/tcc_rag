from __future__ import annotations

import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sql" / "015_knowledge_graph_schema.sql"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def main() -> None:
    with psycopg.connect(database_url()) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        tables = conn.execute(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                  'knowledge_graph_entities', 'knowledge_graph_relations'
              )
            """
        ).fetchone()[0]
    if tables != 2:
        raise RuntimeError("O esquema do grafo não foi criado integralmente")
    print("Esquema do grafo aplicado: 2 tabelas validadas")


if __name__ == "__main__":
    main()

