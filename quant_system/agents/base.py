#!/usr/bin/env python3
"""
Agent 基类 — LLM调用 + 结构化JSON解析 + Schema校验
"""

import json
import re
from typing import Optional


class ResearchAgent:
    """所有研究Agent的基类"""

    model: str = "deepseek-chat"
    system_prompt: str = ""
    output_schema: dict = {}

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.deepseek.com/v1"

    def run(self, **context) -> dict:
        """主流程: LLM调用 → JSON解析 → Schema校验"""
        raw = self._call_llm(context)
        parsed = self._parse_json(raw)
        return self._validate(parsed)

    def _call_llm(self, context: dict) -> str:
        """调用 LLM API"""
        import requests

        user_content = json.dumps(context, ensure_ascii=False, indent=2)

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=60,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _parse_json(self, raw: str) -> dict:
        """从 LLM 输出中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # 尝试 ```json ... ``` 包裹
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {"_raw": raw, "_error": "JSON解析失败"}

    def _validate(self, data: dict) -> dict:
        """按 output_schema 校验输出"""
        if not self.output_schema:
            return data
        validated = {}
        for key, spec in self.output_schema.items():
            if key in data:
                validated[key] = data[key]
            else:
                validated[key] = spec.get("default", None)
        return validated
