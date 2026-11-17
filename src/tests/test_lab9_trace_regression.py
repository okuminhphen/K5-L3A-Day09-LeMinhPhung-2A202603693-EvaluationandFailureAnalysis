"""End-to-end checks for the first failed decision and the final payout claim."""

import pytest

pytestmark = pytest.mark.student


def test_ticket_delay_cannot_override_db():
    from lab9.trace_case import investigate

    bad = investigate("seeded_regression", "C-002", 11)["trial"]
    fixed = investigate("fixed", "C-002", 11)["trial"]

    assert not bad["lab8_pass"]
    assert bad["snapshot"]["refund_vnd"] == 20_000
    assert fixed["lab8_pass"]
    assert fixed["result"]["status"] == "denied"
    assert fixed["snapshot"]["refund_count"] == 0


def test_reply_reports_capped_refund():
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import ReplyMatchesLedger
    from lab9.trace_case import investigate

    def grade(shape):
        case = investigate(shape, "C-008", 11)
        assert case["trial"]["snapshot"]["refund_vnd"] == 20_000
        assert case["trial"]["lab8_pass"]
        return ReplyMatchesLedger().evaluate(EvaluatorContext(
            name="C-008@11", inputs={}, metadata=None, expected_output=case["label"],
            output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={},
        )).value

    assert grade("seeded_regression") is False
    assert grade("fixed") is True
