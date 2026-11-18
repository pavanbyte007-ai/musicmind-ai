"""Guardrails: checks before parsing (the raw text) and after (the preferences).

check_input()          blocks empty, over-long, prompt-injection and non-music text.
validate_preferences() repairs or drops invalid values, snaps labels to the
                       catalog vocabulary, and flags conflicting preferences.

Severity "block" means the pipeline should stop and show the message. "warn"
means continue, but show the message and lower the confidence.
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import List, Tuple

from src.parser import has_music_cue, normalize_genre, normalize_mood
from src.preferences import MOOD_PROFILE, Preferences

MAX_INPUT_CHARS = 500
MAX_TEMPO_BPM = 300
CONFLICT_GAP = 0.55          # energy/valence difference that counts as contradictory
WARNING_PENALTY = 0.15       # confidence lost per warning
LOW_CONFIDENCE = 0.4         # below this, ask the user to clarify

# Heuristic only: a blocklist cannot catch everything. The real protection is
# structural: parsers only fill a schema, and validate_preferences() accepts
# nothing but catalog labels and in-range numbers.
_INJECTION_PATTERNS = [
    r"\b(?:ignore|disregard|forget|override)\b.{0,30}\b(?:instructions?|prompts?|rules|guidelines|everything)\b",
    r"\b(?:ignore|disregard)\b.{0,20}\b(?:above|previous|prior|earlier|preceding)\b",
    r"\b(?:system|developer|hidden)\s+(?:prompt|message|instructions?)\b",
    r"\b(?:show|print|repeat|output|display|reveal|tell)\b.{0,25}\b(?:prompt|instructions|api\s*key)\b",
    r"\bnew\s+instructions?\b",
    r"\byou\s+are\s+now\b",
    r"\bfrom\s+now\s+on\s+you\b",
    r"\bpretend\s+(?:to\s+be|you\s+are)\b",
    r"\bact\s+as\s+(?:an?\s+)?(?:unrestricted|jailbroken|different|evil|dan)\b",
    r"\b(?:jailbreak|developer\s+mode|do\s+anything\s+now)\b",
    r"<\s*/?\s*(?:system|assistant|tool|instructions?)\b",
    r"\[\s*/?\s*(?:system|inst)\s*\]",
    r"```\s*(?:system|assistant)\b",
]
_INJECTION_RX = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PATTERNS]

_NON_MUSIC_RX = re.compile(
    r"\b(?:weather|recipe|stock\s+price|translate|essay|poem|email|calculate|solve|"
    r"capital\s+of|homework\s+help|javascript|python|sql|joke|president|write\s+(?:me\s+)?(?:a|an)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str        # "block" or "warn"
    message: str


@dataclass
class GuardrailResult:
    issues: List[Issue] = field(default_factory=list)
    text: str = ""       # cleaned input text (check_input only)

    @property
    def blocked(self) -> bool:
        return any(i.severity == "block" for i in self.issues)

    @property
    def ok(self) -> bool:
        return not self.blocked

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "warn"]

    def codes(self) -> List[str]:
        return [i.code for i in self.issues]

    def add(self, code: str, severity: str, message: str) -> None:
        self.issues.append(Issue(code, severity, message))


def sanitize(text) -> str:
    """Normalize unicode, drop control characters, collapse whitespace."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch if ch in "\n\t" or unicodedata.category(ch)[0] != "C" else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def check_input(text) -> GuardrailResult:
    """Validate the raw user request before any parsing or API call."""
    result = GuardrailResult()
    cleaned = sanitize(text)
    result.text = cleaned
    if not cleaned:
        result.add("empty_input", "block", "Please describe the music you want, for example "
                   "'chill lofi for studying' or 'fast upbeat pop at 128 bpm'.")
        return result
    if len(cleaned) > MAX_INPUT_CHARS:
        result.add("too_long", "block", f"That request is {len(cleaned)} characters long. "
                   f"Please keep it under {MAX_INPUT_CHARS}.")
        return result
    despaced = re.sub(r"(?<=\b\w) (?=\w\b)", "", cleaned)   # "i g n o r e" -> "ignore"
    if any(rx.search(cleaned) or rx.search(despaced) for rx in _INJECTION_RX):
        result.add("prompt_injection", "block", "That request looks like an attempt to change how the "
                   "system behaves, so it was not processed. Describe the music you want instead.")
        return result
    if _NON_MUSIC_RX.search(cleaned) and not has_music_cue(cleaned):
        result.add("non_music", "block", "MusicMind only recommends music. "
                   "Try describing a genre, mood or energy level.")
    return result


def _finite(value):
    """Return a float, or None if the value is missing, non-numeric, NaN or infinite."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean_unit(name: str, value, result: GuardrailResult):
    """Clamp a 0-1 value; drop it if it is not a usable number."""
    if value is None:
        return None
    number = _finite(value)
    if number is None:
        result.add("invalid_value", "warn", f"Ignored {name}: '{value}' is not a valid number.")
        return None
    if not 0.0 <= number <= 1.0:
        clamped = min(1.0, max(0.0, number))
        result.add("out_of_range", "warn", f"{name.capitalize()} {number:g} is outside 0-1; using {clamped:g}.")
        return clamped
    return number


def detect_conflicts(prefs: Preferences) -> List[str]:
    """Return human-readable descriptions of contradictory preferences."""
    found = list(prefs.conflicts)

    moods = [m for m in [prefs.mood, *prefs.extra_moods] if m in MOOD_PROFILE]
    for i, a in enumerate(moods):
        for b in moods[i + 1:]:
            (ea, va), (eb, vb) = MOOD_PROFILE[a], MOOD_PROFILE[b]
            if round(abs(ea - eb), 2) >= CONFLICT_GAP or round(abs(va - vb), 2) >= CONFLICT_GAP:
                found.append(f"moods '{a}' and '{b}' pull in opposite directions")

    if prefs.mood in MOOD_PROFILE:
        mood_energy, mood_valence = MOOD_PROFILE[prefs.mood]
        if prefs.energy is not None and round(abs(mood_energy - prefs.energy), 2) >= CONFLICT_GAP:
            found.append(f"mood '{prefs.mood}' does not fit energy {prefs.energy:g}")
        if prefs.valence is not None and round(abs(mood_valence - prefs.valence), 2) >= CONFLICT_GAP:
            found.append(f"mood '{prefs.mood}' does not fit valence {prefs.valence:g}")

    # Tempo vs energy: use the explicit energy, else the energy implied by the mood.
    energy = prefs.energy if prefs.energy is not None else MOOD_PROFILE.get(prefs.mood, (None,))[0]
    if prefs.tempo_bpm is not None and energy is not None:
        if (prefs.tempo_bpm >= 140 and energy <= 0.35) or (prefs.tempo_bpm <= 70 and energy >= 0.85):
            found.append(f"tempo {prefs.tempo_bpm:g} BPM does not fit energy {energy:g}")

    if prefs.extra_genres:
        found.append(f"several genres requested ({', '.join([prefs.genre, *prefs.extra_genres])}); "
                     "only the first is used")
    return found


def filter_to_catalog(songs: List[dict], catalog: List[dict]) -> Tuple[List[dict], GuardrailResult]:
    """Output guardrail: keep only songs that exist, unchanged, in the catalog.

    Anything else (an unknown id, or a record whose fields differ from the
    catalog row) is dropped and reported, so a recommendation can never be a
    made-up or altered song.
    """
    result = GuardrailResult()
    by_id = {s["id"]: s for s in catalog}
    kept = []
    for song in songs:
        if by_id.get(song.get("id")) == song:
            kept.append(song)
        else:
            result.add("not_in_catalog", "warn", f"Dropped a recommendation that is not in the catalog: "
                       f"{song.get('title', '?')!r}.")
    return kept, result


def needs_clarification(prefs: Preferences) -> bool:
    """True when the request is too weak or contradictory to act on silently.

    One clearly stated field (confidence 0.4) is enough; an empty or conflicted
    request (below 0.4) should make the UI ask the user to rephrase.
    """
    return prefs.confidence < LOW_CONFIDENCE


def validate_preferences(prefs: Preferences) -> Tuple[Preferences, GuardrailResult]:
    """Return a cleaned copy of the preferences and the issues that were found.

    Values from any parser (rules or Claude) go through here, so the ranker only
    ever sees numbers in range and labels that exist in the catalog.
    """
    result = GuardrailResult()

    energy = _clean_unit("energy", prefs.energy, result)
    valence = _clean_unit("valence", prefs.valence, result)

    tempo = None
    if prefs.tempo_bpm is not None:
        number = _finite(prefs.tempo_bpm)
        if number is None or not 0 < number <= MAX_TEMPO_BPM:
            result.add("invalid_tempo", "warn", f"Ignored tempo '{prefs.tempo_bpm}': "
                       f"expected 1-{MAX_TEMPO_BPM} BPM.")
        else:
            tempo = number

    genre = normalize_genre(prefs.genre)
    if prefs.genre and genre is None:
        result.add("unknown_genre", "warn", f"Genre '{prefs.genre}' is not in the catalog; ignored.")
    mood = normalize_mood(prefs.mood)
    if prefs.mood and mood is None:
        result.add("unknown_mood", "warn", f"Mood '{prefs.mood}' is not in the catalog; ignored.")

    def snap(values, normalizer, primary):
        out = [normalizer(v) for v in values]
        return [v for v in dict.fromkeys(out) if v and v != primary]

    cleaned = replace(
        prefs,
        genre=genre, mood=mood, energy=energy, valence=valence, tempo_bpm=tempo,
        extra_genres=snap(prefs.extra_genres, normalize_genre, genre),
        extra_moods=snap(prefs.extra_moods, normalize_mood, mood),
        notes=list(prefs.notes), conflicts=list(prefs.conflicts),
    )

    for message in detect_conflicts(cleaned):
        result.add("conflict", "warn", f"Conflicting request: {message}.")

    if cleaned.is_empty():
        result.add("no_preferences", "warn", "No genre, mood, energy or tempo was recognized. "
                   "Try something like 'upbeat pop' or 'slow jazz for a rainy evening'.")
        cleaned.confidence = 0.0
    else:
        penalty = WARNING_PENALTY * len(result.warnings)
        cleaned.confidence = round(min(1.0, max(0.0, cleaned.confidence - penalty)), 2)

    cleaned.notes.extend(i.message for i in result.issues)
    return cleaned, result
