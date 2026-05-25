# LLM Agent 模块架构设计

> 日期: 2026-05-25 | 状态: 待审批

## 一、目标

在量化系统中集成 LLM 调用能力, 将当前"纯 Python 函数计算"的 Pipeline 升级为"Python 计算 + LLM 推理"的增强模式。新增独立的沛总(Chief) Agent 做最终裁决, 并将 Meta-Evolution 改造为记忆机制。

---

## 二、架构总览

```
Claude Code (外部 MCP 交互)
       │
┌──────▼─────────────────────────────────┐
│  沛总 Agent (Chief)                     │  ← 🆕 LLM
│  交叉验证 → 冲突裁决 → 最终判断 → 复盘    │
└──────┬─────────────────────────────────┘
       │
┌──────▼─────────────────────────────────┐
│  LLM-Enhanced Pipeline Agents           │  ← 🆕 LLM
│  情报 → 技术 → 发现 → 调度                │
│  每个 Agent = Python计算 + LLM推理        │
└──────┬─────────────────────────────────┘
       │
┌──────▼─────────────────────────────────┐
│  LLM Client (llm/)                      │  ← 🆕
│  OpenAI SDK → DeepSeek API              │
└──────┬─────────────────────────────────┘
       │
┌──────▼─────────────────────────────────┐
│  现有 Python 工具层 (不动)               │
│  indicator_engine / data_adapter /      │
│  decision_engine / backtest_engine ...  │
└────────────────────────────────────────┘
```

### 新增目录结构

```
tdx-mcp/
  llm/                              ← 🆕
    __init__.py
    client.py                       ← 统一 LLM 客户端
    agent_base.py                   ← Agent 基类
    agents/
      intelligence_agent.py
      technical_agent.py
      discovery_agent.py
      deployment_agent.py
      chief_agent.py
    prompts/
      intelligence.md               ← System prompt 模板
      technical.md
      discovery.md
      deployment.md
      chief.md
      review.md                     ← 复盘 prompt
  memory/                           ← 🆕 替代 meta-evolution
    MEMORY.md                       ← 记忆索引
    reviews/                        ← 每笔交易复盘
      YYYY-MM-DD_{symbol}_review.md
  orchestrator.py                   ← 🆕 编排器
```

---

## 三、关键决策

| # | 决策 | 结论 |
|:---:|------|------|
| 1 | 多 Agent | 4 子 Agent + 1 沛总 Agent |
| 2 | API 格式 | OpenAI SDK → DeepSeek (`base_url=https://api.deepseek.com`) |
| 3 | 工具调用 | 混合模式: Python 预计算注入 prompt + 少量查询 tool |
| 4 | 评测方式 | 影子模式: LLM 决策记录日志, 30 天后与实盘/规则版统计对比 |
| 5 | 并行策略 | 情报先行(单线程) → 技术/发现/调度三路并行(ThreadPoolExecutor) |
| 6 | 记忆机制 | 共享 MEMORY.md 索引 + reviews/ 子目录, 每轮交易后复盘写入 |
| 7 | 上下文压缩 | 分层压缩: 每 Agent 按职责获取不同颗粒度数据, 预算 ≤2000 tok/Agent |

---

## 四、编排流程

```
08:55  程序启动
09:00  情报 Agent (单线程, ~8s)
         ├ Python: AKShare 热榜 + 电报 + 板块资金流
         └ LLM: 多源交叉验证, 识别共识标的 + 板块方向
09:05  三路并行 (ThreadPoolExecutor, ~15s)
         ├ Thread 1: 技术 Agent (~12s)
         │   ├ Python: 22只主力池 calc_all + score_stock
         │   └ LLM: 多周期交叉验证, 输出 qualified + vetoed
         ├ Thread 2: 发现 Agent (~15s)
         │   ├ Python: coarse_filter + quick_scan(300只)
         │   └ LLM: 识别符合热点方向的新标的
         └ Thread 3: 调度 Agent (~4s)
             ├ Python: Kelly仓位计算 + 极端场景检测
             └ LLM: 市场状态下是否暂缓部署
09:20  沛总 Agent (~10s)
         ├ 汇总 4 份子 Agent 输出
         ├ 交叉验证找矛盾
         ├ 检索记忆库相关历史教训
         └ 最终裁决: 同意/否决/要求重跑
09:25  输出 final_decision.json
09:30-15:00  心跳监控 (纯 Python, 不经过 LLM)
15:05  复盘 Hook → 沛总写 memory/reviews/
```

### 并发实现

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_pipeline():
    # Step 1: 情报先行
    intel = IntelligenceAgent().run()

    # Step 2: 三路并行
    agents = {
        "technical": TechnicalAgent(),
        "discovery": DiscoveryAgent(),
        "deployment": DeploymentAgent(),
    }
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(a.run, intel_output=intel): n
                   for n, a in agents.items()}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    # Step 3: 沛总汇总
    final = ChiefAgent().run(intel=intel, **results)

    # Step 4: 记忆异步写入
    pool.submit(write_memory, final)

    return final
```

---

## 五、LLM Client

```python
# llm/client.py
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def chat(messages, model="deepseek-chat", json_mode=False):
    kwargs = dict(model=model, messages=messages)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return client.chat.completions.create(**kwargs)
```

### Agent 基类

```python
class BaseAgent:
    name: str
    system_prompt: str          # 从 prompts/{name}.md 加载
    model: str = "deepseek-chat"
    json_mode: bool = True      # 强制输出结构化 JSON

    def build_context(self, **kwargs) -> str:
        """子类实现: 注入 Python 计算结果"""
        raise NotImplementedError

    def run(self, **kwargs) -> dict:
        context = self.build_context(**kwargs)
        memory_context = retrieve_memory(self.name, context)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": memory_context},
            {"role": "user", "content": context},
        ]
        response = chat(messages, self.model, json_mode=self.json_mode)
        return json.loads(response.choices[0].message.content)
```

---

## 六、各 Agent 职责与数据剖面

### 情报 Agent (关键度: 中)

| 输入 | 输出 |
|------|------|
| AKShare 热榜 TOP30 (代码+涨跌幅) | high_consensus[] |
| 财联社电报标题 ≤10 条 | sector_direction[] |
| 行业板块资金流 TOP5 | missed[] (系统池未覆盖的热门标的) |
| 记忆: 同板块历史教训 | market_state |

上下文预算: ~300 tok (数据) + ~200 tok (记忆) + ~500 tok (system) = **~1K tok**

### 技术 Agent (关键度: 最高 🔴)

| 输入 | 输出 |
|------|------|
| 22 只主力池 + 情报missed标的 | qualified[] (评分≥5) |
| **每只**: 单日快照(10字段) + **3日A1X序列**[值×3] + **5日DKX序列**[值×5] + **5日量比序列**[值×5] + 周线方向 + STRONG/WEAK/FAKE标记 + 评分明细文本 | vetoed[] (DKX否决) |
| 发现池TOP10: 单日快照 | 多周期综合解读 |
| 记忆: 同板块/相似评分历史教训 | 板块趋势判断 |

上下文预算: ~1500 tok (数据, 22只×40字段) + ~300 tok (记忆) + ~500 tok (system) = **~2.3K tok**

**此 Agent 是唯一需要"时间序列"数据的 Agent。**

### 发现 Agent (关键度: 中低)

| 输入 | 输出 |
|------|------|
| coarse_filter 候选列表 | new_candidates[] |
| quick_scan TOP30 (A1X+箱体+量比+dzt) | 入库建议 |
| 情报 sector_direction | |
| 记忆: 板块覆盖度历史 | |

上下文预算: ~400 tok + ~200 tok + ~400 tok = **~1K tok**

### 调度 Agent (关键度: 高 🔴)

| 输入 | 输出 |
|------|------|
| 技术Agent qualified TOP5 (score/A1X/price/box) | deploy方案 |
| 账户资金 (或模拟余额) + 闲置天数 | 资金分配建议 |
| Kelly 仓位计算结果 (Python算好, 不交给 LLM) | HOLD_CASH 触发条件 |
| 极端场景检测结果 | |
| 记忆: 同类仓位历史教训 | |

上下文预算: ~200 tok + ~200 tok + ~400 tok = **~0.8K tok**

**绝对不能看到技术 Agent 的否决名单。**

### 沛总 Agent (关键度: 最高 🔴)

| 输入 | 输出 |
|------|------|
| 全部子Agent输出摘要 | final_decision |
| 板块趋势(决策引擎) | 交叉验证结论 |
| 市场三指标: 跌停数/红盘数/风格 | 矛盾裁决 |
| 上证指数涨跌 | 自然语言复盘预览 |
| 记忆检索: 同类历史教训 ≤7条 (同板块×3 + 同评分×2 + 同市场状态×2) | |

上下文预算: ~600 tok + ~400 tok + ~800 tok = **~1.8K tok**

---

## 七、上下文压缩方案

```
Python 全量计算 (~60,000 数据点)
        │
        ├── L1 摘要 (每只 10 字段 × 95 只) → ~800 tok
        ├── L2 板块聚合 (6 板块 × 6 字段) → ~200 tok
        └── L3 市场宏观 (3 指标 + 上证) → ~100 tok

情报 Agent ← L3 + L1(热榜TOP10) + 新闻标题
技术 Agent ← L1(22只全量+序列) + L2
发现 Agent ← L1(发现池TOP30) + L2(热点方向)
调度 Agent ← L1(评分≥5) + 账户状态
沛总 Agent ← L1(TOP5) + L2(全板块) + L3 + 记忆
```

---

## 八、记忆机制

### 文件结构

```
memory/
  MEMORY.md              ← 索引文件，每行一条指到具体 review 文件
  reviews/
    2026-05-26_600863_review.md
    2026-05-28_000070_review.md
    ...
```

### 写入流程

```
每轮交易完成(买入→持有→卖出) → 复盘 Hook 触发:
  1. 沛总 Agent 读入本轮全部决策记录 + 实际结果
  2. LLM 回答三个问题:
     a. 这笔交易做对了什么？
     b. 做错了什么？
     c. 下次遇到类似情况该怎么做？
  3. 写入 memory/reviews/{date}_{symbol}_review.md
  4. 更新 memory/MEMORY.md 索引
```

### 检索策略

```python
def retrieve_memory(agent_name: str, context: dict) -> str:
    """返回格式化的记忆文本 (≤400 tok)"""
    results = []
    # 同一板块历史教训 (最多 3 条)
    results += search(sector=context["sector"], limit=3)
    # 相似评分区间 (最多 2 条)
    results += search(score_range=context["score_band"], limit=2)
    # 相同市场状态 (最多 2 条)
    results += search(market_state=context["market_state"], limit=2)
    return format_as_text(results)
```

### 与 Meta-Evolution 的关系

旧的 `meta-evolution/` 目录 **废弃**，被 memory/ 机制替代:

| | 旧 | 新 |
|------|------|------|
| 触发 | 心跳扫描日志 | 每轮交易完成后 |
| 写入 | 抽象进化提案 (TBD) | 具体经验教训 + LLM 撰写 |
| 使用 | 等人工审批 | 自动检索注入 prompt |
| 文件 | meta-evolution/storage/*.json | memory/reviews/*.md |

---

## 九、评测机制 (影子模式)

```
纯规则版 (现有 decision_engine)          LLM 增强版 (新 Agent 模块)
─────────────────────────────          ────────────────────────────
         │                                        │
         ▼                                        ▼
   每日输出评分+建议                         每日输出评分+建议+推理
         │                                        │
         └──────────────┬─────────────────────────┘
                        ▼
              ┌──────────────────┐
              │  shadows/ 目录    │
              │  两份决策并存     │
              │  不做实盘执行     │
              └──────────────────┘
                        │
              ┌─────────▼─────────┐
              │  30 天后统计对比   │
              │  - 推荐命中率      │
              │  - 推荐标的后续表现 │
              │  - LLM是否过度自信  │
              │  - LLM是否过度保守  │
              └───────────────────┘
```

LLM 增强版必须满足:
- 胜率 ≥ 规则版
- 不会推荐规则版否决的标的 (安全闸)
- 不会比规则版更频繁地发出"买入"信号 (不能过于激进)

---

## 十、运行模式

### 推荐: 常驻进程 (一次启动, 全天自动)

```
08:50  手动启动程序
09:00  自动跑 Pipeline → 输出决策
随后   心跳模式, 盘中无事不弹窗
15:05  自动复盘 → 写 memory/
       输出"今日复盘完成"
```

### 成本估算

每天 6 次 LLM 调用, 合计 ~11.5K tokens → DeepSeek ~¥0.01/天

---

## 十一、风险与边界

| 红线 | 说明 |
|------|------|
| **LLM 不能修改评分** | score_stock() 结果不可被 LLM 覆盖, LLM 只能在此之上做解读 |
| **LLM 不能触发下单** | 只输出建议, 不调用 trading_adapter |
| **LLM 不能看到否决名单** | 调度 Agent 和沛总在交叉验证时不能看到被 DKX 否决的标的 |
| **LLM API 挂掉不能阻塞 Pipeline** | 每个 Agent 有 LLM 调用超时 (15s) 和降级策略 (返回规则版结果) |
| **API Key 不入库** | 通过环境变量 `DEEPSEEK_API_KEY` 传入, 不写进任何文件 |
