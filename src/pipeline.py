"""End-to-end pipeline:

    text -> input guardrails -> parse -> validate -> retrieve -> rank -> explain
         -> output guardrail (every song must come from the catalog)

recommend() never raises for bad user input; it returns a PipelineResult whose
`status` says what happened:

    ok                  recommendations produced from a clear request
    low_confidence      recommendations produced, but the request was weak or
                        conflicting; `messages` explain the best-guess
    needs_clarification nothing usable was understood; no recommendations
    blocked             input guardrail refused the text; no recommendations
    no_results          the catalog produced nothing (empty catalog, k <= 0)

All stages are deterministic for a given input, catalog and parser result.
"""
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from src.explain import Explanation, explain
from src.logging_utils import log_event, query_fingerprint, redact
from src.guardrails import (check_input, filter_to_catalog, needs_clarification,
                            validate_preferences)
from src.parser import parse_preferences
from src.preferences import Preferences, to_prefs
from src.ranker import rank
from src.recommender import load_songs
from src.retriever import retrieve

logger = logging.getLogger("musicmind")

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "songs.csv"
MAX_K = 10
ENHANCED_DIVERSITY = 0.5   # artist-repeat penalty used by the optional enhanced mode


@dataclass
class Recommendation:
    rank: int
    song: Dict
    score: float            # final score (baseline + adjustments)
    baseline_score: float   # exactly score_song()
    fit_percent: float
    explanation: Explanation


@dataclass
class PipelineResult:
    status: str
    query: str
    recommendations: List[Recommendation] = field(default_factory=list)
    preferences: Optional[Preferences] = None
    user_prefs: Optional[Dict] = None        # the score_song-style dict that was ranked
    messages: List[str] = field(default_factory=list)
    guardrail_codes: List[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return self.preferences.confidence if self.preferences else 0.0

    @property
    def parser_source(self) -> str:
        return self.preferences.source if self.preferences else "none"


@lru_cache(maxsize=4)
def _cached_catalog(path: str) -> tuple:
    return tuple(tuple(sorted(s.items())) for s in load_songs(path))


def load_catalog(path=None) -> List[Dict]:
    """Load songs.csv (cached) as a fresh list of dicts."""
    return [dict(items) for items in _cached_catalog(str(path or DEFAULT_CATALOG_PATH))]


def _run_pipeline(text, k, catalog, use_claude, client, soft_labels, diversity) -> PipelineResult:
    guard = check_input(text)
    result = PipelineResult(status="blocked", query=guard.text, guardrail_codes=guard.codes())
    if guard.blocked:
        result.messages = [i.message for i in guard.issues]
        log_event(logger, logging.WARNING, "input_blocked", "input blocked",
                  codes=guard.codes(), **query_fingerprint(text))
        return result

    prefs = parse_preferences(guard.text, use_claude=use_claude, client=client)
    prefs, vguard = validate_preferences(prefs)
    result.preferences = prefs
    result.guardrail_codes += vguard.codes()
    result.messages = list(dict.fromkeys(prefs.notes))
    log_event(logger, logging.INFO, "preferences_parsed", "preferences parsed", parser=prefs.source,
              confidence=prefs.confidence, codes=vguard.codes(), **query_fingerprint(text))

    if prefs.is_empty():
        result.status = "needs_clarification"
        return result

    if prefs.genre and not any(s["genre"] == prefs.genre for s in catalog):
        result.messages.append(f"No songs in the catalog have genre '{prefs.genre}'; "
                               "results rely on mood, energy and tempo.")

    try:
        k = max(1, min(int(k), MAX_K))
    except (TypeError, ValueError, OverflowError):
        k = 5
    user_prefs = to_prefs(prefs)
    result.user_prefs = user_prefs

    candidates = retrieve(user_prefs, catalog, pool_size=max(15, 3 * k))
    ranked = rank(user_prefs, candidates, k=k, soft_labels=soft_labels, diversity=diversity)

    kept, oguard = filter_to_catalog([r.song for r in ranked], catalog)
    result.guardrail_codes += oguard.codes()
    result.messages += [i.message for i in oguard.issues]
    keep_ids = {s["id"] for s in kept}
    ranked = [r for r in ranked if r.song["id"] in keep_ids]

    if not ranked:
        result.status = "no_results"
        result.messages.append("No songs could be recommended from the catalog.")
        return result

    for position, r in enumerate(ranked, start=1):
        exp = explain(r, user_prefs)
        result.recommendations.append(
            Recommendation(position, r.song, r.final_score, r.baseline_score, exp.fit_percent, exp))

    # A request that contradicts itself is always a best guess, even if its confidence is not low.
    if needs_clarification(prefs) or "conflict" in vguard.codes():
        result.status = "low_confidence"
        result.messages.append("This request was unclear or contradictory, so these results are a best guess.")
    else:
        result.status = "ok"
    return result


def recommend(text, k: int = 5, catalog: Optional[List[Dict]] = None,
              use_claude: Optional[bool] = None, client=None,
              soft_labels: bool = False, diversity: float = 0.0) -> PipelineResult:
    """Run the full pipeline for a natural-language request.

    The defaults (soft_labels=False, diversity=0) reproduce the original recommender's
    order exactly. Enhanced ranking is opt-in: soft_labels=True, diversity=ENHANCED_DIVERSITY.

    Every call logs a structured "pipeline_finished" event (status, parser,
    confidence, guardrail codes) or a "pipeline_failure" event if something
    unexpected is raised. The raw query text and API keys are never logged.
    """
    catalog = load_catalog() if catalog is None else catalog
    try:
        result = _run_pipeline(text, k, catalog, use_claude, client, soft_labels, diversity)
    except Exception as exc:
        log_event(logger, logging.ERROR, "pipeline_failure", "pipeline failed",
                  error_type=type(exc).__name__, error=redact(str(exc))[:200], **query_fingerprint(text))
        raise
    log_event(logger, logging.INFO if result.status in ("ok", "needs_clarification") else logging.WARNING,
              "pipeline_finished", "pipeline finished", status=result.status,
              parser=result.parser_source, confidence=result.confidence,
              n_recommendations=len(result.recommendations), codes=result.guardrail_codes,
              mode="enhanced" if (soft_labels or diversity) else "baseline", **query_fingerprint(text))
    return result
