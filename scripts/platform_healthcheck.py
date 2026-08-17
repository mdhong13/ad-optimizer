"""광고 플랫폼 연결 점검 — **읽기만**. 돈이 나가는 호출은 하지 않는다.

왜 필요한가(2026-08-12): QCat 네이버 검색광고의 `stats.mjs` 가 6개월간
  **한 번도 성공한 적이 없었다.** ids 를 JSON 배열로 보내 400 이 났는데,
  아무도 돌려보지 않아 아무도 몰랐다. 캠페인 28개를 굴리면서 광고비가
  어디로 나가는지 못 보고 있었다.
  → 「코드가 있다」와 「작동한다」는 다르다. 주기적으로 실제로 불러봐야 한다.

각 플랫폼에 대해 셋을 따로 보고한다 — 뭉치면 원인이 안 보인다:
  ① 키 있음?   ② 클라이언트 생성됨?   ③ 실제 호출 성공?

⚠️ 점검 로직은 `web/services/platform_status.py` **한 곳**에 있다.
   이 스크립트와 `/settings` 화면이 같은 코드를 쓴다 —
   따로 두면 한쪽만 고쳐지고 화면이 또 거짓말을 한다(2026-08-17).

사용:
  python scripts/platform_healthcheck.py          # 광고 플랫폼만
  python scripts/platform_healthcheck.py --all    # 인프라·키 보관 항목까지
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.services import platform_status as ps  # noqa: E402

CLI_BUDGET_SECONDS = 40   # 사람이 기다리는 자리라 웹(8초)보다 넉넉히 준다

_KEYS = {ps.KEYS_OK: "✅", ps.KEYS_MISSING: "❌ 키 없음", ps.KEYS_UNKNOWN: "—"}
_CLIENT = {ps.CLIENT_OK: "✅", ps.CLIENT_FAIL: "❌", ps.CLIENT_NA: "—"}
_CALL = {
    ps.CALL_OK: "✅",
    ps.CALL_FAIL: "❌",
    ps.CALL_SKIPPED: "건너뜀",
    ps.CALL_TIMEOUT: "시간초과",
    ps.CALL_UNCHECKED: "미점검",
}


def main(show_all: bool = False) -> None:
    print("광고 플랫폼 연결 점검 — 읽기 전용 (돈 안 나감)\n")

    specs = ps.build_specs()
    if not show_all:
        specs = [s for s in specs if s.group == ps.GROUP_ADS]
    results, duration_ms = ps.run_probes(specs, budget=CLI_BUDGET_SECONDS)

    w = max(len(r.label) for r in results) + 2
    print(f"{'플랫폼':<{w}}{'키':<6}{'클라이언트':<10}{'실호출':<8}상세")
    print("-" * (w + 26 + 40))
    for r in results:
        print(f"{r.label:<{w}}{_KEYS[r.keys]:<6}{_CLIENT[r.client]:<10}"
              f"{_CALL[r.call]:<8}{r.detail}")

    probed = [r for r in results if r.call != ps.CALL_UNCHECKED]
    ok = sum(1 for r in probed if r.call == ps.CALL_OK)
    print(f"\n실제 호출 성공 {ok}/{len(probed)}  ({duration_ms / 1000:.1f}초)")
    if not show_all:
        print("※ 인프라(Mongo·QCat RAG·Local LLM)·키 보관 항목은 --all 로 함께 점검")
    print("※ 같은 결과를 웹에서도 본다: /settings (캐시 10분, [지금 점검] 버튼)")


if __name__ == "__main__":
    try:
        main(show_all="--all" in sys.argv)
    except Exception:
        traceback.print_exc()
