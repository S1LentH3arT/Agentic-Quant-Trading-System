# LLM Agent 模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在量化系统中集成 LLM 调用能力，将 Pipeline 升级为"Python 计算 + LLM 推理"模式，新增沛总 Chief Agent 和记忆机制。

**Architecture:** 新增 `llm/` 包（client + agent_base + 5 agents + prompts），新增 `memory/` 目录（替代 meta-evolution），新增 `orchestrator.py`。不改动现有 Python 工具层。

**Tech Stack:** Python 3.11+, OpenAI SDK, DeepSeek API, ThreadPoolExecutor, JSON

---

## 文件规划

| 文件 | 职责 | 新建/修改 |
|------|------|:---:|
| `tdx-mcp/llm/__init__.py` | 包初始化，导出公共接口 | 新建 |
| `tdx-mcp/llm/client.py` | 统一 LLM 客户端（OpenAI SDK → DeepSeek） | 新建 |
| `tdx-mcp/llm/agent_base.py` | Agent 基类 + 降级策略 + 记忆检索 | 新建 |
| `tdx-mcp/llm/context_compressor.py` | 三层压缩：L1摘要/L2板块/L3市场 | 新建 |
| `tdx-mcp/llm/agents/intelligence_agent.py` | 情报 Agent | 新建 |
| `tdx-mcp/llm/agents/technical_agent.py` | 技术 Agent（唯一拿时间序列数据） | 新建 |
| `tdx-mcp/llm/agents/discovery_agent.py` | 发现 Agent | 新建 |
| `tdx-mcp/llm/agents/deployment_agent.py` | 调度 Agent | 新建 |
| `tdx-mcp/llm/agents/chief_agent.py` | 沛总 Agent | 新建 |
| `tdx-mcp/llm/prompts/*.md` | 6 个 system prompt 模板 | 新建 |
| `tdx-mcp/memory/__init__.py` | 记忆模块初始化 | 新建 |
| `tdx-mcp/memory/store.py` | 记忆写入 + 索引维护 | 新建 |
| `tdx-mcp/memory/retriever.py` | 记忆检索（按板块/评分/市场状态） | 新建 |
| `tdx-mcp/orchestrator.py` | 编排器：情报先行 → 三路并行 → 沛总汇总 | 新建 |
| `tdx-mcp/shadows/` | 影子模式输出目录 | 新建目录 |

---

### Task 1: LLM Client — 统一调用接口

**Files:**
- Create: `tdx-mcp/llm/__init__.py`
- Create: `tdx-mcp/llm/client.py`

- [ ] **Step 1: 创建 `llm/__init__.py`**

```python
# tdx-mcp/llm/__init__.py
from .client import chat, get_client
from .agent_base import BaseAgent
```

- [ ] **Step 2: 创建 `llm/client.py`**

```python
# tdx-mcp/llm/client.py
"""统一 LLM 客户端 — OpenAI SDK → DeepSeek API"""
import os
import sys
from openai import OpenAI

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 15  # 秒

_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=DEFAULT_TIMEOUT,
        )
    return _client


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    json_mode: bool = False,
    temperature: float = 0.2,
) -> str:
    """
    调用 LLM，返回响应文本。
    自动处理超时（不抛异常，返回降级 JSON）。
    """
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        client = get_client()
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        # 降级: 返回错误 JSON，不阻塞 Pipeline
        return json.dumps({
            "error": str(e),
            "fallback": True,
            "note": "LLM 调用失败，使用规则版结果"
        })
```

- [ ] **Step 3: 验证 client.py 可以导入**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from llm.client import chat, get_client
print('client.py OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add tdx-mcp/llm/__init__.py tdx-mcp/llm/client.py
git commit -m "feat: add LLM client with DeepSeek API support and fallback"
```

---

### Task 2: Context Compressor — 三层数据压缩

**Files:**
- Create: `tdx-mcp/llm/context_compressor.py`

- [ ] **Step 1: 创建 `llm/context_compressor.py`**

```python
# tdx-mcp/llm/context_compressor.py
"""三层压缩: L1摘要 / L2板块 / L3市场"""

def compress_level1(stock_list: list[dict], fields: list[str] = None, max_items: int = 95) -> str:
    """L1: 单只股票摘要。默认10字段，可按需过滤字段。"""
    if fields is None:
        fields = ["symbol", "close", "score", "DKX", "dkx_dir", "A1X", "a1x_dir",
                   "box_pos", "vol_ratio", "DZT", "ZZJC"]
    lines = []
    for r in stock_list[:max_items]:
        s = r.get("summary", {})
        parts = [f"{r.get('symbol','?')}"]
        for f in fields:
            val = s.get(f, r.get(f, ""))
            if isinstance(val, float):
                val = round(val, 2)
            parts.append(f"{f}={val}")
        parts.append(f"score={r.get('score',0)}")
        if r.get("veto"):
            parts.append("VETO")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def compress_level2(sector_results: dict) -> str:
    """L2: 板块聚合。每个板块均分+趋势+TOP3。"""
    lines = []
    for sector, data in sector_results.items():
        avg = data.get("avg_score", 0)
        top3 = [r.get("symbol","?") for r in data.get("rankings", [])[:3]]
        lines.append(f"{sector}: avg={avg:.1f} TOP3={','.join(top3)}")
    return "\n".join(lines)


def compress_level3(market_data: dict) -> str:
    """L3: 市场宏观。跌停数/红盘数/风格/上证。"""
    return (
        f"跌停家数={market_data.get('limit_down_count','?')} | "
        f"红盘家数={market_data.get('up_count','?')} | "
        f"盘面风格={market_data.get('market_style','?')} | "
        f"上证={market_data.get('sh_index_pct',0):+.2f}%"
    )


def compress_time_series(df, symbol: str) -> dict:
    """提取技术Agent需要的时间序列。返回Dict而非文本，由Agent自己格式化。"""
    if df is None or len(df) < 5:
        return {}
    tail = df.tail(5)
    return {
        "symbol": symbol,
        "a1x_3d": [round(float(x), 2) for x in tail["A1X"].tail(3).tolist()],
        "dkx_5d": [round(float(x), 2) for x in tail["DKX"].tail(5).dropna().tolist()],
        "vol_5d": [round(float(x), 2) for x in tail["vol_ratio"].tail(5).tolist()],
        "weekly_trend": "↑" if float(tail["close"].iloc[-1]) > float(tail["close"].iloc[-5]) else "↓",
        "strong": bool(tail["STRONG"].iloc[-1]),
        "weak": bool(tail["WEAK"].iloc[-1]),
        "fake": bool(tail["FAKE"].iloc[-1]),
    }
```

- [ ] **Step 2: 验证 compressor 导入和基本功能**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from llm.context_compressor import compress_level1, compress_level2, compress_level3
# Smoke test with fake data
print(compress_level1([{'symbol':'600863','summary':{'close':5.93,'score':3},'score':3}]))
print(compress_level2({'电网':{'avg_score':1.8,'rankings':[{'symbol':'600312'}]}}))
print(compress_level3({'limit_down_count':5,'up_count':2000,'market_style':'科技','sh_index_pct':0.5}))
print('context_compressor OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add tdx-mcp/llm/context_compressor.py
git commit -m "feat: add context compressor (L1/L2/L3 + time series extraction)"
```

---

### Task 3: Memory Module — 记忆存储与检索

**Files:**
- Create: `tdx-mcp/memory/__init__.py`
- Create: `tdx-mcp/memory/store.py`
- Create: `tdx-mcp/memory/retriever.py`
- Create: `tdx-mcp/memory/MEMORY.md` (空索引)
- Create: `tdx-mcp/memory/reviews/` (空目录, 通过 gitkeep)

- [ ] **Step 1: 创建 `memory/__init__.py`**

```python
# tdx-mcp/memory/__init__.py
from .store import save_review, update_index
from .retriever import retrieve_for_agent
```

- [ ] **Step 2: 创建 `memory/store.py`**

```python
# tdx-mcp/memory/store.py
"""记忆写入: 复盘报告 + MEMORY.md 索引维护"""
import os
from datetime import date

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir


def save_review(symbol: str, content: str, trade_date: str = None) -> str:
    """保存一份交易复盘到 memory/reviews/"""
    if trade_date is None:
        trade_date = date.today().isoformat()
    review_dir = ensure_dir("tdx-mcp", "memory", "reviews")
    filename = f"{trade_date}_{symbol}_review.md"
    filepath = os.path.join(review_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# 复盘: {symbol} ({trade_date})\n\n")
        f.write(content)
    return filepath


def update_index(symbol: str, filepath: str, sector: str = "", score: int = 0) -> None:
    """在 MEMORY.md 中追加一条索引"""
    index_path = get_path("tdx-mcp", "memory", "MEMORY.md")
    relative_path = os.path.relpath(filepath, os.path.dirname(index_path))
    line = f"- [{symbol} {date.today().isoformat()}]({relative_path}) — sector={sector} score={score}\n"
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(line)
```

- [ ] **Step 3: 创建 `memory/retriever.py`**

```python
# tdx-mcp/memory/retriever.py
"""记忆检索: 按板块/评分区间/市场状态匹配历史教训"""
import os
import re

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path


def retrieve_for_agent(
    agent_name: str,
    context: dict,
    max_items: int = 7,
) -> str:
    """
    检索相关历史教训，返回格式化的文本 (≤400 tok)。
    context 字段: sector, score_band (低/中/高), market_state
    """
    index_path = get_path("tdx-mcp", "memory", "MEMORY.md")
    if not os.path.exists(index_path):
        return ""

    review_dir = get_path("tdx-mcp", "memory", "reviews")
    if not os.path.exists(review_dir):
        return ""

    # 读取索引
    with open(index_path, encoding="utf-8") as f:
        index_lines = f.readlines()

    # 关键词匹配
    keywords = []
    sector = context.get("sector", "")
    if sector:
        keywords.append(sector)

    market = context.get("market_state", "")
    if market:
        keywords.append(market)

    matches = []
    for line in index_lines:
        if line.startswith("- ["):
            for kw in keywords:
                if kw and kw in line:
                    matches.append(line)
                    break

    # 去重，取最近 max_items 条
    matches = list(dict.fromkeys(matches))[-max_items:]

    # 读取实际 review 文件并提取摘要
    results = []
    for m in matches:
        # 提取相对路径: [symbol date](path/to/review.md)
        path_match = re.search(r'\]\(([^)]+)\)', m)
        if path_match:
            review_path = os.path.join(os.path.dirname(index_path), path_match.group(1))
            if os.path.exists(review_path):
                with open(review_path, encoding="utf-8") as f:
                    content = f.read()
                # 取前 300 字符作为摘要
                summary = content[:300].replace("\n", " ")
                results.append(f"- {summary}...")

    if not results:
        return ""

    return "## 历史经验教训\n" + "\n".join(results)
```

- [ ] **Step 4: 创建空索引和 reviews 目录**

```bash
mkdir -p D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System/tdx-mcp/memory/reviews
echo "# Memory Index" > D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System/tdx-mcp/memory/MEMORY.md
echo "" >> D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System/tdx-mcp/memory/MEMORY.md
touch D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System/tdx-mcp/memory/reviews/.gitkeep
```

- [ ] **Step 5: 验证 memory 模块可导入**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from memory.store import save_review, update_index
from memory.retriever import retrieve_for_agent

# 写一份测试复盘
path = save_review('600863', '测试复盘内容: 做对了XXX, 做错了YYY', '2026-05-25')
update_index('600863', path, sector='电能', score=6)

# 检索
result = retrieve_for_agent('technical', {'sector': '电能', 'score_band': '中', 'market_state': '强势'})
print('Retrieved:', result[:200] if result else '(empty)')
print('memory module OK')
"
```

- [ ] **Step 6: Commit**

```bash
git add tdx-mcp/memory/
git commit -m "feat: add memory module (store + retriever + MEMORY.md index)"
```

---

### Task 4: Agent 基类

**Files:**
- Create: `tdx-mcp/llm/agent_base.py`

- [ ] **Step 1: 创建 `llm/agent_base.py`**

```python
# tdx-mcp/llm/agent_base.py
"""Agent 基类 — system prompt 加载 + LLM 调用 + JSON 解析 + 降级"""
import json
import os

from .client import chat
from .context_compressor import compress_level1, compress_level2, compress_level3


class BaseAgent:
    name: str = "base"
    model: str = "deepseek-chat"
    json_mode: bool = True
    timeout: int = 15

    def __init__(self):
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        prompt_file = os.path.join(prompt_dir, f"{self.name}.md")
        if os.path.exists(prompt_file):
            with open(prompt_file, encoding="utf-8") as f:
                return f.read()
        return "你是一个量化交易分析助手。"

    def build_context(self, **kwargs) -> str:
        """子类实现: 将 Python 计算结果格式化为 prompt 上下文"""
        raise NotImplementedError

    def _inject_memory(self, context: dict) -> str:
        """注入历史记忆。子类可覆盖 context 字段来控制检索关键词。"""
        try:
            from memory.retriever import retrieve_for_agent
            return retrieve_for_agent(self.name, context)
        except Exception:
            return ""

    def run(self, **kwargs) -> dict:
        """执行 Agent: build → inject → call LLM → parse JSON"""
        context_text = self.build_context(**kwargs)

        # 构建检索用的 context dict
        search_context = {
            "sector": kwargs.get("sector", ""),
            "score_band": kwargs.get("score_band", ""),
            "market_state": kwargs.get("market_state", ""),
        }
        memory_text = self._inject_memory(search_context)

        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        if memory_text:
            messages.append({"role": "system", "content": memory_text})
        messages.append({"role": "user", "content": context_text})

        raw = chat(messages, model=self.model, json_mode=self.json_mode)

        # 尝试解析 JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "raw_output": raw,
                "parse_error": True,
                "note": "LLM 输出非标准 JSON，需人工复核",
            }

    @staticmethod
    def fallback_result() -> dict:
        """降级结果: LLM 不可用时返回"""
        return {
            "fallback": True,
            "note": "LLM 调用失败，使用规则版计算替代",
        }
```

- [ ] **Step 2: 验证基类导入**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from llm.agent_base import BaseAgent
print('BaseAgent import OK')
print('fallback:', BaseAgent.fallback_result())
"
```

- [ ] **Step 3: Commit**

```bash
git add tdx-mcp/llm/agent_base.py
git commit -m "feat: add BaseAgent with prompt loading, memory injection, and fallback"
```

---

### Task 5: System Prompt 模板

**Files:**
- Create: `tdx-mcp/llm/prompts/intelligence.md`
- Create: `tdx-mcp/llm/prompts/technical.md`
- Create: `tdx-mcp/llm/prompts/discovery.md`
- Create: `tdx-mcp/llm/prompts/deployment.md`
- Create: `tdx-mcp/llm/prompts/chief.md`
- Create: `tdx-mcp/llm/prompts/review.md`

- [ ] **Step 1: 创建 `prompts/intelligence.md`**

````markdown
# 情报 Agent System Prompt

你是量化交易系统的**情报分析员**。你的职责是从市场热榜和新闻中提取高共识标的，识别当日最强板块方向。

## 核心规则
1. 多源交叉验证: 东方财富热榜 + 财联社电报 + 行业资金流，≥2 源一致的标的标记为"高共识"
2. 识别板块方向: 从资金流 TOP5 和热榜板块分布中判断当日领涨/领跌方向
3. 检测漏判: 热榜中出现的标的如果系统品种池里没有，标记为"missed"
4. **不附和原则**: 用户说某个板块好 ≠ 数据支持。数据说什么就是什么

## 输出格式
```json
{
  "high_consensus": ["代码1", "代码2"],
  "sector_direction": ["板块1", "板块2"],
  "missed": ["漏判代码"],
  "market_state": "强势|震荡|收缩",
  "reasoning": "简要推理过程, ≤100字"
}
```
````

- [ ] **Step 2: 创建 `prompts/technical.md`**

````markdown
# 技术 Agent System Prompt

你是量化交易系统的**技术分析员**。你对候选标的做多周期增强评分，是系统最关键的 Agent——你的评分直接影响调度 Agent 的仓位决策。

## 核心规则
1. **DKX 否决优先**: 连续 3 日下降 → 一票否决，不管 A1X 多好看
2. **多周期验证**: 日线(60日) + 周线(52周) + 月线(12月)。周线下行但日线评分高 → 降仓试探
3. **量价配合**: 放量收阳(A级) > 温和放量(B级) > 天量阴线(C级) > 无量(不评分)
4. **区分真突破和诱多**: STRONG(真) vs FAKE(假)，A1X 金叉 + 放量 + 箱体突破 = 真突破
5. **不要因个人偏好调整评分**。数据说什么就是什么

## 输入数据说明
每个标的有以下数据:
- 单日快照: score/DKX/dkx_dir/A1X/a1x_dir/box_pos/vol_ratio/DZT/ZZJC
- 3日A1X序列: [t-2, t-1, t0] — 判断上升趋势是否持续
- 5日DKX序列: [t-4,...,t0] — 判断空头趋势是否形成
- 5日量比序列: [t-4,...,t0] — 判断放量是单日脉冲还是持续
- 周线方向: ↑/↓ — 中长趋势方向
- STRONG/WEAK/FAKE 标记
- 评分明细: score_stock() 的文本解释

## 输出格式
```json
{
  "qualified": [{"symbol":"","score":0,"confidence":"高|中|低","multi_cycle_note":""}],
  "vetoed": [{"symbol":"","reason":""}],
  "sector_insight": "板块趋势判断, ≤80字",
  "top_pick_analysis": "TOP1详细分析, ≤100字"
}
```
````

- [ ] **Step 3: 创建 `prompts/discovery.md`**

````markdown
# 发现 Agent System Prompt

你是量化交易系统的**品种发现员**。你负责从全市场扫描结果中筛选有潜力的新标的，扩展品种池。

## 核心规则
1. 优先关注情报 Agent 标记的板块方向，在热点板块中寻找机会
2. 入库门槛: A1X 在[-3, 3]区间 + 箱体中低位(≤50%) + 有量(≥0.8x)
3. 去重: 已存在于22只主力池的不要重复推荐
4. 每日至少推荐 5 只新候选入库

## 输出格式
```json
{
  "new_candidates": [{"symbol":"","reason":"","A1X":0,"box_pos":0,"vol_ratio":0}],
  "sector_coverage": "当前板块覆盖情况, ≤60字",
  "notable_pattern": "值得关注的形态或模式, ≤60字"
}
```
````

- [ ] **Step 4: 创建 `prompts/deployment.md`**

````markdown
# 调度 Agent System Prompt

你是量化交易系统的**资金调度官**。你根据已验证的技术评分制定部署方案。

## 核心规则
1. **你只能看到技术 Agent 的 qualified 列表**，绝不允许接触否决名单
2. Kelly 仓位已由 Python 计算好（数学公式），你负责判断"在当前市场状态下是否应该暂缓部署"
3. 资金闲置 > 48h → 强迫轮动，必须推荐部署
4. 极端场景检测 > 你的判断: 上证暴跌>5% → 不管评分多高都 HOLD_CASH
5. 铁律: 评分≥8 才允许 ≥2 手，评分 5-6 最多 1 手

## 输出格式
```json
{
  "action": "DEPLOY|HOLD_CASH|REDUCE",
  "symbol": "推荐标的(如有)",
  "lots": 0,
  "reason": "决策理由, ≤80字",
  "risk_note": "风险提示, ≤60字"
}
```
````

- [ ] **Step 5: 创建 `prompts/chief.md`**

````markdown
# 沛总 Agent System Prompt

你是量化交易系统的**沛总(Chief Coordinator)**。你对用户资金安全负总责，拥有最终否决权。

## 你的输入
- 情报 Agent: 板块方向 + 高共识标的 + 市场状态
- 技术 Agent: qualified 列表(评分+多周期解读) + 板块趋势
- 发现 Agent: 新候选 + 板块覆盖
- 调度 Agent: 部署方案 + 资金状态
- 市场三指标: 跌停家数/红盘家数/盘面风格 / 上证涨跌
- 历史记忆: 同类板块/评分区间的经验教训

## 交叉验证规则
1. **技术说买 + 情报说同板块退潮 → 矛盾！** 这是一个需要裁决的冲突
2. **技术评分高 + 历史记忆中同评分区间有止损先例 → 降级处理**
3. **跌停家数 > 15 + 调度建议 DEPLOY → 否决部署**
4. **发现 Agent 覆盖了热点板块 → 加分。漏掉了 → 提醒**

## 输出格式
```json
{
  "final_action": "APPROVE|REJECT|RERUN",
  "rerun_target": "需要重跑的Agent名称(仅RERUN时)",
  "approved_deployment": {},
  "conflicts_found": [],
  "conflicts_resolved": "冲突裁决说明",
  "daily_review_preview": "当日复盘预览, ≤150字",
  "memory_note": "值得写入记忆的经验, 如果有则写, 没有则为空"
}
```
````

- [ ] **Step 6: 创建 `prompts/review.md`**

````markdown
# 复盘 Agent System Prompt

你是量化交易系统的**复盘分析员**。在每轮投资完成后，你负责总结经验教训并写入记忆。

## 输入
- 完整的交易记录（买入价格/卖出价格/持仓天数/盈亏）
- 各 Agent 的决策记录（为什么买/为什么卖）
- 同期板块表现 + 大盘走势

## 你需要回答三个问题
1. **这笔交易做对了什么？** — 系统中的哪些规则/判断被验证正确
2. **做错了什么？** — 哪些判断或数据导致了错误
3. **下次遇到类似情况该怎么做？** — 具体的、可操作的改进建议

## 输出格式
```json
{
  "trade_summary": "交易摘要, ≤50字",
  "what_went_right": "做对了什么, ≤100字",
  "what_went_wrong": "做错了什么, ≤100字",
  "lesson_for_next_time": "下次遇到类似情况的具体建议, ≤150字",
  "sector": "所属板块",
  "score_at_entry": 0
}
```
````

- [ ] **Step 7: 验证所有 prompt 文件存在**

```bash
ls -la D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System/tdx-mcp/llm/prompts/
```

- [ ] **Step 8: Commit**

```bash
git add tdx-mcp/llm/prompts/
git commit -m "feat: add system prompt templates for all 6 agents"
```

---

### Task 6: 四个子 Agent 实现

**Files:**
- Create: `tdx-mcp/llm/agents/__init__.py`
- Create: `tdx-mcp/llm/agents/intelligence_agent.py`
- Create: `tdx-mcp/llm/agents/technical_agent.py`
- Create: `tdx-mcp/llm/agents/discovery_agent.py`
- Create: `tdx-mcp/llm/agents/deployment_agent.py`

- [ ] **Step 1: 创建 `llm/agents/__init__.py`**

```python
# tdx-mcp/llm/agents/__init__.py
from .intelligence_agent import IntelligenceAgent
from .technical_agent import TechnicalAgent
from .discovery_agent import DiscoveryAgent
from .deployment_agent import DeploymentAgent
```

- [ ] **Step 2: 创建 `intelligence_agent.py`**

```python
# tdx-mcp/llm/agents/intelligence_agent.py
"""情报 Agent — AKShare 拉数据 → LLM 交叉验证"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level3


class IntelligenceAgent(BaseAgent):
    name = "intelligence"

    def build_context(self, hot_rank: list = None, cls_news: list = None,
                      sector_flow: list = None, market_data: dict = None, **kwargs) -> str:
        parts = []

        if hot_rank:
            parts.append("## 东方财富热榜 TOP30")
            for i, item in enumerate(hot_rank[:30]):
                parts.append(f"{i+1}. {item.get('code','?')} {item.get('name','?')} "
                           f"price={item.get('price','?')} chg={item.get('change_pct',0):+.2f}%")

        if cls_news:
            parts.append("\n## 财联社早间电报")
            for i, item in enumerate(cls_news[:10]):
                parts.append(f"{i+1}. {item.get('title','')}")

        if sector_flow:
            parts.append("\n## 行业板块资金流 TOP5")
            for item in sector_flow[:5]:
                parts.append(f"- {item}")

        if market_data:
            parts.append(f"\n## 市场宏观\n{compress_level3(market_data)}")

        return "\n".join(parts) if parts else "无数据"
```

- [ ] **Step 3: 创建 `technical_agent.py`**

```python
# tdx-mcp/llm/agents/technical_agent.py
"""技术 Agent — Python 算指标 → LLM 多周期综合解读"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level1, compress_level2, compress_time_series


class TechnicalAgent(BaseAgent):
    name = "technical"

    def build_context(self, main_pool_results: list = None,
                      sector_results: dict = None, **kwargs) -> str:
        parts = ["## 主力池单日快照 (22只)"]
        if main_pool_results:
            parts.append(compress_level1(main_pool_results, max_items=30))

        parts.append("\n## 板块聚合")
        if sector_results:
            parts.append(compress_level2(sector_results))

        return "\n".join(parts)

    def build_time_series_context(self, stock_series: list[dict]) -> str:
        """为每只候选构建时间序列上下文（仅用于技术Agent）"""
        lines = []
        for item in stock_series[:25]:
            lines.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(lines)
```

- [ ] **Step 4: 创建 `discovery_agent.py`**

```python
# tdx-mcp/llm/agents/discovery_agent.py
"""发现 Agent — Python 粗筛 → LLM 模式识别"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level1


class DiscoveryAgent(BaseAgent):
    name = "discovery"

    def build_context(self, scan_results: list = None,
                      sector_direction: list = None, **kwargs) -> str:
        parts = []
        if scan_results:
            parts.append("## 快速扫描 TOP30")
            parts.append(compress_level1(scan_results, max_items=30, fields=[
                "A1X", "a1x_dir", "box_pos", "vol_ratio", "DZT"
            ]))
        if sector_direction:
            parts.append(f"\n## 热点板块方向\n{', '.join(sector_direction)}")
        return "\n".join(parts) if parts else "无数据"
```

- [ ] **Step 5: 创建 `deployment_agent.py`**

```python
# tdx-mcp/llm/agents/deployment_agent.py
"""调度 Agent — Python 算仓位 → LLM 判断部署时机"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent


class DeploymentAgent(BaseAgent):
    name = "deployment"

    def build_context(self, qualified_top5: list = None, account: dict = None,
                      kelly_result: dict = None, extreme: dict = None, **kwargs) -> str:
        parts = []
        if qualified_top5:
            parts.append("## 技术 Agent 合格 TOP5")
            for i, q in enumerate(qualified_top5[:5]):
                parts.append(f"{i+1}. {q.get('symbol','?')} score={q.get('score',0)} "
                           f"A1X={q.get('A1X',0)}({q.get('a1x_dir','?')}) "
                           f"price={q.get('close',0)} box={q.get('box_pos',0)}%")

        if account:
            parts.append(f"\n## 账户状态\n"
                        f"总资产={account.get('total',0)} | "
                        f"可用={account.get('available',0)} | "
                        f"闲置天数={account.get('idle_days',0)}")

        if kelly_result:
            parts.append(f"\n## Kelly 仓位计算结果\n"
                        f"推荐仓位比例={kelly_result.get('fraction',0)}% | "
                        f"推荐手数={kelly_result.get('lots',0)}")

        if extreme and extreme.get("extreme"):
            parts.append(f"\n## ⚠️ 极端场景\n{extreme.get('reason','')} → {extreme.get('action','')}")

        return "\n".join(parts) if parts else "无数据"
```

- [ ] **Step 6: 验证四个 Agent 可以导入**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from llm.agents.intelligence_agent import IntelligenceAgent
from llm.agents.technical_agent import TechnicalAgent
from llm.agents.discovery_agent import DiscoveryAgent
from llm.agents.deployment_agent import DeploymentAgent

for cls in [IntelligenceAgent, TechnicalAgent, DiscoveryAgent, DeploymentAgent]:
    a = cls()
    print(f'{a.name}: prompt={len(a.system_prompt)} chars')

print('All 4 sub-agents OK')
"
```

- [ ] **Step 7: Commit**

```bash
git add tdx-mcp/llm/agents/
git commit -m "feat: add 4 sub-agents (intelligence, technical, discovery, deployment)"
```

---

### Task 7: 沛总 Agent

**Files:**
- Create: `tdx-mcp/llm/agents/chief_agent.py`

- [ ] **Step 1: 创建 `chief_agent.py`**

```python
# tdx-mcp/llm/agents/chief_agent.py
"""沛总 Agent — 交叉验证 + 最终裁决 + 复盘"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level2, compress_level3


class ChiefAgent(BaseAgent):
    name = "chief"

    def build_context(
        self,
        intel_output: dict = None,
        technical_output: dict = None,
        discovery_output: dict = None,
        deployment_output: dict = None,
        sector_results: dict = None,
        market_data: dict = None,
        **kwargs,
    ) -> str:
        parts = []

        if intel_output:
            parts.append("## 情报 Agent 输出")
            parts.append(f"高共识: {intel_output.get('high_consensus',[])}")
            parts.append(f"板块方向: {intel_output.get('sector_direction',[])}")
            parts.append(f"市场状态: {intel_output.get('market_state','?')}")
            parts.append(f"漏判: {intel_output.get('missed',[])}")

        if technical_output:
            parts.append("\n## 技术 Agent 输出")
            parts.append(f"合格: {len(technical_output.get('qualified',[]))} 只")
            parts.append(f"否决: {len(technical_output.get('vetoed',[]))} 只")
            for q in technical_output.get('qualified', [])[:5]:
                parts.append(f"  {q.get('symbol','?')} score={q.get('score',0)}")
            parts.append(f"板块洞察: {technical_output.get('sector_insight','')}")

        if discovery_output:
            parts.append("\n## 发现 Agent 输出")
            parts.append(f"新候选: {len(discovery_output.get('new_candidates',[]))} 只")
            parts.append(f"板块覆盖: {discovery_output.get('sector_coverage','')}")

        if deployment_output:
            parts.append("\n## 调度 Agent 输出")
            parts.append(f"动作: {deployment_output.get('action','?')}")
            parts.append(f"标的: {deployment_output.get('symbol','')}")
            parts.append(f"手数: {deployment_output.get('lots',0)}")
            parts.append(f"理由: {deployment_output.get('reason','')}")

        if sector_results:
            parts.append(f"\n## 板块全景\n{compress_level2(sector_results)}")

        if market_data:
            parts.append(f"\n## 市场三指标\n{compress_level3(market_data)}")

        return "\n".join(parts) if parts else "无数据"


class ReviewAgent(BaseAgent):
    """复盘 Agent — 交易完成后总结经验"""
    name = "review"

    def build_context(
        self,
        trade_record: dict = None,
        agent_decisions: dict = None,
        sector_performance: dict = None,
        **kwargs,
    ) -> str:
        parts = []
        if trade_record:
            parts.append("## 交易记录")
            parts.append(f"标的: {trade_record.get('symbol','?')}")
            parts.append(f"买入: {trade_record.get('entry_price',0)} | "
                        f"卖出: {trade_record.get('exit_price',0)} | "
                        f"持仓: {trade_record.get('hold_days',0)}天")
            parts.append(f"盈亏: {trade_record.get('pnl_pct',0):+.2f}%")

        if agent_decisions:
            parts.append("\n## 各 Agent 决策记录")
            for agent_name, decision in agent_decisions.items():
                parts.append(f"- {agent_name}: {json.dumps(decision, ensure_ascii=False)[:200]}")

        if sector_performance:
            parts.append(f"\n## 同期板块表现\n{compress_level2(sector_performance)}")

        return "\n".join(parts) if parts else "无数据"
```

- [ ] **Step 2: 验证沛总 Agent 导入**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from llm.agents.chief_agent import ChiefAgent, ReviewAgent

c = ChiefAgent()
print(f'ChiefAgent: prompt={len(c.system_prompt)} chars')
r = ReviewAgent()
print(f'ReviewAgent: prompt={len(r.system_prompt)} chars')
print('Chief + Review agents OK')
"
```

- [ ] **Step 3: 更新 `llm/agents/__init__.py` 导出**

Edit `tdx-mcp/llm/agents/__init__.py`, add:
```python
from .chief_agent import ChiefAgent, ReviewAgent
```

- [ ] **Step 4: Commit**

```bash
git add tdx-mcp/llm/agents/chief_agent.py tdx-mcp/llm/agents/__init__.py
git commit -m "feat: add ChiefAgent and ReviewAgent"
```

---

### Task 8: Orchestrator — 编排器

**Files:**
- Create: `tdx-mcp/orchestrator.py`

- [ ] **Step 1: 创建 `orchestrator.py`**

```python
#!/usr/bin/env python3
# tdx-mcp/orchestrator.py
"""
编排器 — 情报先行 → 三路并行 → 沛总汇总 → 记忆写入
"""
import sys, os, json, time
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir

# 导入 LLM Agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm.agents.intelligence_agent import IntelligenceAgent
from llm.agents.technical_agent import TechnicalAgent
from llm.agents.discovery_agent import DiscoveryAgent
from llm.agents.deployment_agent import DeploymentAgent
from llm.agents.chief_agent import ChiefAgent

# 导入现有计算层
from pipeline_runner import (
    _fetch_hot_rank_em, _fetch_cls_telegraph, _fetch_sector_flow,
    _fetch_sector_spot_em, _fetch_new_highs,
)
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from decision_engine import rank_all_sectors, discipline_check


def _collect_intelligence_data() -> dict:
    """收集情报 Agent 需要的原始数据"""
    hot = _fetch_hot_rank_em()
    news = _fetch_cls_telegraph()
    sector_flow = _fetch_sector_flow()
    return {"hot_rank": hot, "cls_news": news, "sector_flow": sector_flow}


def _collect_technical_data(intel_output: dict) -> dict:
    """收集技术 Agent 需要的数据: 22只主力池全量计算"""
    from rolling_capital import get_full_pool

    pool = get_full_pool()
    missed = intel_output.get("missed", [])
    candidates = list(dict.fromkeys(missed + pool))

    results = []
    sector_data = {}
    for sym in candidates[:30]:
        try:
            df = load_kline(sym, count=120)
            df = calc_all_indicators(df)
            s = get_summary(df, sym)
            sc = score_stock(df)
            results.append({
                "symbol": sym, "summary": s, "score": sc["score"],
                "details": sc["details"], "veto": sc.get("veto", False),
            })
        except Exception:
            pass

    # 板块聚合
    try:
        scan = rank_all_sectors()
        sector_data = {k: {"avg_score": v["avg_score"], "rankings": v["rankings"]}
                       for k, v in scan.items()}
    except Exception:
        pass

    return {"main_pool_results": results, "sector_results": sector_data}


def _collect_discovery_data(intel_output: dict) -> dict:
    """收集发现 Agent 需要的数据: 全市场粗筛"""
    try:
        from discovery_engine import coarse_filter, quick_scan
        from mootdx.quotes import StdQuotes
        client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)
        candidates = coarse_filter(client)
        discoveries = quick_scan(candidates, max_scan=200)
        return {
            "scan_results": discoveries,
            "sector_direction": intel_output.get("sector_direction", []),
        }
    except Exception as e:
        return {"scan_results": [], "error": str(e)}


def _collect_deployment_data(technical_output: dict) -> dict:
    """收集调度 Agent 需要的数据: 账户状态 + Kelly 计算"""
    from rolling_capital import detect_extreme, capital_status

    qualified = technical_output.get("qualified", [])
    cash = 7896  # fallback

    try:
        from trading_adapter import get_account
        acct = get_account()
        cash = acct.get("available", cash)
    except Exception:
        pass

    extreme = detect_extreme()
    idle_days = 0  # from capital_status

    # Kelly 仓位计算 (数学公式, 不经过 LLM)
    top = qualified[0] if qualified else None
    kelly = {"fraction": 0, "lots": 0}
    if top:
        price = top.get("close", 0)
        score = top.get("score", 0)
        if price > 0 and score >= 6:
            kelly_frac = min(0.10 + (score - 6) * 0.05, 0.25)
            lots = min(int(cash * kelly_frac / (price * 100)), 4)
            kelly = {"fraction": round(kelly_frac * 100, 1), "lots": max(lots, 1)}

    return {
        "qualified_top5": qualified[:5],
        "account": {"available": cash, "idle_days": idle_days},
        "kelly_result": kelly,
        "extreme": extreme,
    }


def run_orchestrator(use_llm: bool = True) -> dict:
    """
    一键运行完整 Pipeline。
    use_llm=False 时跳过 LLM 调用，只输出 Python 计算结果（影子模式对照）。
    """
    print("=" * 60)
    print(f"  Orchestrator — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  LLM: {'ON' if use_llm else 'OFF (shadow mode)'}")
    print("=" * 60)

    # ── Step 1: 情报 Agent ──
    print("\n[1/3] 情报 Agent...")
    t0 = time.time()
    intel_data = _collect_intelligence_data()
    if use_llm:
        intel_agent = IntelligenceAgent()
        intel_output = intel_agent.run(**intel_data)
    else:
        intel_output = {
            "high_consensus": [h.get("code","") for h in intel_data.get("hot_rank", [])[:10]],
            "sector_direction": intel_data.get("sector_flow", [])[:3],
            "missed": [],
            "market_state": "震荡",
        }
    print(f"  → {len(intel_output.get('high_consensus',[]))} 共识标的 ({time.time()-t0:.1f}s)")

    # ── Step 2: 三路并行 ──
    print("\n[2/3] 技术 + 发现 + 调度 (并行)...")
    t0 = time.time()

    # 先收集所有 Python 数据（主线程，避免 mootdx 连接冲突）
    tech_data = _collect_technical_data(intel_output)
    disc_data = _collect_discovery_data(intel_output)
    depl_data = _collect_deployment_data({"qualified": [
        r for r in tech_data["main_pool_results"]
        if not r.get("veto") and r.get("score", 0) >= 5
    ]})

    results = {}
    if use_llm:
        agents_map = {
            "technical": (TechnicalAgent(), tech_data),
            "discovery": (DiscoveryAgent(), disc_data),
            "deployment": (DeploymentAgent(), depl_data),
        }
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}
            for name, (agent, data) in agents_map.items():
                futures[pool.submit(agent.run, **data)] = name
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result(timeout=30)
                except Exception as e:
                    results[name] = {"error": str(e), "fallback": True}
    else:
        results = {
            "technical": {"qualified": tech_data["main_pool_results"][:5], "vetoed": [], "sector_insight": "shadow"},
            "discovery": {"new_candidates": disc_data.get("scan_results", [])[:5], "sector_coverage": "shadow"},
            "deployment": depl_data,
        }
    print(f"  → 完成 ({time.time()-t0:.1f}s)")

    # ── Step 3: 沛总 Agent ──
    print("\n[3/3] 沛总 Agent...")
    t0 = time.time()
    sector_scan = {}
    try:
        sector_scan = rank_all_sectors()
    except Exception:
        pass

    market_data = {"limit_down_count": 0, "up_count": 0, "market_style": "未知", "sh_index_pct": 0}

    if use_llm:
        chief = ChiefAgent()
        final = chief.run(
            intel_output=intel_output,
            technical_output=results.get("technical", {}),
            discovery_output=results.get("discovery", {}),
            deployment_output=results.get("deployment", {}),
            sector_results=sector_scan,
            market_data=market_data,
        )
    else:
        final = {
            "final_action": "APPROVE",
            "approved_deployment": results.get("deployment", {}),
            "conflicts_found": [],
            "daily_review_preview": "shadow mode — 无 LLM 复盘",
            "memory_note": "",
        }
    print(f"  → 最终裁决: {final.get('final_action','?')} ({time.time()-t0:.1f}s)")

    # ── 保存结果 ──
    today = date.today().isoformat()
    output_dir = ensure_dir("tdx-mcp", "shadows" if not use_llm else "agents", "output")
    output_file = os.path.join(output_dir, f"pipeline_{today}.json")
    full_output = {
        "timestamp": str(datetime.now()),
        "use_llm": use_llm,
        "intelligence": intel_output,
        **results,
        "chief_decision": final,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)
    print(f"\n  → 保存至 {output_file}")

    return full_output


if __name__ == "__main__":
    # 默认影子模式运行（不调 LLM，安全）
    run_orchestrator(use_llm=False)
```

- [ ] **Step 2: 验证 orchestrator 影子模式运行（不调 LLM）**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')
from orchestrator import run_orchestrator
result = run_orchestrator(use_llm=False)
print()
print('Orchestrator shadow mode: OK')
print('Keys:', list(result.keys()))
"
```

- [ ] **Step 3: Commit**

```bash
git add tdx-mcp/orchestrator.py
git commit -m "feat: add orchestrator (intel → parallel → chief → save)"
```

---

### Task 9: 集成验证 — 完整端到端测试

**Files:**
- None new (验证现有文件)

- [ ] **Step 1: 设置测试环境变量（不设真实 key，验证降级）**

```bash
cd D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System && DEEPSEEK_API_KEY=sk-test .venv/Scripts/python.exe -c "
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, 'tdx-mcp')

# 1. 验证 LLM 模块完整导入
from llm import chat, BaseAgent
from llm.agents import (
    IntelligenceAgent, TechnicalAgent,
    DiscoveryAgent, DeploymentAgent,
)
from llm.agents.chief_agent import ChiefAgent, ReviewAgent
from llm.context_compressor import (
    compress_level1, compress_level2, compress_level3,
    compress_time_series,
)
from memory import save_review, update_index, retrieve_for_agent
print('[PASS] All imports OK')

# 2. 验证所有 Agent 可实例化
agents = [
    IntelligenceAgent(), TechnicalAgent(),
    DiscoveryAgent(), DeploymentAgent(),
    ChiefAgent(), ReviewAgent(),
]
for a in agents:
    assert len(a.system_prompt) > 0, f'{a.name} has empty prompt'
print('[PASS] All 6 agents instantiated with prompts')

# 3. 验证 context compressor
test_stock = [{
    'symbol': '600863', 'summary': {
        'close': 5.93, 'DKX': 5.50, 'dkx_dir': '↑',
        'A1X': 4.22, 'a1x_dir': '↑', 'box_pos': 98.0,
        'vol_ratio': 1.07, 'DZT': False, 'ZZJC': False,
    }, 'score': 3, 'veto': False,
}]
l1 = compress_level1(test_stock)
assert '600863' in l1
print('[PASS] Context compressor L1 OK')

# 4. 验证 orchestrator 影子模式
from orchestrator import run_orchestrator
result = run_orchestrator(use_llm=False)
assert 'chief_decision' in result
print('[PASS] Orchestrator shadow mode OK')
print()
print('All integration checks passed.')
"
```

- [ ] **Step 2: 确认 shadows 目录已创建并写入了文件**

```bash
ls D:/Agentic-Quant-Trading-System/Agentic-Quant-Trading-System/tdx-mcp/shadows/
```

- [ ] **Step 3: 清理测试文件并 Commit**

```bash
git add tdx-mcp/shadows/.gitkeep
git commit -m "test: integration check — all modules import, shadow mode runs"
```

---

## 实现顺序总结

```
Task 1: client.py           ← 基础依赖
Task 2: context_compressor   ← 基础依赖
Task 3: memory module        ← 基础依赖
Task 4: agent_base.py        ← 依赖 Task 1+2+3
Task 5: prompts/*.md         ← 独立（纯文本）
Task 6: 4 sub-agents         ← 依赖 Task 4+5
Task 7: chief_agent.py       ← 依赖 Task 4+5
Task 8: orchestrator.py      ← 依赖 Task 6+7
Task 9: 集成验证             ← 依赖全部
```
