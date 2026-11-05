"""微信公众号「模板消息」推送。

适用对象：
  * 微信公众平台「接口测试号」—— 免费、无需认证、模板可自定义（推荐自用）
  * 已认证的「服务号」—— 模板必须从类目模板库选，字段有类型和长度限制

官方文档：
  发送模板消息 https://developers.weixin.qq.com/doc/service/api/notify/template/api_sendtemplatemessage
"""

from __future__ import annotations

from .. import http
from ..config import Config
from ..render import Digest, compact_fields

NAME = "wechat_mp"
LABEL = "微信公众号模板消息"

_ERR_HINTS = {
    40001: "AppSecret 不对（或已被重置），去后台重新复制",
    40013: "AppID 不合法，检查是否复制错",
    40003: "OpenID 无效，确认这个用户已关注该公众号",
    40037: "template_id 无效，检查模板 ID",
    43004: "接收者没有关注这个公众号",
    45009: "接口调用次数超限（每天 10 万次，一般不会碰到）",
    47003: "模板参数不合法：字段名或长度和模板对不上",
}


def _access_token(cfg: Config) -> str:
    w = cfg.wechat
    assert w is not None
    url = http.with_query(
        f"{w.api_base}/cgi-bin/token",
        {"grant_type": "client_credential", "appid": w.appid, "secret": w.secret},
    )
    data = http.get_json(url, timeout=15)
    if data.get("errcode"):
        code = int(data["errcode"])
        raise RuntimeError(f"获取 access_token 失败 [{code}] {data.get('errmsg')} —— {_ERR_HINTS.get(code, '检查 AppID/AppSecret')}")
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"获取 access_token 为空: {data}")
    return token


def send(digest: Digest, cfg: Config) -> str:
    w = cfg.wechat
    if not w:
        raise RuntimeError("未配置 WX_APPID / WX_APPSECRET / WX_TEMPLATE_ID / WX_OPENID")

    values = compact_fields(digest)
    data = {key: {"value": values[key]} for key in w.fields if key in values}
    missing = [key for key in w.fields if key not in values]
    if missing:
        print(f"[wechat] 模板字段无内容、已跳过：{', '.join(missing)}")
    if not data:
        raise RuntimeError("模板字段全为空，没什么可发的")

    token = _access_token(cfg)
    url = f"{w.api_base}/cgi-bin/message/template/send?access_token={token}"

    msgids: list[str] = []
    for openid in w.openids:
        payload = {"touser": openid, "template_id": w.template_id, "data": data}
        if w.link_url:
            payload["url"] = w.link_url
        resp = http.post_json(url, payload, timeout=20)
        if resp.get("errcode"):
            code = int(resp["errcode"])
            hint = _ERR_HINTS.get(code, "")
            raise RuntimeError(f"模板消息发送失败 [{code}] {resp.get('errmsg')} {hint}".strip())
        msgids.append(str(resp.get("msgid", "")))

    return f"已发送 {len(msgids)} 条（字段 {', '.join(data)}）"
