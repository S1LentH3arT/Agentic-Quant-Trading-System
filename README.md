# 🏦 Agentic Quant Trading System v3

> **LLM-enhanced quantitative trading system for A-share market.**
> 8-layer stock selection · 33 factors · AI agent enrichment · full backtest · risk management

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 Table of Contents

- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [📋 Prerequisites](#-prerequisites)
- [🚀 Quick Start](#-quick-start)
- [📊 CLI Commands](#-cli-commands)
- [🤖 AI Agent (Optional)](#-ai-agent-optional)
- [🔒 Safety & Security](#-safety--security)
- [📁 Project Structure](#-project-structure)
- [🛠️ Configuration](#️-configuration)
- [❓ FAQ](#-faq)

---

## ✨ Features

| Layer | Description | Data Source |
|:---|:---|:---|
| 🏭 **L1 Industry** | Policy climate, sector momentum, news catalysts | System + Agent |
| 💰 **L2 Capital Flow** | North-bound money, institutional positioning, main force patterns | System + Agent |
| 📊 **L3 Fundamentals** | Deducted earnings, gross margin, cash flow, PE/PB percentile | Agent |
| 🧩 **L4 Chip Structure** | Shareholder concentration, institutional ratio, lockup risk | Agent |
| 💧 **L5 Liquidity** | Turnover health, supply-demand inflection, independent strength | System |
| 📈 **L6 Technical** | DKX, A1X, box theory, MA alignment, volume-price, multi-period | System |
| 🛡️ **L7 Risk Filter** | Board exclusion, bubble detection, fraud/pledge/insider flags | System + Agent |
| 🏷️ **L8 Classification** | Value-trend / Inflection-reversal / Bottom-lurker | System |

- 🧠 **AI Agent** — DeepSeek LLM enriches L1-L4 with unstructured data parsing (optional)
- 🔄 **Full Backtest Engine** — Same code path as live trading, simulated broker
- ⚡ **Light Backtest** — Fast factor IC testing for rapid experimentation
- 🛡️ **6-Layer Risk Management** — Extreme detection → Position sizing → Signal verification → Compliance
- 📡 **Multi-Source Data** — Tencent API → AKShare → Local CSV cache (3-tier fallback)
- 💾 **Offline Resilience** — Local K-line cache keeps system running when APIs are down

---

## 🏗️ Architecture

```
                    ┌──────────────────────────┐
                    │   QuantResearchAgent     │  LLM enriches L1-L4
                    │   (DeepSeek, optional)   │
                    └──────────┬───────────────┘
                               │ agent_features
                               ▼
AKShare / Tencent  ──→  DataBus  ──→  FactorEngine (33 factors)
                                            │
                                            ▼
                  ┌─────────────────────────────────────┐
                  │        8-Layer Scorer               │
                  │  L1(15%)+L2(18%)+L3(18%)+L4(12%)   │
                  │  +L5(10%)+L6(17%)+L7(veto)         │
                  └──────────────┬──────────────────────┘
                                 │
                                 ▼
                  ┌─────────────────────────────────────┐
                  │  RiskManager (6 gates) → Signals    │
                  │  → OrderManager → MessageBox Confirm│
                  │  → THSBroker (easytrader) → 同花顺  │
                  └─────────────────────────────────────┘
```

---

## 📋 Prerequisites

| Requirement | Version | Check |
|:---|:---|:---|
| 🐍 Python | **3.12+** | `python --version` |
| 📦 pip | latest | `pip --version` |
| 🪟 Windows | 10/11 | (required for `easytrader`) |
| 🔑 DeepSeek API Key | — | *Optional* for AI Agent |

### Required Python Packages

```
pandas  numpy  akshare  requests  mootdx
```

### Optional Packages

```
openai          # AI Agent (DeepSeek API)
easytrader      # Live trading via 同花顺
qstock          # Alternative data source
streamlit       # Dashboard (quant_desk.py)
```

---

## 🚀 Quick Start

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/Agentic-Quant-Trading-System.git
cd Agentic-Quant-Trading-System
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Or (Windows CMD)
.venv\Scripts\activate.bat

# Or (Git Bash / WSL)
source .venv/Scripts/activate
```

### Step 3: Install Core Dependencies

```bash
pip install pandas numpy akshare requests mootdx
```

### Step 4: Verify Installation

```bash
python -m quant_system test
```

Expected output:
```
============================================================
  Quant System v3 — System Test
============================================================
  Registered Factors: 33
    L6 A1X: 4 columns
    L6 DKX: 3 columns
    ...
  Light Backtest: OK
  Pool: 24 stocks across 5 sectors
  Status: Ready [OK]
```

### Step 5: Run Your First Scan

```bash
# Fetch market intelligence
python -m quant_system intel

# Run a full decision scan
python -m quant_system scan

# Run backtest on the main pool
python -m quant_system backtest
```

---

## 📊 CLI Commands

| Command | Description | Example |
|:---|:---|:---|
| `test` | 🧪 System import test + factor registry validation | `python -m quant_system test` |
| `intel` | 📡 Fetch market intelligence (hot list, news, sector flow) | `python -m quant_system intel` |
| `scan` | 🔍 Full decision scan: intel → factors → scoring → signals | `python -m quant_system scan` |
| `scan --agent` | 🤖 Scan with AI Agent enrichment (L1-L4) | `python -m quant_system scan --agent` |
| `backtest` | 📈 Run backtest on pool stocks | `python -m quant_system backtest` |
| `status` | 📊 Print system status (factors, pool, paths) | `python -m quant_system status` |

### Example: Full Daily Workflow

```bash
# 1. Morning: collect overnight intelligence
python -m quant_system intel

# 2. After market open: scan with AI agent
python -m quant_system scan --agent

# 3. After close: run backtest to review signals
python -m quant_system backtest

# 4. End of day: check system health
python -m quant_system status
```

---

## 🤖 AI Agent (Optional)

The system works **fully without AI** — the 33-factor engine computes L5+L6 from pure math. The AI Agent adds L1-L4 enrichment by parsing unstructured data (news, policy text, research reports) into structured quantitative features.

### Enable AI Agent

1. **Get a DeepSeek API Key** from [platform.deepseek.com](https://platform.deepseek.com)

2. **Set the environment variable:**

   ```bash
   # Windows PowerShell
   $env:DEEPSEEK_API_KEY = "sk-your-key-here"

   # Windows CMD
   set DEEPSEEK_API_KEY=sk-your-key-here

   # Git Bash
   export DEEPSEEK_API_KEY=sk-your-key-here
   ```

3. **Run scan with Agent:**

   ```bash
   python -m quant_system scan --agent
   ```

### Fallback Behavior

| Scenario | Result |
|:---|:---|
| No `--agent` flag | System runs on pure factors (default) |
| API key not set | Warning printed, degrades to system mode |
| DeepSeek API timeout | Warning printed, degrades to system mode |
| Agent returns bad data | Validation guard clamps values to safe range |

> 🛡️ **Agent NEVER touches L5/L6/L7** — core scoring is always system-driven.

---

## 🔒 Safety & Security

### 6 Constitutional Rules

1. 📐 **Logic first, data second** — framework before numbers
2. 🤖 **System decides** — entries, exits, sizing all driven by system
3. 💸 **Capital must roll** — cash idle > 24h triggers forced rotation
4. 📊 **Data over opinion** — user bias never overrides system signals
5. 🔇 **Silent discipline** — alerts only on violations, quiet otherwise
6. 🔐 **Security & privacy** — accounts, passwords, positions NEVER leave local machine

### Trade Confirmation

Every live trade requires **Windows MessageBox confirmation** — no silent execution, ever.

---

## 📁 Project Structure

```
Agentic-Quant-Trading-System/
├── quant_system/               # 🏗️ Core system (new architecture)
│   ├── __main__.py             #   CLI entry point
│   ├── config.py               #   Path & config management
│   ├── params.json             #   Tunable parameters registry
│   ├── data/                   #   Data layer
│   │   ├── provider.py         #     Multi-source data adapter
│   │   ├── bus.py              #     Data cache + dedup
│   │   ├── intelligence.py     #     Market intelligence collector
│   │   └── sources.py          #     Data source definitions
│   ├── factors/                #   Factor layer
│   │   ├── engine.py           #     Factor computation engine
│   │   ├── registry.py         #     Factor registry (33 factors)
│   │   ├── validator.py        #     Factor safety validator
│   │   └── definitions/        #     L1-L7 factor definitions
│   ├── strategy/               #   Strategy layer
│   │   ├── scorer.py           #     8-layer weighted scoring
│   │   ├── classifier.py       #     L8 value classification
│   │   ├── pool.py             #     Stock pool management
│   │   ├── signals.py          #     Buy/sell signal generation
│   │   ├── discovery.py        #     Market-wide discovery engine
│   │   └── sector.py           #     Sector analysis
│   ├── risk/                   #   Risk layer
│   │   ├── manager.py          #     6-gate risk approval
│   │   ├── position.py         #     Kelly position sizing
│   │   ├── stops.py            #     4D stop management
│   │   └── extreme.py          #     Extreme scenario detection
│   ├── execution/              #   Execution layer
│   │   ├── broker.py           #     THSBroker + SimulatedBroker
│   │   ├── orders.py           #     Order lifecycle manager
│   │   └── confirm.py          #     Windows MessageBox popup
│   ├── backtest/               #   Backtest layer
│   │   ├── engine.py           #     Full backtest (same as live)
│   │   ├── light.py            #     Light backtest (Agent IC test)
│   │   └── metrics.py          #     7-D performance metrics
│   ├── agents/                 #   AI Agent layer
│   │   ├── base.py             #     ResearchAgent base class
│   │   ├── researcher.py       #     QuantResearchAgent
│   │   └── bridge.py           #     Agent ↔ Scorer bridge
│   ├── validation/             #   Validation layer
│   │   ├── guard.py            #     Unified validation gate
│   │   ├── factor_check.py     #     Factor safety check
│   │   ├── pool_check.py       #     Hallucination prevention
│   │   ├── signal_check.py     #     Signal reasonability
│   │   └── order_check.py      #     Order final review
│   ├── evolution/              #   Meta-evolution
│   │   ├── governor.py         #     Governance audit chain
│   │   └── param_loader.py     #     Parameter management
│   └── storage/                #   Persistence
│       └── journal.py          #     SQLite trade journal
├── tdx-mcp/                    #   Legacy connection layer
│   ├── connection.py           #     ConnectionManager (kept)
│   └── params.json             #     Parameter registry (kept)
├── memory/                     #   🧠 Trading experience base
├── docs/                       #   📚 Design documents
├── quant_desk.py               #   📊 Streamlit dashboard
└── config.py                   #   ⚙️ Global project config
```

---

## 🛠️ Configuration

### Data Sources

Edit the data provider or set environment variables to configure sources:

```python
# quant_system/data/provider.py
# 3-tier fallback: Tencent → AKShare → local cache
# No configuration needed — works out of the box
```

### Factor Weights

Edit `quant_system/params.json` to adjust scoring weights, thresholds, and ranges. All parameters are hot-reloadable without code changes.

### Agent Settings

```json
// quant_system/params.json → agent section
{
  "agent": {
    "enabled": false,        // Enable by default (--agent overrides)
    "timeout_seconds": 60,   // API timeout
    "max_stocks": 20         // Max stocks sent to Agent
  }
}
```

### Trading Setup (Optional)

For live trading with 同花顺:

```bash
pip install easytrader

# Ensure 同花顺 xiadan.exe is running
# Configure path in: quant_system/execution/broker.py
```

---

## ❓ FAQ

**Q: Does the system require an internet connection?**
A: For fresh data, yes. But K-line data is cached locally — once fetched, the system can run offline for up to 3 days with cached data.

**Q: Does the AI Agent cost money?**
A: DeepSeek API charges by token (~$0.14/1M input tokens). The Agent is **disabled by default**. Without `--agent`, the system costs nothing to run.

**Q: Can I use a different LLM provider?**
A: Yes! Edit `quant_system/agents/base.py` — change `base_url` and `model` to any OpenAI-compatible API.

**Q: Does this support US stocks or crypto?**
A: Currently A-share only. The data provider and factor definitions are A-share specific.

**Q: Is live trading safe?**
A: Every trade requires a **Windows MessageBox confirmation** (click [Yes] to proceed). No silent execution. The system also enforces a 6-layer risk approval chain before any order reaches the broker.

**Q: Why are some scores always the same?**
A: L3 (fundamentals) and L4 (chip structure) need data from AKShare's financial API. If AKShare is blocked on your network, these layers return neutral values. Enable `--agent` to fill these gaps with AI-inferred estimates.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Built with ❤️ for disciplined quantitative trading</b><br>
  <sub>Data-driven. System-ruled. Human-supervised.</sub>
</p>
