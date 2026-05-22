import yfinance as yf
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta

class DataProvider:
    def __init__(self):
        # Initialize Baostock for A-share
        try:
            lg = bs.login()
        except Exception as e:
            print(f"Baostock login failed: {e}")

    def get_us_stock_data(self, symbol, period='1d', interval='1h'):
        """Fetch US stock data using yfinance"""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        return df

    def get_cn_stock_data(self, symbol, start_date, end_date):
        """Fetch CN stock data using Baostock"""
        # symbol should be like 'sh.600000'
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,time,open,high,low,close,volume,amount",
            start_date=start_date, end_date=end_date,
            frequency="d", adjust_flag="3"
        )
        data_list = []
        while (rs.next()):
            data_list.append(rs.get_row_data())

        df = pd.DataFrame(data_list, columns=rs.fields)
        # Convert types to numeric
        cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        df.set_index('date', inplace=True)
        return df

    def __del__(self):
        bs.logout()
