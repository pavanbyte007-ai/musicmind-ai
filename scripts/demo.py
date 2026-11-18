"""Command-line demo of the MusicMind AI pipeline (offline, no API key).

Run from the project root:

    python scripts/demo.py "chill lofi for studying, nothing too fast"
    python scripts/demo.py "intense rock, dark, 150 bpm" --enhanced --k 5

Prints the status, what was understood, any warnings, and the recommendations
with their score, fit and explanation. It uses the offline rule-based parser.
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import ENHANCED_DIVERSITY, recommend  # noqa: E402


def render(result) -> str:
    lines = [f"Status: {result.status}"]
    p = result.preferences
    if p is not None:
        understood = {"genre": p.genre, "mood": p.mood, "energy": p.energy, "valence": p.valence, "tempo_bpm": p.tempo_bpm}
        shown = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in understood.items() if v is not None)
        lines.append(f"Understood as: {shown or 'nothing recognized'}")
        lines.append(f"Parser: {p.source}, confidence {p.confidence:.2f}")
    for message in result.messages:
        lines.append(f"Note: {message}")
    for rec in result.recommendations:
        song = rec.song
        lines.append("")
        lines.append(f"{rec.rank}. {song['title']} by {song['artist']} [{song['genre']}/{song['mood']}]  "
                     f"score {rec.score:.2f}, fit {rec.fit_percent:g}%")
        lines.append(f"   {rec.explanation.summary}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MusicMind AI command-line demo")
    ap.add_argument("request", help="what you want to listen to, in plain English")
    ap.add_argument("--k", type=int, default=5, help="number of recommendations (1-10)")
    ap.add_argument("--enhanced", action="store_true",
                    help="enhanced ranking: partial credit for similar genres/moods and artist variety")
    args = ap.parse_args(argv)
    result = recommend(args.request, k=args.k, use_claude=False,
                       soft_labels=args.enhanced, diversity=ENHANCED_DIVERSITY if args.enhanced else 0.0)
    print(render(result))
    return 0 if result.status in ("ok", "low_confidence", "needs_clarification") else 2


if __name__ == "__main__":
    sys.exit(main())
