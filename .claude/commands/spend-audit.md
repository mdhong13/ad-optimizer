---
description: 광고 예산 집행 감사 (캡 준수, ROI, 좀비 탐지, 자동화 오남용 탐지) - 폭주 재발 방지
argument-hint: [--days N (기본 7)]
---

Spend Audit 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/spend-audit/SKILL.md`의 프레임워크를 따라:

1. **예산 캡 준수 확인**: DAILY_BUDGET_CAP(40,000), MAX_DAILY_BUDGET_PER_CAMPAIGN(4,000), MAX_ACTIVE_CAMPAIGNS(25) 위반 여부
2. **플랫폼별 ROI 비교**: Meta/Google/X/Reddit 7일 효율 순위, 재배분 제안
3. **좀비 탐지 4가지**: Phantom(PAUSED+과금), Perpetual(30일+ 지출 0), Forgotten(매니저 누락), Orphan(adset 없음)
4. **이상 집행**: 지출 스파이크, 플랫 라인, 플랫폼 쏠림, API 에러 과금
5. **자동화 오남용**: CANARY_COUNT vs 실제 생성, 재시도 루프, 폭주 감지
6. **실행 가능한 조치 스크립트 경로 제공**

**중요**: 2026-04-19 폭주 사건(CANARY=3인데 19개 생성) 재발 방지가 핵심 목표. 단순 보고가 아니라 즉시 실행 가능한 명령 제공. 빨강/노랑/초록으로 한눈에 판단.
