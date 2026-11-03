"""Command line for the Campus Customs agent team (run from the Homework 5 folder).

    python -m backend.run --reset                 # copy the original DB over the working copy
    python -m backend.run --ticket 101            # Boss works one ticket
    python -m backend.run --board                 # reset, then work every open ticket
    python -m backend.run --board --no-reset      # continue the board after approvals
    python -m backend.run --pending               # list requests waiting on a human
    python -m backend.run --approve 1 --approver "Ken Rice"
    python -m backend.run --reject 2 --approver "Ken Rice" --note "Too expensive"

Requires ANTHROPIC_API_KEY for --ticket and --board. Traces are saved in output/runs/.
"""

import argparse
import asyncio
import json

from backend.models import ApprovalDecision


def _print(obj) -> None:
    print(obj.model_dump_json(indent=2) if hasattr(obj, "model_dump_json") else json.dumps(obj, indent=2, default=str))


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--reset", action="store_true")
    g.add_argument("--ticket", type=int)
    g.add_argument("--board", action="store_true")
    g.add_argument("--pending", action="store_true")
    g.add_argument("--approve", type=int, metavar="REQUEST_ID")
    g.add_argument("--reject", type=int, metavar="REQUEST_ID")
    p.add_argument("--no-reset", action="store_true", help="with --board: don't reset first")
    p.add_argument("--approver", help="your name, required for --approve/--reject")
    p.add_argument("--note", default="")
    a = p.parse_args()

    from backend import approvals, team
    from backend.mcp_tools import call_tool

    if a.reset:
        _print(await team.reset_database())
    elif a.ticket is not None:
        _print(await team.run_ticket(a.ticket))
    elif a.board:
        _print(await team.run_board(reset=not a.no_reset))
    elif a.pending:
        _print(await call_tool("list_approval_requests", {"status": "pending"}))
    else:
        if not a.approver:
            p.error("--approver is required")
        _print(await approvals.decide(ApprovalDecision(
            request_id=a.approve if a.approve is not None else a.reject,
            approve=a.approve is not None, approver=a.approver, note=a.note)))


if __name__ == "__main__":
    asyncio.run(main())
