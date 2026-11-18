import csv
from pathlib import Path

from src.preferences import GENRES, MOODS, MOOD_PROFILE, Preferences, to_prefs
from src.recommender import load_songs, score_song

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "songs.csv"


def test_vocabulary_covers_catalog():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {r["genre"] for r in rows} <= set(GENRES)
    assert {r["mood"] for r in rows} <= set(MOODS)


def test_every_mood_has_profile_in_range():
    for mood, (energy, valence) in MOOD_PROFILE.items():
        assert 0 <= energy <= 1 and 0 <= valence <= 1, mood


def test_to_prefs_full():
    p = Preferences(genre="pop", mood="happy", energy=0.9, valence=0.8, tempo_bpm=128)
    assert to_prefs(p) == {"genre": "pop", "mood": "happy", "energy": 0.9, "valence": 0.8, "tempo_bpm": 128}


def test_to_prefs_fills_from_mood_profile():
    d = to_prefs(Preferences(mood="sad"))
    assert (d["energy"], d["valence"]) == MOOD_PROFILE["sad"]
    assert "tempo_bpm" not in d
    assert d["genre"] == ""


def test_to_prefs_neutral_defaults():
    d = to_prefs(Preferences())
    assert d["energy"] == 0.5 and d["valence"] == 0.5 and d["genre"] == "" and d["mood"] == ""


def test_to_prefs_output_works_with_existing_score_song():
    songs = load_songs(str(CSV_PATH))
    for p in (Preferences(), Preferences(genre="rock", tempo_bpm=150), Preferences(mood="chill", energy=0.3)):
        score, reasons = score_song(to_prefs(p), songs[0])
        assert score > 0 and reasons


def test_is_empty():
    assert Preferences().is_empty()
    assert not Preferences(tempo_bpm=100).is_empty()
