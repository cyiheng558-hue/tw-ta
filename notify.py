# -*- coding: utf-8 -*-
"""通知模組:寄送 Email(SMTP)。

設定方式(環境變數):
  TWTA_SMTP_USER  寄件 Gmail 帳號,如 you@gmail.com
  TWTA_SMTP_PASS  Gmail「應用程式密碼」(非登入密碼!須先到 Google 帳號開啟兩步驟驗證後產生)
  TWTA_MAIL_TO    收件信箱(可省略,預設寄給自己)

沒設定時不會報錯,只會略過寄信、回傳 False。

註:LINE Notify 已於 2025/3 停止服務,故改用 Email。若想用 Telegram/Discord
可仿照本檔加一個 send_xxx 函式。
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header


def email_configured() -> bool:
    return bool(os.environ.get("TWTA_SMTP_USER") and os.environ.get("TWTA_SMTP_PASS"))


def send_email(subject: str, body: str, to: str = None,
               host: str = "smtp.gmail.com", port: int = 587) -> bool:
    """寄送純文字 Email。回傳是否成功。"""
    user = os.environ.get("TWTA_SMTP_USER")
    pw = os.environ.get("TWTA_SMTP_PASS")
    if not user or not pw:
        print("  [notify] 未設定 TWTA_SMTP_USER / TWTA_SMTP_PASS,略過寄信。")
        return False
    to = to or os.environ.get("TWTA_MAIL_TO") or user

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    try:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, [to], msg.as_string())
        print(f"  [notify] 已寄出通知到 {to}")
        return True
    except Exception as e:
        print(f"  [notify] 寄信失敗:{e}")
        return False


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if email_configured():
        send_email("台股工具測試信", "這是一封測試信,代表 Email 設定成功。")
    else:
        print("尚未設定 Email 環境變數,請參考檔案開頭說明。")
