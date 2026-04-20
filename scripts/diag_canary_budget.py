"""KR Canary 캠페인/AdSet 예산 + 실제 지출 확인"""
from __future__ import annotations
import io, sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GRAPH = "https://graph.facebook.com/v21.0"
acc = settings.META_AD_ACCOUNT_ID
tok = settings.META_ACCESS_TOKEN


def main():
    print("=== KR Canary 캠페인 예산 ===")
    r = httpx.get(f"{GRAPH}/{acc}/campaigns",
        params={"access_token": tok, "fields": "id,name,status,daily_budget,lifetime_budget,objective,spend_cap", "limit": 30}, timeout=30)
    canary_ids = []
    for c in r.json().get("data", []):
        nm = c.get("name", "")
        if "Canary" not in nm and "KR-" not in nm:
            continue
        canary_ids.append(c["id"])
        db = int(c.get("daily_budget", 0)) / 100 if c.get("daily_budget") else 0
        lb = int(c.get("lifetime_budget", 0)) / 100 if c.get("lifetime_budget") else 0
        sc = int(c.get("spend_cap", 0)) / 100 if c.get("spend_cap") else 0
        print(f"  {c['id']}  {nm[:45]:45}  {c.get('status'):8}  daily={db}  life={lb}  cap={sc}  obj={c.get('objective','')}")

    print("\n=== KR Canary AdSet 예산 ===")
    r2 = httpx.get(f"{GRAPH}/{acc}/adsets",
        params={"access_token": tok, "fields": "id,name,status,daily_budget,lifetime_budget,bid_strategy,optimization_goal,campaign_id", "limit": 100}, timeout=30)
    for s in r2.json().get("data", []):
        if s.get("campaign_id") not in canary_ids:
            continue
        db = int(s.get("daily_budget", 0)) / 100 if s.get("daily_budget") else 0
        lb = int(s.get("lifetime_budget", 0)) / 100 if s.get("lifetime_budget") else 0
        print(f"  {s['id']}  {s.get('name','')[:50]:50}  {s.get('status'):8}  daily={db}  life={lb}  goal={s.get('optimization_goal')}  bid={s.get('bid_strategy')}")

    print("\n=== 실제 지출 (최근 7일, 캠페인별) ===")
    r3 = httpx.get(f"{GRAPH}/{acc}/insights",
        params={"access_token": tok,
                "fields": "campaign_id,campaign_name,spend,impressions,clicks,date_start,date_stop",
                "level": "campaign", "date_preset": "last_7d", "time_increment": 1, "limit": 200}, timeout=30)
    total = {}
    for row in r3.json().get("data", []):
        cid = row.get("campaign_id")
        if cid not in canary_ids:
            continue
        date = row.get("date_start", "")
        spend = float(row.get("spend", 0))
        imp = int(row.get("impressions", 0))
        clk = int(row.get("clicks", 0))
        key = (cid, date)
        print(f"  {date}  {row.get('campaign_name','')[:40]:40}  spend={spend:8,.0f} KRW  imp={imp:7,}  clk={clk:5,}")
        total[cid] = total.get(cid, 0) + spend

    print("\n=== 캠페인별 7일 누적 ===")
    for cid, s in total.items():
        print(f"  {cid}  total_spend={s:,.0f} KRW")

    print("\n=== 계정 정보 ===")
    r4 = httpx.get(f"{GRAPH}/{acc}",
        params={"access_token": tok, "fields": "id,name,currency,account_status,disable_reason,spend_cap,amount_spent,balance"}, timeout=30)
    ad = r4.json()
    print(f"  name: {ad.get('name')}  currency: {ad.get('currency')}  status: {ad.get('account_status')}")
    print(f"  spend_cap: {ad.get('spend_cap')}  amount_spent: {ad.get('amount_spent')}  balance: {ad.get('balance')}")


if __name__ == "__main__":
    main()
