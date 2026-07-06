# Stock Market Data Pipeline

An automated system that scrapes stock market news and collects historical stock prices using GitHub Actions workflows.

## Overview

This project runs two scheduled data collection pipelines:

1. **Stock News Scraper** — Gathers financial news articles for tracked stocks
2. **Stock Price Collector** — Downloads minute-level historical stock prices

Data is stored in the repository and committed automatically by GitHub Actions.

---

## Architecture

### Stock News Scraper (`action.yaml`)

**Schedule:** Daily at 8 AM Pacific Time (UTC-7)  
**Trigger:** Manual dispatch or scheduled cron

**Flow:**
1. GitHub Actions checks out the repository
2. Executes a Docker container (`danielahcardona/stocks-scrapper:latest`)
3. Docker mounts the workspace into the container: `/app/local/stocks`
4. Container runs `scripts/main.sh`
5. Results are committed and pushed back to the repository

**Script:** `scripts/main.sh`
- Iterates over a list of stock tickers (NET, ABNB, CRM, AMD, NVDA, MSFT, etc.)
- For each ticker, calls: `python /app/local/stocks/scrapper/gather_yfinance_news.py TICKER`
- Generates output in: `scrapper/news/<YYYY-MM-DD>/<TICKER>/` (e.g., `scrapper/news/2025-06-28/AMD/`)

**Docker Command:**
```bash
docker run --rm \
  -v ${{ github.workspace }}:/app/local/stocks \
  danielahcardona/stocks-scrapper:latest \
  /app/local/stocks/scripts/main.sh
```

---

### Stock Price Collector (`save_prices.yml`)

**Schedule:** Weekdays at 22:10 UTC (10:10 PM, well after US market close)  
**Trigger:** Manual dispatch or scheduled cron

**Flow:**
1. GitHub Actions checks out the repository
2. Sets up Python 3.11
3. Installs `yfinance` dependency
4. Executes `scripts/save_prices.sh`
5. Commits new price data and pushes to the repository

**Script:** `scripts/save_prices.sh`
- Iterates over the same list of stock tickers
- For each ticker, calls: `python loader/save_minute_prices.py TICKER`
- Generates output in: `prices/<YYYY-MM-DD>/<TICKER>/price.json` (e.g., `prices/2025-10-17/AMD/price.json`)

---

## Tracked Tickers

Both pipelines track the same list of stocks:

| Stock | Sector | Type |
|-------|--------|------|
| NET, ABNB, CRM, RDDT, PLTR, SPOT | Tech/Growth | Common Stocks |
| WMT, SMCI | Retail/Semiconductor | Common Stocks |
| AMD, NVDA, MSFT, META, AMZN, MELI, INTC, TSLA | Tech/Mega-cap | Common Stocks |
| IBM, ORCL | Enterprise/Legacy | Common Stocks |
| ^GSPC, BAC, T, C, ^NDX, QQQ | Financials/Indices | Indices/Financials |

---

## Data Structure

```
project/
├── scrapper/
│   └── news/
│       └── YYYY-MM-DD/          # Date-organized news
│           └── TICKER/          # Stock ticker folder
│               └── [news data]
│
├── prices/
│   └── YYYY-MM-DD/              # Date-organized prices
│       └── TICKER/
│           └── price.json       # Minute-level price data
│
├── scripts/
│   ├── main.sh                  # News scraper orchestrator
│   ├── save_prices.sh           # Price collector orchestrator
│   └── start-env.sh             # Environment setup
│
└── .github/workflows/
    ├── action.yaml              # News scraper workflow
    └── save_prices.yml          # Price collector workflow
```

---

## Manual Trigger

Both workflows can be manually triggered via GitHub Actions:
- Go to **Actions** → Select workflow → **Run workflow**

Or via GitHub CLI:
```bash
gh workflow run action.yaml
gh workflow run save_prices.yml
```

---

## Dependencies

- **News Scraper:** Docker image `danielahcardona/stocks-scrapper:latest`
- **Price Collector:** Python 3.11 + `yfinance` library

---

## Future Enhancements

The codebase has commented-out data loading functions for database integration:
- `loader/data_loader.py` — Load prices into database
- `loader/data_details.py` — Load stock details
- `scrapper/process_news_in_db.py` — Load news into database

These can be enabled when ready to persist data to a database backend.
