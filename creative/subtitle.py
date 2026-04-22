"""
자막 + 보이스오버 합성 — ffmpeg burn-in.

각 샷(영상 파일)에 대해:
  - 원본 영상 오디오 → TTS mp3 로 교체 (optional)
  - 자막 텍스트를 SRT 로 만들어 프레임에 burn-in (optional)
여러 샷이면 concat demuxer 로 이어 붙여 단일 mp4 출력.

로컬 전용 — 시스템 PATH 의 ffmpeg/ffprobe 에 의존.
"""
from __future__ import annotations
import asyncio
import logging
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "generated" / "creative" / "video"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 한글 가독성을 위한 Windows 기본 폰트. 리눅스/맥이면 사용자가 override.
DEFAULT_FONT_KR = "Malgun Gothic"
DEFAULT_FONT_EN = "Arial"


def _ensure_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg 가 PATH 에 없음. 설치 후 재시도 (winget install Gyan.FFmpeg)")
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe 가 PATH 에 없음 (ffmpeg 설치본에 포함됨)")


def _resolve_path(ref: str) -> Path:
    """`/assets/...` URL 또는 절대경로 → 실제 파일 경로."""
    if not ref:
        raise ValueError("빈 경로")
    if ref.startswith("/assets/"):
        return BASE_DIR / ref.lstrip("/")
    p = Path(ref)
    if not p.is_absolute():
        p = BASE_DIR / ref
    return p


def _probe_duration(path: Path) -> float:
    """ffprobe 로 미디어 길이(초) 추출."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out) if out else 0.0


def _seconds_to_srt_time(s: float) -> str:
    total_ms = int(round(s * 1000))
    hh = total_ms // 3_600_000
    mm = (total_ms % 3_600_000) // 60_000
    ss = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _build_srt(text: str, duration: float) -> str:
    """샷 1개짜리 SRT. 영상 전체 구간에 자막 1개 노출."""
    end = max(duration, 0.5)
    return (
        "1\n"
        f"00:00:00,000 --> {_seconds_to_srt_time(end)}\n"
        f"{text.strip()}\n"
    )


def _escape_for_subtitles_filter(p: Path) -> str:
    """ffmpeg subtitles 필터용 경로 이스케이프 (Windows 드라이브 문자 + 콜론)."""
    s = str(p).replace("\\", "/")
    # 콜론 이스케이프 (C: → C\:)
    s = s.replace(":", r"\:")
    # 작은따옴표 escape
    s = s.replace("'", r"\'")
    return s


async def _run(cmd: list[str]) -> None:
    log.info("[subtitle] ffmpeg: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode("utf-8", "replace")[-1500:]
        raise RuntimeError(f"ffmpeg 실패 (code={proc.returncode}):\n{tail}")


async def _render_shot(
    video_path: Path,
    audio_path: Optional[Path],
    subtitle_text: Optional[str],
    lang: str,
    tmp_dir: Path,
    idx: int,
) -> Path:
    """샷 1개 렌더 — 오디오 교체 + 자막 burn-in → 중간 mp4 반환."""
    out = tmp_dir / f"shot_{idx}.mp4"
    duration = _probe_duration(video_path)

    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    if audio_path is not None:
        cmd += ["-i", str(audio_path)]

    # 자막이 있으면 subtitles 필터 추가
    if subtitle_text and subtitle_text.strip():
        srt_path = tmp_dir / f"shot_{idx}.srt"
        srt_path.write_text(_build_srt(subtitle_text, duration), encoding="utf-8")
        font = DEFAULT_FONT_KR if lang == "kr" else DEFAULT_FONT_EN
        # ASS force_style: 하단 중앙, 흰색 + 검정 아웃라인
        force = (
            f"FontName={font},FontSize=18,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=2,Shadow=0,"
            "Alignment=2,MarginV=60"
        )
        vf = f"subtitles='{_escape_for_subtitles_filter(srt_path)}':force_style='{force}'"
        cmd += ["-vf", vf]

    # 오디오 매핑
    if audio_path is not None:
        # 0번 입력 비디오 + 1번 입력 오디오, 짧은 쪽에 맞춤
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    # 인코딩 설정 — concat 호환을 위해 고정
    cmd += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        str(out),
    ]
    await _run(cmd)
    return out


async def _concat_shots(shots_mp4: list[Path], output: Path) -> None:
    """concat demuxer 로 중간 mp4 여러 개를 1개로 이어붙임."""
    if len(shots_mp4) == 1:
        shutil.copy2(shots_mp4[0], output)
        return
    list_file = output.parent / f"{output.stem}_concat.txt"
    # Windows 경로도 forward slash 쓰면 안전
    lines = [f"file '{str(p).replace(chr(92), '/')}'\n" for p in shots_mp4]
    list_file.write_text("".join(lines), encoding="utf-8")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output),
    ]
    await _run(cmd)


async def render_video(
    shots: list[dict],
    lang: str = "kr",
    output_stem: Optional[str] = None,
) -> dict:
    """
    각 샷(영상 + 선택적 TTS 오디오 + 선택적 자막)을 조합해 단일 mp4 생성.

    shots: [
      {
        "video": "/assets/.../foo.mp4" | "D:/abs/path.mp4"  (필수),
        "audio": "/assets/.../voice.mp3" | None,
        "subtitle": "화면에 burn-in 될 자막" | None,
      }, ...
    ]
    lang: "kr" | "en"  — 기본 폰트 선택용

    반환: {"path": str, "url": str, "shots": int, "duration": float}
    """
    _ensure_ffmpeg()
    if not shots:
        raise ValueError("shots 비어있음")
    if lang not in ("kr", "en"):
        lang = "kr"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    stem = output_stem or f"{ts}_subtitled_{uid}"
    final_path = OUTPUT_DIR / f"{stem}.mp4"

    with tempfile.TemporaryDirectory(prefix="subtitle_") as tdir:
        tmp_dir = Path(tdir)
        intermediates: list[Path] = []
        for i, shot in enumerate(shots):
            v_ref = shot.get("video")
            if not v_ref:
                raise ValueError(f"shot {i}: video 필수")
            v_path = _resolve_path(v_ref)
            if not v_path.exists():
                raise FileNotFoundError(f"shot {i} video 없음: {v_path}")
            a_path: Optional[Path] = None
            if shot.get("audio"):
                a_path = _resolve_path(shot["audio"])
                if not a_path.exists():
                    raise FileNotFoundError(f"shot {i} audio 없음: {a_path}")
            sub = (shot.get("subtitle") or "").strip() or None
            inter = await _render_shot(v_path, a_path, sub, lang, tmp_dir, i)
            intermediates.append(inter)

        await _concat_shots(intermediates, final_path)

    total = _probe_duration(final_path)
    rel = f"/assets/generated/creative/video/{final_path.name}"
    return {
        "path": str(final_path),
        "url": rel,
        "shots": len(shots),
        "duration": round(total, 2),
    }
