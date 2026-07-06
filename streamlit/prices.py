import pandas as pd
import streamlit as st
from datetime import date, timedelta

from config import TIMEFRAMES, INDICATORS
from stock_data import get_stock_codes, fetch_prices, to_series
from charts import build_stock_chart, build_compare_chart, build_rs_chart, build_news_score_chart
from qdrant_search import get_qdrant_models, embed_query, search_news

st.set_page_config(layout="wide")
st.title("Stock Prices")

# ---------------------------------------------------------------------------
# Sidebar / top controls
# ---------------------------------------------------------------------------

try:
    stock_codes = get_stock_codes()
except Exception as e:
    st.error(f"Could not connect to database: {e}")
    st.stop()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    selected_stocks = st.multiselect("Stock codes", stock_codes,
                                     default=[stock_codes[0]] if stock_codes else [])
with col2:
    date_start = st.date_input("Date start", value=date.today() - timedelta(days=7))
with col3:
    date_end = st.date_input("Date end", value=date.today())
with col4:
    timeframe_label = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=3)
with col5:
    selected_indicators = st.multiselect("Indicators", INDICATORS)

if not selected_stocks:
    st.info("Select at least one stock code.")
    st.stop()

if date_start > date_end:
    st.error("Date start must be before date end.")
    st.stop()

interval_seconds = TIMEFRAMES[timeframe_label]

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_labels = (["Compare"] if len(selected_stocks) > 1 else []) + selected_stocks + ["Relative Strength"]
tabs       = st.tabs(tab_labels)
tab_offset = 1 if len(selected_stocks) > 1 else 0

# --- Compare ---
if len(selected_stocks) > 1:
    with tabs[0]:
        mode = st.radio("View", ["% Change", "Price"], horizontal=True)
        stock_dfs = {
            code: fetch_prices(code, date_start, date_end, interval_seconds)
            for code in selected_stocks
        }
        fig = build_compare_chart(stock_dfs, timeframe_label, mode)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No data found for selected stocks.")

# --- Individual stock tabs ---
for i, stock_code in enumerate(selected_stocks):
    with tabs[i + tab_offset]:
        df = fetch_prices(stock_code, date_start, date_end, interval_seconds)
        if df.empty:
            st.warning(f"No data found for {stock_code}.")
            continue
        st.plotly_chart(build_stock_chart(df, stock_code, timeframe_label, selected_indicators),
                        use_container_width=True)
        st.subheader("Data")
        st.dataframe(df, use_container_width=True)

# --- Relative Strength ---
with tabs[-1]:
    st.markdown(
        "**Relative Strength** shows how a stock performs vs a benchmark candle-by-candle. "
        "A rising RS line while the benchmark falls = institutional absorption."
    )
    rs_col1, rs_col2 = st.columns(2)
    with rs_col1:
        rs_stock = st.selectbox("Stock", stock_codes, key="rs_stock")
    with rs_col2:
        rs_bench = st.selectbox("Benchmark (ETF)", stock_codes,
                                index=stock_codes.index("QQQ") if "QQQ" in stock_codes else 0,
                                key="rs_bench")

    if rs_stock == rs_bench:
        st.warning("Stock and benchmark must be different.")
    else:
        df_stock = fetch_prices(rs_stock, date_start, date_end, interval_seconds)
        df_bench = fetch_prices(rs_bench, date_start, date_end, interval_seconds)

        if df_stock.empty or df_bench.empty:
            st.warning("Not enough data for one or both selections.")
        else:
            st.plotly_chart(
                build_rs_chart(to_series(df_stock), to_series(df_bench), rs_stock, rs_bench),
                use_container_width=True,
            )

# ---------------------------------------------------------------------------
# News semantic search
# ---------------------------------------------------------------------------

st.divider()
st.subheader("News Search")

try:
    available_models = get_qdrant_models()
except Exception:
    available_models = ["gemma4:e4b"]

q_col1, q_col2, q_col3 = st.columns([4, 1, 1])
with q_col1:
    query_text = st.text_input("Search news by meaning",
                               placeholder="e.g. AMD earnings beat expectations")
