"""科技新闻：抓多个 RSS，清洗、去重、按「热度 + 新鲜度 + 兴趣」排序。"""

from __future__ import annotations

import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Iterable

from . import http
from .config import Config

# 只放实测能稳定解析的源（36氪/品玩/机器之心的 feed 会返回坏 XML 或 HTML）
SOURCES: dict[str, tuple[str, str]] = {
    "ithome": ("IT之家", "https://www.ithome.com/rss/"),
    "ifanr": ("爱范儿", "https://www.ifanr.com/feed"),
    "sspai": ("少数派", "https://sspai.com/feed"),
    "solidot": ("Solidot", "https://www.solidot.org/index.rss"),
    "geekpark": ("极客公园", "https://www.geekpark.net/rss"),
    "tmtpost": ("钛媒体", "https://www.tmtpost.com/rss"),
}

# 关键词加权：命中越多越可能进 top N
INTEREST: dict[str, float] = {
    "ai": 2.5, "人工智能": 2.5, "大模型": 3.0, "chatgpt": 2.0, "openai": 2.5,
    "deepseek": 3.0, "gemini": 2.0, "claude": 2.0, "智能体": 2.0, "agent": 1.5,
    "芯片": 2.0, "半导体": 2.0, "英伟达": 2.5, "nvidia": 2.5, "台积电": 2.0,
    "苹果": 1.5, "iphone": 1.5, "华为": 1.5, "小米": 1.2, "特斯拉": 1.5,
    "开源": 1.2, "linux": 1.0, "机器人": 1.8, "自动驾驶": 1.8, "航天": 1.5,
    "spacex": 1.8, "量子": 1.5, "安全": 1.0, "漏洞": 1.0, "裁员": 1.2,
}

# 明显不该出现在科技早报里的
BLOCK: tuple[str, ...] = ("招聘", "抽奖", "优惠券", "限时秒杀", "广告")

_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_KEEP = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


@dataclass
class NewsItem:
    title: str
    link: str
    source_key: str
    source_name: str
    published: datetime | None = None
    summary: str = ""
    score: float = 0.0

    @property
    def age_hours(self) -> float:
        if not self.published:
            return 12.0
        now = datetime.now(timezone.utc)
        return max(0.0, (now - self.published).total_seconds() / 3600)

    def age_text(self) -> str:
        h = self.age_hours
        if h < 1:
            return "刚刚"
        if h < 24:
            return f"{int(h)}小时前"
        return f"{int(h // 24)}天前"

    def clean_title(self) -> str:
        return _WS.sub(" ", self.title).strip()


def _clean_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(_HTML_TAG.sub(" ", raw))
    return _WS.sub(" ", text).strip()


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    # RFC 822: Thu, 05 Nov 2026 12:00:00 +0800
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _text_of(node: ET.Element, *names: str) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text
        # 带命名空间的写法
        for tag in (f"{{http://www.w3.org/2005/Atom}}{name}", f"{{http://purl.org/dc/elements/1.1/}}{name}"):
            child = node.find(tag)
            if child is not None and child.text:
                return child.text
    return ""


def parse_feed(raw: bytes, source_key: str) -> list[NewsItem]:
    """解析 RSS 2.0 / Atom，返回条目（时间可能为 None）。"""
    name = SOURCES.get(source_key, (source_key, ""))[0]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RuntimeError(f"{source_key} feed 解析失败: {exc}") from exc

    items: list[NewsItem] = []
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for node in nodes:
        title = _clean_text(_text_of(node, "title"))
        link = _text_of(node, "link")
        if not link:
            link_node = node.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                link = link_node.get("href") or ""
        if not title or not link:
            continue
        published = _parse_time(_text_of(node, "pubDate", "published", "updated", "date"))
        summary = _clean_text(_text_of(node, "description", "summary", "encoded"))[:160]
        items.append(
            NewsItem(
                title=title,
                link=link.strip(),
                source_key=source_key,
                source_name=name,
                published=published,
                summary=summary,
            )
        )
    return items


def normalize(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).lower()
    return _KEEP.sub("", text)


def _similar(a: str, b: str, threshold: float = 0.82) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if a.startswith(b) or b.startswith(a):
        shorter = min(len(a), len(b))
        if shorter >= 8:
            return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    """同一件事多家都报时只留一条（保留先出现的）。"""
    kept: list[NewsItem] = []
    seen_links: set[str] = set()
    for item in items:
        link = item.link.split("?")[0].rstrip("/")
        if link in seen_links:
            continue
        norm = normalize(item.title)
        if any(_similar(norm, normalize(k.title)) for k in kept):
            continue
        seen_links.add(link)
        kept.append(item)
    return kept


ROUNDUP_HINTS = ("早知道", "早报", "晚报", "午报", "周报", "日报", "盘点", "汇总", "合集", "一周")


def _keyword_score(title: str) -> float:
    lowered = title.lower()
    total = 0.0
    for word, weight in INTEREST.items():
        if word in lowered:
            total += weight
    return min(total, 6.0)


def _quality_penalty(title: str) -> float:
    """压一压「日报/盘点」这类大杂烩和超长标题。"""
    penalty = 0.0
    if len(title) > 55:
        penalty -= 2.0
    if any(hint in title for hint in ROUNDUP_HINTS):
        penalty -= 1.5
    if title.count("；") >= 2 or title.count("｜") >= 1:
        penalty -= 1.0
    return penalty


def score_items(items: list[NewsItem]) -> None:
    """打分：新鲜度 + 兴趣 + 标题质量。"""
    for item in items:
        age = item.age_hours
        if age <= 4:
            freshness = 3.0
        elif age <= 10:
            freshness = 2.0
        elif age <= 20:
            freshness = 1.0
        else:
            freshness = 0.0
        item.score = freshness + _keyword_score(item.title) + _quality_penalty(item.title)


def _boost_cross_source(items: list[NewsItem]) -> None:
    """粗略的「多源共振」：标题里出现高度相似的另一条，加分。"""
    norms = [normalize(i.title) for i in items]
    for idx, item in enumerate(items):
        others = 0
        for jdx, other in enumerate(norms):
            if idx == jdx or items[idx].source_key == items[jdx].source_key:
                continue
            if _similar(norms[idx], other, 0.6):
                others += 1
        if others:
            item.score += min(others * 1.5, 4.0)


def collect(cfg: Config, *, now: datetime | None = None) -> list[NewsItem]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=cfg.news_lookback_hours)

    pool: list[NewsItem] = []
    errors: list[str] = []
    for key in cfg.news_sources:
        if key not in SOURCES:
            errors.append(f"{key}: 未知新闻源，可用 {', '.join(SOURCES)}")
            continue
        url = SOURCES[key][1]
        try:
            raw = http.request(url, timeout=20)
            pool.extend(parse_feed(raw, key))
        except Exception as exc:
            errors.append(f"{key}: {exc}")

    if errors:
        print("[news] 部分源抓取失败：" + " | ".join(errors))

    # 时间过滤（没有时间的条目保留，很多站不提供 pubDate）
    def fresh(item: NewsItem) -> bool:
        if item.published is None:
            return True
        return item.published >= cutoff

    candidates = [
        i for i in pool
        if fresh(i) and not any(word in i.title for word in BLOCK)
    ]
    candidates = dedupe(candidates)
    score_items(candidates)
    _boost_cross_source(candidates)
    candidates.sort(key=lambda i: (i.score, -i.age_hours), reverse=True)
    return candidates


def pick(candidates: list[NewsItem], count: int, *, per_source: int = 2) -> list[NewsItem]:
    """挑 top N，同时保证来源多样性（单源最多 per_source 条）。"""
    chosen: list[NewsItem] = []
    counter: dict[str, int] = {}
    for item in candidates:
        if len(chosen) >= count:
            break
        if counter.get(item.source_key, 0) >= per_source:
            continue
        counter[item.source_key] = counter.get(item.source_key, 0) + 1
        chosen.append(item)
    # 不够就用剩下的补齐
    if len(chosen) < count:
        for item in candidates:
            if len(chosen) >= count:
                break
            if item not in chosen:
                chosen.append(item)
    return chosen
