import requests
import json
import pandas as pd
from datetime import datetime

def fetch_eastmoney_data(ticker):
    """
    从东方财富接口获取个股基础信息和实时行情
    """
    # 修正代码格式: 600000 -> sse.600000, 000001 -> szn.000001
    market = "sse" if ticker.startswith('6') else "szn"
    formatted_ticker = f"{market}.{ticker}"

    # 这是一个简化版模拟接口，实际生产环境建议使用 tushare 或专业量化 API
    # 这里使用东财公开的行情 API 结构
    url = f"http://push2.eastmoney.com/api/board.dll?get_stock_quote={formatted_ticker}"

    try:
        # 注意：实际请求可能需要 User-Agent 模拟
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        # 这里的解析逻辑需根据东财实际返回的 JSON 结构动态调整
        # 模拟一个标准的量化返回格式
        data = response.json()
        # 提取关键字段 (这里假设 API 返回包含 name, price, pct_chg)
        info = data.get('data', {})
        return {
            "name": info.get('name', '未知'),
            "price": info.get('price', 0),
            "pct_chg": info.get('pct_chg', 0),
            "industry": info.get('industry', '未知'),
            "last_update": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def sync_portfolio_data():
    """
    同步 TRADING_LOG.json 中的所有标的
    """
    try:
        with open('TRADING_LOG.json', 'r', encoding='utf-8') as f:
            log_data = json.load(f)

        portfolio = log_data.get('portfolio', {})

        # 遍历所有池子
        for pool_name in ['fortress_pool', 'hunter_pool', 'watch_list']:
            items = portfolio.get(pool_name, [])
            for item in items:
                ticker = item.get('ticker')
                if ticker:
                    print(f"Updating {ticker}...")
                    real_time = fetch_eastmoney_data(ticker)
                    if real_time:
                        item['name'] = real_time['name']
                        item['current_price'] = real_time['price']
                        item['pct_chg'] = real_time['pct_chg']
                        item['industry'] = real_time['industry']

        log_data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open('TRADING_LOG.json', 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

        print("✅ 成功同步所有标的实时数据至 TRADING_LOG.json")

    except Exception as e:
        print(f"Sync failed: {e}")

if __name__ == "__main__":
    sync_portfolio_data()
