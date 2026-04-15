"""
MongoDB 컬렉션 스키마 정의 & 인덱스
"""

# 컬렉션별 인덱스 정의
INDEXES = {
    # 캠페인 성과 스냅샷
    "performance_snapshots": [
        {"keys": [("platform", 1), ("date", -1)]},
        {"keys": [("campaign_id", 1), ("date", -1)]},
    ],
    # 에이전트 결정 이력
    "agent_decisions": [
        {"keys": [("status", 1), ("created_at", -1)]},
        {"keys": [("platform", 1), ("campaign_id", 1)]},
    ],
    # 크립토 시장 이벤트
    "market_events": [
        {"keys": [("event_type", 1), ("created_at", -1)]},
    ],
    # 캠페인 사이클 (20→2 최적화)
    "campaign_cycles": [
        {"keys": [("cycle_id", 1)], "unique": True},
        {"keys": [("status", 1), ("created_at", -1)]},
    ],
    # AI 캐릭터
    "characters": [
        {"keys": [("name", 1)], "unique": True},
        {"keys": [("platform", 1), ("active", 1)]},
    ],
    # 바이럴 활동 로그
    "viral_activities": [
        {"keys": [("character_id", 1), ("created_at", -1)]},
        {"keys": [("platform", 1), ("created_at", -1)]},
    ],
    # 콘텐츠 게시 로그
    "published_content": [
        {"keys": [("platform", 1), ("published_at", -1)]},
        {"keys": [("status", 1)]},
    ],
    # 일간 리포트
    "daily_reports": [
        {"keys": [("date", 1)], "unique": True},
    ],
}


def performance_snapshot(
    platform: str,
    campaign_id: str,
    campaign_name: str,
    date: str,
    **kwargs,
) -> dict:
    """성과 스냅샷 문서 생성"""
    doc = {
        "platform": platform,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "ad_set_id": kwargs.get("ad_set_id", ""),
        "ad_set_name": kwargs.get("ad_set_name", ""),
        "date": date,
        "hour": kwargs.get("hour"),
        "impressions": kwargs.get("impressions", 0),
        "clicks": kwargs.get("clicks", 0),
        "spend": kwargs.get("spend", 0.0),
        "conversions": kwargs.get("conversions", 0),
        "revenue": kwargs.get("revenue", 0.0),
        "ctr": kwargs.get("ctr", 0.0),
        "cpc": kwargs.get("cpc", 0.0),
        "cpm": kwargs.get("cpm", 0.0),
        "roas": kwargs.get("roas", 0.0),
    }
    return doc


def agent_decision(
    task_type: str,
    action: str,
    reason: str,
    **kwargs,
) -> dict:
    """에이전트 결정 문서 생성"""
    return {
        "task_type": task_type,
        "platform": kwargs.get("platform", ""),
        "campaign_id": kwargs.get("campaign_id", ""),
        "action": action,
        "target_id": kwargs.get("target_id", ""),
        "current_value": kwargs.get("current_value"),
        "new_value": kwargs.get("new_value"),
        "change_pct": kwargs.get("change_pct"),
        "reason": reason,
        "context": kwargs.get("context"),
        "status": kwargs.get("status", "pending"),
        "dry_run": kwargs.get("dry_run", True),
    }


def campaign_cycle(
    cycle_id: str,
    platform: str,
    total: int,
    survive: int,
) -> dict:
    """캠페인 사이클 문서"""
    return {
        "cycle_id": cycle_id,
        "platform": platform,
        "total_campaigns": total,
        "survive_count": survive,
        "campaigns": [],  # [{campaign_id, name, status, score}]
        "survivors": [],  # [campaign_id, ...]
        "status": "created",  # created → running → analyzed → completed
        "parent_cycle_id": None,
    }


def character(
    name: str,
    platform: str,
    persona: str,
) -> dict:
    """AI 캐릭터 문서"""
    return {
        "name": name,
        "platform": platform,
        "persona": persona,
        "tone": "",
        "interests": [],
        "active": True,
        "total_posts": 0,
        "total_replies": 0,
    }
