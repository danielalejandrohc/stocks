import argparse
import json
from datetime import datetime, timedelta, date, timezone
from pathlib import Path

import yfinance as yf


def fetch_last_1d_1m(ticker: str):
    # Get 1-day, 1-minute data and filter the last 12 hours
    print(f"[DEBUG] Downloading 1m data for ticker={ticker} period=2d prepost=False")
    df = yf.download(tickers=ticker, period="1d", interval="1m")
    if df is None or df.empty:
        print("[DEBUG] Download returned empty DataFrame")
        return []

    # Ensure index is timezone-aware in UTC if possible
    print(f"[DEBUG] Raw df shape={df.shape} tz={getattr(df.index, 'tz', None)} cols={list(df.columns)}")
    try:
        first_ts = df.index[0]
        last_ts = df.index[-1]
        print(f"[DEBUG] Raw time range first={first_ts} last={last_ts}")
    except Exception:
        pass

    # If yfinance returned MultiIndex columns like ('Open','AMD'), collapse to single-level for this ticker
    try:
        if len(df.columns) > 0 and isinstance(df.columns[0], tuple):
            try:
                df = df.xs(ticker, axis=1, level=-1, drop_level=True)
                print(f"[DEBUG] Collapsed MultiIndex to single-level columns for {ticker}. New cols={list(df.columns)}")
            except Exception:
                try:
                    df.columns = [c[0] for c in df.columns]
                    print(f"[DEBUG] Flattened MultiIndex by first level. New cols={list(df.columns)}")
                except Exception:
                    print("[DEBUG] Failed to flatten MultiIndex columns; proceeding as-is")
    except Exception:
        pass

    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
        print("[DEBUG] Localized index to UTC")

    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=12)
    print(f"[DEBUG] now_utc={now_utc} cutoff(last 12h)={cutoff}")
    raw_df = df
    filtered = df[df.index >= cutoff]
    print(f"[DEBUG] After cutoff filter shape={filtered.shape}")
    if not filtered.empty:
        try:
            print(f"[DEBUG] Filtered time range first={filtered.index[0]} last={filtered.index[-1]}")
        except Exception:
            pass
    else:
        # Weekend/holiday fallback: use last trading day's intraday bars from the raw data
        last_ts = raw_df.index[-1]
        start_day = datetime(last_ts.year, last_ts.month, last_ts.day, tzinfo=timezone.utc)
        end_day = start_day + timedelta(days=1)
        filtered = raw_df[(raw_df.index >= start_day) & (raw_df.index < end_day)]
        print(f"[DEBUG] Fallback to last trading day {start_day.date()} shape={filtered.shape}")

    records = []
    for ts, row in filtered.iterrows():
        try:
            # Support both flattened single-level columns and MultiIndex-collapsed columns
            open_v = float(row["Open"]) if "Open" in row else float(row[("Open", ticker)])
            high_v = float(row["High"]) if "High" in row else float(row[("High", ticker)])
            low_v = float(row["Low"]) if "Low" in row else float(row[("Low", ticker)])
            close_v = float(row["Close"]) if "Close" in row else float(row[("Close", ticker)])
            volume_v = float(row["Volume"]) if "Volume" in row else float(row[("Volume", ticker)])
        except Exception:
            # Skip malformed rows
            continue
        record = {
            "Datetime": ts.isoformat(),
            "Ticker": ticker,
            # "Price" column as per example; yfinance does not provide separate Price in intraday OHLCV, use Close
            "Price": close_v,
            "Close": close_v,
            "High": high_v,
            "Low": low_v,
            "Open": open_v,
            "Volume": volume_v,
        }
        records.append(record)
    return records


def write_prices_json(repo_root: Path, ticker: str, records: list, day_str: str | None = None):
    # Date folder defaults to today's date (local system date) unless provided
    if day_str is None:
        day_str = date.today().strftime("%Y-%m-%d")
    out_dir = repo_root / "prices" / day_str / ticker
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "price.json"

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"[DEBUG] Wrote {len(records)} records to {out_file}")

    return out_file


def fetch_day_1m(ticker: str, target_day: date):
    # Fetch 1-minute data for the exact UTC calendar day [00:00, next 00:00)
    start_dt = datetime(target_day.year, target_day.month, target_day.day, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    print(f"[DEBUG] Downloading 1m data for ticker={ticker} start={start_dt} end={end_dt}")
    df = yf.download(tickers=ticker, start=start_dt, end=end_dt, interval="1m")
    if df is None or df.empty:
        print("[DEBUG] Download returned empty DataFrame for target day")
        return []

    print(f"[DEBUG] Raw df shape={df.shape} tz={getattr(df.index, 'tz', None)} cols={list(df.columns)}")
    try:
        first_ts = df.index[0]
        last_ts = df.index[-1]
        print(f"[DEBUG] Raw time range first={first_ts} last={last_ts}")
    except Exception:
        pass

    # Handle possible MultiIndex columns
    try:
        if len(df.columns) > 0 and isinstance(df.columns[0], tuple):
            try:
                df = df.xs(ticker, axis=1, level=-1, drop_level=True)
                print(f"[DEBUG] Collapsed MultiIndex to single-level columns for {ticker}. New cols={list(df.columns)}")
            except Exception:
                try:
                    df.columns = [c[0] for c in df.columns]
                    print(f"[DEBUG] Flattened MultiIndex by first level. New cols={list(df.columns)}")
                except Exception:
                    print("[DEBUG] Failed to flatten MultiIndex columns; proceeding as-is")
    except Exception:
        pass

    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
        print("[DEBUG] Localized index to UTC")

    # Ensure we only keep rows within the exact UTC calendar day
    filtered = df[(df.index >= start_dt) & (df.index < end_dt)]
    print(f"[DEBUG] Day filter [{start_dt}, {end_dt}) shape={filtered.shape}")
    if not filtered.empty:
        try:
            print(f"[DEBUG] Filtered time range first={filtered.index[0]} last={filtered.index[-1]}")
        except Exception:
            pass

    records = []
    for ts, row in filtered.iterrows():
        try:
            open_v = float(row["Open"]) if "Open" in row else float(row[("Open", ticker)])
            high_v = float(row["High"]) if "High" in row else float(row[("High", ticker)])
            low_v = float(row["Low"]) if "Low" in row else float(row[("Low", ticker)])
            close_v = float(row["Close"]) if "Close" in row else float(row[("Close", ticker)])
            volume_v = float(row["Volume"]) if "Volume" in row else float(row[("Volume", ticker)])
        except Exception:
            continue
        records.append({
            "Datetime": ts.isoformat(),
            "Ticker": ticker,
            "Price": close_v,
            "Close": close_v,
            "High": high_v,
            "Low": low_v,
            "Open": open_v,
            "Volume": volume_v,
        })
    return records

def main():
    parser = argparse.ArgumentParser(description="Save 1m prices. Default: last-12h -> prices/today/TICKER/price.json. Optional --date to save exact day.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. NVDA")
    parser.add_argument("--date", dest="date_str", help="Target date in YYYY-MM-DD to fetch exact day's 1m bars (UTC)")
    args = parser.parse_args()

    # Resolve repo root as two levels up from this file (../..)
    repo_root = Path(__file__).resolve().parents[1]

    if args.date_str:
        try:
            target_day = datetime.strptime(args.date_str, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("--date must be in YYYY-MM-DD format")
        records = fetch_day_1m(args.ticker, target_day)
        out_file = write_prices_json(repo_root, args.ticker, records, day_str=target_day.strftime("%Y-%m-%d"))
    else:
        records = fetch_last_1d_1m(args.ticker)
        out_file = write_prices_json(repo_root, args.ticker, records)
    print(f"Wrote {len(records)} records to {out_file}")


if __name__ == "__main__":
    main()
