"""Integrity regressions with metrics that still look green."""

from copy import deepcopy

import pytest

pytestmark = pytest.mark.student


@pytest.fixture
def green():
    from lab9.eval import aggregate

    rows = [{"item_id": f"E-{item}", "seed": seed, "slices": ["money_movement"],
             "pass_rate": True, "cost": 1.0}
            for item in (1, 2) for seed in (11, 22)]
    report = {"manifest": {"items": 2, "seeds": [11, 22], "eval_set_sha": "test"},
              "rows": rows, "metrics": aggregate(rows, ["pass_rate"], k_values=[2]),
              "evaluator_failures": []}
    spec = {"eval_set_version": "v2", "pass_k": [2],
            "metrics": [{"id": "pass_rate", "blocking": True, "threshold": {"min": 0.95}}],
            "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.95,
                        "blocking": True, "no_significant_drop": True}]}
    return report, spec


@pytest.mark.parametrize("edit", ["duplicate", "relabel", "evaluator_failure", "inflated_summary"])
def test_integrity_rejects_green_report_manipulation(green, edit):
    from lab9.gate import check

    base, spec = green
    pr = deepcopy(base)
    if edit == "duplicate":
        pr["rows"][-1] = deepcopy(pr["rows"][0])
    elif edit == "relabel":
        pr["rows"][-1]["slices"] = []
    elif edit == "evaluator_failure":
        pr["evaluator_failures"] = ["E-2@22:ReplyMatchesLedger:crash"]
    else:
        pr["rows"][-1]["pass_rate"] = False

    assert check(base, base, spec)[0] == []
    assert check(pr, base, spec)[0] == ["integrity"]


def test_ratchet_keeps_slice_ci_and_blocking_status(green):
    from lab9.gate import check

    report, base_spec = green
    pr_spec = deepcopy(base_spec)
    pr_spec["slices"][0].update(blocking=False, no_significant_drop=False)
    blocked, lines = check(report, report, pr_spec, base_spec)
    assert blocked == ["integrity"]
    assert any("non-blocking" in line for line in lines)
    assert any("paired CI" in line for line in lines)
