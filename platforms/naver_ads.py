"""
네이버 검색광고 (SearchAd) API — **읽기 전용** 클라이언트

Docs: https://naver.github.io/searchad-apidoc/
원본: qcat/truck/scripts/lib/naverAd.mjs + scripts/ads/history.mjs
      (2026-08-12 실계정 검증 코드를 파이썬으로 이식)

⛔ **AdPlatform ABC 를 일부러 상속하지 않는다.**
   base.AdPlatform 은 create_campaign / update_campaign_budget / pause_campaign 등
   **쓰기 메서드를 @abstractmethod 로 강제**한다. 상속하는 순간 이 파일에 쓰기 경로가
   생기고, 그러면 "허브는 읽기만 한다"는 안전 규칙이 코드 레벨에서 깨진다.
   네이버 쓰기는 qcat/truck/scripts/ads/ 에서 dry-run → 노대표 승인 → --apply 로만 한다.
   그래서 독립 클래스 + GET 전용. POST/PUT/DELETE 는 이 파일에 넣지 않는다.

⚠️ `salesAmt` 는 **광고비**다. 매출이 아니다(네이버 명세). 헷갈리면 ROAS 가 뒤집힌다.
⚠️ 전환매출은 `convAmt` 이고, **전환추적이 설치돼 있어야** 값이 온다. 없으면 0 이 온다 —
   0 이 「안 팔렸다」가 아니라 「측정을 안 하고 있다」일 수 있으니 구별해서 읽을 것.
"""
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.searchad.naver.com"

# /stats 로 요청할 지표. 순서·이름은 네이버 명세 그대로.
#   impCnt=노출 · clkCnt=클릭 · salesAmt=광고비(원) · ccnt=전환수 · convAmt=전환매출(원)
STAT_FIELDS = ["impCnt", "clkCnt", "salesAmt", "ccnt", "convAmt"]

# /stats 는 ids 를 한 번에 무한정 못 받는다. history.mjs 가 실계정에서 쓰는 100개 단위 유지.
STATS_CHUNK = 100

# 네이버 광고 리포트의 기준 시간대는 KST 고정.
# Railway 컨테이너는 UTC 라서 date.today() 를 쓰면 하루가 밀린다 — 명시적으로 KST 를 만든다.
KST = timezone(timedelta(hours=9))


class NaverAds:
    """네이버 검색광고 계정 조회 전용 클라이언트.

    허브 대시보드가 「7일 지출 $0」을 띄우는 동안 실제로는 네이버에서 돈이 나가고 있었다
    (2026-08-17). 이 클래스는 그 구멍을 메우는 **관측용**이다. 집행은 하지 않는다.
    """

    platform_name = "naver"

    # --- 설정 ---

    def is_configured(self) -> bool:
        return bool(
            settings.NAVER_SEARCHAD_CUSTOMER_ID
            and settings.NAVER_SEARCHAD_ACCESS_LICENSE
            and settings.NAVER_SEARCHAD_SECRET_KEY
        )

    # --- 인증 ---

    @staticmethod
    def _sign(method: str, path: str, timestamp: str) -> str:
        """네이버 검색광고 서명.

        message = f"{timestamp}.{method}.{path}" → SECRET_KEY 로 HMAC-SHA256 → base64.
        🩸 **path 만 서명한다 — 쿼리스트링은 제외.** query 를 섞으면 401 이 떨어진다.
        """
        msg = f"{timestamp}.{method}.{path}"
        digest = hmac.new(
            settings.NAVER_SEARCHAD_SECRET_KEY.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _headers(self, method: str, path: str) -> dict:
        # timestamp 는 **밀리초 문자열**. 초 단위로 보내면 서명이 통째로 안 맞는다.
        timestamp = str(int(time.time() * 1000))
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": settings.NAVER_SEARCHAD_ACCESS_LICENSE,
            "X-Customer": str(settings.NAVER_SEARCHAD_CUSTOMER_ID),
            "X-Signature": self._sign(method, path, timestamp),
        }

    # --- HTTP (GET 전용) ---

    def _get(self, path: str, params=None, expect_repeat: Optional[tuple] = None):
        """GET 요청 한 방. 실패는 **예외로 올린다** — 빈 값으로 삼키지 않는다.

        params 는 dict 또는 (key, value) 튜플 리스트.
        🩸 반복 파라미터(`?ids=A&ids=B`)가 필요하면 **튜플 리스트**로 넘겨라. 아래 get_spend 참고.

        expect_repeat=("ids", 28) 을 주면 **실제로 나가는 URL** 에 그 키가 정확히 그만큼
        반복되는지 발사 전에 확인하고, 어긋나면 예외를 던진다. 이유는 아래 get_spend 주석 참고 —
        형식이 틀린 요청이 200 + 빈 데이터로 돌아오기 때문에 응답만 봐서는 감지할 수 없다.
        """
        if not self.is_configured():
            raise RuntimeError(
                "네이버 검색광고 미설정: NAVER_SEARCHAD_CUSTOMER_ID / "
                "ACCESS_LICENSE / SECRET_KEY 확인"
            )
        req = httpx.Request(
            "GET",
            f"{API_BASE}{path}",
            params=params,
            headers=self._headers("GET", path),
        )
        if expect_repeat:
            key, want = expect_repeat
            got = sum(1 for k, _ in req.url.params.multi_items() if k == key)
            if got != want:
                raise RuntimeError(
                    f"Naver Ads {path}: '{key}' 가 {want}개여야 하는데 URL 에 {got}개로 나간다. "
                    f"콤마 조인으로 뭉개졌을 가능성 — 그대로 보내면 200 + 빈 데이터로 조용히 0 이 된다."
                )
        with httpx.Client(timeout=30) as client:
            resp = client.send(req)
        if resp.status_code >= 400:
            logger.error(f"Naver Ads GET {path} → {resp.status_code}: {resp.text[:400]}")
            raise RuntimeError(
                f"Naver Ads {resp.status_code} GET {path}: {resp.text[:300]}"
            )
        return resp.json() if resp.content else {}

    # --- 조회 ---

    def get_campaigns(self) -> list[dict]:
        """GET /ncc/campaigns — 네이버가 준 dict 를 **가공 없이** 그대로 돌려준다.

        base.Campaign 으로 안 감싸는 이유: Campaign.daily_budget 이 USD 전제인데
        네이버는 KRW 다. 환산 없이 float 에 넣으면 대시보드가 원화를 달러로 읽는다.
        원본 dict 로 넘겨서 소비 쪽이 통화를 알고 쓰게 한다.

        주요 키: nccCampaignId · name · campaignTp · status · dailyBudget(원)

        헬스체크가 「실제 호출 1회」로 이걸 쓴다 — 실패는 예외로 올린다.
        """
        data = self._get("/ncc/campaigns")
        if not isinstance(data, list):
            # 정상 응답은 항상 리스트다. 아니면 계약이 바뀐 것 — 조용히 넘기지 않는다.
            raise RuntimeError(f"Naver Ads /ncc/campaigns: 예상 밖 응답 형식 {type(data).__name__}")
        return data

    def get_spend(self, days: int = 7) -> dict:
        """최근 `days` 일 **계정 합계**.

        기간 = 어제까지의 완결된 days 일 (KST 기준).
        오늘을 넣지 않는 이유: 오늘은 부분일이라 날짜 창이 플랫폼마다 어긋난다.
        Meta 쪽이 `date_preset=last_7d`(오늘 제외)를 쓰고 있어 창을 맞췄다.

        반환 키 7개 고정:
          spend(원, salesAmt) · impressions · clicks · conversions ·
          revenue(원, convAmt) · days · currency("KRW")

        실패는 예외로 올린다. 「값이 0」과 「못 읽었다」가 구분 안 되면 이 구멍을 또 판다.
        """
        campaigns = self.get_campaigns()
        ids = [c["nccCampaignId"] for c in campaigns if c.get("nccCampaignId")]

        until = datetime.now(KST).date() - timedelta(days=1)
        since = until - timedelta(days=days - 1)
        time_range = json.dumps({"since": since.isoformat(), "until": until.isoformat()})
        fields = json.dumps(STAT_FIELDS)

        total = {"spend": 0, "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0}

        for i in range(0, len(ids), STATS_CHUNK):
            chunk = ids[i:i + STATS_CHUNK]
            # 🩸 `ids` 는 **반복 쿼리 파라미터**여야 한다 — `?ids=A&ids=B`.
            #    이 버그 하나 때문에 6개월간 광고비를 못 봤다. 2026-08-17 실계정 재측정 결과,
            #    두 오답 형태가 **서로 다르게** 실패한다:
            #      JSON 배열 '["A","B"]' → 400 {"code":11001,"유효하지 않은 ID 형식입니다."}  (시끄러움, 그나마 다행)
            #      콤마 조인  "A,B"      → **200 + {"data":[]}**                              (조용한 0 — 이게 진짜 살인마)
            #    콤마 쪽은 에러가 아니라 「지출 0」으로 보인다. 대시보드가 6개월간 $0 을 띄운 게 정확히 이 모양이다.
            #    그래서 (1) **튜플 리스트로 못 박고** — 이 형태는 반복 파라미터 외로 해석될 수 없다 —
            #         (2) expect_repeat 로 **발사 전에** URL 의 ids 개수를 세서 어긋나면 예외를 던진다.
            #    응답만 봐서는 절대 감지 못 하므로 게이트를 요청 쪽에 둔다.
            params = [("ids", cid) for cid in chunk]
            params.append(("fields", fields))      # JSON 문자열
            params.append(("timeRange", time_range))  # JSON 문자열

            res = self._get("/stats", params=params, expect_repeat=("ids", len(chunk)))
            for row in (res.get("data") or []):
                total["spend"] += int(row.get("salesAmt") or 0)
                total["impressions"] += int(row.get("impCnt") or 0)
                total["clicks"] += int(row.get("clkCnt") or 0)
                total["conversions"] += int(row.get("ccnt") or 0)
                total["revenue"] += int(row.get("convAmt") or 0)

        if not ids:
            logger.warning("Naver Ads: 캠페인 0개 — 지출 0 은 「집행 없음」이지 「조회 실패」가 아니다")

        total["days"] = days
        total["currency"] = "KRW"
        return total
