"""
크리에이티브 생성 라우트 — 카피 / 이미지 / 영상.

- GET  /creative/copy|image|video  페이지 렌더
- POST /creative/copy/generate      LLM 호출 (동기)
- POST /creative/image/generate     Nano Banana 등 (동기)
- POST /creative/video/start        Veo 비동기 작업 시작
- GET  /creative/video/status       Veo 작업 폴링
"""
from __future__ import annotations
import logging
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates

from creative import copy_gen, image_gen, video_gen, prompt_gen, image_resize, tts, tts_script_gen, voices, subtitle, anchor_gen, frame_extract
from creative.models import (
    COPY_PROVIDERS, COPY_DEFAULT_ID,
    IMAGE_MODELS, IMAGE_DEFAULT_ID,
    VIDEO_MODELS, VIDEO_DEFAULT_ID,
)

log = logging.getLogger(__name__)

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


