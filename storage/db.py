"""
MongoDB 연결 및 CRUD
"""
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from config.settings import settings
from storage.models import INDEXES

logger = logging.getLogger(__name__)

_client: MongoClient = None
_db: Database = None


def get_db() -> Database:
    """MongoDB 데이터베이스 인스턴스 반환 (싱글톤)"""
    global _client, _db
    if _db is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        _db = _client[settings.MONGODB_DB]
        logger.info(f"MongoDB connected: {settings.MONGODB_DB}")
    return _db


def get_collection(name: str) -> Collection:
    """컬렉션 인스턴스 반환"""
    return get_db()[name]


def init_db() -> None:
    """인덱스 생성"""
    db = get_db()
    for coll_name, indexes in INDEXES.items():
        coll = db[coll_name]
        for idx in indexes:
            kwargs = {}
            if idx.get("unique"):
                kwargs["unique"] = True
            coll.create_index(idx["keys"], **kwargs)
    logger.info("MongoDB indexes created")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- App Settings (활성 광고 계정 등) ---

def get_app_setting(key: str, default=None):
    doc = get_collection("app_settings").find_one({"key": key}, {"_id": 0})
    return doc["value"] if doc else default


def set_app_setting(key: str, value) -> None:
    get_collection("app_settings").update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "updated_at": _now()}},
        upsert=True,
    )


def get_active_meta_account() -> str:
    """DB에 저장된 활성 Meta 광고 계정 ID. 없으면 settings 기본값."""
    from config.settings import settings as _s
    accounts = _s.meta_ad_accounts
    if not accounts:
        return _s.META_AD_ACCOUNT_ID
    stored = get_app_setting("active_meta_account")
    valid_ids = {a["id"] for a in accounts}
    if stored and stored in valid_ids:
        return stored
    return accounts[0]["id"]


def set_active_meta_account(account_id: str) -> None:
    from config.settings import settings as _s
    valid_ids = {a["id"] for a in _s.meta_ad_accounts}
    if account_id not in valid_ids:
        raise ValueError(f"Unknown Meta account: {account_id}")
    set_app_setting("active_meta_account", account_id)


# --- Performance Snapshots ---

def insert_performance(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("performance_snapshots").insert_one(doc)
    return str(result.inserted_id)


def get_recent_performance(platform: str = None, days: int = 7) -> list:
    """(campaign_id, date) 당 최신 스냅샷 1건만 반환 — 수집 중복 제거."""
    from datetime import timedelta
    cutoff = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    match = {"date": {"$gte": cutoff}}
    if platform:
        match["platform"] = platform
    pipeline = [
        {"$match": match},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": {"campaign_id": "$campaign_id", "date": "$date"},
            "doc": {"$first": "$$ROOT"},
        }},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"date": -1, "spend": -1}},
    ]
    rows = list(get_collection("performance_snapshots").aggregate(pipeline))
    for r in rows:
        r.pop("_id", None)
    return rows


def aggregate_campaign_performance(platform: str = None, days: int = 7) -> dict:
    """campaign_id별 누적 성과 집계 (impressions, clicks, spend, conversions)"""
    from datetime import timedelta
    cutoff = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    match = {"date": {"$gte": cutoff}}
    if platform:
        match["platform"] = platform
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$campaign_id",
            "campaign_name": {"$last": "$campaign_name"},
            "platform": {"$last": "$platform"},
            "impressions": {"$sum": "$impressions"},
            "clicks": {"$sum": "$clicks"},
            "spend": {"$sum": "$spend"},
            "conversions": {"$sum": "$conversions"},
            "revenue": {"$sum": "$revenue"},
            "last_date": {"$max": "$date"},
        }},
    ]
    result = {}
    for row in get_collection("performance_snapshots").aggregate(pipeline):
        cid = row["_id"]
        impressions = row.get("impressions", 0)
        clicks = row.get("clicks", 0)
        spend = row.get("spend", 0.0)
        result[cid] = {
            "campaign_name": row.get("campaign_name", ""),
            "platform": row.get("platform", ""),
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": row.get("conversions", 0),
            "revenue": row.get("revenue", 0.0),
            "ctr": (clicks / impressions) if impressions else 0.0,
            "cpc": (spend / clicks) if clicks else 0.0,
            "last_date": row.get("last_date", ""),
        }
    return result


def get_total_spend(platform: str = None, days: int = 30) -> dict:
    """전체 누적 집행액 및 핵심 지표"""
    from datetime import timedelta
    cutoff = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    match = {"date": {"$gte": cutoff}}
    if platform:
        match["platform"] = platform
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "impressions": {"$sum": "$impressions"},
            "clicks": {"$sum": "$clicks"},
            "spend": {"$sum": "$spend"},
            "conversions": {"$sum": "$conversions"},
            "revenue": {"$sum": "$revenue"},
        }},
    ]
    docs = list(get_collection("performance_snapshots").aggregate(pipeline))
    if not docs:
        return {"impressions": 0, "clicks": 0, "spend": 0.0, "conversions": 0, "revenue": 0.0, "ctr": 0.0, "cpc": 0.0, "roas": 0.0}
    d = docs[0]
    impressions = d.get("impressions", 0)
    clicks = d.get("clicks", 0)
    spend = d.get("spend", 0.0)
    revenue = d.get("revenue", 0.0)
    return {
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "conversions": d.get("conversions", 0),
        "revenue": revenue,
        "ctr": (clicks / impressions) if impressions else 0.0,
        "cpc": (spend / clicks) if clicks else 0.0,
        "roas": (revenue / spend) if spend else 0.0,
    }


# --- Agent Decisions ---

def insert_decision(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("agent_decisions").insert_one(doc)
    return str(result.inserted_id)


def get_pending_decisions() -> list:
    cursor = get_collection("agent_decisions").find(
        {"status": "pending"}, {"_id": 0}
    ).sort("created_at", -1)
    return list(cursor)


def update_decision_status(decision_id: str, status: str) -> None:
    from bson import ObjectId
    get_collection("agent_decisions").update_one(
        {"_id": ObjectId(decision_id)},
        {"$set": {"status": status, "executed_at": _now()}},
    )


# --- Market Events ---

def insert_market_event(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("market_events").insert_one(doc)
    return str(result.inserted_id)


def get_recent_market_events(limit: int = 20) -> list:
    cursor = get_collection("market_events").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return list(cursor)


# --- Campaign Cycles ---

def insert_cycle(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("campaign_cycles").insert_one(doc)
    return str(result.inserted_id)


def update_cycle(cycle_id: str, updates: dict) -> None:
    updates["updated_at"] = _now()
    get_collection("campaign_cycles").update_one(
        {"cycle_id": cycle_id},
        {"$set": updates},
    )


def get_latest_cycle(platform: str = None) -> dict:
    query = {}
    if platform:
        query["platform"] = platform
    return get_collection("campaign_cycles").find_one(
        query, {"_id": 0}, sort=[("created_at", -1)]
    )


def get_cycle_by_id(cycle_id: str) -> dict:
    return get_collection("campaign_cycles").find_one(
        {"cycle_id": cycle_id}, {"_id": 0}
    )


def get_campaign_timeseries(campaign_id: str, days: int = 30) -> list:
    """캠페인의 일별 성과 시계열"""
    from datetime import timedelta
    cutoff = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"campaign_id": campaign_id, "date": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$date",
            "impressions": {"$sum": "$impressions"},
            "clicks": {"$sum": "$clicks"},
            "spend": {"$sum": "$spend"},
            "conversions": {"$sum": "$conversions"},
            "revenue": {"$sum": "$revenue"},
        }},
        {"$sort": {"_id": 1}},
    ]
    result = []
    for row in get_collection("performance_snapshots").aggregate(pipeline):
        impressions = row.get("impressions", 0)
        clicks = row.get("clicks", 0)
        spend = row.get("spend", 0.0)
        result.append({
            "date": row["_id"],
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": row.get("conversions", 0),
            "revenue": row.get("revenue", 0.0),
            "ctr": (clicks / impressions) if impressions else 0.0,
            "cpc": (spend / clicks) if clicks else 0.0,
        })
    return result


def get_campaign_summary(campaign_id: str, days: int = 30) -> dict:
    """캠페인 누적 지표 요약"""
    from datetime import timedelta
    cutoff = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"campaign_id": campaign_id, "date": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$campaign_id",
            "campaign_name": {"$last": "$campaign_name"},
            "platform": {"$last": "$platform"},
            "impressions": {"$sum": "$impressions"},
            "clicks": {"$sum": "$clicks"},
            "spend": {"$sum": "$spend"},
            "conversions": {"$sum": "$conversions"},
            "revenue": {"$sum": "$revenue"},
            "first_date": {"$min": "$date"},
            "last_date": {"$max": "$date"},
        }},
    ]
    docs = list(get_collection("performance_snapshots").aggregate(pipeline))
    if not docs:
        return {}
    d = docs[0]
    impressions = d.get("impressions", 0)
    clicks = d.get("clicks", 0)
    spend = d.get("spend", 0.0)
    revenue = d.get("revenue", 0.0)
    return {
        "campaign_id": d["_id"],
        "campaign_name": d.get("campaign_name", ""),
        "platform": d.get("platform", ""),
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "conversions": d.get("conversions", 0),
        "revenue": revenue,
        "ctr": (clicks / impressions) if impressions else 0.0,
        "cpc": (spend / clicks) if clicks else 0.0,
        "roas": (revenue / spend) if spend else 0.0,
        "first_date": d.get("first_date", ""),
        "last_date": d.get("last_date", ""),
    }


# --- Characters ---

def upsert_character(doc: dict) -> None:
    doc["updated_at"] = _now()
    get_collection("characters").update_one(
        {"name": doc["name"]},
        {"$set": doc, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


def get_active_characters(platform: str = None) -> list:
    query = {"active": True}
    if platform:
        query["platform"] = platform
    cursor = get_collection("characters").find(query, {"_id": 0})
    return list(cursor)


# --- Viral Activities ---

def insert_viral_activity(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("viral_activities").insert_one(doc)
    return str(result.inserted_id)


# --- Published Content ---

def insert_published_content(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("published_content").insert_one(doc)
    return str(result.inserted_id)


# --- Daily Reports ---

def upsert_daily_report(date_str: str, report: dict) -> None:
    report["date"] = date_str
    report["updated_at"] = _now()
    get_collection("daily_reports").update_one(
        {"date": date_str},
        {"$set": report, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


if __name__ == "__main__":
    init_db()
    # 연결 테스트
    db = get_db()
    print(f"Connected to: {db.name}")
    print(f"Collections: {db.list_collection_names()}")
    print("DB initialized successfully.")
