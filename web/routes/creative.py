"""
크리에이티브 생성 라우트 — 카피 / 이미지 / 영상.

- GET  /creative/copy|image|video  페이지 렌더
- POST /creative/copy/generate      LLM 호출 (동기)
- POST /creative/image/generate     Nano Banana 등 (동기)
- POST /creative/video/start        Veo 비동기 작업 시작
- GET  /creative/video/status       Veo 작업 폴링
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates

from creative import copy_gen, image_gen, video_gen, prompt_gen, image_resize, tts, tts_script_gen, voices, subtitle, anchor_gen, frame_extract
from creative.models import (
    COPY_PROVIDERS, COPY_DEFAULT_ID,
    IMAGE_MODELS, IMAGE_DEFAULT_ID,
    VIDEO_MODELS, VIDEO_DEFAULT_ID,
)
from storage.db import get_collection
from agent.telegram import notify_safe

log = logging.getLogger(__name__)

# 카피 batch brief 풀 (정의는 read-only 파일, 로테이션 상태는 DB)
BRIEFS_PATH = Path(__file__).resolve().parents[2] / "creative" / "copy_briefs.json"

router = APIRouter(prefix="/creative")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# ---------- Pages ----------

@router.get("")
async def creative_root(request: Request):
    return templates.TemplateResponse(request, "creative_copy.html", {
        "providers": COPY_PROVIDERS, "default_provider": COPY_DEFAULT_ID,
    })


@router.get("/copy")
async def page_copy(request: Request):
    # 스토리보드 페이지 — 카피 + 3샷 영상 프롬프트 전용. TTS/이미지 옵션은 각 페이지로 이동.
    return templates.TemplateResponse(request, "creative_copy.html", {
        "providers": COPY_PROVIDERS, "default_provider": COPY_DEFAULT_ID,
    })


@router.get("/image")
async def page_image(request: Request):
    return templates.TemplateResponse(request, "creative_image.html", {
        "models": IMAGE_MODELS, "default_model": IMAGE_DEFAULT_ID,
        "platform_sizes": image_resize.PLATFORM_SIZES,
        "providers": COPY_PROVIDERS, "default_provider": COPY_DEFAULT_ID,
    })


@router.get("/video")
async def page_video(request: Request):
    return templates.TemplateResponse(request, "creative_video.html", {
        "models": VIDEO_MODELS, "default_model": VIDEO_DEFAULT_ID,
        "voice_presets": voices.load_voice_presets(),
    })


# ---------- API: Copy ----------

@router.post("/copy/generate")
async def api_copy_generate(payload: dict):
    brief = payload.get("brief") or {}
    provider_id = payload.get("provider_id") or COPY_DEFAULT_ID
    try:
        result = await copy_gen.generate_copy(brief, provider_id)
    except Exception as e:
        log.exception("[creative.copy] generate failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ---------- API: Copy batch (검토 큐 + Telegram, DRY_RUN — 게시 X) ----------
# Phase 3: 기존 generate 에 [저장 → 검토 큐 → Telegram] 한 겹.
# routine 이 매일 트리거 → brief 풀 로테이션 → 검토 카드 → 사람 ✅/🗑.
# 절대 자동 게시 X — 생성물은 copy_review_queue 까지만.

def _load_briefs() -> List[dict]:
    if not BRIEFS_PATH.exists():
        return []
    data = json.loads(BRIEFS_PATH.read_text(encoding="utf-8"))
    return [b for b in (data.get("briefs") or []) if b.get("id")]


def _pick_brief(briefs: List[dict], brief_id: Optional[str]) -> dict:
    """brief_id 지정 시 그것, 아니면 last_used 오래된 순(미사용 우선) 로테이션."""
    if brief_id:
        for b in briefs:
            if b.get("id") == brief_id:
                return b
    state = {s["brief_id"]: s.get("last_used_at")
             for s in get_collection("copy_brief_state").find({}, {"_id": 0})}
    _floor = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(briefs, key=lambda b: (state.get(b["id"]) is not None,
                                         state.get(b["id"]) or _floor))[0]


@router.post("/copy/batch")
async def api_copy_batch(payload: Optional[dict] = None):
    """brief 풀 1건 → 카피 생성 → copy_review_queue 저장 → Telegram 검토 알림.

    payload(선택): {"brief_id": "...", "brief": {...직접...}, "provider_id": "local-vllm"}
    payload 없으면 풀에서 로테이션. provider 기본 = local-vllm (무료 d4win).
    """
    payload = payload or {}
    provider_id = payload.get("provider_id") or "local-vllm"
    brief = payload.get("brief")
    brief_id = payload.get("brief_id")
    if not brief:
        briefs = _load_briefs()
        if not briefs:
            raise HTTPException(status_code=400, detail="brief 풀 비어있음 (creative/copy_briefs.json)")
        brief = _pick_brief(briefs, brief_id)
        brief_id = brief.get("id")

    try:
        result = await copy_gen.generate_copy(brief, provider_id)
    except Exception as e:
        log.exception("[creative.copy.batch] generate failed")
        notify_safe(f"❌ 카피 batch 생성 실패 — {brief.get('campaign', brief_id)}: {e}", sender="copy")
        raise HTTPException(status_code=500, detail=str(e))

    variants = result.get("variants") or []
    now = datetime.now(timezone.utc)
    batch_id = uuid.uuid4().hex[:12]
    docs = []
    for v in variants:
        docs.append({
            "variant_id": uuid.uuid4().hex[:12],
            "batch_id": batch_id,
            "brief_id": brief_id,
            "campaign": brief.get("campaign"),
            "platform": brief.get("platform"),
            "language": brief.get("language"),
            "variant": v,
            "model": result.get("_meta", {}).get("model"),
            "provider_id": result.get("_meta", {}).get("provider_id"),
            "status": "pending",   # pending → accepted | rejected (게시는 별도, 사람 수동)
            "created_at": now,
        })
    if docs:
        get_collection("copy_review_queue").insert_many(docs)
    get_collection("copy_brief_state").update_one(
        {"brief_id": brief_id}, {"$set": {"last_used_at": now}}, upsert=True
    )

    notify_safe(
        f"✍️ 카피 검토 대기 {len(docs)}건\n"
        f"· {brief.get('campaign', '(brief)')}\n"
        f"· {brief.get('platform')} / {brief.get('language')}\n"
        f"검토: /creative/copy/review",
        sender="copy",
    )
    return {"ok": True, "batch_id": batch_id, "count": len(docs),
            "brief_id": brief_id, "model": result.get("_meta", {}).get("model")}


@router.get("/copy/review/list")
async def api_copy_review_list(status: str = "pending", limit: int = 60):
    """검토 큐 조회 (JSON). chunk 2 에서 카드 UI 가 소비."""
    coll = get_collection("copy_review_queue")
    filt = {} if status == "all" else {"status": status}
    rows = list(coll.find(filt, {"_id": 0}).sort("created_at", -1).limit(limit))
    for r in rows:
        if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("reviewed_at") and hasattr(r["reviewed_at"], "isoformat"):
            r["reviewed_at"] = r["reviewed_at"].isoformat()
    counts = {s: coll.count_documents({"status": s}) for s in ("pending", "accepted", "rejected")}
    return {"rows": rows, "counts": counts}


@router.post("/copy/review/{variant_id}/{action}")
async def api_copy_review_action(variant_id: str, action: str):
    """카피 변형 채택/버림. action: accept | reject."""
    if action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="action은 accept 또는 reject")
    new_status = "accepted" if action == "accept" else "rejected"
    r = get_collection("copy_review_queue").update_one(
        {"variant_id": variant_id},
        {"$set": {"status": new_status, "reviewed_at": datetime.now(timezone.utc)}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="variant_id 없음")
    return {"ok": True, "variant_id": variant_id, "status": new_status}


# ---------- API: Storyboard (anchor extraction + 3-shot video prompts) ----------

@router.post("/storyboard/anchor")
async def api_storyboard_anchor(payload: dict):
    """스토리 → 씬 앵커(Character + Setting) 추출."""
    story = (payload.get("story") or "").strip()
    if not story:
        raise HTTPException(status_code=400, detail="story 필수")
    provider_id = payload.get("provider_id") or COPY_DEFAULT_ID
    try:
        result = await anchor_gen.extract_anchor(story, provider_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("[creative.storyboard] anchor failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/storyboard/shots")
async def api_storyboard_shots(payload: dict):
    """앵커 + 스토리 → N샷 영상 프롬프트(각 8초, 앵커 주입 + 얼굴 회피 옵션)."""
    story = (payload.get("story") or "").strip()
    if not story:
        raise HTTPException(status_code=400, detail="story 필수")
    anchor = payload.get("anchor") or {}
    aspect_ratio = payload.get("aspect_ratio") or "9:16"
    n = int(payload.get("n") or 3)
    n = max(1, min(n, 3))
    face_avoid = bool(payload.get("face_avoid"))
    provider_id = payload.get("provider_id") or COPY_DEFAULT_ID
    try:
        result = await prompt_gen.generate_prompts(
            target="video",
            brief_text=story,
            aspect_ratio=aspect_ratio,
            n=n,
            provider_id=provider_id,
            anchor=anchor,
            face_avoid=face_avoid,
        )
    except Exception as e:
        log.exception("[creative.storyboard] shots failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ---------- API: Prompt generation (detailed English prompts for image/video) ----------

@router.post("/prompt/generate")
async def api_prompt_generate(payload: dict):
    target = (payload.get("target") or "").strip()
    if target not in ("image", "video"):
        raise HTTPException(status_code=400, detail="target은 'image' 또는 'video'")
    brief_text = (payload.get("brief_text") or "").strip()
    if not brief_text:
        raise HTTPException(status_code=400, detail="brief_text 필수")
    aspect_ratio = payload.get("aspect_ratio") or ""
    n = int(payload.get("n") or 2)
    # Veo 3.1은 8초/샷 고정 — 영상 프롬프트는 최대 3개(=24s 스티칭)
    if target == "video":
        n = max(1, min(n, 3))
    provider_id = payload.get("provider_id") or COPY_DEFAULT_ID
    phone_screen_text = (payload.get("phone_screen_text") or "").strip()
    must_show = (payload.get("must_show") or "").strip()
    screen_text_language = (payload.get("screen_text_language") or "en").strip().lower()
    try:
        result = await prompt_gen.generate_prompts(
            target, brief_text, aspect_ratio, n, provider_id,
            phone_screen_text=phone_screen_text,
            must_show=must_show,
            screen_text_language=screen_text_language,
        )
    except Exception as e:
        log.exception("[creative.prompt] generate failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ---------- API: Image ----------

@router.post("/image/generate")
async def api_image_generate(payload: dict):
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt 필수")
    model_id = payload.get("model_id") or IMAGE_DEFAULT_ID
    aspect_ratio = payload.get("aspect_ratio") or "4:5"
    n = int(payload.get("n") or 1)
    try:
        results = await image_gen.generate_image(prompt, model_id, aspect_ratio, n)
    except Exception as e:
        log.exception("[creative.image] generate failed")
        raise HTTPException(status_code=500, detail=str(e))
    return {"images": results}


@router.post("/image/resize")
async def api_image_resize(payload: dict):
    """
    원본 이미지를 선택된 플랫폼 사이즈로 center-crop + resize.
    payload: {"source": "/assets/generated/creative/image/foo.jpg", "platform_keys": [...]}
    """
    source = (payload.get("source") or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="source 필수")
    keys = payload.get("platform_keys") or []
    if not keys:
        raise HTTPException(status_code=400, detail="platform_keys 한 개 이상 필요")
    fit = (payload.get("fit") or "cover").strip()
    try:
        results = image_resize.resize_to_platforms(source, keys, fit=fit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("[creative.image.resize] failed")
        raise HTTPException(status_code=500, detail=str(e))
    return {"results": results}


# ---------- API: TTS ----------

@router.get("/tts/voices")
async def api_tts_voices():
    return {"presets": voices.load_voice_presets()}


@router.post("/tts/script")
async def api_tts_script(payload: dict):
    story = (payload.get("story") or payload.get("brief_text") or "").strip()
    if not story:
        raise HTTPException(status_code=400, detail="story 필수")
    n_shots = int(payload.get("n_shots") or 3)
    language = (payload.get("language") or "en").strip().lower()
    provider_id = payload.get("provider_id") or COPY_DEFAULT_ID
    try:
        result = await tts_script_gen.generate_script(story, n_shots, language, provider_id)
    except Exception as e:
        log.exception("[creative.tts] script failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/tts/synthesize")
async def api_tts_synthesize(payload: dict):
    preset_id = (payload.get("preset_id") or "").strip()
    text = (payload.get("text") or "").strip()
    if not preset_id:
        raise HTTPException(status_code=400, detail="preset_id 필수")
    if not text:
        raise HTTPException(status_code=400, detail="text 필수")
    options = payload.get("options") or {}
    try:
        result = await tts.synthesize(preset_id, text, options)
    except Exception as e:
        log.exception("[creative.tts] synthesize failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ---------- API: Video ----------

@router.post("/video/start")
async def api_video_start(payload: dict):
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt 필수")
    model_id = payload.get("model_id") or VIDEO_DEFAULT_ID
    aspect_ratio = payload.get("aspect_ratio") or "9:16"
    duration = int(payload.get("duration_seconds") or 8)
    image_path = (payload.get("image_path") or "").strip() or None
    image_mime = (payload.get("image_mime_type") or "image/jpeg").strip()
    try:
        job = await video_gen.start_video_job(
            prompt, model_id, aspect_ratio, duration,
            image_path=image_path, image_mime_type=image_mime,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("[creative.video] start failed")
        raise HTTPException(status_code=500, detail=str(e))
    return job


@router.post("/video/extract-frame")
async def api_video_extract_frame(payload: dict):
    """영상의 마지막 프레임을 JPG 로 추출 — 다음 샷 image-to-video 용."""
    video = (payload.get("video") or "").strip()
    if not video:
        raise HTTPException(status_code=400, detail="video 필수")
    try:
        result = await frame_extract.extract_last_frame(video)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.exception("[creative.video] extract-frame failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.get("/video/status")
async def api_video_status(op: str):
    if not op:
        raise HTTPException(status_code=400, detail="op(operation_name) 필수")
    try:
        status = await video_gen.poll_video_job(op)
    except Exception as e:
        log.exception("[creative.video] poll failed")
        raise HTTPException(status_code=500, detail=str(e))
    return status


@router.post("/video/subtitle")
async def api_video_subtitle(payload: dict):
    """
    샷별 video + (선택) TTS 오디오 + (선택) 자막 → 단일 mp4 burn-in.

    payload:
      {
        "shots": [{"video": "...", "audio": "..."|null, "subtitle": "..."|null}, ...],
        "lang": "kr" | "en"
      }
    """
    shots = payload.get("shots") or []
    if not shots:
        raise HTTPException(status_code=400, detail="shots 필수")
    lang = (payload.get("lang") or "kr").lower()
    try:
        result = await subtitle.render_video(shots, lang=lang)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        # ffmpeg 미설치 / 실행 실패
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.exception("[creative.subtitle] failed")
        raise HTTPException(status_code=500, detail=str(e))
    return result


