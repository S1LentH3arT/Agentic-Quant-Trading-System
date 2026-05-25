# tdx-mcp/llm/client.py
"""统一 LLM 客户端 — OpenAI SDK → DeepSeek API"""
import os
import json
from openai import OpenAI

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 15

_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=DEFAULT_TIMEOUT,
        )
    return _client


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    json_mode: bool = False,
    temperature: float = 0.2,
) -> str:
    """
    调用 LLM，返回响应文本。
    自动处理超时（不抛异常，返回降级 JSON）。
    """
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        client_obj = get_client()
        response = client_obj.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "fallback": True,
            "note": "LLM 调用失败，使用规则版结果"
        })
