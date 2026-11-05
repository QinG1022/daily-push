"""可选：用大模型给当天要闻写一句总结。

任何 OpenAI 兼容接口都能用（DeepSeek / 通义 / Moonshot / 本地 Ollama…），
只要配 LLM_BASE_URL + LLM_API_KEY + LLM_MODEL。
"""

from __future__ import annotations

from . import http
from .config import LlmConfig

SYSTEM_PROMPT = (
    "你是一名克制、准确的科技新闻编辑。用一句中文概括今天科技圈的重点，"
    "不超过 55 个字，不要标题、不要营销腔、不要感叹号堆砌。只输出这一句话。"
)


def summarize(cfg: LlmConfig, headlines: list[str], weather_hint: str = "") -> str:
    if not headlines:
        return ""
    body = "\n".join(f"- {h}" for h in headlines)
    user = f"今日要闻标题：\n{body}\n\n{weather_hint}\n请给出一句概括。"
    try:
        data = http.post_json(
            f"{cfg.base_url}/chat/completions",
            {
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.4,
                "max_tokens": 160,
                "stream": False,
            },
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            timeout=cfg.timeout,
        )
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        text = (text or "").strip().strip("“”\"'").replace("\n", " ")
        return text[:120]
    except Exception as exc:
        print(f"[llm] 总结生成失败，跳过：{exc}")
        return ""
