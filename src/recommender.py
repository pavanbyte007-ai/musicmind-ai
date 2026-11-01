import csv
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict

# Points system: a genre match is worth 2, a mood match is worth 1, and each
# numeric feature (energy, valence, tempo) is worth up to 1 based on how close
# the song is to the user's target. Maximum score is 6 (5 without a tempo target).
GENRE_POINTS = 2.0
MOOD_POINTS = 1.0

# Tempo is on a 60-172 BPM scale in the catalog, so it is divided by this range
# to make it comparable with the 0-1 features.
TEMPO_MIN_BPM = 60.0
TEMPO_MAX_BPM = 172.0

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py

    likes_acoustic is kept for compatibility but is not used in scoring.
    target_valence and target_tempo_bpm are optional; tempo is skipped if None.
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    target_valence: float = 0.5
    target_tempo_bpm: float = None

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k songs for a user, ranked by score."""
        user_prefs = _profile_to_prefs(user)
        song_dicts = [asdict(song) for song in self.songs]
        ranked = recommend_songs(user_prefs, song_dicts, k)
        by_id = {song.id: song for song in self.songs}
        return [by_id[song_dict["id"]] for song_dict, _, _ in ranked]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return the reasons a song scored the way it did, as one string."""
        _, reasons = score_song(_profile_to_prefs(user), asdict(song))
        return "; ".join(reasons)

def _profile_to_prefs(user: UserProfile) -> Dict:
    """Converts a UserProfile into the dict format used by score_song."""
    prefs = {
        "genre": user.favorite_genre,
        "mood": user.favorite_mood,
        "energy": user.target_energy,
        "valence": user.target_valence,
    }
    if user.target_tempo_bpm is not None:
        prefs["tempo_bpm"] = user.target_tempo_bpm
    return prefs

def load_songs(csv_path: str) -> List[Dict]:
    """Load songs from a CSV file as dicts with numeric fields converted."""
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            songs.append({
                "id": int(row["id"]),
                "title": row["title"],
                "artist": row["artist"],
                "genre": row["genre"],
                "mood": row["mood"],
                "energy": float(row["energy"]),
                "tempo_bpm": float(row["tempo_bpm"]),
                "valence": float(row["valence"]),
                "danceability": float(row["danceability"]),
                "acousticness": float(row["acousticness"]),
            })
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against user preferences and return (score, reasons)."""
    # user_prefs keys: genre, mood, energy, valence (optional, default 0.5),
    # tempo_bpm (optional; the tempo term is skipped if missing).
    reasons = []
    score = 0.0

    # Categorical features: all-or-nothing, worth different points.
    if song["genre"] == user_prefs["genre"]:
        score += GENRE_POINTS
        reasons.append(f"genre matches ({song['genre']}) +{GENRE_POINTS:g}")
    if song["mood"] == user_prefs["mood"]:
        score += MOOD_POINTS
        reasons.append(f"mood matches ({song['mood']}) +{MOOD_POINTS:g}")

    # Numeric features: 1 - distance, so closer to the target scores higher.
    energy_sim = 1 - abs(song["energy"] - user_prefs["energy"])
    score += energy_sim
    reasons.append(
        f"energy {song['energy']:.2f} vs target {user_prefs['energy']:.2f} +{energy_sim:.2f}"
    )

    target_valence = user_prefs.get("valence", 0.5)
    valence_sim = 1 - abs(song["valence"] - target_valence)
    score += valence_sim
    reasons.append(f"valence {song['valence']:.2f} vs target {target_valence:.2f} +{valence_sim:.2f}")

    if "tempo_bpm" in user_prefs:
        tempo_range = TEMPO_MAX_BPM - TEMPO_MIN_BPM
        tempo_sim = max(0.0, 1 - abs(song["tempo_bpm"] - user_prefs["tempo_bpm"]) / tempo_range)
        score += tempo_sim
        reasons.append(
            f"tempo {song['tempo_bpm']:.0f} vs target {user_prefs['tempo_bpm']:.0f} BPM +{tempo_sim:.2f}"
        )

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score every song, sort highest first (ties by id), and return the top k."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        scored.append((song, score, "; ".join(reasons)))
    ranked = sorted(scored, key=lambda item: (-item[1], item[0]["id"]))
    return ranked[:k]
