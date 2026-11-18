"""Candidate retrieval: shortlist songs worth ranking.

A song is a candidate when its genre or mood equals, or is similar to, what the
listener asked for. The shortlist ALWAYS also contains the top `pool_size` songs
by the original score_song() baseline, so retrieval can never hide a song the
baseline recommender would have returned. Everything is deterministic.
"""
from dataclasses import dataclass
from typing import Dict, FrozenSet, List

from src.recommender import GENRE_POINTS, MOOD_POINTS, score_song


def _pairs(table: Dict[tuple, float]) -> Dict[FrozenSet[str], float]:
    return {frozenset(pair): sim for pair, sim in table.items()}


# Hand-picked similarity (0-1) between labels that sound alike. Pairs not listed
# have similarity 0. Like the catalog, these are subjective estimates.
GENRE_SIMILARITY = _pairs({
    ("rock", "metal"): 0.6, ("rock", "punk"): 0.6, ("metal", "punk"): 0.5,
    ("pop", "indie pop"): 0.7, ("pop", "k-pop"): 0.7, ("indie pop", "k-pop"): 0.5,
    ("pop", "edm"): 0.3, ("pop", "latin"): 0.3,
    ("lofi", "ambient"): 0.5, ("lofi", "jazz"): 0.4, ("classical", "ambient"): 0.5,
    ("jazz", "blues"): 0.5, ("jazz", "soul"): 0.5, ("blues", "folk"): 0.3,
    ("soul", "r&b"): 0.7, ("funk", "soul"): 0.5, ("r&b", "funk"): 0.4,
    ("hip hop", "r&b"): 0.5, ("hip hop", "funk"): 0.3,
    ("edm", "house"): 0.7, ("edm", "synthwave"): 0.5, ("synthwave", "house"): 0.4,
    ("country", "folk"): 0.6, ("reggae", "latin"): 0.4,
})

MOOD_SIMILARITY = _pairs({
    ("chill", "relaxed"): 0.8, ("chill", "peaceful"): 0.6, ("relaxed", "peaceful"): 0.7,
    ("chill", "focused"): 0.6, ("chill", "dreamy"): 0.6, ("peaceful", "dreamy"): 0.5,
    ("intense", "angry"): 0.7, ("intense", "energetic"): 0.6, ("angry", "energetic"): 0.4,
    ("happy", "uplifting"): 0.8, ("happy", "playful"): 0.6, ("happy", "hopeful"): 0.6,
    ("uplifting", "hopeful"): 0.7, ("uplifting", "energetic"): 0.5,
    ("sad", "melancholic"): 0.8, ("melancholic", "reflective"): 0.5,
    ("moody", "melancholic"): 0.5, ("moody", "reflective"): 0.5,
    ("nostalgic", "melancholic"): 0.4, ("romantic", "dreamy"): 0.4,
    ("confident", "energetic"): 0.4,
})


def genre_similarity(a: str, b: str) -> float:
    """1.0 if equal, a table value if similar, else 0.0. An empty label never matches."""
    if not a or not b:
        return 0.0
    return 1.0 if a == b else GENRE_SIMILARITY.get(frozenset((a, b)), 0.0)


def mood_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if a == b else MOOD_SIMILARITY.get(frozenset((a, b)), 0.0)


@dataclass(frozen=True)
class Candidate:
    song: Dict
    genre_sim: float
    mood_sim: float
    relevance: float      # weighted label similarity, 0-1
    how: str              # "label" (genre/mood similar) or "baseline" (strong numeric fit)


def retrieve(user_prefs: Dict, songs: List[Dict], pool_size: int = 15) -> List[Candidate]:
    """Return the shortlist for a score_song-style preference dict."""
    if not songs:
        return []
    weight = GENRE_POINTS + MOOD_POINTS

    def make(song, how):
        g = genre_similarity(user_prefs.get("genre", ""), song["genre"])
        m = mood_similarity(user_prefs.get("mood", ""), song["mood"])
        return Candidate(song, g, m, (GENRE_POINTS * g + MOOD_POINTS * m) / weight, how)

    labeled = [c for c in (make(s, "label") for s in songs) if c.genre_sim > 0 or c.mood_sim > 0]
    labeled.sort(key=lambda c: (-c.relevance, c.song["id"]))
    chosen = {c.song["id"] for c in labeled}

    by_baseline = sorted(songs, key=lambda s: (-score_song(user_prefs, s)[0], s["id"]))
    extras = [make(s, "baseline") for s in by_baseline[:pool_size] if s["id"] not in chosen]
    return labeled + extras
