"""
Gmail API로 리포트 이메일 발송
"""
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from config.settings import settings

logger = logging.getLogger(__name__)

SENDER = "bungbungcar13@gmail.com"
RECIPIENTS = ["bungbungcar13@gmail.com"]


def _get_access_token() -> str:
    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        client_id=settings.GOOGLE_ADS_CLIENT_ID,
        client_secret=settings.GOOGLE_ADS_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ],
    )
    creds.refresh(Request())
    return creds.token


def send_report_email(report: dict) -> bool:
    """일간 리포트를 Gmail로 발송"""
    token = _get_access_token()

    summary = report.get("summary_md", "")
    date_str = report.get("date", "today")

    # 간단한 텍스트 요약
    body = f"""OneMessage Ad Optimizer - Daily Report ({date_str})

Spend: ${report.get('total_spend', 0):,.2f}
Clicks: {report.get('total_clicks', 0):,}
Impressions: {report.get('total_impressions', 0):,}
Conversions: {report.get('total_conversions', 0):,}
Avg CTR: {report.get('avg_ctr', 0):.2%}
Avg ROAS: {report.get('avg_roas', 0):.2f}x

---
Full report available at dashboard.
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Ad Optimizer] Daily Report - {date_str}"
    msg["From"] = SENDER
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # markdown을 간단한 HTML로
    html_body = summary.replace("\n", "<br>") if summary else body.replace("\n", "<br>")
    msg.attach(MIMEText(f"<html><body><pre>{html_body}</pre></body></html>", "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    r = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw": raw},
        timeout=30,
    )

    if r.status_code == 200:
        logger.info(f"Report email sent to {RECIPIENTS}")
        return True
    else:
        logger.error(f"Gmail send failed: {r.status_code} {r.text}")
        return False


def send_alert(subject: str, body: str) -> bool:
    """긴급 알림 발송 (시장 이벤트 등)"""
    token = _get_access_token()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[Ad Optimizer ALERT] {subject}"
    msg["From"] = SENDER
    msg["To"] = ", ".join(RECIPIENTS)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    r = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw": raw},
        timeout=30,
    )

    if r.status_code == 200:
        logger.info(f"Alert sent: {subject}")
        return True
    else:
        logger.error(f"Alert send failed: {r.status_code}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_report = {
        "date": "2026-04-15",
        "total_spend": 0,
        "total_clicks": 0,
        "total_impressions": 0,
        "total_conversions": 0,
        "avg_ctr": 0,
        "avg_roas": 0,
        "summary_md": "# Test Report\n\nThis is a test.",
    }
    send_report_email(test_report)
