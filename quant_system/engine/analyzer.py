import talib
import pandas as pd
import numpy as np

class QuantAnalyzer:
    def __init__(self):
        pass

    def analyze(self, df):
        """
        Comprehensive analysis of the provided dataframe (K-line data)
        Expected columns: open, high, low, close, volume
        """
        close = df['Close'].values if 'Close' in df.columns else df['close'].values
        high = df['High'].values if 'High' in df.columns else df['high'].values
        low = df['Low'].values if 'Low' in df.columns else df['low'].values
        volume = df['Volume'].values if 'Volume' in df.columns else df['volume'].values

        # 1. Trend Indicators
        sma_20 = talib.SMA(close, timeperiod=20)
        ema_50 = talib.EMA(close, timeperiod=50)
        macd, macdsignal, macdhist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)

        # 2. Momentum Indicators
        rsi = talib.RSI(close, timeperiod=14)
        stoch = talib.STOCH(high, low, close) # Returns slowk, slowd

        # 3. Volatility Indicators
        upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
        atr = talib.ATR(high, low, close, timeperiod=14)

        # Current values
        curr_close = close[-1]
        curr_rsi = rsi[-1]
        curr_macd = macd[-1]
        curr_macd_sig = macdsignal[-1]

        # --- Trend Scoring Logic (KairoTrend-style) ---
        score = 0
        reasons = []

        # Trend Analysis
        if curr_close > sma_20[-1]:
            score += 1
            reasons.append("Price above SMA20 (Bullish)")
        else:
            score -= 1
            reasons.append("Price below SMA20 (Bearish)")

        if curr_macd > curr_macd_sig:
            score += 1
            reasons.append("MACD Bullish Crossover")
        else:
            score -= 1
            reasons.append("MACD Bearish Crossover")

        # Momentum Analysis
        if curr_rsi > 70:
            score -= 1 # Overbought potential
            reasons.append("RSI Overbought (>70)")
        elif curr_rsi < 30:
            score += 1 # Oversold potential
            reasons.append("RSI Oversold (<30)")
        elif 40 < curr_rsi < 60:
            reasons.append("RSI Neutral")

        # Sentiment
        sentiment = "Neutral"
        if score >= 2: sentiment = "Strong Bullish"
        elif score == 1: sentiment = "Bullish"
        elif score == -1: sentiment = "Bearish"
        elif score <= -2: sentiment = "Strong Bearish"

        return {
            "score": score,
            "sentiment": sentiment,
            "reasons": reasons,
            "metrics": {
                "rsi": float(curr_rsi),
                "macd": float(curr_macd),
                "close": float(curr_close)
            }
        }
