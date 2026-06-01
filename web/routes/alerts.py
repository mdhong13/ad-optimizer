"""
Anomaly + Daily report 알림 endpoint.

외부 cron 또는 사용자 수동 트리거로 호출. ad-optimizer 내부 scheduler X
(5/28 사고로 봉인 — AUTO_START_SCHEDULER=false).

흐름:
  외부 cron-job.org 또는 GitHub Actions 가 매시간/매일 POST 호출
  → DB 데이터 검사 → 룰 위반 시 Telegram alert
  → 일일 요약 매일 아침 박음

엔드포인트:
  POST /alerts/anomaly       — anomaly 룰 검사 + alert
  POST /alerts/daily-summary — 어제 광고 성과 요약
  POST /alerts/spend-audit   — 일일 예산 집행 감사

인증: X-Alert-Key (env ALERT_API_KEY) — 외부 cron 호출용
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from agent.telegram import notify_safe
from storage.db import get_collection, get_total_spend, aggregate_campaign_performance

router = APIRouter(prefix="/alerts")


def _check_alert_auth(x_alert_key: Optional[str]) -> None:
    expected = os.getenv("ALERT_API_KEY", "")
    if not expected:
        # ALERT_API_KEY 미설정 시 — 인증 우회 (로컬 dev). 운영은 박음.
        return
    if not x_alert_key or x_alert_key != expected:
        raise HTTPException(status_code=401, detail="invalid alert key")


# ── Anomaly 검사 ────────────────────────────────────────────
@router.post("/anomaly")
async def alert_anomaly(x_alert_key: Optional[str] = Header(None, alias="X-Alert-Key")):
    """간단 anomaly 룰 검사. 매시간 외부 cron 으로 호출 권장.

    룰:
      1. 최근 1시간 knowin 게시 ghost 비율 ≥ 50% (게시는 됐지만 노출 안 됨)
      2. 최근 1시간 knowin 차단(blocked) ≥ 5건
      3. 최근 1시간 광고 캠페인 생성 ≥ 10건 (5/28 사고 류 자동 생성 폭주)
      4. 일일 누적 광고 spend > 일일 한도 (DAILY_BUDGET_CAP)
    """
    _check_alert_auth(x_alert_key)
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    alerts: list[str] = []

    # 1. ghost 비율
    qcoll = get_collection("knowin_questions")
    recent_verified = qcoll.count_documents({"verified_at": {"$gte": one_hour_ago}, "verified": True})
    recent_ghost = qcoll.count_documents({"verified_at": {"$gte": one_hour_ago}, "verified": False})
    total_recent = recent_verified + recent_ghost
    if total_recent >= 4 and recent_ghost / total_recent >= 0.5:
        alerts.append(
            f"⚠️ knowin Ghost 비율 {recent_ghost}/{total_recent} ({int(100*recent_ghost/total_recent)}%) "
            f"— 최근 1시간. 답변자 ID 차단 또는 답변 패턴 이상 의심."
        )

    # 2. 차단 누적
    recent_blocked = qcoll.count_documents({"$or": [
        {"verified_at": {"$gte": one_hour_ago}, "answer_blocked": True},
    ]})
    if recent_blocked >= 5:
        alerts.append(
            f"⚠️ knowin 차단(blocked) {recent_blocked}건 — 최근 1시간. "
            f"키워드 풀에 지식파트너 영역 검색어 다수 의심."
        )

    # 3. 광고 캠페인 자동 생성 폭주 (5/28 사고 회피)
    # campaign_cycles 또는 published_content 의 최근 1h 생성 카운트
    try:
        cycle_coll = get_collection("campaign_cycles")
        recent_cycles = cycle_coll.count_documents({"created_at": {"$gte": one_hour_ago}})
        if recent_cycles >= 10:
            alerts.append(
                f"🚨 광고 캠페인 자동 생성 {recent_cycles}건 — 최근 1시간. "
                f"5/28 사고 패턴 의심. AUTO_START_SCHEDULER 확인 + Meta·Google 콘솔 확인."
            )
    except Exception:
        pass

    # 4. 일일 누적 spend vs cap
    try:
        cap_str = os.getenv("DAILY_BUDGET_CAP", "")
        if cap_str:
            cap = float(cap_str)
            spend_today = get_total_spend(days=1)
            spent = float(spend_today.get("spend") or 0)
            if spent > cap:
                alerts.append(
                    f"💸 일일 예산 초과 — {spent:,.0f}원 > 한도 {cap:,.0f}원. "
                    f"즉시 모든 캠페인 PAUSE 검토."
                )
    except Exception:
        pass

    # 알림 박음
    if alerts:
        text = "🚨 Anomaly 감지\n\n" + "\n\n".join(alerts)
        notify_safe(text, sender="anomaly")
    else:
        # 정상 — silent (요청 시만 박음)
        pass

    return JSONResponse({"ok": True, "alerts": alerts, "count": len(alerts)})


# ── Daily Summary ──────────────────────────────────────────
@router.post("/daily-summary")
async def alert_daily_summary(x_alert_key: Optional[str] = Header(None, alias="X-Alert-Key")):
    """어제 광고 + knowin 성과 요약. 매일 아침 9시 외부 cron 권장."""
    _check_alert_auth(x_alert_key)

    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # knowin 성과
    qcoll = get_collection("knowin_questions")
    knowin_stats = {
        "posted": qcoll.count_documents({"posted_at": {"$gte": yesterday_start, "$lt": yesterday_end}}),
        "verified": qcoll.count_documents({
            "verified_at": {"$gte": yesterday_start, "$lt": yesterday_end},
            "verified": True,
        }),
        "ghost": qcoll.count_documents({
            "verified_at": {"$gte": yesterday_start, "$lt": yesterday_end},
            "verified": False,
        }),
        "rejected": qcoll.count_documents({"created_at": {"$gte": yesterday_start, "$lt": yesterday_end}}),
    }

    # 광고 spend 어제
    try:
        spend_y = get_total_spend(days=1)
    except Exception:
        spend_y = {}

    lines = ["📊 어제 운영 요약"]
    lines.append("")
    lines.append("[knowin]")
    lines.append(f"  게시: {knowin_stats['posted']}건")
    lines.append(f"  검수 통과: {knowin_stats['verified']}건")
    if knowin_stats["ghost"]:
        lines.append(f"  👻 Ghost: {knowin_stats['ghost']}건")
    lines.append("")
    lines.append("[광고]")
    if spend_y.get("spend"):
        lines.append(f"  지출: {float(spend_y['spend']):,.0f}원")
        lines.append(f"  노출: {spend_y.get('impressions', 0):,}")
        lines.append(f"  클릭: {spend_y.get('clicks', 0):,}")
        if spend_y.get("ctr"):
            lines.append(f"  CTR: {float(spend_y['ctr'])*100:.2f}%")
        if spend_y.get("roas"):
            lines.append(f"  ROAS: {float(spend_y['roas']):.2f}")
    else:
        lines.append("  (데이터 없음)")

    text = "\n".join(lines)
    notify_safe(text, sender="daily")
    return JSONResponse({"ok": True, "summary": text})


# ── Spend Audit ────────────────────────────────────────────
@router.post("/spend-audit")
async def alert_spend_audit(x_alert_key: Optional[str] = Header(None, alias="X-Alert-Key")):
    """좀비 캠페인 (PAUSED + spend > 0) 탐지 + 일일 캡 위반 + 자동화 폭주.

    매일 한 번 권장. 핵심: 5/28 사고 같은 패턴 재발 방지.
    """
    _check_alert_auth(x_alert_key)

    issues: list[str] = []

    # 1. 좀비 캠페인 — 최근 7일 spend > 0 인데 status=PAUSED
    try:
        perf = aggregate_campaign_performance(days=7)
        zombies = [
            (cid, p) for cid, p in perf.items()
            if p.get("spend", 0) > 0 and (p.get("status", "") == "PAUSED")
        ]
        if zombies:
            zlist = "\n".join(f"  · {p['campaign_name']} ({cid}): {p['spend']:,.0f}원" for cid, p in zombies[:5])
            issues.append(f"🧟 좀비 캠페인 {len(zombies)}건 (PAUSED + spend > 0):\n{zlist}")
    except Exception:
        pass

    # 2. 일일 캡 위반 (Daily anomaly 와 중복이지만 명시적)
    try:
        cap_str = os.getenv("DAILY_BUDGET_CAP", "")
        if cap_str:
            cap = float(cap_str)
            today = get_total_spend(days=1)
            spent = float(today.get("spend") or 0)
            if spent > cap:
                issues.append(f"💸 일일 예산 초과 — {spent:,.0f}원 > 한도 {cap:,.0f}원")
    except Exception:
        pass

    if issues:
        text = "💰 Spend Audit\n\n" + "\n\n".join(issues)
        notify_safe(text, sender="spend-audit")

    return JSONResponse({"ok": True, "issues": issues, "count": len(issues)})
