#!/usr/bin/env python3
"""每天把「天气 + 科技要闻」推送到微信或邮箱。

常用命令：
    python main.py --dry-run          # 只抓数据 + 生成预览，不发送
    python main.py                    # 抓数据并发送到 PUSH_CHANNELS 里的渠道
    python main.py --test             # 发一条测试消息，验证渠道配置
    python main.py --only mail        # 只发某个渠道
    python main.py --slot morning     # 手动指定时段（默认按当前时间自动判断）
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pusher import config as config_mod
from pusher import extras as extras_mod
from pusher import llm, news, render, weather
from pusher.channels import send_all

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def _setup_stdout() -> None:
    """Windows 控制台默认 GBK，避免 emoji 直接崩掉。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def resolve_slot(raw: str, tz: str) -> str:
    if raw and raw != "auto":
        return raw
    hour = datetime.now(ZoneInfo(tz)).hour
    if hour < 11:
        return "morning"
    if hour < 15:
        return "noon"
    return "evening"


# 回看窗口跟着时段走，三次推送才不会整版重复
SLOT_WINDOWS = {
    "morning": 12.0,   # 09:00 → 覆盖前晚 21:00 至今早
    "noon": 4.0,       # 12:00 → 覆盖 08:00 至今
    "evening": 6.0,    # 18:00 → 覆盖 12:00 至今
}


def load_pool(cfg: config_mod.Config, slot: str) -> tuple[list[news.NewsItem], float]:
    """按时段窗口筛新闻；货不够就自动放宽，返回 (候选, 实际窗口小时数)。"""
    wanted = cfg.news_lookback_hours if cfg.news_lookback_hours > 0 else SLOT_WINDOWS.get(slot, 24.0)

    # 抓取上限先放到 24 小时，保证后备池够用
    original = cfg.news_lookback_hours
    cfg.news_lookback_hours = max(wanted, 24.0)
    try:
        pool = news.collect(cfg)
    finally:
        cfg.news_lookback_hours = original

    subset: list[news.NewsItem] = []
    used = wanted
    for window in [wanted] + [w for w in (12.0, 24.0) if w > wanted]:
        subset = [i for i in pool if i.age_hours <= window]
        used = window
        if len(subset) >= cfg.news_count:
            break

    cfg.news_lookback_hours = used
    return subset, used


# --------------------------------------------------------------------------- #
# 组装内容
# --------------------------------------------------------------------------- #
def build_digest(cfg: config_mod.Config) -> render.Digest:
    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz)
    slot = resolve_slot(cfg.slot, cfg.timezone)
    print(f"[main] {now:%Y-%m-%d %H:%M} ({cfg.timezone}) slot={slot} · 城市={cfg.city}")

    # ---- 天气 ----
    w: weather.Weather | None = None
    try:
        w = weather.fetch_weather(cfg)
        print(f"[weather] {w.headline()} | {w.comfort_line()}")
    except Exception as exc:
        print(f"[weather] ❌ 获取失败：{exc}")

    # ---- 新闻 ----
    picked: list[news.NewsItem] = []
    try:
        pool, window = load_pool(cfg, slot)
        if cfg.news_mix:
            picked = news.pick_mixed(pool, cfg.news_count, cfg.news_mix)
            mix_desc = " / ".join(f"{k}×{v}" for k, v in cfg.news_mix)
            print(
                f"[news] 回看 {window:.0f} 小时 · 候选 {len(pool)} 条"
                f" · 按配额 {mix_desc} 选出 {len(picked)} 条"
            )
        else:
            picked = news.pick(pool, cfg.news_count)
            print(f"[news] 回看 {window:.0f} 小时 · 候选 {len(pool)} 条 · 选出 {len(picked)} 条")
    except Exception as exc:
        print(f"[news] ❌ 获取失败：{exc}")

    # ---- 附加模块 ----
    ex: list[extras_mod.Extra] = []
    if "quote" in cfg.extras:
        item = extras_mod.one_sentence()
        if item:
            ex.append(item)
    if "countdown" in cfg.extras and cfg.countdowns:
        ex.extend(extras_mod.countdown(cfg.countdowns, cfg.timezone))
    if "fx" in cfg.extras and cfg.fx_pairs:
        ex.extend(extras_mod.fx_rates(cfg.fx_pairs))

    # ---- AI 一句话 ----
    ai = ""
    if cfg.llm and picked:
        ai = llm.summarize(
            cfg.llm,
            [i.clean_title() for i in picked],
            weather_hint=w.headline() if w else "",
        )
        if ai:
            print(f"[llm] {ai}")

    return render.Digest(
        generated=now,
        slot=slot,
        city=w.city if w else cfg.city,
        weather=w,
        news=picked,
        extras=ex,
        ai=ai,
        lookback_hours=cfg.news_lookback_hours,
    )


def build_test_digest(cfg: config_mod.Config) -> render.Digest:
    now = datetime.now(ZoneInfo(cfg.timezone))
    return render.Digest(
        generated=now,
        slot=resolve_slot(cfg.slot, cfg.timezone),
        city=cfg.city,
        is_test=True,
        raw_fields={
            "title": "daily-push 测试",
            "weather": "推送链路正常 ✅",
            "news": "如果你看到这条，说明配置成功",
            "tip": "接下来按计划自动发送",
            "ai": "无需任何操作",
            "remark": f"测试时间 {now:%m-%d %H:%M}",
            **{f"n{i}": f"字段 n{i} 测试正常" for i in range(1, 6)},
        },
    )


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def save_preview(digest: render.Digest) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = render.render_markdown(digest)
    (OUT_DIR / f"preview-{digest.slot}.md").write_text(md, encoding="utf-8")
    (OUT_DIR / "latest.md").write_text(md, encoding="utf-8")
    (OUT_DIR / "latest.html").write_text(render.render_page(digest), encoding="utf-8")
    # GitHub Pages 发布的入口页
    (OUT_DIR / "index.html").write_text(render.render_page(digest), encoding="utf-8")
    return OUT_DIR / "latest.md"


def print_compact(digest: render.Digest) -> None:
    print("\n----- 公众号模板消息字段（--test 时也能看到）-----")
    for key, value in render.compact_fields(digest).items():
        pretty = value.replace("\n", " / ")
        print(f"  {key:8s} = {pretty}")
    print("----------------------------------------------\n")


# --------------------------------------------------------------------------- #
# 选稿明细
# --------------------------------------------------------------------------- #
def explain_selection(cfg: config_mod.Config) -> int:
    """打印选稿明细和各品类前几名，方便调关键词与配额。不发送任何消息。"""
    print("[explain] 抓取并排序，不发送…")
    pool, window = load_pool(cfg, resolve_slot(cfg.slot, cfg.timezone))

    print(
        f"\n候选 {len(pool)} 条 · 回看 {window:.0f} 小时"
        f" · 目标 {cfg.news_count} 条"
    )

    def label(cat: str) -> str:
        return news.CATEGORY_LABELS.get(cat, cat)

    buckets: dict[str, list[news.NewsItem]] = {}
    for item in pool:
        buckets.setdefault(news.categorize(item.title), []).append(item)

    summary = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
    print("各类候选：" + "  ".join(f"{label(k)}={len(v)}" for k, v in summary))

    if cfg.news_mix:
        desc = " / ".join(f"{label(k)}×{v}" for k, v in cfg.news_mix)
        print(f"\n=== 按配额推送：{desc} ===")
        picked = news.pick_mixed(pool, cfg.news_count, cfg.news_mix)
    else:
        print("\n=== 纯按分数推送（未设 NEWS_MIX） ===")
        picked = news.pick(pool, cfg.news_count)

    for idx, item in enumerate(picked, 1):
        print(
            f"{idx:2d}. {item.age_hours:5.1f}h {item.score:5.2f} "
            f"[{label(news.categorize(item.title))}] "
            f"{item.source_name}  {item.clean_title()[:30]}"
        )

    cat_sum: dict[str, int] = {}
    src_sum: dict[str, int] = {}
    for item in picked:
        cat = label(news.categorize(item.title))
        cat_sum[cat] = cat_sum.get(cat, 0) + 1
        src_sum[item.source_name] = src_sum.get(item.source_name, 0) + 1
    print("\n品类分布：" + "  ".join(f"{k}={v}" for k, v in cat_sum.items()))
    print("来源分布：" + "  ".join(f"{k}={v}" for k, v in src_sum.items()))

    print("\n=== 各品类前 4 名（核对分类是否准确） ===")
    for cat, _ in (cfg.news_mix or [("ai", 0), ("phone", 0), ("game", 0), ("intl", 0)]):
        print(f"\n【{label(cat)}】")
        items = buckets.get(cat, [])[:4]
        if not items:
            print("  无")
            continue
        for idx, item in enumerate(items, 1):
            print(
                f"  {idx}. {item.age_hours:5.1f}h {item.score:5.2f} "
                f"{item.source_name}  {item.clean_title()[:32]}"
            )
    return 0


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    _setup_stdout()
    parser = argparse.ArgumentParser(description="每日天气 + 科技要闻推送")
    parser.add_argument("--slot", default=None, help="morning / noon / evening / auto")
    parser.add_argument("--dry-run", action="store_true", help="只生成预览，不发送")
    parser.add_argument("--test", action="store_true", help="发送测试消息")
    parser.add_argument("--only", default=None, help="只发指定渠道，逗号分隔")
    parser.add_argument("--show", action="store_true", help="打印完整 markdown 预览")
    parser.add_argument("--explain", action="store_true", help="打印选稿明细，不发送")
    args = parser.parse_args(argv)

    cfg = config_mod.load_config(args.slot)

    if args.explain:
        return explain_selection(cfg)

    broken = cfg.missing_channels()
    if broken:
        print(f"[config] ⚠️ 这些渠道参数不全，已跳过：{', '.join(broken)}")
        cfg.channels = [c for c in cfg.channels if c not in broken]
    if not cfg.channels and not args.dry_run and not args.only:
        print("[config] ❌ 没有可用渠道。请检查 .env 里的 WX_APPID 等配置。")
        return 2

    digest = build_test_digest(cfg) if args.test else build_digest(cfg)
    # 测试消息不覆盖正式预览文件，免得 latest.md 被一条「测试」冲掉
    if not digest.is_test:
        path = save_preview(digest)
        print(f"[main] 预览已写入 {path}")

    if args.show or args.dry_run:
        # 终端里打纯文本版（没有 ** / ## 这些 markdown 记号），文件里留完整 markdown
        print("\n========== 消息正文 ==========")
        print(render.render_plain(digest))
        print_compact(digest)

    if args.dry_run:
        print("[main] --dry-run：未发送。")
        return 0

    only = [s.strip() for s in args.only.split(",") if s.strip()] if args.only else None
    results = send_all(cfg, digest, only=only)
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"[main] ❌ 失败渠道：{', '.join(failed)}")
        return 1
    print("[main] ✅ 全部渠道发送完成")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
