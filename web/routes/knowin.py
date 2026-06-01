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
from fastapi import APIRouter, Request, Form, BackgroundTasks, Header, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import os
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

# 비트럭 시그널 — 본문·title 에 박혀있으면 즉시 격리.
# 외제 승용차·SUV·일반 승용차 모델명. 트럭 키워드보다 우선 검사.
_NON_TRUCK_KEYWORDS = [
    # 외제 브랜드
    "BMW", "벤츠", "Benz", "아우디", "Audi", "볼보", "Volvo",
    "폭스바겐", "Volkswagen", "포르쉐", "Porsche", "테슬라", "Tesla",
    "재규어", "Jaguar", "랜드로버", "Land Rover", "미니쿠퍼", "MINI",
    "푸조", "Peugeot", "시트로엥", "Citroen", "캐딜락", "Cadillac",
    "포드", "Ford", "쉐보레", "Chevrolet", "지프", "Jeep",
    "렉서스", "Lexus", "토요타", "Toyota", "혼다", "Honda",
    "닛산", "Nissan", "마쓰다", "Mazda", "스바루", "Subaru",
    "인피니티", "Infiniti", "어큐라", "Acura",
    # 외제 모델
    "G30", "520d", "320d", "X5", "X3", "X1", "X6", "X7",
    "A4", "A6", "A8", "A3", "A5", "A7", "Q5", "Q7",
    "E클래스", "S클래스", "C클래스", "GLC", "GLE", "GLS",
    "220d", "200d", "250d", "350d",
    # 국산 SUV·승용
    "산타페", "싼타페", "쏘렌토", "투싼", "스포티지", "셀토스",
    "팰리세이드", "코나", "베뉴", "셀토스", "스토닉",
    "QM6", "QM3", "XM3", "QM5",
    "카니발", "스타리아",
    "그랜저", "소나타", "아반떼", "엑센트", "베르나",
    "K3", "K5", "K7", "K8", "K9", "올뉴", "더뉴",
    "제네시스", "G70", "G80", "G90", "GV70", "GV80",
    "코란도", "티볼리", "렉스턴", "무쏘",
    # 일반 자가용 시그널 (트럭 운전자가 잘 안 쓰는 용어)
    "럭셔리라인스페셜", "익스클루시브", "다이나믹",
]


def _is_truck_topic(text: str) -> bool:
    """본문이 트럭 토픽인지 — negative 우선, positive 보조.

    1. 외제 승용차·SUV 모델명 박혀있으면 즉시 False (격리)
    2. 트럭 키워드 박혀있으면 True (통과)
    3. 둘 다 없으면 False (보수적 격리 — 일반 부품어만 있는 케이스)
    """
    if not text:
        return False
    # 1) Negative 우선
    for nk in _NON_TRUCK_KEYWORDS:
        if nk in text:
            return False
    # 2) Positive
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
    """태스크 종료 — finished_at + 최종 status + Telegram 알림"""
    coll = get_collection("knowin_tasks")
    coll.update_one(
        {"task_id": task_id},
        {"$set": {
            "status": status,
            "finished_at": datetime.now(timezone.utc),
            "error": error,
        }},
    )

    # Telegram 알림 — task 결과 요약
    try:
        from agent.telegram import notify_safe
        t = coll.find_one({"task_id": task_id}, {"_id": 0})
        if not t:
            return
        ttype = t.get("type", "task")
        emoji = {"crawl": "🔍", "match": "🎯", "backfill": "📝", "verify": "✅"}.get(ttype, "🧩")
        if status == "failed":
            notify_safe(
                f"{emoji} {ttype} 실패 — {error or 'unknown'}",
                sender="knowin",
            )
        else:
            # 통계 요약 — type 별 다른 필드
            if ttype == "crawl":
                msg = f"발견 {t.get('found',0)} · 신규 {t.get('inserted',0)} · skip {t.get('skipped',0)}"
            elif ttype == "match":
                msg = f"matched {t.get('matched',0)} · rejected {t.get('rejected',0)} · draft {t.get('draft_ok',0)}/{(t.get('draft_ok',0)+t.get('draft_fail',0))}"
            elif ttype == "backfill":
                msg = f"body ok {t.get('found',0)} · 차단 {t.get('rejected',0)} · 본인답 {t.get('matched',0)} · fail {t.get('skipped',0)}"
            elif ttype == "verify":
                msg = f"verified {t.get('matched',0)} · ghost {t.get('rejected',0)} · fail {t.get('skipped',0)}"
            else:
                msg = f"processed {t.get('processed',0)}/{t.get('total',0)}"
            notify_safe(f"{emoji} {ttype} 완료 — {msg}", sender="knowin", silent=True)
    except Exception:
        pass

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
        # 사용자가 삭제(rejected)·차단(blocked)·트럭아님(off_topic) 처리한 카드는
        # 같은 question_id 가 다른 키워드로 잡혀도 재처리 X.
        TERMINAL_STATUSES = {"posted", "rejected", "blocked", "off_topic"}

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
    # 종료 상태 (rejected/posted/blocked/off_topic) 카드는 백필 skip — status 보호
    _TERMINAL = ["rejected", "posted", "blocked", "off_topic"]
    filt = {
        "$and": [
            {"$or": [{"body_plain": {"$exists": False}}, {"body_plain": ""}, {"body_plain": None}]},
            {"link": {"$exists": True, "$ne": ""}},
            {"status": {"$nin": _TERMINAL}},
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
        # 차단 영역 — status=blocked 로 즉시 격리 (큐에서 자동 제거)
        coll.update_one(
            {"question_id": question_id},
            {"$set": {"status": "blocked"}},
        )
        return JSONResponse(
            {"ok": False, "error": f"답변 차단 영역: {q.get('blocked_reason') or '외부 답변 불가'}"},
            status_code=400,
        )
    text = _question_text(q)
    if not text:
        coll.update_one({"question_id": question_id}, {"$set": {"status": "rejected"}})
        return JSONResponse({"ok": False, "error": "질문 본문 비어있음"}, status_code=400)

    m = match_question(text)
    if not m.matched:
        # RAG 미달 — status=rejected 로 격리 (큐에서 자동 제거)
        coll.update_one(
            {"question_id": question_id},
            {"$set": {"status": "rejected", "matched_score": m.top_score}},
        )
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
def _build_approve_trace(q: dict, draft: Optional[dict], verify_meta, action_label: str = "승인") -> dict:
    """단계별 trace — 텍스트 dump + 구조화 객체.

    action_label: "승인" | "게시 완료" | "재검수" 등. 헤더에 박힘.
    사용자가 trace.text 를 클립보드 복사 → Claude 채팅에 박음 → 클로드 분석.
    """
    body_plain = q.get("body_plain") or ""
    desc = q.get("description_plain") or ""
    lines: list[str] = []
    lines.append(f"=== knowin {action_label} trace (qid={q.get('question_id')}) ===")
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
        lines.append("  (skip — 게시 후 📌 게시 완료 버튼이 검수 박음)")
    else:
        lines.append(f"  fetch URL        : {verify_meta.fetch_url or '?'}")
        lines.append(f"  fetched_at       : {verify_meta.fetched_at or '?'}")
        lines.append(f"  HTTP status      : {verify_meta.http_status or '?'}")
        lines.append(f"  page size        : {verify_meta.page_size:,} bytes")
        lines.append(f"  body fetch ok    : {bool(verify_meta.body)}")
        # 페이지에서 감지한 모든 답변자 마스킹 — 핵심 디버그 정보
        m_list = verify_meta.masked_answerers or []
        lines.append(f"  답변자 마스킹    : {len(m_list)}명")
        if m_list:
            for m in m_list[:20]:
                lines.append(f"    · {m}")
            if len(m_list) > 20:
                lines.append(f"    ... (+{len(m_list)-20}명)")
        else:
            lines.append("    (감지된 답변자 0명 — 답변 없는 페이지 또는 lazy-load)")
        lines.append(f"  본인 매칭 (nors/live): {verify_meta.answered_by or '(매칭 0건)'}")
        lines.append(f"  answer_blocked   : {verify_meta.answer_blocked} ({verify_meta.blocked_reason or '-'})")
        lines.append(f"  → verified       : {verify_meta.already_answered}")
    lines.append("")
    lines.append("[DB update]")
    if verify_meta and verify_meta.already_answered:
        final_status = "posted (검수 통과 — 본인 ID 답변 박힘)"
    elif verify_meta and verify_meta.answer_blocked:
        final_status = "blocked (지식파트너/FAQ 영역 — 답변 게시 자체 불가)"
    elif verify_meta is not None:
        final_status = "approved (게시 대기 또는 ghost — 네이버 차단/캐시/실패)"
    else:
        final_status = "approved (검수 skip — 게시 후 📌 클릭 시 검수)"
    lines.append(f"  status   : approved → {final_status}")
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
    """승인 = 답변 검토 통과 마킹만. 검수 fetch X (게시 후 📌 게시 완료 가 박음).

    빠른 1초 응답. trace 출력에서 [게시 검수] 섹션은 'skip' 으로 박힘.
    """
    coll = get_collection("knowin_questions")
    q = coll.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return JSONResponse({"ok": False, "error": "질문 없음"}, status_code=404)

    now = datetime.now(timezone.utc)
    coll.update_one(
        {"question_id": question_id},
        {"$set": {"status": "approved", "approved_at": now}},
    )
    get_collection("knowin_answers").update_one(
        {"question_id": question_id}, {"$set": {"status": "approved"}}
    )
    q["status"] = "approved"

    draft = get_collection("knowin_answers").find_one({"question_id": question_id}, {"_id": 0})
    return JSONResponse(_build_approve_trace(q, draft, None, action_label="승인"))


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
        "answer_blocked": meta.answer_blocked,
        "blocked_reason": meta.blocked_reason,
        "masked_answerers": meta.masked_answerers,
        "page_size": meta.page_size,
        "fetch_url": meta.fetch_url,
        "fetched_at": meta.fetched_at,
        "http_status": meta.http_status,
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


@router.post("/restore/{question_id}")
async def knowin_restore(question_id: str):
    """ghost·posted·blocked·off_topic 카드를 큐로 복원 (status=approved).

    verify 흔적 (verified/verified_at/posted_at/answered_by/manual_posted/verify_attempts)
    전부 unset. answers 컬렉션도 동기.
    """
    coll = get_collection("knowin_questions")
    r1 = coll.update_one(
        {"question_id": question_id},
        {
            "$set": {"status": "approved"},
            "$unset": {
                "verified": "",
                "verified_at": "",
                "posted_at": "",
                "manual_posted": "",
                "answered_by": "",
                "verify_attempts": "",
                "answer_blocked": "",
                "blocked_reason": "",
            },
        },
    )
    get_collection("knowin_answers").update_one(
        {"question_id": question_id},
        {"$set": {"status": "approved"}, "$unset": {"posted_at": ""}},
    )
    if r1.modified_count == 0:
        return RedirectResponse("/knowin?msg=restore-notfound", status_code=303)
    return RedirectResponse(f"/knowin?msg=restored#q-{question_id}", status_code=303)


@router.post("/recheck-topic")
async def knowin_recheck_topic():
    """body 가진 matched/approved 항목들 토픽 재검사 (page fetch 없이, 빠름).

    토픽 룰 변경 후 옛 큐 정리용. 비트럭 → status=off_topic.
    """
    coll = get_collection("knowin_questions")
    candidates = list(
        coll.find(
            {"status": {"$in": ["matched", "approved"]}},
            {"_id": 1, "question_id": 1, "title_plain": 1, "body_plain": 1, "description_plain": 1},
        )
    )
    moved = kept = 0
    for q in candidates:
        text = ((q.get("title_plain") or "") + " "
                + (q.get("body_plain") or q.get("description_plain") or "")).strip()
        if not _is_truck_topic(text):
            coll.update_one({"_id": q["_id"]}, {"$set": {"status": "off_topic"}})
            moved += 1
        else:
            kept += 1
    return RedirectResponse(
        f"/knowin?msg=recheck-done&moved={moved}&kept={kept}",
        status_code=303,
    )


@router.post("/posted/{question_id}")
async def knowin_posted(question_id: str):
    """사용자가 네이버에 직접 게시했다 마킹 + 즉시 검수.

    검수 결과에 따라 status 분기:
      - 본인 답변 박힘 → posted + verified=true
      - 차단 영역 → blocked
      - 안 박힘 (ghost) → approved 유지 + verified=false (ghost 경고에 뜸)
    """
    coll = get_collection("knowin_questions")
    q = coll.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return JSONResponse({"ok": False, "error": "질문 없음"}, status_code=404)

    now = datetime.now(timezone.utc)
    link = q.get("link") or ""
    verify_meta = None
    if link:
        try:
            verify_meta = fetch_question_meta(link)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("knowin").warning("posted verify fetch 실패 (qid=%s): %s", question_id, e)
            verify_meta = None

    if verify_meta is not None and verify_meta.already_answered:
        # ✅ 검수 통과 — 본인 답변 박힘 확인
        coll.update_one(
            {"question_id": question_id},
            {
                "$set": {
                    "status": "posted",
                    "posted_at": now,
                    "verified": True,
                    "verified_at": now,
                    "answered_by": verify_meta.answered_by,
                    "manual_posted": True,
                },
                "$inc": {"verify_attempts": 1},
            },
        )
        get_collection("knowin_answers").update_one(
            {"question_id": question_id},
            {"$set": {"status": "posted", "posted_at": now}},
        )
        q["status"] = "posted"
    elif verify_meta is not None and verify_meta.answer_blocked:
        # 🚫 차단 영역
        coll.update_one(
            {"question_id": question_id},
            {
                "$set": {
                    "status": "blocked",
                    "answer_blocked": True,
                    "blocked_reason": verify_meta.blocked_reason,
                    "verified": False,
                    "verified_at": now,
                },
                "$inc": {"verify_attempts": 1},
            },
        )
        get_collection("knowin_answers").update_one(
            {"question_id": question_id},
            {"$set": {"status": "blocked"}},
        )
        q["status"] = "blocked"
        q["answer_blocked"] = True
        q["blocked_reason"] = verify_meta.blocked_reason
    elif verify_meta is not None:
        # 👻 Ghost — 페이지 fetch OK 했지만 본인 답변 안 박힘. status=approved 유지.
        coll.update_one(
            {"question_id": question_id},
            {
                "$set": {"verified": False, "verified_at": now},
                "$inc": {"verify_attempts": 1},
            },
        )
        # status 그대로 (approved 또는 matched) — ghost 경고에 뜸
    else:
        # fetch 실패 — 옛 동작 폴백 (단순 posted 마킹)
        coll.update_one(
            {"question_id": question_id},
            {"$set": {"status": "posted", "posted_at": now, "manual_posted": True}},
        )
        get_collection("knowin_answers").update_one(
            {"question_id": question_id},
            {"$set": {"status": "posted", "posted_at": now}},
        )
        q["status"] = "posted"

    draft = get_collection("knowin_answers").find_one({"question_id": question_id}, {"_id": 0})

    # Telegram 알림 — 게시 결과
    try:
        from agent.telegram import notify_safe
        title = (q.get("title_plain") or "")[:60]
        if verify_meta is None:
            notify_safe(f"📌 게시 마킹 (검수 skip) — {title}", sender="knowin", silent=True)
        elif verify_meta.already_answered:
            notify_safe(f"✅ 게시 확인 — {title} (답변자: {verify_meta.answered_by})", sender="knowin")
        elif verify_meta.answer_blocked:
            notify_safe(f"🚫 차단 영역 — {title} ({verify_meta.blocked_reason})", sender="knowin")
        else:
            notify_safe(f"👻 Ghost (게시 후 안 박힘) — {title} · 원본: {q.get('link','')}", sender="knowin")
    except Exception:
        pass

    return JSONResponse(_build_approve_trace(q, draft, verify_meta, action_label="게시 완료"))


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
    """카드 삭제 — status=rejected 박음. 종료 상태라 재수집 시 자동 skip.

    답변 차단/RAG 미달/일반 거절 모두 동일 흐름 — 큐에서 사라짐.
    """
    get_collection("knowin_questions").update_one(
        {"question_id": question_id}, {"$set": {"status": "rejected"}}
    )
    return RedirectResponse("/knowin?msg=deleted", status_code=303)


# ════════════════════════════════════════════════════════════
# 자동 게시 Worker API (본인 PC Playwright worker 가 호출)
# ════════════════════════════════════════════════════════════
#
# 흐름:
#   1. 사용자가 카드 '🤖 자동 게시 큐' 클릭 → POST /knowin/queue-post/{qid}
#      → knowin_post_queue insert (status=queued)
#   2. 본인 PC worker 가 poll → GET /knowin/post-queue/next
#      → 한 건 dequeue (status=in_progress, worker_id 박힘)
#   3. worker 가 Playwright 로 네이버 form 박기 + 등록
#   4. 결과 보고 → POST /knowin/post-queue/report/{job_id}
#      → status=done/failed/captcha-stop. done 이면 knowin_questions 도 검수 트리거.
#
# 인증: X-Worker-Key 헤더 — env KNOWIN_WORKER_API_KEY 와 비교
# 미설정 시 모든 endpoint 401

def _check_worker_auth(x_worker_key: Optional[str]) -> None:
    expected = os.getenv("KNOWIN_WORKER_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="KNOWIN_WORKER_API_KEY 미설정 (Railway env)")
    if not x_worker_key or x_worker_key != expected:
        raise HTTPException(status_code=401, detail="invalid worker key")


@router.post("/queue-post/{question_id}")
async def knowin_queue_post(question_id: str, account: str = Form("auto")):
    """카드에서 '🤖 자동 게시 큐' 누르면 호출. 큐에 작업 박음.

    account: 'auto' (worker 가 결정) | 'nors' | 'live'
    """
    coll_q = get_collection("knowin_questions")
    q = coll_q.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        return RedirectResponse("/knowin?msg=queue-error&reason=notfound", status_code=303)

    # 답변 초안 있어야 함
    draft = get_collection("knowin_answers").find_one({"question_id": question_id}, {"_id": 0})
    if not draft or not draft.get("full_text"):
        return RedirectResponse("/knowin?msg=queue-error&reason=nodraft", status_code=303)

    # 차단 영역·이미 답변·off_topic 큐에 박지 X
    if q.get("answer_blocked") or q.get("already_answered") or q.get("status") in ("blocked", "off_topic", "posted"):
        return RedirectResponse(
            f"/knowin?msg=queue-error&reason=status&status={q.get('status')}",
            status_code=303,
        )

    # 이미 큐에 있는지 (queued or in_progress)
    qcoll = get_collection("knowin_post_queue")
    existing = qcoll.find_one({
        "question_id": question_id,
        "status": {"$in": ["queued", "in_progress"]},
    })
    if existing:
        return RedirectResponse(
            f"/knowin?msg=queue-error&reason=dup&job={existing.get('job_id')}",
            status_code=303,
        )

    job_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    qcoll.insert_one({
        "job_id": job_id,
        "question_id": question_id,
        "link": q.get("link"),
        "title_plain": q.get("title_plain"),
        "full_text": draft.get("full_text"),
        "account": account,         # auto | nors | live
        "status": "queued",
        "queued_at": now,
        "started_at": None,
        "finished_at": None,
        "worker_id": None,
        "error": None,
        "captcha_at": None,
    })
    return RedirectResponse(f"/knowin?msg=queued&job={job_id}#q-{question_id}", status_code=303)


@router.get("/post-queue/next")
async def knowin_post_queue_next(
    worker_id: str,
    account: str = "any",
    x_worker_key: Optional[str] = Header(None, alias="X-Worker-Key"),
):
    """Worker poll — 다음 작업 dequeue.

    account: 'any' | 'nors' | 'live' — worker 가 로그인한 계정 명시.
    """
    _check_worker_auth(x_worker_key)
    qcoll = get_collection("knowin_post_queue")

    # 조건: status=queued. account='any' 면 모두, 그 외엔 account=='auto' or 일치
    filt: dict = {"status": "queued"}
    if account != "any":
        filt["account"] = {"$in": ["auto", account]}

    now = datetime.now(timezone.utc)
    doc = qcoll.find_one_and_update(
        filt,
        {"$set": {"status": "in_progress", "started_at": now, "worker_id": worker_id}},
        sort=[("queued_at", 1)],
        return_document=True,  # type: ignore
    )
    if not doc:
        return JSONResponse({"job": None})
    doc.pop("_id", None)
    for k in ("queued_at", "started_at", "finished_at", "captcha_at"):
        if doc.get(k) and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return JSONResponse({"job": doc})


@router.post("/post-queue/report/{job_id}")
async def knowin_post_queue_report(
    job_id: str,
    result: str = Form(...),   # 'done' | 'failed' | 'captcha-stop'
    error: str = Form(""),
    posted_account: str = Form(""),   # worker 가 실제 박은 계정 (nors/live)
    x_worker_key: Optional[str] = Header(None, alias="X-Worker-Key"),
):
    """Worker 결과 보고. done 이면 knowin_questions 도 검수 트리거."""
    _check_worker_auth(x_worker_key)
    if result not in ("done", "failed", "captcha-stop"):
        raise HTTPException(status_code=400, detail="invalid result")

    qcoll = get_collection("knowin_post_queue")
    now = datetime.now(timezone.utc)
    update: dict = {"status": result, "finished_at": now}
    if error:
        update["error"] = error
    if posted_account:
        update["posted_account"] = posted_account
    if result == "captcha-stop":
        update["captcha_at"] = now
    qcoll.update_one({"job_id": job_id}, {"$set": update})

    job = qcoll.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    # done 이면 knowin_questions 도 fetch + verify 트리거
    if result == "done":
        qid = job.get("question_id")
        link = job.get("link") or ""
        if link:
            try:
                meta = fetch_question_meta(link)
            except Exception:
                meta = None
            if meta is not None:
                update_q: dict = {"verified_at": now}
                if meta.already_answered:
                    update_q.update({
                        "status": "posted",
                        "posted_at": now,
                        "verified": True,
                        "answered_by": meta.answered_by,
                        "auto_posted": True,
                    })
                    get_collection("knowin_answers").update_one(
                        {"question_id": qid},
                        {"$set": {"status": "posted", "posted_at": now}},
                    )
                else:
                    # worker 가 등록 성공했다고 보고했는데 페이지엔 안 박힘 = 노출 지연 또는 보류
                    update_q["verified"] = False
                get_collection("knowin_questions").update_one(
                    {"question_id": qid}, {"$set": update_q, "$inc": {"verify_attempts": 1}}
                )

    return JSONResponse({"ok": True, "job_id": job_id, "status": result})


@router.get("/post-queue/list")
async def knowin_post_queue_list():
    """UI 용 큐 상태 조회 (auth 불요 — 내부 모니터링)"""
    qcoll = get_collection("knowin_post_queue")

    # 최근 50건 (모든 status)
    rows = list(
        qcoll.find({}, {"_id": 0}).sort("queued_at", -1).limit(50)
    )
    for r in rows:
        for k in ("queued_at", "started_at", "finished_at", "captcha_at"):
            if r.get(k) and hasattr(r[k], "isoformat"):
                r[k] = r[k].isoformat()
        # full_text 너무 길어서 잘라 보냄
        if r.get("full_text"):
            r["full_text_preview"] = r["full_text"][:200]
            del r["full_text"]

    # 통계
    counts = {
        s: qcoll.count_documents({"status": s})
        for s in ("queued", "in_progress", "done", "failed", "captcha-stop")
    }
    # 오늘 done 카운트 (일 한도 추적)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    counts["today_done"] = qcoll.count_documents({
        "status": "done",
        "finished_at": {"$gte": today_start},
    })

    return JSONResponse({"jobs": rows, "counts": counts})
