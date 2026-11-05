"""极简 HTTP 客户端（基于 urllib，零第三方依赖）。

设计目标：对外网抓取足够宽容 —— 超时、重试、UA、错误可读。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

# 有些站点（IT之家、极客公园）会拒绝默认的 Python-urllib UA，给个像浏览器的。
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 daily-push/1.0"
)


class HttpError(RuntimeError):
    """请求失败（网络错误或非 2xx）。"""


def request(
    url: str,
    *,
    data: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 2,
    backoff: float = 1.6,
    method: str | None = None,
) -> bytes:
    """发起请求并返回响应体。5xx / 429 / 网络错误会重试。"""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("User-Agent", USER_AGENT)
            req.add_header("Accept-Encoding", "identity")
            for key, value in (headers or {}).items():
                req.add_header(key, value)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:  # 4xx/5xx
            body = b""
            try:
                body = exc.read()[:300]
            except Exception:  # pragma: no cover - 尽力而为
                pass
            snippet = body.decode("utf-8", "replace")
            last = HttpError(f"HTTP {exc.code} {url} :: {snippet}")
            if exc.code < 500 and exc.code != 429:
                break  # 客户端错误重试没意义
        except Exception as exc:  # 超时、DNS、连接重置……
            last = exc
        if attempt < retries:
            time.sleep(backoff ** attempt)
    raise HttpError(f"request failed: {url} :: {last}")


def get_json(url: str, *, timeout: float = 20.0, retries: int = 2) -> Any:
    return json.loads(request(url, timeout=timeout, retries=retries).decode("utf-8"))


def post_json(
    url: str,
    payload: Any,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 1,
) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    merged = {"Content-Type": "application/json; charset=utf-8"}
    merged.update(headers or {})
    raw = request(url, data=body, headers=merged, timeout=timeout, retries=retries, method="POST")
    return json.loads(raw.decode("utf-8"))


def post_form(
    url: str,
    fields: Mapping[str, str],
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 1,
) -> bytes:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    merged = {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
    merged.update(headers or {})
    return request(url, data=body, headers=merged, timeout=timeout, retries=retries, method="POST")


def with_query(url: str, params: Mapping[str, Any]) -> str:
    clean = {k: v for k, v in params.items() if v is not None}
    if not clean:
        return url
    sep = "&" if urllib.parse.urlparse(url).query else "?"
    return f"{url}{sep}{urllib.parse.urlencode(clean)}"
