# Stock Market Data Pipeline

Collects stock news and minute-level prices on a schedule, then analyses them locally
with an LLM-backed summarisation / sentiment stack and a Streamlit dashboard.

The project has two halves that can be used independently:

| Half | Runs where | What it does |
|------|-----------|--------------|
| **Collection** | GitHub Actions (automated) | Scrapes Yahoo Finance news and downloads 1-minute price bars, committing both back into this repository |
| **Analysis** | Your machine (`docker compose`) | Loads that data into Postgres + Qdrant, summarises and scores news with a local LLM, and serves an interactive dashboard |

Collection needs nothing but the repo. Analysis is entirely optional and never runs in CI.

---

## Architecture

```
                   ┌───────────────── GitHub Actions ─────────────────┐
                   │                                                  │
 Yahoo Finance ──► gather_yfinance_news.py ──► scrapper/news/<date>/  │
 (Playwright)      (action.yaml, 16:00 UTC)                           │
                   │                                                  │
 yfinance API ───► save_minute_prices.py ────► prices/<date>/         │
                   (save_prices.yml, 22:10 UTC weekdays)              │
                   └────────────────────┬─────────────────────────────┘
                                        │  committed to the repo
                                        ▼
                   ┌───────────────── local stack ────────────────────┐
                   │                                                  │
  prices/  ──► loader/load_prices.py ──────────────► Postgres         │
                                                        │             │
  news/    ──► sentiment/sentiment_summarize_news.py    │             │
                 (Ollama or GPT: summary + score)       │             │
                       │ writes back into news.json     │             │
                       ▼                                │             │
               loader/qdrant_loader.py ──► Qdrant ◄─────┤             │
                 (nomic-embed-text vectors)             │             │
                                                        ▼             │
                                           streamlit/prices.py :8501  │
                   └──────────────────────────────────────────────────┘
```

---

# Part 1 — Automated collection

## Stock news scraper

**Workflow:** [`.github/workflows/action.yaml`](.github/workflows/action.yaml)
**Schedule:** `0 16 * * *` — 16:00 UTC daily (08:00 PST / 09:00 PDT)
**Trigger:** scheduled cron or manual dispatch

1. Checks out the repository.
2. Runs `danielahcardona/stocks-scrapper:latest`, mounting the workspace at `/app/local/stocks`.
3. The container executes `scripts/main.sh`, which loops over the ticker list and calls
   `python /app/local/stocks/scrapper/gather_yfinance_news.py <TICKER>` for each.
4. For every ticker, [`gather_yfinance_news.py`](scrapper/gather_yfinance_news.py) opens
   `finance.yahoo.com/quote/<TICKER>/news/` with headless Chromium, extracts article links,
   then visits each article (batches of 32, concurrency scaled to CPU count) and pulls the body text.
5. Results are committed and pushed back to the repository.

```bash
docker run --rm \
  -v ${{ github.workspace }}:/app/local/stocks \
  danielahcardona/stocks-scrapper:latest \
  /app/local/stocks/scripts/main.sh
```

**Output:** `scrapper/news/<YYYY-MM-DD>/<TICKER>/` with two subfolders:

```
head/
  news.json        # [{url, title}] — links found on the quote page
  content.html     # raw page HTML      (gitignored)
  screenshot.png   # page screenshot    (gitignored)
detail/
  news.json        # same entries plus full article text, and later summaries/scores
```

> The date folder uses **UTC-6**, set in [`gather_yfinance_news.py:17`](scrapper/gather_yfinance_news.py#L17).
> Price folders use UTC (see below), so the two trees can disagree by a day near midnight.

## Stock price collector

**Workflow:** [`.github/workflows/save_prices.yml`](.github/workflows/save_prices.yml)
**Schedule:** `10 22 * * 1-5` — 22:10 UTC on weekdays, after the US close under both EST and EDT
**Trigger:** scheduled cron or manual dispatch

1. Checks out the repository with full history.
2. Sets up Python 3.11 and installs `yfinance`.
3. Runs `scripts/save_prices.sh`, which calls `python loader/save_minute_prices.py <TICKER>`
   per ticker.
4. Commits `prices/` and pushes.

By default [`save_minute_prices.py`](loader/save_minute_prices.py) downloads `period="1d",
interval="1m"` and keeps the **last 12 hours** of bars, falling back to the most recent trading
day when that window is empty (weekends, holidays). Output goes to
`prices/<YYYY-MM-DD>/<TICKER>/price.json`, where the date is the runner's local date — UTC on
GitHub Actions.

There is also a backfill mode that fetches one exact UTC calendar day:

```bash
python loader/save_minute_prices.py NVDA --date 2026-08-14
scripts/save_prices.sh NVDA          # single ticker, today
bash scripts/save_prices.sh          # full list, today
```

Yahoo only serves 1-minute bars for roughly the last 7 days, so backfill has a short reach.

## Tracked tickers

Both pipelines iterate over the same 24 symbols, defined in
[`scripts/main.sh:4`](scripts/main.sh#L4) and [`scripts/save_prices.sh:23`](scripts/save_prices.sh#L23).
Keep the two lists in sync when editing.

| Symbols | Category |
|---------|----------|
| AMD, NVDA, INTC | Semiconductors |
| SMCI | Servers / AI hardware |
| MSFT, CRM, PLTR, NET, ORCL, IBM | Software, cloud & enterprise IT |
| META, RDDT, SPOT | Social & media platforms |
| AMZN, MELI, ABNB | E-commerce & marketplaces |
| TSLA | Automotive / EV |
| WMT | Retail |
| BAC, C | Banking |
| T | Telecom |
| ^GSPC, ^NDX | Indices (S&P 500, Nasdaq-100) |
| QQQ | ETF (Nasdaq-100) |

## Manual trigger

```bash
gh workflow run action.yaml
gh workflow run save_prices.yml
```

Or **Actions** → select the workflow → **Run workflow**.

---

# Part 2 — Local analysis stack

## Quick start

```bash
docker compose up -d
```

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `stocks-pg` | `postgres:14` | 5432 | Price and news tables; initialised from [`pg/init.sql`](pg/init.sql) |
| `stocks-qdrant` | `qdrant/qdrant` | 6333 / 6334 | Vector store for news summaries |
| `stocks-ollama` | `ollama/ollama` | 11434 | Local LLM + embedding inference (requests all NVIDIA GPUs) |
| `stocks-streamlit` | built from [`dockerfiles/Dockerfile.streamlit`](dockerfiles/Dockerfile.streamlit) | 8501 | Dashboard |

Then pull the models Ollama needs:

```bash
docker exec -it stocks-ollama ollama pull nomic-embed-text   # embeddings, 768-dim
docker exec -it stocks-ollama ollama pull gemma4:e4b         # or another summarisation model
```

The dashboard is at <http://localhost:8501>, but it is empty until you load prices.

> The compose file requests an NVIDIA GPU for Ollama. Without one, drop the `deploy.resources`
> block from the `ollama` service or run Ollama on the host instead.

## 1. Load prices into Postgres

```bash
python loader/load_prices.py
```

[`load_prices.py`](loader/load_prices.py) walks `prices/*/*/price.json`, skips
`(date, stock_code)` pairs already present, converts timestamps to naive UTC, and bulk-inserts
with `ON CONFLICT (datetime, stock_code) DO NOTHING`. It is safe to re-run.

Connection comes from `DATABASE_URL`; from the host you will usually want:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/stocks python loader/load_prices.py
```

## 2. Summarise and score news

```bash
python sentiment/sentiment_summarize_news.py AMD            # local model via Ollama
python sentiment/sentiment_summarize_news.py AMD --force    # regenerate existing summaries
python sentiment/sentiment_summarize_news.py GPT <api_key> AMD
```

[`analyzer.py`](sentiment/analyzer.py) walks every `scrapper/news/*/AMD/detail/news.json`, and for
each article: cleans the body with [`purified_text`](utils/utils.py) (strips bylines, ticker
lists, ads and footers, truncating at ~650 chars), generates a one-sentence summary constrained by
[`SUMMARY_PROMPT`](sentiment/prompts.py), then scores that summary 0.0–1.0 with `SENTIMENT_PROMPT`.
Results are written back into the same `news.json` atomically, keyed by model name, so several
models can coexist per article. Articles with no relevant content get the sentinel
`"No direct information about <TICKER> found."` and are skipped for scoring.

**The script prompts interactively** for which model to use — the choices live in
[`select_local_model`](utils/utils.py#L121). Set `SUMMARY_MAX_WORKERS` to parallelise
(default `1`).

## 3. Index summaries in Qdrant

```bash
cd loader
python qdrant_loader.py AMD "gemma4:e4b"        # embed + upsert one ticker/model
python qdrant_loader.py --cleanup --dry-run     # preview dedup + no-info removal
python qdrant_loader.py --cleanup
python qdrant_loader.py --backfill-sentiment AMD
```

Each `(article, model)` pair becomes one point, with a deterministic SHA-256 id over
`symbol|date|url|model`, embedded via Ollama's `nomic-embed-text`. The payload carries
`summary, url, stock, date, model, sentiment_score`, all indexed for filtered search.

> **Run this from inside `loader/`.** [`qdrant_loader.py:292`](loader/qdrant_loader.py#L292)
> resolves the news directory from `os.getcwd()`, so it fails elsewhere.

## 4. Dashboard

[`streamlit/prices.py`](streamlit/prices.py) offers:

- **Candlestick charts** per ticker, resampled server-side into 1 min → 24 h buckets, with
  optional SMA 20/50, EMA 20, Bollinger Bands, Volume, RSI and MACD subplots.
- **Compare tab** — several tickers on one axis, as price or % change.
- **Relative Strength** — a stock against a benchmark (defaults to QQQ), candle by candle.

A **News Search** section is started at the bottom of the file but is **unfinished**: it renders
the search box, then stops. `embed_query`, `search_news` and `build_news_score_chart` are imported
and never called, so typing a query does nothing. The supporting pieces
([`qdrant_search.py`](streamlit/qdrant_search.py), [`charts.py`](streamlit/charts.py)) are complete —
only the wiring in `prices.py` is missing.

## Notebooks

[`dashboards/stocks.ipynb`](dashboards/stocks.ipynb) and
[`dashboards/sentiment.ipynb`](dashboards/sentiment.ipynb) are exploratory matplotlib/pandas
notebooks that read from Postgres and the news JSON directly. They predate the Streamlit app.

---

## Repository layout

```
.github/workflows/
  action.yaml               News scraper workflow (16:00 UTC daily)
  save_prices.yml           Price collector workflow (22:10 UTC weekdays)

scripts/
  main.sh                   News orchestrator, runs inside the scraper container
  save_prices.sh            Price orchestrator, runs on the CI runner
  start-env.sh              Interactive shell in danielahcardona/stocks:latest

scrapper/
  gather_yfinance_news.py   Playwright scraper: links + article bodies
  process_news_in_db.py     Backfills empty `detail` fields straight into Postgres
  yfinance_detail.py        Scratch/experimental single-article scraper
  news/<date>/<TICKER>/     Collected news (head/ and detail/)

loader/
  save_minute_prices.py     yfinance -> prices/<date>/<TICKER>/price.json
  load_prices.py            prices/ -> Postgres (idempotent bulk load)
  qdrant_loader.py          Summaries -> Qdrant, plus cleanup/backfill utilities
  data_loader.py            Legacy: company_info + stock straight from yfinance
  data_details.py           Legacy: detail/news.json -> stock_news table
  load_head.sh              Legacy wrapper for data_loader.py
  load_details.sh           Legacy wrapper for data_details.py

sentiment/
  sentiment_summarize_news.py   Entry point (CLI arg parsing)
  analyzer.py                   Directory walk, caching, atomic writes
  chains.py                     LangChain assembly (ChatOllama / ChatOpenAI)
  prompts.py                    Summary and sentiment prompt templates

streamlit/
  prices.py                 Dashboard entry point
  charts.py                 Candlestick, compare, relative-strength, news-score figures
  stock_data.py             Postgres queries, resampling, technical indicators
  qdrant_search.py          Embedding + filtered vector search
  config.py                 Env-var configuration, timeframes, indicator list

pg/
  init.sql                  Schema: stock, company_info, stock_news
  queries.sql               Reference N-minute resampling query

utils/utils.py              purified_text, extract_first_date, select_local_model
dockerfiles/                Image definitions (see Dependencies)
docker-compose.yml          Local stack: pg + qdrant + ollama + streamlit
prices/<date>/<TICKER>/     Collected minute bars
```

---

## Data formats

### `prices/<date>/<TICKER>/price.json`

```json
[
  {
    "Datetime": "2026-09-02T09:30:00-04:00",
    "Ticker": "AMD",
    "Price": 458.510009765625,
    "Close": 458.510009765625,
    "High": 458.9879150390625,
    "Low": 455.82000732421875,
    "Open": 458.45001220703125,
    "Volume": 530120.0
  }
]
```

`Datetime` carries the **exchange-local offset** as returned by yfinance, not UTC.
`Price` duplicates `Close` — yfinance provides no separate price field for intraday bars.

### `scrapper/news/<date>/<TICKER>/detail/news.json`

```json
[
  {
    "url": "https://finance.yahoo.com/news/....html",
    "title": "...",
    "detail": "full article text",
    "date": "2025-07-01T08:15:00",
    "summaries":        { "gemma4:e4b": "one-sentence summary" },
    "sentiment_scores": { "gemma4:e4b": 0.8 }
  }
]
```

`summaries` and `sentiment_scores` appear only after the sentiment stage runs, and only for the
models it was run with. `date` is parsed out of the article body by
[`extract_first_date`](utils/utils.py). Some older files also carry an `analysis` field from a
retired HuggingFace FinBERT-style classifier; nothing in the current codebase reads or writes it.

### Database schema ([`pg/init.sql`](pg/init.sql))

- **`stock`** — one row per minute bar, unique on `(datetime, stock_code)`, with the date parts
  denormalised into `year/month/day/hour/minute` columns.
- **`company_info`** — ~110 columns of yfinance `.info` fundamentals, primary key `(stock_code, info_date)`.
- **`stock_news`** — `(date, stock_code, url)` primary key with `title`, `detail` and sentiment columns.

---

## Configuration

All are read via `os.getenv` with the defaults shown.

| Variable | Default | Used by |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://postgres:password@host.docker.internal:5432/stocks` | `load_prices.py` |
| `DATABASE_URL` | `postgresql://postgres:password@localhost:5432/stocks` | `streamlit/config.py` |
| `QDRANT_URL` | `http://host.docker.internal:6333` / `http://localhost:6333` | `qdrant_loader.py` / streamlit |
| `OLLAMA_URL` | `http://host.docker.internal:11434` / `http://localhost:11434` | `qdrant_loader.py` / streamlit |
| `QDRANT_COLLECTION` | `stock_news_summaries` | `qdrant_loader.py`, streamlit |
| `QDRANT_VECTOR_DIM` | `768` | `qdrant_loader.py` |
| `EMBEDDING_MODEL` | `nomic-embed-text` | `qdrant_loader.py`, streamlit |
| `SUMMARY_MAX_WORKERS` | `1` | `sentiment/analyzer.py` |

The Ollama base URL used for summarisation is hardcoded to `http://host.docker.internal:11434`
in [`chains.py`](sentiment/chains.py) and is not configurable by environment variable.

Postgres credentials (`postgres` / `password`) are hardcoded in `docker-compose.yml` and in the
legacy `loader/data_loader.py`, `loader/data_details.py` and `scrapper/process_news_in_db.py`.
The stack is intended for local use only — do not expose these ports.

---

## Dependencies

There is no `requirements.txt`; each piece declares its own environment.

| Component | Needs |
|-----------|-------|
| News scraper | `danielahcardona/stocks-scrapper:latest` — Playwright + Chromium, BeautifulSoup, lxml. [`dockerfiles/DockerfileGatherNews`](dockerfiles/DockerfileGatherNews) provides the equivalent base. |
| Price collector | Python 3.11 + `yfinance` (installed by the workflow) |
| `load_prices.py` | `psycopg2` |
| Sentiment | `langchain`, `langchain-core`, `langchain-ollama`, `langchain-openai` — see [`dockerfiles/Dockerfile`](dockerfiles/Dockerfile) |
| Qdrant loader | `qdrant-client`, `requests` |
| Streamlit | `streamlit`, `plotly`, `psycopg2-binary`, `qdrant-client`, `requests` |

---

## Known limitations

- **Repository size.** Two workflows commit every weekday; `prices/` alone is over 500 MB and git
  history is larger still. Expect slow clones, and consider Parquet, a separate data repo, or LFS
  before this grows much further.
- **The dashboard's News Search is unfinished** — see [Dashboard](#4-dashboard).
- **Date-folder timezones differ** between the news tree (UTC-6) and the price tree (UTC).
- **`qdrant_loader.py` must be run from `loader/`** — it builds its input path from the working
  directory.
- **The sentiment entry point is interactive** (`input()` for model choice) and cannot be
  automated as-is.
- **`loader/data_details.py` renames its input** to `processed+<timestamp>.json` after loading,
  which hides the file from `analyzer.py` and `qdrant_loader.py`. Prefer `load_prices.py` and the
  sentiment/Qdrant path; `data_loader.py` and `data_details.py` also open a database connection at
  import time.
- **`scrapper/yfinance_detail.py` is scratch code** — it ignores its argument and scrapes one
  hardcoded URL.
- No tests, and no license file.
