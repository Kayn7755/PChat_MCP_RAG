from __future__ import annotations

import logging
import smtplib
import threading
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email_async(
    host: str,
    port: int,
    username: str,
    password: str,
    to_addr: str,
    subject: str,
    body: str,
) -> None:
    def _run() -> None:
        if not username or not password:
            logger.warning("邮件未配置，跳过发送 to=%s", to_addr)
            return
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = username
            msg["To"] = to_addr
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                s.login(username, password)
                s.sendmail(username, [to_addr], msg.as_string())
            logger.info("邮件发送成功 to=%s", to_addr)
        except Exception:
            logger.exception("邮件发送失败 to=%s", to_addr)

    threading.Thread(target=_run, daemon=True).start()
