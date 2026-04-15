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


# --- Performance Snapshots ---

def insert_performance(doc: dict) -> str:
    doc["created_at"] = _now()
    result = get_collection("performance_snapshots").insert_one(doc)
    return str(result.inserted_id)


def get_recent_performance(platform: str = None, days: int = 7) -> list:
    from datetime import timedelta
    cutoff = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    query = {"date": {"$gte": cutoff}}
    if platform:
        query["platform"] = platform
    cursor = get_collection("performance_snapshots").find(
        query, {"_id": 0}
    ).sort("date", -1)
    return list(cursor)


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
