---
description: 광고 소재(이미지/영상/음성) 제작 브리프 생성 - Imagen, 메타휴먼, Qwen TTS 입력용
argument-hint: [캠페인명 또는 카피 변형 ID]
---

Creative Brief 스킬을 실행합니다.

## 입력
$ARGUMENTS

## 지침
`.claude/skills/creative-brief/SKILL.md`의 프레임워크를 따라:

1. **전제 확인**: ad-copy 결과 + audience-analysis 필요. 없으면 선행 안내
2. **소재 유형 결정**: Static Image / Video / Carousel / Interactive 중 플랫폼에 맞게
3. **시각 방향**: 앵글별 컬러/스타일/감정/구도 (공포/사랑/효율/권위 등 매칭 테이블 참조)
4. **플랫폼 포맷 엄수**: 크기, 비율, 파일 크기, 자막 요구사항
5. **메타휴먼 아바타 지시** (영상 시): 캐릭터/의상/표정/제스처/카메라/배경
6. **Qwen TTS 음성 브리프**: 언어/스타일/속도/피치/강조
7. **Imagen/Midjourney 프롬프트**: 구체적 영어 프롬프트 + 파라미터
8. **A/B용 변형 3~4개 동시 제안**: 플랫폼별/페르소나별/앵글별

**중요**: 카피와 비주얼의 **앵글 일관성 필수**. 접근성(자막, 색약), 문화 민감성(크립토 + 사망 주제), OneMessage 선호 톤("따뜻한 준비" > 공포) 반영. 기존 `assets/generated/` 자산 재사용 가능성 먼저 검토.
