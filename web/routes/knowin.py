"""
네이버 지식인 자동 답글 — Phase 1 (수동 검토)

흐름:
  1. /knowin       — 큐 현황 + 검색 트리거 + 매칭 트리거
  2. /knowin/match — 미매칭 큐 → RAG 매칭 → 점수 갱신
  3. /knowin/draft?qid=... — 답변 초안 생성
  4. /knowin/approve?qid=... — 승인 (게시는 수동)
  5. /knowin/crawl  — 키워드 풀로 batch 검색 (수동 트리거)

⚠️ 자동 게시 X — 첫 단계는 검토 큐만.
"""
from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import uuid

from storage.db import get_collection
from agent.knowin_matcher import match_question
from agent.knowin_answerer import generate_answer
from agent.knowin_keyword_pool import build_keyword_pool, keyword_pool_stats


# ── 태스크 진행도 헬퍼 ─────────────────────────────────────
def _task_start(task_type: str, total: int) -> str:
    """태스크 시작 — task_id 발급 + MongoDB insert"""
    task_id = uuid.uuid4().hex[:12]
    get_collection("knowin_tasks").insert_one({
        "task_id": task_id,
        "type": task_type,         # 'crawl' | 'match'
        "status": "running",
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "total": total,
        "processed": 0,
        "found": 0,                # crawl 시 누적 발견 수
        "inserted": 0,             # crawl 시 신규 insert
        "matched": 0,              # match 시 matched 카운트
        "rejected": 0,             # match 시 rejected 카운트
        "current_item": None,
        "error": None,
    })
    return task_id


def _task_update(task_id: str, **fields):
    """진행 상태 갱신 — increment 가능 필드는 `$inc_*` 키로 박음"""
    inc = {}
    set_ = {}
    for k, v in fields.items():
        if k.startswith("inc_"):
            inc[k[4:]] = v
        else:
            set_[k] = v
    update = {}
    if set_:
        update["$set"] = set_
    if inc:
        update["$inc"] = inc
    if update:
        get_collection("knowin_tasks").update_one({"task_id": task_id}, update)


def _task_finish(task_id: str, status: str = "completed", error: str = None):
    """태스크 종료 — finished_at + 최종 status"""
    get_collection("knowin_tasks").update_one(
        {"task_id": task_id},
        {"$set": {
            "status": status,
            "finished_at": datetime.now(timezone.utc),
            "error": error,
        }},
    )

router = APIRouter(prefix="/knowin")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# 표면별 지식인 작전 — 추후 MongoDB knowin_campaigns 컬렉션으로 이관
SURFACE_CAMPAIGNS = [
    {
        "id": "truck",
        "surface": "truck.qcat.kr",
        "keywords_count_est": "3,858 (위키 + 일반어)",
        "answer_link_base": "https://truck.qcat.kr/wiki",
        "persona": "양자냥 (X — 답변 익명)",
        "status": "🟡 Phase 1 (수동 검토)",
        "expected_volume": "일 5~10건 답변",
        "notes": "공식 검색 API 활용, 수동 검토 후 클립보드 복사 게시",
    },
    {
        "id": "qcat-guide",
        "surface": "qcat-guide",
        "keywords_count_est": "Phase 2 예정",
        "answer_link_base": "https://guide.qcat.kr",
        "persona": "양자냥 (X — 답변 익명)",
        "status": "🟢 미가동",
        "expected_volume": "캠핑 시즌 집중",
        "notes": "캠핑·배터리·히터 키워드 별도 풀",
    },
    {
        "id": "liveon",
        "surface": "shoppingliveon.com",
        "keywords_count_est": "Phase 2 예정",
        "answer_link_base": "https://shoppingliveon.com",
        "persona": "도라미 (X — 답변 익명)",
        "status": "🟢 미가동 (페이업 통과 후)",
        "expected_volume": "주 10~20건",
        "notes": "베타 — 답변 보수적",
    },
]


GUARDRAILS = [
    "네이버 공식 검색 API 사용 (feedback_naver_unofficial_caution 정책 준수)",
    "답변 본문 5문장 이상 + 구체 정보 — '자세한 건 링크' 금지",
    "출처 박스 형식 통일 (트럭의 기사 위키 [URL])",
    "일 5~10건 한도 (반복 패턴 회피)",
    "페르소나 박지 X — 익명 정보 제공자 톤",
    "광고성 표현 금지 ('최고', '1위', '절대 안전' 등)",
    "수동 검토 첫 2주 (자동 게시 X)",
    "답변자 계정 트럭 카테고리 전문성 누적",
]


# ── 큐 현황 ─────────────────────────────────────────────────
@router.get("")
async def knowin_overview(request: Request):
    coll = get_collection("knowin_questions")
    stats = {
        "total": coll.estimated_document_count(),
        "pending": coll.count_documents({"status": "pending"}),
        "matched": coll.count_documents({"status": "matched"}),
        "rejected": coll.count_documents({"status": "rejected"}),
        "answered": coll.count_documents({"status": "answered"}),
    }
    # 매칭 점수 높은 후보 큐 (상위 20)
    queue = list(
        coll.find({"status": "matched"}, {"_id": 0}).sort("matched_score", -1).limit(20)
    )
    kw_stats = keyword_pool_stats()

    return templates.TemplateResponse(request, "knowin.html", {
        "campaigns": SURFACE_CAMPAIGNS,
        "guardrails": GUARDRAILS,
        "stats": stats,
        "queue": queue,
        "kw_stats": kw_stats,
        "active_count": sum(1 for c in SURFACE_CAMPAIGNS if not c["status"].startswith("🟢")),
        "total_count": len(SURFACE_CAMPAIGNS),
    })


# ── 검색 (네이버 API → MongoDB) ───────────────────────────
def _crawl_task(limit: int):
    """백그라운드 실행 — 키워드 풀 처음 N개로 검색.

    진행 상태를 `knowin_tasks` 컬렉션에 실시간 기록.
    예외는 catch 후 task status=failed.
    """
    import logging, time
    log = logging.getLogger("knowin.crawl")

    pool = build_keyword_pool()
    if not pool:
        log.warning("키워드 풀이 비어있음")
        return

    keywords = pool[:limit]
    task_id = _task_start("crawl", total=len(keywords))
    log.info("[%s] 크롤 시작: %d / %d 키워드", task_id, len(keywords), len(pool))

    try:
        from intelligence.knowin_crawler import NaverKinSearch
        from storage.db import get_collection
        coll = get_collection("knowin_questions")
        api = NaverKinSearch()

        for i, kw in enumerate(keywords):
            _task_update(task_id, current_item=kw, processed=i)
            results = api.search(kw, display=20)
            found_n = len(results)
            inserted_n = 0
            for r in results:
                doc = r.to_doc()
                res = coll.update_one(
                    {"question_id": r.question_id},
                    {"$setOnInsert": doc, "$addToSet": {"matched_keywords": kw}},
                    upsert=True,
                )
                if res.upserted_id:
                    inserted_n += 1
            _task_update(task_id, inc_found=found_n, inc_inserted=inserted_n)
            time.sleep(0.2)  # throttle

        _task_update(task_id, processed=len(keywords), current_item=None)
        _task_finish(task_id, "completed")
        log.info("[%s] 크롤 완료", task_id)
    except RuntimeError as e:
        log.error("[%s] 크롤 실패 (환경): %s", task_id, e)
        _task_finish(task_id, "failed", error=str(e))
    except Exception as e:
        log.exception("[%s] 크롤 실패 (예상 외): %s", task_id, e)
        _task_finish(task_id, "failed", error=str(e))


@router.post("/crawl")
async def knowin_crawl(
    background: BackgroundTasks,
    limit: int = Form(20),
):
    """키워드 풀 batch 검색 (백그라운드)"""
    background.add_task(_crawl_task, limit)
    return RedirectResponse("/knowin?msg=crawl-started", status_code=303)


# ── 매칭 (pending 큐 → RAG score) ───────────────────────────
def _match_task(limit: int):
    """pending 질문들 → RAG 매칭 → status 갱신. 진행 상태 기록."""
    import logging
    log = logging.getLogger("knowin.match")
    coll = get_collection("knowin_questions")

    pending_n = coll.count_documents({"status": "pending"})
    will_process = min(limit, pending_n)
    task_id = _task_start("match", total=will_process)
    log.info("[%s] 매칭 시작: %d 건", task_id, will_process)

    try:
        cursor = coll.find({"status": "pending"}).limit(limit)
        for i, q in enumerate(cursor):
            text = (q.get("title_plain") or "") + " " + (q.get("description_plain") or "")
            text = text.strip()
            _task_update(task_id, current_item=text[:60], processed=i)
            if not text:
                coll.update_one({"_id": q["_id"]}, {"$set": {"status": "rejected"}})
                _task_update(task_id, inc_rejected=1)
                continue
            m = match_question(text)
            if m.matched:
                coll.update_one(
                    {"_id": q["_id"]},
                    {"$set": {
                        "status": "matched",
                        "matched_url": m.url,
                        "matched_score": m.top_score,
                        "matched_title": m.title,
                        "matched_at": datetime.now(timezone.utc),
                    }},
                )
                _task_update(task_id, inc_matched=1)
            else:
                coll.update_one({"_id": q["_id"]}, {"$set": {"status": "rejected", "matched_score": m.top_score}})
                _task_update(task_id, inc_rejected=1)

        _task_update(task_id, processed=will_process, current_item=None)
        _task_finish(task_id, "completed")
        log.info("[%s] 매칭 완료", task_id)
    except Exception as e:
        log.exception("[%s] 매칭 실패: %s", task_id, e)
        _task_finish(task_id, "failed", error=str(e))


@router.post("/match")
async def knowin_match(
    background: BackgroundTasks,
    limit: int = Form(50),
):
    """pending 큐 매칭 실행 (백그라운드)"""
    background.add_task(_match_task, limit)
    return RedirectResponse("/knowin?msg=match-started", status_code=303)


# ── 태스크 상태 JSON (UI auto-refresh) ─────────────────────
@router.get("/tasks")
async def knowin_tasks_status():
    """진행 중 + 최근 완료 5건. UI 폴링용."""
    coll = get_collection("knowin_tasks")
    running = list(coll.find({"status": "running"}, {"_id": 0}).sort("started_at", -1))
    recent = list(coll.find(
        {"status": {"$in": ["completed", "failed"]}},
        {"_id": 0}
    ).sort("finished_at", -1).limit(5))
    # 큐 통계 같이 반환 (UI 한 번에 갱신)
    qcoll = get_collection("knowin_questions")
    queue_stats = {
        "total": qcoll.estimated_document_count(),
        "pending": qcoll.count_documents({"status": "pending"}),
        "matched": qcoll.count_documents({"status": "matched"}),
        "rejected": qcoll.count_documents({"status": "rejected"}),
        "answered": qcoll.count_documents({"status": "answered"}),
    }
    # datetime → isoformat
    def _serialize(t):
        for k in ("started_at", "finished_at"):
            if t.get(k):
                t[k] = t[k].isoformat()
        return t
    return JSONResponse({
        "running": [_serialize(t) for t in running],
        "recent": [_serialize(t) for t in recent],
        "queue": queue_stats,
    })


# ── 답변 초안 생성 ──────────────────────────────────────────
@router.get("/draft/{question_id}")
async def knowin_draft(request: Request, question_id: str):
    coll = get_collection("knowin_questions")
    q = coll.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return templates.TemplateResponse(request, "knowin_draft.html", {
            "error": "질문 없음", "question_id": question_id,
        })

    # 답변 초안 — 이미 생성된 게 있으면 가져오고, 없으면 새로 생성
    answers = get_collection("knowin_answers")
    existing = answers.find_one({"question_id": question_id}, {"_id": 0})

    draft = None
    if existing:
        draft = existing
    else:
        text = (q.get("title_plain") or "") + " " + (q.get("description_plain") or "")
        m = match_question(text)
        if not m.matched:
            return templates.TemplateResponse(request, "knowin_draft.html", {
                "error": "RAG 매칭 미달", "question": q,
            })
        try:
            llm = "local"  # 로컬 vLLM 우선 (비용 0)
            answer = generate_answer(text, m, llm=llm)
        except Exception as e:
            return templates.TemplateResponse(request, "knowin_draft.html", {
                "error": f"LLM 호출 실패: {e}", "question": q,
            })
        draft = {
            "question_id": question_id,
            "body": answer.body,
            "full_text": answer.full_text,
            "source_url": answer.source_url,
            "source_title": answer.source_title,
            "match_score": answer.match_score,
            "word_count": answer.word_count,
            "sentence_count": answer.sentence_count,
            "llm_model": answer.llm_model,
            "warnings": answer.warnings,
            "status": "draft",
            "created_at": datetime.now(timezone.utc),
        }
        answers.insert_one(dict(draft))

    return templates.TemplateResponse(request, "knowin_draft.html", {
        "question": q, "draft": draft,
    })


# ── 승인·거절 ────────────────────────────────────────────────
@router.post("/approve/{question_id}")
async def knowin_approve(question_id: str):
    get_collection("knowin_questions").update_one(
        {"question_id": question_id}, {"$set": {"status": "approved"}}
    )
    get_collection("knowin_answers").update_one(
        {"question_id": question_id}, {"$set": {"status": "approved"}}
    )
    return RedirectResponse(f"/knowin/draft/{question_id}?msg=approved", status_code=303)


@router.post("/reject/{question_id}")
async def knowin_reject(question_id: str):
    get_collection("knowin_questions").update_one(
        {"question_id": question_id}, {"$set": {"status": "rejected"}}
    )
    return RedirectResponse("/knowin?msg=rejected", status_code=303)
