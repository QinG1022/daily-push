"""配置：全部来自环境变量（也可写在项目根目录的 .env 里）。

用环境变量的好处：GitHub Actions 里直接映射 Secrets，本地跑就 `cp .env.example .env`。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# .env 读取
# --------------------------------------------------------------------------- #
def load_dotenv(path: Path | None = None) -> None:
    """读取 KEY=VALUE 形式的环境文件；已存在的真实环境变量优先。"""
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _env_optional_float(name: str) -> float | None:
    raw = _env(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_list(name: str, default: str = "") -> list[str]:
    raw = _env(name) or default
    for sep in (";", "\n", " "):
        raw = raw.replace(sep, ",")
    return [part.strip() for part in raw.split(",") if part.strip()]


# --------------------------------------------------------------------------- #
# 各渠道配置
# --------------------------------------------------------------------------- #
@dataclass
class WeChatConfig:
    appid: str
    secret: str
    template_id: str
    openids: list[str]
    # 要发到模板里的字段顺序；必须与模板里的 {{xxx.DATA}} 一一对应
    fields: list[str] = field(
        default_factory=lambda: ["title", "weather", "news", "tip", "ai", "remark"]
    )
    link_url: str = ""  # 点开消息时跳转的链接（可留空）
    api_base: str = "https://api.weixin.qq.com"


@dataclass
class MailConfig:
    host: str
    port: int
    user: str
    password: str
    to: list[str]
    sender: str = ""


@dataclass
class LlmConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    timeout: float = 25.0


@dataclass
class Config:
    # 通用
    city: str = "北京"
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "Asia/Shanghai"
    slot: str = "auto"

    # 数据源
    news_sources: list[str] = field(default_factory=list)
    news_count: int = 6
    news_lookback_hours: float = 30.0

    # 推送
    channels: list[str] = field(default_factory=list)

    # 附加模块
    extras: list[str] = field(default_factory=list)
    countdowns: list[str] = field(default_factory=list)  # "2027-01-01|元旦"
    fx_pairs: list[str] = field(default_factory=list)  # "USD:CNY"

    # 渠道实例
    wechat: WeChatConfig | None = None
    mail: MailConfig | None = None
    llm: LlmConfig | None = None
    serverchan_key: str = ""
    pushplus_token: str = ""
    wecom_webhook: str = ""

    # ------------------------------------------------------------------ #
    def missing_channels(self) -> list[str]:
        """返回配置了但缺关键参数的渠道名。"""
        broken: list[str] = []
        if "wechat_mp" in self.channels and not (
            self.wechat and self.wechat.appid and self.wechat.secret
            and self.wechat.template_id and self.wechat.openids
        ):
            broken.append("wechat_mp")
        if "serverchan" in self.channels and not self.serverchan_key:
            broken.append("serverchan")
        if "pushplus" in self.channels and not self.pushplus_token:
            broken.append("pushplus")
        if "wecom" in self.channels and not self.wecom_webhook:
            broken.append("wecom")
        if "mail" in self.channels and not (
            self.mail and self.mail.host and self.mail.user and self.mail.to
        ):
            broken.append("mail")
        return broken


DEFAULT_SOURCES = "ithome,ifanr,sspai,solidot,geekpark,tmtpost"


def load_config(slot_override: str | None = None) -> Config:
    load_dotenv()

    cfg = Config(
        city=_env("CITY", "北京"),
        latitude=_env_optional_float("LATITUDE"),
        longitude=_env_optional_float("LONGITUDE"),
        timezone=_env("TZ_NAME", "Asia/Shanghai"),
        slot=slot_override or _env("SLOT", "auto"),
        news_sources=_env_list("NEWS_SOURCES", DEFAULT_SOURCES),
        news_count=max(1, _env_int("NEWS_COUNT", 6)),
        news_lookback_hours=_env_float("NEWS_LOOKBACK_HOURS", 30.0),
        channels=_env_list("PUSH_CHANNELS", "wechat_mp"),
        extras=_env_list("EXTRAS", ""),
        countdowns=_env_list("COUNTDOWN", ""),
        fx_pairs=_env_list("FX_PAIRS", ""),
        serverchan_key=_env("SERVERCHAN_SENDKEY"),
        pushplus_token=_env("PUSHPLUS_TOKEN"),
        wecom_webhook=_env("WECOM_WEBHOOK"),
    )

    if _env("WX_APPID") or _env("WX_APPSECRET"):
        # 没配大模型时默认不发 ai 字段，免得模板里「💡 一句：」后面空着
        base_fields = ["title", "weather", "news", "tip"]
        if _env("LLM_API_KEY"):
            base_fields.append("ai")
        base_fields.append("remark")
        fields = _env_list("WX_FIELDS") or base_fields
        cfg.wechat = WeChatConfig(
            appid=_env("WX_APPID"),
            secret=_env("WX_APPSECRET"),
            template_id=_env("WX_TEMPLATE_ID"),
            openids=_env_list("WX_OPENID"),
            fields=fields,
            link_url=_env("WX_LINK_URL"),
            api_base=_env("WX_API_BASE", "https://api.weixin.qq.com").rstrip("/"),
        )

    if _env("SMTP_HOST"):
        cfg.mail = MailConfig(
            host=_env("SMTP_HOST"),
            port=_env_int("SMTP_PORT", 465),
            user=_env("SMTP_USER"),
            password=_env("SMTP_PASS"),
            to=_env_list("MAIL_TO", _env("SMTP_USER")),
            sender=_env("MAIL_FROM", _env("SMTP_USER")),
        )

    if _env("LLM_API_KEY"):
        cfg.llm = LlmConfig(
            api_key=_env("LLM_API_KEY"),
            base_url=_env("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
            model=_env("LLM_MODEL", "deepseek-chat"),
            timeout=_env_float("LLM_TIMEOUT", 25.0),
        )

    return cfg


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #
SLOT_LABELS = {
    "morning": "早间",
    "noon": "午间",
    "evening": "晚间",
}
