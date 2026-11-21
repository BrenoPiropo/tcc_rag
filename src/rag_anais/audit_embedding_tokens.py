from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import transformers
from transformers import AutoTokenizer


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria do tamanho dos fragmentos no tokenizer do modelo")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--max-sequence-length", type=int, default=1024)
    args = parser.parse_args()

    args.log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(args.log, encoding="utf-8"), logging.StreamHandler()],
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.revision,
        cache_dir=str(args.cache_dir),
        local_files_only=True,
    )
    counts: list[int] = []
    with args.chunks.open("r", encoding="utf-8", newline="") as stream:
        for position, row in enumerate(csv.DictReader(stream), start=1):
            count = len(tokenizer(row["chunk_text"], add_special_tokens=True, truncation=False)["input_ids"])
            counts.append(count)
            if position % 500 == 0:
                logging.info("PROGRESSO | %d fragmentos", position)

    values = np.asarray(counts, dtype=np.int32)
    summary = {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": args.model,
        "model_revision": args.revision,
        "transformers_version": transformers.__version__,
        "chunks": len(counts),
        "model_tokens": {
            "minimum": int(values.min()),
            "maximum": int(values.max()),
            "average": round(float(values.mean()), 2),
            "median": round(float(np.median(values)), 2),
            "percentile_95": round(float(np.percentile(values, 95)), 2),
            "percentile_99": round(float(np.percentile(values, 99)), 2),
        },
        "above_512": int(np.sum(values > 512)),
        "above_configured_max": int(np.sum(values > args.max_sequence_length)),
        "configured_max_sequence_length": args.max_sequence_length,
        "result": "approved" if not np.any(values > args.max_sequence_length) else "requires_adjustment",
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("FIM | %s", json.dumps(summary, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["result"] == "approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
