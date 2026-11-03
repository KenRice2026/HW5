"""Append-only audit trail: output/audit_trail.json.

The file is one JSON list of AuditRecord entries. Every step of every agent's loop is
appended as it happens (the prompt it was given, each model response with its tool
calls, each batch of tool results, its final output or error), plus the run loop's
ticket updates and resets and every human approval and payment. Nothing is ever
removed: each append reads the list, adds one entry and atomically replaces the file.

If the file exists but can't be read as a list, it is left untouched and new entries go
to audit_trail.unreadable.jsonl next to it (one JSON object per line), with a warning.
Writing the audit never raises, so a locked file can't stop an agent run.

record_node() turns one PydanticAI agent-graph node into an AuditRecord.
"""

import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

from pydantic_ai import _agent_graph as graph
from pydantic_ai.messages import (
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from backend.config import AUDIT_TRAIL, PROMPTS_DIR
from backend.models import (
    AuditRecord,
    AuditToolCall,
    AuditToolResult,
    RunUsageSnapshot,
    StepType,
    StepUsage,
    TeamDeps,
)

RESULT_CHARS = 4000
TEXT_CHARS = 4000

_lock = threading.Lock()
_pending: list[dict] = []  # entries not yet written because the file was locked
REPLACE_RETRIES = 10


def now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"... [{len(text) - limit} more chars]"


def _json(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def _refused(content) -> bool:
    if isinstance(content, dict):
        return content.get("ok") is False or content.get("found") is False
    return isinstance(content, str) and content.startswith("Refused")


def prompt_version(agent: str) -> str:
    return hashlib.sha256((PROMPTS_DIR / f"{agent}.md").read_bytes()).hexdigest()[:12]


def _side_file(suffix: str, entry: dict) -> None:
    with AUDIT_TRAIL.with_suffix(suffix).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def append(record: AuditRecord) -> None:
    """Append one entry. Never raises: an audit hiccup must not kill an agent run.

    On Windows/OneDrive the file can be briefly locked (sync, antivirus), so the replace is
    retried. If it still fails, the entry is kept in memory and written with the next
    successful append, and a copy goes to audit_trail.pending.jsonl so nothing is lost.
    """
    entry = record.model_dump(mode="json")
    with _lock:
        AUDIT_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        if AUDIT_TRAIL.exists() and AUDIT_TRAIL.stat().st_size:
            try:
                entries = json.loads(AUDIT_TRAIL.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    raise ValueError("not a JSON list")
            except (ValueError, OSError) as exc:
                print(f"warning: {AUDIT_TRAIL.name} is unreadable ({exc}); left untouched, "
                      f"appending to {AUDIT_TRAIL.with_suffix('.unreadable.jsonl').name}", file=sys.stderr)
                _side_file(".unreadable.jsonl", entry)
                return
        _pending.append(entry)
        tmp = AUDIT_TRAIL.with_suffix(".json.tmp")
        for attempt in range(REPLACE_RETRIES):
            try:
                tmp.write_text(json.dumps(entries + _pending, indent=2), encoding="utf-8")
                os.replace(tmp, AUDIT_TRAIL)
                _pending.clear()
                return
            except OSError:
                time.sleep(0.05 * (attempt + 1))
        print(f"warning: {AUDIT_TRAIL.name} is locked; {len(_pending)} entr(ies) held for the next write "
              f"and copied to {AUDIT_TRAIL.with_suffix('.pending.jsonl').name}", file=sys.stderr)
        _side_file(".pending.jsonl", entry)


def _run_usage(usage) -> RunUsageSnapshot:
    return RunUsageSnapshot(requests=usage.requests, tool_calls=usage.tool_calls,
                            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)


def _base(deps: TeamDeps, step: int, step_type: StepType, **kw) -> AuditRecord:
    return AuditRecord(
        recorded_at=now(), run_id=deps.run_id, ticket_id=deps.ticket_id, actor=deps.agent.value,
        actor_type="agent", agent_run_id=deps.agent_run_id, parent_agent_run_id=deps.parent_agent_run_id,
        delegated_by=deps.chain[-1].value if deps.chain else None, depth=deps.depth, step=step,
        step_type=step_type, **kw)


def record_prompt(deps: TeamDeps, prompt: str, model: str) -> None:
    append(_base(deps, 0, StepType.PROMPT, model=model, prompt_version=prompt_version(deps.agent.value),
                 text=_clip(prompt, TEXT_CHARS)))


def record_node(node, deps: TeamDeps, step: int, usage) -> bool:
    """Audit one step of the agent loop; returns True if the node was recorded.
    UserPromptNode and End are covered by record_prompt / record_output."""
    if isinstance(node, graph.ModelRequestNode):
        results, texts = [], []
        for part in node.request.parts:
            if isinstance(part, ToolReturnPart):
                results.append(AuditToolResult(tool=part.tool_name, tool_call_id=part.tool_call_id,
                                               result=_clip(_json(part.content), RESULT_CHARS),
                                               refused=_refused(part.content)))
            elif isinstance(part, RetryPromptPart):
                results.append(AuditToolResult(tool=part.tool_name or "(output)", tool_call_id=part.tool_call_id,
                                               result=_clip(_json(part.content), RESULT_CHARS),
                                               refused=True, retry=True))
            elif isinstance(part, UserPromptPart):
                texts.append(_json(part.content))
        append(_base(deps, step, StepType.MODEL_REQUEST, tool_results=results,
                     text=_clip("\n".join(texts), TEXT_CHARS) or None, run_usage=_run_usage(usage)))
    elif isinstance(node, graph.CallToolsNode):
        resp = node.model_response
        calls = [AuditToolCall(tool=p.tool_name, tool_call_id=p.tool_call_id, args=p.args_as_dict())
                 for p in resp.parts if isinstance(p, ToolCallPart)]
        text = "\n".join(p.content for p in resp.parts if isinstance(p, TextPart))
        thinking = "\n".join(p.content for p in resp.parts if isinstance(p, ThinkingPart) and p.content)
        u = resp.usage
        append(_base(deps, step, StepType.MODEL_RESPONSE, model=resp.model_name, tool_calls=calls,
                     text=_clip(text, TEXT_CHARS) or None, thinking=_clip(thinking, TEXT_CHARS) or None,
                     usage=StepUsage(input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                                     cache_read_tokens=u.cache_read_tokens, cache_write_tokens=u.cache_write_tokens),
                     run_usage=_run_usage(usage)))
        return True
    return False


def record_output(deps: TeamDeps, step: int, output, usage) -> None:
    append(_base(deps, step, StepType.FINAL_OUTPUT, output=output.model_dump(mode="json"),
                 run_usage=_run_usage(usage)))


def record_error(deps: TeamDeps, step: int, exc: Exception, usage) -> None:
    append(_base(deps, step, StepType.ERROR, error=f"{type(exc).__name__}: {exc}",
                 run_usage=_run_usage(usage) if usage else None))


def record_action(run_id: str, actor: str, actor_type: str, step_type: StepType, *, ticket_id=None,
                  tool: str | None = None, args=None, result=None, text: str | None = None) -> None:
    """A run-loop, reset, human-decision or payment entry (not part of an agent's own loop)."""
    append(AuditRecord(
        recorded_at=now(), run_id=run_id, ticket_id=ticket_id, actor=actor, actor_type=actor_type,
        step_type=step_type, text=text,
        tool_calls=[AuditToolCall(tool=tool, args=args)] if tool else [],
        tool_results=[AuditToolResult(tool=tool, result=_clip(_json(result), RESULT_CHARS),
                                      refused=_refused(result))] if tool else []))
