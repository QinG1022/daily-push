"""联网补充：用 DeepSeek Search API 找 RSS 没覆盖到的热点。

关键点：**链接一律取搜索结果里的 url**，不让模型生成，
所以不会出现"点开 404"的情况。

接口文档：https://api-docs.deepseek.com/zh-cn/guides/search
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from . import http
from .config import Config

# 每个板块一条查询，只有出现在 NEWS_MIX 里的板块才会查
QUERIES: dict[str, str] = {
    "ai": "AI 大模型 发布 融资",
    "chip": "半导体 芯片 制程 新品",
    "phone": "手机 新品 发布 开售",
    "auto": "汽车 智能驾驶 新车 发布",
    "energy": "新能源 电池 光伏 储能",
}

# 搜索结果的质量门槛：权威性 0~4，rerank 0~3（≥1.5 为优质）
MIN_AUTHORITY = 2
MIN_RERANK = 1.5


@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""
    site: str = ""
    published: datetime | None = None
    authority: int = -1
    rerank: float = 0.0

    def age_text(self) -> str:
        if not self.published:
            return ""
        hours = (datetime.now(timezone.utc) - self.published).total_seconds() / 3600
        if hours < 0:
            return ""
        if hours < 1:
            return "刚刚"
        if hours < 24:
            return f"{int(hours)}小时前"
        return f"{int(hours // 24)}天前"

    def meta(self) -> str:
        bits = [b for b in (self.site, self.age_text()) if b]
        return " · ".join(bits)


def _parse_date(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    text = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalize(url: str) -> str:
    return url.split("?")[0].rstrip("/")


def search_once(cfg: Config, query: str, count: int = 8) -> list[Hit]:
    """调一次 Search 接口，返回候选。"""
    data = http.post_json(
        f"{cfg.search_base}/v1/tools/search",
        {"query": query, "count": count, "need_content": False},
        headers={"Authorization": f"Bearer {cfg.search_key}"},
        timeout=25,
        retries=1,
    )
    hits: list[Hit] = []
    for row in data.get("results") or []:
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        if not url or not title:
            continue
        authority = row.get("authority")
        hits.append(
            Hit(
                title=title,
                url=url,
                snippet=(row.get("snippet") or "").strip(),
                site=(row.get("site_name") or "").strip(),
                published=_parse_date(row.get("date")),
                authority=int(authority) if isinstance(authority, int) else -1,
                rerank=float(row.get("rerank_score") or 0),
            )
        )
    return hits


def _accept(hit: Hit, seen: set[str]) -> bool:
    key = _normalize(hit.url)
    if key in seen:
        return False
    if hit.authority >= 0 and hit.authority < MIN_AUTHORITY:
        return False
    if hit.rerank and hit.rerank < MIN_RERANK:
        return False
    return True


def fill_section(
    cfg: Config, category: str, existing_links: Iterable[str], need: int
) -> list[Hit]:
    """某个板块缺货时，按该板块的关键词搜一次，返回补得上的条目。"""
    query = QUERIES.get(category)
    if not cfg.search_key or need <= 0 or not query:
        return []

    seen = {_normalize(link) for link in existing_links}
    try:
        hits = search_once(cfg, query)
    except Exception as exc:
        print(f"[search] {category} 查询失败：{exc}")
        return []

    picked: list[Hit] = []
    for hit in hits:
        if len(picked) >= need:
            break
        if _accept(hit, seen):
            seen.add(_normalize(hit.url))
            picked.append(hit)
    return picked


EPIC_QUERY = "Epic 喜加一 免费游戏 本周"
_EPIC_HINTS = ("喜加一", "免费领取", "限时免费", "免费送", "限免")


def _looks_epic(title: str) -> bool:
    if any(hint in title for hint in _EPIC_HINTS):
        return True
    lowered = title.lower()
    return "epic" in lowered and ("免费" in title or "领取" in title)


def find_epic(cfg: Config, existing_links: Iterable[str]) -> Hit | None:
    """单独搜一条 Epic 喜加一，只在下午那次调用。"""
    if not cfg.search_key:
        return None
    seen = {_normalize(link) for link in existing_links}
    try:
        hits = search_once(cfg, EPIC_QUERY, count=10)
    except Exception as exc:
        print(f"[search] Epic 查询失败：{exc}")
        return None
    for hit in hits:
        if _looks_epic(hit.title) and _accept(hit, seen):
            return hit
    return None
