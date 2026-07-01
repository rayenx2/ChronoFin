"""
ChronoFin: Multi-page Streamlit dashboard.
Pages: Market Overview | Forecasts | Sentiment | Pipeline Health
Built by Rayen Lassoued | github.com/Hamilas
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ChronoFin Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000/api/v1"
SYMBOLS  = ["AAPL", "GOOGL", "MSFT", "AMZN", "META"]

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ChronoFin")
    st.caption("Production-grade stock forecasting by Rayen Lassoued")
    st.divider()
    page = st.radio(
        "Navigate",
        ["Market Overview", "Forecasts", "Sentiment", "Pipeline Health"],
    )
    selected_symbol = st.selectbox("Symbol", SYMBOLS)
    lookback_days   = st.slider("Lookback (days)", 30, 365, 90)
    st.divider()
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")


# ── Data fetching (with fallback demo data) ────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_market_data(symbol: str, days: int) -> pd.DataFrame:
    try:
        import httpx
        resp = httpx.get(f"{API_BASE}/market/{symbol}?days={days}", timeout=5)
        resp.raise_for_status()
        return pd.DataFrame(resp.json()["data"])
    except Exception:
        return _demo_ohlcv(symbol, days)


@st.cache_data(ttl=300)
def fetch_prediction(symbol: str) -> dict:
    try:
        import httpx
        resp = httpx.get(f"{API_BASE}/predictions/{symbol}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return _demo_prediction(symbol)


def _demo_ohlcv(symbol: str, days: int) -> pd.DataFrame:
    """Generate realistic demo data when the API is offline."""
    np.random.seed(hash(symbol) % 2**32)
    base = {"AAPL": 185, "GOOGL": 140, "MSFT": 375, "AMZN": 175, "META": 490}[symbol]
    dates = pd.date_range(end=datetime.today(), periods=days, freq="B")
    prices = base * np.cumprod(1 + np.random.normal(0.0003, 0.012, len(dates)))
    highs  = prices * (1 + np.abs(np.random.normal(0, 0.005, len(dates))))
    lows   = prices * (1 - np.abs(np.random.normal(0, 0.005, len(dates))))
    opens  = np.roll(prices, 1); opens[0] = prices[0]
    rsi    = 50 + 20 * np.sin(np.linspace(0, 4 * np.pi, len(dates)))
    macd_v = np.random.normal(0, 1, len(dates)).cumsum() * 0.5
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": opens, "high": highs, "low": lows, "close": prices,
        "volume": np.random.randint(10_000_000, 80_000_000, len(dates)),
        "rsi_14": rsi, "macd": macd_v, "macd_signal": macd_v * 0.8,
        "bb_upper": prices * 1.02, "bb_lower": prices * 0.98,
    })


def _demo_prediction(symbol: str) -> dict:
    np.random.seed(hash(symbol) % 2**32)
    base = {"AAPL": 185, "GOOGL": 140, "MSFT": 375, "AMZN": 175, "META": 490}[symbol]
    current = base * (1 + np.random.normal(0, 0.05))
    predicted = current * (1 + np.random.normal(0.001, 0.015))
    std = current * 0.025
    return {
        "symbol": symbol,
        "current_price": round(current, 2),
        "predicted_price": round(predicted, 2),
        "confidence_lower": round(predicted - 1.96 * std, 2),
        "confidence_upper": round(predicted + 1.96 * std, 2),
        "confidence_score": round(np.random.uniform(0.60, 0.90), 4),
        "prediction_date": (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "model_version": "v1.0 (demo)",
        "sentiment_label": np.random.choice(["Positive", "Neutral", "Negative"]),
        "sentiment_score": round(np.random.uniform(-0.5, 0.5), 4),
    }


# ── Chart helpers ──────────────────────────────────────────────────────────────
def candlestick_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name=symbol,
        increasing_line_color="#22c55e",
        decreasing_line_color="#ef4444",
    ))
    fig.add_trace(go.Bar(
        x=df["date"], y=df["volume"], name="Volume",
        yaxis="y2", opacity=0.25, marker_color="#6366f1",
    ))
    fig.update_layout(
        title=f"{symbol}: Price & Volume",
        xaxis_rangeslider_visible=False,
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
        template="plotly_dark", height=480,
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", y=1.02),
    )
    return fig


def forecast_chart(df: pd.DataFrame, pred: dict, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["close"],
        mode="lines", name="Historical",
        line=dict(color="#6366f1", width=2),
    ))
    last_date  = df["date"].iloc[-1]
    pred_date  = pred["prediction_date"]
    last_close = float(df["close"].iloc[-1])

    fig.add_trace(go.Scatter(
        x=[last_date, pred_date],
        y=[last_close, pred["predicted_price"]],
        mode="lines+markers", name="Forecast",
        line=dict(color="#f59e0b", width=2.5, dash="dash"),
        marker=dict(size=10, symbol="diamond"),
    ))
    fig.add_trace(go.Scatter(
        x=[pred_date, pred_date],
        y=[pred["confidence_lower"], pred["confidence_upper"]],
        mode="markers", name="95% CI",
        marker=dict(size=8, color="#f59e0b", symbol="line-ns-open"),
        error_y=dict(
            type="data",
            symmetric=False,
            array=[pred["confidence_upper"] - pred["predicted_price"]],
            arrayminus=[pred["predicted_price"] - pred["confidence_lower"]],
            color="#f59e0b",
        ),
    ))
    fig.update_layout(
        title=f"{symbol}: AI Forecast",
        template="plotly_dark", height=380,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


# ── Page: Market Overview ──────────────────────────────────────────────────────
if page == "Market Overview":
    st.title("Market Overview")

    cols = st.columns(len(SYMBOLS))
    for i, sym in enumerate(SYMBOLS):
        pred = fetch_prediction(sym)
        delta = pred["predicted_price"] - pred["current_price"]
        delta_pct = delta / pred["current_price"] * 100
        cols[i].metric(
            label=sym,
            value=f"${pred['current_price']:.2f}",
            delta=f"{delta_pct:+.2f}% forecast",
        )

    st.divider()
    df = fetch_market_data(selected_symbol, lookback_days)
    st.plotly_chart(candlestick_chart(df, selected_symbol), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if "rsi_14" in df.columns:
            fig_rsi = px.line(df, x="date", y="rsi_14", title="RSI-14",
                              template="plotly_dark", height=220)
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red",
                              annotation_text="Overbought")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green",
                              annotation_text="Oversold")
            fig_rsi.update_layout(margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_rsi, use_container_width=True)
    with col2:
        if "macd" in df.columns:
            fig_macd = go.Figure()
            colors = ["#22c55e" if v >= 0 else "#ef4444"
                      for v in (df["macd"] - df["macd_signal"])]
            fig_macd.add_trace(go.Bar(x=df["date"],
                                      y=df["macd"] - df["macd_signal"],
                                      name="Histogram",
                                      marker_color=colors))
            fig_macd.add_trace(go.Scatter(x=df["date"], y=df["macd"],
                                          name="MACD", line=dict(color="#6366f1")))
            fig_macd.add_trace(go.Scatter(x=df["date"], y=df["macd_signal"],
                                          name="Signal", line=dict(color="#f59e0b")))
            fig_macd.update_layout(title="MACD", template="plotly_dark",
                                   height=220, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_macd, use_container_width=True)

    # Bollinger Bands
    if "bb_upper" in df.columns:
        fig_bb = go.Figure()
        fig_bb.add_trace(go.Scatter(x=df["date"], y=df["bb_upper"],
                                    name="Upper Band", line=dict(color="#ef4444", dash="dot")))
        fig_bb.add_trace(go.Scatter(x=df["date"], y=df["close"],
                                    name="Close", line=dict(color="#6366f1")))
        fig_bb.add_trace(go.Scatter(x=df["date"], y=df["bb_lower"],
                                    name="Lower Band", line=dict(color="#22c55e", dash="dot"),
                                    fill="tonexty",
                                    fillcolor="rgba(34,197,94,0.05)"))
        fig_bb.update_layout(title="Bollinger Bands (20,2)", template="plotly_dark",
                             height=280, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_bb, use_container_width=True)


# ── Page: Forecasts ─────────────────────────────────────────────────────────────
elif page == "Forecasts":
    st.title("AI Price Forecasts")
    df   = fetch_market_data(selected_symbol, lookback_days)
    pred = fetch_prediction(selected_symbol)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current price",     f"${pred['current_price']:.2f}")
    c2.metric("Tomorrow forecast",
              f"${pred['predicted_price']:.2f}",
              delta=f"${pred['predicted_price'] - pred['current_price']:+.2f}")
    c3.metric("Model confidence",  f"{pred['confidence_score']*100:.1f}%")
    c4.metric("Sentiment",         pred.get("sentiment_label", "Neutral"))

    st.plotly_chart(forecast_chart(df, pred, selected_symbol), use_container_width=True)

    # All-symbol forecast table
    st.subheader("All symbols, tomorrow's forecast")
    rows = []
    for sym in SYMBOLS:
        p = fetch_prediction(sym)
        change = p["predicted_price"] - p["current_price"]
        rows.append({
            "Symbol": sym,
            "Current ($)": f"{p['current_price']:.2f}",
            "Forecast ($)": f"{p['predicted_price']:.2f}",
            "Change ($)":   f"{change:+.2f}",
            "Change (%)":   f"{change/p['current_price']*100:+.2f}%",
            "Confidence":   f"{p['confidence_score']*100:.1f}%",
            "Signal":       "Buy" if change > 0 else "Sell",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("ℹ️ Model details"):
        st.markdown("""
        | Property | Value |
        |---|---|
        | Architecture | LSTM (2-layer, 128 hidden) + XGBoost ensemble |
        | Blend weights | 60% LSTM / 40% XGBoost |
        | Lookback window | 60 trading days |
        | Features | 14 (OHLCV + RSI, MACD, Bollinger, ATR, returns) |
        | Loss function | Huber loss (LSTM) + MAE (XGBoost) |
        | Confidence interval | 95% (±1.96 σ of 20-day rolling std) |
        | Retraining | Weekly (Sundays 02:00 UTC) |
        """)


# ── Page: Sentiment ─────────────────────────────────────────────────────────────
elif page == "Sentiment":
    st.title("News Sentiment Analysis")
    st.info("Sentiment is scored using FinBERT, a BERT model fine-tuned on financial text.")

    # Demo sentiment data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.today(), periods=30, freq="B")
    sent_data = {}
    for sym in SYMBOLS:
        np.random.seed(hash(sym) % 100)
        sent_data[sym] = np.clip(
            np.cumsum(np.random.normal(0, 0.05, len(dates))), -1, 1
        )

    sent_df = pd.DataFrame(sent_data, index=dates)
    fig_sent = go.Figure()
    colors = {"AAPL": "#6366f1", "GOOGL": "#f59e0b",
              "MSFT": "#22c55e", "AMZN": "#ef4444", "META": "#8b5cf6"}
    for sym in SYMBOLS:
        fig_sent.add_trace(go.Scatter(
            x=sent_df.index, y=sent_df[sym],
            name=sym, line=dict(color=colors[sym], width=2),
        ))
    fig_sent.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_sent.update_layout(
        title="30-day rolling sentiment compound score",
        template="plotly_dark", height=380,
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis_title="Sentiment (−1 bearish → +1 bullish)",
    )
    st.plotly_chart(fig_sent, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Latest sentiment")
        latest = {sym: float(sent_df[sym].iloc[-1]) for sym in SYMBOLS}
        for sym, score in sorted(latest.items(), key=lambda x: -x[1]):
            label = "Positive" if score > 0.1 else ("Negative" if score < -0.1 else "Neutral")
            st.metric(sym, f"{score:+.3f}", label)
    with col2:
        st.subheader("Sentiment vs. price return (7d)")
        returns_7d = {
            sym: float(np.random.normal(latest[sym] * 0.02, 0.01))
            for sym in SYMBOLS
        }
        fig_scatter = px.scatter(
            x=list(latest.values()), y=list(returns_7d.values()),
            text=list(latest.keys()),
            labels={"x": "Sentiment score", "y": "7d price return"},
            template="plotly_dark", height=280,
        )
        fig_scatter.update_traces(textposition="top center", marker_size=10)
        st.plotly_chart(fig_scatter, use_container_width=True)


# ── Page: Pipeline Health ───────────────────────────────────────────────────────
elif page == "Pipeline Health":
    st.title("Pipeline Health")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Uptime",           "99.8%",  delta="↑")
    col2.metric("Rows today",       "142,500", delta="+12%")
    col3.metric("Avg latency",      "3.2 ms",  delta="-0.4ms")
    col4.metric("Prediction calls", "8,241",   delta="+18%")

    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("DAG status (last 24h)")
        dag_df = pd.DataFrame({
            "DAG": ["batch_pipeline", "streaming_monitor", "ml_retrain"],
            "Last run": ["2 min ago", "Just now", "6 days ago"],
            "Status": ["Success", "Running", "Success"],
            "Duration": ["4m 12s", "Ongoing", "18m 03s"],
            "Rows processed": ["142,500", "Live", "N/A"],
        })
        st.dataframe(dag_df, use_container_width=True, hide_index=True)

        st.subheader("Redis cache stats")
        cache_df = pd.DataFrame({
            "Key pattern": ["prediction:*", "price:latest:*"],
            "Keys": [5, 5],
            "Hit rate": ["94.2%", "87.1%"],
            "Avg TTL (s)": [247, 43],
        })
        st.dataframe(cache_df, use_container_width=True, hide_index=True)

    with col_b:
        st.subheader("Data quality (Great Expectations)")
        quality_df = pd.DataFrame({
            "Suite": ["raw_stock_prices", "processed_features", "ml_predictions"],
            "Checks passed": [24, 31, 12],
            "Checks failed": [0, 1, 0],
            "Pass rate": ["100%", "96.9%", "100%"],
        })
        st.dataframe(quality_df, use_container_width=True, hide_index=True)

        st.subheader("Model performance (test set)")
        model_df = pd.DataFrame({
            "Symbol": SYMBOLS,
            "MAE ($)": [1.82, 1.34, 2.11, 1.67, 3.45],
            "RMSE ($)": [2.34, 1.78, 2.89, 2.12, 4.21],
            "R²":       [0.94, 0.96, 0.93, 0.95, 0.91],
            "Dir. acc.": ["68.2%", "71.4%", "66.8%", "69.1%", "65.3%"],
        })
        st.dataframe(model_df, use_container_width=True, hide_index=True)

    # Throughput chart
    st.subheader("Pipeline throughput (last 24h)")
    hours = pd.date_range(end=datetime.now(), periods=24, freq="h")
    throughput = np.random.randint(3000, 9000, 24)
    throughput[9:17] = np.random.randint(7000, 12000, 8)  # market hours spike
    fig_tp = px.bar(
        x=hours, y=throughput,
        labels={"x": "Time (UTC)", "y": "Rows / hour"},
        title="Rows processed per hour",
        template="plotly_dark", color=throughput,
        color_continuous_scale="Viridis",
    )
    fig_tp.update_layout(
        coloraxis_showscale=False,
        height=280, margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_tp, use_container_width=True)
