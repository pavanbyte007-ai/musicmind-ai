"""Ranking on top of the original score_song().

With soft_labels=False and diversity=0 (the defaults) the order is exactly what
recommend_songs() returns: highest baseline score first, ties by lower id.

Optional adjustments, both off by default:
* soft_labels: partial credit when genre/mood is similar but not equal
  (e.g. metal for a rock fan), at SOFT_LABEL_WEIGHT of the exact-match points.
* diversity: each song by an artist already in the list loses `diversity` points.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from src.recommender import GENRE_POINTS, MOOD_POINTS, score_song
from src.retriever import Candidate, genre_similarity, mood_similarity

SOFT_LABEL_WEIGHT = 0.5


@dataclass
class RankedSong:
    song: Dict
    baseline_score: float            # exactly score_song()
    label_bonus: float = 0.0         # soft-label credit (>= 0)
    diversity_penalty: float = 0.0   # (>= 0)
    reasons: List[str] = field(default_factory=list)   # score_song reasons + adjustments

    @property
    def final_score(self) -> float:
        return self.baseline_score + self.label_bonus - self.diversity_penalty


def _soft_bonus(user_prefs: Dict, song: Dict):
    """Return (bonus, reasons) for similar-but-not-equal genre and mood."""
    bonus, reasons = 0.0, []
    g = genre_similarity(user_prefs.get("genre", ""), song["genre"])
    if 0 < g < 1:
        pts = SOFT_LABEL_WEIGHT * g * GENRE_POINTS
        bonus += pts
        reasons.append(f"similar genre ({song['genre']} ~ {user_prefs['genre']}) +{pts:.2f}")
    m = mood_similarity(user_prefs.get("mood", ""), song["mood"])
    if 0 < m < 1:
        pts = SOFT_LABEL_WEIGHT * m * MOOD_POINTS
        bonus += pts
        reasons.append(f"similar mood ({song['mood']} ~ {user_prefs['mood']}) +{pts:.2f}")
    return bonus, reasons


def rank(user_prefs: Dict, candidates: List[Candidate], k: int = 5,
         soft_labels: bool = False, diversity: float = 0.0) -> List[RankedSong]:
    """Rank candidates and return the top k as RankedSong objects."""
    if k <= 0 or not candidates:
        return []
    diversity = max(0.0, float(diversity))

    pool = []
    for cand in candidates:
        base, reasons = score_song(user_prefs, cand.song)
        bonus, extra = _soft_bonus(user_prefs, cand.song) if soft_labels else (0.0, [])
        pool.append(RankedSong(cand.song, base, bonus, 0.0, reasons + extra))

    # Greedy selection: best adjusted score first; ties by lower id (deterministic).
    chosen: List[RankedSong] = []
    artist_counts: Dict[str, int] = {}
    while pool and len(chosen) < k:
        def adjusted(r: RankedSong) -> float:
            return r.baseline_score + r.label_bonus - diversity * artist_counts.get(r.song["artist"], 0)
        best = min(pool, key=lambda r: (-adjusted(r), r.song["id"]))
        pool.remove(best)
        repeats = artist_counts.get(best.song["artist"], 0)
        if diversity and repeats:
            best.diversity_penalty = diversity * repeats
            best.reasons.append(f"repeat artist ({best.song['artist']}) -{best.diversity_penalty:.2f}")
        artist_counts[best.song["artist"]] = repeats + 1
        chosen.append(best)
    return chosen
