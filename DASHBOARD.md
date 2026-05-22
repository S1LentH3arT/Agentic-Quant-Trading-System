# 📈 量化交易系统 - 实时运行仪表盘 (Dashboard)

> **状态**: 🟢 运行中 | **最后更新**: 2026-05-11 | **核心逻辑**: 非对称性 $\text{EV}$ 驱动

## 🚩 当前核心战略
- **目标**: A股 5400 标的 $\rightarrow$ Alpha 绝对收益
- **风控**: $\text{MDD} < 8\%$ (强制止损)
- **当前阶段**: 机构化演进 $\rightarrow$ 捕捉高凸性机会

## 💰 资产分布 (Portfolio Snapshot)
| 池子 | 标的 | 角色 | 成本 | 状态 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **堡垒池** | 600036 | 防御锚点 | 37.5 | Holding | $\text{ROE} \ge 15\%$ |
| **猎手池** | 513180 | 弹性标的 | 0.626 | Holding | 恒生科技 $\text{Beta}$ 驱动 |
| **猎手池** | 000981 | 进攻标的 | 4.01 | Holding | 订单流驱动 |

## 🔍 重点监控 (Watchlist)
- [ ] **688055**: 趋势领头羊 ($\text{Beta } 1.6$) $\rightarrow$ 等待 15min 动能触发
- [ ] **300311**: 爆发点 ($\text{High Alpha}$) $\rightarrow$ 监控 Order Flow 异常

## 🗓️ 每日执行检查清单 (Daily Routine)
- [ ] **09:00-09:30**: 财联社/X 情报 $\rightarrow$ 行业方向研判
- [ ] **盘中**: 每 15 分钟扫描一次量化因子 $\rightarrow$ 订单流对齐
- [ ] **16:00**: 深度复盘 $\rightarrow$ 利润转移 $\rightarrow$ 更新 `KNOWLEDGE_BASE.md`

---
**快捷指令**: 
- 查看详细状态 $\rightarrow$ `Read TRADING_LOG.json`
- 修改交易逻辑 $\rightarrow$ `Edit KNOWLEDGE_BASE.md`
