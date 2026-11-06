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

# 只放实测能稳定解析的源（36氪/品玩/机器之心/观察者网的 feed 会返回坏 XML 或 HTML）
SOURCES: dict[str, tuple[str, str]] = {
    "ithome": ("IT之家", "https://www.ithome.com/rss/"),
    "ifanr": ("爱范儿", "https://www.ifanr.com/feed"),
    "sspai": ("少数派", "https://sspai.com/feed"),
    "solidot": ("Solidot", "https://www.solidot.org/index.rss"),
    "geekpark": ("极客公园", "https://www.geekpark.net/rss"),
    "tmtpost": ("钛媒体", "https://www.tmtpost.com/rss"),
    "jiemian": ("界面新闻", "https://a.jiemian.com/index.php?m=article&a=rss"),
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
# 评论连载（「（上篇）」这种）不是新闻，别占要闻位
SERIAL_HINTS = ("（上篇）", "（下篇）", "（上）", "（下）", "（一）", "（二）", "（三）", "连载", "系列报道")
# 活动预告/人事/辟谣这类，不是新闻
EVENT_HINTS = (
    "报名", "议程", "嘉宾", "预告", "揭晓", "邀请函", "征集", "招募",
    "面对面", "圆桌", "沙龙", "誓师", "授旗", "启动仪式", "开幕致辞",
)
LOW_VALUE_HINTS = ("公关", "任命", "履新", "招聘", "诈骗", "辟谣", "澄清", "律师函")
# 纯 A 股/美股行情类，和科技早报无关
FINANCE_HINTS = (
    "股价", "涨停", "跌停", "预增", "减持", "定增", "股东", "增持", "回购",
    "重挫", "跌逾", "涨逾", "收涨", "收跌", "跌超", "涨超", "指数", "个股",
    "板块", "市值", "财报", "净利", "营收",
)
# 同一品牌最多占几条，避免整版都是「苹果又发新机」
BRANDS = (
    # 手机/消费电子
    "苹果", "mac", "imac", "macbook", "ipad", "iphone",
    "华为", "荣耀", "小米", "红米", "redmi", "oppo", "vivo", "一加",
    "realme", "iqoo", "魅族", "努比亚", "中兴", "摩托罗拉", "三星", "索尼",
    "联想", "戴尔", "华硕",
    # 芯片与互联网
    "英伟达", "nvidia", "特斯拉", "openai", "谷歌", "google", "微软",
    "字节", "腾讯", "阿里", "meta",
)


def _keyword_score(title: str) -> float:
    lowered = title.lower()
    total = 0.0
    for word, weight in INTEREST.items():
        if word in lowered:
            total += weight
    # 关键词只做微调：压缩到 0~3 分，避免一条旧闻靠堆热词压过最新消息
    return min(total * 0.5, 3.0)


def _quality_penalty(title: str) -> float:
    """压一压「日报/盘点/评论连载/股闻」这类不该进早报的内容。"""
    penalty = 0.0
    if len(title) > 55:
        penalty -= 2.0
    if any(hint in title for hint in ROUNDUP_HINTS):
        penalty -= 1.5
    if any(hint in title for hint in SERIAL_HINTS):
        penalty -= 1.5
    if any(hint in title for hint in FINANCE_HINTS):
        penalty -= 2.5
    if any(hint in title for hint in EVENT_HINTS):
        penalty -= 2.0
    if any(hint in title for hint in LOW_VALUE_HINTS):
        penalty -= 2.0
    if title.count("；") >= 2 or title.count("｜") >= 1:
        penalty -= 1.0
    return penalty


def _is_market_noise(title: str) -> bool:
    """股市行情类：涨跌、指数点位、中概股这些，和科技早报无关。"""
    if "指数" in title and ("涨" in title or "跌" in title):
        return True
    if any(k in title for k in ("美股", "港股", "A股", "中概股", "纳斯达克指数")):
        return True
    if any(k in title for k in ("个股", "板块", "涨停", "跌停")):
        return True
    return False


def _brand_of(title: str) -> str:
    """粗判品牌，用来限制同一家公司刷屏。"""
    lowered = title.lower()
    for brand in BRANDS:
        if brand.lower() in lowered:
            return brand.lower()
    return ""


# --------------------------------------------------------------------------- #
# 分类：按品类配额选稿
# --------------------------------------------------------------------------- #
GAME_KEYS = (
    "游戏", "steam", "epic", "playstation", "ps5", "psn", "switch", "任天堂",
    "xbox", "电竞", "主机", "掌机", "手游", "原神", "米哈游", "育碧", "暴雪",
)
AI_KEYS = (
    "openai", "chatgpt", "deepseek", "claude", "anthropic", "gemini", "gpt",
    "大模型", "模型", "人工智能", "智能体", "llm", "llama", "sora", "通义",
    "文心", "豆包", "kimi", "智谱", "月之暗面", "copilot", "生成式",
)
PHONE_KEYS = (
    "苹果", "iphone", "ipad", "macbook", "imac", "airpods", "华为", "小米",
    "三星", "荣耀", "oppo", "vivo", "一加", "realme", "iqoo", "魅族", "红米",
    "手机", "折叠屏", "骁龙", "天玑", "鸿蒙", "ios", "android", "平板",
)
# 手机类必须「品牌 + 产品/动作词」双命中，否则「小米成立公关部」也会被算成手机新闻
PHONE_BRAND_WORDS = (
    "苹果", "iphone", "ipad", "华为", "小米", "红米", "redmi", "oppo", "vivo",
    "一加", "realme", "iqoo", "魅族", "荣耀", "三星", "努比亚", "中兴", "摩托罗拉",
)
PHONE_PRODUCT_KEYS = (
    "手机", "新机", "中端机", "旗舰机", "开模", "真机", "上手", "开售", "售价",
    "元起", "国补", "机型", "折叠屏", "平板", "macbook", "imac", "airpods",
    "耳机", "手表", "手环", "发布", "曝光", "亮相", "屏幕", "影像", "续航",
    "芯片", "处理器", "配色", "按键", "按钮",
)
PHONE_NEGATIVE = ("机器人", "智能体", "自动驾驶", "汽车", "大模型", "远程", "云服务")
# 半导体 / 芯片：制程、设备、厂商，不含「骁龙/天玑」这类手机 SoC（那些归手机）
CHIP_KEYS = (
    "芯片", "半导体", "晶圆", "光刻", "制程", "台积电", "中芯", "英伟达",
    "nvidia", "amd", "高通", "联发科", "arm", "dram", "nand", "gpu", "soc",
    "封装", "存储器", "代工", "显卡", "算力芯片", "3nm", "2nm", "5nm",
)
# 汽车：整车 / 智驾 / 座舱（电池、光伏这些归「新能源」）
AUTO_KEYS = (
    "汽车", "特斯拉", "比亚迪", "蔚来", "小鹏", "理想汽车", "问界", "智界",
    "极氪", "零跑", "哪吒", "自动驾驶", "智驾", "车机", "增程", "纯电", "混动",
    "车企", "整车", "座舱", "新车", "小米汽车", "鸿蒙智行",
)
# 新能源：只在能源侧，不收整车
ENERGY_KEYS = (
    "新能源", "光伏", "储能", "锂电", "固态电池", "电池", "风电", "氢能",
    "充电桩", "电网", "碳中和", "宁德时代", "太阳能", "核电", "特高压",
)
INTL_KEYS = (
    "欧盟", "美国", "日本", "韩国", "德国", "英国", "法国", "印度", "俄罗斯",
    "白宫", "国会", "联合国", "nasa", "spacex", "欧洲", "加拿大", "巴西",
    "澳大利亚", "东南亚", "中东",
)
# 英文 "ai" 要用词边界，否则 again / said / chain 都会被误判
_AI_RE = re.compile(r"(?<![a-z])ai(?![a-z])", re.IGNORECASE)

CATEGORY_LABELS = {
    "ai": "AI 前线",
    "chip": "半导体芯片",
    "phone": "手机",
    "auto": "汽车",
    "energy": "新能源",
    "game": "游戏",
    "intl": "国际",
    "other": "其他",
}


# 同一品类里，某个品牌最多占几条；没列出的品类用默认 per_brand
BRAND_CAPS = {
    "phone": 99,   # 手机类不限品牌
}


def categorize(title: str) -> str:
    """把标题丢进一个品类。顺序即优先级，先命中的赢。

    game → ai → phone → chip → auto → energy → intl → other
    """
    lowered = title.lower()
    if any(key in lowered for key in GAME_KEYS):
        return "game"
    if _AI_RE.search(lowered) or any(key in lowered for key in AI_KEYS):
        return "ai"
    if (
        any(brand in lowered for brand in PHONE_BRAND_WORDS)
        and any(key in lowered for key in PHONE_PRODUCT_KEYS)
        and not any(neg in lowered for neg in PHONE_NEGATIVE)
    ):
        return "phone"
    if any(key in lowered for key in CHIP_KEYS):
        return "chip"
    if any(key in lowered for key in AUTO_KEYS):
        return "auto"
    if any(key in lowered for key in ENERGY_KEYS):
        return "energy"
    if any(key in lowered for key in INTL_KEYS):
        return "intl"
    return "other"


# 有些源是综合媒体，得先过一道「科技门槛」再进候选池
TECH_GATE = (
    "ai", "人工智能", "芯片", "半导体", "手机", "苹果", "华为", "小米", "三星",
    "特斯拉", "马斯克", "互联网", "软件", "数据", "算力", "机器人", "自动驾驶",
    "5g", "6g", "量子", "航天", "spacex", "openai", "英伟达", "谷歌", "微软",
    "meta", "亚马逊", "云计算", "大模型", "科技", "数码", "游戏",
)
SOURCE_GATES: dict[str, tuple[str, ...]] = {"jiemian": TECH_GATE}


def _passes_gate(item: NewsItem) -> bool:
    gate = SOURCE_GATES.get(item.source_key)
    if not gate:
        return True
    lowered = item.title.lower()
    return any(key in lowered for key in gate)


# 新鲜度：连续衰减而不是按档位切，这样「10 分钟前」一定排在「3 小时前」前面
FRESH_MAX = 5.0
FRESH_WINDOW_H = 18.0


def _freshness(age_hours: float) -> float:
    return max(0.0, FRESH_MAX * (1.0 - age_hours / FRESH_WINDOW_H))


# Epic 喜加一 / 限免：价值高、每天都有，固定加分确保它排在游戏类第一
EPIC_FREE_HINTS = ("喜加一", "免费领取", "限时免费", "免费送", "限免")


def _is_epic_free(title: str) -> bool:
    if any(hint in title for hint in EPIC_FREE_HINTS):
        return True
    lowered = title.lower()
    return "epic" in lowered and ("免费" in title or "领取" in title)


def score_items(items: list[NewsItem]) -> None:
    """打分：新鲜度（主导）+ 关键词 + 标题质量；多源共振在后面单独加。"""
    for item in items:
        item.score = (
            _freshness(item.age_hours)
            + _keyword_score(item.title)
            + _quality_penalty(item.title)
        )
        if _is_epic_free(item.title):
            item.score += 3.0


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
            item.score += min(others * 2.0, 4.0)


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
        if fresh(i)
        and not any(word in i.title for word in BLOCK)
        and not _is_market_noise(i.title)
        and _passes_gate(i)
    ]
    candidates = dedupe(candidates)
    score_items(candidates)
    _boost_cross_source(candidates)
    candidates.sort(key=lambda i: (i.score, -i.age_hours), reverse=True)
    return candidates


def pick(
    candidates: list[NewsItem],
    count: int,
    *,
    per_source: int = 3,
    per_brand: int = 2,
    fresh_hours: float = 10.0,
    fresh_ratio: float = 0.6,
) -> list[NewsItem]:
    """挑 top N。

    三条约束：
      * 单源最多 per_source 条（IT之家 一天能出 60 条，不限会霸屏）
      * 同品牌最多 per_brand 条（避免整版都是苹果新品）
      * 至少六成来自最近 fresh_hours 小时
    """
    chosen: list[NewsItem] = []
    src_count: dict[str, int] = {}
    brand_count: dict[str, int] = {}
    taken: set[int] = set()

    def take(item: NewsItem) -> bool:
        if id(item) in taken:
            return False
        if src_count.get(item.source_key, 0) >= per_source:
            return False
        brand = _brand_of(item.title)
        if brand and brand_count.get(brand, 0) >= per_brand:
            return False
        chosen.append(item)
        taken.add(id(item))
        src_count[item.source_key] = src_count.get(item.source_key, 0) + 1
        if brand:
            brand_count[brand] = brand_count.get(brand, 0) + 1
        return True

    # 第一轮：最近 fresh_hours 小时内的，按分数优先占住名额
    need_fresh = max(1, int(round(count * fresh_ratio)))
    for item in candidates:
        if len(chosen) >= need_fresh:
            break
        if item.age_hours <= fresh_hours:
            take(item)

    # 第二轮：剩下的按总分补满（含第一轮没凑够的情况）
    for item in candidates:
        if len(chosen) >= count:
            break
        take(item)

    return chosen[:count]


def pick_mixed(
    candidates: list[NewsItem],
    total: int,
    mix: list[tuple[str, int]],
    *,
    per_source: int = 5,
    per_brand: int = 3,
) -> list[NewsItem]:
    """按品类配额选稿，例如 ai:3 / phone:3 / game:1 / intl:2 / other:1。

    每个品类内部按分数取（分数由新鲜度主导），配额没填满时用全局高分补齐。
    """
    if not mix:
        return pick(candidates, total)

    buckets: dict[str, list[NewsItem]] = {}
    for item in candidates:
        buckets.setdefault(categorize(item.title), []).append(item)

    chosen: list[NewsItem] = []
    taken: set[int] = set()
    src_count: dict[str, int] = {}
    brand_count: dict[tuple[str, str], int] = {}

    def take(item: NewsItem, cat: str, source_cap: int, brand_cap: int) -> bool:
        if id(item) in taken:
            return False
        # source_cap = 0 表示这一轮不限来源
        if source_cap and src_count.get(item.source_key, 0) >= source_cap:
            return False
        brand = _brand_of(item.title)
        if brand and brand_count.get((cat, brand), 0) >= brand_cap:
            return False
        chosen.append(item)
        taken.add(id(item))
        src_count[item.source_key] = src_count.get(item.source_key, 0) + 1
        if brand:
            brand_count[(cat, brand)] = brand_count.get((cat, brand), 0) + 1
        return True

    # Epic 喜加一保底：无视来源上限，先占一个位置
    pinned: dict[str, int] = {}
    for item in candidates:
        if _is_epic_free(item.title) and take(item, "game", 0, per_brand):
            pinned["game"] = pinned.get("game", 0) + 1
            break

    # Epic 是「额外一条」，不挤占品类配额：有就多一条，没有就是原定条数
    limit = total + sum(pinned.values())

    # 配额阶段给来源留一个宽松上限：既不卡死品类，也不让 IT之家 一家占满
    quota_cap = max(per_source, int(round(total * 0.75)))
    for cat, quota in mix:
        got = pinned.get(cat, 0)
        brand_cap = BRAND_CAPS.get(cat, per_brand)
        for item in buckets.get(cat, []):
            if got >= quota or len(chosen) >= limit:
                break
            if take(item, cat, quota_cap, brand_cap):
                got += 1

    # 补位阶段才收紧来源上限；同时给每个品类一个软上限（配额 +1），
    # 免得别的板块缺货时，补位全堆到同一个品类上
    quota_of = dict(mix)
    cat_taken: dict[str, int] = {}
    for picked_item in chosen:
        c = categorize(picked_item.title)
        cat_taken[c] = cat_taken.get(c, 0) + 1

    for item in candidates:
        if len(chosen) >= limit:
            break
        cat = categorize(item.title)
        cap = quota_of.get(cat)
        if cap is not None and cat_taken.get(cat, 0) >= cap + 1:
            continue
        if take(item, cat, per_source, BRAND_CAPS.get(cat, per_brand)):
            cat_taken[cat] = cat_taken.get(cat, 0) + 1

    chosen.sort(key=lambda i: (i.score, -i.age_hours), reverse=True)
    return chosen[:limit]
