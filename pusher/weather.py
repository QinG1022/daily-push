"""天气：Open-Meteo（免费、无需 key、支持中文地名地理编码）。

数据来源：
  https://geocoding-api.open-meteo.com/v1/search
  https://api.open-meteo.com/v1/forecast
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from . import http
from .config import ROOT, Config

CACHE_DIR = ROOT / ".cache"
GEOCODE_CACHE = CACHE_DIR / "geocode.json"

# WMO weather code -> (中文描述, emoji)
WMO: dict[int, tuple[str, str]] = {
    0: ("晴", "☀️"),
    1: ("晴间多云", "🌤"),
    2: ("多云", "⛅"),
    3: ("阴", "☁️"),
    45: ("有雾", "🌫"),
    48: ("雾凇", "🌫"),
    51: ("小毛毛雨", "🌦"),
    53: ("毛毛雨", "🌦"),
    55: ("较密毛毛雨", "🌦"),
    56: ("冻毛毛雨", "🌧"),
    57: ("冻毛毛雨", "🌧"),
    61: ("小雨", "🌦"),
    63: ("中雨", "🌧"),
    65: ("大雨", "🌧"),
    66: ("冻雨", "🌧"),
    67: ("冻雨", "🌧"),
    71: ("小雪", "🌨"),
    73: ("中雪", "🌨"),
    75: ("大雪", "❄️"),
    77: ("米雪", "🌨"),
    80: ("阵雨", "🌦"),
    81: ("强阵雨", "🌧"),
    82: ("暴雨", "⛈"),
    85: ("阵雪", "🌨"),
    86: ("强阵雪", "❄️"),
    95: ("雷阵雨", "⛈"),
    96: ("雷阵雨伴冰雹", "⛈"),
    99: ("雷暴伴冰雹", "⛈"),
}

DAY_LABELS = ("今天", "明天", "后天")


def describe(code: int) -> tuple[str, str]:
    return WMO.get(int(code), ("未知", "🌡"))


def uv_level(uv: float) -> str:
    if uv < 3:
        return "低"
    if uv < 6:
        return "中等"
    if uv < 8:
        return "高"
    if uv < 11:
        return "很高"
    return "极高"


_AQI_LEVELS = (
    (50, "优"),
    (100, "良"),
    (150, "轻度污染"),
    (200, "中度污染"),
    (300, "重度污染"),
)


def aqi_level(aqi: int) -> str:
    for limit, name in _AQI_LEVELS:
        if aqi <= limit:
            return name
    return "严重污染"


def _hm(iso: str) -> str:
    """'2026-11-06T06:43' -> '06:43'"""
    return iso[11:16] if len(iso) >= 16 else ""


def fetch_aqi(lat: float, lon: float, tz: str) -> int | None:
    """空气质量单独一个接口，失败就返回 None，不影响主流程。"""
    try:
        url = http.with_query(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            {
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "current": "us_aqi",
                "timezone": tz,
            },
        )
        data = http.get_json(url, timeout=12, retries=1)
        value = (data.get("current") or {}).get("us_aqi")
        return int(value) if value is not None else None
    except Exception:
        return None


@dataclass
class DayForecast:
    day: date
    label: str
    code: int
    text: str
    emoji: str
    tmax: float
    tmin: float
    pop: int
    precip: float
    uv: float
    sunrise: str = ""
    sunset: str = ""

    @property
    def range_text(self) -> str:
        return f"{self.tmin:.0f}~{self.tmax:.0f}℃"


@dataclass
class Weather:
    city: str
    current_temp: float
    feels_like: float
    humidity: int
    wind: float
    now_code: int
    days: list[DayForecast] = field(default_factory=list)
    dress: str = ""
    aqi: int | None = None

    # ------------------------------------------------------------------ #
    @property
    def today(self) -> DayForecast | None:
        return self.days[0] if self.days else None

    @property
    def now_text(self) -> str:
        return describe(self.now_code)[0]

    @property
    def now_emoji(self) -> str:
        return describe(self.now_code)[1]

    def headline(self) -> str:
        """一行天气，适合放在消息最上面（用当天预报，而不是实时观测）。"""
        if not self.today:
            return f"{self.city} {self.now_emoji}{self.now_text} {self.current_temp:.0f}℃"
        t = self.today
        return f"{self.city} {t.emoji}{t.text} {t.range_text} · 降水 {t.pop}%"

    def comfort_line(self) -> str:
        return (
            f"现在 {self.current_temp:.0f}℃（体感 {self.feels_like:.0f}℃）"
            f"· 湿度 {self.humidity}% · 风 {self.wind:.0f}km/h"
        )

    def tips(self) -> list[str]:
        """根据温度/降水/紫外线/风力生成出行提示。"""
        out: list[str] = []
        t = self.today
        if t:
            spread = t.tmax - t.tmin
            if spread >= 10:
                out.append(f"早晚温差 {spread:.0f}℃，分层穿衣最稳")
            if t.tmin <= 0:
                out.append(f"最低 {t.tmin:.0f}℃，羽绒/厚外套别省")
            elif t.tmin < 8:
                out.append("早晚偏凉，出门加件外套")
            elif t.tmax >= 32:
                out.append("白天偏热，注意补水和防晒")

            snow = t.code in (71, 73, 75, 77, 85, 86)
            if snow:
                out.append("有降雪，路面湿滑，通勤慢一点")
            elif t.pop >= 60:
                out.append(f"降水概率 {t.pop}%，记得带伞")
            elif t.pop >= 30:
                out.append(f"可能零星降雨（{t.pop}%），备把折叠伞")
            if t.uv >= 8:
                out.append(f"紫外线很强（UV {t.uv:.0f}），做好防晒")
            elif t.uv >= 6:
                out.append(f"紫外线较强（UV {t.uv:.0f}），注意防晒")
            if self.wind >= 30:
                out.append("风比较大，骑车注意安全")
        if self.dress:
            out.append(f"穿搭建议：{self.dress}")
        return out


# --------------------------------------------------------------------------- #
# 取数
# --------------------------------------------------------------------------- #
def _load_geocode_cache() -> dict[str, Any]:
    try:
        return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_geocode_cache(data: dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        GEOCODE_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # 缓存只是优化，失败不影响主流程


def geocode(city: str) -> tuple[float, float, str]:
    """地名 -> (纬度, 经度, 规范地名)。"""
    cache = _load_geocode_cache()
    key = city.strip().lower()
    if key in cache:
        item = cache[key]
        return item["lat"], item["lon"], item["name"]

    url = http.with_query(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": city, "count": 1, "language": "zh", "format": "json"},
    )
    data = http.get_json(url, timeout=15)
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"找不到城市「{city}」，请检查 CITY 环境变量")
    hit = results[0]
    name = hit.get("name") or city
    admin1 = hit.get("admin1") or ""
    # 同名地名很多：只有「北京」这种已经包含在「北京市」里的就不重复拼了
    if admin1 and name not in admin1 and len(admin1) <= 8:
        name = f"{name}（{admin1}）"
    cache[key] = {"lat": hit["latitude"], "lon": hit["longitude"], "name": name}
    _save_geocode_cache(cache)
    return hit["latitude"], hit["longitude"], name


def dress_advice(feels_like: float) -> str:
    if feels_like < -5:
        return "羽绒服 + 帽围巾，手套带上"
    if feels_like < 0:
        return "厚羽绒服，注意防风"
    if feels_like < 5:
        return "厚外套 / 棉服 + 毛衣"
    if feels_like < 10:
        return "外套或呢子大衣，内搭针织"
    if feels_like < 15:
        return "夹克 / 风衣 + 长袖"
    if feels_like < 20:
        return "长袖衬衫或薄外套即可"
    if feels_like < 25:
        return "短袖 / 薄长袖，随身带件薄外套"
    if feels_like < 30:
        return "短袖短裤，注意防晒"
    return "轻薄透气，尽量避开正午户外"


def fetch_weather(cfg: Config) -> Weather:
    if cfg.latitude is not None and cfg.longitude is not None:
        lat, lon, name = cfg.latitude, cfg.longitude, cfg.city
    else:
        lat, lon, name = geocode(cfg.city)

    url = http.with_query(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,precipitation_sum,uv_index_max,"
                     "sunrise,sunset",
            "timezone": cfg.timezone,
            "forecast_days": 3,
        },
    )
    data = http.get_json(url, timeout=20)

    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    days: list[DayForecast] = []
    for idx, day_str in enumerate(daily.get("time") or []):
        code = (daily.get("weather_code") or [0])[idx]
        text, emoji = describe(code)
        days.append(
            DayForecast(
                day=datetime.strptime(day_str, "%Y-%m-%d").date(),
                label=DAY_LABELS[idx] if idx < len(DAY_LABELS) else day_str,
                code=int(code),
                text=text,
                emoji=emoji,
                tmax=float((daily.get("temperature_2m_max") or [0])[idx]),
                tmin=float((daily.get("temperature_2m_min") or [0])[idx]),
                pop=int((daily.get("precipitation_probability_max") or [0])[idx] or 0),
                precip=float((daily.get("precipitation_sum") or [0])[idx] or 0),
                uv=float((daily.get("uv_index_max") or [0])[idx] or 0),
                sunrise=_hm((daily.get("sunrise") or [""])[idx] or ""),
                sunset=_hm((daily.get("sunset") or [""])[idx] or ""),
            )
        )
    feels = float(cur.get("apparent_temperature", cur.get("temperature_2m", 0)) or 0)
    return Weather(
        city=name,
        current_temp=float(cur.get("temperature_2m", 0) or 0),
        feels_like=feels,
        humidity=int(cur.get("relative_humidity_2m", 0) or 0),
        wind=float(cur.get("wind_speed_10m", 0) or 0),
        now_code=int(cur.get("weather_code", 0) or 0),
        days=days,
        dress=dress_advice(feels),
        aqi=fetch_aqi(lat, lon, cfg.timezone),
    )


def format_forecast_lines(w: Weather, limit: int = 3) -> list[str]:
    lines = []
    for d in w.days[:limit]:
        lines.append(f"{d.label} {d.emoji}{d.text} {d.range_text} 降水{d.pop}%")
    return lines
