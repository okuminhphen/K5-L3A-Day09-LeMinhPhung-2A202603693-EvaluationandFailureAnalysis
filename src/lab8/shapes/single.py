"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.runtime import dispatch, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    memory: dict = {}  # tool outputs seen so far; run_react only passes the last one to decide

    def decide(seen: dict) -> dict:
        """Pick the next READ tool, or stop. It never names issue_refund."""
        last = seen.get("last_tool")
        if last is None:
            trace.add("react", {"tool": "get_claim_view"})
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}
        result = seen["last_result"]
        if last == "get_claim_view":
            if not result.get("found"):
                return {"final": {"decision": "unknown_claim"}}
            if not result.get("order_id"):
                return {"final": {"decision": "needs_info"}}
            memory["claim"] = result
            trace.add("react", {"tool": "lookup_order"})
            return {
                "tool": "lookup_order",
                "args": {"order_id": result["order_id"], "principal_id": result["principal_id"]},
            }
        if last == "lookup_order":
            if not result.get("visible"):
                return {"final": {"decision": "escalated"}}
            memory["order"] = result["order"]
            return {"final": {"decision": "quote"}}
        return {"final": {"decision": "unexpected_state"}}

    loop = run_react(
        conn,
        budget,
        observation={"claim": {"claim_id": claim_id}},
        decide=decide,
        max_steps=MAX_STEPS,
        worker=False,
    )
    if loop["stopped"] != "final":
        trace.add("decision", {"stopped": loop["stopped"]})
        return _done(conn, claim_id, seed, "failed", 0, budget, trace, "step_cap")

    decision = loop["final"].get("decision")
    trace.add("decision", {"decision": decision})
    if decision == "unknown_claim":
        return _done(conn, claim_id, seed, "failed", 0, budget, trace, "unknown_claim")
    if decision == "needs_info":
        return _done(conn, claim_id, seed, "needs_info", 0, budget, trace)
    if decision == "escalated":
        return _done(conn, claim_id, seed, "escalated", 0, budget, trace)
    if decision != "quote":
        return _done(conn, claim_id, seed, "failed", 0, budget, trace, "bad_decision")

    # After the loop the shape's own code prices the order. The loop never sets the amount.
    quote = dispatch(conn, budget, "compute_compensation", {"order": memory["order"]}, worker=False)
    amount = int(quote["amount_vnd"])
    trace.add("quote", {"amount_vnd": amount, "reason": quote.get("reason")})
    if amount <= 0:
        return _done(conn, claim_id, seed, "denied", 0, budget, trace)

    # Pass the FULL quote. The host subtracts earlier refunds on the same order.
    # crash_at goes straight to the host. InjectedCrash is not caught here so the crash is real.
    result = issue_refund(conn, claim_id, amount, crash_at=crash_at)
    trace.add("host", {"ok": result["ok"], "reason": result["reason"], "conflict": result["conflict"]})
    if result["ok"]:
        return _done(conn, claim_id, seed, "resolved", amount, budget, trace)
    if result["conflict"]:
        return _done(conn, claim_id, seed, "failed", amount, budget, trace, result["reason"])
    return _done(conn, claim_id, seed, "denied", amount, budget, trace, result["reason"])


def _done(
    conn,
    claim_id: str,
    seed: int,
    status: str,
    proposal_amount: int,
    budget: Budget,
    trace: Trace,
    error_reason: str | None = None,
) -> RunResult:
    return finish(
        conn,
        shape=SHAPE,
        claim_id=claim_id,
        seed=seed,
        status=status,
        proposal_amount=proposal_amount,
        budget=budget,
        trace=trace,
        error_reason=error_reason,
    )
