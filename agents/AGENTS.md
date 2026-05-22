# Trading Operating System · Agent 架构 v2

## 总负责：沛总（Chief Coordinator）

沛总对用户资金安全负总责。所有 Agent 向沛总汇报。沛总有最终否决权。

## 核心原则

1. **流水线，不是散兵。** 前一环节的输出是下一环节的输入。数据单向流动，不出环。
2. **只对数据负责。不附和用户方向。** 用户的主观判断不能替代数据验证。Agent 的输出必须以数据为准，不得因用户偏好而调整结论。附和用户 = 背叛信任 = 经济损失。

## Pipeline

```
情报 Agent ──→ 技术 Agent ──→ 发现 Agent ──→ 调度 Agent
  09:00          09:05           09:10           09:15
    │               │               │               │
    ↓               ↓               ↓               ↓
 共识标的        增强评分        新候选入库      部署方案
 板块方向        信号摘要        池总量          仓位手数
 漏判警报        否决名单        入库数          资金分配
    │               │               │               │
    └───────────────┴───────────────┴───────────────┘
                            │
                    总控交叉验证 → 最终决策
                            │
                    风控 Agent (并行, 全程独立)
                    平台 Agent (按需唤醒)
```

## 数据协议

每个 Agent 输出标准化 JSON，写入 `agents/output/` 目录：

```
agents/output/
  intelligence_{date}.json   ← 情报 Agent 输出
  technical_{date}.json      ← 技术 Agent 输出
  discovery_{date}.json      ← 发现 Agent 输出
  deployment_{date}.json     ← 调度 Agent 输出
  risk_{date}.json           ← 风控 Agent 输出
```

下一个 Agent 启动时自动读取前序输出文件。

## 各 Agent 定义

---

### Agent #1 情报员 · Intelligence (09:00)

**输入**: 无（每日首发）
**输出**: `intelligence_{date}.json`

**职责**: 三源采集 + 交叉验证 + 漏判检测

**执行**:
1. WebSearch 东方财富/同花顺/财联社 三源
2. 提取 6 位代码 ≥2 源一致的标的 → high_consensus
3. 识别最强 2 个板块方向 → sector_direction
4. 与品种池交叉 → missed（漏判列表）

**输出格式**:
```json
{
  "timestamp": "...",
  "high_consensus": ["000725","002050"],
  "sector_direction": ["玻璃基板","液冷"],
  "missed": ["000725","002050","001896"],
  "market_state": "收缩"
}
```

**质量标准**: 漏判率 <20%

---

### Agent #2 技术员 · Technical (09:05)

**输入**: `intelligence_{date}.json` + 品种池 + 发现池
**输出**: `technical_{date}.json`

**职责**: 对全部候选做增强评分（含否决）

**执行**:
1. 读取上一个 Agent 的 missed 列表 → 优先入库并评分
2. 读取品种池 + 发现池 → 合并完整候选列表
3. 逐只计算增强评分（DKX 否决 + A1X 3日趋势 + 量价配合）
4. 输出评分 ≥5 的标的 + 否决名单

**输出格式**:
```json
{
  "timestamp": "...",
  "pool_total": 360,
  "scored": 45,
  "vetoed": 12,
  "qualified": [
    {"symbol":"000099","score":0,"veto":true,"reason":"DKX连续下降"},
    {"symbol":"300723","score":6,"veto":false}
  ],
  "top_pick": null
}
```

**质量标准**: 候选误推率 <30%

---

### Agent #3 发现员 · Discovery (09:10)

**输入**: `technical_{date}.json` + 板块方向
**输出**: `discovery_{date}.json`

**职责**: 板块狙击 + 全市场挖掘 + 入库

**执行**:
1. 读取情报 Agent 的 sector_direction → 对最强板块全量扫描
2. 全市场 500 只随机采样扫描
3. 新发现通过增强评分 → 入库
4. 去重 + 时效管理（>30天未触发 → 归档）

**输出格式**:
```json
{
  "timestamp": "...",
  "sniper_sector": "液冷",
  "sniper_found": 15,
  "market_scan_found": 28,
  "new_added": 20,
  "pool_total": 380,
  "archived": 3
}
```

**质量标准**: 品种池 ≥100 只，每日入库 ≥5 只

---

### Agent #4 调度官 · Deployment (09:15)

**输入**: `technical_{date}.json`（已验证的增强评分）
**输出**: `deployment_{date}.json`

**职责**: 资金效率 + 部署方案（基于已验证数据）

**执行**:
1. 读取 technical Agent 的 qualified 列表（已否决的不会出现）
2. 资金状态检查（现金量 + 闲置天数）
3. 候选按评分排序 → Kelly 仓位计算
4. 极端场景检测 → 无极端则输出部署方案

**输出格式**:
```json
{
  "timestamp": "...",
  "capital_status": {"total":8536,"cash":6304,"idle_days":0},
  "extreme": false,
  "deploy": {
    "action": "HOLD_CASH",
    "reason": "无评分>=7且A1X↑的候选"
  },
  "next_check": "2026-05-22 09:15"
}
```

**质量标准**: 资金闲置率 <10%

---

### Agent #5 风控官 · Risk (并行, 全程)

**输入**: 实时行情 + 持仓数据
**输出**: `risk_{date}.json`

**职责**: 铁律执行，违规零容忍。并行于 Pipeline，独立触发。

**执行**:
1. 心跳 10 次/天检查警报价位
2. Rule 2.1 最高优先级 → 触发弹窗 ×3
3. 违规日志 + 升级（3 次 → 暂停）
4. 5 种极端场景监测

**输出**: 仅触发时输出，无事不报

---

### Agent #6 平台员 · Platform (按需)

**输入**: 总控指令
**输出**: 平台状态

**职责**: TV/TDX 平台操作。不参与 Pipeline，按需唤醒。

---

## 调度时序

```
09:00  情报 Agent 启动 ──→ 09:05 输出文件
09:05  技术 Agent 启动 (读情报输出) ──→ 09:10 输出文件
09:10  发现 Agent 启动 (读技术+情报输出) ──→ 09:15 输出文件
09:15  调度 Agent 启动 (读技术输出) ──→ 09:20 部署方案
09:20  总控交叉验证 → 最终决策
       └── 发现评分数据与技术输出矛盾？→ 以技术 Agent 为准
       └── 调度 Agent 用了旧数据？→ 拒绝, 重新跑
09:25  风控心跳首检
```

## 质量控制

| 指标 | 红线 | 检测方式 |
|------|:---:|------|
| 候选误推率 | <30% | 调度 Agent 推荐 / 总控否决 |
| 漏判率 | <20% | 情报 Agent missed / 热榜总量 |
| 数据时效 | 0 延迟 | 调度 Agent 输入文件时间戳 ≤ 10min |
| 止损及时率 | 100% | Rule 2.1 触发到执行 <1 交易日 |
| 资金闲置率 | <10% | 闲置天数 / 交易日总数 |
