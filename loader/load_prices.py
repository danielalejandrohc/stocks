import os
import json
import glob
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@host.docker.internal:5432/stocks")
PRICES_DIR = Path(__file__).resolve().parents[1] / "prices"

INSERT_SQL = """
    INSERT INTO stock (datetime, year, month, day, hour, minute, stock_code, timezone,
                       open, high, low, close, volume, dividends, stock_splits)
    VALUES %s
    ON CONFLICT (datetime, stock_code) DO NOTHING
"""


def parse_row(entry, stock_code):
    dt = datetime.fromisoformat(entry["Datetime"])
    tz_name = str(dt.tzinfo) if dt.tzinfo else None
    dt_utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return (
        dt_utc,
        dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute,
        stock_code,
        tz_name,
        entry.get("Open"),
        entry.get("High"),
        entry.get("Low"),
        entry.get("Close"),
        int(entry["Volume"]) if entry.get("Volume") is not None else None,
        entry.get("Dividends"),
        entry.get("Stock Splits"),
    )


ALREADY_LOADED_SQL = "SELECT DISTINCT DATE(datetime), stock_code FROM stock"
BATCH_SIZE = 50


def fetch_loaded(conn) -> set:
    with conn.cursor() as cur:
        cur.execute(ALREADY_LOADED_SQL)
        return {(str(row[0]), row[1]) for row in cur.fetchall()}


def load_all(conn):
    files = sorted(PRICES_DIR.glob("*/*/price.json"))
    print(f"Found {len(files)} price files")

    loaded = fetch_loaded(conn)
    print(f"Already loaded: {len(loaded)} (date, stock_code) pairs — skipping those files")

    pending = [
        p for p in files
        if (p.parent.parent.name, p.parent.name) not in loaded
    ]
    print(f"Files to insert: {len(pending)}")

    inserted = 0
    with conn.cursor() as cur:
        for i, path in enumerate(pending, start=1):
            stock_code = path.parent.name
            date_str = path.parent.parent.name

            with open(path, encoding="utf-8") as f:
                entries = json.load(f)

            rows = [parse_row(e, stock_code) for e in entries]
            if rows:
                execute_values(cur, INSERT_SQL, rows)
                inserted += len(rows)
                print(f"  {date_str}/{stock_code}: {len(rows)} rows")

            if i % BATCH_SIZE == 0:
                conn.commit()

    conn.commit()
    print(f"Done. Inserted {inserted} rows, skipped {len(files) - len(pending)} files.")


if __name__ == "__main__":
    with psycopg2.connect(DB_URL) as conn:
        load_all(conn)
