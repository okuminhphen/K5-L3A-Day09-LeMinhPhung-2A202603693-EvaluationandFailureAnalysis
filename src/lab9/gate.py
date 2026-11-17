"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []
    problems = []
    for section, key in (("metrics", lambda m: m["id"]), ("slices", lambda s: (s["name"], s["metric"]))):
        current = {key(entry): entry for entry in spec.get(section) or []}
        for previous in base_spec.get(section) or []:
            name = key(previous)
            entry = current.get(name)
            if entry is None:
                problems.append(f"ratchet removed {section} entry {name}")
                continue
            if previous.get("blocking") and not entry.get("blocking"):
                problems.append(f"ratchet made {name} non-blocking")
            old = previous.get("threshold", {}) if section == "metrics" else previous
            new = entry.get("threshold", {}) if section == "metrics" else entry
            for bound in ("min", "max", "max_increase"):
                if bound not in old:
                    continue
                value = new.get(bound)
                if (value is None or (value < old[bound] if bound == "min" else value > old[bound])):
                    problems.append(f"ratchet loosened {name} {bound}")
            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"ratchet removed the paired CI check for {name}")
    return problems


def _rows_by_trial(rows: list[dict]) -> dict[tuple[str, int], dict]:
    return {(row["item_id"], row["seed"]): row for row in rows
            if isinstance(row.get("item_id"), str) and type(row.get("seed")) is int}


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = _ratchet_problems(spec, base_spec) if base_spec is not None else []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    for label, report in (("PR", pr), ("baseline", base)):
        manifest, rows, metrics = report["manifest"], report["rows"], report["metrics"]
        if report.get("evaluator_failures"):
            problems.append(f"{label} has evaluator failures")
        if any(isinstance(value, (int, float)) and not isfinite(value) for value in metrics.values()):
            problems.append(f"{label} has non-finite metrics")
        indexed = _rows_by_trial(rows)
        seeds = set(manifest["seeds"])
        items = {item for item, _ in indexed}
        if (not items or not seeds or len(seeds) != len(manifest["seeds"])
                or len(items) != manifest["items"]
                or len(rows) != manifest["items"] * len(seeds)
                or len(rows) != len(indexed)
                or indexed.keys() != {(item, seed) for item in items for seed in seeds}):
            problems.append(f"{label} has missing, duplicate or unlisted trials")
        missing = [metric for metric in graded
                   if any(type(row.get(metric)) is not bool for row in rows)]
        if missing:
            problems.append(f"{label} has missing or invalid row scores for {', '.join(missing)}")
        costs_valid = all(type(row.get("cost")) in (float, int) and isfinite(row["cost"]) for row in rows)
        if not costs_valid and ("cost_per_success" in metrics or any("cost" in row for row in rows)):
            problems.append(f"{label} has missing or invalid trial costs")
        if not missing and costs_valid and len(indexed) == len(rows):
            expected = aggregate(rows, graded, k_values=spec.get("pass_k", []))
            inconsistent = [key for key in {*graded, *(expected.keys() & metrics.keys())}
                            if metrics.get(key) != expected.get(key)]
            if inconsistent:
                problems.append(f"{label} aggregates disagree with rows: {', '.join(sorted(inconsistent))}")

    current, baseline = _rows_by_trial(pr["rows"]), _rows_by_trial(base["rows"])
    if current.keys() != baseline.keys():
        problems.append("PR (item, seed) coverage differs from baseline")
    elif any(set(row.get("slices") or []) != set(baseline[key].get("slices") or [])
             for key, row in current.items()):
        problems.append("PR slice tags differ from baseline")
    return problems


def _paired_ci(a: dict[str, float], b: dict[str, float], spec: dict) -> tuple[float, float, float]:
    keys = sorted(a.keys() & b.keys())
    bs = spec.get("bootstrap", {})
    return stats.paired_bootstrap(
        [a[key] for key in keys], [b[key] for key in keys],
        n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
        confidence=bs.get("confidence", 0.95),
    )


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    for entry in spec.get("slices") or []:
        name, metric = entry["name"], entry["metric"]
        key = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        value = sum(a.values()) / len(a) if a else None
        failed = value is None or value < entry.get("min", float("-inf"))
        note = ""
        if entry.get("no_significant_drop"):
            if a and a.keys() == b.keys():
                delta, lo, hi = _paired_ci(a, b, spec)
                failed |= hi < 0
                note = f" Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            else:
                failed = True
                note = " missing paired slice scores"
        if failed and entry.get("blocking"):
            blocked.append(key)
        verdict = ("BLOCK" if entry.get("blocking") else "warn") if failed else "ok"
        lines.append(f"  {key:<36} {value!s:<8}{note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            if a and a.keys() == b.keys():
                d, lo, hi = _paired_ci(a, b, spec)
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
            else:
                verdict = "missing"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
