from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


LEXICAL_TOKEN = re.compile(r"\w+(?:[-’']\w+)*|[^\w\s]", re.UNICODE)
SENTENCE_END = re.compile(r"[.!?](?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])")
SECTION = re.compile(
    r"\b(INTRODUÇÃO|OBJETIVOS?|MATERIAIS? E MÉTODOS|METODOLOGIA|"
    r"RESULTADOS(?: E DISCUSSÃO)?|CONCLUS(?:ÃO|ÕES)|PALAVRAS[- ]CHAVE)\b",
    re.IGNORECASE,
)
FIELDS = [
    "chunk_id", "document_sha256", "page_number", "chunk_index", "chunk_text",
    "char_start", "char_end", "lexical_token_count", "overlap_previous_tokens",
    "section_labels", "source_text_sha256", "chunk_text_sha256",
    "segmentation_method", "segmentation_version", "created_at",
]


def token_count(text: str) -> int:
    return sum(1 for _ in LEXICAL_TOKEN.finditer(text))


def units_from_text(text: str, maximum: int) -> list[dict[str, int]]:
    units: list[dict[str, int]] = []
    for line_match in re.finditer(r"[^\n]+", text):
        line = line_match.group()
        left = len(line) - len(line.lstrip())
        right = len(line.rstrip())
        if right <= left:
            continue
        line_start = line_match.start() + left
        content = text[line_start:line_match.start() + right]
        boundaries = [0]
        boundaries.extend(match.end() for match in SENTENCE_END.finditer(content))
        boundaries.append(len(content))
        for first, last in zip(boundaries, boundaries[1:]):
            while first < last and content[first].isspace():
                first += 1
            while last > first and content[last - 1].isspace():
                last -= 1
            if first >= last:
                continue
            start = line_start + first
            end = line_start + last
            tokens = list(LEXICAL_TOKEN.finditer(text, start, end))
            if len(tokens) <= maximum:
                units.append({"start": start, "end": end, "tokens": len(tokens)})
                continue
            for offset in range(0, len(tokens), maximum):
                part = tokens[offset:offset + maximum]
                units.append({"start": part[0].start(), "end": part[-1].end(), "tokens": len(part)})
    return units


def segment_text(text: str, target: int, maximum: int, minimum: int, overlap: int) -> list[dict[str, int]]:
    units = units_from_text(text, maximum)
    if not units:
        return []
    chunks: list[dict[str, int]] = []
    start_index = 0
    while start_index < len(units):
        end_index = start_index
        total = 0
        while end_index < len(units):
            candidate = total + units[end_index]["tokens"]
            if end_index > start_index and candidate > maximum:
                break
            if end_index > start_index and total >= minimum and candidate > target:
                break
            total = candidate
            end_index += 1
            if total >= target:
                break
        if end_index == start_index:
            end_index += 1
            total = units[start_index]["tokens"]
        chunks.append({
            "start": units[start_index]["start"],
            "end": units[end_index - 1]["end"],
            "tokens": total,
        })
        if end_index >= len(units):
            break
        next_start = end_index
        overlap_total = 0
        while next_start > start_index and overlap_total < overlap:
            next_start -= 1
            overlap_total += units[next_start]["tokens"]
        if next_start == start_index:
            next_start = end_index
        start_index = next_start
    return chunks


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sample_segmentation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    for handler in (logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def run(input_path: Path, output_dir: Path, log_path: Path, target: int, maximum: int, minimum: int, overlap: int) -> dict[str, object]:
    logger = configure_logging(log_path)
    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        pages = list(csv.DictReader(stream))
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []
    uncovered_non_whitespace = 0

    logger.info(
        "INÍCIO | páginas=%d | alvo=%d | máximo=%d | mínimo=%d | sobreposição=%d",
        len(pages), target, maximum, minimum, overlap,
    )
    for page_position, page in enumerate(pages, start=1):
        text = page["normalized_text"]
        chunks = segment_text(text, target, maximum, minimum, overlap)
        coverage = [False] * len(text)
        previous_end = 0
        for chunk_index, chunk in enumerate(chunks, start=1):
            start = chunk["start"]
            end = chunk["end"]
            chunk_text = text[start:end]
            for position in range(start, end):
                coverage[position] = True
            actual_overlap = token_count(text[start:previous_end]) if start < previous_end else 0
            chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            identity = f"{page['document_sha256']}:{page['page_number']}:{chunk_index}:{chunk_hash}"
            labels = list(dict.fromkeys(match.group(1).upper() for match in SECTION.finditer(chunk_text)))
            rows.append({
                "chunk_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "document_sha256": page["document_sha256"],
                "page_number": int(page["page_number"]),
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "char_start": start,
                "char_end": end,
                "lexical_token_count": token_count(chunk_text),
                "overlap_previous_tokens": actual_overlap,
                "section_labels": json.dumps(labels, ensure_ascii=False),
                "source_text_sha256": page["text_sha256"],
                "chunk_text_sha256": chunk_hash,
                "segmentation_method": "sentence_aware_lexical_overlap",
                "segmentation_version": "1.0.0",
                "created_at": created_at,
            })
            previous_end = end
        uncovered_non_whitespace += sum(
            not covered and not character.isspace()
            for character, covered in zip(text, coverage)
        )
        logger.info(
            "PÁGINA %d/%d | documento=%s | página=%s | fragmentos=%d",
            page_position, len(pages), page["document_sha256"][:12], page["page_number"], len(chunks),
        )

    csv_path = output_dir / "sample_chunks.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    document_metadata: dict[str, dict[str, str]] = {}
    documents_path = output_dir / "sample_documents.csv"
    if documents_path.exists():
        with documents_path.open("r", encoding="utf-8-sig", newline="") as stream:
            document_metadata = {row["sha256"]: row for row in csv.DictReader(stream)}
    review_lines = [
        "# Revisão da amostra de fragmentos",
        "",
        "Cada seção abaixo mostra exatamente o texto que será representado por um embedding.",
        "",
    ]
    current_document = ""
    for row in rows:
        document_hash = str(row["document_sha256"])
        if document_hash != current_document:
            metadata = document_metadata.get(document_hash, {})
            review_lines.extend([
                f"## Edição {metadata.get('edition', '?')} - ID {metadata.get('site_user_id', '?')} - {metadata.get('participant_name', 'participante não identificado')}",
                "",
                f"Documento: `{document_hash}`",
                "",
            ])
            current_document = document_hash
        review_lines.extend([
            f"### Página {row['page_number']} - fragmento {row['chunk_index']}",
            "",
            f"Unidades lexicais: {row['lexical_token_count']} | Sobreposição anterior: {row['overlap_previous_tokens']} | Seções: {row['section_labels']}",
            "",
            str(row["chunk_text"]),
            "",
            "---",
            "",
        ])
    (output_dir / "sample_chunks_review.md").write_text("\n".join(review_lines), encoding="utf-8")

    token_values = [int(row["lexical_token_count"]) for row in rows]
    per_page = Counter((row["document_sha256"], row["page_number"]) for row in rows)
    summary = {
        "created_at_utc": created_at,
        "scope": "approved_extraction_sample",
        "documents": len({row["document_sha256"] for row in rows}),
        "pages": len(pages),
        "chunks": len(rows),
        "parameters": {
            "target_lexical_tokens": target,
            "maximum_lexical_tokens": maximum,
            "minimum_lexical_tokens": minimum,
            "desired_overlap_lexical_tokens": overlap,
        },
        "lexical_tokens_per_chunk": {
            "minimum": min(token_values),
            "maximum": max(token_values),
            "average": round(sum(token_values) / len(token_values), 2),
        },
        "chunks_per_page": {
            "minimum": min(per_page.values()),
            "maximum": max(per_page.values()),
            "average": round(sum(per_page.values()) / len(per_page), 2),
        },
        "uncovered_non_whitespace_characters": uncovered_non_whitespace,
        "duplicate_chunk_ids": len(rows) - len({row["chunk_id"] for row in rows}),
        "provisional_token_definition": "Unicode lexical units; model tokenizer will be measured after embedding-model selection",
        "ready_for_manual_review": uncovered_non_whitespace == 0,
    }
    (output_dir / "sample_segmentation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("FIM | %s", json.dumps(summary, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Segmentação da amostra textual dos Anais da SIC/UESC")
    parser.add_argument("--input", type=Path, default=Path("artifacts/sample_pages.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/sample_segmentation.log"))
    parser.add_argument("--target", type=int, default=450)
    parser.add_argument("--maximum", type=int, default=520)
    parser.add_argument("--minimum", type=int, default=120)
    parser.add_argument("--overlap", type=int, default=75)
    args = parser.parse_args()
    result = run(args.input, args.output_dir, args.log, args.target, args.maximum, args.minimum, args.overlap)
    return 0 if result["ready_for_manual_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
