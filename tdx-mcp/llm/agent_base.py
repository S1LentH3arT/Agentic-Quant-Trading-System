# tdx-mcp/llm/agent_base.py
"""Agent 基类 — system prompt 加载 + LLM 调用 + JSON 解析 + 降级"""
import json
import os

from .client import chat


class BaseAgent:
    name: str = "base"
    model: str = "deepseek-chat"
    json_mode: bool = True

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
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 build_context(**kwargs)"
        )

    def _inject_memory(self, context: dict) -> str:
        """注入历史记忆。子类可覆盖 context 字段来控制检索关键词。"""
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from memory.retriever import retrieve_for_agent
            index_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "memory", "MEMORY.md"
            )
            return retrieve_for_agent(self.name, context, index_path)
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

        # 解析 JSON: 先检查是否降级响应, 再尝试解析
        try:
            result = json.loads(raw)
            if result.get("fallback"):
                return result
            return result
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
