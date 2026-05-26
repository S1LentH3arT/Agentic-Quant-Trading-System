# 量化交易系统重构设计

**日期**: 2026-05-26
**状态**: 已确认
**目标**: 研究+交易一体化（B模型），LLM研究 + 系统执行，架构清晰分层

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────┐
│              Agent 研究区（LLM 隔离）                     │
│  QuantResearchAgent: 原始数据 → 结构化量化特征            │
│  · 不写报告、不做评价、不交易                              │
│  · 输出全部是向量/标量/枚举，可直接计算                     │
├─────────────────────────────────────────────────────────┤
│                  〓 系统校验层 〓                          │
│  防幻觉(代码真伪) / 范围检查 / 因子安全 / 订单终审        │
├─────────────────────────────────────────────────────────┤
│  数据层  │ AKShare 统一适配 → DataBus 缓存               │
│  因子层  │ 因子引擎 + 注册表 + 校验器                     │
│  策略层  │ 评分引擎 + 信号生成 + 品种池 + 发现引擎        │
│  风控层  │ 五道关卡（极端/纪律/仓位/复核/集中度）          │
│  执行层  │ Broker抽象 → easytrader → 弹窗确认             │
│  回测引擎│ 完整回测(同实盘) + 轻量回测(Agent实验)          │
├─────────────────────────────────────────────────────────┤
│  元进化   │ param_loader + governor 审计骨架（保留）       │
│  持久化   │ SQLite交易日志 + 状态文件                      │
└─────────────────────────────────────────────────────────┘
```

## 二、核心设计原则

1. **LLM只研究，系统只执行** — LLM不出现在交易关键路径上
2. **回测与实盘同引擎** — strategy → risk → execution 同一套代码路径，仅 Broker 不同
3. **Agent输出必须可验证** — 所有产出流经校验层，数值有范围，代码需存在验证
4. **安全私密不降级** — 6条宪法 + 弹窗确认 + easytrader同花顺全链路不出本机

---

## 三、选股闭环：8 层体系

只做主板+创业板实体个股，剔除科创板+ETF+ST。

```
L1 宏观产业定性 → L2 主流资金追踪 → L3 财报内核深挖 → L4 筹码结构透析
       ↓                    ↓                ↓              ↓
  政策底行业          北向+机构+大单    扣非/毛利/现金流  股本/股东/解禁
  AI研报解析          底部吸筹判定      PE分位锚定       机构占比

L5 流动性与供需 → L6 技术趋势拐点 → L7 风控排雷 → L8 价值分类
       ↓              ↓            ↓           ↓
  日均成交/换手    月线→周线→日线   硬性剔除     价值趋势/拐点反转/低位潜伏
  供需拐点        多周期共振       7类雷区
```

### 目录结构

```
quant_system/                        # 新根目录（放弃 tdx-mcp/）
├── config.py                        # 全局配置 + 路径管理
├── params.json                      # 可调参数注册表
│
├── data/
│   ├── provider.py                  # AKShare 统一适配器
│   ├── bus.py                       # 数据总线（缓存+去重）
│   └── sources.py                   # 数据源定义（K线/北向/机构/财报/股东/解禁/研报/行业）
│
├── factors/
│   ├── engine.py                    # 因子计算引擎
│   ├── registry.py                  # 因子注册表（管理名称/公式/参数/有效期）
│   ├── validator.py                 # 因子校验（公式安全/参数/IC）
│   └── definitions/
│       ├── industry.py              # L1 产业宏观：政策底/景气度/行业周期
│       ├── capital_flow.py          # L2 资金追踪：北向/机构/主力大单
│       ├── fundamentals.py          # L3 财报内核：扣非/毛利/现金流/商誉/质押/PE分位
│       ├── chip_structure.py        # L4 筹码结构：股本/股东人数/机构占比/解禁
│       ├── liquidity.py             # L5 流动性：日均成交额/换手率/供需关系
│       ├── technical.py             # L6 技术趋势：DKX/A1X/箱体/均线/量价/多周期
│       ├── risk_filter.py           # L7 风控排雷：硬性剔除规则（科创板/ETF/ST/亏损/造假/减持/质押/商誉）
│       └── custom.py                # Agent 构造的因子（校验后写入）
│
├── strategy/
│   ├── scorer.py                    # 评分引擎（L1-L7 加权综合）
│   ├── classifier.py               # L8 价值分类：价值趋势/拐点反转/低位潜伏
│   ├── pool.py                      # 品种池（分类管理 + 发现池 + 黑名单）
│   ├── signals.py                   # 信号生成（买入/卖出/减仓）
│   ├── discovery.py                 # 全市场发现引擎（8层筛选流水线）
│   └── sector.py                    # 板块分析（产业景气+赛道方向）
│
├── risk/
│   ├── manager.py                   # 风控总入口（五道关卡 + L7 排雷前置）
│   ├── position.py                  # 仓位计算（Kelly + 市场调节 + 集中度 + 标的分类加权）
│   ├── stops.py                     # 止损管理（硬/ATR/跟踪/时间 四维）
│   └── extreme.py                   # 极端场景检测（5种停机+Agent风险叠加）
│
├── execution/
│   ├── broker.py                    # Broker抽象 + THSBroker(easytrader实现)
│   ├── orders.py                    # 订单生命周期管理
│   └── confirm.py                   # Windows MessageBox 弹窗确认
│
├── backtest/
│   ├── engine.py                    # 完整回测（与策略/风控/执行同路径）
│   ├── light.py                     # 轻量回测（Agent快速实验）
│   └── metrics.py                   # 7+维度绩效指标
│
├── agents/
│   ├── base.py                      # ResearchAgent 基类
│   └── researcher.py                # QuantResearchAgent: 研报/政策/资金/财报 → 量化特征
│
├── validation/
│   ├── guard.py                     # 校验入口（四子模块统一调用）
│   ├── factor_check.py              # 因子合法性校验（安全编译+样本测试）
│   ├── signal_check.py              # 信号合理性校验
│   ├── pool_check.py                # 品种池防幻觉（AKShare全A股存在性验证）
│   └── order_check.py              # 订单终审（资金/手数/价格）
│
├── evolution/
│   ├── governor.py                  # 治理审计链（保留骨架）
│   └── param_loader.py              # 参数管理（保留，因子引擎基础依赖）
│
└── storage/
    ├── journal.py                   # SQLite交易日志（3表：orders/daily_snapshot/position_history）
    └── state.py                     # 状态文件（品种池/扫描结果/信号历史）
```

## 四、层间数据流

```
AKShare
  │
  ├── 行情数据: K线/分时/板块/热榜
  ├── 资金数据: 北向流向/机构持仓/大宗交易
  ├── 财报数据: 扣非净利润/毛利率/经营现金流/商誉/质押/PE-PB
  ├── 筹码数据: 股东人数/十大流通股东/解禁计划
  └── 研报数据: 行业研报/公司研报/宏观政策
       │
       ▼
data/provider ──→ data/bus
  │
  ├──→ agents/researcher ──→ 研报→产业拐点/订单爆发/产品提价
  │                          财报→虚增判定/现金流质量/估值水位
  │                          资金→北向趋势/机构建仓/主力意图
  │                          政策→扶持行业/打压行业/景气度方向
  │                              │
  │                              ▼ struct量化特征
  │                        validation/guard ──→ 防幻觉校验
  │                              │
  │                              ▼
  │                    strategy/scorer ←── L1产业/ L2资金 / L3财报 / L4筹码 Agent特征
  │
  └──→ factors/engine
           │
           ├── L1 产业因子: 政策底得分 / 行业景气度 / AI研报信号
           ├── L2 资金因子: 北向连续加仓 / 机构持仓变化 / 主力大单方向
           ├── L3 财报因子: 扣非增长 / 毛利趋势 / 现金流质量 / 商誉质押 / PE分位
           ├── L4 筹码因子: 股本适中 / 股东递减 / 机构占比 / 解禁压力
           ├── L5 流动性因子: 日均成交额 / 换手率区间 / 供需拐点 / 独立抗跌
           ├── L6 技术因子: DKX / A1X / 箱体 / 均线 / 量价 / 月周日趋共振
           └── L7 排雷因子: 科创板 / ETF / ST / 亏损 / 造假 / 减持 / 质押 / 商誉 / 高位
                  │
                  ▼ 各层因子值
           strategy/scorer ──→ 8层加权综合评分
                  │
                  ▼
           strategy/classifier ──→ 价值趋势股 / 拐点反转股 / 低位潜伏股
                  │
                  ▼
           strategy/signals ──→ 按分类差异化信号阈值
                  │
                  ▼
           risk/manager ──→ 五道关卡 + L7排雷前置
                  │
                  ▼
           execution/confirm → broker → journal

═══════════ 回测路径 ═══════════
strategy → risk → SimulatedBroker → metrics
(同实盘代码，仅 Broker 替换为模拟撮合 + 滑点0.1% + 手续费0.03%)
```

## 五、迁移映射

### 保留并迁移

| 旧文件 | 新位置 | 处理方式 |
|---|---|---|
| `tdx-mcp/indicator_engine.py` | `factors/engine.py` + `factors/definitions/*.py` | 核心算法迁移，因子定义拆分为独立文件 |
| `tdx-mcp/decision_engine.py` | `strategy/scorer.py` + `strategy/pool.py` | 评分 + 板块逻辑分离 |
| `tdx-mcp/rolling_capital.py` | `risk/manager.py` + `risk/extreme.py` | 风控独立 |
| `tdx-mcp/trading_adapter.py` | `execution/broker.py` + `execution/orders.py` | 连接/指令/执行三层分离 |
| `tdx-mcp/backtest_engine.py` | `backtest/engine.py` + `backtest/metrics.py` | 回测+指标分离 |
| `tdx-mcp/data_adapter.py` | `data/provider.py` | 移除TDX，仅保留AKShare |
| `tdx-mcp/discovery_engine.py` | `strategy/discovery.py` | 核心扫描逻辑保留 |
| `tdx-mcp/sector_sniper.py` | `strategy/sector.py` | 板块挖掘保留 |
| `tdx-mcp/trade_journal.py` | `storage/journal.py` | 原样迁移 |
| `tdx-mcp/param_loader.py` | `evolution/param_loader.py` | 原样迁移 |
| `tdx-mcp/heartbeat.py` | `risk/manager.py` 内部 | 心跳风控合并 |
| `meta-evolution/core/governor.py` | `evolution/governor.py` | 保留审计骨架 |
| `config.py` | `quant_system/config.py` | 路径定义迁移 |

### 移除

`orchestrator.py`, `scheduler.py`, `review_hook.py`, `llm/agents/`(6个旧Agent), `llm/agent_base.py`, `llm/client.py`, `llm/context_compressor.py`, `server.py`, `notify.py`, `consensus_engine.py`, `price_monitor.py`, `chart_renderer.py`, `pipeline_runner.py`, `meta-evolution/core/observer.py`, `meta-evolution/core/analyst.py`, `meta-evolution/core/deriver.py`, `meta-evolution/meta_evolution_manager.py`, `quant_system/engine/analyzer.py`, `SYNC_LOOP.md`, `DEPLOY_FEISHU.md`

### 不碰

`quant_desk.py` (Streamlit仪表盘), `sync_market_data.py` (后续对接新数据层), `tdx-mcp/connection.py` (被 execution/broker 直接引用)

## 六、因子定义规范

### 因子分类（8层）

所有因子统一用 `FactorDefinition` 注册，按层级分类：

```python
@dataclass
class FactorDefinition:
    name: str              # 因子名
    layer: int             # 1-7 对应选股体系层级（L8是分类，不含因子）
    category: str          # industry / capital_flow / fundamentals / chip / liquidity / technical / risk_filter
    version: int
    author: str            # "system" 或 "agent"
    params: dict           # {name: {value, range[min,max], desc}}
    compute_fn: str        # Python lambda 表达式字符串
    requires: list[str]    # 需要的输入列
    output_columns: list[str]
    weight: float          # 在综合评分中的权重（每层内权重和=1）
    hypothesis: str = ""
```

### 各层因子清单

**L1 产业宏观** (权重 15%)
| 因子 | 数据源 | 说明 |
|---|---|---|
| policy_support | Agent解析政策/研报 | 扶持行业=+1, 中性=0, 打压=-1 |
| industry_prosperity | AKShare行业数据 | 营收增速+库存周期+供需缺口综合 |
| research_signal | Agent解析研报 | 产业拐点/产能扩张/订单爆发/产品提价 → [0,1] |
| sector_direction | AKShare板块流向 | 板块资金净流入方向 |

**L2 资金追踪** (权重 18%)
| 因子 | 数据源 | 说明 |
|---|---|---|
| north_bound_duration | AKShare北向资金 | 连续加仓天数/15-30日累计净买 |
| institution_position | AKShare机构持仓 | 新进重仓+持仓比例抬升 |
| main_force_pattern | 分时量价计算 | 阴线吸筹+阳线拉升, 下跌缩量+上涨放量 |
| capital_phase | Agent资金判定 | 底部吸筹/中途加仓/高位接力/出货/僵尸 |

**L3 财报内核** (权重 18%)
| 因子 | 数据源 | 说明 |
|---|---|---|
| deducted_np_growth | AKShare财报 | 扣非净利润持续增长/季度环比加速 |
| gross_margin_trend | AKShare财报 | 毛利率稳定上行 |
| operating_cf_quality | AKShare财报 | 经营现金流>0, 与利润匹配 |
| goodwill_pledge_risk | AKShare财报 | 商誉/总资产低, 质押率低 |
| pe_pb_percentile | AKShare估值 | PE/PB近5年分位<20% |

**L4 筹码结构** (权重 12%)
| 因子 | 数据源 | 说明 |
|---|---|---|
| share_capital_fit | AKShare股本 | 避开超大+超小盘 |
| holder_decline | AKShare股东 | 连续4季股东递减 |
| institutional_ratio | AKShare十大流通 | 机构为主, 非散户扎堆 |
| lockup_pressure | AKShare解禁 | 无近期待解禁/无减持计划 |

**L5 流动性** (权重 10%)
| 因子 | 数据源 | 说明 |
|---|---|---|
| avg_turnover_stable | K线计算 | 日均成交额稳定 |
| turnover_healthy | K线计算 | 换手率适中 |
| supply_demand_inflection | 量价分析 | 卖压衰竭+买盘递增 |
| independent_strength | 对比大盘 | 独立抗跌属性 |

**L6 技术趋势** (权重 17%)
| 因子 | 数据源 | 说明 |
|---|---|---|
| dkx_smx | K线计算 | DKX多空线+SMX |
| a1x_dzt_zzjc | K线计算 | 资金动量+金叉死叉 |
| box_position | K线计算 | 箱体位置+突破确认 |
| ma_alignment | K线计算 | 站上60/120日均线, 均线走平拐头 |
| volume_price_healthy | K线计算 | 回调缩量+企稳放量 |
| multi_period_resonance | 多周期计算 | 月线打底→周线反转→日线买点 |

**L7 风控排雷** (权重 10% — 单项否决，不计分)
| 规则 | 来源 | 说明 |
|---|---|---|
| board_exclude | 系统规则 | 剔除科创板(688开头)+ETF+ST/*ST |
| loss_exclude | 财报 | 业绩亏损/扣非为负 |
| fraud_exclude | Agent+公开数据 | 财报造假/立案调查/诉讼 |
| bubble_exclude | 技术 | 高位翻倍/纯概念无业绩 |
| insider_risk_exclude | 公告 | 频繁减持/高比例质押/商誉暴雷 |
| chaos_exclude | Agent判定 | 主营杂乱/频繁跨界蹭热点 |

## 七、Agent 设计

### QuantResearchAgent — 非结构化数据 → 结构化量化特征

Agent 不做交易决策，不产报告文本。只做一件事：把 AI 语言能力用于解析非结构化数据，输出可直接计算的数值。

**输入源**:
- 行业研报/公司研报（AI提取：产业拐点/产能扩张/订单爆发/产品提价）
- 宏观政策文本（AI判定：扶持行业/打压行业/中性）
- 财报附注/公告（AI提取：虚增利润疑点/关联交易/资产出售占比）
- 资金行为模式（AI判定：底部吸筹/中途加仓/高位出货/僵尸股）

**输出 Schema**:
```python
{
    "L1_industry": [{
        "sector": str,
        "policy_score": float,      # -1 ~ +1 政策方向
        "prosperity_signal": float, # 0~1 景气度信号
        "research_catalyst": float, # 0~1 研报催化剂强度
        "avoid_flag": bool,         # 下行赛道标记
    }],
    "L2_capital": [{
        "symbol": str,
        "north_verdict": str,       # "连续加仓"/"震荡"/"持续流出"
        "institution_phase": str,   # "底部建仓"/"加仓"/"减仓"/"未覆盖"
        "main_force_phase": str,    # "底部吸筹"/"中途加仓"/"高位接力"/"出货"/"无关注"
        "crowd_risk": bool,         # 散户抱团/无资金关注
    }],
    "L3_fundamentals": [{
        "symbol": str,
        "deducted_quality": float,     # 0~1 扣非利润质量
        "gross_margin_signal": float,  # 0~1 毛利率趋势
        "cf_quality_flag": int,        # 1=健康 0=可疑 -1=危险
        "hidden_risk_flags": [str],    # ["虚增利润"/"商誉过高"/"质押率超50%"]
    }],
    "L4_chip": [{
        "symbol": str,
        "holder_trend": str,           # "持续集中"/"分散"/"震荡"
        "institution_quality": float,  # 0~1 机构持仓质量
        "lockup_risk": float,          # 0~1 解禁减持风险
    }],
    "L7_risk": [{
        "symbol": str,
        "fraud_risk": float,           # 0~1 造假风险
        "lawsuit_flag": bool,          # 立案调查
        "chaos_flag": bool,            # 主营杂乱/跨界蹭热点
        "exclude": bool,               # 全局排除标记
        "exclude_reason": str,
    }],
    "pool_candidates": [{
        "symbol": str,
        "source": str,                 # "研报发现"/"景气度筛选"/"北向追踪"/"财报挖掘"
        "initial_layer_scores": dict,  # {L1:0.7, L2:0.8, L3:0.6}
    }],
}
```

### 后续开放的 Agent 工具

- `get_kline(symbols, count)` — 数据层
- `get_north_flow(symbol)` — 北向资金
- `get_financials(symbol)` — 财报细项
- `get_holders(symbol)` — 股东结构
- `list_factors(layer)` / `propose_factor(definition)` — 因子层
- `run_light_backtest(symbols, factors)` — 回测层
- `compute_stats(symbols, factors)` — 统计分析

### 禁止 Agent 直接调用

- `broker.send()` / `risk.approve()` / `pool.add()`（需校验确认）
- 任何下单/风控审批/品种池写入操作

## 八、风控体系

### L7 排雷：前置硬性剔除（策略层入口）

在评分开始之前执行，被标记 exclude=True 的标的直接剔除，不进评分流程：

| # | 剔除规则 | 来源 |
|---|---|---|
| 1 | 科创板(688) / ETF / ST / *ST | 系统规则 |
| 2 | 扣非净利润为负 / 连续亏损 | L3财报因子 |
| 3 | 财报造假嫌疑 / 立案调查 / 重大诉讼 | Agent L7标记 |
| 4 | 高位翻倍(60日涨幅>100%) / 纯概念无业绩 | L6技术因子+Agent |
| 5 | 频繁减持(季度>3次) / 质押率>50% / 商誉/总资产>30% | L4+L3因子 |
| 6 | 主营杂乱 / 跨界蹭热点 | Agent L7标记 |
| 7 | 北向持续流出 / 机构持续减仓 | L2资金因子 |

### 风控五道关卡（保留原有五关，L7排雷前置）

| 关卡 | 内容 |
|---|---|
| 0. 排雷前置 | L7 硬性剔除 → 不合格标的不进评分 |
| 1. 极端场景 | 上证-5% / 月回撤-15% / 全板块双杀 / 补偿性反弹 → HALT |
| 2. 持仓纪律 | ZZJC死叉 → 全清 / 硬止损-11% / 时间止损>15天 |
| 3. 仓位约束 | Kelly基础 + 市场调节 + 分类加权(拐点反转>价值趋势>低位潜伏) |
| 4. 信号复核 | 价格/量能/涨跌停二次确认 |
| 5. 合规终审 | 订单终审(资金/手数/价格) + 弹窗确认 |

## 九、止损四维度

- **硬止损**: 入场价 × (1 − 11%)
- **ATR动态**: 收盘 − 2×ATR(14)
- **跟踪止损**: DZT触发后5日内按收盘−5%
- **时间止损**: 持仓>15天且浮盈<3% → 强制离场

取最紧者（最高价）为有效止损。

## 十、评分模型：8 层加权综合

### 公式

```
综合评分 = Σ(layer_i_score × layer_i_weight), i=1..7

其中:
· L1-L6 按各自因子加权求和出 layer_score → [0,1]
· L7 为排雷层 — 不参与加权，触发任何一条则总分=0（直接剔除）
· L8 为分类标签 — 不影响评分，影响仓位和持有策略
```

### 各层权重

| 层级 | 权重 | 说明 |
|---|---|---|
| L1 产业宏观 | 15% | 赛道对了才有底层动力 |
| L2 资金追踪 | 18% | 资金是股价上涨唯一驱动 |
| L3 财报内核 | 18% | 质地决定抗风险能力 |
| L4 筹码结构 | 12% | 筹码集中才有拉升潜力 |
| L5 流动性 | 10% | 有量才有执行可行性 |
| L6 技术趋势 | 17% | 拐点共振确定入场时机 |
| L7 风控排雷 | — | 单项否决，不计分 |
| **总计** | **100%** | |

### 仓位分档（含分类加权）

```python
def size_position(score: float, classification: str, cash: float, equity: float):
    # 基础 Kelly
    kelly = min(0.10 + (score - 0.60) * 0.30, 0.25)

    # L8 分类加权
    class_mult = {
        "拐点反转": 1.2,    # 爆发力最强，优先配置
        "价值趋势": 1.0,    # 标准仓位
        "低位潜伏": 0.6,    # 等待资金觉醒，轻仓试探
    }.get(classification, 0.0)

    kelly *= class_mult

    # 市场环境调节（与先前风控逻辑一致）
    lots = min(int(cash * kelly / (price * 100)), max_lots)
    return lots
```

### L8 价值分类

| 分类 | 特征 | 策略 |
|---|---|---|
| 价值趋势股 | L3≥0.7 + L2≥0.6 + L6≥0.5 | 中长线持有，趋势跟踪止损 |
| 拐点反转股 | L3≥0.5 + L2≥0.7 + L6拐点共振 | 核心主攻，爆发力最强 |
| 低位潜伏股 | L3≥0.6 + PE分位低 + L4≥0.5 + L2待启动 | 轻仓埋伏，等待资金信号 |

### 筛选闭环公式

```
L1产业→L2资金→L3财报→L4筹码→L5流动性→L6技术→L7排雷→L8分类→锁定标的
```

## 十一、交易执行约束

- 同花顺 easytrader: 唯一可行散户方案
- 连接路径可配置: `config.ths_exe_path`
- Broker 接口抽象: 未来可切 QMT
- 每笔交易弹窗确认（宪法第6条铁律）
- 同花顺断开 → 禁止任何下单
- 账号密码不由系统代码接触

## 十二、回测引擎

| 类型 | 用途 | 与实盘关系 |
|---|---|---|
| `backtest/engine.py` (完整) | 系统校验+兜底回测 | 共用 strategy→risk→execution 路径 |
| `backtest/light.py` (轻量) | Agent快速IC测试 | 仅评分+因子相关性，不模拟仓位 |

完整回测: 次日开盘价成交 + 0.1%滑点 + 0.03%手续费
轻量回测: 无成本假设，秒级完成

## 十三、校验规则汇总

| 校验点 | 规则 |
|---|---|
| 品种代码 | 6位数字 + AKShare全A股存在性验证 + 非ST/非退市/非停牌 |
| 因子公式 | 黑名单关键词 + compile检查 + 列名无冲突 + 参数在range内 + 样本数据实际运行 |
| Agent特征 | 数值在定义区间内，null字段检测 |
| 订单 | 资金≤可用 / 手数1~上限 / 价格>0 / 止损<买入价 |
| 板块名 | 在AKShare板块列表中 |

---

*下一阶段: writing-plans 生成实现计划*
