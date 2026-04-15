"""
일간 성과 리포트 생성
"""
import logging
from datetime import date

from storage.db import get_recent_performance, get_recent_market_events, upsert_daily_report

logger = logging.getLogger(__name__)


def generate_daily_report() -> dict:
    today = date.today().isoformat()
    performance = get_recent_performance(days=1)

    total_spend = sum(r.get("spend", 0) for r in performance)
    total_clicks = sum(r.get("clicks", 0) for r in performance)
    total_impressions = sum(r.get("impressions", 0) for r in performance)
    total_conversions = sum(r.get("conversions", 0) for r in performance)
    avg_roas = (
        sum(r.get("roas", 0) for r in performance) / len(performance) if performance else 0
    )
    avg_ctr = (
        sum(r.get("ctr", 0) for r in performance) / len(performance) if performance else 0
    )

    events = get_recent_market_events(limit=5)
    events_text = "\n".join(
        f"- [{e.get('event_type', '')}] {e.get('title', '')}" for e in events
    ) or "없음"

    summary_md = f"""# OneMessage 일간 광고 리포트 — {today}

## 오늘의 성과 요약

| 지표 | 값 |
|------|----|
| 총 지출 | ${total_spend:,.2f} |
| 총 클릭 | {total_clicks:,} |
| 총 노출 | {total_impressions:,} |
| 전환 | {total_conversions:,} |
| 평균 ROAS | {avg_roas:.2f}x |
| 평균 CTR | {avg_ctr:.2%} |

## 오늘의 크립토 시장 이벤트

{events_text}

## 캠페인별 상세

| 플랫폼 | 캠페인 | 지출 | ROAS | CTR |
|--------|--------|------|------|-----|
""" + "\n".join(
        f"| {r.get('platform', '')} | {r.get('campaign_name', '')} | ${r.get('spend', 0):.2f} | {r.get('roas', 0):.2f}x | {r.get('ctr', 0):.2%} |"
        for r in performance
    )

    report = {
        "total_spend": total_spend,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "total_conversions": total_conversions,
        "avg_roas": avg_roas,
        "avg_ctr": avg_ctr,
        "summary_md": summary_md,
    }

    upsert_daily_report(today, report)
    logger.info(f"Daily report generated: {today}")
    return report
