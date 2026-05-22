# Skill: Information Channel Monitoring (信息渠道监控)

## Description
Ability to actively monitor and synthesize critical financial and macro-economic information from high-signal channels to support quantitative strategy and decision making.

## Priority Channels
- **财联社 (Cailian Press)**: Primary source for real-time domestic policy, corporate news, and market-moving flashes.
- **金十数据 (Jin10)**: Primary source for global macro data, FX/Commodity volatility, and international central bank movements.
- **X (formerly Twitter)**: Primary source for global alpha, "finwit" sentiment, breaking news from key influencers, and real-time global narrative shifts.

## Execution Logic
1. **Signal Extraction**: Filter noise from these channels to identify "high-conviction" events (e.g., unexpected policy shifts, black swan events).
2. **Cross-Verification**: Cross-reference a flash from 财联社 with global macro movements on 金十数据 and sentiment on X to determine the impact radius.
3. **Impact Analysis**: Translate the information into potential market impact (e.g., "Hawkish Fed signal $\rightarrow$ USD $\uparrow$ $\rightarrow$ Equities $\downarrow$").
4. **Integration**: Feed the synthesized insight into the Quant Intelligence layer for strategy adjustment.

## Output Requirements
- Concise, time-stamped summaries.
- Source attribution (e.g., [财联社], [金十], [X]).
- Suggested action or observation for the Quant Strategist.
