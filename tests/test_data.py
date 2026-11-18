"""Data-quality tests for data/songs.csv."""
import csv
from pathlib import Path

import pytest

from src.recommender import load_songs, TEMPO_MIN_BPM, TEMPO_MAX_BPM

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "songs.csv"

EXPECTED_COLUMNS = [
    "id", "title", "artist", "genre", "mood", "energy", "tempo_bpm",
    "valence", "danceability", "acousticness", "source",
]
UNIT_FEATURES = ["energy", "valence", "danceability", "acousticness"]


@pytest.fixture(scope="module")
def rows():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_schema_columns_in_order(rows):
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == EXPECTED_COLUMNS


def test_catalog_has_forty_songs(rows):
    assert len(rows) == 40


def test_ids_are_unique_and_contiguous(rows):
    ids = [int(r["id"]) for r in rows]
    assert len(set(ids)) == len(ids)
    assert ids == list(range(1, 41))


def test_no_empty_text_fields(rows):
    for r in rows:
        for col in ("title", "artist", "genre", "mood", "source"):
            assert r[col].strip(), f"id {r['id']} has empty {col}"


def test_titles_are_unique(rows):
    titles = [r["title"] for r in rows]
    assert len(set(titles)) == len(titles)


def test_unit_features_in_range(rows):
    for r in rows:
        for col in UNIT_FEATURES:
            assert 0.0 <= float(r[col]) <= 1.0, f"id {r['id']} {col} out of range"


def test_tempo_within_scoring_range(rows):
    for r in rows:
        assert TEMPO_MIN_BPM <= float(r["tempo_bpm"]) <= TEMPO_MAX_BPM, f"id {r['id']} tempo"


def test_source_labels_match_id_ranges(rows):
    for r in rows:
        i = int(r["id"])
        expected = "original" if i <= 10 else "added" if i <= 18 else "synthetic"
        assert r["source"] == expected, f"id {i}"


def test_original_eighteen_records_preserved(rows):
    """Existing records and ids must not change (spot-check key fields)."""
    by_id = {int(r["id"]): r for r in rows}
    expected = {
        1: ("Sunrise City", "Neon Echo", "pop", "happy", 0.82, 118, 0.84),
        3: ("Storm Runner", "Voltline", "rock", "intense", 0.91, 152, 0.48),
        13: ("Iron Tide", "Black Harbor", "metal", "angry", 0.97, 172, 0.25),
        18: ("Rainy Window Blues", "Mara Quinn", "blues", "sad", 0.30, 68, 0.22),
    }
    for i, (title, artist, genre, mood, energy, tempo, valence) in expected.items():
        r = by_id[i]
        assert (r["title"], r["artist"], r["genre"], r["mood"]) == (title, artist, genre, mood)
        assert (float(r["energy"]), float(r["tempo_bpm"]), float(r["valence"])) == (energy, tempo, valence)


def test_catalog_is_diverse(rows):
    assert len({r["genre"] for r in rows}) >= 15
    assert len({r["mood"] for r in rows}) >= 14


def test_load_songs_still_works_with_source_column():
    songs = load_songs(str(CSV_PATH))
    assert len(songs) == 40
    assert set(songs[0]) == set(EXPECTED_COLUMNS) - {"source"}
