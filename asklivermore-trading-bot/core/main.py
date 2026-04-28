"""
core.main
=========
Production entrypoint. Runs the LangGraph pipeline on a fixed cadence during
market hours, with a heartbeat watchdog and graceful shutdown.

Usage:
  asklivermore-bot run         # default loop
  asklivermore-bot once        # single tick (useful for cron / debug)
  asklivermore-bot replay PATH # replay a CSV through the graph
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings
from core.graph import build_graph
from core.logging import get_logger
from core.state import AgentState

log = get_logger(__name__)

_shutdown = False


def _handle_signal(signum, _frame):
    global _shutdown
    log.warning("main.shutdown_signal", signum=signum)
    _shutdown = True


def _new_state() -> AgentState:
    return {
        "run_id": f"run-{int(time.time())}",
        "started_at": datetime.now(tz=timezone.utc),
        "errors": [],
    }


def run_once() -> AgentState:
    graph = build_graph()
    state = _new_state()
    log.info("main.tick.start", run_id=state["run_id"], mode=settings.execution_mode)
    try:
        result = graph.invoke(state)
    except Exception as e:
        log.exception("main.tick.failed", error=str(e))
        return state
    log.info("main.tick.done", run_id=state["run_id"])
    return result  # type: ignore[return-value]


def run_loop(tick_seconds: int = 60) -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    log.info("main.loop.start", tick_seconds=tick_seconds)
    while not _shutdown:
        start = time.time()
        try:
            state = run_once()
            if state.get("halted"):
                log.warning("main.loop.halted", reason=state.get("halt_reason"))
                break
        except Exception as e:
            log.exception("main.loop.iter_failed", error=str(e))
        elapsed = time.time() - start
        sleep_for = max(0, tick_seconds - elapsed)
        for _ in range(int(sleep_for)):
            if _shutdown:
                break
            time.sleep(1)
    log.info("main.loop.exit")


def replay(csv_path: Path) -> None:
    """Replay a CSV through the pipeline in scan-only fashion."""
    from core.csv_ingest import parse_csv

    candidates = parse_csv(csv_path)
    log.info("replay.start", file=str(csv_path), candidates=len(candidates))
    graph = build_graph()
    state = _new_state()
    state["candidates"] = candidates  # type: ignore[typeddict-item]
    # Skip scanner (we already have candidates) — but the graph's entry is scanner,
    # so we just let it run; the scanner will append to existing candidates if any.
    result = graph.invoke(state)
    log.info(
        "replay.done",
        decisions=1 if result.get("decision") else 0,
        executions=len(result.get("executions") or []),
    )


def cli() -> None:
    p = argparse.ArgumentParser(prog="asklivermore-bot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("once")
    loop_p = sub.add_parser("run")
    loop_p.add_argument("--tick-seconds", type=int, default=60)
    rp = sub.add_parser("replay")
    rp.add_argument("csv", type=Path)
    args = p.parse_args()

    if args.cmd == "once":
        run_once()
    elif args.cmd == "run":
        run_loop(tick_seconds=args.tick_seconds)
    elif args.cmd == "replay":
        replay(args.csv)


if __name__ == "__main__":
    cli()
