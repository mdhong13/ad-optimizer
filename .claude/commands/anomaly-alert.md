---
description: 광고 성과/시스템 이상 조기 감지 (CTR 급변, 지출 폭주, API 에러, 자동화 오동작)
argument-hint: [--window N분 (기본 60)]
---

Anomaly Alert 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/anomaly-alert/SKILL.md`의 프레임워크를 따라:

1. **성과 이상**: CTR 급락/급등, CPA 폭등, 전환율 붕괴, 노출 0
2. **예산 이상**: 지출 스파이크, 조기 고갈, 캡 초과 임박
3. **시스템 이상**: API 에러 스파이크, 인증 실패, DB 타임아웃, 스케줄러 정지
4. **자동화 이상**: 반복 생성 루프, 과도한 생성, 롤백 실패
5. **정책 이상**: 광고 거부, 계정 경고, 결제 경고

**통계 기준**: 2σ → Warning (노랑), 3σ → Critical (빨강)
**계절성 보정**: 요일/시간대/이벤트 효과 고려
**근본 원인 자동 진단 포함**

**중요**: Critical만 즉시 알림, Warning은 배치, Info는 daily-report로. False Positive 10% 이하 유지. 각 경보마다 실행 가능한 조치 포함.
