"""邮件：最通用的一条路。

QQ 邮箱 / 163 用「授权码」而不是登录密码：
  QQ 邮箱 → 设置 → 账号 → 开启 SMTP 服务 → 生成授权码
  然后用 SMTP_HOST=smtp.qq.com SMTP_PORT=465 SMTP_USER=你@qq.com SMTP_PASS=授权码
"""

from __future__ import annotations

import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

from ..config import Config
from ..render import Digest, render_html, render_plain

NAME = "mail"
LABEL = "邮件"


def send(digest: Digest, cfg: Config) -> str:
    m = cfg.mail
    if not m or not m.host or not m.user or not m.to:
        raise RuntimeError("未配置 SMTP_HOST / SMTP_USER / SMTP_PASS / MAIL_TO")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(digest.title, "utf-8")
    msg["From"] = formataddr((str(Header("每日速递", "utf-8")), m.sender or m.user))
    msg["To"] = ", ".join(m.to)
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(render_plain(digest), "plain", "utf-8"))
    msg.attach(MIMEText(render_html(digest), "html", "utf-8"))

    context = ssl.create_default_context()
    if m.port == 465:
        server = smtplib.SMTP_SSL(m.host, m.port, timeout=30, context=context)
    else:
        server = smtplib.SMTP(m.host, m.port, timeout=30)
        server.ehlo()
        try:
            server.starttls(context=context)
            server.ehlo()
        except smtplib.SMTPException:
            pass

    try:
        server.login(m.user, m.password)
        server.sendmail(m.user, m.to, msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass
    return f"已发送到 {', '.join(m.to)}"
