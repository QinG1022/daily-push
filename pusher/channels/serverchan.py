"""Server酱（方糖）—— 推送到微信服务号「方糖」，免费额度每天 5 条左右。"""

from __future__ import annotations

import json

from .. import http
from ..config import Config
from ..render import Digest, render_markdown

NAME = "serverchan"
LABEL = "Server酱"


def send(digest: Digest, cfg: Config) -> str:
    if not cfg.serverchan_key:
        raise RuntimeError("未配置 SERVERCHAN_SENDKEY")
    url = f"https://sctapi.ftqq.com/{cfg.serverchan_key}.send"
    raw = http.post_form(
        url,
        {"title": digest.title, "desp": render_markdown(digest)},
        timeout=25,
    )
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise RuntimeError(f"返回不是 JSON: {raw[:200]!r}")
    if data.get("code") != 0:
        raise RuntimeError(f"Server酱返回失败: {data}")
    return "已提交（在微信「方糖」服务号里查看）"
