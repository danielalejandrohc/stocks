import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from stock_data import add_indicators, to_series


def build_stock_chart(df: pd.DataFrame, stock_code: str, timeframe_label: str, indicators: list) -> go.Figure:
    """Candlestick chart with optional indicator subplots."""
    df = add_indicators(df.copy(), indicators)

    extra_rows  = [i for i in ["Volume", "RSI", "MACD"] if i in indicators]
    n_rows      = 1 + len(extra_rows)
    row_heights = [0.6] + [0.4 / len(extra_rows)] * len(extra_rows) if extra_rows else [1.0]

    fig   = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                          vertical_spacing=0.03, row_heights=row_heights)
    x     = df["start_time"]
    open_ = df["close"].shift(1, fill_value=df["close"].iloc[0])

    fig.add_trace(go.Candlestick(
        x=x, open=open_, high=df["high"], low=df["low"], close=df["close"],
        name=stock_code, showlegend=False,
    ), row=1, col=1)

    if "SMA 20" in indicators:
        fig.add_trace(go.Scatter(x=x, y=df["sma20"], name="SMA 20", line=dict(color="orange", width=1)), row=1, col=1)
    if "SMA 50" in indicators:
        fig.add_trace(go.Scatter(x=x, y=df["sma50"], name="SMA 50", line=dict(color="cyan",   width=1)), row=1, col=1)
    if "EMA 20" in indicators:
        fig.add_trace(go.Scatter(x=x, y=df["ema20"], name="EMA 20", line=dict(color="yellow", width=1)), row=1, col=1)
    if "Bollinger Bands" in indicators:
        fig.add_trace(go.Scatter(x=x, y=df["bb_upper"], name="BB Upper",
                                 line=dict(color="gray", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["bb_lower"], name="BB Lower",
                                 line=dict(color="gray", width=1, dash="dot"),
                                 fill="tonexty", fillcolor="rgba(128,128,128,0.1)"), row=1, col=1)

    for i, indicator in enumerate(extra_rows, start=2):
        if indicator == "Volume":
            colors = ["green" if c >= o else "red" for c, o in zip(df["close"], open_)]
            fig.add_trace(go.Bar(x=x, y=df["volume"], marker_color=colors, showlegend=False), row=i, col=1)
            fig.update_yaxes(title_text="Volume", row=i, col=1)

        elif indicator == "RSI":
            fig.add_trace(go.Scatter(x=x, y=df["rsi"], line=dict(color="purple", width=1), showlegend=False), row=i, col=1)
            fig.add_hline(y=70, line=dict(color="red",   dash="dot", width=1), row=i, col=1)
            fig.add_hline(y=30, line=dict(color="green", dash="dot", width=1), row=i, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=i, col=1)

        elif indicator == "MACD":
            fig.add_trace(go.Scatter(x=x, y=df["macd"],        name="MACD",   line=dict(color="blue",   width=1), showlegend=False), row=i, col=1)
            fig.add_trace(go.Scatter(x=x, y=df["macd_signal"], name="Signal", line=dict(color="orange", width=1), showlegend=False), row=i, col=1)
            hist_colors = ["green" if v >= 0 else "red" for v in df["macd_hist"]]
            fig.add_trace(go.Bar(x=x, y=df["macd_hist"], marker_color=hist_colors, showlegend=False), row=i, col=1)
            fig.update_yaxes(title_text="MACD", row=i, col=1)

    fig.update_layout(
        title=f"{stock_code} — {timeframe_label} candles",
        xaxis_type="category",
        xaxis_rangeslider_visible=False,
        height=600 + len(extra_rows) * 150,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=0, r=0, t=60, b=0),
    )
    fig.update_xaxes(type="category")
    return fig


def build_compare_chart(stock_dfs: dict[str, pd.DataFrame], timeframe_label: str, mode: str) -> go.Figure:
    """Overlay multiple stocks on one chart, aligned on a shared time index."""
    all_series = {code: to_series(df) for code, df in stock_dfs.items() if not df.empty}
    if not all_series:
        return go.Figure()

    shared_index = sorted(set().union(*[s.index for s in all_series.values()]))
    fig = go.Figure()

    for stock_code, series in all_series.items():
        aligned = series.reindex(shared_index)
        if mode == "% Change":
            base  = aligned.dropna().iloc[0]
            y     = (aligned / base - 1) * 100
            hover = "%{y:.2f}%"
        else:
            y     = aligned
            hover = "$%{y:.2f}"
        fig.add_trace(go.Scatter(
            x=shared_index, y=y, mode="lines", name=stock_code,
            connectgaps=False,
            hovertemplate=f"{stock_code} {hover}<extra></extra>",
        ))

    if mode == "% Change":
        fig.add_hline(y=0, line=dict(color="gray", dash="dot", width=1))

    fig.update_layout(
        title=f"Compare — {timeframe_label} — {mode}",
        xaxis_title="Time",
        yaxis_title="% Change from start" if mode == "% Change" else "Price (USD)",
        xaxis_type="date",
        height=550,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=0, r=0, t=60, b=0),
    )
    return fig


def build_rs_chart(s_stock: pd.Series, s_bench: pd.Series, stock_code: str, bench_code: str) -> go.Figure:
    """Relative Strength chart: % change comparison + RS ratio % change."""
    common  = s_stock.index.intersection(s_bench.index)
    s_stock = s_stock.reindex(common)
    s_bench = s_bench.reindex(common)

    pct_stock = (s_stock / s_stock.iloc[0] - 1) * 100
    pct_bench = (s_bench / s_bench.iloc[0] - 1) * 100
    rs_pct    = ((s_stock / s_bench) / (s_stock.iloc[0] / s_bench.iloc[0]) - 1) * 100

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.05, row_heights=[0.5, 0.5],
        subplot_titles=[
            f"{stock_code} vs {bench_code} — % Change from start",
            f"RS % Change ({stock_code} / {bench_code}) — positive = outperforming",
        ],
    )

    fig.add_trace(go.Scatter(x=common, y=pct_stock, name=stock_code,
                             line=dict(color="#00CC96", width=1.5), connectgaps=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=common, y=pct_bench, name=bench_code,
                             line=dict(color="#636EFA", width=1.5), connectgaps=False), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="gray", dash="dot", width=1), row=1, col=1)

    fig.add_trace(go.Scatter(x=common, y=rs_pct, name="RS",
                             line=dict(color="#FFA15A", width=1.5), connectgaps=False,
                             showlegend=False), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="gray", dash="dot", width=1), row=2, col=1)

    fig.update_yaxes(title_text="% Change",    row=1, col=1)
    fig.update_yaxes(title_text="RS % Change", row=2, col=1)
    fig.update_layout(
        xaxis_type="date", height=600,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=0, r=0, t=60, b=0),
    )
    return fig


def build_news_score_chart(df: pd.DataFrame) -> go.Figure:
    """Scatter plot of news relevance scores over time, grouped by stock."""
    df = df.copy()
    df["date_dt"] = pd.to_datetime(df["date"])
    df["label"]   = df["summary"].str[:60] + "…"

    fig = go.Figure()
    for stock_name, grp in df.groupby("stock"):
        fig.add_trace(go.Scatter(
            x=grp["date_dt"], y=grp["score"],
            mode="markers", name=stock_name,
            marker=dict(size=10, opacity=0.8),
            text=grp["label"],
            hovertemplate="<b>%{text}</b><br>Date: %{x|%Y-%m-%d}<br>Score: %{y:.4f}<extra>%{fullData.name}</extra>",
        ))

    fig.update_layout(
        title="Relevance score by date",
        xaxis_title="Date", yaxis_title="Similarity score",
        xaxis_type="date", height=350,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=0, r=0, t=50, b=0),
    )
    return fig
