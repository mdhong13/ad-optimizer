"""
OpenClaw 에이전트 매니저 — 10개 동시 에이전트 관리
각 에이전트 = AI 캐릭터 (고유 페르소나)
텍스트 생성 = 로컬 LLM (비용 0)
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from agent.local_llm import LocalLLM
from viral.character import Character, get_preset_characters
from storage import db

logger = logging.getLogger(__name__)

MAX_AGENTS = 10


class OpenClawAgent:
    """단일 에이전트 — 캐릭터 기반 자율 활동"""

    def __init__(self, character: Character, llm: LocalLLM):
        self.character = character
        self.llm = llm
        self.active = True
        self.task_count = 0
        self.last_activity = None

    @property
    def name(self) -> str:
        return self.character.name

    @property
    def platform(self) -> str:
        return self.character.platform

    def execute_comment(self, context: str) -> dict:
        """댓글 생성 태스크"""
        try:
            text = self.character.generate_comment(context, self.llm)
            self.task_count += 1
            self.last_activity = datetime.now().isoformat()

            activity = {
                "character_id": self.character.name,
                "character_name": self.character.name,
                "platform": self.platform,
                "task_type": "comment",
                "context": context[:300],
                "generated_text": text[:1000],
                "status": "generated",
                "agent_session": True,
            }
            db.insert_viral_activity(activity)
            logger.debug(f"[{self.name}] Comment generated ({len(text)} chars)")
            return activity
        except Exception as e:
            logger.error(f"[{self.name}] Comment failed: {e}")
            return {"status": "error", "error": str(e)}

    def execute_post(self, topic: str) -> dict:
        """게시글 생성 태스크"""
        try:
            result = self.character.generate_post(topic, self.llm)
            self.task_count += 1
            self.last_activity = datetime.now().isoformat()

            activity = {
                "character_id": self.character.name,
                "character_name": self.character.name,
                "platform": self.platform,
                "task_type": "post",
                "topic": topic,
                "generated_title": result.get("title", ""),
                "generated_text": result.get("body", "")[:1000],
                "status": "generated",
                "agent_session": True,
            }
            db.insert_viral_activity(activity)
            logger.debug(f"[{self.name}] Post generated: {result.get('title', '')[:50]}")
            return activity
        except Exception as e:
            logger.error(f"[{self.name}] Post failed: {e}")
            return {"status": "error", "error": str(e)}

    def status(self) -> dict:
        return {
            "name": self.name,
            "platform": self.platform,
            "active": self.active,
            "task_count": self.task_count,
            "last_activity": self.last_activity,
        }


class OpenClawManager:
    """에이전트 매니저 — 최대 10개 동시 실행"""

    def __init__(self, max_agents: int = MAX_AGENTS):
        self.max_agents = max_agents
        self.llm = LocalLLM()
        self.agents = []
        self._executor = None

    def init_agents(self, characters: list = None):
        """캐릭터 기반 에이전트 초기화"""
        if characters is None:
            # DB에서 로드, 없으면 프리셋
            db_chars = db.get_active_characters()
            if db_chars:
                characters = [
                    Character(**{k: v for k, v in c.items() if k in Character.__dataclass_fields__})
                    for c in db_chars
                ]
            else:
                characters = get_preset_characters()

        self.agents = []
        for char in characters[:self.max_agents]:
            agent = OpenClawAgent(char, self.llm)
            self.agents.append(agent)

        logger.info(f"OpenClaw: {len(self.agents)} agents initialized")
        return self.agents

    def get_agents_by_platform(self, platform: str) -> list:
        return [a for a in self.agents if a.platform == platform]

    def run_parallel_tasks(self, tasks: list, max_workers: int = None) -> list:
        """
        태스크를 병렬 실행
        tasks: [{
            "agent_name": "CryptoGuardian",  (or index)
            "task_type": "comment" | "post",
            "context": "...",     (for comment)
            "topic": "...",       (for post)
        }]
        """
        if max_workers is None:
            max_workers = min(len(tasks), self.max_agents)

        agent_map = {a.name: a for a in self.agents}
        results = []

        def _execute(task):
            agent_name = task.get("agent_name", "")
            agent = agent_map.get(agent_name)
            if not agent:
                # index 기반 fallback
                idx = task.get("agent_index", 0) % len(self.agents)
                agent = self.agents[idx]

            if task.get("task_type") == "post":
                return agent.execute_post(task.get("topic", "crypto security"))
            else:
                return agent.execute_comment(task.get("context", ""))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_execute, t): t for t in tasks}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Parallel task error: {e}")
                    results.append({"status": "error", "error": str(e)})

        logger.info(f"Parallel execution: {len(results)}/{len(tasks)} completed")
        return results

    def scan_and_engage_all(self) -> dict:
        """전 플랫폼 스캔 → 기회 탐지 → 에이전트 배정 → 병렬 실행"""
        if not self.agents:
            self.init_agents()

        tasks = []
        total_opportunities = 0

        # Reddit 스캔
        reddit_agents = self.get_agents_by_platform("reddit")
        if reddit_agents:
            try:
                from viral.platforms.reddit import search_all_keywords
                posts = search_all_keywords(limit_per_kw=3)
                top_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)[:5]
                for i, post in enumerate(top_posts):
                    agent = reddit_agents[i % len(reddit_agents)]
                    context = f"r/{post.get('subreddit', '')}: {post.get('title', '')}\n{post.get('selftext', '')[:200]}"
                    tasks.append({
                        "agent_name": agent.name,
                        "task_type": "comment",
                        "context": context,
                    })
                total_opportunities += len(top_posts)
            except Exception as e:
                logger.warning(f"Reddit scan failed: {e}")

        # YouTube 스캔
        youtube_agents = self.get_agents_by_platform("youtube")
        if youtube_agents:
            try:
                from viral.platforms.youtube import scan_crypto_videos
                videos = scan_crypto_videos()
                top_videos = videos[:5]
                for i, video in enumerate(top_videos):
                    agent = youtube_agents[i % len(youtube_agents)]
                    context = f"[{video.get('channel', '')}] {video.get('title', '')}\n{video.get('description', '')[:200]}"
                    tasks.append({
                        "agent_name": agent.name,
                        "task_type": "comment",
                        "context": context,
                    })
                total_opportunities += len(top_videos)
            except Exception as e:
                logger.warning(f"YouTube scan failed: {e}")

        # 병렬 실행
        results = []
        if tasks:
            results = self.run_parallel_tasks(tasks)

        return {
            "agents_active": len(self.agents),
            "opportunities_found": total_opportunities,
            "tasks_executed": len(results),
            "tasks_success": len([r for r in results if r.get("status") != "error"]),
            "timestamp": datetime.now().isoformat(),
        }

    def status(self) -> dict:
        """전체 에이전트 상태"""
        return {
            "total_agents": len(self.agents),
            "max_agents": self.max_agents,
            "agents": [a.status() for a in self.agents],
            "llm_available": self.llm.is_available(),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mgr = OpenClawManager()
    mgr.init_agents()

    print(f"Agents: {len(mgr.agents)}")
    for a in mgr.agents:
        print(f"  [{a.platform}] {a.name}")

    print(f"\nLLM available: {mgr.llm.is_available()}")
