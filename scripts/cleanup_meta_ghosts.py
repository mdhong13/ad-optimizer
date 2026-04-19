"""
Meta 계정의 유령 캠페인 일괄 삭제

용도: 스케줄러 버그로 생성된 'OneMessage Auto *' 등 PAUSED + 스펜드 0원 캠페인 정리.

안전장치:
  - 스펜드(지출) 있는 캠페인은 자동 보호 (삭제 안 함)
  - --keep-prefix 로 보호할 이름 prefix 지정 (기본: KR-Canary-)
  - --dry-run 으로 대상 먼저 출력

사용:
  python -m scripts.cleanup_meta_ghosts --dry-run          # 미리보기
  python -m scripts.cleanup_meta_ghosts --delete           # 실삭제
  python -m scripts.cleanup_meta_ghosts --delete --keep-prefix KR-Canary-,Brand-
"""
import argparse
import io
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

GRAPH = "https://graph.facebook.com/v21.0"


def list_campaigns(account_id: str, token: str):
    """캠페인 + 30일 성과 지표 조회"""
    url = f"{GRAPH}/{account_id}/campaigns"
    params = {
        "fields": "id,name,status,daily_budget,created_time,insights.date_preset(maximum){spend,impressions}",
        "limit": 200,
        "access_token": token,
    }
    out = []
    while url:
        r = httpx.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("data", []))
        # 페이지네이션
        next_url = data.get("paging", {}).get("next")
        url = next_url
        params = None  # next_url already has all params
    return out


def get_spend(c: dict) -> float:
    ins = c.get("insights", {}).get("data", [])
    if not ins:
        return 0.0
    try:
        return float(ins[0].get("spend", 0.0) or 0.0)
    except (ValueError, TypeError):
        return 0.0


def delete_campaign(campaign_id: str, token: str) -> bool:
    url = f"{GRAPH}/{campaign_id}"
    r = httpx.delete(url, params={"access_token": token}, timeout=30)
    if r.status_code == 200 and r.json().get("success"):
        return True
    print(f"  삭제 실패 {campaign_id}: {r.status_code} {r.text[:150]}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Meta 유령 캠페인 정리")
    parser.add_argument("--account", default=settings.META_AD_ACCOUNT_ID or "act_481473468715453",
                        help="광고 계정 ID (기본: settings)")
    parser.add_argument("--keep-prefix", default="KR-Canary-",
                        help="보호할 이름 prefix 콤마구분 (기본: KR-Canary-)")
    parser.add_argument("--dry-run", action="store_true",
                        help="삭제 대상만 표시 (기본 동작)")
    parser.add_argument("--delete", action="store_true",
                        help="실삭제 실행")
    args = parser.parse_args()

    token = settings.META_ACCESS_TOKEN
    if not token:
        raise SystemExit("META_ACCESS_TOKEN 미설정")

    keep_prefixes = [p.strip() for p in args.keep_prefix.split(",") if p.strip()]
    dry = not args.delete

    print(f"계정: {args.account}")
    print(f"보호 prefix: {keep_prefixes}")
    print(f"모드: {'DRY-RUN (미리보기)' if dry else '실삭제'}\n")

    campaigns = list_campaigns(args.account, token)
    print(f"총 {len(campaigns)}개 캠페인 발견\n")

    keep_protected = []
    keep_spent = []
    to_delete = []
    for c in campaigns:
        name = c.get("name", "")
        if any(name.startswith(p) for p in keep_prefixes):
            keep_protected.append(c)
            continue
        spend = get_spend(c)
        if spend > 0:
            keep_spent.append((c, spend))
            continue
        to_delete.append(c)

    print(f"[유지] prefix 매칭 {len(keep_protected)}개:")
    for c in keep_protected:
        print(f"  - {c['name']}  ({c['id']})")
    print()

    print(f"[유지] 스펜드 있음 {len(keep_spent)}개:")
    for c, spend in keep_spent:
        print(f"  - {c['name']}  ({c['id']})  spend={spend}")
    print()

    print(f"[삭제 대상] {len(to_delete)}개:")
    for c in to_delete:
        print(f"  - {c['name']}  ({c['id']})  status={c.get('status')}")
    print()

    if dry:
        print(f"미리보기 완료. 실삭제하려면 --delete 추가")
        return

    # 실삭제
    print(f"{len(to_delete)}개 삭제 시작...")
    ok = 0
    for c in to_delete:
        if delete_campaign(c["id"], token):
            ok += 1
            print(f"  OK {c['name']}")
    print(f"\n완료: {ok}/{len(to_delete)} 삭제됨")


if __name__ == "__main__":
    main()
