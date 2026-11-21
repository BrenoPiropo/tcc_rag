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

import pypdf
from pypdf import PdfReader

from extract_sample import normalize_text, text_metrics


DOCUMENT_FIELDS = [
    "sha256", "edition", "site_user_id", "participant_name", "source_path",
    "byte_size", "page_count", "manifest_status", "audited_at",
]
PAGE_FIELDS = [
    "document_sha256", "page_number", "raw_text", "normalized_text",
    "alpha_count", "alpha_ratio", "replacement_char_count", "extraction_status",
    "extraction_method", "extractor_version", "text_sha256", "needs_ocr",
    "extraction_error", "extracted_at",
]


def configure_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("corpus_extraction")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return logger


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def page_row(document_hash: str, page_number: int, raw_text: str, error: str = "") -> dict[str, object]:
    normalized = normalize_text(raw_text) if not error else ""
    status = "error" if error else ("extracted" if normalized else "empty")
    _, alpha, ratio, replacements, needs_ocr = text_metrics(normalized)
    return {
        "document_sha256": document_hash,
        "page_number": page_number,
        "raw_text": raw_text,
        "normalized_text": normalized,
        "alpha_count": alpha,
        "alpha_ratio": f"{ratio:.6f}",
        "replacement_char_count": replacements,
        "extraction_status": status,
        "extraction_method": "pypdf_layout",
        "extractor_version": pypdf.__version__,
        "text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest() if not error else "",
        "needs_ocr": str(needs_ocr).lower(),
        "extraction_error": error[:500],
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_document(row: dict[str, str], audited_at: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    path = Path(row["file"])
    declared_pages = int(row["page_count"])
    pages: list[dict[str, object]] = []
    try:
        reader = PdfReader(str(path), strict=False)
        actual_pages = len(reader.pages)
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text(extraction_mode="layout") or ""
                pages.append(page_row(row["sha256"], page_number, raw_text))
            except Exception as exc:
                pages.append(page_row(row["sha256"], page_number, "", f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        actual_pages = declared_pages
        error = f"{type(exc).__name__}: {exc}"
        pages = [page_row(row["sha256"], number, "", error) for number in range(1, declared_pages + 1)]

    document = {
        "sha256": row["sha256"],
        "edition": int(row["edition"]),
        "site_user_id": int(row["site_user_id"]),
        "participant_name": row["participant_name"],
        "source_path": str(path),
        "byte_size": int(row["actual_bytes"]),
        "page_count": actual_pages,
        "manifest_status": row["manifest_status"],
        "audited_at": audited_at,
    }
    return document, pages


def batch_summary(documents: list[dict[str, object]], pages: list[dict[str, object]]) -> dict[str, object]:
    statuses = Counter(str(page["extraction_status"]) for page in pages)
    return {
        "documents": len(documents),
        "pages": len(pages),
        "extracted_pages": statuses["extracted"],
        "empty_pages": statuses["empty"],
        "error_pages": statuses["error"],
        "ocr_candidates": sum(page["needs_ocr"] == "true" for page in pages),
        "normalized_characters": sum(len(str(page["normalized_text"])) for page in pages),
        "documents_by_edition": dict(Counter(str(doc["edition"]) for doc in documents)),
    }


def combine_batches(batch_dir: Path, pattern: str, output: Path) -> None:
    files = sorted(batch_dir.glob(pattern))
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


def extract_corpus(inventory_path: Path, output_dir: Path, log_path: Path, batch_size: int) -> dict[str, object]:
    logger = configure_logging(log_path)
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    with inventory_path.open("r", encoding="utf-8-sig", newline="") as stream:
        inventory = [row for row in csv.DictReader(stream) if row["structure_ok"].lower() == "true"]
    if not inventory:
        raise ValueError("O inventário não contém documentos estruturalmente válidos")

    output_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = output_dir / "extraction_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    audited_at = datetime.fromtimestamp(inventory_path.stat().st_mtime, timezone.utc).isoformat()
    total_batches = math.ceil(len(inventory) / batch_size)
    summaries: list[dict[str, object]] = []
    processed = 0
    logger.info("INÍCIO | documentos=%d | lotes=%d | tamanho_lote=%d", len(inventory), total_batches, batch_size)

    for batch_number in range(1, total_batches + 1):
        first = (batch_number - 1) * batch_size
        rows = inventory[first:first + batch_size]
        stem = f"{batch_number:04d}"
        documents_path = batch_dir / f"documents_{stem}.csv"
        pages_path = batch_dir / f"pages_{stem}.csv"
        summary_path = batch_dir / f"summary_{stem}.json"
        if documents_path.exists() and pages_path.exists() and summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summaries.append(summary)
            processed += int(summary["documents"])
            logger.info("LOTE %d/%d REUTILIZADO | progresso=%d/%d", batch_number, total_batches, processed, len(inventory))
            continue

        documents: list[dict[str, object]] = []
        pages: list[dict[str, object]] = []
        for row in rows:
            document, document_pages = extract_document(row, audited_at)
            documents.append(document)
            pages.extend(document_pages)
            processed += 1
            if processed % 100 == 0 or processed == len(inventory):
                logger.info("PROGRESSO | %d/%d documentos (%.1f%%)", processed, len(inventory), processed * 100 / len(inventory))

        write_csv_atomic(documents_path, DOCUMENT_FIELDS, documents)
        write_csv_atomic(pages_path, PAGE_FIELDS, pages)
        summary = batch_summary(documents, pages)
        summary.update({"batch": batch_number, "first_inventory_row": first + 1, "last_inventory_row": first + len(rows)})
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summaries.append(summary)
        logger.info(
            "LOTE %d/%d CONCLUÍDO | documentos=%d | páginas=%d | erros=%d | OCR=%d",
            batch_number, total_batches, summary["documents"], summary["pages"],
            summary["error_pages"], summary["ocr_candidates"],
        )

    documents_output = output_dir / "corpus_documents.csv"
    pages_output = output_dir / "corpus_pages.csv"
    combine_batches(batch_dir, "documents_*.csv", documents_output)
    combine_batches(batch_dir, "pages_*.csv", pages_output)

    totals = Counter()
    editions = Counter()
    for summary in summaries:
        for key in ("documents", "pages", "extracted_pages", "empty_pages", "error_pages", "ocr_candidates", "normalized_characters"):
            totals[key] += int(summary[key])
        editions.update({key: int(value) for key, value in dict(summary["documents_by_edition"]).items()})

    finished = datetime.now(timezone.utc)
    result = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "duration_seconds": round(time.monotonic() - clock, 3),
        "inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        "extractor": "pypdf",
        "extractor_version": pypdf.__version__,
        "extraction_mode": "layout",
        "batch_size": batch_size,
        "batches": total_batches,
        **dict(totals),
        "documents_by_edition": dict(sorted(editions.items())),
        "ocr_rule": "chars < 100 OR alpha_ratio < 0.30 OR replacement_chars > 0",
        "documents_csv": str(documents_output.resolve()),
        "pages_csv": str(pages_output.resolve()),
        "completed": totals["documents"] == len(inventory),
    }
    (output_dir / "corpus_extraction_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("FIM | %s", json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extração integral do corpus dos Anais da SIC/UESC")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/corpus_extraction.log"))
    parser.add_argument("--batch-size", type=int, default=250)
    args = parser.parse_args()
    result = extract_corpus(args.inventory, args.output_dir, args.log, args.batch_size)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
