"""
바이럴 봇 매니저 — 캐릭터 관리 & 태스크 배분
OpenClaw 에이전트 10개 동시 실행 지원
"""
import logging
from datetime import datetime
from agent.local_llm import LocalLLM
from viral.character import Character, get_preset_characters
from storage import db

logger = logging.getLogger(__name__)


class ViralManager:
    def __init__(self):
        self.llm = LocalLLM()
        self.characters = []

    def load_characters(self, platform: str = None):
        """DB에서 캐릭터 로드, 없으면 프리셋 사용"""
        db_chars = db.get_active_characters(platform)
        if db_chars:
            self.characters = [
                Character(**{k: v for k, v in c.items() if k in Character.__dataclass_fields__})
                for c in db_chars
            ]
        else:
            self.characters = get_preset_characters(platform)
            for c in self.characters:
                db.upsert_character(c.to_dict())
        logger.info(f"Loaded {len(self.characters)} characters")

    def assign_tasks(self, opportunities: list) -> list:
        """
        기회 목록에 캐릭터를 매칭하여 태스크 생성
        Returns: [{character, opportunity, task_type}]
        """
        tasks = []
        char_idx = 0
        for opp in opportunities:
            platform = opp.get("platform", "reddit")
            # 해당 플랫폼 캐릭터 중 순환 배정
            platform_chars = [c for c in self.characters if c.platform == platform]
            if not platform_chars:
                platform_chars = self.characters  # fallback

            char = platform_chars[char_idx % len(platform_chars)]
            char_idx += 1

            tasks.append({
                "character": char,
                "opportunity": opp,
                "task_type": "comment" if opp.get("type") == "post" else "reply",
            })
        return tasks

    def execute_task(self, task: dict) -> dict:
        """단일 바이럴 태스크 실행 (댓글/글 생성)"""
        char = task["character"]
        opp = task["opportunity"]
        task_type = task["task_type"]

        context = f"Post: {opp.get('title', '')}\n{opp.get('body', opp.get('selftext', ''))[:300]}"

        if task_type == "comment":
            text = char.generate_comment(context, self.llm)
        else:
            result = char.generate_post(opp.get("topic", "crypto security"), self.llm)
            text = f"{result.get('title', '')}\n\n{result.get('body', '')}"

        activity = {
            "character_id": char.name,
            "character_name": char.name,
            "platform": char.platform,
            "task_type": task_type,
            "target_url": opp.get("url", ""),
            "generated_text": text[:1000],
            "status": "generated",  # generated → posted → verified
        }
        db.insert_viral_activity(activity)

        logger.info(f"[{char.name}] Generated {task_type} ({len(text)} chars)")
        return activity

    def run_batch(self, opportunities: list) -> list:
        """배치 실행 — 기회 목록 전체 처리"""
        self.load_characters()
        tasks = self.assign_tasks(opportunities)

        results = []
        for task in tasks:
            try:
                result = self.execute_task(task)
                results.append(result)
            except Exception as e:
                logger.error(f"Task failed for {task['character'].name}: {e}")

        logger.info(f"Batch complete: {len(results)}/{len(tasks)} tasks")
        return results

    def scan_and_engage(self, platform: str = "reddit") -> dict:
        """Reddit 스캔 → 기회 탐지 → 댓글 생성"""
        from viral.community_monitor import search_reddit_all_keywords

        self.load_characters(platform)
        posts = search_reddit_all_keywords(limit_per_kw=3)

        # 상위 10개만 처리
        top_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)[:10]
        opportunities = [
            {"platform": "reddit", "type": "post", **p}
            for p in top_posts
        ]

        results = []
        for opp in opportunities:
            # 관련 캐릭터 선택
            reddit_chars = [c for c in self.characters if c.platform == "reddit"]
            if not reddit_chars:
                continue

            char = reddit_chars[len(results) % len(reddit_chars)]
            try:
                text = char.generate_comment(
                    f"r/{opp.get('subreddit', '')}: {opp.get('title', '')}\n{opp.get('selftext', '')[:200]}",
                    self.llm,
                )
                activity = {
                    "character_id": char.name,
                    "platform": "reddit",
                    "task_type": "comment",
                    "target_url": opp.get("url", ""),
                    "target_title": opp.get("title", ""),
                    "generated_text": text[:1000],
                    "status": "generated",
                }
                db.insert_viral_activity(activity)
                results.append(activity)
            except Exception as e:
                logger.warning(f"Comment generation failed: {e}")

        return {
            "posts_found": len(posts),
            "comments_generated": len(results),
            "timestamp": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mgr = ViralManager()
    mgr.load_characters()
    for c in mgr.characters:
        print(f"  [{c.platform}] {c.name}: {c.persona[:50]}...")
