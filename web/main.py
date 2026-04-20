"""
FastAPI 웹 대시보드 진입점
"""
import logging
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

from storage.db import init_db
from web import live_logs, scheduler_bg
from web.routes import dashboard, campaigns, decisions, scheduler, events, viral, publisher, settings, creative

live_logs.install_handler()

app = FastAPI(title="OneMessage Ad Optimizer", version="2.0.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Static files (CSS, JS, PWA)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Generated assets (creative outputs, etc.)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

app.include_router(dashboard.router)
app.include_router(campaigns.router)
app.include_router(decisions.router)
app.include_router(scheduler.router)
app.include_router(events.router)
app.include_router(viral.router)
app.include_router(publisher.router)
app.include_router(settings.router)
app.include_router(creative.router)


@app.on_event("startup")
async def startup():
    import asyncio
    live_logs.set_loop(asyncio.get_running_loop())
    init_db()
    scheduler_bg.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler_bg.shutdown()


@app.get("/health")
async def health():
    return {"status": "ok", "app": "OneMessage Ad Optimizer", "version": "2.0.0"}


from fastapi.responses import HTMLResponse

_PRIVACY_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OneMessage 개인정보처리방침 / Privacy Policy</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:820px;margin:40px auto;padding:0 20px;line-height:1.7;color:#222}
h1{border-bottom:2px solid #333;padding-bottom:8px}
h2{margin-top:32px;color:#333}
a{color:#0b5fff}
small{color:#666}
</style>
</head>
<body>
<h1>OneMessage 개인정보처리방침</h1>
<p><small>시행일: 2026-04-19</small></p>

<p>OneMessage(이하 "서비스")는 사용자의 개인정보를 중요시하며, 관련 법령에 따라 다음과 같이 개인정보를 처리합니다.</p>

<h2>1. 수집하는 개인정보 항목</h2>
<ul>
<li>계정 정보: 이메일 주소, 닉네임</li>
<li>지갑 연동 정보: 공개 주소(개인키는 수집·저장하지 않음)</li>
<li>서비스 이용 기록: 접속 로그, 기기 정보(OS, 앱 버전)</li>
</ul>

<h2>2. 개인정보의 수집 및 이용 목적</h2>
<ul>
<li>서비스 제공 및 사용자 인증</li>
<li>사망 감지 및 지정 수신자에게 메시지 전달</li>
<li>서비스 개선, 통계 분석, 오류 대응</li>
<li>마케팅 및 광고 (사용자 동의 시)</li>
</ul>

<h2>3. 개인정보의 보유 및 이용 기간</h2>
<p>사용자가 서비스 탈퇴를 요청하거나 수집·이용 목적이 달성된 경우 지체 없이 파기합니다. 단, 관계 법령에 따라 보존이 필요한 경우 해당 기간 동안 보관합니다.</p>

<h2>4. 개인정보의 제3자 제공</h2>
<p>서비스는 사용자의 동의 없이 개인정보를 제3자에게 제공하지 않습니다. 단, 사용자가 지정한 수신자에게 사망 감지 메시지를 전달하는 경우에 한해 사용자가 설정한 내용을 전달합니다.</p>

<h2>5. 개인정보의 처리 위탁</h2>
<p>원활한 서비스 제공을 위해 아래 업체에 일부 업무를 위탁할 수 있습니다.</p>
<ul>
<li>클라우드 인프라: Amazon Web Services, Railway, Vercel</li>
<li>광고 플랫폼: Meta Platforms, Google, X(Twitter), Reddit</li>
</ul>

<h2>6. 사용자의 권리</h2>
<p>사용자는 언제든지 개인정보 열람·수정·삭제·처리정지를 요청할 수 있습니다. 요청은 아래 연락처로 해주시기 바랍니다.</p>

<h2>7. 쿠키 및 유사 기술</h2>
<p>서비스는 사용자 경험 개선을 위해 쿠키 및 유사 기술을 사용할 수 있으며, 브라우저 설정을 통해 거부할 수 있습니다.</p>

<h2>8. 개인정보 보호 책임자</h2>
<p>
담당자: OneMessage 운영팀<br>
이메일: <a href="mailto:bungbungcar13@gmail.com">bungbungcar13@gmail.com</a>
</p>

<h2>9. 개인정보처리방침 변경</h2>
<p>본 방침이 변경되는 경우 변경 사항을 본 페이지에 공지합니다.</p>

<hr>
<h1>OneMessage Privacy Policy</h1>
<p><small>Effective: 2026-04-19</small></p>

<p>OneMessage ("the Service") values user privacy and processes personal information in accordance with applicable laws as described below.</p>

<h2>1. Information We Collect</h2>
<ul>
<li>Account: email address, nickname</li>
<li>Wallet linkage: public address only (private keys are never collected or stored)</li>
<li>Usage logs: access logs, device information (OS, app version)</li>
</ul>

<h2>2. Purpose of Use</h2>
<ul>
<li>Providing the service and authenticating users</li>
<li>Death detection and delivering messages to designated recipients</li>
<li>Service improvement, analytics, troubleshooting</li>
<li>Marketing and advertising (with user consent)</li>
</ul>

<h2>3. Retention</h2>
<p>We delete personal information without delay upon account deletion or when the purpose of collection is fulfilled, except where retention is required by law.</p>

<h2>4. Third-Party Sharing</h2>
<p>We do not share personal information with third parties without user consent, except for delivering messages to recipients designated by the user.</p>

<h2>5. Processors</h2>
<ul>
<li>Cloud infrastructure: Amazon Web Services, Railway, Vercel</li>
<li>Ad platforms: Meta Platforms, Google, X (Twitter), Reddit</li>
</ul>

<h2>6. User Rights</h2>
<p>Users may request access, correction, deletion, or suspension of processing of their personal information at any time via the contact below.</p>

<h2>7. Cookies</h2>
<p>The service may use cookies and similar technologies. You can refuse them through your browser settings.</p>

<h2>8. Contact</h2>
<p>
OneMessage Operations<br>
Email: <a href="mailto:bungbungcar13@gmail.com">bungbungcar13@gmail.com</a>
</p>

<h2>9. Changes</h2>
<p>We will post any changes to this policy on this page.</p>
</body>
</html>"""


@app.get("/privacy", response_class=HTMLResponse)
@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    return _PRIVACY_HTML


@app.get("/api/scheduler/status")
async def scheduler_status():
    return scheduler_bg.status()
