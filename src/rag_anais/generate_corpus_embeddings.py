from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import platform
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sentence_transformers
import torch
import transformers
from sentence_transformers import SentenceTransformer

from generate_sample_embeddings import EMBEDDING_FIELDS, MODEL_FIELDS, vector_text


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("corpus_embeddings")
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


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EMBEDDING_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def combine_batches(batch_dir: Path, output: Path) -> None:
    files = sorted(batch_dir.glob("embeddings_*.csv"))
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as target:
        for index, source in enumerate(files):
            with source.open("r", encoding="utf-8", newline="") as stream:
                header = stream.readline()
                if index == 0:
                    target.write(header)
                for line in stream:
                    target.write(line)
    temporary.replace(output)


def cache_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def generate(
    chunks_path: Path, documents_path: Path, output_dir: Path, log_path: Path,
    cache_dir: Path, model_name: str, revision: str, checkpoint_size: int,
    encode_batch_size: int, max_sequence_length: int,
) -> dict[str, object]:
    logger = configure_logging(log_path)
    started = datetime.now(timezone.utc)
    wall_clock = time.monotonic()
    model_key = f"{model_name}@{revision}"
    with chunks_path.open("r", encoding="utf-8", newline="") as stream:
        chunks = list(csv.DictReader(stream))
    with documents_path.open("r", encoding="utf-8", newline="") as stream:
        documents = {row["sha256"]: row for row in csv.DictReader(stream)}
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = output_dir / "corpus_embedding_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(max(1, min(6, torch.get_num_threads())))
    logger.info(
        "INÍCIO | modelo=%s | revisão=%s | fragmentos=%d | checkpoint=%d | lote_inferência=%d",
        model_name, revision, len(chunks), checkpoint_size, encode_batch_size,
    )

    load_started = time.monotonic()
    model = SentenceTransformer(
        model_name,
        revision=revision,
        device="cpu",
        cache_folder=str(cache_dir),
        trust_remote_code=False,
        local_files_only=True,
    )
    model.max_seq_length = max_sequence_length
    dimension = int(model.get_embedding_dimension())
    if dimension != 1024:
        raise ValueError(f"Dimensão inesperada: {dimension}; esperado: 1024")
    load_seconds = time.monotonic() - load_started
    logger.info("MODELO CARREGADO | dimensão=%d | segundos=%.3f", dimension, load_seconds)

    created_at = started.isoformat()
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
    with (output_dir / "corpus_embedding_model.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MODEL_FIELDS)
        writer.writeheader()
        writer.writerow(model_row)

    total_batches = math.ceil(len(chunks) / checkpoint_size)
    total_inference_seconds = 0.0
    processed = 0
    for batch_number in range(1, total_batches + 1):
        first = (batch_number - 1) * checkpoint_size
        batch_chunks = chunks[first:first + checkpoint_size]
        stem = f"{batch_number:04d}"
        embeddings_path = batch_dir / f"embeddings_{stem}.csv"
        summary_path = batch_dir / f"summary_{stem}.json"
        if embeddings_path.exists() and summary_path.exists():
            batch_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if batch_summary["model_key"] != model_key:
                raise ValueError(f"Lote {batch_number} pertence a outro modelo")
            processed += int(batch_summary["embeddings"])
            total_inference_seconds += float(batch_summary["inference_seconds"])
            logger.info("CHECKPOINT %d/%d REUTILIZADO | progresso=%d/%d", batch_number, total_batches, processed, len(chunks))
            continue

        texts = [row["chunk_text"] for row in batch_chunks]
        token_counts = [
            len(model.tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"])
            for text in texts
        ]
        if max(token_counts) > max_sequence_length:
            raise ValueError(f"Checkpoint {batch_number} excede {max_sequence_length} tokens")
        inference_started = time.monotonic()
        vectors = np.asarray(
            model.encode(
                texts,
                batch_size=encode_batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )
        inference_seconds = time.monotonic() - inference_started
        total_inference_seconds += inference_seconds
        rows: list[dict[str, object]] = []
        norms: list[float] = []
        for chunk, token_count, vector in zip(batch_chunks, token_counts, vectors):
            norm = float(np.linalg.norm(vector))
            norms.append(norm)
            rows.append({
                "chunk_id": chunk["chunk_id"],
                "model_key": model_key,
                "model_token_count": token_count,
                "truncated": "false",
                "l2_norm": f"{norm:.9f}",
                "embedding": vector_text(vector),
                "created_at": created_at,
            })
        write_csv_atomic(embeddings_path, rows)
        batch_summary = {
            "batch": batch_number,
            "model_key": model_key,
            "embeddings": len(rows),
            "inference_seconds": round(inference_seconds, 3),
            "token_minimum": min(token_counts),
            "token_maximum": max(token_counts),
            "norm_minimum": min(norms),
            "norm_maximum": max(norms),
        }
        summary_path.write_text(json.dumps(batch_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        processed += len(rows)
        rate = processed / max(total_inference_seconds, 0.001)
        eta_minutes = (len(chunks) - processed) / max(rate, 0.001) / 60
        logger.info(
            "CHECKPOINT %d/%d | progresso=%d/%d (%.1f%%) | segundos=%.2f | ETA=%.1f min",
            batch_number, total_batches, processed, len(chunks), processed * 100 / len(chunks),
            inference_seconds, eta_minutes,
        )

    output_path = output_dir / "corpus_embeddings.csv"
    combine_batches(batch_dir, output_path)

    identifiers: set[str] = set()
    token_counts: list[int] = []
    norms: list[float] = []
    duplicate_ids = 0
    truncated_count = 0
    with output_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["chunk_id"] in identifiers:
                duplicate_ids += 1
            identifiers.add(row["chunk_id"])
            token_counts.append(int(row["model_token_count"]))
            norms.append(float(row["l2_norm"]))
            truncated_count += row["truncated"].lower() == "true"

    chunks_by_edition = Counter(
        documents[row["document_sha256"]]["edition"] for row in chunks
    )
    finished = datetime.now(timezone.utc)
    summary = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "wall_duration_seconds": round(time.monotonic() - wall_clock, 3),
        "model_load_seconds": round(load_seconds, 3),
        "inference_seconds": round(total_inference_seconds, 3),
        "model_name": model_name,
        "model_revision": revision,
        "model_key": model_key,
        "dimension": dimension,
        "max_sequence_length": max_sequence_length,
        "normalized": True,
        "embeddings": len(token_counts),
        "embeddings_by_edition": dict(sorted(chunks_by_edition.items())),
        "model_tokens": {
            "minimum": min(token_counts),
            "maximum": max(token_counts),
            "average": round(sum(token_counts) / len(token_counts), 2),
        },
        "truncated_embeddings": truncated_count,
        "duplicate_chunk_ids": duplicate_ids,
        "l2_norm": {
            "minimum": min(norms),
            "maximum": max(norms),
            "average": round(sum(norms) / len(norms), 9),
        },
        "throughput_embeddings_per_second": round(len(token_counts) / total_inference_seconds, 3),
        "checkpoint_size": checkpoint_size,
        "encode_batch_size": encode_batch_size,
        "model_cache_bytes": cache_size(cache_dir),
        "environment": {
            "python": platform.python_version(),
            "sentence_transformers": sentence_transformers.__version__,
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "numpy": np.__version__,
            "device": "cpu",
            "torch_threads": torch.get_num_threads(),
        },
        "output_csv": str(output_path.resolve()),
        "completed": len(token_counts) == len(chunks) and truncated_count == 0 and duplicate_ids == 0,
    }
    (output_dir / "corpus_embeddings_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("FIM | %s", json.dumps(summary, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Geração integral e retomável dos embeddings do corpus")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/corpus_embeddings.log"))
    parser.add_argument("--cache-dir", type=Path, default=Path("models/huggingface"))
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--checkpoint-size", type=int, default=32)
    parser.add_argument("--encode-batch-size", type=int, default=4)
    parser.add_argument("--max-sequence-length", type=int, default=1024)
    args = parser.parse_args()
    result = generate(
        args.chunks, args.documents, args.output_dir, args.log, args.cache_dir,
        args.model, args.revision, args.checkpoint_size, args.encode_batch_size,
        args.max_sequence_length,
    )
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
