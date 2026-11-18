# AI Interactions Log

This file records how AI assistance was used to extend the Music Recommender into **MusicMind AI**, and how the results were checked. It is a summary of one development session with an AI coding assistant (Claude Code, running inside VS Code), written from that session's record. Nothing here is reconstructed from memory or invented, and where the record does not say something (for example, what the author tried by hand outside the session), this log says so.

**Scope.** This covers the MusicMind AI extension only (catalog expansion, parsing, guardrails, retrieval, ranking, explanations, pipeline, Streamlit app, logging, evaluation harness and documentation). The original recommender was also built with an AI assistant; that is described by the author in [Appendix A, Section 9 of the model card](model_card.md#appendix-a-original-model-card-vibe-matcher-10-18-song-catalog) and is not repeated here.

---

## Agentic Workflow (SF8)

**What task did you give the agent?**

Extend the existing recommender into MusicMind AI for an Applied AI System assignment: a Streamlit app with natural-language preference understanding, song retrieval, recommendation ranking, guardrails, reliability testing, a Mermaid architecture diagram, documentation and reproducible outputs. The work was run as an approval-gated, multi-step agentic workflow: the agent inspected the repo and proposed a plan, the author approved it, and the agent then implemented one stage at a time, ran the tests, and reported before the next stage was approved.

**Prompts used** (short quotes or close paraphrases of the author's actual directives, in order):

1. *Stage 0, inspect and plan:* "Inspect the entire repository... Explain the current architecture, existing functionality, reusable components, and limitations. Then propose an upgraded architecture... Do not modify any files or install packages yet. Give me a concise implementation plan."
2. *Decisions on the plan:* use Claude only as an **optional** parser with a rule-based offline fallback; expand the dataset to about 40 songs and clearly mark synthetic records; preserve the existing recommender and its scoring as the foundation; keep the modules separate; "avoid unnecessary complexity"; "Implement in small stages... Do not overwrite existing functionality or commit/push without my approval." The author also asked for a file-by-file breakdown before any implementation.
3. *Stage 1:* package files and pytest config; 18 to 40 songs with a `source` column (`original` 1-10, `added` 11-18, `synthetic` 19-40); CSV tests; keep `.venv` out of Git; do not install Anthropic.
4. *Environment check:* confirm which interpreter is active and whether pytest is in `.venv`; then "Choose Option A": install only pytest in `.venv`.
5. *Stage 2:* preferences, rule parser, optional Claude parser with timeout and fallback, guardrails, tests with mocked Claude responses; install `anthropic` only if needed.
6. *Focused review:* test negation, ambiguous keywords, low-confidence requests, conflicting preferences and prompt injection; fix genuine issues, add regression tests, "do not over-engineer the heuristic protections".
7. *Stage 3:* retriever, ranker (baseline via `score_song`, optional diversity), explanations, pipeline; deterministic; baseline regression tests.
8. *Stage 4:* "Change pipeline defaults to baseline mode (`soft_labels=False`, `diversity=0`)", keep enhanced as an option, show fit percentage and parser confidence separately, build the Streamlit UI; install only streamlit and pandas.
9. *Stage 5:* reliability harness with structured logging, measured results saved to `results/`, "clearly distinguish measured results from subjective/manual evaluation", "do not claim the system is unbiased or fully safe based only on tests".
10. *Stage 6:* finalize README, model card, diagram, this log and pinned requirements, using real results only.

**What did the agent generate or change?**

| Stage | Files created or changed | Tests passing afterward |
|---|---|---|
| 1 | `data/songs.csv` (+22 synthetic songs, `source` column), `src/__init__.py`, `tests/__init__.py`, `pytest.ini`, `tests/test_data.py` | 13 |
| 2 | `src/preferences.py`, `src/parser.py`, `src/guardrails.py`, three test files | 59 |
| 2 review | edits to `parser.py` and `guardrails.py`, `tests/test_review_regressions.py` | 108 |
| 3 | `src/retriever.py`, `src/ranker.py`, `src/explain.py`, `src/pipeline.py`, three test files | 171 |
| 4 | `app.py`, `tests/test_app.py`; pipeline defaults changed to baseline; streamlit and pandas installed in `.venv` | 185 |
| 5 | `src/logging_utils.py`, `src/evaluation.py`, `scripts/reliability.py`, `data/eval_cases.json`, `results/*`, two test files; logging added to parser and pipeline | 266 |
| 6 | `README.md`, `model_card.md`, `ai_interactions.md`, `diagrams/architecture.mmd`, `requirements*.txt`, `scripts/demo.py`, `tests/test_demo.py` | 271 |
| 6 follow-up | `src/logging_utils.py` (NullHandler), `scripts/demo.py` (workaround removed), `tests/test_logging.py`, test counts in the docs | 276 |

No commits or pushes were made by the agent, and `src/recommender.py`, `src/main.py`, `scripts/evaluate.py` and `tests/test_recommender.py` were left unmodified throughout (checked with `git diff` after each stage; `scripts/evaluate.py` output was also diffed against a saved baseline).

**What did you verify or fix manually?**

The record shows these human decisions and gates; it does **not** record what the author may have run or inspected on their own outside the session (for example, whether the app was opened in a browser by the author).

- Approved or held every stage before the next began, and set the five architecture decisions above.
- Chose Option A for the environment (install only pytest) after the agent reported that `.venv` had no pytest.
- Ordered a focused parser/guardrail review before Stage 3.
- Changed the pipeline default from enhanced to baseline (below).
- Required real command output, real results and an explicit measured-vs-subjective split in the documentation.

The agent's own verification at every stage was running the full test suite inside `.venv`, checking that the original files had no diff, and, from Stage 5, running `scripts\reliability.py --verify` (a second run must reproduce the saved results byte for byte).

---

## Decision log: suggestions accepted, modified and rejected

| # | Stage | Suggestion or event | Outcome | Why | How it was checked |
|---|---|---|---|---|---|
| 1 | Plan | The agent proposed using the LLM **only to parse text into a preference schema**, with the deterministic ranker and catalog as the source of truth and an offline rule-based fallback. | **Accepted** (with Claude made explicitly optional) | Songs can only come from the catalog; results stay reproducible; works with no API key. | Mocked and scripted Claude failures all end in valid, catalog-only results (`tests/test_parser.py`, `tests/test_reliability.py`). The live API was never tested. |
| 2 | Plan | The agent proposed expanding the catalog to about 40 songs. | **Accepted, specified by the author** | More coverage for retrieval and tests. The author fixed the exact `source` labels for ids 1-10, 11-18 and 19-40. | `tests/test_data.py` checks schema, ids, ranges and the source labels. |
| 3 | 1 | After the catalog grew, `scripts/evaluate.py` printed different output. | **Flagged, not suppressed** | The numbers in the original README and model card describe the 18-song catalog. | Output diffed against a pre-change baseline. Old numbers kept as Appendix A of the model card. |
| 4 | 1 | The agent found `.venv` held only pip, and that the passing tests had run on the system Python. | **Author chose Option A** (install pytest only) | A reproducible claim needs tests to run in the project's own environment. | 13 tests re-run inside `.venv`. |
| 5 | 2 | The agent had proposed installing `anthropic` at Stage 2 (and asked first); the author replied to install it "only if needed". | **Not installed** | The agent judged it unnecessary: the package is imported lazily and tests inject a fake client. | `pip list` after each stage shows no `anthropic`. |
| 6 | 2 | First parser run: 17 tests failed. | **Agent error, fixed** | A helper returned (position, label) while callers expected (label, position). | All parser tests pass. |
| 7 | 2 | The agent's own sample run parsed "chill lofi for studying, nothing too fast" with a fast tempo. | **Bug fixed** | "nothing" was not a negation word. | Regression test added. |
| 8 | 2 review | The probe run found misparsed negation ("anything but pop"), "mad about jazz" read as angry, bogus conflicts on "punk rock", unflagged "peaceful metal at 170 bpm", several injection phrasings that slipped through, and a false positive on "reveal the secret to good lofi". | **Fixed**, except limits left on purpose | The author asked not to over-engineer; the remaining gaps are listed in the model card (for example "Please repeat the text above" is not blocked). | 49 regression tests. |
| 9 | 3 | The agent made the pipeline default to **enhanced** ranking (similar-label credit and artist variety on). | **Not accepted as written.** The author changed the default to baseline in Stage 4. | Fits the requirement to preserve the original recommender as the foundation: default output should trace exactly to it. | A test pins the defaults. The Stage 5 evaluation later showed enhanced rarely changes the top-1 (unchanged in 92%) and gave no gain in artist variety (4.92 vs 4.92). Which mode is better has not been tested with people. |
| 10 | 3 | Three failing tests. | **Agent test errors, not code bugs; tests corrected** | One used an input with no preferences, one miscalculated a bonus (0.95, not 0.60), one asserted a penalty that was never charged. | Corrected tests pass; the code was unchanged. |
| 11 | 4 | The agent used a deprecated Streamlit argument and a test helper that did not work with the test library's element lists. | **Fixed** | Warnings and a failing test. | App renders without warnings; 13 UI tests pass. |
| 12 | 5 | While writing the conflicting-request cases the harness showed 4 of 7 returned status `ok`. | **Real design flaw found and fixed** | Contradictory requests were flagged only in a caption. They now return `low_confidence` with a "best guess" warning. | 61 of 61 cases met expectations after the fix. |
| 13 | 5 | A report line said "5.03 distinct artists in the top 5", which is impossible. | **Agent error, fixed** | A `k=10` case was counted over ten songs. | Report regenerated; it counts the first five only. |
| 14 | 6 | The agent tried to install a Mermaid renderer to check the diagram; the permission system **denied** the command. | **Not retried or worked around** | Respect the denial. | The diagram was checked with a local structural script only (balanced brackets, quotes, subgraphs, defined nodes). It has not been rendered by Mermaid tooling in this environment. |
| 15 | 6 | Running the README examples showed stray `input blocked` lines on stderr when no log handler is configured. | **Reported first, then fixed at the author's request** | During docs the author said not to change application logic, so the agent only mitigated it in `scripts/demo.py` and reported it. The author then asked for the one-line fix: a `logging.NullHandler` on the `musicmind` logger (guarded against duplicates). The demo workaround was removed because it would have stacked duplicate handlers. | New tests run `recommend()` in a clean process and check stderr is empty, that the check fails if the handler is removed, that re-import and `configure_logging()` leave exactly one NullHandler, and that JSON logging still writes. 276 tests pass. |

---

## What the AI could not tell and was not asked to claim

- Whether the recommendations sound right to a real listener, whether the system is fair across genres, or whether the guardrails stop a determined attacker. These need humans, and `results/manual_review_template.csv` is a blank sheet waiting for a reviewer.
- How the real Claude API behaves with the parser; only fake clients were used.
- The 22 synthetic songs and the 61 evaluation expectations were written with AI assistance and one person's judgment; they are not independent ground truth.

---

## Design Pattern (SF10)

*Not attempted.* No design-pattern exercise was requested in this session, so this section is intentionally left unfilled rather than retrofitted.
