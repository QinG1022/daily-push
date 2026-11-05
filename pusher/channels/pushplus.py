"""PushPlus（推送加）—— 微信扫码关注公众号即可收，免费每天 200 条。"""

from __future__ import annotations

from .. import http
from ..config import Config
from ..render import Digest, render_markdown

NAME = "pushplus"
LABEL = "PushPlus"


def send(digest: Digest, cfg: Config) -> str:
    if not cfg.pushplus_token:
        raise RuntimeError("未配置 PUSHPLUS_TOKEN")
    data = http.post_json(
        "https://www.pushplus.plus/send",
        {
            "token": cfg.pushplus_token,
            "title": digest.title,
            "content": render_markdown(digest),
            "template": "markdown",
        },
        timeout=25,
    )
    if data.get("code") != 200:
        raise RuntimeError(f"PushPlus 返回失败: {data}")
    return "已提交（在微信「pushplus 推送加」里查看）"
