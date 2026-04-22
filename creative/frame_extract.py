"""
영상 마지막 프레임 추출 — 3샷 체이닝(Layer 3)용.

생성된 mp4 의 마지막 프레임을 JPG 로 저장해, 다음 샷의 Veo `image.bytesBase64Encoded`
입력으로 넘긴다. 같은 인물/배경으로 이어질 확률을 크게 높임.

로컬 ffmpeg 의존.
"""
from __future__ import annotations
import asyncio
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "generated" / "creative" / "frames"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg 가 PATH 에 없음. 설치 후 재시도 (winget install Gyan.FFmpeg)")


def _resolve_video_path(ref: str) -> Path:
    if not ref:
        raise ValueError("빈 경로")
    if ref.startswith("/assets/"):
        return BASE_DIR / ref.lstrip("/")
    p = Path(ref)
    if not p.is_absolute():
        p = BASE_DIR / ref
    return p


async def _run(cmd: list[str]) -> None:
    log.info("[frame_extract] ffmpeg: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"ffmpeg 실패 (code={proc.returncode}):\n{tail}")


async def extract_last_frame(video_ref: str) -> dict:
    """
    video_ref: '/assets/...' URL 또는 절대 경로.
    반환: {"path": abs, "url": '/assets/...', "mime_type": "image/jpeg"}

    기법: `-sseof -0.5` 로 파일 끝 직전 0.5s 에서 시작, `-update 1 -q:v 1` 로 단일
    JPG 쓰기. 짧은 샷에서도 안전하게 마지막 프레임을 얻는다.
    """
    _ensure_ffmpeg()
    vpath = _resolve_video_path(video_ref)
    if not vpath.exists():
        raise FileNotFoundError(f"video 없음: {vpath}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    out = OUTPUT_DIR / f"{ts}_lastframe_{uid}.jpg"

    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.5",
        "-i", str(vpath),
        "-update", "1",
        "-q:v", "1",
        "-frames:v", "1",
        str(out),
    ]
    await _run(cmd)

    if not out.exists() or out.stat().st_size == 0:
        # 아주 짧은 샷은 -sseof 가 음수 위치로 못 가는 경우 있어 fallback
        out.unlink(missing_ok=True)
        cmd2 = [
            "ffmpeg", "-y",
            "-i", str(vpath),
            "-vf", "select=eq(n\\,0)+eof",  # 실용적으로는 전체를 돌려 마지막 프레임을 -update 로 덮어씀
            "-update", "1",
            "-q:v", "1",
            str(out),
        ]
        await _run(cmd2)
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("마지막 프레임 추출 실패")

    rel = f"/assets/generated/creative/frames/{out.name}"
    return {"path": str(out), "url": rel, "mime_type": "image/jpeg"}
