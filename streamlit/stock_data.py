import psycopg2
import pandas as pd
import streamlit as st
from datetime import date, timedelta

from config import DB_URL

_PRICES_QUERY = """
WITH CTE AS (
    SELECT
        *,
        FLOOR(EXTRACT(EPOCH FROM datetime) / %(interval_seconds)s) AS interval_group,
        LAST_VALUE(close) OVER (
            PARTITION BY FLOOR(EXTRACT(EPOCH FROM datetime) / %(interval_seconds)s)
            ORDER BY datetime
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_close_in_interval
    FROM stock
    WHERE stock_code = %(stock_code)s
      AND datetime >= %(date_start)s
      AND datetime <  %(date_end)s
)
SELECT
    MIN(datetime)               AS start_time,
    MAX(datetime)               AS end_time,
    MIN(low)                    AS low,
    MAX(high)                   AS high,
    MAX(last_close_in_interval) AS close,
    SUM(volume)                 AS volume
FROM CTE
GROUP BY interval_group
ORDER BY start_time
"""


@st.cache_data(ttl=60)
def get_stock_codes() -> list[str]:
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT stock_code FROM stock ORDER BY stock_code")
            return [r[0] for r in cur.fetchall()]


@st.cache_data(ttl=60)
def fetch_prices(stock_code: str, date_start: date, date_end: date, interval_seconds: int) -> pd.DataFrame:
    with psycopg2.connect(DB_URL) as conn:
        return pd.read_sql(
            _PRICES_QUERY,
            conn,
            params={
                "stock_code":       stock_code,
                "date_start":       date_start,
                "date_end":         date_end + timedelta(days=1),
                "interval_seconds": interval_seconds,
            },
        )


def to_series(df: pd.DataFrame) -> pd.Series:
    """Close prices as a tz-naive UTC-indexed Series."""
    idx = pd.to_datetime(df["start_time"]).dt.tz_localize(None)
    return pd.Series(df["close"].values, index=idx)


def add_indicators(df: pd.DataFrame, indicators: list) -> pd.DataFrame:
    c = df["close"]

    if "SMA 20" in indicators:
        df["sma20"] = c.rolling(20).mean()
    if "SMA 50" in indicators:
        df["sma50"] = c.rolling(50).mean()
    if "EMA 20" in indicators:
        df["ema20"] = c.ewm(span=20, adjust=False).mean()
    if "Bollinger Bands" in indicators:
        sma = c.rolling(20).mean()
        std = c.rolling(20).std()
        df["bb_upper"] = sma + 2 * std
        df["bb_lower"] = sma - 2 * std
    if "RSI" in indicators:
        delta = c.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss))
    if "MACD" in indicators:
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        df["macd"]        = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"]   = df["macd"] - df["macd_signal"]

    return df
