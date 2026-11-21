from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import platform
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sentence_transformers
import torch
import transformers
from sentence_transformers import SentenceTransformer


MODEL_FIELDS = [
    "model_key", "provider", "model_name", "revision", "dimension",
    "max_sequence_length", "pooling", "normalized", "library",
    "library_version", "framework", "framework_version", "device", "created_at",
]
EMBEDDING_FIELDS = [
    "chunk_id", "model_key", "model_token_count", "truncated", "l2_norm",
    "embedding", "created_at",
]


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sample_embeddings")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def select_stratified_sample(
    chunks_path: Path, documents_path: Path, per_edition: int,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with documents_path.open("r", encoding="utf-8", newline="") as stream:
        documents = {row["sha256"]: row for row in csv.DictReader(stream)}
    by_edition: dict[int, list[dict[str, str]]] = defaultdict(list)
    with chunks_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            edition = int(documents[row["document_sha256"]]["edition"])
            by_edition[edition].append(row)

    selected: list[dict[str, str]] = []
    for edition in range(1, 6):
        rows = sorted(
            by_edition[edition],
            key=lambda row: (row["document_sha256"], int(row["page_number"]), int(row["chunk_index"])),
        )
        if len(rows) < per_edition:
            raise ValueError(f"Edição {edition} contém apenas {len(rows)} fragmentos")
        positions = [round(index * (len(rows) - 1) / (per_edition - 1)) for index in range(per_edition)]
        selected.extend(rows[position] for position in positions)
    return selected, documents


def vector_text(vector: np.ndarray) -> str:
    return "[" + ",".join(f"{float(value):.9g}" for value in vector) + "]"


def generate(
    chunks_path: Path, documents_path: Path, output_dir: Path, log_path: Path,
    cache_dir: Path, model_name: str, revision: str, per_edition: int,
    batch_size: int, max_sequence_length: int,
) -> dict[str, object]:
    logger = configure_logging(log_path)
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    selected, documents = select_stratified_sample(chunks_path, documents_path, per_edition)
    model_key = f"{model_name}@{revision}"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(max(1, min(6, torch.get_num_threads())))

    logger.info(
        "INÍCIO | modelo=%s | revisão=%s | amostra=%d | dispositivo=cpu",
        model_name, revision, len(selected),
    )
    load_started = time.monotonic()
    model = SentenceTransformer(
        model_name,
        revision=revision,
        device="cpu",
        cache_folder=str(cache_dir),
        trust_remote_code=False,
    )
    model.max_seq_length = max_sequence_length
    dimension = int(model.get_embedding_dimension())
    if dimension != 1024:
        raise ValueError(f"Dimensão inesperada: {dimension}; esperado: 1024")
    load_seconds = time.monotonic() - load_started
    logger.info("MODELO CARREGADO | dimensão=%d | segundos=%.3f", dimension, load_seconds)

    texts = [row["chunk_text"] for row in selected]
    token_counts = [
        len(model.tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"])
        for text in texts
    ]
    truncated = [count > max_sequence_length for count in token_counts]
    if any(truncated):
        raise ValueError(
            f"A amostra contém {sum(truncated)} fragmentos acima de {max_sequence_length} tokens do modelo"
        )

    vectors: list[np.ndarray] = []
    inference_started = time.monotonic()
    total_batches = math.ceil(len(texts) / batch_size)
    for batch_number, first in enumerate(range(0, len(texts), batch_size), start=1):
        batch = texts[first:first + batch_size]
        encoded = model.encode(
            batch,
            batch_size=len(batch),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors.extend(np.asarray(encoded, dtype=np.float32))
        logger.info(
            "LOTE %d/%d | fragmentos=%d/%d",
            batch_number, total_batches, min(first + len(batch), len(texts)), len(texts),
        )
    inference_seconds = time.monotonic() - inference_started

    created_at = datetime.now(timezone.utc).isoformat()
    model_row = {
        "model_key": model_key,
        "provider": "BAAI",
        "model_name": model_name,
        "revision": revision,
        "dimension": dimension,
        "max_sequence_length": max_sequence_length,
        "pooling": "sentence-transformers model configuration",
        "normalized": "true",
        "library": "sentence-transformers",
        "library_version": sentence_transformers.__version__,
        "framework": "torch",
        "framework_version": torch.__version__,
        "device": "cpu",
        "created_at": created_at,
    }
    with (output_dir / "sample_embedding_model.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MODEL_FIELDS)
        writer.writeheader()
        writer.writerow(model_row)

    embedding_rows: list[dict[str, object]] = []
    norms: list[float] = []
    for chunk, token_count, was_truncated, vector in zip(selected, token_counts, truncated, vectors):
        norm = float(np.linalg.norm(vector))
        norms.append(norm)
        embedding_rows.append({
            "chunk_id": chunk["chunk_id"],
            "model_key": model_key,
            "model_token_count": token_count,
            "truncated": str(was_truncated).lower(),
            "l2_norm": f"{norm:.9f}",
            "embedding": vector_text(vector),
            "created_at": created_at,
        })
    with (output_dir / "sample_embeddings.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EMBEDDING_FIELDS)
        writer.writeheader()
        writer.writerows(embedding_rows)

    selected_rows = []
    for chunk, token_count in zip(selected, token_counts):
        metadata = documents[chunk["document_sha256"]]
        selected_rows.append({
            "edition": metadata["edition"],
            "site_user_id": metadata["site_user_id"],
            "participant_name": metadata["participant_name"],
            "chunk_id": chunk["chunk_id"],
            "page_number": chunk["page_number"],
            "chunk_index": chunk["chunk_index"],
            "model_token_count": token_count,
            "chunk_text": chunk["chunk_text"],
        })
    with (output_dir / "sample_embedding_selection.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected_rows[0]))
        writer.writeheader()
        writer.writerows(selected_rows)

    finished = datetime.now(timezone.utc)
    summary = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "duration_seconds": round(time.monotonic() - clock, 3),
        "model_load_seconds": round(load_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "model_name": model_name,
        "model_revision": revision,
        "model_key": model_key,
        "dimension": dimension,
        "max_sequence_length": max_sequence_length,
        "normalized": True,
        "sample_strategy": f"{per_edition} fragmentos determinísticos distribuídos por edição",
        "sample_chunks": len(selected),
        "chunks_by_edition": dict(Counter(documents[row["document_sha256"]]["edition"] for row in selected)),
        "model_tokens": {
            "minimum": min(token_counts),
            "maximum": max(token_counts),
            "average": round(sum(token_counts) / len(token_counts), 2),
        },
        "truncated_chunks": sum(truncated),
        "l2_norm": {
            "minimum": round(min(norms), 9),
            "maximum": round(max(norms), 9),
            "average": round(sum(norms) / len(norms), 9),
        },
        "environment": {
            "python": platform.python_version(),
            "sentence_transformers": sentence_transformers.__version__,
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "numpy": np.__version__,
            "device": "cpu",
            "torch_threads": torch.get_num_threads(),
        },
        "ready_for_database_import": sum(truncated) == 0 and all(abs(norm - 1.0) < 1e-5 for norm in norms),
    }
    (output_dir / "sample_embeddings_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("FIM | %s", json.dumps(summary, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Geração controlada de embeddings BGE-M3")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/sample_embeddings.log"))
    parser.add_argument("--cache-dir", type=Path, default=Path("models/huggingface"))
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--per-edition", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-sequence-length", type=int, default=1024)
    args = parser.parse_args()
    result = generate(
        args.chunks, args.documents, args.output_dir, args.log, args.cache_dir,
        args.model, args.revision, args.per_edition, args.batch_size,
        args.max_sequence_length,
    )
    return 0 if result["ready_for_database_import"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
