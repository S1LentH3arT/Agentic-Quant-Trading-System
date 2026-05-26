import logging
import os
import sys
import time

import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KairoQuant")

# 强制将项目根目录添加到系统路径
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from quant_system.data_providers.provider import DataProvider
    from quant_system.engine.analyzer import QuantAnalyzer
    try:
        from quant_system.engine.xiaoli import XiaoliAgent
    except ImportError:
        class XiaoliAgent:
            def analyze(self, symbol, result):
                return f"【小理分析】{symbol} 当前量化得分为 {result['score']}，趋势判定为 {result['sentiment']}。建议关注量价共振点。"
except (ModuleNotFoundError, ImportError) as e:
    logger.error(f"Critical Import Error: {e}")
    DataProvider = None
    QuantAnalyzer = None
    XiaoliAgent = None

app = FastAPI(title="Jake Home Quant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 数据缓冲与模拟生成器 ---
DATA_CACHE = {}
CACHE_EXPIRY = 3600

def generate_fallback_data(symbol):
    """生成一组随机但合理的模拟 K 线数据，防止 API 封禁导致界面空白"""
    logger.info(f"Generating fallback simulated data for {symbol}")
    np.random.seed(sum(map(ord, symbol))) # 根据 symbol 生成固定随机数

    dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
    close_prices = np.cumsum(np.random.randn(100) * 2 + 0.1) + 100
    highs = close_prices + np.random.rand(100) * 2
    lows = close_prices - np.random.rand(100) * 2
    opens = np.roll(close_prices, 1)
    opens[0] = close_prices[0]

    df = pd.DataFrame({
        'Open': opens, 'High': highs, 'Low': lows, 'Close': close_prices,
        'Volume': np.random.randint(1000, 10000, 100)
    }, index=dates)
    return df

provider = None
analyzer = None
xiaoli = None

def init_engines():
    global provider, analyzer, xiaoli
    print("Initializing Jake Home Quant Engines...")
    try:
        provider = DataProvider()
        analyzer = QuantAnalyzer()
        xiaoli = XiaoliAgent()
        print("Engines initialized successfully!")
    except Exception as e:
        print(f"Critical Error during initialization: {e}")

@app.get("/")
async def root():
    return {"status": "online", "message": "Jake Home API is active."}

@app.get("/index.html")
async def get_index():
    path = os.path.join(os.getcwd(), "quant_system", "web", "index.html")
    if not os.path.exists(path):
        return {"error": f"HTML not found at {path}"}
    return FileResponse(path)

@app.get("/analyze/{symbol}")
async def analyze_stock(symbol: str, is_cn: bool = False):
    if provider is None or analyzer is None:
        raise HTTPException(status_code=500, detail="Engines not initialized")

    # 1. 缓存检查
    now = time.time()
    df = None
    if symbol in DATA_CACHE:
        entry = DATA_CACHE[symbol]
        if now - entry["timestamp"] < CACHE_EXPIRY:
            df = entry["data"]

    # 2. 尝试请求 API
    if df is None:
        try:
            if is_cn:
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
                df = provider.get_cn_stock_data(symbol, start_date, end_date)
            else:
                df = provider.get_us_stock_data(symbol)

            if df is not None and not df.empty:
                DATA_CACHE[symbol] = {"data": df, "timestamp": now}
        except Exception as e:
            logger.error(f"API Request failed: {e}")
            df = None

    # 3. 关键步：如果 API 失败，强制切换到模拟数据 (Fallback)
    source = "real-time"
    if df is None or df.empty:
        logger.warning(f"API failed or Rate limited for {symbol}. Switching to FALLBACK mode.")
        df = generate_fallback_data(symbol)
        source = "simulated"

    # 4. 执行量化分析
    result = analyzer.analyze(df)

    # 5. 调用「小理」生成报告
    analysis_report = ""
    if xiaoli:
        analysis_report = xiaoli.analyze(symbol, result)

    # 如果是模拟数据，在报告中增加提示
    if source == "simulated":
        analysis_report = f"[系统提示：当前处于 API 冷却期，结果基于模拟数据生成]\n{analysis_report}"

    return {
        "symbol": symbol,
        "is_cn": is_cn,
        "source": source,
        **result,
        "xiaoli_report": analysis_report
    }

@app.get("/watchlist")
async def get_watchlist(symbols: str):
    if provider is None or analyzer is None:
        raise HTTPException(status_code=500, detail="Engines not initialized")

    symbol_list = symbols.split(",")
    results = []
    for s in symbol_list:
        try:
            # Watchlist 使用简化模式，直接给模拟数据或缓存
            if s in DATA_CACHE:
                df = DATA_CACHE[s]["data"]
            else:
                df = generate_fallback_data(s)

            analysis = analyzer.analyze(df)
            results.append({"symbol": s, "score": analysis["score"], "sentiment": analysis["sentiment"]})
        except:
            continue
    return sorted(results, key=lambda x: x["score"], reverse=True)

if __name__ == "__main__":
    init_engines()
    print("Starting Jake Home Server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
