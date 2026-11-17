"""Shape A — deterministic workflow. Student work.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Suggested steps. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> status `needs_info`. Do not write the ledger.
3. `lookup_order`. If not visible -> `escalated`. Do not copy phone, address, item, internal note.
4. Quote from the order row. Ignore delay numbers written in the ticket.
5. Quote amount 0 -> `denied`. Do not call issue_refund.
6. Quote amount > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`.
   Pass the FULL quote. The host checks the claim's own approval and subtracts
   what earlier claims already got for the same order (T13, T14). Do not
   subtract it yourself or the host subtracts twice.
   Auth failure or order already refunded -> `denied` (the host writes `policy_denied`).
   `proposal_amount` stays the full quote. Amount conflict -> `failed`.
7. Success -> `resolved`. One ledger row, one `refund_committed` audit.
8. Use MockLLM only to draft the reply text, if you want a model call at all.

The model must not choose the refund amount and must not commit the refund.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.runtime import dispatch
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace

SHAPE = "workflow"


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

    claim = dispatch(conn, budget, "get_claim_view", {"claim_id": claim_id}, worker=False)
    trace.add("claim", {"found": claim.get("found", False)})
    if not claim.get("found"):
        return _done(conn, claim_id, seed, "failed", 0, budget, trace, "unknown_claim")

    principal_id = claim["principal_id"]
    order_id = claim.get("order_id")

    if not order_id:
        trace.add("decision", {"status": "needs_info"})
        return _done(conn, claim_id, seed, "needs_info", 0, budget, trace)

    scope = dispatch(
        conn,
        budget,
        "lookup_order",
        {"order_id": order_id, "principal_id": principal_id},
        worker=False,
    )
    trace.add("order", {"visible": scope.get("visible", False), "reason": scope.get("reason")})
    if not scope.get("visible"):
        return _done(conn, claim_id, seed, "escalated", 0, budget, trace)

    quote = dispatch(
        conn,
        budget,
        "compute_compensation",
        {"order": scope["order"]},
        worker=False,
    )
    amount = int(quote["amount_vnd"])
    trace.add("quote", {"amount_vnd": amount, "reason": quote.get("reason")})

    if amount <= 0:
        return _done(conn, claim_id, seed, "denied", 0, budget, trace)

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
