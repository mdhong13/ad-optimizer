---
name: Creative Brief
description: 광고 소재 제작 브리프를 생성한다. 이미지(Imagen), 영상(언리얼 메타휴먼 + Qwen TTS), 카피가 일관된 메시지를 전달하도록 상세 명세. ad-copy 결과를 입력 받아 시각/음성 요소로 확장.
---

# Creative Brief (크리에이티브 제작 브리프)

## 역할
광고의 **시각/음성 소재 제작 지시서**를 작성한다. 카피(ad-copy)는 메시지를 정의하고, 이 스킬은 그 메시지를 **이미지/영상/음성**으로 구현하는 방법을 명세한다. AI 이미지 생성기(Imagen), 메타휴먼 아바타, TTS 엔진이 입력으로 쓴다.

## 입력 전제
- `ad-copy` 결과: 헤드라인, 본문, 앵글, CTA
- `audience-analysis`: 타겟 페르소나 (톤/비주얼 방향 결정)
- 플랫폼: 포맷 제약 결정 (Meta Reels vs Google Display 다름)

## 소재 유형별 브리프

### 1. Static Image (정적 이미지)

**용도**: Meta Feed, Google Display, Reddit, X

**브리프 항목**:
- **주 메시지**: 이미지에 들어갈 핵심 문구 (5~7단어)
- **주 오브젝트**: 중앙에 놓을 대상 (인물/제품/상징물)
- **배경**: 환경/톤 설명
- **컬러 팔레트**: 주/보조 색 (HEX 코드)
- **스타일**: 사실적/일러스트/3D/미니멀/감성
- **감정**: 이 이미지가 주는 느낌 (안심/긴급/따뜻함/신뢰)
- **포지션**: 텍스트 위치, 여백 규칙
- **플랫폼 크기**:
  - Meta Feed: 1080×1080 (정사각) / 1080×1350 (4:5)
  - Meta Stories: 1080×1920
  - Google Display: 300×250, 728×90, 336×280
  - X: 1200×675 (16:9)
  - Reddit: 1200×628

**Imagen/Midjourney 프롬프트 예시**:
```
A warm family scene in soft morning light. A smartphone on a wooden table
showing a message preview. Cozy home interior, muted blue and cream
color palette. Photorealistic, shallow depth of field, emotional
storytelling mood. Empty space in upper-right for text overlay.
--ar 1:1 --style photorealistic --v 6
```

### 2. Video (영상)

**용도**: YouTube Shorts, Meta Reels, TikTok, IG Reels, X Video

**브리프 항목**:
- **Duration**: 6초(Bumper) / 15초 / 30초 / 60초
- **Hook (첫 3초)**: 스크롤 멈출 요소
- **Story Arc**: 상황→문제→해결→CTA
- **Shot List**: 장면별 컷
- **Narration Script**: 음성 대본 (메타휴먼/TTS)
- **캡션/자막**: 음성 못 듣는 유저용 (Reels 85% 무음 시청)
- **Background Music**: 분위기 (감성/역동/미니멀)
- **Aspect Ratio**: 9:16 (세로) / 1:1 / 16:9
- **CTA Overlay**: 마지막 2초 액션 유도

**메타휴먼 아바타 브리프**:
- 캐릭터 선택: [페르소나별 최적 아바타]
- 의상: [톤에 맞춘 의상]
- 표정: [감정 지시]
- 제스처: [강조 포인트별]
- 카메라 앵글: [상반신/얼굴 클로즈업]
- 배경: [실내/실외/추상]

**Qwen TTS 음성 브리프**:
- Language: ko-KR / en-US / ja-JP
- Voice Style: [부드러움/자신감/따뜻함]
- Speed: 0.9x (감성) / 1.0x (표준) / 1.1x (역동)
- Pitch: 기본 / +2 (밝음) / -2 (진중)
- Emphasis: [강조할 단어 리스트]

### 3. Carousel (캐러셀)

**용도**: Meta Feed, Instagram

**브리프 항목**:
- **카드 수**: 3~10장
- **내러티브**: 카드별 메시지 흐름 (전/중/결)
- **일관성**: 톤/컬러/폰트 통일
- **첫 카드**: Hook (스크롤 유도)
- **마지막 카드**: CTA 카드

### 4. Interactive (인터랙티브)

**용도**: Meta Canvas/Instant Experience, Google Lightbox

**브리프 항목**:
- 단계별 상호작용 (스와이프/탭/줌)
- 각 단계 메시지
- 최종 랜딩 경로

## 메시지-비주얼 매칭

**앵글별 시각 언어**:
| 앵글 | 톤 | 색상 | 구도 | 예시 |
|------|-----|------|------|------|
| 공포 | 긴장 | 회색/빨강 | 대비 강함, 날카로운 | 보안 자물쇠, 파손된 지갑 |
| 사랑 | 따뜻 | 크림/노랑 | 부드러움, 인물 중심 | 가족, 편지, 손 |
| 효율 | 미니멀 | 파랑/흰색 | 깔끔, 여백 | 시계, 체크리스트, 3분 |
| 권위 | 신뢰 | 네이비/은색 | 대칭, 정적 | 로고, 인증서, 전문가 |
| 호기심 | 신비 | 보라/검정 | 비대칭, 미스터리 | 질문표, 닫힌 문 |
| 사회증명 | 친근 | 자연색 | 군중/리뷰 | 유저 사진, 별점 |

## 브리프 출력 포맷

```markdown
# 🎨 Creative Brief — [캠페인명] / [변형 A]

## 전제
- **카피**: "[헤드라인]"
- **앵글**: 사랑
- **타겟**: [페르소나 요약]
- **플랫폼**: Meta Reels (세로 9:16, 15초)

## 시각 방향
- **감정**: 따뜻함, 안도감
- **컬러**: Primary #4A90E2 (부드러운 파랑), Accent #F5E6A8 (크림)
- **스타일**: 사실적, 감성 스토리텔링
- **구도**: 인물 중심, 얕은 심도

## Shot List (15초 영상)

### 0:00-0:03 Hook
- **비주얼**: 아침 햇살이 드는 침실, 40대 남성이 스마트폰을 보며 생각에 잠김
- **나레이션**: [음성 없음, 환경음만]
- **캡션**: "만약 내일 내가 사라진다면"

### 0:03-0:08 문제 제기
- **비주얼**: 지갑 앱 → 복잡한 개인키 화면
- **나레이션**: "당신의 암호화폐는 당신만 알죠"
- **캡션**: [동일 자막]

### 0:08-0:13 해결
- **비주얼**: OneMessage UI → 가족에게 전달되는 메시지
- **나레이션**: "OneMessage는 그 연결을 이어줍니다"
- **캡션**: [동일]

### 0:13-0:15 CTA
- **비주얼**: 앱 다운로드 버튼, URL
- **나레이션**: "지금 시작하세요"
- **캡션**: "Learn More →"

## 메타휴먼 아바타 지시 (해당 시 사용)
- 캐릭터: [K001_male_40s] (40대 한국 남성)
- 의상: 단정한 스웨터, 집 분위기
- 표정: 생각→결심
- 카메라: 얼굴 클로즈업 → 상반신
- 배경: 침실 → 거실 (부드러운 컷)

## Qwen TTS 음성
- Voice: ko-KR-InJoonNeural (또는 대체)
- Style: 차분하고 따뜻함
- Speed: 0.95x
- Emphasis: "연결", "이어줍니다", "지금"

## 이미지 생성 프롬프트 (Imagen)
```
A Korean man in his 40s sitting by a window in soft morning light,
looking thoughtfully at his smartphone. Cozy bedroom, warm color
palette of soft blue and cream. Photorealistic, shallow depth of
field, emotional mood. Vertical composition 9:16.
--ar 9:16 --style raw --v 6
```

## 배경 음악
- 무드: 감성적, 잔잔
- 장르: Piano solo / Ambient
- 레퍼런스: [YouTube Audio Library / Epidemic Sound 카테고리]

## 파일 사양
- Resolution: 1080×1920 (9:16)
- Format: MP4, H.264, 30fps
- 파일 크기: <30MB (Meta 권장)
- 캡션: SRT 별도 파일
- 썸네일: 1080×1920 정지 이미지

## 제작 순서
1. 이미지/영상 생성 (Imagen + 언리얼)
2. 나레이션 TTS 생성 (Qwen)
3. 캡션 SRT 작성
4. 편집 병합 (DaVinci/Premiere)
5. 플랫폼 업로드 포맷 변환

## 대체 변형 (A/B용)
이 브리프의 변형 3개 자동 제안:
- **변형 B**: 여성 화자 버전 (여성 페르소나 타겟)
- **변형 C**: 자막만 버전 (음소거 재생용)
- **변형 D**: 영문 더빙 (글로벌 타겟)
```

## 작업 지침

1. **카피와 비주얼 일관성**: 카피의 앵글과 비주얼 톤이 **반드시 일치**해야 함. 공포 카피에 밝은 이미지 → 인지 부조화.

2. **플랫폼 제약 엄수**: 
   - 파일 크기, 해상도, 길이, 자막 필수 여부
   - 크리에이티브 정책 (Meta 금지 요소, Google 광고 승인 기준)

3. **접근성**: 
   - 자막/캡션 필수 (85% 무음 재생)
   - 색약 대비 (텍스트-배경 명도 4.5:1 이상)
   - 빠른 플래시 금지 (발작 유발)

4. **문화적 민감성**: 
   - OneMessage는 "사망" 관련 → 문화권별 표현 조심
   - 종교/민감 상징 피하기
   - 한국 vs 일본 vs 서양 톤 다름

5. **제작 리소스 현실성**: 
   - 메타휴먼 렌더링 시간/비용 고려
   - TTS 생성 시간 (Qwen 로컬)
   - Imagen API 비용
   - 1개 브리프 → 여러 플랫폼 변형 가능하게 설계

6. **A/B 대비 다중 변형**: 1 브리프에서 **2~4개 변형** 함께 제안 (플랫폼별, 페르소나별, 앵글별).

7. **버전 관리**: 브리프에 버전 번호/날짜. 카피 수정 시 브리프 재생성.

8. **기존 자산 활용**: `assets/generated/{platform}/` 폴더의 기존 이미지/영상 재사용 가능성 먼저 검토.

## OneMessage 프로젝트 맥락
- 주 제품: 사망 감지 메시징 (크립토 자산 상속)
- 시각 방향: "따뜻한 준비" > "공포" (일반적으로 우세)
- 금기: 노골적 죽음 묘사 (Meta 거부 사례)
- 선호 표현: 가족, 편지, 연결, 시간, 기억
- 색상 선호: 파란색 계열 (신뢰, 차분함)
- 아바타: 언리얼 메타휴먼 + Qwen TTS (로컬 생성, 비용 0)
- 이미지: Imagen 4.0 (API 비용 있음)
- 저장: `assets/generated/{platform}/` (메타/구글/트위터/블로그)
