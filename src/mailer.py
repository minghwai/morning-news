"""
SMTP 발송기.

네이버: smtp.naver.com / 465(SSL) 또는 587(STARTTLS)
       메일 → 환경설정 → POP3/IMAP 설정에서 'IMAP/SMTP 사용함'이 켜져 있어야 한다.
Gmail : smtp.gmail.com / 465 또는 587, 반드시 '앱 비밀번호' 사용.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


class MailError(RuntimeError):
    pass


def send(subject: str, html_body: str, text_body: str, attachments: list[str] | None = None):
    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "465") or 465)
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    to_raw = os.environ.get("NOTIFY_EMAIL", "").strip()

    missing = [
        name
        for name, val in (
            ("SMTP_HOST", host),
            ("SMTP_USER", user),
            ("SMTP_PASS", password),
            ("NOTIFY_EMAIL", to_raw),
        )
        if not val
    ]
    if missing:
        raise MailError(f"메일 설정 누락: {', '.join(missing)}")

    recipients = [addr.strip() for addr in to_raw.replace(";", ",").split(",") if addr.strip()]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    for path in attachments or []:
        p = Path(path)
        if not p.exists():
            print(f"    [경고] 첨부 파일 없음, 건너뜀: {path}")
            continue
        msg.add_attachment(
            p.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=p.name,
        )

    ctx = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(user, password)
                server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError(
            "SMTP 로그인 실패. 네이버는 '환경설정 → POP3/IMAP 설정 → 사용함'이 켜져 있어야 하고, "
            f"2단계 인증 사용 시 앱 비밀번호가 필요합니다. (원본: {exc})"
        ) from exc

    print(f"    → 발송 완료: {', '.join(recipients)}")
