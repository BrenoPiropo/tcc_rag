from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from segment_sample import FIELDS, SECTION, segment_text, token_count


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("corpus_segmentation")
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
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def combine_batches(batch_dir: Path, output: Path) -> None:
    files = sorted(batch_dir.glob("chunks_*.csv"))
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


def segment_page(
    page: dict[str, str], created_at: str, target: int, maximum: int,
    minimum: int, overlap: int,
) -> tuple[list[dict[str, object]], int]:
    text = page["normalized_text"]
    chunks = segment_text(text, target, maximum, minimum, overlap)
    rows: list[dict[str, object]] = []
    coverage = [False] * len(text)
    previous_end = 0
    for chunk_index, chunk in enumerate(chunks, start=1):
        start = chunk["start"]
        end = chunk["end"]
        chunk_text = text[start:end]
        for position in range(start, end):
            coverage[position] = True
        section_labels = list(dict.fromkeys(match.group(1).upper() for match in SECTION.finditer(chunk_text)))
        chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        identity = f"{page['document_sha256']}:{page['page_number']}:{chunk_index}:{chunk_hash}"
        rows.append({
            "chunk_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "document_sha256": page["document_sha256"],
            "page_number": int(page["page_number"]),
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "char_start": start,
            "char_end": end,
            "lexical_token_count": token_count(chunk_text),
            "overlap_previous_tokens": token_count(text[start:previous_end]) if start < previous_end else 0,
            "section_labels": json.dumps(section_labels, ensure_ascii=False),
            "source_text_sha256": page["text_sha256"],
            "chunk_text_sha256": chunk_hash,
            "segmentation_method": "sentence_aware_lexical_overlap",
            "segmentation_version": "1.0.0",
            "created_at": created_at,
        })
        previous_end = end
    uncovered = sum(not covered and not character.isspace() for character, covered in zip(text, coverage))
    return rows, uncovered


def segment_corpus(
    pages_path: Path, documents_path: Path, output_dir: Path, log_path: Path,
    batch_size: int, target: int, maximum: int, minimum: int, overlap: int,
) -> dict[str, object]:
    logger = configure_logging(log_path)
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    with pages_path.open("r", encoding="utf-8-sig", newline="") as stream:
        pages = list(csv.DictReader(stream))
    with documents_path.open("r", encoding="utf-8-sig", newline="") as stream:
        editions = {row["sha256"]: row["edition"] for row in csv.DictReader(stream)}
    if not pages:
        raise ValueError("O arquivo de páginas está vazio")

    output_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = output_dir / "segmentation_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    total_batches = math.ceil(len(pages) / batch_size)
    created_at = started.isoformat()
    processed = 0
    total_uncovered = 0
    logger.info(
        "INÍCIO | páginas=%d | lotes=%d | alvo=%d | máximo=%d | mínimo=%d | sobreposição=%d",
        len(pages), total_batches, target, maximum, minimum, overlap,
    )

    for batch_number in range(1, total_batches + 1):
        first = (batch_number - 1) * batch_size
        batch_pages = pages[first:first + batch_size]
        stem = f"{batch_number:04d}"
        chunks_path = batch_dir / f"chunks_{stem}.csv"
        summary_path = batch_dir / f"summary_{stem}.json"
        if chunks_path.exists() and summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            processed += int(summary["pages"])
            total_uncovered += int(summary["uncovered_non_whitespace_characters"])
            logger.info("LOTE %d/%d REUTILIZADO | progresso=%d/%d", batch_number, total_batches, processed, len(pages))
            continue

        rows: list[dict[str, object]] = []
        uncovered = 0
        for page in batch_pages:
            page_rows, page_uncovered = segment_page(page, created_at, target, maximum, minimum, overlap)
            rows.extend(page_rows)
            uncovered += page_uncovered
            processed += 1
            if processed % 250 == 0 or processed == len(pages):
                logger.info("PROGRESSO | %d/%d páginas (%.1f%%)", processed, len(pages), processed * 100 / len(pages))
        write_csv_atomic(chunks_path, rows)
        token_values = [int(row["lexical_token_count"]) for row in rows]
        summary = {
            "batch": batch_number,
            "pages": len(batch_pages),
            "chunks": len(rows),
            "tokens_min": min(token_values),
            "tokens_max": max(token_values),
            "tokens_total": sum(token_values),
            "uncovered_non_whitespace_characters": uncovered,
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        total_uncovered += uncovered
        logger.info("LOTE %d/%d CONCLUÍDO | páginas=%d | fragmentos=%d | não_cobertos=%d", batch_number, total_batches, len(batch_pages), len(rows), uncovered)

    output_path = output_dir / "corpus_chunks.csv"
    combine_batches(batch_dir, output_path)

    identifiers: set[str] = set()
    document_ids: set[str] = set()
    page_ids: set[tuple[str, str]] = set()
    tokens: list[int] = []
    chunks_per_page: Counter[tuple[str, str]] = Counter()
    chunks_by_edition: Counter[str] = Counter()
    duplicate_ids = 0
    with output_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["chunk_id"] in identifiers:
                duplicate_ids += 1
            identifiers.add(row["chunk_id"])
            document_ids.add(row["document_sha256"])
            page_key = (row["document_sha256"], row["page_number"])
            page_ids.add(page_key)
            chunks_per_page[page_key] += 1
            chunks_by_edition[editions[row["document_sha256"]]] += 1
            tokens.append(int(row["lexical_token_count"]))

    finished = datetime.now(timezone.utc)
    result = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "duration_seconds": round(time.monotonic() - clock, 3),
        "source_pages_sha256": hashlib.sha256(pages_path.read_bytes()).hexdigest(),
        "documents": len(document_ids),
        "pages": len(page_ids),
        "chunks": len(tokens),
        "parameters": {
            "target_lexical_tokens": target,
            "maximum_lexical_tokens": maximum,
            "minimum_desired_lexical_tokens": minimum,
            "desired_overlap_lexical_tokens": overlap,
            "batch_size_pages": batch_size,
        },
        "lexical_tokens_per_chunk": {
            "minimum": min(tokens),
            "maximum": max(tokens),
            "average": round(sum(tokens) / len(tokens), 2),
        },
        "chunks_per_page": {
            "minimum": min(chunks_per_page.values()),
            "maximum": max(chunks_per_page.values()),
            "average": round(sum(chunks_per_page.values()) / len(chunks_per_page), 2),
        },
        "chunks_by_edition": dict(sorted(chunks_by_edition.items())),
        "uncovered_non_whitespace_characters": total_uncovered,
        "duplicate_chunk_ids": duplicate_ids,
        "segmentation_method": "sentence_aware_lexical_overlap",
        "segmentation_version": "1.0.0",
        "provisional_token_definition": "Unicode lexical units; model tokenizer will be measured after embedding-model selection",
        "output_csv": str(output_path.resolve()),
        "completed": len(page_ids) == len(pages) and total_uncovered == 0 and duplicate_ids == 0,
    }
    (output_dir / "corpus_segmentation_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("FIM | %s", json.dumps(result, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Segmentação integral dos Anais da SIC/UESC")
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/corpus_segmentation.log"))
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--target", type=int, default=450)
    parser.add_argument("--maximum", type=int, default=520)
    parser.add_argument("--minimum", type=int, default=120)
    parser.add_argument("--overlap", type=int, default=75)
    args = parser.parse_args()
    result = segment_corpus(
        args.pages, args.documents, args.output_dir, args.log, args.batch_size,
        args.target, args.maximum, args.minimum, args.overlap,
    )
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
