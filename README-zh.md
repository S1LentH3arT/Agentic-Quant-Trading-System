# 🏦 OpenQuant v3

> **LLM 增强的 A 股量化交易系统。**
> 8 层选股 · 33 因子 · AI 智能体增强 · 完整回测 · 风控体系

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 目录

- [✨ 核心功能](#-核心功能)
- [🏗️ 系统架构](#️-系统架构)
- [📋 环境要求](#-环境要求)
- [🚀 快速开始](#-快速开始)
- [📊 CLI 命令](#-cli-命令)
- [🤖 AI 智能体（可选）](#-ai-智能体可选)
- [🔒 安全私密](#-安全私密)
- [📁 项目结构](#-项目结构)
- [🛠️ 配置说明](#️-配置说明)
- [❓ 常见问题](#-常见问题)

---

## ✨ 核心功能

| 层级 | 说明 | 数据来源 |
|:---|:---|:---|
| 🏭 **L1 产业宏观** | 政策气候、板块动量、消息催化强度 | 系统 + AI 智能体 |
| 💰 **L2 资金追踪** | 北向资金、机构持仓、主力大单行为 | 系统 + AI 智能体 |
| 📊 **L3 财报内核** | 扣非利润、毛利率、现金流、PE/PB 分位 | AI 智能体 |
| 🧩 **L4 筹码结构** | 股东集中度、机构占比、解禁风险 | AI 智能体 |
| 💧 **L5 流动性** | 换手健康度、供需拐点、独立抗跌 | 系统 |
| 📈 **L6 技术趋势** | DKX、A1X、箱体、均线、量价、多周期共振 | 系统 |
| 🛡️ **L7 风控排雷** | 科创板/ST 剔除、高位翻倍、造假/质押/减持标记 | 系统 + AI 智能体 |
| 🏷️ **L8 价值分类** | 价值趋势股 / 拐点反转股 / 低位潜伏股 | 系统 |

- 🧠 **AI 智能体** — DeepSeek 大模型解析非结构化数据，增强 L1-L4 特征（可选）
- 🔄 **完整回测引擎** — 与实盘共用同一套代码路径
- ⚡ **轻量回测** — 秒级因子 IC 测试，快速实验
- 🛡️ **六道风控关卡** — 极端检测 → 仓位约束 → 信号复核 → 合规终审
- 📡 **多源数据** — 腾讯 API → AKShare → 本地 CSV 缓存（三级兜底）
- 💾 **离线韧性** — 本地 K 线缓存，API 挂了也能跑

---

## 🏗️ 系统架构

```
                    ┌──────────────────────────┐
                    │   QuantResearchAgent     │  大模型增强 L1-L4
                    │   (DeepSeek, 可选)       │
                    └──────────┬───────────────┘
                               │ agent_features
                               ▼
腾讯API / AKShare  ──→  DataBus  ──→  FactorEngine (33因子)
                                            │
                                            ▼
                  ┌─────────────────────────────────────┐
                  │          8 层综合评分                │
                  │  L1(15%)+L2(18%)+L3(18%)+L4(12%)   │
                  │  +L5(10%)+L6(17%)+L7(一票否决)      │
                  └──────────────┬──────────────────────┘
                                 │
                                 ▼
                  ┌─────────────────────────────────────┐
                  │  风控(6关) → 信号 → 弹窗确认         │
                  │  → THSBroker(easytrader) → 同花顺   │
                  └─────────────────────────────────────┘
```

---

## 📋 环境要求

| 依赖 | 版本 | 检查方式 |
|:---|:---|:---|
| 🐍 Python | **3.12+** | `python --version` |
| 📦 pip | 最新 | `pip --version` |
| 🪟 Windows | 10/11 | （`easytrader` 实盘交易需要） |
| 🔑 DeepSeek API Key | — | *可选*，仅 AI 智能体需要 |

### 核心依赖包

```
pandas  numpy  akshare  requests  mootdx
```

### 可选依赖包

```
openai          # AI 智能体 (DeepSeek API)
easytrader      # 实盘交易 (同花顺)
qstock          # 备用数据源
streamlit       # 仪表盘 (quant_desk.py)
```

---

## 🚀 快速开始

### 第一步：克隆仓库

```bash
git clone https://github.com/your-username/OpenQuant.git
cd OpenQuant
```

### 第二步：创建虚拟环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 或 (Windows CMD)
.venv\Scripts\activate.bat

# 或 (Git Bash / WSL)
source .venv/Scripts/activate
```

### 第三步：安装核心依赖

```bash
pip install pandas numpy akshare requests mootdx
```

> 💡 国内用户如果下载慢，可以用清华镜像：
> ```bash
> pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pandas numpy akshare requests mootdx
> ```

### 第四步：验证安装

```bash
python -m quant_system test
```

看到以下输出表示安装成功：
```
============================================================
  Quant System v3 — 系统测试
============================================================
  已注册因子: 33
    L6 A1X: 4 columns
    L6 DKX: 3 columns
    ...
  轻量回测: OK
  品种池: 24 只
  状态: 系统就绪 [OK]
```

### 第五步：运行第一个扫描

```bash
# 拉取市场情报（热榜、电报、板块）
python -m quant_system intel

# 完整决策扫描
python -m quant_system scan

# 主力池回测
python -m quant_system backtest
```

---

## 📊 CLI 命令

| 命令 | 功能 | 示例 |
|:---|:---|:---|
| `test` | 🧪 系统导入测试 + 因子注册验证 | `python -m quant_system test` |
| `intel` | 📡 市场情报采集（热榜、电报、板块流向） | `python -m quant_system intel` |
| `scan` | 🔍 完整决策扫描：情报 → 因子 → 评分 → 信号 | `python -m quant_system scan` |
| `scan --agent` | 🤖 带 AI 智能体增强的决策扫描（L1-L4） | `python -m quant_system scan --agent` |
| `backtest` | 📈 主力池批量回测 | `python -m quant_system backtest` |
| `status` | 📊 打印系统状态（因子数、品种池、路径） | `python -m quant_system status` |

### 示例：完整交易日流程

```bash
# 1. 早盘前：采集隔夜情报
python -m quant_system intel

# 2. 开盘后：带 AI 智能体扫描
python -m quant_system scan --agent

# 3. 收盘后：回测复盘
python -m quant_system backtest

# 4. 全天结束：检查系统状态
python -m quant_system status
```

---

## 🤖 AI 智能体（可选）

系统**不依赖 AI 也能完整运行**——33 因子引擎对 L5+L6 做纯数学计算。AI 智能体的作用是解析非结构化数据（新闻、政策文本、研报），将其转化为 L1-L4 的结构化量化特征，填补系统无法从 API 直接获取的数据缺口。

### 启用 AI 智能体

1. **获取 DeepSeek API Key**：[platform.deepseek.com](https://platform.deepseek.com)

2. **设置环境变量：**

   ```bash
   # Windows PowerShell
   $env:DEEPSEEK_API_KEY = "sk-你的密钥"

   # Windows CMD
   set DEEPSEEK_API_KEY=sk-你的密钥

   # Git Bash
   export DEEPSEEK_API_KEY=sk-你的密钥
   ```

3. **带 Agent 运行扫描：**

   ```bash
   python -m quant_system scan --agent
   ```

### 降级机制

| 场景 | 结果 |
|:---|:---|
| 不加 `--agent` | 纯因子计算（默认模式） |
| API Key 未设置 | 打印警告，自动降级为纯因子模式 |
| DeepSeek API 超时 | 打印警告，自动降级 |
| 智能体返回异常值 | 校验层裁剪到安全范围，不污染评分 |

> 🛡️ **智能体绝不触碰 L5/L6/L7**——核心评分始终由系统驱动。

---

## 🔒 安全私密

### 六条宪法

1. 📐 **逻辑先行，数据验证** — 先说清楚逻辑框架，再用数据验证
2. 🤖 **系统说了算** — 开仓、减仓、仓位、轮动全部由系统决定
3. 💸 **资金必须滚动** — 现金 > 1000 且闲置 > 24h → 强迫轮动
4. 📊 **不附和，只对数据负责** — 用户的方向 ≠ 系统的方向
5. 🔇 **纪律静默运行** — 违规触发时弹窗，无事不表
6. 🔐 **安全私密第一** — 账号、密码、持仓、资金绝不出本机

### 交易确认

每笔实盘交易**必须经过 Windows 弹窗确认**——永不静默下单。

```
┌──────────────────────────────────────┐
│  ⚡ 买入确认 — 600863               │
│                                      │
│  价格: 7.30 元                       │
│  手数: 2 手                          │
│  资金: 1,460 元                      │
│  止损: 6.50                          │
│                                      │
│  逻辑: A1X金叉 + 箱体低位 + 放量     │
│                                      │
│  点[是]确认   点[否]取消             │
└──────────────────────────────────────┘
```

---

## 📁 项目结构

```
OpenQuant/
├── quant_system/               # 🏗️ 核心系统（新架构）
│   ├── __main__.py             #   CLI 主入口
│   ├── config.py               #   路径与配置管理
│   ├── params.json             #   可调参数注册表
│   ├── data/                   #   数据层
│   │   ├── provider.py         #     多源数据适配器
│   │   ├── bus.py              #     数据总线（缓存+去重）
│   │   ├── intelligence.py     #     市场情报采集
│   │   └── sources.py          #     数据源定义
│   ├── factors/                #   因子层
│   │   ├── engine.py           #     因子计算引擎
│   │   ├── registry.py         #     因子注册表（33个因子）
│   │   ├── validator.py        #     因子安全校验
│   │   └── definitions/        #     L1-L7 因子定义文件
│   ├── strategy/               #   策略层
│   │   ├── scorer.py           #     8层加权综合评分
│   │   ├── classifier.py       #     L8 价值分类
│   │   ├── pool.py             #     品种池管理
│   │   ├── signals.py          #     买卖信号生成
│   │   ├── discovery.py        #     全市场发现引擎
│   │   └── sector.py           #     板块分析
│   ├── risk/                   #   风控层
│   │   ├── manager.py          #     六道关卡风控审批
│   │   ├── position.py         #     Kelly 仓位计算
│   │   ├── stops.py            #     四维止损管理
│   │   └── extreme.py          #     极端场景检测
│   ├── execution/              #   执行层
│   │   ├── broker.py           #     THSBroker + 模拟券商
│   │   ├── orders.py           #     订单生命周期管理
│   │   └── confirm.py          #     Windows MessageBox 弹窗
│   ├── backtest/               #   回测层
│   │   ├── engine.py           #     完整回测（与实盘同路径）
│   │   ├── light.py            #     轻量回测（Agent IC 测试）
│   │   └── metrics.py          #     7 维度绩效指标
│   ├── agents/                 #   AI 智能体层
│   │   ├── base.py             #     ResearchAgent 基类
│   │   ├── researcher.py       #     QuantResearchAgent
│   │   └── bridge.py           #     智能体 ↔ 评分器桥接
│   ├── validation/             #   校验层
│   │   ├── guard.py            #     统一校验入口
│   │   ├── factor_check.py     #     因子合法性
│   │   ├── pool_check.py       #     品种池防幻觉
│   │   ├── signal_check.py     #     信号合理性
│   │   └── order_check.py      #     订单终审
│   ├── evolution/              #   元进化
│   │   ├── governor.py         #     治理审计链
│   │   └── param_loader.py     #     参数管理
│   └── storage/                #   持久化
│       └── journal.py          #     SQLite 交易日志
├── tdx-mcp/                    #   遗留连接层
│   ├── connection.py           #     ConnectionManager（保留）
│   └── params.json             #     参数注册表（保留）
├── memory/                     #   🧠 交易经验库
├── docs/                       #   📚 设计文档
├── quant_desk.py               #   📊 Streamlit 仪表盘
└── config.py                   #   ⚙️ 全局项目配置
```

---

## 🛠️ 配置说明

### 数据源

系统默认使用三级兜底策略，无需额外配置即可工作：

```
腾讯 API →  AKShare  →  本地 CSV 缓存
 (主力)     (备用)       (兜底)
```

### 因子权重

编辑 `quant_system/params.json` 可调整各因子权重、阈值和范围。所有参数热加载，无需改代码。

### 智能体配置

```json
// quant_system/params.json → agent 配置段
{
  "agent": {
    "enabled": false,        // 默认启用？（--agent 可覆盖）
    "timeout_seconds": 60,   // API 超时时间（秒）
    "max_stocks": 20         // 送入智能体的最大股票数
  }
}
```

### 实盘交易配置（可选）

接入同花顺实盘交易：

```bash
pip install easytrader

# 确保同花顺 xiadan.exe 已运行
# 配置路径在: quant_system/execution/broker.py
```

---

## ❓ 常见问题

**Q: 系统需要联网吗？**
A: 获取新数据需要联网。但 K 线数据会自动缓存到本地 CSV——一旦拉取过一次，即使断网也能用缓存数据继续运行（最多 3 天）。

**Q: AI 智能体花钱吗？**
A: DeepSeek API 按 token 计费（约 1 元/百万输入 token）。智能体**默认关闭**，不加 `--agent` 完全免费。

**Q: 能用其他大模型吗？**
A: 可以！修改 `quant_system/agents/base.py`——改 `base_url` 和 `model` 即可对接任何 OpenAI 兼容的 API。

**Q: 支持美股或加密货币吗？**
A: 当前仅支持 A 股。数据适配器和因子定义均为 A 股专用。

**Q: 实盘交易安全吗？**
A: 每笔交易**必须经过 Windows 弹窗确认**（点[是]才执行）。系统还设置了六道风控关卡，任何一关不通过都不会到达券商。

**Q: 为什么有些评分总是相同？**
A: L3（财报）和 L4（筹码）需要 AKShare 的财报/股东 API 数据。如果网络环境导致 AKShare 不可用，这些层会返回中性值。启用 `--agent` 可以用 AI 推断值填补这些缺口。

**Q: 可以部署到 Linux 服务器吗？**
A: 研究和回测部分完全可以在 Linux 上运行。但实盘交易依赖 `easytrader`（Windows 同花顺客户端），只能在 Windows 上执行。

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

<p align="center">
  <b>用纪律和数据，做有尊严的交易</b><br>
  <sub>数据驱动 · 系统裁决 · 人工监督</sub>
</p>
