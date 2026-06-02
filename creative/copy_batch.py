"""
카피 batch 코어 — 생성 → copy_review_queue 저장 → Telegram 검토 알림.

두 진입점이 공유:
  - 사람: POST /creative/copy/batch       (Basic auth, UI '카피 생성' 버튼)
  - 기계: POST /alerts/copy-batch         (X-Alert-Key, daily routine)

DRY_RUN 본질: 생성물은 검토 큐까지만. 실제 게시는 사람 ✅ 후.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from creative import copy_gen
from storage.db import get_collection
from agent.telegram import notify_safe

log = logging.getLogger(__name__)

# brief 정의는 read-only 파일, 로테이션 상태(last_used)는 DB(copy_brief_state)
BRIEFS_PATH = Path(__file__).resolve().parent / "copy_briefs.json"


def load_briefs() -> List[dict]:
    if not BRIEFS_PATH.exists():
        return []
    data = json.loads(BRIEFS_PATH.read_text(encoding="utf-8"))
    return [b for b in (data.get("briefs") or []) if b.get("id")]


def pick_brief(briefs: List[dict], brief_id: Optional[str]) -> dict:
    """brief_id 지정 시 그것, 아니면 last_used 오래된 순(미사용 우선) 로테이션."""
    if brief_id:
        for b in briefs:
            if b.get("id") == brief_id:
                return b
    state = {s["brief_id"]: s.get("last_used_at")
             for s in get_collection("copy_brief_state").find({}, {"_id": 0})}
    _floor = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(briefs, key=lambda b: (state.get(b["id"]) is not None,
                                         state.get(b["id"]) or _floor))[0]


async def run_copy_batch(brief_id: Optional[str] = None,
                         brief: Optional[dict] = None,
                         provider_id: str = "local-vllm") -> dict:
    """brief 1건 → 카피 생성 → copy_review_queue insert → Telegram. 결과 dict 반환.

    brief 직접 전달 안 하면 풀에서 로테이션. brief 풀 비면 ValueError.
    """
    if not brief:
        briefs = load_briefs()
        if not briefs:
            raise ValueError("brief 풀 비어있음 (creative/copy_briefs.json)")
        brief = pick_brief(briefs, brief_id)
        brief_id = brief.get("id")

    try:
        result = await copy_gen.generate_copy(brief, provider_id)
    except Exception as e:
        log.exception("[copy_batch] generate failed")
        notify_safe(f"❌ 카피 batch 생성 실패 — {brief.get('campaign', brief_id)}: {e}", sender="copy")
        raise

    variants = result.get("variants") or []
    now = datetime.now(timezone.utc)
    batch_id = uuid.uuid4().hex[:12]
    docs = []
    for v in variants:
        docs.append({
            "variant_id": uuid.uuid4().hex[:12],
            "batch_id": batch_id,
            "brief_id": brief_id,
            "campaign": brief.get("campaign"),
            "platform": brief.get("platform"),
            "language": brief.get("language"),
            "variant": v,
            "model": result.get("_meta", {}).get("model"),
            "provider_id": result.get("_meta", {}).get("provider_id"),
            "status": "pending",   # pending → accepted | rejected (게시는 사람 수동)
            "created_at": now,
        })
    if docs:
        get_collection("copy_review_queue").insert_many(docs)
    get_collection("copy_brief_state").update_one(
        {"brief_id": brief_id}, {"$set": {"last_used_at": now}}, upsert=True
    )

    notify_safe(
        f"✍️ 카피 검토 대기 {len(docs)}건\n"
        f"· {brief.get('campaign', '(brief)')}\n"
        f"· {brief.get('platform')} / {brief.get('language')}\n"
        f"검토: /creative/copy/review",
        sender="copy",
    )
    return {"ok": True, "batch_id": batch_id, "count": len(docs),
            "brief_id": brief_id, "model": result.get("_meta", {}).get("model")}
