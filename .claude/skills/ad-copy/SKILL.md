---
name: Ad Copy Generation
description: 광고 카피(헤드라인, 본문, CTA)를 플랫폼별 제약과 포맷에 맞춰 생성한다. Google Ads, Meta, X, Reddit 4개 플랫폼의 고유 형식을 준수하며, 타겟 오디언스 분석 결과를 반영한다. 같은 메시지의 무의미한 반복이 아니라 검증 가능한 가설별 변형을 만든다.
---

# Ad Copy Generation (광고 카피 생성)

## 역할
광고 마케팅의 **"뭐라고 말할지"** 를 책임지는 카피라이터로 행동한다. 3C(Customer, Context, Creative) 중 Creative의 핵심. 플랫폼별 제약(글자 수, 포맷, 금지어)을 지키면서 **가설 기반 변형**을 만든다.

## 작업 전제
반드시 **먼저 타겟 오디언스가 정의**돼 있어야 한다. 없으면 `/audience-analysis` 먼저 실행하도록 안내할 것. 타겟 없이 카피 쓰는 것은 과녁 없이 활 쏘는 것과 같다.

## 카피 프레임워크

### 메시지 앵글 (Angle)
같은 제품도 다양한 각도에서 접근 가능. 각 변형은 **다른 앵글**이어야 진짜 A/B 테스트가 된다:

1. **공포 소구 (Pain)**: "놓치면 잃는다"
2. **가족/사랑 (Love)**: "소중한 사람을 위해"
3. **효율/편의 (Convenience)**: "간단하고 자동"
4. **권위/신뢰 (Authority)**: "전문가가 인정한"
5. **호기심 (Curiosity)**: "당신이 모르는 사실"
6. **사회증명 (Social Proof)**: "n만 명이 사용 중"
7. **희소성 (Scarcity)**: "한정 수량/기간"
8. **FOMO**: "다른 사람은 이미"

같은 제품에 여러 앵글 → 어느 앵글이 타겟에게 먹히는지 데이터로 검증.

### 카피 구조 (AIDA + PAS)
- **A**ttention: 첫 한 줄에 시선 꽂기
- **I**nterest: 관심 끌 정보/혜택
- **D**esire: 구체적 이점/결과
- **A**ction: 명확한 다음 단계 (CTA)

변형: **P**roblem → **A**gitate → **S**olution (문제 제기 → 고조 → 해결)

## 플랫폼별 포맷

### Meta (Facebook/Instagram)
Single Image/Video Ad 기준:
- **Primary Text (본문)**: 125자 권장 (최대 약 2200자) — 대부분 유저는 125자만 봄
- **Headline**: 27자 권장 (최대 40)
- **Description (뉴스피드 하단 작은 글씨)**: 27자 권장 (선택)
- **CTA Button**: 미리 정의된 목록 중 선택 (Learn More, Sign Up, Shop Now 등)
- **Link URL**: 랜딩 페이지 URL

Reels/Stories:
- 텍스트 오버레이 짧게 (3~5단어)
- 음성/캡션 필수

Instagram Feed:
- 해시태그 3~5개 (과도하면 역효과)
- 캡션은 스토리텔링 용으로 길게 가능

### Google Ads

**Search Ads (Responsive Search Ad)**:
- **Headlines**: 최대 15개 (각 30자)
- **Descriptions**: 최대 4개 (각 90자)
- Google이 조합을 자동 최적화 → 다양한 앵글 제공이 유리
- **Display Path (URL 경로 커스텀)**: 각 15자 × 2칸

**Display Ads**:
- Short Headline: 30자
- Long Headline: 90자
- Description: 90자
- Business Name: 25자

**YouTube Ads**:
- In-stream: 음성 대본 15~30초 (첫 5초가 승부)
- Bumper: 6초 (한 문장)
- Companion Banner: 제목 + 설명

### X (Twitter) Ads
- **Tweet Copy**: 280자 (한글은 약 140자에 해당)
- **Website Card**: 70자 제목 + 랜딩 URL
- **Image Ads**: 이미지 + 본문 + CTA
- 톤: 대화체, 비공식, 구어체, 이모지/해시태그 활용
- 첫 문장에 훅 필수 (타임라인 스크롤 중 0.3초 안에 승부)

### Reddit Ads
- **Title**: 300자 (최대) / 50~100자 권장
- **Post Body**: 40,000자 (최대) / 실전은 짧고 정직한 게 유리
- 톤: **광고 티가 나면 즉시 차단** — 진정성 있는 대화형 필수
- 서브레딧 문화 준수 (r/Bitcoin vs r/CryptoCurrency 톤이 다름)
- CTA는 부드럽게: "Check out", "Try it", "Learn more"
- ⚠️ 노골적 판매 금지, 가치 제공 먼저

## 가설 기반 변형 설계

**나쁜 예** (무의미한 변형):
- 변형 A: "OneMessage로 자산을 지키세요"
- 변형 B: "OneMessage로 자산을 보호하세요"
- → 단어만 바뀜. 데이터 수집해도 학습 없음.

**좋은 예** (앵글이 다른 변형):
- 변형 A [공포]: "개인키를 잃으면 당신의 비트코인은 영원히 사라집니다"
- 변형 B [사랑]: "가족이 당신의 디지털 자산을 이어받을 수 있게"
- 변형 C [효율]: "3분 설정으로 완료, 매월 자동 확인"
- → 어떤 동기가 타겟에게 가장 강한지 데이터로 판별 가능.

## 출력 포맷

```markdown
# 광고 카피 생성: [캠페인/페르소나 이름]

## 전제
- **타겟 페르소나**: [audience-analysis 결과 요약]
- **주 페인포인트**: [Critical 페인]
- **제품 핵심 가치**: [한 줄]

## 카피 변형 매트릭스

| # | 앵글 | 플랫폼 | 헤드라인 | 본문 | CTA |
|---|------|--------|----------|------|-----|
| A | 공포 | Meta | [카피] | [카피] | Learn More |
| B | 사랑 | Meta | [카피] | [카피] | Sign Up |
| C | 효율 | Meta | [카피] | [카피] | Get Started |
...

## 플랫폼별 상세

### Meta (Single Image Ad)
**변형 A [앵글]**
- Primary Text (125자): [내용]
- Headline (27자): [내용]
- CTA: [버튼]
- Landing URL: [URL]

[B, C... 반복]

### Google Ads (Responsive Search Ad)
**Ad Group: [이름]**
- Headlines (15개, 각 앵글에서):
  1. [30자]
  2. [30자]
  ...
- Descriptions (4개):
  1. [90자]
  ...
- Final URL: [URL]

### X (Twitter)
**변형 A [앵글]**
- Tweet: [280자]
- Image/Card: [설명]

### Reddit
**Subreddit: r/[이름]**
**변형 A [앵글]**
- Title: [카피]
- Body: [본문 — 광고 티 안 나게]
- Target Subreddits: [리스트]

## 검증 가설
각 변형이 테스트하는 가설:
- A vs B: [공포 vs 사랑 앵글 중 무엇이 CTR 높은가]
- A vs C: [감정 vs 편의 강조 중 무엇이 전환 좋은가]
...

## 유의사항
- 플랫폼 금지어 체크됨
- 크립토 광고 규정 준수 (Meta: 승인 필요, Google: 라이선스 요구)
- 지역별 규제 고려됨 (한국 vs 미국 vs 일본)
```

## 작업 지침

1. **먼저 audience-analysis 확인**: 있으면 그걸 기반으로, 없으면 "먼저 `/audience-analysis` 실행 권장"으로 안내 후, 최소 가정하고 진행 시 **[가정]** 태그 명시.

2. **앵글 다양화 필수**: 한 캠페인 그룹에 동일 앵글 2번 이상 쓰지 말 것. 앵글 = 가설이다.

3. **플랫폼 글자 수 엄수**: 초과 시 Meta는 "…" 잘림, Google은 거부. 쓰고 나서 반드시 카운트 확인.

4. **금지어 체크**:
   - Meta: "you/your" 과도 사용, 건강/부 과장
   - Google: "#1", "최고" 같은 우등 표현
   - 전체: 크립토 관련 "guaranteed returns", "투자 수익 보장" 절대 금지

5. **CTA는 랜딩과 일치**: CTA "Sign Up" 인데 랜딩이 제품 소개만 있으면 불일치 → 낮은 전환. CTA-랜딩 일관성 체크.

6. **로컬라이제이션**: 한/영 양쪽 쓸 경우, 단순 번역이 아니라 해당 문화권 톤으로 재작성. 특히 Reddit 영문은 한국식 번역체 금지.

7. **A/B로 끝내지 말고 검증 가설 명시**: 각 변형이 무엇을 배우려는지 한 줄로 적기. 이것이 다음 단계 `ab-test` 스킬 입력으로 쓰임.

8. **기존 승자 반영**: 이전 캠페인 사이클에서 성과 좋았던 변형이 있으면 (DB `campaigns` 컬렉션), 그 핵심 요소(앵글/단어)를 유지하면서 다음 변형 생성 — **진화 알고리즘 사고**.

## OneMessage 프로젝트 맥락
- 주 제품: 사망 감지 메시징 (크립토 지갑 자산 상속)
- 톤: 공포보다 **따뜻한 준비**가 일반적으로 우세
- 금기: "죽음"을 너무 직설적으로 써서 광고 거부 당한 이력 있음 → "소중한 사람", "유산", "연결 끊김" 같은 우회 표현 선호
- 승인 주의: Meta는 "death/dying" 직접 언급 시 거부 사례 많음
