"""PushPlus（推送加）—— 微信里「pushplus 推送加」服务号收消息。

注意：2024-08-01 起，未实名的账号无法调用发送接口，必须先做实名认证。
额度：微信渠道实名用户每天 200 次请求以内正常推送，超出当天停推。
"""

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
