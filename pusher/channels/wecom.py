"""企业微信群机器人 Webhook。

个人可以注册一个「企业微信」（无需营业执照），建个群加机器人就能收；
还能在手机企业微信里把消息同步到微信（消息 → 微信插件）。
"""

from __future__ import annotations

from .. import http
from ..config import Config
from ..render import Digest, render_markdown

NAME = "wecom"
LABEL = "企业微信机器人"

# 企业微信 markdown 上限 4096 字节
MAX_BYTES = 3800


def _trim_bytes(text: str, limit: int = MAX_BYTES) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", "ignore") + "\n\n…（内容过长已截断）"


def send(digest: Digest, cfg: Config) -> str:
    if not cfg.wecom_webhook:
        raise RuntimeError("未配置 WECOM_WEBHOOK")
    content = _trim_bytes(render_markdown(digest))
    data = http.post_json(
        cfg.wecom_webhook,
        {"msgtype": "markdown", "markdown": {"content": content}},
        timeout=25,
    )
    if data.get("errcode") != 0:
        raise RuntimeError(f"企业微信返回失败: {data}")
    return "已发送到群机器人"
