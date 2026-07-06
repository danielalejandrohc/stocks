"""
Entry point for news summarisation and sentiment analysis.

Usage:
    python sentiment_summarize_news.py AMD
    python sentiment_summarize_news.py AMD --force
    python sentiment_summarize_news.py GPT <openai_api_key>
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import os

from analyzer import analyze_news_for_stock

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'


def main():
    args = sys.argv[1:]

    force_overwrite = "--force" in args
    if force_overwrite:
        args.remove("--force")

    if args and args[0].upper() == "GPT":
        if len(args) < 2:
            print("Usage: sentiment_summarize_news.py GPT <openai_api_key> [STOCK]")
            sys.exit(1)
        gpt_api_key = args[1]
        stock_code  = args[2] if len(args) > 2 else "NVDA"
        use_gpt     = True
    else:
        stock_code  = args[0] if args else "NVDA"
        gpt_api_key = None
        use_gpt     = False

    base_dir = os.path.join(os.path.dirname(__file__), "..", "scrapper", "news")

    analyze_news_for_stock(
        stock_code=stock_code,
        base_dir=base_dir,
        use_gpt=use_gpt,
        gpt_api_key=gpt_api_key,
        force_overwrite=force_overwrite,
    )


if __name__ == "__main__":
    main()
