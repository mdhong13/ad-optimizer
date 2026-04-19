# Meta Pixel 설정 가이드

랜딩 페이지(onemsg.net)에 Meta Pixel 을 삽입해 광고 클릭 → 페이지 조회 → 전환을 추적.
대시보드는 캠페인/광고 단위 Meta Insights 로 노출/클릭 이미 보지만, **페이지에서의 행동(CTA 클릭, 설치 의도, 가입)** 은 Pixel 로만 측정 가능.

---

## 1. Events Manager 에서 Pixel 생성

1. https://business.facebook.com/events_manager 접속
2. 좌측 **데이터 소스 연결** → **웹** 선택 → 다음
3. 데이터 세트 이름: `OneMessage Web` → 만들기
4. 생성된 **Pixel ID** (15~16자리 숫자) 복사

## 2. 환경 변수 설정

로컬:
```bash
# .env
META_PIXEL_ID=123456789012345
```

Railway:
- Dashboard → ad-optimizer 서비스 → Variables → `META_PIXEL_ID` 추가
- 저장 후 자동 재배포 (~2분)

## 3. onemsg.net 랜딩에 JS 삽입

`<head>` 안 최상단에 (Google Analytics 앞):

```html
<!-- Meta Pixel -->
<script>
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', 'YOUR_PIXEL_ID');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id=YOUR_PIXEL_ID&ev=PageView&noscript=1"/></noscript>
<!-- End Meta Pixel -->
```

`YOUR_PIXEL_ID` → 위에서 복사한 15자리로 치환.

## 4. 커스텀 이벤트 (CTA 버튼 클릭 등)

```html
<button onclick="fbq('track', 'Lead'); location.href='https://play.google.com/...'">
  앱 설치하기
</button>
```

표준 이벤트 목록:
- `PageView` — 페이지 로드 (자동)
- `Lead` — 관심 표명 (CTA 클릭, 이메일 입력)
- `CompleteRegistration` — 회원가입 완료
- `Subscribe` — 구독 시작
- `InitiateCheckout` — 결제 시작
- `Purchase` — 결제 완료 (`{value: 9.99, currency: 'USD'}`)

## 5. Events Manager 에서 검증

1. Events Manager → 테스트 이벤트 탭
2. `https://onemsg.net` 접속
3. "PageView" 이벤트가 실시간 찍히는지 확인
4. 버튼 클릭 → "Lead" 이벤트 확인

## 6. 캠페인 최적화 목표로 사용

Meta Ads Manager 에서 캠페인 생성 시:
- **Traffic** 목표 → 랜딩 클릭 최대화
- **Sales/Leads** 목표 → Pixel 의 `Purchase`/`Lead` 이벤트 최대화
- 앱 캠페인(OUTCOME_APP_PROMOTION)은 Pixel 대신 **SDK/MMP 연동** 필요 (별도)

## 7. 코드에서 Pixel 참조

`config/settings.py`:
```python
META_PIXEL_ID: str = os.getenv("META_PIXEL_ID", "")
```

캠페인 최적화를 Pixel 이벤트에 맞추려면 AdSet `promoted_object`:
```python
{
    "pixel_id": settings.META_PIXEL_ID,
    "custom_event_type": "LEAD",  # 또는 PURCHASE, COMPLETE_REGISTRATION
}
```

## ⚠️ 주의

- Pixel 은 **웹 전용**. 앱 설치 캠페인에는 MMP(AppsFlyer/Adjust) 또는 Facebook SDK 필요
- iOS 14+ 에서 ATT 프롬프트 거부 시 일부 이벤트 손실 (Aggregated Event Measurement)
- 개인정보 필드(이메일/전화) 전송 시 Meta 가 자동 해시 — 그래도 유저 동의 필수
- Ad Blocker 탐지 대응으로 **Conversions API (CAPI)** 병행 권장 (서버→Meta)

## 📁 관련 파일

- `config/settings.py` — `META_PIXEL_ID`
- `config/platforms/meta.yaml` — Pixel 필드 기록
- (TODO) `publisher/platforms/capi.py` — Conversions API 서버 구현
