from __future__ import annotations

import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "sql" / "013_generation_evaluation_schema.sql",
    ROOT / "sql" / "014_seed_generation_evaluation_v1.sql",
)


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://rag_user:troque-esta-senha@127.0.0.1:25432/rag_anais",
    )


def main() -> None:
    with psycopg.connect(database_url()) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"))
            print(f"Aplicado: {migration.name}")
        count = conn.execute(
            "SELECT count(*) FROM generation_evaluation_items"
        ).fetchone()[0]
    print(f"Itens do protocolo: {count}")


if __name__ == "__main__":
    main()

