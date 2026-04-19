"""
OneMessage Facebook Page — 영문 일일 스토리텔링 포스트

흐름:
  1. FB Page에서 최근 14개 포스트 긁어와 topic_tag 추출 (중복 회피)
  2. Claude 로 스토리 생성 (headline, body, image_prompt, topic_tag)
  3. Imagen 4.0 으로 히어로 이미지 생성 (1:1, 1080x1080)
  4. FB Page 에 photo + caption 으로 게시
  5. 결과 로그 (성공 시 post_id, 실패 시 예외)

수동 실행:
  python -m publisher.story_publisher
  python -m publisher.story_publisher --dry-run        # 생성만, 게시 X
  python -m publisher.story_publisher --draft          # 비공개(published=false) 로 업로드 — 페이지 피드 관리자만 볼 수 있음
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.claude import ClaudeAgent
from config.settings import settings
from publisher.platforms.facebook import FacebookPage

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "generated" / "fb_en"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOPIC_TAG_RE = re.compile(r"topic:\s*([a-z0-9\-]+)", re.IGNORECASE)


def extract_recent_topic_tags(posts: list[dict]) -> list[str]:
    """포스트 message 하단에 'topic: xxx-yyy' 숨김 태그 심어 두기 — 회수는 여기서."""
    tags: list[str] = []
    for p in posts:
        m = TOPIC_TAG_RE.search(p.get("message", "") or "")
        if m:
            tags.append(m.group(1).lower())
    return tags


def generate_story(recent_tags: list[str]) -> dict:
    """Claude 호출 → {topic_tag, headline, body, image_prompt, link_url}"""
    agent = ClaudeAgent()
    system = agent._load_prompt("fb_story_en")
    if not system:
        # agent/prompts/ 에만 둔 상태. Publisher 쪽에 같은 이름 복사본 없어도 fallback.
        from pathlib import Path as _P
        alt = _P(__file__).resolve().parent.parent / "agent" / "prompts" / "fb_story_en.md"
        system = alt.read_text(encoding="utf-8")

    user_msg = json.dumps({
        "recent_topic_tags_last_14_posts": recent_tags,
        "instruction": "Pick a topic_tag NOT in the list above. Return the JSON spec.",
    }, indent=2)

    story = agent.ask_json(system, user_msg, max_tokens=2000)
    required = {"topic_tag", "headline", "body", "image_prompt", "link_url"}
    missing = required - set(story.keys())
    if missing:
        raise ValueError(f"Claude response missing fields: {missing}")
    return story


def generate_image(prompt: str, out_path: Path, aspect_ratio: str = "1:1") -> Path:
    """Imagen 4.0 호출 → 파일 저장"""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"imagen-4.0-generate-001:predict?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": aspect_ratio},
    }
    r = httpx.post(url, json=payload, timeout=180)
    r.raise_for_status()
    preds = r.json().get("predictions") or r.json().get("generatedImages", [])
    if not preds:
        raise RuntimeError(f"Imagen no predictions: {str(r.json())[:200]}")
    img_b64 = preds[0].get("bytesBase64Encoded") or preds[0].get("image", {}).get("bytesBase64Encoded")
    if not img_b64:
        raise RuntimeError("Imagen response missing image bytes")
    out_path.write_bytes(base64.b64decode(img_b64))
    return out_path


def build_post_body(story: dict) -> str:
    """Body + hidden topic tag (향후 중복 회피용) + link."""
    tag = story["topic_tag"]
    body = story["body"].strip()
    link = story.get("link_url") or "https://onemsg.net"
    # topic 태그는 맨 아래 작게 — FB 에서 시각적으로 튀지 않게
    return f"{body}\n\n—\nLearn more: {link}\ntopic: {tag}"


def run(dry_run: bool = False, draft: bool = False) -> dict:
    """
    일일 포스트 1건 생성 + 게시.
    반환: {topic_tag, post_id, image_path, status}
    """
    page = FacebookPage()
    if not page.is_configured():
        raise RuntimeError("Facebook Page 미구성 (META_ACCESS_TOKEN/META_PAGE_ID)")
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 미설정")

    # 1. 최근 포스트에서 주제 태그 수집
    try:
        recent = page.recent_posts(limit=14)
        recent_tags = extract_recent_topic_tags(recent)
        logger.info(f"Recent topic tags (14 posts): {recent_tags}")
    except Exception as e:
        logger.warning(f"recent_posts 실패 — 빈 리스트로 진행: {e}")
        recent_tags = []

    # 2. 스토리 생성
    story = generate_story(recent_tags)
    logger.info(f"Generated story: tag={story['topic_tag']} headline={story['headline']}")

    # 3. 이미지 생성
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_tag = re.sub(r"[^a-z0-9\-]", "-", story["topic_tag"].lower())
    img_path = OUTPUT_DIR / f"{ts}_{safe_tag}.png"
    generate_image(story["image_prompt"], img_path, aspect_ratio="1:1")
    logger.info(f"Image saved: {img_path.name}")

    # 4. 게시
    message = build_post_body(story)
    if dry_run:
        print("=" * 70)
        print(f"[DRY RUN] topic: {story['topic_tag']}")
        print(f"headline: {story['headline']}")
        print(f"image: {img_path}")
        print("-" * 70)
        print(message)
        print("=" * 70)
        return {"topic_tag": story["topic_tag"], "post_id": None,
                "image_path": str(img_path), "status": "dry_run"}

    post_id = page.post_photo(
        image_path=str(img_path),
        message=message,
        published=not draft,
    )
    return {
        "topic_tag": story["topic_tag"],
        "post_id": post_id,
        "image_path": str(img_path),
        "status": "draft" if draft else "published",
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser(description="OneMessage FB EN 일일 스토리 포스트")
    ap.add_argument("--dry-run", action="store_true", help="생성만, 게시 안 함")
    ap.add_argument("--draft", action="store_true",
                    help="비공개(published=false) 업로드 — 관리자만 볼 수 있음")
    args = ap.parse_args()

    result = run(dry_run=args.dry_run, draft=args.draft)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
