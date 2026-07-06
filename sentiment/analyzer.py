"""
Walks the news directory tree and processes each article:
  - generates a summary (if missing)
  - scores sentiment (if missing)
  - writes results back to news.json atomically
"""

import json
import logging
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from utils.utils import purified_text, select_local_model, extract_first_date
import chains

logger = logging.getLogger(__name__)

_processed_counter = 0
_processed_counter_lock = Lock()


def analyze_news_for_stock(
    stock_code: str,
    base_dir: str = "/app/local/scrapper/news/",
    use_gpt: bool = False,
    gpt_api_key: str = None,
    force_overwrite: bool = False,
):
    logger.info("Starting analysis — stock: %s  dir: %s", stock_code, base_dir)

    if not os.path.exists(base_dir):
        logger.error("Base directory does not exist: %s", base_dir)
        return

    workers = max(1, int(os.getenv("SUMMARY_MAX_WORKERS", "1")))
    logger.info("Workers: %d  force_overwrite: %s", workers, force_overwrite)

    model_id, _ = select_local_model()
    chains.initialize_model(model_id, use_gpt=use_gpt, gpt_api_key=gpt_api_key)

    summary_cache: dict[str, str] = {}
    summary_cache_lock = Lock()
    start_time = time.time()

    def _save_sentiment(item: dict, key: str, summary: str) -> None:
        """Write sentiment score into item unless it is a no-info summary."""
        if chains.is_no_info(summary):
            logger.info("Skipping sentiment (no-info summary)")
            return
        if key not in item.get("sentiment_scores", {}):
            score = chains.score_summary(summary)
            item.setdefault("sentiment_scores", {})[key] = score
            logger.info("Sentiment scored: %.4f", score)

    def _process_item(item: dict) -> None:
        item.pop("summary", None)

        url   = item.get("url", "unknown")
        title = item.get("title", "")[:80]
        logger.info("Processing: %s | %s", title, url)

        # Extract article date
        try:
            dt = extract_first_date(item.get("detail", ""))
            item["date"] = dt.isoformat() if dt else None
        except Exception:
            logger.error("Date extraction failed for %s\n%s", url, traceback.format_exc())
            sys.exit(1)

        key = model_id
        item.setdefault("summaries", {})

        # --- Skip if summary already exists ---
        if not force_overwrite:
            with summary_cache_lock:
                cached = summary_cache.get(url)
                if cached:
                    item["summaries"][key] = cached
                    logger.info("Cache hit: %s", url)
                    _save_sentiment(item, key, cached)
                    return

                if key in item["summaries"]:
                    existing = item["summaries"][key]
                    summary_cache[url] = existing
                    logger.info("Skipping (exists): %s", url)
                    _save_sentiment(item, key, existing)
                    return

        # --- Run the full chain: text -> summary + sentiment_score ---
        detail = purified_text(item.get("detail", ""), 650)
        result = chains.run_analysis(stock_code, detail)

        summary = result["summary"]
        logger.info("Summary: %s", summary)

        global _processed_counter
        with _processed_counter_lock:
            _processed_counter += 1
            elapsed = time.time() - start_time
            rate = (_processed_counter / elapsed) * 60.0 if elapsed > 0 else 0.0
            logger.info("Progress: %d articles  %.2f/min  %.1fs", _processed_counter, rate, elapsed)

        if not summary.strip():
            return

        item["summaries"][key] = summary
        with summary_cache_lock:
            summary_cache[url] = summary

        if not chains.is_no_info(summary):
            item.setdefault("sentiment_scores", {})[key] = result["sentiment_score"]
            logger.info("Sentiment: %.4f", result["sentiment_score"])

        if use_gpt:
            time.sleep(1.2)

    def _write_atomic(path: str, data: list) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    # --- Walk directory tree ---
    for date_folder in sorted(os.listdir(base_dir)):
        date_path  = os.path.join(base_dir, date_folder)
        stock_path = os.path.join(date_path, stock_code)
        news_file  = os.path.join(stock_path, "detail", "news.json")

        if not os.path.isfile(news_file):
            continue

        try:
            with open(news_file, "r", encoding="utf-8") as f:
                news_data = json.load(f)
            logger.info("File: %s  (%d articles)", news_file, len(news_data))

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_process_item, item) for item in news_data]
                for future in as_completed(futures):
                    future.result()
                    _write_atomic(news_file, news_data)

            _write_atomic(news_file, news_data)

        except Exception:
            logger.error("Failed: %s\n%s", news_file, traceback.format_exc())
            sys.exit(1)

    logger.info("Done — %s  %.2fs", stock_code, time.time() - start_time)
