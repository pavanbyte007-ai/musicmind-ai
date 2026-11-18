"""Human-readable explanations and score breakdowns.

score_song() only returns text reasons, so the numeric breakdown is recomputed
here with the same formulas and constants. tests/test_explain.py asserts the
components always add up to score_song() exactly.
"""
from dataclasses import dataclass
from typing import Dict, List

from src.ranker import RankedSong
from src.recommender import GENRE_POINTS, MOOD_POINTS, TEMPO_MAX_BPM, TEMPO_MIN_BPM


@dataclass(frozen=True)
class Component:
    name: str
    points: float
    max_points: float      # 0 when the listener did not ask for this feature
    detail: str


@dataclass
class Explanation:
    summary: str
    components: List[Component]
    baseline_score: float
    max_score: float       # best possible baseline score for this request
    fit_percent: float     # baseline_score / max_score * 100
    adjustments: List[str]  # soft-label bonus / diversity penalty lines


def score_components(user_prefs: Dict, song: Dict) -> List[Component]:
    """Per-feature points, using the same formulas as score_song()."""
    comps = []
    wanted_genre = user_prefs.get("genre", "")
    if wanted_genre:
        hit = song["genre"] == wanted_genre
        comps.append(Component("genre", GENRE_POINTS if hit else 0.0, GENRE_POINTS,
                               f"{song['genre']} vs requested {wanted_genre}"))
    else:
        comps.append(Component("genre", 0.0, 0.0, "no genre requested"))

    wanted_mood = user_prefs.get("mood", "")
    if wanted_mood:
        hit = song["mood"] == wanted_mood
        comps.append(Component("mood", MOOD_POINTS if hit else 0.0, MOOD_POINTS,
                               f"{song['mood']} vs requested {wanted_mood}"))
    else:
        comps.append(Component("mood", 0.0, 0.0, "no mood requested"))

    energy = 1 - abs(song["energy"] - user_prefs["energy"])
    comps.append(Component("energy", energy, 1.0, f"{song['energy']:.2f} vs target {user_prefs['energy']:.2f}"))

    target_valence = user_prefs.get("valence", 0.5)
    valence = 1 - abs(song["valence"] - target_valence)
    comps.append(Component("valence", valence, 1.0, f"{song['valence']:.2f} vs target {target_valence:.2f}"))

    if "tempo_bpm" in user_prefs:
        tempo = max(0.0, 1 - abs(song["tempo_bpm"] - user_prefs["tempo_bpm"]) / (TEMPO_MAX_BPM - TEMPO_MIN_BPM))
        comps.append(Component("tempo", tempo, 1.0,
                               f"{song['tempo_bpm']:.0f} vs target {user_prefs['tempo_bpm']:.0f} BPM"))
    return comps


def _sentence(components: List[Component]) -> str:
    strengths, gaps = [], []
    for c in components:
        if c.max_points == 0:
            continue
        ratio = c.points / c.max_points
        if c.name in ("genre", "mood"):
            (strengths if ratio == 1 else gaps).append(f"{c.name} ({c.detail})")
        elif ratio >= 0.9:
            strengths.append(f"{c.name} ({c.detail})")
        elif ratio <= 0.7:
            gaps.append(f"{c.name} ({c.detail})")
    parts = []
    if strengths:
        parts.append("Good match on " + ", ".join(strengths) + ".")
    if gaps:
        parts.append("Weaker on " + ", ".join(gaps) + ".")
    return " ".join(parts) or "A moderate match on all requested features."


def explain(ranked: RankedSong, user_prefs: Dict) -> Explanation:
    """Explain one ranked song: summary sentence, breakdown and adjustments."""
    song = ranked.song
    components = score_components(user_prefs, song)
    max_score = sum(c.max_points for c in components)
    fit = round(100 * ranked.baseline_score / max_score, 1) if max_score else 0.0
    adjustments = []
    if ranked.label_bonus:
        adjustments.append(f"similar genre/mood bonus +{ranked.label_bonus:.2f}")
    if ranked.diversity_penalty:
        adjustments.append(f"repeat-artist penalty -{ranked.diversity_penalty:.2f}")
    summary = f"{song['title']} by {song['artist']} - {fit:g}% fit. {_sentence(components)}"
    if adjustments:
        summary += " Adjustments: " + "; ".join(adjustments) + "."
    return Explanation(summary, components, ranked.baseline_score, max_score, fit, adjustments)
