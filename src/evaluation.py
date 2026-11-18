"""Reliability and evaluation harness (deterministic, offline).

What is MEASURED here (automatic, reproducible):
  * whether each hand-written case meets its stated expectation
  * recommendation success, guardrail catch rate and false-block rate
  * parser confidence per request category
  * catalog validity of every recommended song
  * baseline ranking consistency (pipeline == original recommend_songs) and
    run-to-run determinism
  * parser-fallback behaviour with scripted (fake) Claude failures
  * genre/mood coverage probes and catalog balance

What is NOT measured (needs human judgment) is listed in NOT_MEASURED and in
the generated report. The expectations in data/eval_cases.json are the
developer's opinions, so "passed" means "met those expectations", not "is good".
No network is used: Claude is only ever a scripted fake.
"""
import csv
import json
import logging
import math
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional

from src.logging_utils import LOGGER_NAME
from src.pipeline import ENHANCED_DIVERSITY, MAX_K, PipelineResult, load_catalog, recommend
from src.preferences import GENRES, MOODS
from src.recommender import recommend_songs, score_song

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "data" / "eval_cases.json"
RESULTS_DIR = ROOT / "results"
SCHEMA_VERSION = 1
CATEGORIES = ["normal", "vague", "conflicting", "blocked", "edge", "fallback"]

NOT_MEASURED = [
    "Whether the recommended songs actually sound right to a real listener (relevance, taste, surprise).",
    "Fairness across genres or listeners: the catalog is small, hand-made and partly synthetic, and "
    "the genre probe below only shows coverage, not fairness.",
    "How well the rule-based parser handles real users' phrasing beyond these hand-written cases.",
    "Behaviour of the real Claude API (only scripted fakes were used; no network calls are made).",
    "Resistance to prompt injection or misuse beyond the listed patterns. Passing these tests does not "
    "show the system is safe.",
    "Usability and clarity of the Streamlit interface and of the explanations for real people.",
]


# --------------------------------------------------------------------------- #
# Scripted fake Claude client (never touches the network)
# --------------------------------------------------------------------------- #
class ScriptedClient:
    """Mimics anthropic.Anthropic().messages.create for a named failure mode."""

    def __init__(self, mode: str):
        self.mode, self.calls = mode, 0
        self.messages = SimpleNamespace(create=self._create)

    def _tool(self, payload):
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name="set_preferences", input=payload)])

    def _create(self, **kwargs):
        self.calls += 1
        if self.mode == "timeout":
            raise TimeoutError("request timed out")
        if self.mode == "leaky_error":
            raise RuntimeError("401 invalid x-api-key: sk-ant-api03-FAKEKEY1234567890abcdef")
        if self.mode == "malformed":
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="sorry")])
        if self.mode == "hallucinated":
            return self._tool({"genre": "vaporwave-polka", "mood": "zesty", "energy": 7, "tempo_bpm": -5})
        if self.mode == "garbage_types":
            return self._tool({"genre": 5, "energy": "high", "mood": None})
        if self.mode == "valid":
            return self._tool({"genre": "jazz", "mood": "relaxed", "energy": 0.3, "confidence": 0.9})
        raise ValueError(f"unknown scripted mode {self.mode!r}")


class EventCounter(logging.Handler):
    """Counts structured log events by name (used to prove logging is wired in)."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.counts: Counter = Counter()

    def emit(self, record):
        self.counts[getattr(record, "event", "log")] += 1


# --------------------------------------------------------------------------- #
# Running cases
# --------------------------------------------------------------------------- #
def load_cases(path=CASES_PATH) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["cases"]


def case_text(case: Dict):
    if "text_repeat" in case:
        rep = case["text_repeat"]
        return rep["unit"] * rep["count"]
    return case.get("text")


def run_case(case: Dict, catalog: List[Dict], enhanced: bool = False):
    """Run one case through the real pipeline. Returns (result, scripted_client_or_None)."""
    client = ScriptedClient(case["claude"]["mode"]) if "claude" in case else None
    kwargs = {"k": case["k"]} if "k" in case else {}
    result = recommend(
        case_text(case), catalog=catalog,
        use_claude=True if client else False, client=client,
        soft_labels=enhanced, diversity=ENHANCED_DIVERSITY if enhanced else 0.0, **kwargs)
    return result, client


def signature(result: PipelineResult):
    return (result.status, tuple(result.guardrail_codes), result.parser_source, round(result.confidence, 6),
            tuple((r.song["id"], round(r.score, 9)) for r in result.recommendations))


def validity_problems(result: PipelineResult, catalog: List[Dict], enhanced: bool) -> List[str]:
    """Structural checks on the recommendations of one result."""
    by_id = {s["id"]: s for s in catalog}
    recs, problems = result.recommendations, []
    if len(recs) > MAX_K:
        problems.append("more than MAX_K recommendations")
    if len({r.song["id"] for r in recs}) != len(recs):
        problems.append("duplicate song in list")
    if [r.rank for r in recs] != list(range(1, len(recs) + 1)):
        problems.append("ranks are not 1..n")
    for r in recs:
        if by_id.get(r.song["id"]) != r.song:
            problems.append(f"song {r.song.get('id')} is not an unchanged catalog record")
        if not (math.isfinite(r.score) and math.isfinite(r.baseline_score)):
            problems.append("non-finite score")
        if not 0 <= r.fit_percent <= 100:
            problems.append("fit outside 0-100")
        if result.user_prefs and abs(r.baseline_score - score_song(result.user_prefs, r.song)[0]) > 1e-9:
            problems.append("baseline_score differs from score_song")
        if not enhanced and r.score != r.baseline_score:
            problems.append("baseline mode score differs from baseline_score")
    if not enhanced and [r.score for r in recs] != sorted((r.score for r in recs), reverse=True):
        problems.append("baseline scores are not sorted descending")
    return problems


def baseline_mismatch(result: PipelineResult, catalog: List[Dict]) -> bool:
    """True if baseline-mode output differs from the original recommend_songs()."""
    if not result.recommendations:
        return False
    n = len(result.recommendations)
    expected = recommend_songs(result.user_prefs, catalog, n)
    return ([r.song["id"] for r in result.recommendations] != [s["id"] for s, _, _ in expected]
            or [r.score for r in result.recommendations] != [sc for _, sc, _ in expected])


def check_expectations(case: Dict, result: PipelineResult, client: Optional[ScriptedClient]) -> List[str]:
    """Compare a result with the case's expect block; return the failed checks."""
    e, failed = case["expect"], []
    p, recs = result.preferences, result.recommendations

    def need(cond, msg):
        if not cond:
            failed.append(msg)

    if "status" in e:
        need(result.status == e["status"], f"status {result.status!r} != {e['status']!r}")
    if "parser_source" in e:
        need(result.parser_source == e["parser_source"], f"parser {result.parser_source!r} != {e['parser_source']!r}")
    for field, attr in (("genre", "genre"), ("mood", "mood"), ("tempo", "tempo_bpm")):
        if field in e:
            got = getattr(p, attr) if p else None
            need(got == e[field], f"{field} {got!r} != {e[field]!r}")
    if "n_recs" in e:
        need(len(recs) == e["n_recs"], f"n_recs {len(recs)} != {e['n_recs']}")
    if "min_recs" in e:
        need(len(recs) >= e["min_recs"], f"n_recs {len(recs)} < {e['min_recs']}")
    if "top1_in" in e:
        need(bool(recs) and recs[0].song["title"] in e["top1_in"], f"top1 {recs[0].song['title'] if recs else None!r} not in {e['top1_in']}")
    if "top_genre_in" in e:
        need(bool(recs) and recs[0].song["genre"] in e["top_genre_in"], f"top genre {recs[0].song['genre'] if recs else None!r} not in {e['top_genre_in']}")
    if "min_confidence" in e:
        need(result.confidence >= e["min_confidence"], f"confidence {result.confidence} < {e['min_confidence']}")
    if "max_confidence" in e:
        need(result.confidence <= e["max_confidence"], f"confidence {result.confidence} > {e['max_confidence']}")
    for code in e.get("codes", []):
        need(code in result.guardrail_codes, f"missing guardrail code {code!r} (got {result.guardrail_codes})")
    if "message_contains" in e:
        need(any(e["message_contains"] in m for m in result.messages), f"no message contains {e['message_contains']!r}")
    if "client_calls" in e:
        need(client is not None and client.calls == e["client_calls"], f"client calls {client.calls if client else None} != {e['client_calls']}")
    blob = json.dumps([result.messages, [r.explanation.summary for r in recs]], ensure_ascii=False)
    for bad in e.get("forbidden_text", []):
        need(bad not in blob, f"forbidden text {bad!r} appears in output")
    return failed


def rnd(x, digits=4):
    return None if x is None else round(float(x), digits)


def record_for(case, result, client, failed, problems, mismatch, deterministic) -> Dict:
    p = result.preferences
    return {
        "id": case["id"], "category": case["category"],
        "text": case_text(case) if isinstance(case_text(case), (str, type(None))) and len(str(case_text(case))) <= 120
        else f"<{len(str(case_text(case)))} characters>",
        "status": result.status, "parser_source": result.parser_source,
        "confidence": rnd(result.confidence),
        "genre": p.genre if p else None, "mood": p.mood if p else None,
        "energy": rnd(p.energy) if p else None, "valence": rnd(p.valence) if p else None,
        "tempo_bpm": rnd(p.tempo_bpm) if p else None,
        "n_recs": len(result.recommendations),
        "top_titles": [r.song["title"] for r in result.recommendations],
        "guardrail_codes": list(result.guardrail_codes),
        "expectations_met": not failed, "failed_checks": failed,
        "validity_problems": problems, "baseline_mismatch": mismatch, "deterministic": deterministic,
    }


# --------------------------------------------------------------------------- #
# Probes and aggregation
# --------------------------------------------------------------------------- #
def probe(catalog: List[Dict], labels, key: str) -> Dict:
    """Ask for each label alone ("<label> music") and see whether the catalog answers it."""
    counts = Counter(s[key] for s in catalog)
    rows = []
    for label in labels:
        res = recommend(f"{label} music", catalog=catalog, use_claude=False, k=5)
        recs = res.recommendations
        rows.append({"label": label, "songs_in_catalog": counts.get(label, 0), "status": res.status,
                     "top1": recs[0].song["title"] if recs else None,
                     "top1_matches": bool(recs) and recs[0].song[key] == label,
                     "top5_contains": any(r.song[key] == label for r in recs)})
    n = len(rows)
    return {"rows": rows,
            "top1_match_rate": rnd(sum(r["top1_matches"] for r in rows) / n),
            "top5_contains_rate": rnd(sum(r["top5_contains"] for r in rows) / n),
            "labels_with_single_song": sorted(r["label"] for r in rows if r["songs_in_catalog"] == 1),
            "labels_missed_in_top5": sorted(r["label"] for r in rows if not r["top5_contains"])}


def catalog_stats(catalog: List[Dict]) -> Dict:
    sources = Counter()
    path = ROOT / "data" / "songs.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sources[row.get("source", "unknown")] += 1
    genres = Counter(s["genre"] for s in catalog)
    return {"songs": len(catalog), "by_source": dict(sorted(sources.items())),
            "genres": len(genres), "moods": len({s["mood"] for s in catalog}),
            "songs_per_genre": dict(sorted(genres.items())),
            "genres_with_one_song": sorted(g for g, n in genres.items() if n == 1),
            "largest_genre": max(genres.items(), key=lambda kv: (kv[1], kv[0]))}


def rate(num: int, den: int):
    return None if den == 0 else rnd(num / den)


def evaluate(catalog: Optional[List[Dict]] = None, cases: Optional[List[Dict]] = None) -> Dict:
    """Run everything and return the full results dictionary (no timestamps: deterministic)."""
    catalog = load_catalog() if catalog is None else catalog
    cases = load_cases() if cases is None else cases

    logger = logging.getLogger(LOGGER_NAME)
    counter, old_level = EventCounter(), logger.level
    logger.addHandler(counter)
    logger.setLevel(logging.INFO)
    try:
        records, enhanced_rows = [], []
        for case in cases:
            result, client = run_case(case, catalog)
            again, _ = run_case(case, catalog)
            deterministic = signature(result) == signature(again)
            failed = check_expectations(case, result, client)
            problems = validity_problems(result, catalog, enhanced=False)
            rec = record_for(case, result, client, failed, problems, baseline_mismatch(result, catalog), deterministic)
            records.append(rec)

            if result.recommendations:
                rich, _ = run_case(case, catalog, enhanced=True)
                enhanced_rows.append({
                    "id": case["id"],
                    "problems": validity_problems(rich, catalog, enhanced=True),
                    "top1_same": rich.recommendations[0].song["id"] == result.recommendations[0].song["id"],
                    "artists_base": len({r.song["artist"] for r in result.recommendations[:5]}),
                    "artists_rich": len({r.song["artist"] for r in rich.recommendations[:5]}),
                    "n": len(result.recommendations)})

        genre_probe = probe(catalog, GENRES, "genre")
        mood_probe = probe(catalog, MOODS, "mood")
        stats = catalog_stats(catalog)
        events = dict(sorted(counter.counts.items()))
    finally:
        logger.removeHandler(counter)
        logger.setLevel(old_level)

    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    categories = {}
    for cat in CATEGORIES:
        rows = by_cat.get(cat, [])
        if not rows:
            continue
        parsed = [r["confidence"] for r in rows if cat != "blocked"]
        categories[cat] = {
            "cases": len(rows), "expectations_met": sum(r["expectations_met"] for r in rows),
            "pass_rate": rate(sum(r["expectations_met"] for r in rows), len(rows)),
            "confidence_mean": rnd(sum(parsed) / len(parsed)) if parsed else None,
            "confidence_min": min(parsed) if parsed else None,
            "confidence_max": max(parsed) if parsed else None}

    expect_recs = [c for c, r in zip(cases, records) if c["expect"].get("status") in ("ok", "low_confidence")]
    expect_block = [(c, r) for c, r in zip(cases, records) if c["expect"].get("status") == "blocked"]
    with_recs = [r for r in records if r["n_recs"]]
    songs_checked = sum(r["n_recs"] for r in records)
    enh_problems = sum(len(x["problems"]) for x in enhanced_rows)
    multi = [x for x in enhanced_rows if x["n"] >= 5]
    fallback_rows = [r for r in records if r["parser_source"] == "rules-fallback"]

    measured = {
        "cases_total": len(records),
        "expectations_met": sum(r["expectations_met"] for r in records),
        "expectation_pass_rate": rate(sum(r["expectations_met"] for r in records), len(records)),
        "recommendation_success": {
            "requests_expected_to_return_songs": len(expect_recs),
            "returned_songs": sum(1 for c, r in zip(cases, records) if c in expect_recs and r["n_recs"] > 0),
            "rate": rate(sum(1 for c, r in zip(cases, records) if c in expect_recs and r["n_recs"] > 0), len(expect_recs))},
        "guardrails": {
            "inputs_expected_blocked": len(expect_block),
            "blocked_correctly": sum(1 for _, r in expect_block if r["status"] == "blocked"),
            "catch_rate": rate(sum(1 for _, r in expect_block if r["status"] == "blocked"), len(expect_block)),
            "false_blocks": sum(1 for c, r in zip(cases, records) if c["expect"].get("status") != "blocked" and r["status"] == "blocked")},
        "parser_confidence_by_category": categories,
        "catalog_validity": {
            "recommended_songs_checked": songs_checked,
            "problems_found": sum(len(r["validity_problems"]) for r in records),
            "enhanced_mode_problems_found": enh_problems,
            "valid_rate": rate(songs_checked - sum(len(r["validity_problems"]) for r in records), songs_checked)},
        "baseline_consistency": {
            "cases_with_recommendations": len(with_recs),
            "mismatches_vs_original_recommend_songs": sum(r["baseline_mismatch"] for r in records),
            "nondeterministic_cases": sum(not r["deterministic"] for r in records)},
        "parser_fallback": {
            "cases_using_fallback": len(fallback_rows),
            "fallback_cases_that_still_returned_songs": sum(1 for r in fallback_rows if r["n_recs"] > 0)},
        "enhanced_vs_baseline": {
            "cases_compared": len(enhanced_rows),
            "top1_unchanged_rate": rate(sum(x["top1_same"] for x in enhanced_rows), len(enhanced_rows)),
            "mean_distinct_artists_top5_baseline": rnd(sum(x["artists_base"] for x in multi) / len(multi)) if multi else None,
            "mean_distinct_artists_top5_enhanced": rnd(sum(x["artists_rich"] for x in multi) / len(multi)) if multi else None,
            "note": "descriptive only: says how the modes differ, not which is better"},
        "log_event_counts": events,
    }
    failures = ([f"{r['id']}: {c}" for r in records for c in r["failed_checks"]]
                + [f"{r['id']}: validity: {p}" for r in records for p in r["validity_problems"]]
                + [f"{r['id']}: baseline ranking differs from original recommender" for r in records if r["baseline_mismatch"]]
                + [f"{r['id']}: result changed between two identical runs" for r in records if not r["deterministic"]]
                + [f"{x['id']}: enhanced validity: {p}" for x in enhanced_rows for p in x["problems"]])
    measured["all_checks_passed"] = not failures

    return {"schema_version": SCHEMA_VERSION,
            "evidence_type": "automatic checks against developer-written expectations (see not_measured)",
            "config": {"catalog_songs": len(catalog), "cases": len(cases), "max_k": MAX_K,
                       "network_used": False, "claude": "scripted fake client only"},
            "measured": measured, "failures": failures, "cases": records,
            "genre_probe": genre_probe, "mood_probe": mood_probe, "catalog_stats": stats,
            "not_measured": NOT_MEASURED}


# --------------------------------------------------------------------------- #
# Output files
# --------------------------------------------------------------------------- #
def _pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def render_report(res: Dict) -> str:
    m, cs = res["measured"], res["catalog_stats"]
    lines = ["# MusicMind AI - Evaluation Report", "",
             "_Generated by `python scripts/reliability.py`. Deterministic and offline: no timestamps, no network, "
             "Claude replaced by a scripted fake._", "",
             "## 1. Measured automatically", "",
             "These numbers come from running the real pipeline on hand-written cases in `data/eval_cases.json`. "
             "\"Passed\" means *the system met the developer's expectation for that case*; the expectations are "
             "judgment calls, not ground truth.", "",
             f"- **Cases:** {m['cases_total']} | **expectations met:** {m['expectations_met']} "
             f"({_pct(m['expectation_pass_rate'])}) | **all checks passed:** {m['all_checks_passed']}",
             f"- **Recommendation success:** {m['recommendation_success']['returned_songs']}/"
             f"{m['recommendation_success']['requests_expected_to_return_songs']} requests that should return songs did",
             f"- **Guardrails:** blocked {m['guardrails']['blocked_correctly']}/{m['guardrails']['inputs_expected_blocked']} "
             f"inputs expected to be blocked; false blocks on other cases: {m['guardrails']['false_blocks']}",
             f"- **Catalog validity:** {m['catalog_validity']['recommended_songs_checked']} recommended songs checked, "
             f"{m['catalog_validity']['problems_found']} problems (enhanced mode: {m['catalog_validity']['enhanced_mode_problems_found']})",
             f"- **Baseline consistency:** {m['baseline_consistency']['mismatches_vs_original_recommend_songs']} mismatches vs the original "
             f"`recommend_songs` over {m['baseline_consistency']['cases_with_recommendations']} cases; "
             f"{m['baseline_consistency']['nondeterministic_cases']} nondeterministic cases",
             f"- **Parser fallback:** {m['parser_fallback']['cases_using_fallback']} cases fell back to rules; "
             f"{m['parser_fallback']['fallback_cases_that_still_returned_songs']} still returned songs", "",
             "### Results and parser confidence by category", "",
             "| Category | Cases | Expectations met | Mean confidence | Min | Max |", "|---|---|---|---|---|---|"]
    for cat, c in m["parser_confidence_by_category"].items():
        conf = (lambda v: "n/a (not parsed)" if v is None else f"{v:.2f}")
        lines.append(f"| {cat} | {c['cases']} | {c['expectations_met']}/{c['cases']} | {conf(c['confidence_mean'])} | "
                     f"{conf(c['confidence_min'])} | {conf(c['confidence_max'])} |")
    e = m["enhanced_vs_baseline"]
    lines += ["", "### Enhanced vs baseline ranking (descriptive)", "",
              f"Over {e['cases_compared']} cases with results: top-1 song unchanged in {_pct(e['top1_unchanged_rate'])}; "
              f"mean distinct artists in the top 5: {e['mean_distinct_artists_top5_baseline']} (baseline) vs "
              f"{e['mean_distinct_artists_top5_enhanced']} (enhanced). This shows how the modes differ, not which is better.", "",
              "### Coverage probes (one label at a time)", "",
              f"Asking for each of the {len(res['genre_probe']['rows'])} genres alone (`<genre> music`): top-1 has that genre in "
              f"{_pct(res['genre_probe']['top1_match_rate'])}, top-5 contains it in {_pct(res['genre_probe']['top5_contains_rate'])}. "
              f"Moods ({len(res['mood_probe']['rows'])}): top-1 {_pct(res['mood_probe']['top1_match_rate'])}, "
              f"top-5 {_pct(res['mood_probe']['top5_contains_rate'])}.",
              f"Genres missed in top 5: {', '.join(res['genre_probe']['labels_missed_in_top5']) or 'none'}. "
              f"Moods missed in top 5: {', '.join(res['mood_probe']['labels_missed_in_top5']) or 'none'}.", "",
              f"Catalog: {cs['songs']} songs, {cs['genres']} genres, {cs['moods']} moods; sources {cs['by_source']}. "
              f"{len(cs['genres_with_one_song'])} genres have exactly one song, so those tastes have almost nothing "
              f"to choose from. Largest genre: {cs['largest_genre'][0]} ({cs['largest_genre'][1]} songs). "
              "This is a coverage statistic, **not** a fairness measurement. The probes are also a weak test: the catalog was "
              "built to contain every genre and mood at least once, so a 100% result is expected and says little about "
              "how the system treats tastes outside the catalog.", "",
              "### Log events recorded during the run", "",
              ", ".join(f"`{k}`: {v}" for k, v in m["log_event_counts"].items()),
              "(Counts include the repeat runs used for the determinism and enhanced-mode comparisons.)", "",
              "### Failures", ""]
    lines += [f"- {f}" for f in res["failures"]] or ["None. Every automatic check passed."]
    lines += ["", "## 2. Not measured: needs human or manual evaluation", ""]
    lines += [f"- {item}" for item in res["not_measured"]]
    lines += ["", "A blank rating sheet is generated at `results/manual_review_template.csv` for a human reviewer "
                  "to score relevance and explanation clarity. Nothing in it has been filled in by the system.", "",
              "## 3. What these results do and do not show", "",
              "- They show the system behaves as specified on these cases, deterministically and offline, and that "
              "every recommendation is an unchanged catalog record.",
              "- They do **not** show the system is unbiased, fair, safe, or good at recommending music. The catalog "
              "and the expectations are small, hand-made and partly synthetic, and the injection and non-music "
              "guardrails are pattern lists that a determined user can get around.", ""]
    return "\n".join(lines)


def write_outputs(res: Dict, out_dir=RESULTS_DIR) -> Dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"json": out / "evaluation_results.json", "csv": out / "evaluation_cases.csv",
             "report": out / "evaluation_report.md", "manual": out / "manual_review_template.csv"}
    paths["json"].write_text(json.dumps(res, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    fields = ["id", "category", "text", "status", "parser_source", "confidence", "genre", "mood", "energy",
              "valence", "tempo_bpm", "n_recs", "top_titles", "guardrail_codes", "expectations_met", "failed_checks"]
    with open(paths["csv"], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in res["cases"]:
            row = {k: r[k] for k in fields}
            for k in ("top_titles", "guardrail_codes", "failed_checks"):
                row[k] = "; ".join(row[k])
            w.writerow(row)
    paths["report"].write_text(render_report(res), encoding="utf-8", newline="\n")
    with open(paths["manual"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["case_id", "request", "top_5_songs", "reviewer", "relevance_1_to_5",
                    "explanation_clear_1_to_5", "anything_inappropriate_or_wrong", "notes"])
        for r in res["cases"]:
            if r["n_recs"] >= 5 and r["category"] in ("normal", "conflicting", "edge"):
                w.writerow([r["id"], r["text"], "; ".join(r["top_titles"]), "", "", "", "", ""])
    return paths
