import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class SnowballScanner:
    """
    High-Beta Momentum Scanner for the '4200 Point Breakout' scenario.
    Goal: Identify stocks that are strongly resonating with the index breakout.
    """
    def __init__(self, target_index="sh000001"):
        self.target_index = target_index
        print(f"[{datetime.now()}] Snowball Scanner Initialized. Targeting Index: {target_index}")

    def get_market_breadth(self):
        """Get overall market sentiment and index trend."""
        df = ak.stock_zh_a_spot_em()
        return df

    def calculate_beta(self, stock_df, index_df):
        """Calculate the beta of a stock relative to the index."""
        # Simple linear regression for Beta
        merged = pd.merge(stock_df['close'], index_df['close'], left_index=True, right_index=True)
        if len(merged) < 20: return 0

        # Calculate returns
        returns = merged.pct_change().dropna()
        cov = np.cov(returns.iloc[:, 0], returns.iloc[:, 1])[0, 1]
        var = np.var(returns.iloc[:, 1])
        return cov / var if var != 0 else 0

    def scan(self, top_n=5):
        """
        The main scanning pipeline:
        1. Filter by Price/Volume Resonance
        2. Filter by Relative Strength
        3. Calculate Beta for final selection
        """
        print(f"[{datetime.now()}] Scanning for high-resonance targets...")

        # 1. Get all A-shares spot data
        spot_df = ak.stock_zh_a_spot_em()

        # Filter 1: Volume Resonance (Current Vol > 2x Avg Vol)
        # Note: In real scenario, we'd compare with hist data. Here we use spot indicators.
        # We look for stocks with significant gain and high volume
        candidates = spot_df[
            (spot_df['涨跌幅'] > 3) &
            (spot_df['成交额'] > 100000000) # Must be liquid (> 100M)
        ].copy()

        # Filter 2: Relative Strength
        # Assume the index is at 4200 and moving up. We want the leaders.
        # Sort by gain
        candidates = candidates.sort_values(by='涨跌幅', ascending=False)

        # 3. Refined Beta & Momentum Filter
        final_list = []
        for idx, row in candidates.head(50).iterrows():
            symbol = row['代码']
            try:
                # Fetch historical data for Beta and RSI
                stock_hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
                index_hist = ak.stock_zh_a_hist(symbol="000001", period="daily", adjust="qfq") # Using SH000001

                stock_hist['close'] = pd.to_numeric(stock_hist['收盘'])
                index_hist['close'] = pd.to_numeric(index_hist['收盘'])

                beta = self.calculate_beta(stock_hist, index_hist)

                if beta > 1.5:
                    final_list.append({
                        "symbol": symbol,
                        "name": row['名称'],
                        "beta": round(beta, 2),
                        "gain": row['涨跌幅'],
                        "volume": row['成交额']
                    })
            except Exception as e:
                continue

            if len(final_list) >= top_n:
                break

        return pd.DataFrame(final_list)

if __name__ == "__main__":
    scanner = SnowballScanner()
    targets = scanner.scan()
    print("\n--- 🚀 TARGETS FOR SNOWBALL EXECUTION 🚀 ---")
    if not targets.empty:
        print(targets)
    else:
        print("No high-beta targets found matching the criteria.")
