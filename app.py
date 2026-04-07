import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="AI Stock Pro Dashboard", layout="wide")

st.title("🚀 AI Stock Pro Dashboard")

# Sidebar
st.sidebar.header("Settings")
stock_symbol = st.sidebar.text_input("Stock Symbol", "RELIANCE.NS")
period = st.sidebar.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y"])
interval = st.sidebar.selectbox("Data Interval", ["1d", "1wk", "1mo"])

@st.cache_data
def load_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period=period, interval=interval)
    return data

# Fetch data
with st.spinner("Loading stock data..."):
    data = load_data(stock_symbol, period, interval)

if data is None or data.empty:
    st.error("No data available. Please enter a valid stock symbol and try again.")
else:
    data = data.dropna(subset=["Close"])
    if data.empty:
        st.error("No closing prices found for this symbol.")
    else:
        data["MA50"] = data["Close"].rolling(window=50, min_periods=1).mean()

        # RSI Calculation
        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14, min_periods=1).mean()
        avg_loss = loss.rolling(window=14, min_periods=1).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        data["RSI"] = 100 - (100 / (1 + rs))

        latest = data.iloc[-1]
        latest_price = latest["Close"]
        latest_ma = latest["MA50"]
        latest_rsi = latest["RSI"]

        # Layout
        col1, col2, col3 = st.columns(3)

        col1.metric("💰 Price", f"{latest_price:.2f}")
        col2.metric("📊 MA50", f"{latest_ma:.2f}")
        col3.metric("⚡ RSI", f"{latest_rsi:.2f}" if pd.notna(latest_rsi) else "N/A")

        st.subheader("📈 Price & MA50")
        st.line_chart(data[["Close", "MA50"]])

        st.subheader("📊 RSI")
        st.line_chart(data["RSI"])

        # Signal Logic
        st.subheader("📢 AI Signal")
        if pd.notna(latest_rsi):
            if latest_price > latest_ma and latest_rsi < 30:
                st.success("🔥 STRONG BUY (Trend Up + Oversold)")
            elif latest_price < latest_ma and latest_rsi > 70:
                st.error("🚨 STRONG SELL (Trend Down + Overbought)")
            elif latest_price > latest_ma:
                st.info("📊 BUY (Uptrend)")
            else:
                st.warning("📉 SELL (Downtrend)")
        else:
            st.info("Waiting for enough data to compute RSI.")

        st.subheader("📋 Latest Data")
        st.dataframe(
            data.tail(10).style.format({
                "Close": "{:.2f}",
                "MA50": "{:.2f}",
                "RSI": "{:.2f}"
            })
        )