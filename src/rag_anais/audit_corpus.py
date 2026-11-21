from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


EXPECTED_COLUMNS = {"timestamp", "edition", "user_id", "name", "file", "bytes", "status"}
EXPECTED_EDITIONS = {1, 2, 3, 4, 5}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def audit_pdf(row: dict[str, str]) -> dict[str, object]:
    path = Path(row["file"])
    edition = int(row["edition"])
    reported_bytes = int(row["bytes"])
    result: dict[str, object] = {
        "edition": edition,
        "site_user_id": int(row["user_id"]),
        "participant_name": row["name"].strip(),
        "file": str(path),
        "manifest_status": row["status"].strip(),
        "reported_bytes": reported_bytes,
        "exists": path.is_file(),
        "actual_bytes": None,
        "size_matches": False,
        "pdf_signature": False,
        "structure_ok": False,
        "encrypted": False,
        "page_count": None,
        "sha256": None,
        "error": "",
    }
    if not path.is_file():
        result["error"] = "arquivo ausente"
        return result

    try:
        result["actual_bytes"] = path.stat().st_size
        result["size_matches"] = result["actual_bytes"] == reported_bytes
        with path.open("rb") as stream:
            result["pdf_signature"] = stream.read(5) == b"%PDF-"
        result["sha256"] = sha256_file(path)

        reader = PdfReader(str(path), strict=False)
        result["encrypted"] = reader.is_encrypted
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise ValueError("PDF criptografado sem senha vazia")
        result["page_count"] = len(reader.pages)
        result["structure_ok"] = result["page_count"] > 0
    except Exception as exc:  # registra e continua para auditar todo o corpus
        result["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return result


def write_inventory(rows: list[dict[str, object]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit(manifest: Path, output_dir: Path, log_path: Path) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing_columns = EXPECTED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"Colunas ausentes no manifesto: {sorted(missing_columns)}")
        manifest_rows = list(reader)

    logging.info("Auditoria iniciada: %d registros", len(manifest_rows))
    inventory: list[dict[str, object]] = []
    for index, row in enumerate(manifest_rows, start=1):
        inventory.append(audit_pdf(row))
        if index % 100 == 0 or index == len(manifest_rows):
            logging.info("Progresso: %d/%d", index, len(manifest_rows))

    hash_groups: dict[str, list[str]] = defaultdict(list)
    key_groups: dict[tuple[int, int], int] = Counter()
    for item in inventory:
        if item["sha256"]:
            hash_groups[str(item["sha256"])].append(str(item["file"]))
        key_groups[(int(item["edition"]), int(item["site_user_id"]))] += 1

    duplicate_hashes = {
        digest: files for digest, files in sorted(hash_groups.items()) if len(files) > 1
    }
    duplicate_keys = [
        {"edition": edition, "site_user_id": user_id, "count": count}
        for (edition, user_id), count in sorted(key_groups.items())
        if count > 1
    ]
    edition_counts = Counter(int(item["edition"]) for item in inventory)
    status_counts = Counter(str(item["manifest_status"]) for item in inventory)
    page_counts = [int(item["page_count"]) for item in inventory if item["page_count"]]

    critical = sum(
        1
        for item in inventory
        if not item["exists"]
        or not item["size_matches"]
        or not item["pdf_signature"]
        or not item["structure_ok"]
        or item["manifest_status"].upper() != "OK"
        or int(item["edition"]) not in EXPECTED_EDITIONS
    )
    summary: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest.resolve()),
        "manifest_sha256": sha256_file(manifest),
        "records": len(inventory),
        "edition_counts": dict(sorted(edition_counts.items())),
        "manifest_status_counts": dict(sorted(status_counts.items())),
        "existing_files": sum(bool(item["exists"]) for item in inventory),
        "matching_sizes": sum(bool(item["size_matches"]) for item in inventory),
        "valid_pdf_signatures": sum(bool(item["pdf_signature"]) for item in inventory),
        "structurally_readable_pdfs": sum(bool(item["structure_ok"]) for item in inventory),
        "encrypted_pdfs": sum(bool(item["encrypted"]) for item in inventory),
        "total_bytes": sum(int(item["actual_bytes"] or 0) for item in inventory),
        "total_pages": sum(page_counts),
        "minimum_pages": min(page_counts) if page_counts else 0,
        "maximum_pages": max(page_counts) if page_counts else 0,
        "duplicate_manifest_keys": duplicate_keys,
        "duplicate_content_groups": duplicate_hashes,
        "duplicate_content_group_count": len(duplicate_hashes),
        "critical_record_count": critical,
        "ready_for_text_extraction": critical == 0,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_inventory(inventory, output_dir / "corpus_inventory.csv")
    (output_dir / "corpus_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info("Auditoria concluída: %s", json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria somente leitura do corpus SIC/UESC")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--log", type=Path, default=Path("logs/corpus_audit.log"))
    args = parser.parse_args()
    summary = audit(args.manifest, args.output_dir, args.log)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_text_extraction"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

