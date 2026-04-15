"""
OneMessage Ad Optimizer CLI
rich 기반 터미널 인터페이스
"""
import argparse
import sys
import json
import logging

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()


def cmd_init(args):
    """DB 초기화"""
    from storage.db import init_db
    init_db()
    console.print("[green]✓[/] DB initialized successfully.")


def cmd_collect(args):
    """성과 데이터 수집"""
    from scheduler.tasks import collect_performance
    with console.status("[cyan]Collecting performance data..."):
        collect_performance()
    console.print("[green]✓[/] Performance data collected.")


def cmd_market(args):
    """크립토 시장 체크"""
    from intelligence.crypto_monitor import run_check, get_market_context

    with console.status("[cyan]Checking crypto market..."):
        ctx = get_market_context()
        events, trigger = run_check()

    panel = Panel(
        f"BTC: [bold yellow]${ctx.get('btc_price_usd', 0):,.0f}[/] "
        f"([{'green' if ctx.get('btc_change_24h', 0) >= 0 else 'red'}]{ctx.get('btc_change_24h', 0):+.2f}%[/])\n"
        f"ETH: [bold yellow]${ctx.get('eth_price_usd', 0):,.0f}[/] "
        f"([{'green' if ctx.get('eth_change_24h', 0) >= 0 else 'red'}]{ctx.get('eth_change_24h', 0):+.2f}%[/])",
        title="[bold]Crypto Market[/]",
    )
    console.print(panel)

    if trigger:
        console.print(f"[bold red]⚡ Market event detected — agent would be triggered![/]")
    else:
        console.print("[dim]No significant market events.[/]")


def cmd_optimize(args):
    """에이전트 최적화 실행"""
    from scheduler.tasks import run_agent_optimization
    console.print(f"[cyan]Running agent optimization... (dry_run={not args.execute})[/]")
    run_agent_optimization()
    console.print("[green]✓[/] Optimization complete. Check /decisions in the web dashboard.")


def cmd_decisions(args):
    """대기 중인 결정 목록"""
    from storage.db import get_pending_decisions
    decisions = get_pending_decisions()

    if not decisions:
        console.print("[dim]No pending decisions.[/]")
        return

    table = Table(title=f"Pending Decisions ({len(decisions)})")
    table.add_column("ID", style="dim")
    table.add_column("Platform")
    table.add_column("Action", style="yellow")
    table.add_column("Change")
    table.add_column("Reason")

    for d in decisions:
        table.add_row(
            str(d["id"]),
            d["platform"],
            d["action"],
            f"{d['current_value']} → {d['new_value']} ({d['change_pct']:+.1f}%)",
            d["reason"][:60] + ("..." if len(d["reason"]) > 60 else ""),
        )
    console.print(table)


def cmd_execute(args):
    """결정 실행 (승인)"""
    from storage.db import get_pending_decisions
    from optimizer.executor import execute_all_pending

    pending = get_pending_decisions()
    if not pending:
        console.print("[dim]No pending decisions to execute.[/]")
        return

    console.print(f"[yellow]Executing {len(pending)} decisions...[/]")
    result = execute_all_pending(pending)
    console.print(f"[green]✓[/] Executed: {result['executed']}, Failed: {result['failed']}")


def cmd_report(args):
    """일간 리포트 생성"""
    from scheduler.tasks import generate_report
    with console.status("[cyan]Generating report..."):
        generate_report()
    console.print("[green]✓[/] Report generated. Check /decisions or daily_reports in DB.")


def cmd_serve(args):
    """웹 대시보드 실행"""
    import uvicorn
    console.print("[cyan]Starting web dashboard at http://localhost:8000[/]")
    uvicorn.run("web.main:app", host="0.0.0.0", port=args.port, reload=args.reload)


def cmd_content(args):
    """바이럴 콘텐츠 생성"""
    from viral.content_generator import (
        generate_blog_post, generate_twitter_thread,
        generate_ad_creative, list_topics,
    )
    if args.list_topics:
        topics = list_topics()
        table = Table(title="사용 가능한 주제")
        table.add_column("Key", style="cyan")
        table.add_column("Description")
        for k, v in topics.items():
            table.add_row(k, v)
        console.print(table)
        return

    if args.type == "blog":
        with console.status(f"[cyan]Generating {args.platform} post ({args.topic})..."):
            result = generate_blog_post(topic=args.topic, platform=args.platform)
    elif args.type == "thread":
        with console.status(f"[cyan]Generating Twitter thread ({args.topic})..."):
            result = generate_twitter_thread(topic=args.topic)
    elif args.type == "creative":
        with console.status(f"[cyan]Generating {args.platform} ad creative ({args.creative_type})..."):
            result = generate_ad_creative(platform=args.platform, creative_type=args.creative_type)
    else:
        console.print("[red]Unknown type. Use: blog, thread, creative[/]")
        return

    console.print(Panel(json.dumps(result, indent=2, ensure_ascii=False), title="Generated Content"))
    console.print("[green]✓[/] Content saved to viral/output/")


def cmd_scan(args):
    """Reddit 커뮤니티 스캔"""
    from viral.community_monitor import run_community_scan, get_opportunities

    with console.status("[cyan]Scanning Reddit communities..."):
        result = run_community_scan(generate_replies=args.replies)

    console.print(f"[green]✓[/] Found {result['total_posts']} posts, saved {result['saved']}")

    opportunities = get_opportunities(limit=10)
    if opportunities:
        table = Table(title="Top Opportunities")
        table.add_column("Subreddit", style="blue")
        table.add_column("Title")
        table.add_column("Score")
        table.add_column("Relevance")
        for o in opportunities:
            table.add_row(
                f"r/{o['subreddit']}",
                o["title"][:50] + ("..." if len(o["title"]) > 50 else ""),
                str(o["score"]),
                f"{o['relevance']:.1f}",
            )
        console.print(table)


def main():
    parser = argparse.ArgumentParser(
        prog="ad-optimizer",
        description="OneMessage Ad Optimizer CLI",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="DB 초기화")
    sub.add_parser("collect", help="성과 데이터 수집")
    sub.add_parser("market", help="크립토 시장 체크")

    opt_p = sub.add_parser("optimize", help="에이전트 최적화 실행")
    opt_p.add_argument("--execute", action="store_true", help="실제 API 실행 (기본: dry-run)")

    sub.add_parser("decisions", help="대기 중인 결정 목록")
    sub.add_parser("execute", help="대기 중인 결정 실행")
    sub.add_parser("report", help="일간 리포트 생성")

    serve_p = sub.add_parser("serve", help="웹 대시보드 실행")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--reload", action="store_true")

    content_p = sub.add_parser("content", help="바이럴 콘텐츠 생성")
    content_p.add_argument("--type", choices=["blog", "thread", "creative"], default="blog")
    content_p.add_argument("--topic", default="foda_sudden_death")
    content_p.add_argument("--platform", default="blog", help="blog, reddit, twitter, meta, google")
    content_p.add_argument("--creative-type", default="foda", help="foda, education, solution, event_response")
    content_p.add_argument("--list-topics", action="store_true", help="사용 가능한 주제 목록")

    scan_p = sub.add_parser("scan", help="Reddit 커뮤니티 스캔")
    scan_p.add_argument("--replies", action="store_true", help="답변 초안도 생성")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    cmd_map = {
        "init": cmd_init,
        "collect": cmd_collect,
        "market": cmd_market,
        "optimize": cmd_optimize,
        "decisions": cmd_decisions,
        "execute": cmd_execute,
        "report": cmd_report,
        "serve": cmd_serve,
        "content": cmd_content,
        "scan": cmd_scan,
    }

    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
