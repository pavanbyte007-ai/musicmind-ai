"""MusicMind AI - Streamlit front end.

Run from the project root:   streamlit run app.py

Works fully offline with the rule-based parser. The optional Claude parser is
only used if you switch it on in the sidebar AND an ANTHROPIC_API_KEY is set;
otherwise the app silently falls back to the offline rules and says so.
"""
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.logging_utils import configure_logging  # noqa: E402
from src.pipeline import ENHANCED_DIVERSITY, MAX_K, PipelineResult, recommend  # noqa: E402

logger = logging.getLogger("musicmind")
if os.environ.get("MUSICMIND_LOG_FILE"):      # opt-in structured logging, e.g. logs/app.jsonl
    configure_logging(os.environ["MUSICMIND_LOG_FILE"])

EXAMPLES = [
    "chill lofi for studying",
    "fast angry punk at 170 bpm",
    "happy pop, high energy, around 120 bpm",
    "slow sad blues",
    "romantic jazz for a date night",
]
BASELINE, ENHANCED = "Baseline (original scoring)", "Enhanced (similar labels + artist variety)"
RULES, CLAUDE = "Offline rules (default)", "Claude (optional)"

st.set_page_config(page_title="MusicMind AI", page_icon="🎵", layout="centered")


# --------------------------------------------------------------------------- #
# State and callbacks
# --------------------------------------------------------------------------- #
def submit() -> None:
    """Remember the text the user submitted (button press or Enter)."""
    st.session_state["submitted"] = st.session_state.get("query", "")


def use_example(text: str) -> None:
    st.session_state["query"] = text
    submit()


@st.cache_data(show_spinner=False)
def catalog_table() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "songs.csv")


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_understanding(result: PipelineResult) -> None:
    """Parser confidence and what was understood (separate from per-song fit)."""
    prefs = result.preferences
    if prefs is None:
        return
    with st.container(border=True):
        left, right = st.columns([1, 2])
        left.metric("Parser confidence", f"{prefs.confidence:.0%}",
                    help="How well your words mapped onto genre, mood, energy and tempo. "
                         "This is about understanding the request, not about how good the songs are.")
        left.progress(min(1.0, max(0.0, prefs.confidence)))
        source = {"rules": "offline rules", "claude": "Claude", "rules-fallback": "offline rules (Claude unavailable)"}
        right.markdown("**Understood as**")
        facts = {
            "Genre": prefs.genre, "Mood": prefs.mood,
            "Energy": None if prefs.energy is None else f"{prefs.energy:.2f}",
            "Valence": None if prefs.valence is None else f"{prefs.valence:.2f}",
            "Tempo": None if prefs.tempo_bpm is None else f"{prefs.tempo_bpm:.0f} BPM",
        }
        shown = [f"**{k}:** {v}" for k, v in facts.items() if v]
        right.markdown("  \n".join(shown) if shown else "_nothing recognized_")
        right.caption(f"Parsed by: {source.get(prefs.source, prefs.source)}")


def render_messages(result: PipelineResult) -> None:
    codes = set(result.guardrail_codes)
    if result.status == "blocked":
        box = st.warning if "empty_input" in codes else st.error
        for msg in result.messages:
            box(msg, icon="🛡️" if "empty_input" not in codes else "✍️")
        return
    if result.status == "needs_clarification":
        st.info("I couldn't tell what kind of music you want. " + " ".join(result.messages), icon="💬")
        return
    for msg in result.messages:
        if "best guess" in msg:
            st.warning(msg, icon="⚠️")
        else:
            st.caption(f"ℹ️ {msg}")


def render_recommendation(rec, enhanced: bool) -> None:
    song, exp = rec.song, rec.explanation
    with st.container(border=True):
        head, nums = st.columns([3, 2])
        head.markdown(f"### {rec.rank}. {song['title']}")
        head.markdown(f"**{song['artist']}** · {song['genre']} · {song['mood']}")
        score_col, fit_col = nums.columns(2)
        score_col.metric("Score", f"{rec.score:.2f}", help=f"Out of {exp.max_score:g} possible for this request")
        fit_col.metric("Fit", f"{rec.fit_percent:g}%", help="How closely the song matches the parsed request")
        nums.progress(min(1.0, rec.fit_percent / 100))
        with st.expander("Why this song?"):
            st.write(exp.summary)
            table = pd.DataFrame(
                [{"Feature": c.name.capitalize(), "Points": round(c.points, 2),
                  "Max": c.max_points, "Detail": c.detail} for c in exp.components])
            st.dataframe(table, hide_index=True, width="stretch")
            if exp.adjustments:
                st.caption("Enhanced adjustments: " + "; ".join(exp.adjustments)
                           + f" (baseline score {rec.baseline_score:.2f})")
            elif enhanced:
                st.caption("No enhanced adjustments applied to this song.")


def render_catalog_note() -> None:
    table = catalog_table()
    synthetic = int((table["source"] == "synthetic").sum())
    with st.expander(f"About the catalog ({len(table)} songs)"):
        st.caption(f"Every recommendation comes from this catalog. {synthetic} records are synthetic "
                   "(made up for this project, not real songs); the rest are hand-written estimates.")
        st.dataframe(table, hide_index=True, width="stretch")


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
st.title("🎵 MusicMind AI")
st.caption("Describe the music you're in the mood for. I'll work out what you mean and pick songs from a "
           "small catalog, and show my reasoning.")

with st.sidebar:
    st.header("Settings")
    k = st.select_slider("Number of recommendations", options=list(range(1, MAX_K + 1)), value=5, key="k")
    mode = st.radio("Ranking", [BASELINE, ENHANCED], key="mode",
                    help="Baseline is the original scoring. Enhanced also gives partial credit to similar "
                         "genres and moods (e.g. metal for a rock fan) and avoids repeating artists.")
    parser_choice = st.radio("Preference parser", [RULES, CLAUDE], key="parser",
                             help="Offline rules work without any account. Claude needs the 'anthropic' package "
                                  "and an ANTHROPIC_API_KEY environment variable; if it isn't available the "
                                  "app falls back to the offline rules.")
    st.caption("Deterministic: the same request always gives the same results.")

st.text_input("What do you want to listen to?", key="query", on_change=submit,
              placeholder="e.g. chill lofi for studying, nothing too fast")
st.button("Find music", key="find", type="primary", on_click=submit)

st.caption("Try an example:")
for col, example in zip(st.columns(len(EXAMPLES)), EXAMPLES):
    col.button(example, key=f"ex_{example}", on_click=use_example, args=(example,), width="stretch")

submitted = st.session_state.get("submitted")
if submitted is None:
    st.info("Type a request above, or pick an example, to get started.", icon="👆")
else:
    enhanced = mode == ENHANCED
    try:
        with st.spinner("Finding songs..."):
            result = recommend(
                submitted, k=k,
                use_claude=(parser_choice == CLAUDE),
                soft_labels=enhanced,
                diversity=ENHANCED_DIVERSITY if enhanced else 0.0,
            )
    except Exception:  # last-resort safety net: never show a traceback to the listener
        logger.exception("pipeline failed")
        st.error("Something went wrong while finding songs. Please try rephrasing your request.", icon="🚧")
    else:
        render_messages(result)
        if result.status not in ("blocked",):
            render_understanding(result)
        if result.recommendations:
            st.subheader(f"Top {len(result.recommendations)} for “{result.query}”")
            for rec in result.recommendations:
                render_recommendation(rec, enhanced)
        elif result.status == "needs_clarification":
            st.caption("Try one of the examples above, or mention a genre, a mood, how energetic it should be, or a tempo.")
        elif result.status == "no_results":
            st.warning("No songs could be recommended.")

st.divider()
render_catalog_note()
