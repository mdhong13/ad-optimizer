"""
Veo 영상 씬 이어붙이기 + 플랫폼별 포맷 출력

입력: 16:9 1920x1080 mp4 N개 (같은 fps/코덱)
출력:
  - concat_16x9.mp4     (원본 이어붙임, 1920x1080)
  - concat_9x16.mp4     (YouTube Shorts, 1080x1920, 블러 배경 + 센터)
  - concat_4x5.mp4      (Meta Feed, 1080x1350, 센터 크롭)

사용:
  python -m scripts.concat_ad_videos \
    assets/generated/meta/a.mp4 \
    assets/generated/meta/b.mp4 \
    --out-prefix variant_a
"""
import argparse
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUTPUT_DIR = Path("D:/0_Dotcell/ad-optimizer/assets/generated/meta")


def run(cmd):
    print(f"$ ffmpeg {' '.join(cmd[1:])[:200]}...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-2000:])
        raise SystemExit(f"ffmpeg 실패 (exit {r.returncode})")


def concat_demux(inputs, output):
    """같은 규격 mp4 무손실 이어붙임 (concat demuxer)"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for p in inputs:
            # ffmpeg concat demuxer는 '을 \' 로 이스케이프
            safe = str(Path(p).resolve()).replace("\\", "/").replace("'", r"'\''")
            f.write(f"file '{safe}'\n")
        listfile = f.name
    try:
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
             "-c", "copy", str(output)])
    finally:
        Path(listfile).unlink(missing_ok=True)


def to_shorts_9x16(src, output):
    """16:9 → 9:16 (1080x1920). 블러 배경 + 센터 포그라운드."""
    # 블러 배경: 1080x1920로 크롭·스케일 + gblur
    # 포그라운드: 1080x608 스케일 (1920x1080 비율 유지), 중앙 배치
    vf = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=30[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )
    run([FFMPEG, "-y", "-i", str(src),
         "-filter_complex", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart",
         str(output)])


def to_feed_4x5(src, output):
    """16:9 → 4:5 (1080x1350). 센터 크롭."""
    # 1920x1080 → 높이는 1080 유지, 너비 864 (1080 * 4/5) 센터 크롭 → 1080x1350 스케일
    vf = "crop=ih*4/5:ih,scale=1080:1350"
    run([FFMPEG, "-y", "-i", str(src),
         "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart",
         str(output)])


def main():
    parser = argparse.ArgumentParser(description="Veo 씬 이어붙이기 + 포맷 변환")
    parser.add_argument("inputs", nargs="+", help="입력 mp4 파일들 (순서대로)")
    parser.add_argument("--out-prefix", default="variant",
                        help="출력 파일 접두사 (기본: variant)")
    args = parser.parse_args()

    inputs = [Path(p) for p in args.inputs]
    for p in inputs:
        if not p.exists():
            raise SystemExit(f"파일 없음: {p}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    master = OUTPUT_DIR / f"{args.out_prefix}_16x9.mp4"
    shorts = OUTPUT_DIR / f"{args.out_prefix}_9x16.mp4"
    feed = OUTPUT_DIR / f"{args.out_prefix}_4x5.mp4"

    print(f"[1/3] concat → {master.name}")
    concat_demux(inputs, master)
    print(f"  OK ({master.stat().st_size // 1024} KB)")

    print(f"[2/3] 9:16 Shorts → {shorts.name}")
    to_shorts_9x16(master, shorts)
    print(f"  OK ({shorts.stat().st_size // 1024} KB)")

    print(f"[3/3] 4:5 Meta Feed → {feed.name}")
    to_feed_4x5(master, feed)
    print(f"  OK ({feed.stat().st_size // 1024} KB)")

    print(f"\n완료. 출력 폴더: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
