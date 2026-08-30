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

    # 네이버는 계정에 따라 전체 주소를 거부하고 아이디만 받는 경우가 있다.
    # SMTP_LOGIN이 지정돼 있으면 그것을 쓰고, 없으면 전체 주소 → 아이디 순으로 시도한다.
    explicit = os.environ.get("SMTP_LOGIN", "").strip()
    if explicit:
        login_ids = [explicit]
    elif "@" in user:
        login_ids = [user, user.split("@", 1)[0]]
    else:
        login_ids = [user]

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
    last_error = None

    for attempt, login_id in enumerate(login_ids, 1):
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as server:
                    server.login(login_id, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=30) as server:
                    server.ehlo()
                    server.starttls(context=ctx)
                    server.ehlo()
                    server.login(login_id, password)
                    server.send_message(msg)
            if attempt > 1:
                print(f"    (로그인 아이디를 '{login_id}' 형식으로 재시도해 성공했습니다)")
            break
        except smtplib.SMTPAuthenticationError as exc:
            last_error = exc
            print(f"    [경고] 로그인 거부 — 아이디 형식 {attempt}/{len(login_ids)} 실패")
            continue
    else:
        raise MailError(
            "SMTP 로그인이 거부됐습니다(535). 확인할 것: "
            "(1) 2단계 인증을 쓴다면 계정 비밀번호가 아니라 '애플리케이션 비밀번호'가 필요합니다. "
            "(2) 네이버 메일 환경설정 → POP3/IMAP 설정이 '사용함'인지. "
            "(3) SMTP_PASS에 앞뒤 공백이나 줄바꿈이 섞이지 않았는지. "
            f"(원본: {last_error})"
        ) from last_error

    print(f"    → 발송 완료: {', '.join(recipients)}")
