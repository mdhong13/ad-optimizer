---
description: 어제 광고 성과 일간 리포트 생성 (플랫폼별 요약 + 이상치 + 오늘 액션)
argument-hint: [날짜 (기본 어제) 또는 특정 캠페인 ID]
---

Daily Report 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/daily-report/SKILL.md`의 프레임워크를 따라:

1. DB + Meta/Google/X/Reddit API에서 전일 데이터 수집 (Asia/Seoul 기준 00:00~23:59)
2. 헤드라인 한 줄 요약 (지출, 전환, CPA + MoM 비교)
3. 플랫폼별 성과 테이블 (지출/노출/클릭/CTR/CPA/ROAS + 어제 대비)
4. 캠페인 Top 3 (승자 + 이유) + Bottom 3 (패자 + 이유)
5. 이상치 알림 (CTR/CPA 2σ 밖, 좀비, 에러)
6. 오늘 액션 아이템 (우선순위 순, 구체적 실행 명령)
7. 실험 진행 현황

**중요**: 데이터 딜레이 있는 지표는 "잠정" 표시. 액션은 "모니터링" 같은 모호한 지시 금지, 실행 가능한 명령으로.
