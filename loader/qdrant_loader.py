import json
import os
import sys
import traceback
import logging
from pathlib import Path
import hashlib
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, PayloadSchemaType, PointIdsList

# Example how to run it python qdrant_loader.py AMD "gemma4:e4b"

# Ensure project root is importable when script is run from loader/ directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "stock_news_summaries")
VECTOR_DIM = int(os.getenv("QDRANT_VECTOR_DIM", "768"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


def embed_text(text: str) -> list[float]:
    clean_text = (text or "").replace("\n", " ").strip()
    if not clean_text:
        raise ValueError("Cannot embed empty text.")

    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": clean_text},
        timeout=60,
    )
    response.raise_for_status()
    vector = list(response.json().get("embedding", []))
    if len(vector) != VECTOR_DIM:
        raise RuntimeError(
            f"Embedding dim mismatch for model '{EMBEDDING_MODEL}'. "
            f"Expected {VECTOR_DIM}, got {len(vector)}."
        )
    return vector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://host.docker.internal:6333"))


def ensure_collection() -> None:
    """
    Create the collection if missing, validate vector size, and ensure payload indexes.
    """
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info("Created collection '%s' with dim=%s", COLLECTION_NAME, VECTOR_DIM)
    else:
        info = qdrant_client.get_collection(COLLECTION_NAME)
        cfg = info.config.params.vectors
        current_dim = cfg.size if hasattr(cfg, "size") else None
        if current_dim != VECTOR_DIM:
            raise RuntimeError(
                f"Collection '{COLLECTION_NAME}' has dim={current_dim}, but loader expects {VECTOR_DIM}. "
                "Set QDRANT_VECTOR_DIM to match, or recreate the collection."
            )

    # Ensure payload indexes for fast filtered queries
    for field, schema in [
        ("model",           PayloadSchemaType.KEYWORD),
        ("stock",           PayloadSchemaType.KEYWORD),
        ("date",            PayloadSchemaType.KEYWORD),
        ("sentiment_score", PayloadSchemaType.FLOAT),
    ]:
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=schema,
        )
    logger.info("Payload indexes ensured for model, stock, date, sentiment_score")


def qdrant_upsert(id, summary, url, stock, date, model, sentiment_score=None):
    vector = embed_text(summary)
    payload = {
        "summary": summary,
        "url": url,
        "stock": stock,
        "date": date,
        "model": model,
    }
    if sentiment_score is not None:
        payload["sentiment_score"] = sentiment_score
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=id, vector=vector, payload=payload)],
    )


def make_id(symbol: str, published_date: str, url: str, model: str = "", debug=False) -> str:
    raw = f"{symbol}|{published_date}|{url}|{model}".encode("utf-8")
    id = hashlib.sha256(raw).hexdigest()[:32]
    if debug:
        print(f"Id: {id} generated from symbol: {symbol}, published_date: {published_date}, url: {url}, model: {model}")
    return id   # string id

def process_news_files(base_dir, stock_code="NVDA", model_filter=None, logger=logging.getLogger("qdrant_loader")):
    """
    Load summaries into Qdrant. Each (article, model) pair becomes one point.
    If model_filter is set (e.g. "gemma4:e4b"), only that model's summaries are loaded.
    """
    for date_folder in os.listdir(base_dir):
        date_path = os.path.join(base_dir, date_folder)
        if not os.path.isdir(date_path):
            continue

        stock_path = os.path.join(date_path, stock_code)
        if not os.path.isdir(stock_path):
            continue

        news_file = os.path.join(stock_path, "detail", "news.json")
        if not os.path.exists(news_file):
            continue

        try:
            with open(news_file, "r", encoding="utf-8") as f:
                news_data = json.load(f)
                for item in news_data:
                    summaries = item.get("summaries", {})
                    if not summaries:
                        logger.warning("No summaries for %s", item.get("url", "?"))
                        continue
                    for model_name, summary_text in summaries.items():
                        if model_filter and model_name != model_filter:
                            continue
                        if not summary_text.strip():
                            continue
                        point_id = make_id(stock_code, date_folder, item["url"], model_name, debug=True)
                        sentiment_score = item.get("sentiment_scores", {}).get(model_name)
                        qdrant_upsert(point_id, summary_text, item["url"], stock_code, date_folder, model_name, sentiment_score)
                        logger.info("Upserted %s | %s | %s (sentiment=%s)", stock_code, model_name, item["url"][:60], sentiment_score)
        except Exception as e:
            logger.error(f"Failed to process {news_file}: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)


def _scroll_all(fields: list[str]) -> list:
    """Fetch every point in the collection (payload only, no vectors)."""
    points, offset = [], None
    while True:
        batch, offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=None,
            limit=500,
            offset=offset,
            with_payload=fields,
            with_vectors=False,
        )
        points.extend(batch)
        if offset is None:
            break
    return points


def _delete_batch(ids: list) -> None:
    if not ids:
        return
    qdrant_client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=PointIdsList(points=ids),
    )


def cleanup(dry_run: bool = False) -> None:
    """
    1. Remove points whose summary contains no useful content
       (e.g. "No direct information about AMD found.").
    2. Deduplicate by (stock, url, model): for each group keep only the
       point with the oldest date, delete the rest.
    """
    logger.info("Fetching all points from '%s'…", COLLECTION_NAME)
    points = _scroll_all(["summary", "stock", "url", "date", "model"])
    logger.info("Total points fetched: %d", len(points))

    to_delete: set[str] = set()

    # --- Step 1: empty / no-info summaries ---
    NO_INFO_PREFIX = "No direct information about"
    for p in points:
        summary = (p.payload.get("summary") or "").strip()
        if not summary or summary.startswith(NO_INFO_PREFIX):
            to_delete.add(p.id)

    logger.info("Step 1 — no-info summaries to remove: %d", len(to_delete))

    # --- Step 2: deduplicate (stock, url, model) — keep oldest date ---
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for p in points:
        if p.id in to_delete:
            continue
        key = (
            p.payload.get("stock", ""),
            p.payload.get("url", ""),
            p.payload.get("model", ""),
        )
        groups[key].append(p)

    dup_count = 0
    for key, group in groups.items():
        if len(group) == 1:
            continue
        # Sort ascending by date string (YYYY-MM-DD sorts lexicographically)
        group.sort(key=lambda p: p.payload.get("date", ""))
        # Keep index 0 (oldest), mark the rest for deletion
        for p in group[1:]:
            to_delete.add(p.id)
            dup_count += 1

    logger.info("Step 2 — duplicate points to remove: %d", dup_count)
    logger.info("Total to delete: %d", len(to_delete))

    if dry_run:
        logger.info("Dry run — no deletions performed.")
        return

    ids = list(to_delete)
    BATCH = 200
    for i in range(0, len(ids), BATCH):
        _delete_batch(ids[i:i + BATCH])
        logger.info("Deleted batch %d–%d", i, min(i + BATCH, len(ids)))

    logger.info("Cleanup complete.")


def backfill_sentiment(base_dir: str, stock_code: str, model_filter: str = None) -> None:
    """
    For every point already in Qdrant that lacks a sentiment_score payload field,
    look up the score from the local news.json and set_payload — no re-embedding.
    """
    logger.info("Backfilling sentiment scores for %s…", stock_code)

    # Build a lookup: point_id -> score from news.json files
    scores: dict[str, float] = {}
    for date_folder in os.listdir(base_dir):
        date_path = os.path.join(base_dir, date_folder)
        if not os.path.isdir(date_path):
            continue
        news_file = os.path.join(date_path, stock_code, "detail", "news.json")
        if not os.path.exists(news_file):
            continue
        with open(news_file, encoding="utf-8") as f:
            news_data = json.load(f)
        for item in news_data:
            for model_name, score in item.get("sentiment_scores", {}).items():
                if model_filter and model_name != model_filter:
                    continue
                pid = make_id(stock_code, date_folder, item["url"], model_name)
                scores[pid] = score

    logger.info("Found %d sentiment scores in local files", len(scores))

    # Fetch existing points and patch those missing the field
    points = _scroll_all(["sentiment_score"])
    updated = 0
    for p in points:
        if p.id in scores and p.payload.get("sentiment_score") is None:
            qdrant_client.set_payload(
                collection_name=COLLECTION_NAME,
                payload={"sentiment_score": scores[p.id]},
                points=[p.id],
            )
            updated += 1

    logger.info("Backfill complete — updated %d points.", updated)


if __name__ == "__main__":
    # Usage:
    #   python qdrant_loader.py AMD "gemma4:e4b"          — load news
    #   python qdrant_loader.py --cleanup                  — clean up collection
    #   python qdrant_loader.py --cleanup --dry-run        — preview without deleting
    #   python qdrant_loader.py --backfill-sentiment AMD   — patch existing points
    base_dir = os.path.join(os.getcwd(), "..", "scrapper", "news")

    if "--cleanup" in sys.argv:
        ensure_collection()
        cleanup(dry_run="--dry-run" in sys.argv)
    elif "--backfill-sentiment" in sys.argv:
        idx = sys.argv.index("--backfill-sentiment")
        stock_code = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "NVDA"
        model_filter = sys.argv[idx + 2] if idx + 2 < len(sys.argv) else None
        ensure_collection()
        backfill_sentiment(base_dir, stock_code, model_filter)
    else:
        stock_code = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
        model_filter = sys.argv[2] if len(sys.argv) > 2 else None
        ensure_collection()
        process_news_files(base_dir, stock_code, model_filter=model_filter, logger=logging.getLogger("qdrant_loader"))