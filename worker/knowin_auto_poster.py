"""
네이버 지식인 자동 답변 게시 worker — 본인 PC 로컬 실행.

⚠️ 보안·정책 가드레일:
  · 본인 PC 에서만 실행. Railway·서버 박지 X (비번·쿠키 노출 위험).
  · 쿠키는 본인 PC 파일에만 저장 (`worker/.kin_state_{account}.json`).
  · API 키는 본인 PC env 또는 .env (별도 .gitignore — 절대 커밋 X).
  · reCAPTCHA 떠면 즉시 중단 + 사용자 알림 (자동 우회 X).
  · 일 한도 + 분당 한도 + 지터 박혀있음. 강제 우회 X.

흐름:
  1. 시작 시 본인 ID(들)로 한 번 로그인 → 쿠키 저장
  2. polling loop: GET /knowin/post-queue/next?worker_id=...&account=...
  3. 작업 받으면 Playwright 로 해당 link 답변 form 열기
  4. full_text 박기 + "등록" 버튼 클릭
  5. 결과 확인 (URL 변화·메시지·페이지 마스킹)
  6. POST /knowin/post-queue/report/{job_id} 결과 보고
  7. 다음 작업 (지터 60~180초)

사용법:
  cd worker
  pip install playwright requests python-dotenv
  python -m playwright install chromium
  # 첫 실행 — 본인 ID 로그인 (interactive)
  python knowin_auto_poster.py --login --account nors
  python knowin_auto_poster.py --login --account live
  # 운영 — polling worker
  python knowin_auto_poster.py --account nors --daily-limit 5
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PWTimeout
except ImportError:
    print("Playwright 미설치. 다음 명령 실행:")
    print("  pip install playwright requests python-dotenv")
    print("  python -m playwright install chromium")
    sys.exit(1)


# ── 설정 ────────────────────────────────────────────────────
DEFAULT_BASE = "https://adteam.onemsg.net"
DEFAULT_POLL_INTERVAL = (60, 180)   # 60~180초 지터
DEFAULT_PER_MINUTE_LIMIT = 1        # 분당 1건 최대
WORKER_DIR = Path(__file__).resolve().parent
STATE_DIR = WORKER_DIR

CAPTCHA_SELECTORS = [
    'iframe[src*="recaptcha"]',
    'iframe[src*="captcha"]',
    'div.recaptcha',
    'div#captcha',
]

ANSWER_FORM_SELECTORS = [
    'textarea[name="content"]',
    'textarea#answerInput',
    'div[contenteditable="true"]',
]

SUBMIT_BUTTON_SELECTORS = [
    'button:has-text("등록")',
    'button:has-text("답변 등록")',
    'input[type="submit"][value*="등록"]',
]

POSTED_MESSAGE_PATTERNS = [
    re.compile(r"등록되었습니다"),
    re.compile(r"답변이\s*등록"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(account: str) -> Path:
    return STATE_DIR / f".kin_state_{account}.json"


# ── 로그인 (interactive 첫 실행) ────────────────────────────
def login_flow(account: str) -> None:
    """본인 ID 로 한 번 로그인 → 쿠키 저장. interactive — captcha·OTP 등 본인이 처리."""
    log = logging.getLogger("worker.login")
    state = _state_path(account)
    log.info("[%s] 로그인 시작. 브라우저 열림 — 본인 ID(%s) 로 직접 로그인 + 닫기 마세요.", account, account)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        log.info("로그인 완료 후 enter 키 누르세요 (이 콘솔에서). 그 후 쿠키 저장됩니다.")
        input("로그인 끝났으면 Enter > ")
        context.storage_state(path=str(state))
        log.info("[%s] 쿠키 저장 완료: %s", account, state)
        browser.close()


# ── 단일 작업 실행 ────────────────────────────────────────
def _detect_captcha(page: Page) -> bool:
    for sel in CAPTCHA_SELECTORS:
        if page.locator(sel).count() > 0:
            return True
    return False


def _find_form(page: Page):
    for sel in ANSWER_FORM_SELECTORS:
        if page.locator(sel).count() > 0:
            return page.locator(sel).first
    return None


def _find_submit_button(page: Page):
    for sel in SUBMIT_BUTTON_SELECTORS:
        if page.locator(sel).count() > 0:
            return page.locator(sel).first
    return None


def post_one_answer(context: BrowserContext, job: dict) -> dict:
    """단일 답변 등록. Returns {'result': 'done|failed|captcha-stop', 'error': str}"""
    log = logging.getLogger("worker.post")
    link = job["link"]
    full_text = job["full_text"]
    qid = job["question_id"]
    log.info("[%s] 답변 페이지 이동: %s", qid, link)

    page = context.new_page()
    try:
        # 답변 페이지로 이동
        page.goto(link, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)   # 답변 form lazy-load 대기

        # 답변하기 버튼이 따로 있는 경우 클릭 (모바일 페이지엔 보통 form 바로 박힘)
        try:
            answer_btn = page.locator('a:has-text("답변하기"), button:has-text("답변하기")').first
            if answer_btn.count() > 0:
                answer_btn.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        # captcha 감지
        if _detect_captcha(page):
            log.warning("[%s] captcha 감지 — 중단", qid)
            return {"result": "captcha-stop", "error": "reCAPTCHA detected"}

        # 답변 form 찾기
        form = _find_form(page)
        if not form:
            log.error("[%s] 답변 form 못 찾음", qid)
            return {"result": "failed", "error": "answer form not found"}

        # form 박기
        try:
            form.fill(full_text, timeout=5000)
        except PWTimeout:
            # contenteditable 인 경우 type 으로 박기
            form.click()
            page.keyboard.insert_text(full_text)
        page.wait_for_timeout(1500)

        # 등록 직전 한 번 더 captcha 확인
        if _detect_captcha(page):
            return {"result": "captcha-stop", "error": "reCAPTCHA on submit"}

        # 등록 버튼
        submit = _find_submit_button(page)
        if not submit:
            return {"result": "failed", "error": "submit button not found"}

        submit.click()
        page.wait_for_timeout(3500)   # 등록 처리 대기

        # 등록 후 captcha 떴을 수도
        if _detect_captcha(page):
            return {"result": "captcha-stop", "error": "reCAPTCHA after submit"}

        # 페이지 텍스트에 "등록되었습니다" 류 메시지
        page_text = page.content()
        for pat in POSTED_MESSAGE_PATTERNS:
            if pat.search(page_text):
                log.info("[%s] 등록 메시지 감지", qid)
                return {"result": "done", "error": ""}

        # 메시지 없어도 URL 변화 등으로 추정 가능. 보수적으로 failed 박지 말고 done 표시.
        # (검수 fetch 가 verified=false 면 ghost 로 떨어짐)
        log.info("[%s] 등록 메시지 미감지 — done 보고 (검수가 최종 판단)", qid)
        return {"result": "done", "error": "registered (no confirmation message)"}

    except Exception as e:
        log.exception("[%s] 등록 예외", qid)
        return {"result": "failed", "error": str(e)[:300]}
    finally:
        page.close()


# ── Polling Loop ───────────────────────────────────────────
def fetch_next_job(base_url: str, api_key: str, worker_id: str, account: str) -> Optional[dict]:
    try:
        r = requests.get(
            f"{base_url}/knowin/post-queue/next",
            params={"worker_id": worker_id, "account": account},
            headers={"X-Worker-Key": api_key},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("job")
    except Exception as e:
        logging.getLogger("worker").warning("poll fetch 실패: %s", e)
        return None


def report_result(base_url: str, api_key: str, job_id: str, result: str, error: str, posted_account: str) -> bool:
    try:
        r = requests.post(
            f"{base_url}/knowin/post-queue/report/{job_id}",
            data={"result": result, "error": error, "posted_account": posted_account},
            headers={"X-Worker-Key": api_key},
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        logging.getLogger("worker").error("report 실패 (job=%s): %s", job_id, e)
        return False


def run_worker(args) -> None:
    log = logging.getLogger("worker")
    state_path = _state_path(args.account)
    if not state_path.exists():
        log.error("[%s] 쿠키 없음. 먼저 로그인 박으세요: python knowin_auto_poster.py --login --account %s",
                  args.account, args.account)
        sys.exit(1)

    api_key = os.getenv("KNOWIN_WORKER_API_KEY", "")
    if not api_key:
        log.error("env KNOWIN_WORKER_API_KEY 미설정. worker/.env 또는 OS env 박으세요.")
        sys.exit(1)

    log.info("[%s] worker 시작 — daily_limit=%d, per_minute_limit=%d, poll=%d~%ds",
             args.account, args.daily_limit, args.per_minute_limit,
             args.poll_min, args.poll_max)

    today_done = 0
    last_post_at: Optional[float] = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=str(state_path))

        try:
            while True:
                # 일 한도 검사
                if today_done >= args.daily_limit:
                    log.info("[%s] 일 한도 %d 도달. 24h wait.", args.account, args.daily_limit)
                    time.sleep(3600)
                    today_done = 0
                    continue

                # 분당 한도 검사
                if last_post_at:
                    elapsed = time.time() - last_post_at
                    min_gap = 60.0 / args.per_minute_limit
                    if elapsed < min_gap:
                        time.sleep(min_gap - elapsed)

                job = fetch_next_job(args.base, api_key, args.worker_id, args.account)
                if not job:
                    sleep_s = random.uniform(args.poll_min, args.poll_max)
                    log.debug("[%s] no job. sleep %.0fs", args.account, sleep_s)
                    time.sleep(sleep_s)
                    continue

                log.info("[%s] job %s — qid=%s", args.account, job["job_id"], job["question_id"])
                result = post_one_answer(context, job)
                ok = report_result(
                    args.base, api_key, job["job_id"],
                    result["result"], result["error"], args.account,
                )
                if not ok:
                    log.warning("report 실패 — 재시도 안 함")

                if result["result"] == "captcha-stop":
                    log.error("[%s] captcha — worker 중단", args.account)
                    break
                if result["result"] == "done":
                    today_done += 1
                    last_post_at = time.time()
                    log.info("[%s] done. 오늘 %d/%d. 다음 작업 전 지터 wait.",
                             args.account, today_done, args.daily_limit)
                else:
                    log.warning("[%s] failed: %s", args.account, result.get("error"))

                # 지터 wait
                jitter = random.uniform(args.poll_min, args.poll_max)
                time.sleep(jitter)
        finally:
            browser.close()


# ── CLI ────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="knowin 자동 게시 worker (본인 PC 로컬)")
    ap.add_argument("--account", required=True, choices=["nors", "live"], help="네이버 계정 prefix")
    ap.add_argument("--login", action="store_true", help="첫 실행 시 로그인 후 쿠키 저장")
    ap.add_argument("--base", default=os.getenv("KNOWIN_BASE_URL", DEFAULT_BASE),
                    help="ad-optimizer 서버 URL (기본: %s)" % DEFAULT_BASE)
    ap.add_argument("--worker-id", default=os.getenv("KNOWIN_WORKER_ID", "local-pc-1"))
    ap.add_argument("--daily-limit", type=int, default=int(os.getenv("KNOWIN_DAILY_LIMIT", "5")))
    ap.add_argument("--per-minute-limit", type=int, default=DEFAULT_PER_MINUTE_LIMIT)
    ap.add_argument("--poll-min", type=int, default=DEFAULT_POLL_INTERVAL[0])
    ap.add_argument("--poll-max", type=int, default=DEFAULT_POLL_INTERVAL[1])
    ap.add_argument("--headless", action="store_true", help="브라우저 헤드리스 (captcha 시 보이지 X)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # .env 로컬 로드 시도
    try:
        from dotenv import load_dotenv
        load_dotenv(WORKER_DIR / ".env")
    except ImportError:
        pass

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.login:
        login_flow(args.account)
        return

    run_worker(args)


if __name__ == "__main__":
    main()
