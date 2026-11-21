from __future__ import annotations

import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sql" / "016_query_routing_schema.sql"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def main() -> None:
    statement = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(database_url()) as conn:
        conn.execute(statement)
    print(f"Esquema aplicado: {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
