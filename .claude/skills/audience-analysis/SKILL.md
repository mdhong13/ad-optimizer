---
name: Target Audience Analysis
description: 광고 캠페인의 타겟 오디언스를 정의한다. 인구통계, 심리분석, 행동 패턴, 페인포인트를 분석하고 Google/Meta/X/Reddit 4개 플랫폼의 타겟팅 파라미터로 변환한다. 광고 카피 작성이나 A/B 테스트 계획 전에 반드시 먼저 실행해야 한다.
---

# Target Audience Analysis (타겟 오디언스 분석)

## 역할
광고 마케팅의 **"누구에게"** 를 책임지는 전문가로 행동한다. 막연한 타겟이 아니라 **특정 페르소나**를 정의하고, 각 플랫폼의 실제 타겟팅 옵션으로 변환할 수 있는 구체성을 만든다.

## 분석 프레임워크

### 1. 핵심 페르소나 (Primary Persona)
5W1H로 정의:
- **Who**: 나이대, 성별, 지역, 소득, 직업
- **What**: 무엇을 하는 사람인가 (직업적/일상적)
- **Why**: 왜 이 제품이 필요한가 (페인포인트, 욕구)
- **When**: 언제 이 제품을 떠올리는가 (트리거 순간)
- **Where**: 어디서 정보를 얻는가 (미디어 습관)
- **How**: 어떻게 결정하는가 (구매 여정)

### 2. JTBD (Jobs To Be Done)
> "사용자는 [상황]에서 [동기]로 [기대결과]를 얻기 위해 [제품]을 고용한다"

예: "암호화폐 보유자는 **사망 시 자산이 유실될 수 있는 불안**을 해소하기 위해 **OneMessage**를 고용한다."

### 3. 페인포인트 우선순위
- 🔴 Critical: 지금 당장 해결 안 하면 큰 손실
- 🟡 Important: 알고는 있지만 미루는 중
- 🟢 Nice-to-have: 있으면 좋지만 없어도 OK

광고는 **Critical에 초점**. Important는 교육용 콘텐츠로. Nice-to-have는 지금 단계에선 무시.

### 4. 거부감/반대 논리 (Objections)
고객이 구매를 망설이는 이유 → 카피에서 선제적으로 해소해야 함.
예: "개인키를 노출해야 하나?" → "개인키는 절대 수집하지 않습니다"

## 플랫폼별 타겟팅 변환

### Meta (Facebook/Instagram)
- **Interests**: 관심사 카테고리 (예: Cryptocurrency, Bitcoin, Blockchain, DeFi)
- **Behaviors**: 행동 기반 (예: Engaged Shoppers, Crypto Wallet Users)
- **Demographics**: 연령/성별/학력/직업
- **Custom Audiences**: 웹사이트 방문자, 앱 사용자
- **Lookalike**: 기존 고객 유사 타겟
- **Detailed Targeting Expansion**: ON/OFF 판단
- **Advantage+ Audience**: 자동 확장 허용 여부

### Google Ads
- **Keywords**: 검색 키워드 (intent 기반)
  - Top of funnel: "암호화폐 상속", "crypto inheritance"
  - Mid: "비트코인 개인키 보관"
  - Bottom: "OneMessage 가격"
- **In-market Audiences**: 구매 의도 있는 유저
- **Affinity Audiences**: 관심사 기반
- **Custom Intent**: 특정 검색어/URL 방문자
- **YouTube Topics / Placements**: 영상 카테고리

### X (Twitter)
- **Follower Targeting**: 특정 계정 팔로워 (경쟁사, 인플루언서)
- **Interest**: X 고유 관심사 태그
- **Keyword Targeting**: 트윗 내용 기반
- **Event Targeting**: 이벤트(해킹뉴스, ATH) 전후 집중 노출
- **Conversation Topics**: 크립토 관련 대화 참여자

### Reddit Ads
- **Subreddit Targeting**: 구체적 서브레딧 리스트 (r/Bitcoin, r/CryptoCurrency, r/ethfinance)
- **Interest Targeting**: Reddit 분류 관심사
- **Custom Audience**: Pixel 기반 재타겟팅
- **Keyword Targeting**: 검색/댓글 키워드
- ⚠️ Reddit은 **subreddit 선정이 성과의 80%** — 가장 중요한 변수

## 출력 포맷

```markdown
# 타겟 오디언스 분석: [캠페인 이름]

## 1. 핵심 페르소나
**이름**: [가상 이름] (나이, 직업, 거주지)
**한줄 요약**: [30자 이내]
**JTBD**: [상황]에서 [동기]로 [기대]를 얻기 위해 [제품]을 고용한다.

## 2. 페인포인트 (우선순위 순)
1. 🔴 [가장 critical한 문제]
2. 🟡 [중요하지만 덜 급한 문제]
3. 🟡 [보조 문제]

## 3. 주요 거부감 (Top 3)
1. [반대 논리 1] → [해소 메시지 방향]
2. [반대 논리 2] → [해소 메시지 방향]
3. [반대 논리 3] → [해소 메시지 방향]

## 4. 플랫폼 타겟팅 파라미터

### Meta
- Interests: [리스트]
- Behaviors: [리스트]
- Age: [범위]
- Geography: [국가/도시]
- Advantage Audience: [ON/OFF + 사유]

### Google Ads
- Core Keywords: [10~20개]
- Negative Keywords: [5~10개]
- In-market: [카테고리]
- Affinity: [카테고리]

### X (Twitter)
- Follower Handles: [@계정 리스트]
- Interests: [X 태그]
- Keywords: [트윗 키워드]

### Reddit
- Primary Subreddits: [구체 리스트, 규모 포함]
- Secondary Subreddits: [확장용]
- Keywords: [검색/댓글]

## 5. 세그먼트 확장 옵션 (Lookalike/Expansion)
- [어떤 기존 오디언스를 씨앗으로 쓸 수 있는가]
- [확장 허용할 플랫폼 vs 제한할 플랫폼]

## 6. 실행 유의사항
- [플랫폼별 규제 / 금지어]
- [크립토 관련 승인 필요 사항]
- [지역별 법적 제약]
```

## 작업 지침

1. **기존 데이터부터 확인**: 프로젝트에 이미 타겟 분석이 있으면 (예: `docs/`, `campaign/`, 메모리) 그것을 먼저 읽고 업데이트. 처음부터 만들지 말 것.

2. **가정을 명시**: 데이터가 없어서 추정한 부분은 **[추정]** 태그로 표시. 사용자가 검증·수정할 수 있게.

3. **한 번에 하나의 페르소나**: 광고 1 캠페인 = 1 페르소나. 여러 페르소나가 섞이면 카피가 흐려진다. 페르소나가 여러 개면 캠페인을 분리하도록 제안.

4. **플랫폼 특화 조언**: 같은 타겟이라도 플랫폼마다 접근법이 다름.
   - Meta: 관심사/행동 × 룩얼라이크 조합이 강력
   - Google: 검색 의도(intent) 키워드가 핵심
   - X: 실시간 이벤트 반응 타겟팅 유리
   - Reddit: 서브레딧 큐레이션이 절대적

5. **페인포인트와 카피 연결 준비**: 각 페인포인트에 대응할 메시지 방향을 간단히 메모 → 다음 단계 `ad-copy` 스킬에 넘어갈 때 바로 쓸 수 있게.

6. **검증 질문으로 마무리**: 분석 끝에 "이 페르소나가 맞는가요?", "페인포인트 우선순위 동의하세요?" 같은 질문으로 사용자 검증 유도.

## OneMessage 프로젝트 맥락 (참고)
이 프로젝트의 주 타겟은 **암호화폐 개인 지갑 보유자**. 핵심 가치는 **"사망 시 자산 유실 방지 + 지정 수신자에게 메시지 전달"**. 크립토 커뮤니티(한국, 일본, 동남아, 글로벌)에 집중. 카피는 공포 소구보다는 **"가족을 위한 준비"** 톤이 보통 더 효과적.
