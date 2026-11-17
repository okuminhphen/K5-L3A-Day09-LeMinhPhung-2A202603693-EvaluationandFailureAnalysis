"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.handoff import make_handoff
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    shape = "orchestrator"
    budget = Budget()
    trace = Trace(make_run_id(shape, claim_id, seed))
    conn = connect(store_path)

    def result(
        status: str, proposal: int = 0, reason: str | None = None
    ) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal})
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    try:
        budget.add_tool(tool_cost())
        claim = get_claim_view(conn, claim_id)
        if not claim["found"]:
            return result("failed", reason="unknown_claim")
        if not claim["order_id"]:
            return result("needs_info", reason="missing_order_id")

        handoff = make_handoff(
            request_id=f"REQ-{claim_id}",
            claim_id=claim_id,
            task="check_applicable_policy",
            facts={},
            # The quote tool needs the order returned by lookup_order.
            allowed_tools=["lookup_order", "compute_compensation"],
        )
        trace.add("handoff", handoff)
        investigation = run_readonly_investigators(
            conn, budget, handoff, principal_id=claim["principal_id"]
        )
        tools = investigation["tools"]
        order_view = tools["lookup_order"]
        trace.add("order_lookup", {"visible": order_view["visible"]})
        if not order_view["visible"]:
            return result("escalated", reason=order_view["reason"])

        quote = tools["compute_compensation"]
        proposal = int(quote["amount_vnd"])
        trace.add("quote", {"amount_vnd": proposal})
        if proposal <= 0:
            return result("denied", reason=quote["reason"])

        # The host applies approval and prior refunds to the full quote.
        budget.add_tool(tool_cost())
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        if outcome["ok"]:
            return result("resolved", proposal)
        status = "failed" if outcome["conflict"] else "denied"
        return result(status, proposal, outcome["reason"])
    finally:
        conn.close()
