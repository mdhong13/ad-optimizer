# KR Canary 통합 캠페인 마이그레이션

기존: 캠페인 3개 × ₩150,000/일 = ₩450,000/일 (모두 개별 CBO 불가능)
이후: 캠페인 1개 × ₩50,000/일 (CBO 가 3 AdSet 간 자동 배분)

## 왜 통합?

1. **CBO (Campaign Budget Optimization)** — 성과 좋은 AdSet 에 예산 몰림
2. **Meta A/B 테스트 표준 구조** — 1 캠페인, 여러 AdSet/Ad
3. **리포팅 간결** — 대시보드에서 한 줄로 집계
4. **사용자 상한 준수** — 일 ₩50,000 한도 유지

## 실행 순서

### 1. 통합 캠페인 생성 (DRY_RUN 먼저)

대시보드 `/campaigns` → **KR Canary Unified** 카드
- AdSet 선택 (C1/C2/C3 기본 A 앵글)
- 예산 ₩50,000
- "실제 생성" 체크 OFF → **통합 캠페인 생성** → DRY_RUN 로그 확인
- 문제없으면 "실제 생성" ON → 다시 클릭

또는 CLI:
```bash
python -m scripts.launch_kr_canary_unified --live --budget 50000
```

### 2. Meta UI 에서 PAUSED 상태 확인

- campaigns list 상단에 `KR-Canary-Unified` 나타남
- AdSet 3개: `C1-A-자녀-부모걱정`, `C2-A-1인가구`, `C3-A-65+본인`
- 각 AdSet 마다 Ad 1개
- 전부 PAUSED

### 3. 기존 3 캠페인 일시중지

Meta UI (Ads Manager) → 기존 캠페인 선택 → **해제** 토글 OFF:
- KR-Canary-C1-A-자녀-부모걱정
- KR-Canary-C2-A-1인가구
- KR-Canary-C3-A-65+본인

> 삭제 대신 **일시중지** 권장 — 과거 지출/성과 히스토리 보존

### 4. 통합 캠페인 활성화

Meta UI → `KR-Canary-Unified` → 해제 토글 ON
(캠페인 + 3 AdSet + 3 Ad 모두 활성화 확인)

## 예산 작동 방식 (CBO)

- **캠페인 레벨:** ₩50,000/일 (하드 상한)
- **AdSet 레벨:** 개별 예산 없음 — Meta 가 학습 후 재배분
- **학습 기간 3-5일:** 초반엔 균등 분배 → 이후 성과순으로 기울어짐
- **수동 개입 최소화:** AdSet 개별 중단은 CBO 학습 방해

## 성과 비교 (마이그레이션 후 7일 관찰)

| 지표 | 기존 3캠페인 | 통합 1캠페인 | 목표 |
|---|---|---|---|
| CPC | ₩131 평균 | ? | 하락 |
| 학습률 | 각 캠페인 개별 | 전체 통합 | 빨라짐 |
| AdSet간 격차 | 보임 | CBO 가 조정 | 균형 |

## 롤백

문제 발생 시:
1. `KR-Canary-Unified` 일시중지
2. 기존 3캠페인 다시 활성화
3. 이슈 수정 후 재시도

## 자동화 규칙

- **원칙:** 지금부터 KR 캠페인은 Unified 구조만 사용
- **예산 상한:** 일 ₩50,000/캠페인 (하드코딩, `launch_kr_canary_unified.py` 에서 경고)
- 기존 `launch_kr_canary.py` 는 하위 호환 유지하지만 **신규 실행 비권장**
