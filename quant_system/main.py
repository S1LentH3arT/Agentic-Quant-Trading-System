from data_providers.provider import DataProvider
from engine.analyzer import QuantAnalyzer
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

def test_analysis(symbol, is_cn=False):
    provider = DataProvider()
    analyzer = QuantAnalyzer()

    print(f"Analyzing {symbol}...")

    if is_cn:
        # For A-share, we need dates
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
        df = provider.get_cn_stock_data(symbol, start_date, end_date)
    else:
        # US stock
        df = provider.get_us_stock_data(symbol)

    if df is None or df.empty:
        print("Failed to fetch data.")
        return

    result = analyzer.analyze(df)
    print("\n--- Analysis Result ---")
    print(f"Sentiment: {result['sentiment']}")
    print(f"Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    print(f"Metrics: {result['metrics']}")

if __name__ == "__main__":
    # Test US Stock: Apple
    test_analysis("AAPL")
