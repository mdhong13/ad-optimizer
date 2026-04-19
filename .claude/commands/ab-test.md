---
description: 광고 변형의 A/B 테스트를 통계적으로 유효하게 설계 (가설, 샘플 사이즈, 종료 조건 포함)
argument-hint: [캠페인명 또는 가설 요약]
---

A/B Test Planning 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/ab-test/SKILL.md`의 프레임워크를 따라 다음을 수행:

1. **전제 확인**: audience-analysis + ad-copy 결과가 있는지 확인, 없으면 선행 단계 실행 안내
2. **가설 명시**: H1(테스트 가설) + H0(귀무가설) + 근거 + 예상 결과
3. **변수 격리 확인**: 한 번에 하나의 변수만 변경 — 여러 변수 바꾸려 하면 실험 쪼개라고 경고
4. **Primary Metric 1개만**: CPA/CTR/전환율 중 승패 기준 하나로 강제. Secondary와 Guardrail은 별도
5. **샘플 사이즈 사전 계산**: MDE, 유의수준, 검정력 기반. 변형당 필요 impression/click/conversion 및 예산 추정
6. **종료 조건**: 기간, 샘플 도달, p-value 기준 사전 명시. **Peeking 금지 경고**
7. **플랫폼별 실험 구조 반영**:
   - Meta: 내장 A/B 도구 활용
   - Google: Drafts & Experiments 또는 RSA 자산 최적화
   - X: 단기 실험 권장
   - Reddit: 서브레딧 자체를 변수로 가능
8. **OneMessage 예산 제약 반영**: 일 40,000원 상한 → 2~4주 필요성 안내
9. **후속 액션**: A/B/Inconclusive 각 결과에 따른 다음 스텝
10. **학습 목적 명시**: 실험 종료 시 무엇을 배울 것인지 사전 정의

출력은 SKILL.md의 9개 섹션 포맷을 따를 것.
