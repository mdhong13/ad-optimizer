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
from intelligence.knowin_body_fetcher import fetch_question_body, fetch_question_meta


# ── 질문 텍스트 정규화 ─────────────────────────────────────
# 네이버 검색 API description 은 검색어 발췌(snippet)라 답변본문이 잡힐 위험.
# body_plain (페이지 직접 fetch) 우선, 없으면 description_plain fallback.

def _question_text(q: dict) -> str:
    """matcher/answerer 에 줄 본문 — body 우선, description 폴백"""
    title = (q.get("title_plain") or "").strip()
    body = (q.get("body_plain") or "").strip() or (q.get("description_plain") or "").strip()
    return (title + " " + body).strip()


# ── 트럭 토픽 필터 ─────────────────────────────────────────
# 키워드 검색이 일반 부품명 (녹스센서/DPF/요소수) 도 포함해서 외제 승용차
# 질문이 큐 절반 이상 차지. 본문에 트럭·화물차 시그널 없으면 격리.
_TRUCK_TOPIC_KEYWORDS = [
    # 차종·톤급
    "트럭", "화물차", "화물자동차", "화물 운송", "화물운송",
    "카고", "윙바디", "윙탑", "탑차", "냉동차", "냉장차",
    "덤프", "압롤", "추레라", "트랙터",
    "1톤", "1.4톤", "2.5톤", "3.5톤", "5톤", "8톤", "9.5톤",
    "11톤", "14톤", "18톤", "25톤", "25.5톤",
    # 트럭 차종 모델
    "포터", "봉고", "리베로", "마이티", "메가트럭", "프리마", "트라고",
    "노부스", "파맥스", "엑시언트", "콘트라스트",
    # 트럭 행정·자격
    "화물자격증", "화물 자격증", "화물운송종사",
    "축중량", "축하중", "과적", "톤급", "총중량", "적재량",
    # 트럭 사업·업종 키워드
    "지입", "용차", "화물기사", "기사님", "운수사업",
]


def _is_truck_topic(text: str) -> bool:
    """본문에 트럭·화물차 시그널 키워드 있는지"""
    if not text:
        return False
    for kw in _TRUCK_TOPIC_KEYWORDS:
        if kw in text:
            return True
    return False


def _ensure_body(q: dict) -> dict:
    """body_plain + answer_blocked + already_answered 없으면 페이지 fetch → DB 저장 + q 갱신.

    이미 확정된 항목은 skip (캐시).
    already_answered (본인 ID 답변 있음) 시 자동 status=posted 마킹.
    """
    if q.get("body_plain") or q.get("answer_blocked") or q.get("already_answered"):
        return q
    link = q.get("link") or ""
    if not link:
        return q
    try:
        meta = fetch_question_meta(link)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("knowin").warning("meta fetch 실패 (qid=%s): %s", q.get("question_id"), e)
        return q

    update: dict = {}
    if meta.body:
        q["body_plain"] = meta.body
        update["body_plain"] = meta.body
    if meta.answer_blocked:
        q["answer_blocked"] = True
        q["blocked_reason"] = meta.blocked_reason
        update["answer_blocked"] = True
        update["blocked_reason"] = meta.blocked_reason
    if meta.already_answered:
        q["already_answered"] = True
        q["answered_by"] = meta.answered_by
        q["status"] = "posted"
        update["already_answered"] = True
        update["answered_by"] = meta.answered_by
        update["status"] = "posted"
        update["posted_at"] = datetime.now(timezone.utc)
        update["manual_posted"] = True   # 자동 감지지만 외부 직접 답변
    if update:
        get_collection("knowin_questions").update_one(
            {"question_id": q.get("question_id")}, {"$set": update}
        )
        # 본인 답변이면 answers 컬렉션도 마킹 (있는 경우)
        if meta.already_answered:
            get_collection("knowin_answers").update_one(
                {"question_id": q.get("question_id")},
                {"$set": {"status": "posted", "posted_at": update["posted_at"]}},
            )
    return q


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
        "skipped": 0,              # crawl 시 종료 status (posted/rejected) 자동 skip
        "matched": 0,              # match 시 matched 카운트
        "rejected": 0,             # match 시 rejected 카운트
        "draft_ok": 0,             # match 시 답변 초안 자동 생성 성공
        "draft_fail": 0,           # match 시 답변 초안 실패 (LLM 등)
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
        "approved": coll.count_documents({"status": "approved"}),
        "posted": coll.count_documents({"status": "posted"}),
        "blocked": coll.count_documents({"status": "blocked"}),
        "off_topic": coll.count_documents({"status": "off_topic"}),
        "verified": coll.count_documents({"status": "posted", "verified": True}),
        "ghost": coll.count_documents({
            "status": {"$in": ["posted", "approved"]},
            "verified": False,
        }),
    }
    # ghost 항목들 (검수 실패 — 네이버에 본인 답변 박혀있지 않음) — 상단 경고용
    ghosts = list(
        coll.find(
            {"status": {"$in": ["posted", "approved"]}, "verified": False},
            {"_id": 0, "question_id": 1, "title_plain": 1, "link": 1, "verify_attempts": 1, "verified_at": 1},
        ).sort("verified_at", -1).limit(10)
    )
    # 매칭 큐 — matched + approved 양쪽 표시 (승인 후에도 게시완료 추적해야 하므로)
    queue = list(
        coll.find(
            {"status": {"$in": ["matched", "approved"]}}, {"_id": 0}
        ).sort("matched_score", -1).limit(20)
    )
    # 답변 본문 bulk fetch — 메인에서 인라인 표시용 (draft 페이지 우회)
    qids = [q.get("question_id") for q in queue if q.get("question_id")]
    answers_map: dict = {}
    if qids:
        answers_map = {
            a["question_id"]: a
            for a in get_collection("knowin_answers").find(
                {"question_id": {"$in": qids}}, {"_id": 0}
            )
        }
    for q in queue:
        q["answer"] = answers_map.get(q.get("question_id"))

    kw_stats = keyword_pool_stats()

    return templates.TemplateResponse(request, "knowin.html", {
        "campaigns": SURFACE_CAMPAIGNS,
        "guardrails": GUARDRAILS,
        "stats": stats,
        "queue": queue,
        "ghosts": ghosts,
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

        # 종료 status — 자동 skip 대상 (재수집 시 큐 오염 방지)
        TERMINAL_STATUSES = {"posted", "rejected"}

        for i, kw in enumerate(keywords):
            _task_update(task_id, current_item=kw, processed=i)
            results = api.search(kw, display=20)
            found_n = len(results)

            # 한 번에 종료 status 인 기존 question_id 미리 fetch (효율)
            qids = [r.question_id for r in results]
            terminal_ids = set()
            if qids:
                terminal_ids = {
                    d["question_id"]
                    for d in coll.find(
                        {"question_id": {"$in": qids}, "status": {"$in": list(TERMINAL_STATUSES)}},
                        {"question_id": 1, "_id": 0},
                    )
                }

            inserted_n = 0
            skipped_n = 0
            for r in results:
                if r.question_id in terminal_ids:
                    skipped_n += 1
                    continue   # posted/rejected 는 재처리 X
                doc = r.to_doc()
                res = coll.update_one(
                    {"question_id": r.question_id},
                    {"$setOnInsert": doc, "$addToSet": {"matched_keywords": kw}},
                    upsert=True,
                )
                if res.upserted_id:
                    inserted_n += 1
            _task_update(task_id, inc_found=found_n, inc_inserted=inserted_n, inc_skipped=skipped_n)
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
            # 1) 진짜 본문 fetch (네이버 description 발췌가 답변본문일 수 있음 — 동문서답 방지)
            #    동시에 답변 차단 영역(지식파트너/FAQ) 검출
            q = _ensure_body(q)
            _task_update(task_id, current_item=(q.get("title_plain") or "")[:60], processed=i)

            # 2a) 본인 ID 이미 답변 → _ensure_body 가 이미 status=posted 박음. skip.
            if q.get("already_answered"):
                _task_update(task_id, inc_rejected=1)
                continue

            # 2b) 답변 차단 영역 → 즉시 격리 (종료 상태)
            if q.get("answer_blocked"):
                coll.update_one(
                    {"_id": q["_id"]},
                    {"$set": {"status": "blocked", "blocked_reason": q.get("blocked_reason")}},
                )
                _task_update(task_id, inc_rejected=1)
                continue

            text = _question_text(q)
            if not text:
                coll.update_one({"_id": q["_id"]}, {"$set": {"status": "rejected"}})
                _task_update(task_id, inc_rejected=1)
                continue

            # 3) 트럭 토픽 필터 — 외제 승용차 등 비트럭 질문 격리
            if not _is_truck_topic(text):
                coll.update_one(
                    {"_id": q["_id"]},
                    {"$set": {"status": "off_topic"}},
                )
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
                # 답변 초안 자동 생성 (사용자가 매치 큐에서 직접 작성 안 해도 OK)
                try:
                    answers = get_collection("knowin_answers")
                    if not answers.find_one({"question_id": q.get("question_id")}, {"_id": 1}):
                        draft = generate_answer(text, m, llm="local")
                        answers.insert_one({
                            "question_id": q.get("question_id"),
                            "body": draft.body,
                            "full_text": draft.full_text,
                            "source_url": draft.source_url,
                            "source_title": draft.source_title,
                            "match_score": draft.match_score,
                            "word_count": draft.word_count,
                            "sentence_count": draft.sentence_count,
                            "llm_model": draft.llm_model,
                            "warnings": draft.warnings,
                            "status": "draft",
                            "created_at": datetime.now(timezone.utc),
                        })
                        _task_update(task_id, inc_draft_ok=1)
                except Exception as draft_e:
                    log.warning("draft 자동 생성 실패 (qid=%s): %s", q.get("question_id"), draft_e)
                    _task_update(task_id, inc_draft_fail=1)
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


# ── 본문 백필 (옛 큐 description-only 항목 보강) ───────────
def _backfill_body_task(limit: int):
    """body_plain 비어있는 항목들 → 페이지 fetch → DB 저장.

    동문서답 위험 1순위: description 발췌가 답변본문일 수 있음.
    matched/approved 우선, 그 다음 pending.
    """
    import logging, time
    log = logging.getLogger("knowin.backfill")
    coll = get_collection("knowin_questions")

    # matched/approved 우선 + pending 다음 (limit 안에서)
    filt = {
        "$and": [
            {"$or": [{"body_plain": {"$exists": False}}, {"body_plain": ""}, {"body_plain": None}]},
            {"link": {"$exists": True, "$ne": ""}},
        ]
    }
    candidates = list(
        coll.find(filt).sort([("status", 1), ("matched_score", -1)]).limit(limit)
    )
    task_id = _task_start("backfill", total=len(candidates))
    log.info("[%s] body 백필 시작: %d 건", task_id, len(candidates))

    ok_n = fail_n = blocked_n = own_n = 0
    try:
        for i, q in enumerate(candidates):
            link = q.get("link") or ""
            _task_update(task_id, current_item=link[:80], processed=i)
            try:
                meta = fetch_question_meta(link)
            except Exception as e:  # noqa: BLE001
                log.warning("fetch 실패 (qid=%s): %s", q.get("question_id"), e)
                meta = None

            if meta is None:
                fail_n += 1
            else:
                update: dict = {}
                now = datetime.now(timezone.utc)
                if meta.body:
                    update["body_plain"] = meta.body
                # 우선순위: already_answered > answer_blocked > off_topic
                if meta.already_answered:
                    update["already_answered"] = True
                    update["answered_by"] = meta.answered_by
                    update["status"] = "posted"
                    update["posted_at"] = now
                    update["manual_posted"] = True
                    own_n += 1
                elif meta.answer_blocked:
                    update["answer_blocked"] = True
                    update["blocked_reason"] = meta.blocked_reason
                    update["status"] = "blocked"
                    blocked_n += 1
                elif meta.body:
                    # body 확보됐고 차단·본인답 아님 — 트럭 토픽 검사
                    text_for_topic = ((q.get("title_plain") or "") + " " + meta.body).strip()
                    if not _is_truck_topic(text_for_topic):
                        update["status"] = "off_topic"
                if update:
                    coll.update_one({"_id": q["_id"]}, {"$set": update})
                    # already_answered 면 answers 컬렉션도 마킹
                    if meta.already_answered:
                        get_collection("knowin_answers").update_one(
                            {"question_id": q.get("question_id")},
                            {"$set": {"status": "posted", "posted_at": now}},
                        )
                if meta.body:
                    ok_n += 1
                elif not (meta.answer_blocked or meta.already_answered):
                    fail_n += 1
            time.sleep(1.0)  # throttle

        _task_update(
            task_id,
            processed=len(candidates),
            current_item=None,
            found=ok_n,
            inserted=ok_n,
            skipped=fail_n,
            rejected=blocked_n,    # 차단 카운트
            matched=own_n,         # already_answered 카운트 (재활용 필드)
        )
        _task_finish(task_id, "completed")
        log.info("[%s] 백필 완료: ok=%d fail=%d blocked=%d own=%d", task_id, ok_n, fail_n, blocked_n, own_n)
    except Exception as e:
        log.exception("[%s] 백필 실패: %s", task_id, e)
        _task_finish(task_id, "failed", error=str(e))


@router.post("/backfill-body")
async def knowin_backfill_body(
    background: BackgroundTasks,
    limit: int = Form(50),
):
    """body_plain 없는 큐 항목 → 페이지 fetch 백그라운드"""
    background.add_task(_backfill_body_task, limit)
    return RedirectResponse("/knowin?msg=backfill-started", status_code=303)


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
        "approved": qcoll.count_documents({"status": "approved"}),
        "posted": qcoll.count_documents({"status": "posted"}),
        "blocked": qcoll.count_documents({"status": "blocked"}),
        "off_topic": qcoll.count_documents({"status": "off_topic"}),
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


# ── 답변 초안 생성 (메인 인라인용 JSON) ────────────────────
def _draft_to_json(d: dict) -> dict:
    """MongoDB doc → JSON-safe dict"""
    out = {k: v for k, v in d.items() if k != "_id"}
    ca = d.get("created_at")
    if ca and hasattr(ca, "isoformat"):
        out["created_at"] = ca.isoformat()
    return out


@router.post("/regenerate/{question_id}")
async def knowin_regenerate(question_id: str):
    """기존 draft 삭제 + 다시 생성. body 백필 후 동문서답 수정용.

    matched/approved 상태에서만 의미 있음. JSON 응답.
    """
    answers = get_collection("knowin_answers")
    answers.delete_one({"question_id": question_id})
    # generate 흐름 그대로 호출
    return await knowin_generate(question_id)


@router.post("/generate/{question_id}")
async def knowin_generate(question_id: str):
    """미생성 답변 초안을 그 자리에서 생성. JSON 응답.

    /knowin 메인의 JS가 미생성 카드별로 직렬 호출 → 카드 교체.
    이미 생성된 경우 그대로 반환 (race condition 안전).
    """
    coll = get_collection("knowin_questions")
    q = coll.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return JSONResponse({"ok": False, "error": "질문 없음"}, status_code=404)

    answers = get_collection("knowin_answers")
    existing = answers.find_one({"question_id": question_id}, {"_id": 0})
    if existing:
        return JSONResponse({"ok": True, "draft": _draft_to_json(existing)})

    q = _ensure_body(q)
    if q.get("answer_blocked"):
        return JSONResponse(
            {"ok": False, "error": f"답변 차단 영역: {q.get('blocked_reason') or '외부 답변 불가'}"},
            status_code=400,
        )
    text = _question_text(q)
    if not text:
        return JSONResponse({"ok": False, "error": "질문 본문 비어있음"}, status_code=400)

    m = match_question(text)
    if not m.matched:
        return JSONResponse(
            {"ok": False, "error": f"RAG 매칭 미달 (score={m.top_score:.3f})"},
            status_code=400,
        )

    try:
        answer = generate_answer(text, m, llm="local")
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"LLM 호출 실패: {e}"}, status_code=500)

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
    return JSONResponse({"ok": True, "draft": _draft_to_json(draft)})


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
        q = _ensure_body(q)
        text = _question_text(q)
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


# ── 승인 trace 빌더 (Claude 세션 디버그용) ────────────────
def _build_approve_trace(q: dict, draft: Optional[dict], verify_meta) -> dict:
    """승인 단계별 trace — 텍스트 dump + 구조화 객체.

    사용자가 trace.text 를 클립보드 복사 → Claude 채팅에 박음 → 클로드 분석.
    """
    body_plain = q.get("body_plain") or ""
    desc = q.get("description_plain") or ""
    lines: list[str] = []
    lines.append(f"=== knowin 승인 trace (qid={q.get('question_id')}) ===")
    lines.append(f"timestamp: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("[질문]")
    lines.append(f"  title    : {(q.get('title_plain') or '')[:200]}")
    lines.append(f"  link     : {q.get('link', '')}")
    lines.append(f"  keyword  : {q.get('keyword', '')}")
    lines.append(f"  date     : {q.get('post_date', '')}")
    lines.append(f"  body_src : {'fetched (m.kin)' if body_plain else 'description-only (snippet — 동문서답 위험)'}")
    if body_plain:
        lines.append(f"  body     : {body_plain[:600]}")
    elif desc:
        lines.append(f"  desc     : {desc[:300]}")
    lines.append(f"  blocked  : {bool(q.get('answer_blocked'))} ({q.get('blocked_reason') or '-'})")
    lines.append(f"  already  : {bool(q.get('already_answered'))} (by {q.get('answered_by') or '-'})")
    lines.append("")
    lines.append("[RAG 매칭]")
    lines.append(f"  url     : {q.get('matched_url') or '-'}")
    lines.append(f"  title   : {q.get('matched_title') or '-'}")
    score = q.get("matched_score") or 0
    lines.append(f"  score   : {score:.3f}" if isinstance(score, (int, float)) else f"  score   : {score}")
    lines.append("")
    if draft:
        lines.append("[답변 초안]")
        lines.append(f"  model       : {draft.get('llm_model') or '?'}")
        msc = draft.get("match_score") or 0
        lines.append(f"  match_score : {msc:.3f}" if isinstance(msc, (int, float)) else f"  match_score : {msc}")
        lines.append(f"  words / sent: {draft.get('word_count', 0)} / {draft.get('sentence_count', 0)}")
        lines.append(f"  warnings    : {draft.get('warnings') or '[]'}")
        lines.append(f"  source_url  : {draft.get('source_url') or '-'}")
        lines.append(f"  body        :")
        lines.append(f"    {(draft.get('body') or '')[:1200]}")
        lines.append("")
    lines.append("[게시 검수 (직후 페이지 fetch)]")
    if verify_meta is None:
        lines.append("  (skip — link 없음 또는 fetch 실패)")
    else:
        lines.append(f"  body fetch ok    : {bool(verify_meta.body)}")
        lines.append(f"  already_answered : {verify_meta.already_answered}")
        lines.append(f"  answered_by      : {verify_meta.answered_by or '(none — 본인 ID 답변 미발견)'}")
        lines.append(f"  answer_blocked   : {verify_meta.answer_blocked}")
        lines.append(f"  → verified       : {verify_meta.already_answered}")
    lines.append("")
    lines.append("[DB update]")
    lines.append(f"  status   : approved → {'posted (검수 통과)' if (verify_meta and verify_meta.already_answered) else 'approved (게시 대기 또는 ghost)'}")
    lines.append(f"  verified : {(verify_meta.already_answered if verify_meta else None)}")

    return {
        "ok": True,
        "trace_id": uuid.uuid4().hex[:12],
        "question_id": q.get("question_id"),
        "verified": (verify_meta.already_answered if verify_meta else None),
        "ghost": (verify_meta is not None and not verify_meta.already_answered and not verify_meta.answer_blocked),
        "body_source": "fetched" if body_plain else "description-only",
        "text": "\n".join(lines),
    }


# ── 승인·거절·게시완료 ──────────────────────────────────────
@router.post("/approve/{question_id}")
async def knowin_approve(question_id: str):
    """승인 + 즉시 게시 검수 + 단계별 trace JSON (Claude 세션 디버그용)"""
    coll = get_collection("knowin_questions")
    q = coll.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return JSONResponse({"ok": False, "error": "질문 없음"}, status_code=404)

    # status 갱신
    now = datetime.now(timezone.utc)
    coll.update_one({"question_id": question_id}, {"$set": {"status": "approved", "approved_at": now}})
    get_collection("knowin_answers").update_one(
        {"question_id": question_id}, {"$set": {"status": "approved"}}
    )
    q["status"] = "approved"

    # 즉시 게시 검수 시도 (페이지에 본인 ID 답변 박혔는지)
    verify_meta = None
    link = q.get("link") or ""
    if link:
        try:
            verify_meta = fetch_question_meta(link)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("knowin").warning("approve verify fetch 실패 (qid=%s): %s", question_id, e)
            verify_meta = None

        if verify_meta is not None:
            update = {"verified": verify_meta.already_answered, "verified_at": now}
            if verify_meta.already_answered:
                update.update({
                    "status": "posted",
                    "posted_at": now,
                    "answered_by": verify_meta.answered_by,
                    "manual_posted": True,
                })
                get_collection("knowin_answers").update_one(
                    {"question_id": question_id},
                    {"$set": {"status": "posted", "posted_at": now}},
                )
                q["status"] = "posted"
            coll.update_one(
                {"question_id": question_id},
                {"$set": update, "$inc": {"verify_attempts": 1}},
            )

    draft = get_collection("knowin_answers").find_one({"question_id": question_id}, {"_id": 0})
    return JSONResponse(_build_approve_trace(q, draft, verify_meta))


@router.post("/verify/{question_id}")
async def knowin_verify_one(question_id: str):
    """단일 게시 검수 — 페이지 재 fetch + already_answered 갱신.

    캐시 지연·재게시 후 사용. ghost (verified=false) 항목을 다시 확인.
    """
    coll = get_collection("knowin_questions")
    q = coll.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return JSONResponse({"ok": False, "error": "질문 없음"}, status_code=404)
    link = q.get("link") or ""
    if not link:
        return JSONResponse({"ok": False, "error": "link 없음"}, status_code=400)

    try:
        meta = fetch_question_meta(link)
    except Exception as e:
        coll.update_one({"question_id": question_id}, {"$inc": {"verify_attempts": 1}})
        return JSONResponse({"ok": False, "error": f"fetch 실패: {e}"}, status_code=502)

    now = datetime.now(timezone.utc)
    update = {"verified": meta.already_answered, "verified_at": now}
    if meta.already_answered:
        update.update({
            "status": "posted",
            "posted_at": now,
            "answered_by": meta.answered_by,
            "manual_posted": True,
        })
        get_collection("knowin_answers").update_one(
            {"question_id": question_id},
            {"$set": {"status": "posted", "posted_at": now}},
        )
    coll.update_one({"question_id": question_id}, {"$set": update, "$inc": {"verify_attempts": 1}})
    return JSONResponse({
        "ok": True,
        "verified": meta.already_answered,
        "answered_by": meta.answered_by,
        "page_fetch_ok": bool(meta.body),
    })


def _verify_all_task():
    """approved+ghost+posted-unverified 일괄 재검수 백그라운드"""
    import logging, time as _time
    log = logging.getLogger("knowin.verify")
    coll = get_collection("knowin_questions")
    candidates = list(
        coll.find(
            {
                "status": {"$in": ["approved", "posted"]},
                "$or": [
                    {"verified": None},
                    {"verified": False},
                    {"verified": {"$exists": False}},
                ],
            },
            {"_id": 0, "question_id": 1, "link": 1},
        ).limit(50)
    )
    task_id = _task_start("verify", total=len(candidates))
    log.info("[%s] verify 시작: %d 건", task_id, len(candidates))
    verified_n = ghost_n = fail_n = 0
    try:
        for i, q in enumerate(candidates):
            link = q.get("link") or ""
            qid = q.get("question_id")
            _task_update(task_id, current_item=str(qid), processed=i)
            meta = None
            if link:
                try:
                    meta = fetch_question_meta(link)
                except Exception:
                    meta = None
            if meta is None:
                fail_n += 1
                coll.update_one({"question_id": qid}, {"$inc": {"verify_attempts": 1}})
            else:
                now = datetime.now(timezone.utc)
                update: dict = {"verified": meta.already_answered, "verified_at": now}
                if meta.already_answered:
                    update.update({
                        "status": "posted",
                        "posted_at": now,
                        "answered_by": meta.answered_by,
                        "manual_posted": True,
                    })
                    verified_n += 1
                    get_collection("knowin_answers").update_one(
                        {"question_id": qid},
                        {"$set": {"status": "posted", "posted_at": now}},
                    )
                else:
                    ghost_n += 1
                coll.update_one({"question_id": qid}, {"$set": update, "$inc": {"verify_attempts": 1}})
            _time.sleep(1.0)
        _task_update(
            task_id,
            processed=len(candidates),
            current_item=None,
            matched=verified_n,
            rejected=ghost_n,
            skipped=fail_n,
        )
        _task_finish(task_id, "completed")
        log.info("[%s] verify 완료: verified=%d ghost=%d fail=%d", task_id, verified_n, ghost_n, fail_n)
    except Exception as e:
        log.exception("[%s] verify 실패: %s", task_id, e)
        _task_finish(task_id, "failed", error=str(e))


@router.post("/verify-all")
async def knowin_verify_all(background: BackgroundTasks):
    background.add_task(_verify_all_task)
    return RedirectResponse("/knowin?msg=verify-started", status_code=303)


@router.post("/posted/{question_id}")
async def knowin_posted(question_id: str):
    """실제 네이버 게시 완료 — 종료 상태 (재수집 시 자동 skip)"""
    now = datetime.now(timezone.utc)
    get_collection("knowin_questions").update_one(
        {"question_id": question_id},
        {"$set": {"status": "posted", "posted_at": now}},
    )
    get_collection("knowin_answers").update_one(
        {"question_id": question_id},
        {"$set": {"status": "posted", "posted_at": now}},
    )
    return RedirectResponse("/knowin?msg=posted", status_code=303)


@router.post("/mark-posted")
async def knowin_mark_posted(link: str = Form(""), question_id: str = Form("")):
    """네이버에 수동으로 직접 게시한 답변을 DB에 posted 마킹.

    link (전체 URL) 또는 question_id (docId) 중 하나 필수.
    DB에 없으면 최소 row 박아서 재수집 시 skip 보장.
    """
    from urllib.parse import urlparse, parse_qs

    qid = (question_id or "").strip()
    lnk = (link or "").strip()

    if not qid and lnk:
        try:
            p = urlparse(lnk)
            qs = parse_qs(p.query)
            qid = (qs.get("docId") or [""])[0]
        except Exception:
            qid = ""

    if not qid:
        return RedirectResponse("/knowin?msg=mark-posted-error", status_code=303)

    now = datetime.now(timezone.utc)
    coll = get_collection("knowin_questions")
    existing = coll.find_one({"question_id": qid}, {"_id": 1})
    if existing:
        coll.update_one(
            {"question_id": qid},
            {"$set": {"status": "posted", "posted_at": now}},
        )
        get_collection("knowin_answers").update_one(
            {"question_id": qid},
            {"$set": {"status": "posted", "posted_at": now}},
        )
        return RedirectResponse(f"/knowin?msg=marked-posted#q-{qid}", status_code=303)

    # DB 에 없는 질문 → 최소 row 박음 (재수집 시 skip 보장)
    coll.insert_one({
        "question_id": qid,
        "link": lnk or f"https://kin.naver.com/qna/detail.naver?docId={qid}",
        "status": "posted",
        "posted_at": now,
        "title_plain": "(수동 등록 — 외부 직접 답변)",
        "manual_posted": True,
        "created_at": now,
    })
    return RedirectResponse("/knowin?msg=marked-posted-new", status_code=303)


@router.post("/reject/{question_id}")
async def knowin_reject(question_id: str):
    get_collection("knowin_questions").update_one(
        {"question_id": question_id}, {"$set": {"status": "rejected"}}
    )
    return RedirectResponse("/knowin?msg=rejected", status_code=303)
