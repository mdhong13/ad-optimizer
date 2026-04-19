---
description: 플랫폼별 광고 카피(헤드라인/본문/CTA)를 가설 기반 변형으로 생성
argument-hint: [캠페인명, 플랫폼, 변형 개수]
---

Ad Copy Generation 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/ad-copy/SKILL.md`의 프레임워크를 따라 다음을 수행:

1. **타겟 분석 확인 (필수)**: audience-analysis 결과가 없으면 먼저 `/audience-analysis` 실행을 권고하고, 그래도 진행하면 최소 가정을 [가정] 태그로 명시
2. **앵글 다양화**: 공포/사랑/효율/권위/호기심/사회증명/희소성/FOMO 중 **서로 다른 앵글**로 변형 생성 (같은 앵글 반복 금지)
3. **플랫폼별 포맷 엄수**:
   - Meta: Primary Text 125자, Headline 27자, CTA 버튼 선택
   - Google: RSA 15 headlines × 30자 + 4 descriptions × 90자
   - X: 280자, 훅 첫 문장
   - Reddit: 서브레딧 문화 준수, 광고티 제거, 가치 제공형
4. **각 변형의 검증 가설** 한 줄로 명시 (A vs B에서 무엇을 배우려는지)
5. **기존 성과 데이터 반영**: DB campaigns 컬렉션에서 이전 승자가 있으면 핵심 요소 유지
6. **금지어/규제 체크**: Meta 크립토 정책, Google 우등 표현, 지역별 제약
7. **CTA-랜딩 일치 확인**

출력은 SKILL.md의 변형 매트릭스 + 플랫폼별 상세 포맷으로.
