from __future__ import annotations

import logging
from pathlib import Path

from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "BAAI/bge-reranker-v2-m3"
MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
MODEL_CACHE = ROOT / "models" / "huggingface"
LOG_PATH = ROOT / "logs" / "reranker_v2_download.log"


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.info("INÍCIO | modelo=%s | revisão=%s", MODEL_NAME, MODEL_REVISION)
    snapshot = snapshot_download(
        repo_id=MODEL_NAME,
        revision=MODEL_REVISION,
        cache_dir=MODEL_CACHE,
    )
    logging.info("CONCLUÍDO | caminho=%s", snapshot)


if __name__ == "__main__":
    main()

