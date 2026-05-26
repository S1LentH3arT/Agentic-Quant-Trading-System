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

## 三、目录结构

```
quant_system/                        # 新根目录（放弃 tdx-mcp/）
├── config.py                        # 全局配置 + 路径管理
├── params.json                      # 可调参数注册表
│
├── data/
│   ├── provider.py                  # AKShare 统一适配器
│   └── bus.py                       # 数据总线（缓存+去重）
│
├── factors/
│   ├── engine.py                    # 因子计算引擎
│   ├── registry.py                  # 因子注册表（管理名称/公式/参数/有效期）
│   ├── validator.py                 # 因子校验（公式安全/参数/IC）
│   └── definitions/
│       ├── trend.py                 # 趋势类：DKX/A1X/均线角度
│       ├── volume.py                # 量能类：量比/放量/缩量
│       ├── box.py                   # 箱体类：布林/通道/支撑阻力
│       └── custom.py                # Agent 构造的因子（校验后写入）
│
├── strategy/
│   ├── scorer.py                    # 评分引擎（技术评分 + Agent特征加成）
│   ├── pool.py                      # 品种池（主力池 + 发现池 + 黑名单）
│   ├── signals.py                   # 信号生成（买入/卖出/减仓）
│   ├── discovery.py                 # 全市场发现引擎
│   └── sector.py                    # 板块分析
│
├── risk/
│   ├── manager.py                   # 风控总入口（五道关卡）
│   ├── position.py                  # 仓位计算（Kelly + 市场调节 + 集中度）
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
│   └── researcher.py                # QuantResearchAgent: 数据→量化特征
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
  ▼
data/provider ──→ data/bus
  │
  ├──→ agents/researcher ──→ {market_features, sector_features, stock_signals, risk_features, pool_candidates}
  │                              │
  │                              ▼
  │                        validation/guard ──→ 防幻觉校验
  │                              │
  │                              ▼ 校验通过
  │                    strategy/scorer ←── agent特征叠加到技术评分
  │
  └──→ factors/engine ──→ factors/registry
                              │
                              ▼
                        strategy/scorer  (0-9 基础技术评分)
                              │
                              ▼ agent_bonus + event_flag - crowding_warning
                        调整后评分 (0-10)
                              │
                              ▼
                        strategy/signals  → 买入/卖出/减仓信号
                              │
                              ▼
                        risk/manager ──→ 五道关卡
                              │
                              ▼ 通过的订单
                        validation/order_check ──→ 终审
                              │
                              ▼
                        execution/confirm ──→ Windows 弹窗
                              │
                              ▼ 用户确认
                        execution/broker ──→ easytrader 下单
                              │
                              ▼
                        storage/journal ──→ SQLite 记录

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

所有因子统一用 `FactorDefinition` 注册：

```python
@dataclass
class FactorDefinition:
    name: str              # 因子名，如 "A1X"
    category: str          # trend / volume / box / custom
    version: int
    author: str            # "system" 或 "agent"
    params: dict           # {name: {value, range[min,max], desc}}
    compute_fn: str        # Python lambda 表达式字符串
    requires: list[str]    # 需要的输入列 ["close", "volume", ...]
    output_columns: list[str]  # 输出的新列名
    hypothesis: str = ""   # Agent提交时必填：因子假设
```

## 七、Agent 设计

### 单一 QuantResearchAgent

- **输入**: 市场原始数据（热榜/板块/新闻/财报）
- **输出**: 纯量化特征向量，不产报告
  - `market_features`: regime_score, breadth_ratio, limit_down_severity, hot_concentration, new_high_ratio
  - `sector_features`: momentum, capital_flow, leader_strength, dispersion, quality_score
  - `stock_signals`: feature_bonus [-5,+5], event_flag [-1,0,1], crowding_warning [0,1]
  - `risk_features`: sector_drawdown_flag, compensatory_rally, style_rotation
  - `pool_candidates`: symbol + source + initial_quality
- **规则**: 不确定输出 null，不编造，严格按 schema

### 后续开放的 Agent 工具

- `get_kline(symbols, count)` — 数据层
- `list_factors()` / `propose_factor(definition)` — 因子层
- `run_light_backtest(symbols, strategy)` — 回测层
- `compute_stats(symbols, factors)` — 回测层

### 禁止 Agent 直接调用

- `broker.send()` — 执行层
- `risk.approve()` — 风控层
- `pool.add()` — 需校验确认

## 八、风控五道关卡

| 关卡 | 内容 |
|---|---|
| 1. 极端场景 | 上证-5% / 月回撤-15% / 全板块双杀 / 补偿性反弹 → HALT |
| 2. 持仓纪律 | ZZJC死叉 → 全清 / 硬止损-11% / 时间止损>15天 |
| 3. 仓位约束 | Kelly基础 + 市场环境调节 + 单票≤30%权益 + 板块≤40% |
| 4. 信号复核 | 价格/量能/涨跌停二次确认 |
| 5. 合规终审 | 订单终审(资金/手数/价格) + 弹窗确认 |

## 九、止损四维度

- **硬止损**: 入场价 × (1 − 11%)
- **ATR动态**: 收盘 − 2×ATR(14)
- **跟踪止损**: DZT触发后5日内按收盘−5%
- **时间止损**: 持仓>15天且浮盈<3% → 强制离场

取最紧者（最高价）为有效止损。

## 十、评分模型

### 基础技术评分 (0-9)
- DKX否决: 连降3日 → 0分
- 冲高回落扣分: −2
- A1X: 0-3分 + 箱体: 0-3分 + 量能: 0-3分

### Agent 特征叠加
```
调整后评分 = 技术评分 + feature_bonus[-5,+5] + event_flag[-1,0,1] − crowding_warning×2
clamp 到 [0, 10]
```

### 仓位分档

| 评分 | Kelly基准 | 市场调节 | 最大手数 |
|---|---|---|---|
| >=8 | 10% + (8-6)×5% = 20% | ±10% | 4 |
| >=7 | 15% | ±10% | 3 |
| >=6 | 10% | ±10% | 2 |
| <6 | 不部署 | - | 0 |

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
