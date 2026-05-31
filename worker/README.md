# knowin 자동 게시 worker — 본인 PC 로컬 실행

⚠️ **본인 PC 에서만 실행**. 네이버 비번·쿠키 노출 위험 — Railway·서버 박지 X.

## 정책
- 네이버 약관: 자동화 게시 모호한 회색지대. 신중하게.
- 시민 등급 신규 답변자: 일 5~10건 권장. 초기 1주는 3건.
- reCAPTCHA 떠면 자동 중단. 본인 처리.
- 답변자 ID 분산 (norsunglae / livecanvas 교대).

## 설치

```bash
cd D:\0_Dotcell\ad-optimizer\worker
pip install playwright requests python-dotenv
python -m playwright install chromium
```

## env 설정

`worker/.env` (gitignore 되어있음, 커밋 X):
```env
KNOWIN_WORKER_API_KEY=<Railway env 와 동일한 값>
KNOWIN_BASE_URL=https://adteam.onemsg.net
KNOWIN_WORKER_ID=local-pc-1
KNOWIN_DAILY_LIMIT=5
```

Railway 측에도 동일 API 키 박음 (Settings → Variables):
```
KNOWIN_WORKER_API_KEY=<랜덤 32자 hex 등>
```

## 첫 실행 — 로그인 + 쿠키 저장

각 계정에 한 번씩:

```bash
# norsunglae 계정
python knowin_auto_poster.py --login --account nors
# → 브라우저 뜸 → 본인 ID 로 로그인 → 터미널에 Enter → .kin_state_nors.json 저장

# livecanvas 계정
python knowin_auto_poster.py --login --account live
# → .kin_state_live.json 저장
```

저장된 쿠키 파일 (`.kin_state_*.json`) 은 **gitignore + 절대 공유 X**.

## 운영

```bash
# 백그라운드 실행 (norsunglae 계정, 일 5건)
python knowin_auto_poster.py --account nors --daily-limit 5

# 또 다른 터미널 — livecanvas 동시 운영 가능
python knowin_auto_poster.py --account live --daily-limit 5

# 헤드리스 모드 (브라우저 안 보임 — 디버깅 끝나면)
python knowin_auto_poster.py --account nors --headless
```

## 흐름

1. ad-optimizer 카드에서 `🤖 자동 게시 큐` 버튼 누름 → MongoDB `knowin_post_queue` 에 job insert
2. worker 가 60~180초마다 polling — `GET /knowin/post-queue/next`
3. job 받으면 Playwright 가 답변 페이지 이동 + form 박기 + 등록 클릭
4. 결과 보고 — `POST /knowin/post-queue/report/{job_id}`
   - `done`: 등록 메시지 감지. ad-optimizer 가 페이지 fetch 검수 자동 트리거
   - `failed`: form 못 찾음·예외 등
   - `captcha-stop`: reCAPTCHA — worker 중단 + 본인 알림

## 한도

- 분당 1건 (강제 gap)
- 일 한도 (`--daily-limit`, 기본 5)
- 지터 60~180초 (`--poll-min`, `--poll-max`)
- 일 한도 도달 시 24h sleep

## 보안

- `.kin_state_*.json` — 본인 PC 만. gitignore + 절대 공유 X.
- `.env` — API 키. gitignore.
- worker 가 ad-optimizer 측에 비번·쿠키 전송 X. 결과만 보고.

## 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| `쿠키 없음` 에러 | login 안 박음 | `--login` 으로 첫 실행 |
| `KNOWIN_WORKER_API_KEY 미설정` | worker/.env 또는 OS env 누락 | env 박기 |
| `answer form not found` | 네이버 페이지 구조 변경 또는 답변 차단 | 셀렉터 업데이트 또는 해당 link 수동 확인 |
| `reCAPTCHA detected` | 네이버 자동 의심 | 일 한도 ↓, 지터 ↑, 며칠 wait |
| 401 unauthorized | API 키 불일치 | Railway env 와 본인 PC env 동일한지 확인 |
| 답변 등록됐는데 페이지엔 안 박힘 | 노출 보류 (시민 등급) | 시간 지나면 노출. 24h 후 검수 다시 |

## 모니터링

브라우저에서 `https://adteam.onemsg.net/knowin` →
- 상단 🤖 자동 게시 worker 큐 카드 — 실시간 status (queued/in_progress/done/failed/captcha-stop)
- "오늘 done N" 카운트 — 일 한도 추적

## 중단

worker 프로세스 Ctrl+C. captcha-stop 또는 일 한도 도달 시 자동 중단.
