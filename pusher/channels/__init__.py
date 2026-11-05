"""推送渠道。

每个模块暴露 NAME、LABEL 和 send(digest, cfg) -> str。
send 抛异常表示失败，返回值是一句人话的结果描述。
"""

from __future__ import annotations

from typing import Callable

from ..config import Config
from ..render import Digest
from . import mail, pushplus, serverchan, wechat_mp, wecom

MODULES = (wechat_mp, serverchan, pushplus, wecom, mail)

REGISTRY: dict[str, tuple[str, Callable[[Digest, Config], str]]] = {
    mod.NAME: (mod.LABEL, mod.send) for mod in MODULES
}


def send_all(
    cfg: Config, digest: Digest, *, only: list[str] | None = None
) -> list[tuple[str, bool, str]]:
    """依次发送到所有已配置渠道，返回 (渠道, 是否成功, 信息)。"""
    targets = only or cfg.channels
    results: list[tuple[str, bool, str]] = []
    for name in targets:
        if name not in REGISTRY:
            detail = f"未知渠道，可用：{', '.join(REGISTRY)}"
            print(f"[push] ❌ {name}: {detail}")
            results.append((name, False, detail))
            continue
        label, func = REGISTRY[name]
        try:
            detail = func(digest, cfg)
            results.append((name, True, detail))
            print(f"[push] ✅ {label}: {detail}")
        except Exception as exc:
            results.append((name, False, str(exc)))
            print(f"[push] ❌ {label}: {exc}")
    return results
