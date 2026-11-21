from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pypdf
from pypdf import PdfReader


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\x00", ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def select_sample(inventory: list[dict[str, str]]) -> list[dict[str, str]]:
    by_edition: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in inventory:
        if row["structure_ok"].lower() == "true":
            by_edition[int(row["edition"])].append(row)

    selected: list[dict[str, str]] = []
    for edition in range(1, 6):
        rows = sorted(by_edition[edition], key=lambda item: int(item["site_user_id"]))
        positions = [0, len(rows) // 3, (2 * len(rows)) // 3, len(rows) - 1]
        choices = [rows[position] for position in positions]
        multipage = next((row for row in rows if int(row["page_count"]) > 1), None)
        if multipage and multipage not in choices:
            choices[1] = multipage
        selected.extend(choices)
    return selected


def text_metrics(text: str) -> tuple[int, int, float, int, bool]:
    chars = len(text)
    alpha = sum(character.isalpha() for character in text)
    ratio = alpha / chars if chars else 0.0
    replacements = text.count("\ufffd")
    needs_ocr = chars < 100 or ratio < 0.30 or replacements > 0
    return chars, alpha, ratio, replacements, needs_ocr


def extract(inventory_path: Path, output_dir: Path, log_path: Path) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    with inventory_path.open("r", encoding="utf-8-sig", newline="") as stream:
        inventory = list(csv.DictReader(stream))
    sample = select_sample(inventory)
    if len(sample) != 20:
        raise ValueError(f"A amostra deveria conter 20 documentos, mas contém {len(sample)}")

    documents: list[dict[str, object]] = []
    pages: list[dict[str, object]] = []
    started = datetime.now(timezone.utc)
    for index, row in enumerate(sample, start=1):
        path = Path(row["file"])
        documents.append(
            {
                "sha256": row["sha256"],
                "edition": int(row["edition"]),
                "site_user_id": int(row["site_user_id"]),
                "participant_name": row["participant_name"],
                "source_path": str(path),
                "byte_size": int(row["actual_bytes"]),
                "page_count": int(row["page_count"]),
                "manifest_status": row["manifest_status"],
                "audited_at": started.isoformat(),
            }
        )
        reader = PdfReader(str(path), strict=False)
        for page_number, page in enumerate(reader.pages, start=1):
            extracted_at = datetime.now(timezone.utc).isoformat()
            error = ""
            try:
                raw_text = page.extract_text(extraction_mode="layout") or ""
                normalized = normalize_text(raw_text)
                status = "extracted" if normalized else "empty"
            except Exception as exc:
                raw_text = ""
                normalized = ""
                status = "error"
                error = f"{type(exc).__name__}: {exc}"[:500]
            _, alpha, ratio, replacements, needs_ocr = text_metrics(normalized)
            pages.append(
                {
                    "document_sha256": row["sha256"],
                    "page_number": page_number,
                    "raw_text": raw_text,
                    "normalized_text": normalized,
                    "alpha_count": alpha,
                    "alpha_ratio": f"{ratio:.6f}",
                    "replacement_char_count": replacements,
                    "extraction_status": status,
                    "extraction_method": "pypdf_layout",
                    "extractor_version": pypdf.__version__,
                    "text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                    if status != "error"
                    else "",
                    "needs_ocr": str(needs_ocr).lower(),
                    "extraction_error": error,
                    "extracted_at": extracted_at,
                }
            )
        logging.info("Extraído %d/20: edição %s, id %s", index, row["edition"], row["site_user_id"])

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("sample_documents.csv", documents), ("sample_pages.csv", pages)):
        # UTF-8 sem BOM evita que o primeiro nome de coluna seja alterado no COPY do PostgreSQL.
        with (output_dir / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    finished = datetime.now(timezone.utc)
    summary = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "extractor": "pypdf",
        "extractor_version": pypdf.__version__,
        "extraction_mode": "layout",
        "sampling": "4 documentos determinísticos por edição; inclui documento multipágina",
        "documents": len(documents),
        "pages": len(pages),
        "extracted_pages": sum(row["extraction_status"] == "extracted" for row in pages),
        "empty_pages": sum(row["extraction_status"] == "empty" for row in pages),
        "error_pages": sum(row["extraction_status"] == "error" for row in pages),
        "ocr_candidates": sum(row["needs_ocr"] == "true" for row in pages),
        "total_normalized_characters": sum(len(str(row["normalized_text"])) for row in pages),
        "ready_for_manual_review": True,
    }
    (output_dir / "sample_extraction_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info("Amostra concluída: %s", json.dumps(summary, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Extração textual da amostra do corpus")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/sample_extraction.log"))
    args = parser.parse_args()
    extract(args.inventory, args.output_dir, args.log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

