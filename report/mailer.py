"""透過 Gmail SMTP 寄出 HTML 郵件。需要 Gmail「應用程式密碼」，不是登入密碼。"""
import os
import smtplib
from email.message import EmailMessage


def send_email(subject: str, html: str) -> None:
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipients = [a.strip() for a in os.environ.get("MAIL_TO", user).split(",") if a.strip()]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content("您的郵件軟體不支援 HTML，請改用支援 HTML 的郵件軟體閱讀本報告。")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
