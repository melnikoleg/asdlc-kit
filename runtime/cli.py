"""Command-line entry point.

    # Start a pipeline (runs up to the approval gate, then pauses)
    python -m runtime.cli demo-feature "Build a TODO REST API"

    # Approve (or cancel) the paused pipeline
    python -m runtime.cli demo-feature --approve
    python -m runtime.cli demo-feature --cancel

    # Resume after a crash, continuing from the last checkpoint
    python -m runtime.cli demo-feature --resume

The thread id is the issue name, so resume/approve work across processes —
the durable checkpointer reloads exactly where the pipeline left off.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from langgraph.types import Command

from .checkpoint import open_checkpointer
from .config import load_config
from .graph import build_graph
from .state import new_state


def _print_interrupt(result: dict) -> bool:
    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if not interrupts:
        return False
    for itr in interrupts:
        payload = getattr(itr, "value", itr)
        print("\n⏸  APPROVAL REQUIRED")
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    print("\nApprove with:  python -m runtime.cli <issue> --approve")
    print("Cancel  with:  python -m runtime.cli <issue> --cancel")
    return True


def _print_final(state: dict) -> None:
    phase = state.get("phase")
    print(f"\n✅ phase={phase} iteration={state.get('iteration', 0)}")
    if state.get("failing_agents"):
        print(f"   failing: {', '.join(state['failing_agents'])}")
    for artifact in state.get("artifacts", []):
        print(f"   • {artifact}")


async def _run(args: argparse.Namespace) -> int:
    config = load_config()
    if not config.anthropic_api_key:
        print(
            "[warn] ANTHROPIC_API_KEY not set — falling back to local Claude Code "
            "credentials (subscription). Use an API key for server/automated runs.",
            file=sys.stderr,
        )

    thread = {"configurable": {"thread_id": args.issue}}
    async with open_checkpointer(config) as cp:
        graph = build_graph(config, checkpointer=cp)

        if args.approve or args.cancel:
            decision = "approve" if args.approve else "cancel"
            result = await graph.ainvoke(Command(resume=decision), thread)
        elif args.resume:
            result = await graph.ainvoke(None, thread)
        else:
            if not args.requirement:
                print("error: a requirement is required to start a pipeline", file=sys.stderr)
                return 2
            result = await graph.ainvoke(new_state(args.issue, args.requirement), thread)

        if _print_interrupt(result):
            return 0
        _print_final(result)
        return 0 if result.get("phase") == "done" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runtime.cli", description="Run the SDLC pipeline.")
    parser.add_argument("issue", help="kebab-case issue name (also the resume thread id)")
    parser.add_argument("requirement", nargs="?", help="requirement text (to start a pipeline)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--approve", action="store_true", help="approve a paused pipeline")
    group.add_argument("--cancel", action="store_true", help="cancel a paused pipeline")
    group.add_argument("--resume", action="store_true", help="resume from the last checkpoint")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
