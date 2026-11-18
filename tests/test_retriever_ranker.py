"""Retriever and ranker tests, including regression against the original recommender."""
import itertools
from pathlib import Path

import pytest

from src.preferences import GENRES
from src.ranker import rank
from src.recommender import load_songs, recommend_songs, score_song
from src.retriever import (GENRE_SIMILARITY, MOOD_SIMILARITY, genre_similarity, mood_similarity,
                           retrieve)

CSV = str(Path(__file__).resolve().parent.parent / "data" / "songs.csv")


@pytest.fixture(scope="module")
def songs():
    return load_songs(CSV)


def prefs(**kw):
    base = {"genre": "pop", "mood": "happy", "energy": 0.8, "valence": 0.8, "tempo_bpm": 120}
    base.update(kw)
    return base


# ---------- similarity tables ----------
def test_similarity_basics():
    assert genre_similarity("rock", "rock") == 1.0
    assert genre_similarity("rock", "metal") == genre_similarity("metal", "rock") == 0.6
    assert genre_similarity("rock", "jazz") == 0.0
    assert genre_similarity("", "rock") == 0.0 and genre_similarity("", "") == 0.0
    assert mood_similarity("chill", "relaxed") == 0.8
    assert mood_similarity("sad", "happy") == 0.0


def test_similarity_tables_use_known_labels_and_valid_values():
    from src.preferences import MOODS
    for table, vocab in ((GENRE_SIMILARITY, GENRES), (MOOD_SIMILARITY, MOODS)):
        for pair, sim in table.items():
            assert len(pair) == 2 and pair <= set(vocab) and 0 < sim < 1, pair


# ---------- retriever ----------
def test_retrieve_includes_exact_and_similar_labels(songs):
    cands = retrieve(prefs(genre="rock", mood="intense"), songs)
    by_title = {c.song["title"]: c for c in cands}
    assert by_title["Storm Runner"].relevance == 1.0
    assert by_title["Iron Tide"].genre_sim == 0.6            # metal ~ rock
    assert by_title["Iron Cathedral"].mood_sim == 1.0         # metal/intense


def test_retrieve_is_deterministic_and_has_no_duplicates(songs):
    a = retrieve(prefs(), songs)
    b = retrieve(prefs(), songs)
    assert [c.song["id"] for c in a] == [c.song["id"] for c in b]
    assert len({c.song["id"] for c in a}) == len(a)


def test_retrieve_pads_when_nothing_matches_labels(songs):
    cands = retrieve({"genre": "", "mood": "", "energy": 0.5, "valence": 0.5}, songs, pool_size=8)
    assert len(cands) == 8 and all(c.how == "baseline" for c in cands)


def test_retrieve_empty_catalog():
    assert retrieve(prefs(), []) == []


def test_retrieve_only_returns_catalog_songs(songs):
    ids = {s["id"] for s in songs}
    assert all(c.song["id"] in ids and c.song in songs for c in retrieve(prefs(), songs))


# ---------- baseline regression: ranker == recommend_songs ----------
def _baseline(p, songs, k):
    return [(s["id"], sc) for s, sc, _ in recommend_songs(p, songs, k)]


def _ranked(p, songs, k, **kw):
    return [(r.song["id"], r.baseline_score) for r in rank(p, retrieve(p, songs, max(15, 3 * k)), k, **kw)]


def test_default_ranker_matches_original_for_many_profiles(songs):
    moods = ["happy", "chill", "intense", "sad", "romantic", ""]
    for genre, mood, energy in itertools.product(list(GENRES) + ["", "bossa nova"], moods, (0.1, 0.5, 0.95)):
        p = {"genre": genre, "mood": mood, "energy": energy, "valence": 1 - energy}
        assert _ranked(p, songs, 5) == _baseline(p, songs, 5), (genre, mood, energy)


def test_default_ranker_matches_original_with_tempo_and_other_k(songs):
    for k in (1, 3, 5, 10, 40):
        for tempo in (60, 120, 200):
            p = prefs(tempo_bpm=tempo)
            assert _ranked(p, songs, k) == _baseline(p, songs, k)


def test_golden_scores_from_readme(songs):
    top = rank(prefs(), retrieve(prefs(), songs), k=2)
    assert top[0].song["title"] == "Sunrise City" and round(top[0].baseline_score, 2) == 5.92
    p = prefs(genre="rock", mood="intense", energy=0.92, valence=0.35, tempo_bpm=150)
    best = rank(p, retrieve(p, songs), k=1)[0]
    assert best.song["title"] == "Storm Runner"


def test_baseline_score_is_exactly_score_song(songs):
    for r in rank(prefs(), retrieve(prefs(), songs), k=5, soft_labels=True, diversity=0.5):
        assert r.baseline_score == score_song(prefs(), r.song)[0]


# ---------- optional adjustments ----------
def test_soft_labels_off_gives_no_bonus(songs):
    assert all(r.label_bonus == 0 for r in rank(prefs(genre="rock"), retrieve(prefs(genre="rock"), songs), 10))


def test_soft_labels_reward_similar_genre(songs):
    p = prefs(genre="rock", mood="intense", energy=0.92, valence=0.35, tempo_bpm=150)
    plain = {r.song["title"]: r for r in rank(p, retrieve(p, songs), 40)}
    soft = {r.song["title"]: r for r in rank(p, retrieve(p, songs), 40, soft_labels=True)}
    # metal ~ rock (0.6 * 2 pts) and angry ~ intense (0.7 * 1 pt), each at half weight
    assert soft["Iron Tide"].label_bonus == pytest.approx(0.5 * 0.6 * 2 + 0.5 * 0.7 * 1)
    assert soft["Iron Tide"].final_score > plain["Iron Tide"].final_score
    assert soft["Storm Runner"].label_bonus == 0                            # exact match: no extra
    assert any("similar genre" in why for why in soft["Iron Tide"].reasons)


def test_soft_labels_never_lower_a_score(songs):
    for plain, soft in zip(rank(prefs(), retrieve(prefs(), songs), 40),
                           rank(prefs(), retrieve(prefs(), songs), 40, soft_labels=True)):
        assert soft.final_score >= soft.baseline_score


def test_diversity_separates_repeat_artists(songs):
    p = prefs(genre="lofi", mood="chill", energy=0.38, valence=0.58, tempo_bpm=76)
    cands = retrieve(p, songs)
    plain = rank(p, cands, 5)
    diverse = rank(p, cands, 5, diversity=1.5)
    artists = lambda rs: [r.song["artist"] for r in rs]
    assert len(set(artists(plain))) < 5          # the baseline repeats LoRoom
    assert len(set(artists(diverse))) == 5       # diversity avoids the repeat
    # When a repeat is unavoidable it is charged and explained.
    forced = rank(p, cands, 40, diversity=1.5)
    penalised = [r for r in forced if r.diversity_penalty > 0]
    assert penalised and all("repeat artist" in r.reasons[-1] for r in penalised)
    for r in forced:
        assert r.final_score == pytest.approx(r.baseline_score + r.label_bonus - r.diversity_penalty)


def test_diversity_zero_and_negative_are_baseline(songs):
    cands = retrieve(prefs(), songs)
    base = [r.song["id"] for r in rank(prefs(), cands, 8)]
    assert [r.song["id"] for r in rank(prefs(), cands, 8, diversity=0)] == base
    assert [r.song["id"] for r in rank(prefs(), cands, 8, diversity=-3)] == base


def test_rank_edge_cases(songs):
    cands = retrieve(prefs(), songs)
    assert rank(prefs(), cands, 0) == [] and rank(prefs(), [], 5) == []
    assert len(rank(prefs(), cands, 1000)) == len(cands)


def test_rank_is_deterministic(songs):
    cands = retrieve(prefs(), songs)
    runs = [[(r.song["id"], r.final_score) for r in rank(prefs(), cands, 8, True, 0.5)] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
