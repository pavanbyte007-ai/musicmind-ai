"""Structured listener preferences: the output of parsing, the input of ranking.

A Preferences object holds only what the listener actually expressed (unknown
values stay None). to_prefs() converts it into the plain dict that the existing
score_song()/recommend_songs() functions already accept, filling gaps with
neutral defaults, so the recommender itself does not change.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Catalog vocabulary. tests/test_preferences.py checks that every genre and mood
# in data/songs.csv appears here, so the two cannot drift apart silently.
GENRES = (
    "pop", "indie pop", "lofi", "rock", "ambient", "jazz", "synthwave",
    "hip hop", "classical", "metal", "country", "r&b", "edm", "reggae",
    "blues", "latin", "k-pop", "folk", "punk", "funk", "soul", "house",
)

# Typical (energy, valence) of each mood. Used to fill in a missing energy or
# valence target and to detect contradictory requests. Values are rough,
# hand-picked estimates, like the catalog itself.
MOOD_PROFILE: Dict[str, tuple] = {
    "happy": (0.75, 0.85), "chill": (0.35, 0.60), "intense": (0.90, 0.40),
    "relaxed": (0.35, 0.70), "moody": (0.65, 0.40), "focused": (0.40, 0.58),
    "confident": (0.75, 0.65), "peaceful": (0.20, 0.45), "angry": (0.95, 0.30),
    "nostalgic": (0.50, 0.65), "romantic": (0.50, 0.62), "energetic": (0.90, 0.80),
    "uplifting": (0.80, 0.85), "sad": (0.30, 0.25), "melancholic": (0.50, 0.30),
    "dreamy": (0.40, 0.60), "playful": (0.80, 0.88), "reflective": (0.55, 0.40),
    "hopeful": (0.62, 0.72),
}
MOODS = tuple(MOOD_PROFILE)

NEUTRAL = 0.5


@dataclass
class Preferences:
    """What the listener asked for. None means "not specified"."""
    genre: Optional[str] = None
    mood: Optional[str] = None
    energy: Optional[float] = None        # 0-1
    valence: Optional[float] = None       # 0-1
    tempo_bpm: Optional[float] = None
    confidence: float = 0.0               # 0-1, how much of the request was understood
    source: str = "rules"                 # "rules", "claude" or "rules-fallback"
    notes: List[str] = field(default_factory=list)
    extra_genres: List[str] = field(default_factory=list)   # other genres mentioned
    extra_moods: List[str] = field(default_factory=list)    # other moods mentioned
    conflicts: List[str] = field(default_factory=list)      # contradictions found while parsing

    def is_empty(self) -> bool:
        """True when no preference at all was understood."""
        return all(v is None for v in (self.genre, self.mood, self.energy, self.valence, self.tempo_bpm))


def to_prefs(p: Preferences) -> Dict:
    """Convert Preferences into the dict format used by score_song().

    Missing energy/valence come from the mood profile, else 0.5. A missing
    genre or mood becomes "" (matches no song). Tempo is left out when unknown,
    which makes score_song skip the tempo term.
    """
    mood_energy, mood_valence = MOOD_PROFILE.get(p.mood, (NEUTRAL, NEUTRAL))
    prefs = {
        "genre": p.genre or "",
        "mood": p.mood or "",
        "energy": p.energy if p.energy is not None else mood_energy,
        "valence": p.valence if p.valence is not None else mood_valence,
    }
    if p.tempo_bpm is not None:
        prefs["tempo_bpm"] = p.tempo_bpm
    return prefs
