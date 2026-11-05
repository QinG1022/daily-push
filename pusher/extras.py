"""附加模块：每日一句、倒数日、汇率。全部可选，失败就静默跳过。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import http


@dataclass
class Extra:
    kind: str
    label: str
    text: str


def one_sentence() -> Extra | None:
    """一言（hitokoto）—— 每天一句不一样的话。"""
    try:
        data = http.get_json("https://v1.hitokoto.cn/?encode=json&c=k", timeout=10, retries=1)
        text = (data.get("hitokoto") or "").strip()
        source = (data.get("from") or "").strip()
        if not text:
            return None
        suffix = f" —— {source}" if source else ""
        return Extra(kind="quote", label="每日一句", text=f"{text}{suffix}")
    except Exception:
        return None


def countdown(specs: list[str], tz: str = "Asia/Shanghai") -> list[Extra]:
    """倒数日。格式：`2027-01-01|元旦`，可写多组，用逗号/换行分隔。"""
    out: list[Extra] = []
    today = datetime.now(ZoneInfo(tz)).date()
    for spec in specs:
        raw = spec.strip()
        if not raw:
            continue
        target_str, _, name = raw.partition("|")
        name = (name or "目标日").strip()
        try:
            target = date.fromisoformat(target_str.strip())
        except ValueError:
            continue
        delta = (target - today).days
        if delta > 0:
            out.append(Extra(kind="countdown", label=name, text=f"距 {name} 还有 {delta} 天"))
        elif delta == 0:
            out.append(Extra(kind="countdown", label=name, text=f"今天就是 {name} 🎉"))
        elif delta >= -3:
            out.append(Extra(kind="countdown", label=name, text=f"{name} 已经过去 {-delta} 天"))
    return out


def fx_rates(pairs: list[str]) -> list[Extra]:
    """汇率（frankfurter，欧洲央行数据，免费）。格式：`USD:CNY`。"""
    out: list[Extra] = []
    for pair in pairs:
        base, _, quote = pair.partition(":")
        if not base or not quote:
            continue
        try:
            url = http.with_query(
                f"https://api.frankfurter.dev/v1/latest", {"base": base.upper(), "symbols": quote.upper()}
            )
            data = http.get_json(url, timeout=10, retries=1)
            rate = (data.get("rates") or {}).get(quote.upper())
            if rate is None:
                continue
            out.append(
                Extra(
                    kind="fx",
                    label=f"{base.upper()}/{quote.upper()}",
                    text=f"1 {base.upper()} ≈ {rate:.4f} {quote.upper()}",
                )
            )
        except Exception:
            continue
    return out
