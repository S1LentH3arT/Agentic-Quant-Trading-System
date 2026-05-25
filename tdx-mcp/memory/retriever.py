# tdx-mcp/memory/retriever.py
"""记忆检索: 按板块/评分区间/市场状态匹配历史教训"""
import os
import re


def retrieve_for_agent(
    agent_name: str,
    context: dict,
    index_path: str,
    max_items: int = 7,
) -> str:
    """
    检索相关历史教训，返回格式化的文本 (≤400 tok)。
    context 字段: sector, market_state
    """
    if not os.path.exists(index_path):
        return ""

    review_dir = os.path.join(os.path.dirname(index_path), "reviews")
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
        path_match = re.search(r'\]\(([^)]+)\)', m)
        if path_match:
            review_path = os.path.join(os.path.dirname(index_path), path_match.group(1))
            if os.path.exists(review_path):
                with open(review_path, encoding="utf-8") as f:
                    content = f.read()
                summary = content[:300].replace("\n", " ")
                results.append(f"- {summary}...")

    if not results:
        return ""

    return "## 历史经验教训\n" + "\n".join(results)
