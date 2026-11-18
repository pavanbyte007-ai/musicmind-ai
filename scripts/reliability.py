"""Reliability and evaluation harness: deterministic, offline, no API key.

Run from the project root:

    python scripts/reliability.py            # run, print summary, write results/
    python scripts/reliability.py --verify   # also re-run and confirm the files on disk reproduce exactly

Outputs (results/):
    evaluation_results.json       machine-readable metrics and per-case records
    evaluation_cases.csv          one row per case
    evaluation_report.md          human-readable report (measured vs not measured)
    manual_review_template.csv    BLANK sheet for a human reviewer

A JSON-lines run log goes to logs/reliability.jsonl (git-ignored; has timestamps).
Exit code is 1 if any automatic check fails.
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation import evaluate, render_report, write_outputs  # noqa: E402
from src.logging_utils import configure_logging  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(PROJECT_ROOT / "results"), help="results directory")
    ap.add_argument("--log", default=str(PROJECT_ROOT / "logs" / "reliability.jsonl"), help="JSON-lines log file")
    ap.add_argument("--verify", action="store_true", help="re-run and check the saved results reproduce exactly")
    args = ap.parse_args()

    handler = configure_logging(args.log, mode="w")
    try:
        results = evaluate()
    finally:
        handler.close()
    paths = write_outputs(results, args.out)

    m = results["measured"]
    print(f"Cases: {m['cases_total']}  expectations met: {m['expectations_met']} ({m['expectation_pass_rate']:.0%})")
    print(f"Recommendation success: {m['recommendation_success']['returned_songs']}/{m['recommendation_success']['requests_expected_to_return_songs']}")
    print(f"Guardrail catch rate: {m['guardrails']['blocked_correctly']}/{m['guardrails']['inputs_expected_blocked']}  false blocks: {m['guardrails']['false_blocks']}")
    print(f"Catalog problems: {m['catalog_validity']['problems_found']}  baseline mismatches: {m['baseline_consistency']['mismatches_vs_original_recommend_songs']}  nondeterministic: {m['baseline_consistency']['nondeterministic_cases']}")
    for cat, c in m["parser_confidence_by_category"].items():
        print(f"  {cat:12s} {c['expectations_met']}/{c['cases']} met, mean confidence {c['confidence_mean']}")
    print("Files:", ", ".join(str(p.relative_to(PROJECT_ROOT)) if PROJECT_ROOT in p.parents else str(p) for p in paths.values()))
    for failure in results["failures"]:
        print("FAIL:", failure)

    if args.verify:
        before = {name: p.read_bytes() for name, p in paths.items()}
        write_outputs(evaluate(), args.out)
        same = all(p.read_bytes() == before[name] for name, p in paths.items())
        print("Reproducibility check (second run vs saved files):", "IDENTICAL" if same else "DIFFERENT")
        if not same:
            return 1
    return 0 if m["all_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
