from pathlib import Path

import pytest

from src.explain import explain, score_components
from src.ranker import RankedSong, rank
from src.recommender import load_songs, score_song
from src.retriever import retrieve

CSV = str(Path(__file__).resolve().parent.parent / "data" / "songs.csv")
SONGS = load_songs(CSV)

PROFILES = [
    {"genre": "pop", "mood": "happy", "energy": 0.8, "valence": 0.8, "tempo_bpm": 120},
    {"genre": "lofi", "mood": "chill", "energy": 0.38, "valence": 0.58},
    {"genre": "", "mood": "sad", "energy": 0.3, "valence": 0.25, "tempo_bpm": 200},
    {"genre": "rock", "mood": "", "energy": 0.9, "valence": 0.4, "tempo_bpm": 40},
]


def test_components_sum_to_score_song_for_every_song_and_profile():
    for p in PROFILES:
        for song in SONGS:
            total = sum(c.points for c in score_components(p, song))
            assert total == pytest.approx(score_song(p, song)[0], abs=1e-9), (p, song["title"])


def test_max_points_follow_the_request():
    comps = {c.name: c for c in score_components(PROFILES[1], SONGS[0])}
    assert comps["tempo"] if "tempo" in comps else True
    assert "tempo" not in comps                       # no tempo requested
    assert comps["genre"].max_points == 2 and comps["mood"].max_points == 1
    nog = {c.name: c for c in score_components(PROFILES[2], SONGS[0])}
    assert nog["genre"].max_points == 0 and nog["genre"].detail == "no genre requested"


def test_explanation_for_top_pick():
    p = PROFILES[0]
    top = rank(p, retrieve(p, SONGS), 1)[0]
    e = explain(top, p)
    assert top.song["title"] == "Sunrise City"
    assert e.baseline_score == top.baseline_score and e.max_score == 6.0
    assert e.fit_percent == round(100 * top.baseline_score / 6.0, 1)
    assert "Sunrise City by Neon Echo" in e.summary and "genre (pop" in e.summary
    assert e.adjustments == []


def test_explanation_mentions_gaps():
    p = PROFILES[0]
    gym = next(s for s in SONGS if s["title"] == "Gym Hero")
    e = explain(RankedSong(gym, score_song(p, gym)[0]), p)
    assert "Weaker on mood" in e.summary


def test_explanation_lists_adjustments():
    p = {"genre": "rock", "mood": "intense", "energy": 0.9, "valence": 0.4}
    ranked = rank(p, retrieve(p, SONGS), 10, soft_labels=True, diversity=1.0)
    e = [explain(r, p) for r in ranked]
    assert any("similar genre/mood bonus" in a for x in e for a in x.adjustments)


def test_fit_percent_bounds_and_zero_division():
    for p in PROFILES:
        for r in rank(p, retrieve(p, SONGS), 40):
            assert 0 <= explain(r, p).fit_percent <= 100
