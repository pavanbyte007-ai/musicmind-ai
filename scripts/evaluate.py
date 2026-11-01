"""Evaluation script for the Music Recommender Simulation.

Runs three user profiles and three edge cases through the real recommender,
then compares two weight experiments and prints a few bias checks.

Run from anywhere with:  python scripts/evaluate.py
(or from the project root: python -m scripts.evaluate)

The recommender is deterministic (no randomness), so every run prints the
same output. The experiments use a weight-adjustable copy of the formula; the
script first asserts that the copy matches the real score_song at the normal
weights, so the experiment numbers can be trusted.
"""
import sys
from collections import Counter
from pathlib import Path
from statistics import pstdev

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.recommender import (  # noqa: E402
    load_songs, score_song, recommend_songs, TEMPO_MIN_BPM, TEMPO_MAX_BPM,
)

PROFILES = {
    "High-Energy Pop": {"genre": "pop", "mood": "happy", "energy": 0.9, "valence": 0.8, "tempo_bpm": 128},
    "Chill Lo-fi": {"genre": "lofi", "mood": "chill", "energy": 0.38, "valence": 0.58, "tempo_bpm": 76},
    "Deep Intense Rock": {"genre": "rock", "mood": "intense", "energy": 0.92, "valence": 0.35, "tempo_bpm": 150},
}

EDGE_CASES = {
    "Genre not in catalog (k-pop)": {"genre": "k-pop", "mood": "happy", "energy": 0.8, "valence": 0.8, "tempo_bpm": 120},
    "Conflicting (lofi/chill but fast, loud, happy)": {"genre": "lofi", "mood": "chill", "energy": 0.95, "valence": 0.9, "tempo_bpm": 170},
    "Tempo above catalog range (200 BPM)": {"genre": "metal", "mood": "angry", "energy": 0.97, "valence": 0.25, "tempo_bpm": 200},
}

# Points per feature: genre and mood are all-or-nothing, the rest are up to this much.
BASE = dict(genre=2, mood=1, energy=1, valence=1, tempo=1)
EXP1 = dict(genre=1, mood=1, energy=2, valence=1, tempo=1)  # energy x2, genre x0.5
EXP2 = dict(genre=2, mood=0, energy=1, valence=1, tempo=1)  # mood matching removed


def variant_score(prefs, song, w):
    """Score a song like score_song, but with adjustable per-feature weights."""
    tempo_range = TEMPO_MAX_BPM - TEMPO_MIN_BPM
    return (
        w["genre"] * (song["genre"] == prefs["genre"])
        + w["mood"] * (song["mood"] == prefs["mood"])
        + w["energy"] * (1 - abs(song["energy"] - prefs["energy"]))
        + w["valence"] * (1 - abs(song["valence"] - prefs["valence"]))
        + w["tempo"] * max(0.0, 1 - abs(song["tempo_bpm"] - prefs["tempo_bpm"]) / tempo_range)
    )


def rank(songs, prefs, w):
    """Rank all songs by variant_score, highest first (ties by id)."""
    return sorted(songs, key=lambda sg: (-variant_score(prefs, sg, w), sg["id"]))


def show_full(songs, name, prefs, k=5):
    """Print the top k results for a profile with scores and reasons."""
    print("=" * 78)
    print(f"PROFILE: {name}\n  {prefs}")
    for i, (sg, sc, why) in enumerate(recommend_songs(prefs, songs, k), 1):
        print(f"{i}. {sg['title']} by {sg['artist']} [{sg['genre']}/{sg['mood']}]  (Score: {sc:.2f})")
        for reason in why.split("; "):
            print(f"     - {reason}")


def show_compact(songs, prefs, w, k=5):
    """Return (title, score) pairs for the top k under the given weights."""
    return [(sg["title"], round(variant_score(prefs, sg, w), 2)) for sg in rank(songs, prefs, w)[:k]]


def main() -> None:
    songs = load_songs(str(PROJECT_ROOT / "data" / "songs.csv"))

    # Sanity check: the weight-adjustable copy equals the real implementation.
    for p in list(PROFILES.values()) + list(EDGE_CASES.values()):
        for sg in songs:
            assert abs(variant_score(p, sg, BASE) - score_song(p, sg)[0]) < 1e-9
    print("Sanity check passed: experiment formula == real score_song at baseline weights\n")

    print("##### PART A: THREE PROFILES (real recommend_songs, Top 5) #####")
    for name, prefs in PROFILES.items():
        show_full(songs, name, prefs)

    print("\n##### PART B: EDGE CASES (Top 3, real recommend_songs) #####")
    for name, prefs in EDGE_CASES.items():
        print("=" * 78)
        print(f"{name}\n  {prefs}")
        for i, (sg, sc, _) in enumerate(recommend_songs(prefs, songs, 3), 1):
            print(f"{i}. {sg['title']} [{sg['genre']}/{sg['mood']}]  (Score: {sc:.2f})")

    print("\n##### PART C: EXPERIMENTS (Top 5 per profile) #####")
    for name, prefs in PROFILES.items():
        print("=" * 78)
        print(name)
        for label, w in [("Baseline        ", BASE), ("Exp1 energy x2, genre x0.5", EXP1), ("Exp2 no mood match ", EXP2)]:
            print(f"  {label}: {show_compact(songs, prefs, w)}")

    print("\n##### PART D: BIAS CHECKS #####")
    print("Genre counts:", dict(Counter(s["genre"] for s in songs)))
    print("Mood counts :", dict(Counter(s["mood"] for s in songs)))
    print("\nSpread (std dev) of each numeric similarity across the songs, per profile:")
    print(f"{'profile':20s} {'energy':>7s} {'valence':>8s} {'tempo':>7s}")
    tempo_range = TEMPO_MAX_BPM - TEMPO_MIN_BPM
    for name, p in PROFILES.items():
        e = [1 - abs(s["energy"] - p["energy"]) for s in songs]
        v = [1 - abs(s["valence"] - p["valence"]) for s in songs]
        t = [max(0, 1 - abs(s["tempo_bpm"] - p["tempo_bpm"]) / tempo_range) for s in songs]
        print(f"{name:20s} {pstdev(e):7.3f} {pstdev(v):8.3f} {pstdev(t):7.3f}")
    print("\nSongs sharing each profile's genre / mood:")
    for name, p in PROFILES.items():
        print(f"  {name}: genre matches={sum(s['genre'] == p['genre'] for s in songs)}, "
              f"mood matches={sum(s['mood'] == p['mood'] for s in songs)}")


if __name__ == "__main__":
    main()
