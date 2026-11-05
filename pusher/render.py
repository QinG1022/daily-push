"""把抓到的数据渲染成不同渠道能用的样子。

三种形态：
  render_markdown —— 邮件 / Server酱 / PushPlus / 企业微信（支持链接）
  compact_fields  —— 公众号模板消息（纯文本、每字段 ≤100 字）
  render_html     —— 邮件正文
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape

from .extras import Extra
from .news import NewsItem
from .weather import Weather, format_forecast_lines

SLOT_TITLES = {
    "morning": "早间科技速递",
    "noon": "午间科技速递",
    "evening": "晚间科技速递",
}
WEEKDAYS = "一二三四五六日"

# 公众号模板消息单字段上限约 120 字，留点余量
WX_FIELD_LIMIT = 100


@dataclass
class Digest:
    generated: datetime
    slot: str
    city: str
    weather: Weather | None = None
    news: list[NewsItem] = field(default_factory=list)
    extras: list[Extra] = field(default_factory=list)
    ai: str = ""
    lookback_hours: float = 24.0
    # --test 时直接给定字段，跳过正常渲染
    raw_fields: dict[str, str] | None = None

    # ------------------------------------------------------------------ #
    @property
    def local(self) -> datetime:
        return self.generated

    @property
    def date_text(self) -> str:
        return f"{self.local.month}月{self.local.day}日 周{WEEKDAYS[self.local.weekday()]}"

    @property
    def title(self) -> str:
        return f"{self.local.month}月{self.local.day}日 {SLOT_TITLES.get(self.slot, '科技速递')}"

    @property
    def full_title(self) -> str:
        return f"{self.date_text} · {SLOT_TITLES.get(self.slot, '科技速递')}"

    def tips(self) -> list[str]:
        return self.weather.tips() if self.weather else []

    def extra_of(self, kind: str) -> list[Extra]:
        return [e for e in self.extras if e.kind == kind]


def truncate(text: str, limit: int = WX_FIELD_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _news_line(item: NewsItem, idx: int, *, with_link: bool) -> str:
    head = f"{idx}. {item.clean_title()}"
    meta = f"{item.source_name} · {item.age_text()}"
    if with_link:
        return f"{head} — {meta}\n   {item.link}"
    return f"{head}（{item.source_name}）"


# --------------------------------------------------------------------------- #
# Markdown（邮件 / 推送服务）
# --------------------------------------------------------------------------- #
def render_markdown(d: Digest) -> str:
    lines: list[str] = [f"## {d.full_title}", ""]

    if d.weather:
        w = d.weather
        t = w.today
        if t:
            lines.append(f"**{w.city}** {t.emoji} {t.text}　{t.range_text}　降水 {t.pop}%")
        else:
            lines.append(f"**{w.city}** {w.now_emoji} {w.now_text}　{w.current_temp:.0f}℃")
        lines.append(w.comfort_line())
        fc = format_forecast_lines(w, limit=3)
        if fc:
            lines.append("")
            lines.append("　".join(fc))
    else:
        lines.append("_天气数据暂不可用_")
    lines.append("")

    if d.news:
        lines.append(f"### 📰 近 {d.lookback_hours:.0f} 小时要闻")
        for idx, item in enumerate(d.news, 1):
            lines.append(_news_line(item, idx, with_link=True))
        lines.append("")
    else:
        lines.append("_暂时没抓到符合条件的新闻_")
        lines.append("")

    tips = d.tips()
    if tips:
        lines.append("### 🧥 出门提示")
        lines.extend(f"- {t}" for t in tips)
        lines.append("")

    if d.ai:
        lines.append("### 🎯 一句话")
        lines.append(d.ai)
        lines.append("")

    quotes = d.extra_of("quote")
    if quotes:
        lines.append(f"> {quotes[0].text}")
        lines.append("")

    marks = d.extra_of("countdown")
    if marks:
        lines.append("### 🗓 倒数日")
        lines.extend(f"- {m.text}" for m in marks)
        lines.append("")

    fx = d.extra_of("fx")
    if fx:
        lines.append("### 💱 汇率")
        lines.append("　".join(e.text for e in fx))
        lines.append("")

    lines.append("---")
    lines.append(f"由 daily-push 生成 · {d.local:%Y-%m-%d %H:%M}")
    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------- #
# 纯文本（QQ / 短信 / 企业微信 text）
# --------------------------------------------------------------------------- #
def render_plain(d: Digest) -> str:
    lines = [d.full_title, "=" * 30, ""]
    if d.weather:
        w = d.weather
        lines.append(f"{w.city}｜{w.comfort_line()}")
        lines.extend(format_forecast_lines(w))
        lines.append("")
    if d.news:
        lines.append(f"【近 {d.lookback_hours:.0f} 小时要闻】")
        for idx, item in enumerate(d.news, 1):
            lines.append(f"{idx}. {item.clean_title()}（{item.source_name} · {item.age_text()}）")
            lines.append(f"   {item.link}")
        lines.append("")
    if d.ai:
        lines.extend(["【一句话】", d.ai, ""])
    for tip in d.tips():
        lines.append(f"· {tip}")
    for e in d.extras:
        if e.kind in ("countdown", "fx"):
            lines.append(f"· {e.text}")
    lines.append("")
    lines.append(f"daily-push · {d.local:%m-%d %H:%M}")
    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------- #
# HTML（邮件）
# --------------------------------------------------------------------------- #
def render_html(d: Digest) -> str:
    def section(title: str, body: str) -> str:
        return (
            f'<h3 style="margin:22px 0 8px;font-size:15px;color:#111;'
            f'border-left:3px solid #2f7cf6;padding-left:8px">{title}</h3>{body}'
        )

    parts: list[str] = [
        '<meta charset="utf-8">',
        '<div style="max-width:640px;margin:0 auto;padding:24px 20px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;'
        'font-size:14px;line-height:1.7;color:#333;background:#fff">',
        f'<h2 style="margin:0 0 4px;font-size:20px;color:#111">{escape(d.full_title)}</h2>',
        f'<div style="color:#999;font-size:12px">生成于 {d.local:%Y-%m-%d %H:%M}</div>',
    ]

    if d.weather:
        w = d.weather
        t = w.today
        parts.append(
            '<div style="margin-top:18px;padding:14px 16px;background:#f5f8ff;border-radius:10px">'
            f'<div style="font-size:16px;font-weight:600">{escape(w.city)}　{w.now_emoji} {escape(w.now_text)}'
            f'　{escape(t.range_text) if t else ""}　降水 {t.pop if t else 0}%</div>'
            f'<div style="color:#666;margin-top:6px">{escape(w.comfort_line())}</div>'
            f'<div style="color:#666;margin-top:4px">{escape("　".join(format_forecast_lines(w)))}</div>'
            "</div>"
        )
    else:
        parts.append('<p style="color:#999">天气数据暂不可用</p>')

    if d.news:
        items = "".join(
            f'<li style="margin:8px 0"><a href="{escape(i.link)}" style="color:#1a5fd0;text-decoration:none">'
            f"{escape(i.clean_title())}</a>"
            f'<span style="color:#999;font-size:12px"> — {escape(i.source_name)} · {escape(i.age_text())}</span></li>'
            for i in d.news
        )
        parts.append(section(f"📰 近 {d.lookback_hours:.0f} 小时要闻", f'<ol style="padding-left:22px;margin:0">{items}</ol>'))
    else:
        parts.append(section("📰 要闻", '<p style="color:#999">暂时没抓到符合条件的新闻</p>'))

    if d.ai:
        parts.append(
            section("🎯 一句话", f'<div style="padding:12px 14px;background:#fffaf0;border-radius:8px">{escape(d.ai)}</div>')
        )

    tips = d.tips()
    if tips:
        parts.append(section("🧥 出门提示", "<ul style=\"padding-left:20px;margin:0\">" + "".join(
            f"<li style=\"margin:4px 0\">{escape(t)}</li>" for t in tips
        ) + "</ul>"))

    marks = d.extra_of("countdown") + d.extra_of("fx")
    if marks:
        parts.append(section("🗓 其他", "".join(f'<div style="color:#555">{escape(m.text)}</div>' for m in marks)))

    quotes = d.extra_of("quote")
    if quotes:
        parts.append(
            f'<div style="margin-top:22px;padding:12px 14px;border-left:3px solid #ddd;color:#777">{escape(quotes[0].text)}</div>'
        )

    parts.append('<div style="margin-top:26px;padding-top:12px;border-top:1px solid #eee;color:#aaa;font-size:12px">daily-push 自动生成</div>')
    parts.append("</div>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# 公众号模板消息字段
# --------------------------------------------------------------------------- #
def compact_fields(d: Digest) -> dict[str, str]:
    """键名与公众号模板里的 {{xxx.DATA}} 对应。"""
    if d.raw_fields is not None:
        return {k: v for k, v in d.raw_fields.items() if v}

    fields: dict[str, str] = {"title": d.title}

    w = d.weather
    if w and w.today:
        t = w.today
        tomorrow = w.days[1] if len(w.days) > 1 else None
        fields["weather"] = truncate(
            f"{w.city} {t.emoji}{t.text} {t.range_text} 降水{t.pop}%", WX_FIELD_LIMIT
        )
        tail = f" · 明天{tomorrow.emoji}{tomorrow.text} {tomorrow.range_text}" if tomorrow else ""
        fields["remark"] = truncate(
            f"现在{w.current_temp:.0f}℃ 体感{w.feels_like:.0f}℃{tail}", WX_FIELD_LIMIT
        )
    elif w:
        fields["weather"] = truncate(f"{w.city} {w.now_emoji}{w.now_text} {w.current_temp:.0f}℃")
        fields["remark"] = "天气详情暂缺"
    else:
        fields["weather"] = "天气数据暂不可用"
        fields["remark"] = ""

    # 要闻：拼到字数上限为止（公众号没有富文本，只能塞标题）
    lines: list[str] = []
    budget = WX_FIELD_LIMIT
    target = min(4, len(d.news))
    per_line = max(14, (budget - target) // target) if target else 0
    for idx, item in enumerate(d.news[:target], 1):
        prefix = f"{idx}. "
        room = max(6, per_line - len(prefix))
        title = item.clean_title()
        if len(title) > room:
            title = title[: room - 1].rstrip() + "…"
        line = prefix + title
        if len(line) + 1 > budget:
            break
        lines.append(line)
        budget -= len(line) + 1
    fields["news"] = "\n".join(lines) if lines else "今天暂无更新"

    # n1~n5 给「服务号类目模板」用：thing 类型字段上限 20 字
    for idx, item in enumerate(d.news[:5], 1):
        fields[f"n{idx}"] = truncate(item.clean_title(), 20)

    tips = d.tips()
    if tips:
        fields["tip"] = truncate("；".join(tips[:2]))
    elif d.weather:
        fields["tip"] = "天气平稳，按平常穿就好"
    else:
        fields["tip"] = "天气数据暂缺，临出门再看一眼"

    fields["ai"] = truncate(d.ai) if d.ai else ""
    return {k: v for k, v in fields.items() if v}
