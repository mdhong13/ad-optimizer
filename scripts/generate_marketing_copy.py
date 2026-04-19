"""
OneMessage 마케팅 카피 생성 스크립트
Gemini API를 사용하여 메인 페이지 제목/문구 + 매체별 광고 소재 생성
"""
import json
import httpx
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

PRODUCT_CONTEXT = """
## OneMessage 제품 정보

### 안심메시지 (Safety Message)
- 백그라운드 앱이 스마트폰 사용을 감지
- 12시간 미사용 시 지정 번호로 SMS 발송: "1월 19일 안성회님이 12시간 동안 스마트폰을 사용하지 않았습니다. 전화로 안부를 확인해 주세요."
- 주 1회 무료 메시지 제공
- 매일 안심 메시지 옵션: "1월 19일 오늘 하루 안성회님은 잘 지내고 있습니다."

### 원메시지 (One Message)
- AWS 클라우드 서버에 저장 - 스마트폰이 꺼지거나, 파손되거나, 바다에 빠져도 100% 발송
- 설정한 타이머(최대 7일) 만료 시 수신자에게 자동 전송
- 스마트폰 사용 감지 시 체크인 → 타이머 리셋
- 비상 복구 비밀번호로 메시지 복원 가능
- SMS 보안 주의: 암호화폐 프라이빗 키 직접 기재 금지, 보관 장소 안내 권장
- 예시: "너에게 선물을 남겼어. 아빠 서재에서 칼 세이건의 코스모스를 열어봐."
- 예시: "비트코인 지갑 프라이빗 키는 양말 서랍 안쪽 겉과 속이 다른 양말 뭉치 속. 100개야. 당신은 이제 부자야."

### 원메시지 프로 (One Message Pro)
- 최대 1년 타이머
- 여러 메시지를 각각 다른 타이머로 저장
- SMS 카운트다운 알림 (Day3, Day2, 1시간 전) + 타이머 리셋 링크
- 앱 삭제 후에도 링크로 타이머 리셋 가능
- 10일 이상 타이머 권장 (혼수 상태 대비)
- 안전 확인 메시지 설정 권장: 중요 메시지 전에 가족/지인에게 상태 확인 메시지

## 타겟 오디언스
- 암호화폐 개인 지갑 보유자 (프라이빗 키 전달 필요성)
- 고위험 직업군 (군인, 소방관, 경찰 등)
- 해외 거주자/여행자
- 고령 가족 돌봄 관계자
- 디지털 자산 보유자 전반

## 핵심 가치
1. 100% 전송 보장 (클라우드 기반)
2. 자동 생존 감지 (체크인 시스템)
3. 암호화폐 자산 보호 (프라이빗 키 전달)
4. 가족 안심 (일상 안부 확인)
"""


def call_gemini(prompt: str) -> str:
    """Gemini API 호출"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 16384,
        }
    }
    resp = httpx.post(GEMINI_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_main_page_copy():
    """메인 페이지 제목과 문구 생성"""
    prompt = f"""
당신은 앱 마케팅 전문 카피라이터입니다.

{PRODUCT_CONTEXT}

## 요청
OneMessage 앱의 **메인 페이지(앱스토어/웹사이트 랜딩 페이지)** 제목과 문구를 작성해주세요.

### 출력 형식 (JSON)
```json
{{
  "main_titles": [
    {{
      "title_kr": "한국어 제목",
      "title_en": "English Title",
      "subtitle_kr": "한국어 부제",
      "subtitle_en": "English Subtitle"
    }}
  ],
  "hero_copy": [
    {{
      "angle": "어떤 관점 (예: 크립토, 가족안심, 긴급상황)",
      "headline_kr": "헤드라인 한국어",
      "headline_en": "Headline English",
      "body_kr": "본문 한국어 (2-3문장)",
      "body_en": "Body English (2-3 sentences)",
      "cta_kr": "CTA 버튼 텍스트",
      "cta_en": "CTA Button Text"
    }}
  ],
  "taglines": [
    {{
      "kr": "한국어 태그라인",
      "en": "English Tagline"
    }}
  ]
}}
```

### 조건
- main_titles: 5개 (다양한 톤 - 감성적, 실용적, 긴급한, 신뢰감, 도발적)
- hero_copy: 4개 (크립토 자산 보호, 가족 안심, 긴급 상황 대비, 디지털 유산 각도)
- taglines: 8개 (짧고 임팩트 있는)
- 한국어와 영어 모두 제공
- 암호화폐 지갑 소유자를 주요 타겟으로
- 감정적 호소와 실용적 가치 모두 포함
- JSON만 출력, 다른 텍스트 없이
"""
    return call_gemini(prompt)


def generate_ad_creatives():
    """매체별 광고 소재 생성"""
    prompt = f"""
당신은 디지털 광고 전문 카피라이터입니다.

{PRODUCT_CONTEXT}

## 요청
각 광고 매체에 맞는 광고 소재(텍스트 카피)를 작성해주세요.

### 출력 형식 (JSON)
```json
{{
  "google_ads": {{
    "search": [
      {{
        "headline_1": "30자 이내",
        "headline_2": "30자 이내",
        "headline_3": "30자 이내",
        "description_1": "90자 이내",
        "description_2": "90자 이내",
        "target_keywords": ["키워드1", "키워드2"]
      }}
    ],
    "display": [
      {{
        "headline": "30자 이내",
        "long_headline": "90자 이내",
        "description": "90자 이내",
        "image_suggestion": "이미지 컨셉 설명"
      }}
    ]
  }},
  "meta_ads": {{
    "facebook": [
      {{
        "primary_text": "본문 (125자 권장)",
        "headline": "40자 이내",
        "description": "30자 이내",
        "cta": "CTA 버튼",
        "image_suggestion": "이미지 컨셉",
        "target_audience": "타겟 설명"
      }}
    ],
    "instagram": [
      {{
        "caption": "인스타그램 캡션 (2200자 이내, 해시태그 포함)",
        "image_suggestion": "이미지/릴스 컨셉",
        "story_text": "스토리용 짧은 텍스트"
      }}
    ]
  }},
  "twitter_x": [
    {{
      "tweet_text": "280자 이내 (해시태그 포함)",
      "thread_hook": "스레드 첫 번째 트윗",
      "image_suggestion": "이미지 컨셉"
    }}
  ],
  "reddit": [
    {{
      "title": "게시물 제목",
      "body": "본문 (자연스러운 톤, 광고 느낌 최소화)",
      "target_subreddit": "추천 서브레딧",
      "angle": "접근 각도"
    }}
  ]
}}
```

### 조건
- google_ads.search: 5세트 (크립토 보호, 디지털 유산, 긴급 메시지, 가족 안심, 일반)
- google_ads.display: 3세트
- meta_ads.facebook: 4세트 (A/B 테스트용)
- meta_ads.instagram: 3세트
- twitter_x: 5세트 (크립토 커뮤니티 타겟)
- reddit: 3세트 (r/cryptocurrency, r/Bitcoin, r/personalfinance)
- 한국어와 영어 버전 모두 포함 (각 필드에 _kr, _en 접미사 추가)
- 크립토 시장 이벤트 활용 가능한 동적 소재 포함
- JSON만 출력, 다른 텍스트 없이
"""
    return call_gemini(prompt)


def generate_content_marketing():
    """콘텐츠 마케팅용 블로그/SEO 카피"""
    prompt = f"""
당신은 콘텐츠 마케팅 전문가입니다.

{PRODUCT_CONTEXT}

## 요청
OneMessage 관련 콘텐츠 마케팅 소재를 작성해주세요.

### 출력 형식 (JSON)
```json
{{
  "blog_titles": [
    {{
      "title_kr": "블로그 제목 한국어",
      "title_en": "Blog Title English",
      "category": "카테고리 (crypto/safety/digital-legacy/family)",
      "seo_keywords_kr": ["키워드"],
      "seo_keywords_en": ["keywords"],
      "outline_kr": "간략 개요",
      "outline_en": "Brief outline"
    }}
  ],
  "email_subject_lines": [
    {{
      "subject_kr": "이메일 제목",
      "subject_en": "Email Subject",
      "preview_kr": "프리뷰 텍스트",
      "preview_en": "Preview text"
    }}
  ],
  "app_store_copy": {{
    "short_description_kr": "80자 이내",
    "short_description_en": "80 chars max",
    "long_description_kr": "4000자 이내 앱스토어 설명",
    "long_description_en": "4000 chars max app store description",
    "whats_new_kr": "업데이트 노트",
    "whats_new_en": "What's New note",
    "keywords_kr": ["키워드 목록"],
    "keywords_en": ["keyword list"]
  }}
}}
```

### 조건
- blog_titles: 8개 (다양한 카테고리)
- email_subject_lines: 6개 (오픈율 최적화)
- app_store_copy: 완전한 앱스토어 등록용 카피
- 한국어/영어 모두 포함
- JSON만 출력, 다른 텍스트 없이
"""
    return call_gemini(prompt)


def clean_json_response(text: str) -> str:
    """Gemini 응답에서 JSON 추출"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def main():
    output_dir = "D:/0_Dotcell/ad-optimizer/docs/generated"
    os.makedirs(output_dir, exist_ok=True)

    results = {}

    # 1. 메인 페이지 카피
    print("=" * 60)
    print("[1/3] 메인 페이지 제목/문구 생성 중...")
    print("=" * 60)
    try:
        raw = generate_main_page_copy()
        cleaned = clean_json_response(raw)
        try:
            data = json.loads(cleaned)
            results["main_page"] = data
            print("  -> 성공!")
        except json.JSONDecodeError:
            results["main_page_raw"] = raw
            print("  -> JSON 파싱 실패, raw 텍스트 저장")
    except Exception as e:
        print(f"  -> 오류: {e}")
        results["main_page_error"] = str(e)

    # 2. 매체별 광고 소재
    print("\n" + "=" * 60)
    print("[2/3] 매체별 광고 소재 생성 중...")
    print("=" * 60)
    try:
        raw = generate_ad_creatives()
        cleaned = clean_json_response(raw)
        try:
            data = json.loads(cleaned)
            results["ad_creatives"] = data
            print("  -> 성공!")
        except json.JSONDecodeError:
            results["ad_creatives_raw"] = raw
            print("  -> JSON 파싱 실패, raw 텍스트 저장")
    except Exception as e:
        print(f"  -> 오류: {e}")
        results["ad_creatives_error"] = str(e)

    # 3. 콘텐츠 마케팅
    print("\n" + "=" * 60)
    print("[3/3] 콘텐츠 마케팅 소재 생성 중...")
    print("=" * 60)
    try:
        raw = generate_content_marketing()
        cleaned = clean_json_response(raw)
        try:
            data = json.loads(cleaned)
            results["content_marketing"] = data
            print("  -> 성공!")
        except json.JSONDecodeError:
            results["content_marketing_raw"] = raw
            print("  -> JSON 파싱 실패, raw 텍스트 저장")
    except Exception as e:
        print(f"  -> 오류: {e}")
        results["content_marketing_error"] = str(e)

    # 결과 저장
    output_file = os.path.join(output_dir, "marketing_copy_all.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n전체 결과 저장: {output_file}")

    # 개별 파일도 저장
    for key in ["main_page", "ad_creatives", "content_marketing"]:
        if key in results:
            individual_file = os.path.join(output_dir, f"{key}.json")
            with open(individual_file, "w", encoding="utf-8") as f:
                json.dump(results[key], f, ensure_ascii=False, indent=2)
            print(f"개별 저장: {individual_file}")

    print("\n완료!")
    return results


if __name__ == "__main__":
    main()
