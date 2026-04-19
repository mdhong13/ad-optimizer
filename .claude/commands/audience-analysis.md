---
description: 광고 캠페인 타겟 오디언스를 분석하고 Google/Meta/X/Reddit 타겟팅 파라미터로 변환
argument-hint: [캠페인명 또는 제품 설명]
---

Target Audience Analysis 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/audience-analysis/SKILL.md`의 프레임워크를 따라 다음을 수행:

1. **기존 타겟 분석 확인**: 프로젝트 내에 이미 정의된 페르소나가 있는지 먼저 검색 (memory, docs/, campaign/ 등)
2. **페르소나 정의**: 5W1H + JTBD + 페인포인트 우선순위
3. **거부감(Objections) Top 3**: 각각에 대응할 메시지 방향
4. **4개 플랫폼 타겟팅 파라미터 변환**:
   - Meta: Interests, Behaviors, Demographics, Advantage+ 판단
   - Google: Keywords (intent별), In-market, Affinity
   - X: Follower, Keywords, Interests, Events
   - Reddit: Primary/Secondary Subreddits, Keywords
5. **가정(assumption)은 [추정] 태그로 표시**
6. **마지막에 사용자 검증 질문**: 이 페르소나/페인 순위가 맞는지 확인

출력은 SKILL.md의 표준 포맷을 따를 것.
