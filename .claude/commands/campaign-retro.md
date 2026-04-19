---
description: 종료된 캠페인 회고 - KPT 분석, A/B 가설 검증, 학습 태깅 후 DB 누적
argument-hint: [캠페인 ID 또는 사이클 번호]
---

Campaign Retrospective 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/campaign-retro/SKILL.md`의 프레임워크를 따라:

1. **기본 정보**: 기간, 예산 집행, 결과 (생존/탈락/수동 중단)
2. **핵심 지표**: 목표 대비 실제 (CPA/CTR/전환/학습 단계)
3. **가설 검증**: 사전 H1이 맞았나? 통계적 유의성 달성? (샘플 작으면 "추정"으로)
4. **KPT**:
   - Keep: 효과적이었던 것 (유지할 요소)
   - Problem: 문제였던 것
   - Try: 다음 시도할 것
5. **성과 귀인**: 크리에이티브/타겟팅/입찰/타이밍/플랫폼/외부 요인 다중 고려 (단일 요인 단정 금지)
6. **학습 태그**: #persona #angle #format #creative #bidding #timing #platform 중 최소 2~3개
7. **DB 저장**: `campaign_retros` 컬렉션에 구조화 저장

**중요**: 실패도 학습. 부정적 결과("공포 앵글이 나빴다")도 동등하게 기록. 다음 audience-analysis/ad-copy/ab-test 실행 시 이 학습이 반영되도록.
