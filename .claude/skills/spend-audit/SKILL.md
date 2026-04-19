---
name: Spend Audit
description: 광고 예산 집행을 감사한다. DAILY_BUDGET_CAP 준수 확인, 플랫폼별 ROI 비교, 좀비 캠페인(PAUSED지만 과금 걸림) 탐지, 예산 이상치 감지. 자동화 폭주 사고 재발 방지용 안전망.
---

# Spend Audit (예산 집행 감사)

## 역할
**광고 자동화의 안전망**. 자동 최적화 시스템이 예상 밖으로 폭주하지 않는지 검증. 2026-04-19 사건(CANARY_COUNT=3인데 19개 생성된 폭주)처럼 버그/설정 실수가 예산을 태우는 걸 사전에 막는다.

## 감사 체크리스트

### 1. 예산 캡 준수
- 일 예산 캡(`DAILY_BUDGET_CAP=40,000`) vs 실제 지출
- 캠페인당 예산 상한(`MAX_DAILY_BUDGET_PER_CAMPAIGN=4,000`) 위반 건
- 활성 캠페인 개수(`MAX_ACTIVE_CAMPAIGNS=25`) 초과 여부
- 👉 **위반 시 즉시 중단 가능한 스크립트 제공**

### 2. 플랫폼별 ROI 비교
| 플랫폼 | 지출 (7일) | 전환 | CPA | 효율 순위 |
|--------|-----------|------|-----|-----------|
| Meta | ₩140k | 48 | ₩2,917 | 1위 |
| Google | ₩80k | 12 | ₩6,667 | 3위 |
| X | ₩40k | 8 | ₩5,000 | 2위 |

→ 최저 효율 플랫폼에서 고효율로 예산 재배분 제안.

### 3. 좀비 캠페인 탐지
**좀비의 4가지 유형**:
- 🧟 **Phantom**: PAUSED인데 과금 걸린 건 (Meta에서 종종 발생)
- 🧟 **Perpetual**: 30일 이상 지출 0원인데 ACTIVE
- 🧟 **Forgotten**: 캠페인 매니저 사이클에서 누락된 건
- 🧟 **Orphan**: adset/ad 없이 캠페인 껍데기만 있는 건

### 4. 이상 집행 감지
- **스파이크**: 일 지출이 7일 중간값의 3배 이상
- **플랫 라인**: 예산 소진율이 24시간 내 0%→100% (정상 분배 실패)
- **플랫폼 쏠림**: 하루 지출의 80%+ 한 플랫폼 집중 (리스크 노출)
- **API 에러 과금**: 크리에이티브 실패 후에도 캠페인에 과금 걸린 케이스

### 5. 자동화 오남용 탐지
- CANARY_COUNT(3) vs 실제 생성 수
- 캠페인 매니저 사이클당 정상 생성 비율
- 재시도 루프 감지 (같은 hash 반복 생성)
- Meta/Google API 에러 비율

## 감사 스크립트 생성

감사 결과에 따라 **실행 가능한 스크립트 경로**를 제공:
```bash
# 좀비 일괄 아카이브
python scripts/meta_archive_paused.py --apply

# 특정 플랫폼 전체 중단
python scripts/meta_pause_all.py --account act_xxx

# 예산 재조정
python scripts/meta_rebalance_budgets.py --from act_X --to act_Y
```

## 감사 결과 포맷

```markdown
# 💰 Spend Audit — 2026-04-19 (7일 회고)

## 🚦 전체 판정
[✅ 정상 / ⚠️ 주의 / 🚨 위반]

## 1. 예산 캡 준수
- 일 캡: ₩40,000 | 실제 최대 일지출: ₩38,200 ✅
- 캠페인당: ₩4,000 | 최대 단일 캠페인: ₩3,850 ✅
- 활성 캠페인: 19 / 25 ✅
- ⚠️ 경고: 4/19 23:00 잠시 ₩39,800 도달 (캡 99.5%)

## 2. 플랫폼 ROI
[테이블]
→ 제안: Google에서 Meta로 일 ₩5k 재배분

## 3. 좀비 탐지
- 🧟 Phantom 0건
- 🧟 Perpetual 3건: [id 리스트] → `scripts/meta_archive_paused.py --apply`
- 🧟 Orphan 1건: bc3bb1 (adset 없음) → 수동 삭제

## 4. 이상 집행
- ✅ 스파이크 없음
- ⚠️ 플랫폼 쏠림: 4/18 Meta 85% 집중 → 분산 필요
- ✅ API 에러 과금 없음

## 5. 자동화 오남용
- 🚨 **4/19 14:00 CANARY_COUNT=3인데 19개 생성됨**
  - 원인 조사 필요: scheduler/campaign_manager 버그
  - 임시 조치: CAMPAIGNS_PER_CYCLE=3 강제 하드코딩
  - 근본 조치: 재시도 루프 방지 로직 추가

## 🔧 권장 실행 명령
```bash
# 1. 좀비 정리
python scripts/meta_archive_paused.py --apply

# 2. 폭주 원인 로그 확인
python scripts/railway_logs.py --since "2026-04-19 13:59" --grep "canary\|campaign_cycle"

# 3. 예산 재조정
python -m campaign.manager --rebalance --from-google --to-meta --amount 5000
```

## 📊 7일 트렌드
- 총 지출: ₩220k / 예산 ₩280k (78.5%)
- 총 전환: 68
- 평균 CPA: ₩3,235
- 가장 효율 좋은 날: 4/17 화요일 (CPA ₩2,100)
```

## 작업 지침

1. **위반은 빨간색, 주의는 노란색, 정상은 초록색**: 눈으로 한 번에 판단 가능해야.

2. **근본 원인 제안**: 단순히 "좀비 있음" 끝이 아니라 "왜 생겼나" 추론 (예: 특정 사이클에서 실패 후 롤백 누락).

3. **실행 명령 첨부**: 감사만 하고 끝 아니라, 바로 실행할 수 있는 스크립트 경로/파라미터 제공.

4. **시간 범위**: 기본 7일. `--days N` 인자로 조정 가능하게.

5. **이상치 민감도**:
   - 초기 단계(예산 적음): 노이즈 크므로 보수적으로
   - 스케일 단계(예산 큼): 더 타이트하게

6. **교차 검증**: DB와 API 값이 다르면 경고. 동기화 문제일 수 있음.

7. **시계열 저장**: 감사 결과를 `audit_log` 컬렉션에 저장 → 트렌드 분석 가능.

## OneMessage 프로젝트 맥락
- DAILY_BUDGET_CAP=40,000 KRW (config/settings.py)
- MAX_DAILY_BUDGET_PER_CAMPAIGN=4,000 KRW
- MAX_ACTIVE_CAMPAIGNS=25
- CANARY_MODE=true (첫 사이클 3개만)
- CANARY_COUNT=3
- DRY_RUN 플래그 존중 (True면 실제 변경 없이 플랜만)
