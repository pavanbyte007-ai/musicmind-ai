import sys
from types import SimpleNamespace

import pytest

from src import parser
from src.parser import (ParserError, normalize_genre, normalize_mood, parse_preferences,
                        parse_rules, parse_with_claude)


# ---------- rule-based parser: normal inputs ----------
def test_full_request():
    p = parse_rules("I want happy pop, high energy, about 128 bpm")
    assert (p.genre, p.mood, p.tempo_bpm) == ("pop", "happy", 128)
    assert p.energy == 0.9
    assert p.source == "rules"
    assert p.confidence > 0.6


def test_genre_synonyms():
    assert parse_rules("some lo-fi beats").genre == "lofi"
    assert parse_rules("old school hip-hop").genre == "hip hop"
    assert parse_rules("rnb slow jams").genre == "r&b"
    assert parse_rules("kpop please").genre == "k-pop"
    assert parse_rules("electronic stuff").genre == "edm"


def test_longest_phrase_wins():
    assert parse_rules("indie pop").genre == "indie pop"
    assert parse_rules("indie pop").extra_genres == []
    assert parse_rules("k-pop").genre == "k-pop"
    assert parse_rules("pop punk").genre == "punk"


def test_mood_synonyms():
    assert parse_rules("something calm").mood == "peaceful"
    assert parse_rules("music for studying").mood == "focused"
    assert parse_rules("cheerful tunes").mood == "happy"
    assert parse_rules("date night").mood == "romantic"


def test_energy_valence_tempo_cues():
    p = parse_rules("quiet and dark and slow")
    assert (p.energy, p.valence, p.tempo_bpm) == (0.3, 0.25, 70)
    assert parse_rules("a fast one").tempo_bpm == 145


def test_numeric_forms():
    assert parse_rules("energy 0.8").energy == 0.8
    assert parse_rules("energy of 70%").energy == pytest.approx(0.7)
    assert parse_rules("valence 3/10").valence == pytest.approx(0.3)
    assert parse_rules("120 BPM").tempo_bpm == 120


def test_negation_ignored():
    p = parse_rules("rock but no metal, not sad")
    assert p.genre == "rock" and p.mood is None
    assert parse_rules("I don't want country").genre is None
    p = parse_rules("chill lofi for studying, nothing too fast")
    assert p.tempo_bpm is None and p.genre == "lofi"


def test_case_and_whitespace_insensitive():
    assert parse_rules("  JAZZ   ").genre == "jazz"


def test_deterministic():
    text = "happy pop with high energy"
    assert parse_rules(text) == parse_rules(text)


# ---------- ambiguous / unusual inputs ----------
def test_nothing_recognized():
    p = parse_rules("something nice please")
    assert p.is_empty() and p.confidence == 0.0


def test_multiple_genres_keep_first_and_note():
    p = parse_rules("lofi or metal")
    assert p.genre == "lofi" and p.extra_genres == ["metal"]
    assert any("several genres" in n for n in p.notes)


def test_conflicting_energy_cues_recorded():
    p = parse_rules("quiet but loud")
    assert p.energy == 0.3 and p.conflicts


def test_word_boundaries():
    assert parse_rules("breakfast rapid").is_empty()   # 'fast' in breakfast, 'rap' in rapid


def test_normalize_helpers():
    assert normalize_genre("Hip_Hop") == "hip hop"
    assert normalize_genre("bossa nova") is None
    assert normalize_genre(None) is None
    assert normalize_mood("Calm") == "peaceful"
    assert normalize_mood("zesty") is None


# ---------- Claude parser with mocked responses ----------
class FakeClient:
    """Stands in for anthropic.Anthropic; records the request."""
    def __init__(self, tool_input=None, error=None, blocks=None):
        self.calls = []
        self._tool_input, self._error, self._blocks = tool_input, error, blocks
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        blocks = self._blocks if self._blocks is not None else [
            SimpleNamespace(type="text", text="ok"),
            SimpleNamespace(type="tool_use", name="set_preferences", input=self._tool_input),
        ]
        return SimpleNamespace(content=blocks)


def test_claude_parse_success_and_request_shape():
    client = FakeClient({"genre": "Jazz", "mood": "relaxed", "energy": 0.3, "tempo_bpm": 90, "confidence": 0.9})
    p = parse_with_claude("slow jazz", client=client, timeout=3.0)
    assert (p.genre, p.mood, p.energy, p.tempo_bpm, p.confidence, p.source) == ("jazz", "relaxed", 0.3, 90, 0.9, "claude")
    call = client.calls[0]
    assert call["timeout"] == 3.0
    assert call["tool_choice"] == {"type": "tool", "name": "set_preferences"}
    assert call["messages"] == [{"role": "user", "content": "slow jazz"}]
    assert "untrusted" in call["system"]
    assert "api_key" not in call and "ANTHROPIC" not in str(call)


def test_claude_garbage_values_are_neutralized_not_trusted():
    client = FakeClient({"genre": 5, "energy": "high", "valence": True, "confidence": 7})
    p = parse_with_claude("x", client=client)
    assert p.genre is None and p.energy is None and p.valence is None and p.confidence == 1.0


def test_claude_reply_without_tool_call_raises():
    with pytest.raises(ParserError):
        parse_with_claude("x", client=FakeClient(blocks=[SimpleNamespace(type="text", text="hi")]))
    with pytest.raises(ParserError):
        parse_with_claude("x", client=FakeClient(tool_input="not a dict"))


# ---------- selection and offline fallback ----------
def test_auto_mode_uses_claude_when_client_given():
    p = parse_preferences("anything", client=FakeClient({"genre": "rock", "confidence": 0.8}))
    assert p.source == "claude" and p.genre == "rock"


def test_use_claude_false_never_calls_client():
    client = FakeClient({"genre": "rock"})
    p = parse_preferences("jazz", use_claude=False, client=client)
    assert p.source == "rules" and p.genre == "jazz" and client.calls == []


def test_api_error_falls_back_to_rules():
    client = FakeClient(error=TimeoutError("timed out"))
    p = parse_preferences("happy pop", client=client)
    assert p.source == "rules-fallback"
    assert (p.genre, p.mood) == ("pop", "happy")
    assert any("TimeoutError" in n for n in p.notes)


def test_malformed_reply_falls_back_to_rules():
    p = parse_preferences("calm jazz", client=FakeClient(blocks=[]))
    assert p.source == "rules-fallback" and p.genre == "jazz"


def test_no_api_key_means_offline_rules(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(parser, "_make_client", lambda t: pytest.fail("must not build a client"))
    assert parse_preferences("metal").source == "rules"
    forced = parse_preferences("metal", use_claude=True)
    assert forced.source == "rules-fallback" and forced.genre == "metal"
    assert any("ANTHROPIC_API_KEY" in n for n in forced.notes)


def test_missing_anthropic_package_falls_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-not-a-real-key")
    monkeypatch.setitem(sys.modules, "anthropic", None)   # makes `import anthropic` fail
    p = parse_preferences("blues")
    assert p.source == "rules-fallback" and p.genre == "blues"
    assert any("not installed" in n for n in p.notes)
