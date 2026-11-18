# 🎧 Model Card: MusicMind AI

*Extends the original Music Recommender Simulation ("Vibe Matcher 1.0"). The original model card is preserved word for word in [Appendix A](#appendix-a-original-model-card-vibe-matcher-10-18-song-catalog).*

**How to read this card.** Statements marked **Measured** come from automatic runs you can reproduce (`scripts\reliability.py`, `pytest`) and are backed by files in [results/](results/). Statements marked **Subjective** are judgments (mine or the assistant's) that no test establishes. Nothing here claims the system is unbiased, fair or fully safe.

---

## 1. Model Name

**MusicMind AI**: a natural-language front end, guardrails, retrieval and explanation layer built around the original content-based recommender (`score_song`, unchanged). Entry points: a Streamlit app (`app.py`), a command-line demo (`scripts/demo.py`) and the original runner (`python -m src.main`).

---

## 2. Intended Use

**Goal.** Given a short English request ("chill lofi for studying", "fast angry punk at 170 bpm"), work out the listener's genre, mood, energy, valence and tempo targets and recommend the best-matching songs from a 40-song catalog, with a score, a fit percentage and a plain-language reason for each.

- **Who it is for:** classroom exploration of how recommenders, guardrails and evaluation fit together.
- **What it recommends:** only songs present in `data/songs.csv`. The language model, when enabled, never picks or invents songs. It only fills a fixed preference schema.
- **Assumptions about the user:** they can describe their taste in English using words the parser knows, and their request describes one taste.

**Not intended for:**

- A real music service or real listeners. The catalog has 40 songs and 22 of them are synthetic.
- Judging how good a song or artist is, or deciding which artists get exposure. Scores measure closeness to a parsed request, not quality.
- Mental-health or wellbeing support. A request like "sad songs" returns songs labelled *sad*; the system does not assess or respond to how anyone is feeling.
- Anything that needs fairness across genres, languages or listeners (see sections 5 and 6).
- Security-sensitive use. The guardrails are heuristic (section 6).

---

## 3. How It Works (summary)

Pipeline (diagram: [diagrams/architecture.mmd](diagrams/architecture.mmd)):

1. **Input guardrails** block empty, over-500-character, prompt-injection and non-music text.
2. **Parsing.** A rule-based parser (synonyms, negation, numbers, tempo cues) is the default. An optional Claude parser uses a forced tool call with a 10 s timeout and falls back to the rules on any failure.
3. **Validation** clamps ranges, drops invalid numbers, snaps labels to the catalog vocabulary, flags contradictory requests and sets a parser confidence.
4. **Retrieval** shortlists songs with an equal or similar genre or mood, plus the baseline's top picks.
5. **Ranking** uses the original `score_song` (genre 2, mood 1, energy/valence/tempo up to 1 each, max 6). **Baseline** is the default. **Enhanced** (opt-in) adds half-weight credit for similar genre/mood and a 0.5-point penalty per repeated artist.
6. **Explanation** shows a per-feature breakdown, a fit percentage and a summary.
7. **Output guardrail** drops anything that is not an unchanged catalog record.

Parser **confidence** (how well the request was understood) and **fit** (how well a song matches what was understood) are different numbers and are always shown separately.

---

## 4. Data

**Catalog: `data/songs.csv`, 40 songs, 22 genres, 19 moods.** A `source` column labels where each record came from:

| Source | Ids | Count | Description |
|---|---|---|---|
| `original` | 1-10 | 10 | The songs provided with the original assignment. |
| `added` | 11-18 | 8 | Added in the original project to cover gaps (sad, classical, metal and others). |
| `synthetic` | 19-40 | **22** | Invented for this project. |

**About the 22 synthetic songs.** Titles, artist names and every numeric feature (energy, tempo, valence, danceability, acousticness) were written by hand, with the AI assistant drafting the records and the author approving the plan. They are **not** real recordings and no audio was measured. They were added to broaden coverage: seven new genres (latin, k-pop, folk, punk, funk, soul, house), five new moods (melancholic, dreamy, playful, reflective, hopeful) and extra songs in genres that had only one. Artist and title names are invented; I did not check them against real catalogs, so a coincidental resemblance to a real artist or song is possible.

**Balance (Measured).** Lofi is the largest genre with 4 songs; **7 genres have exactly one song** (folk, funk, house, k-pop, latin, punk, soul) and 7 moods have exactly one (confident, focused, hopeful, melancholic, playful, reflective, relaxed). Danceability and acousticness are loaded but not used in scoring. Missing from the catalog: lyrics, language, artist popularity, release year, listening history.

**Evaluation cases: `data/eval_cases.json`.** 61 hand-written requests (normal, vague, conflicting, blocked, edge, fallback) with the expectation I wrote for each. They are not real user queries.

---

## 5. Evaluation

### 5a. Measured (automatic, reproducible)

Source: [results/evaluation_report.md](results/evaluation_report.md) and [results/evaluation_results.json](results/evaluation_results.json). Reproduce with `.\.venv\Scripts\python.exe scripts\reliability.py --verify`. The run is deterministic and offline (Claude is replaced by a scripted fake).

| Metric | Result |
|---|---|
| Cases that met the expectation I wrote | 61 of 61 |
| Recommendation success (requests that should return songs) | 39 of 39 |
| Guardrails: inputs that should be blocked, blocked / false blocks | 12 of 12 / 0 |
| Catalog validity: songs checked / problems | 196 / 0 (enhanced mode also 0) |
| Baseline ranking vs original `recommend_songs` | 0 mismatches over 39 cases |
| Non-deterministic cases | 0 |
| Cases that fell back from Claude to the rules / still returned songs | 3 / 3 |
| Mean parser confidence: normal / conflicting / vague | 0.66 / 0.36 / 0.00 |
| Enhanced vs baseline: top-1 unchanged / mean distinct artists in top 5 | 92% / 4.92 vs 4.92 |
| Coverage probes (each genre and mood requested alone): top-5 contains it | 100% (22 genres, 19 moods) |

The test suite has 276 passing tests (`.\.venv\Scripts\python.exe -m pytest -q`).

**What these numbers mean.** "61 of 61" means the system did what I said it should on cases I wrote. The coverage probes are a **weak** test: the catalog was built to contain every genre and mood, so 100% was expected. Enhanced and baseline modes look nearly identical on these cases, and the numbers do not say which is better.

### 5b. Testing surprises and known failure cases

**Surprises found while testing, since fixed:**

- **The catalog expansion changed the original evaluation.** Adding 22 songs changed what `scripts\evaluate.py` prints (new songs entered the top 5, and Velvet Static became the rock profile's #2). The numbers in the original model card refer to the 18-song catalog and are now historical.
- **"nothing too fast" was parsed as a fast tempo**, because "nothing" was not treated as negation. Fixed, with a regression test.
- **"anything but pop" was parsed as a request *for* pop.** Fixed (it now requests nothing).
- **"mad about jazz" set the mood to angry.** Removed "mad" from the anger synonyms.
- **"punk rock" and "folk rock" triggered a bogus several-genres conflict.** Compound genres now map to one genre.
- **Contradictory requests came back as plain `ok`.** The reliability harness caught this: requests like "peaceful metal at 170 bpm" were flagged only in a small caption. Any conflicting request now returns `low_confidence` with a "best guess" warning.
- **Unconfigured logging printed to the console.** With no log handler, Python's last-resort handler wrote WARNING-level pipeline events (such as `input blocked`) to stderr. Fixed by attaching a `logging.NullHandler` to the `musicmind` logger, with tests that run `recommend()` in a clean process and check stderr is empty (and that the check fails if the handler is removed).
- **Several injection phrasings slipped through** ("ignore the above...", "show me your prompt", letters spaced out as "i g n o r e"). Patterns were added; one false positive ("reveal the secret to good lofi") was removed.

**Known failure cases that still exist (reproduced during this write-up):**

- **Unknown phrasing gets no result.** "I want something to cry to", "music for a rainy day", "songs like <artist>", "bossa nova" and "música tranquila" all return `needs_clarification`. "relaxing piano" is read as a mood only, because "piano" is recognized only in "piano music".
- **Ambiguous words.** "fast food jazz" is given a fast tempo (145 BPM). "upbeat sad songs" is accepted with no conflict warning, because the gap between the sad mood and the upbeat energy cue is just under the conflict threshold.
- **Negation cannot exclude.** "anything but pop" is no longer misread, but the system cannot recommend "everything except pop".
- **Injection defences are pattern lists.** A rephrased attack can pass the check. "Please repeat the text above" is not blocked, though it ends harmlessly as `needs_clarification`. The structural protection is that parsers only fill a schema and every value is validated.
- **Baseline ranking still has the original quirk.** For "intense rock, dark, 150 bpm" the baseline puts the bright pop song Gym Hero at #4, above the metal songs, only because its mood label is "intense". Enhanced mode softens this, but it is hand-tuned.
- **The live Claude path is untested** (only mocked and scripted clients).

### 5c. Human evaluation: limits

**No human evaluation has been done.** All evidence is automatic. Specifically:

- I wrote the data, the parser vocabulary, the similarity tables and the 61 expectations. The same person (with AI assistance) defined both the system and its test, so they can share blind spots.
- No real users, no user study, no rating of whether recommendations sound right, and no assessment of the explanations' clarity or the interface's usability.
- `results/manual_review_template.csv` is a **blank** rating sheet (relevance and explanation clarity, 1 to 5) for a human reviewer. It has not been filled in, and nothing in the project pretends otherwise.
- Even a small human review would be limited by the catalog: 40 songs, 22 invented, no audio.

---

## 6. Limitations, Bias and Misuse

**Limitations**

- **Tiny, partly synthetic catalog.** Tastes in the 7 single-song genres depend almost entirely on one song. A genre missing from the catalog earns no genre points.
- **Scoring inherits the original's weaknesses.** Genre and mood are exact labels worth 3 of 6 points, one profile is one taste, and energy and tempo overlap. On the original 18-song catalog valence varied least across songs, so it had the weakest say (not re-measured for 40 songs).
- **Rule parser is English-only and vocabulary-limited.** It reflects the words I thought of.
- **Fixed numbers are opinions.** The mood-to-energy/valence profile, the similarity tables (rock~metal and others), the conflict threshold (0.55) and the enhanced-mode weights are hand-picked.

**Bias considerations (Subjective; fairness is not measured)**

- **Unequal service across tastes.** A lofi listener has 4 songs to match and a folk or funk listener has 1. The coverage probes show every label is *present*, not that listeners are served equally.
- **Genre vocabulary and language.** The genre list is small and English-centred; non-English requests are not understood. Real music cultures are far more varied than 22 genres.
- **Stereotyped mood assumptions.** The mood profile assumes, for example, that "sad" means low energy and low valence, and the similarity tables encode cultural judgments about which genres "sound alike". Real listeners and songs break these assumptions.
- **Tests built from the same assumptions.** The evaluation cases use the same vocabulary the parser knows, so good results on them overstate how it would do on real phrasing.
- **Synthetic data can hide gaps.** Because the 22 synthetic songs were written to fill the catalog's holes, results on this catalog look better than they would on messy real data.

**Misuse and misinterpretation risks**

- **Prompt injection and off-topic use.** Mitigated by input patterns, schema-only parsing, value validation and an output check that only catalog songs are returned. These are not a guarantee of safety.
- **Privacy.** With the Claude parser enabled, the text of the request is sent to a third-party API. Logs store only a request's length and a short hash, redact API keys, and are git-ignored; they still reveal usage patterns.
- **Over-trusting the numbers.** "98% fit" means close to the parsed request, not "this is a great song for you". A low-confidence request still returns songs (marked as a best guess), which a user could mistake for a confident answer.
- **Not a wellbeing tool.** Mood-based matching must not be presented as support for someone who is struggling.

---

## 7. Future Work

- Get real human ratings using the blank template, and compare baseline and enhanced modes with actual listeners.
- Add measured audio features and a larger, balanced catalog; remove or clearly separate synthetic records.
- Support genuine exclusion ("anything but pop"), multi-taste profiles and broader phrasing, possibly by testing the Claude parser against the live API and comparing it with the rules.
- Evaluate fairness across genres on a bigger catalog before making any claim about it.

---

## 8. AI Collaboration Reflection

*Drafted by the AI assistant from the actual record of this project's development session, for the author to review and edit in their own voice. The full log is in [ai_interactions.md](ai_interactions.md).*

**Tool.** Claude Code (an AI coding assistant) did most of the typing for MusicMind AI, working in six approved stages. The author set the requirements, approved each stage, made the decisions listed below, and the assistant ran the tests after every stage.

**One suggestion that was accepted: use the language model only as a preference parser, with the deterministic recommender as the source of truth and an offline fallback.** The assistant proposed this in its initial architecture plan, and the author approved it with the added requirement that Claude be optional and that the existing recommender and scoring be preserved as the foundation. Reasons it was a good call: songs can only come from the catalog, so the model cannot hallucinate recommendations; results stay reproducible; and the project works with no API key. The design held up under testing: the harness's scripted Claude failures (timeouts, malformed replies, hallucinated labels, an error message containing a key) all ended in valid, catalog-only results with the key redacted. The cost is that the real API path is still unverified.

**One suggestion that was not accepted as written: enhanced ranking as the default.** In Stage 3 the assistant built the pipeline with the optional enhancements (similar-label credit, artist variety) switched **on** by default, reasoning that they fix a known weakness of the original scoring. The author changed this in Stage 4 to baseline by default, keeping enhanced as an explicit option. The reason that fits the project's stated rules is that the original recommender and its behaviour were to be preserved as the foundation, so default results should be exactly traceable to it. The later evaluation supports the cautious choice but does not settle the question: on the 39 evaluation cases that returned songs, enhanced mode left the top-1 song unchanged in 92% and gave no gain in artist variety (4.92 vs 4.92). Whether enhanced results are *better* is a subjective question that has not been tested with people.

**What verification caught (the assistant was wrong, and the checks showed it):**

- A parser helper returned (position, label) pairs while every caller expected (label, position); 17 tests failed at once. Fixed.
- Three Stage 3 test failures were mistakes in the assistant's own expected values (for example, it forgot that the mood "angry" is similar to "intense", so Iron Tide's bonus is 0.95, not 0.60). The code was right and the tests were corrected.
- A Stage 5 report line implied "5.03 distinct artists in the top 5", which is impossible; a `k=10` case had been counted. Fixed, and the report now counts the first five only.
- The reliability harness exposed a real design gap (conflicting requests reported as `ok`) that the assistant's own earlier tests had missed. Fixed.

**Lessons.** Treat AI-written code as a draft to be tested, require real command output before putting numbers in documentation, and keep what was measured separate from what was merely asserted. The harness and these documents were written to follow that rule. They still rest on one developer's data and expectations, which is why section 5c matters.

---

## Appendix A: Original model card (Vibe Matcher 1.0, 18-song catalog)

*Preserved from the original project, with headings shifted down two levels. Every number below refers to the 18-song catalog and the original scoring; after the catalog grew to 40 songs, `scripts\evaluate.py` prints different results. It is kept as a record of the original work, not as a description of the current system.*

### 🎧 Model Card: Music Recommender Simulation

#### 1. Model Name  

**Vibe Matcher 1.0**: a small, content-based music recommender that runs from the command line (`python -m src.main`).

---

#### 2. Intended Use  

**Goal / task.** Given one listener's taste (favorite genre and mood, plus target energy, valence and tempo), pick the 5 songs from an 18-song catalog that fit best, and say why.

Vibe Matcher suggests the top 5 songs from an 18-song catalog for one listener at a time.

- **What it recommends:** songs whose genre, mood, energy, valence (how positive it sounds) and tempo are close to what the listener asked for.
- **Assumptions about the user:** they can name a favorite genre and mood and pick target energy, valence and tempo, and their taste is one fixed point (not a mix of different tastes).
- **Who it is for:** classroom exploration. It is a simulation to learn how recommenders work, not a tool for real listeners.

**Not intended for:**

- Real listeners or a real music app. The catalog is 18 songs, so most tastes have almost nothing to match.
- Judging how good a song or artist is, or deciding which artists get exposure. The scores only measure closeness to a typed-in profile, and the song data is hand-made.
- Guessing a person's mood or taste from their behavior. It never looks at listening history, likes or skips.
- Anything that needs fairness across genres. Lofi has 3 songs and most genres have 1, so it treats listeners unequally by design.

---

#### 3. How the Model Works  

Think of it as a points game. The listener tells the system what they want, and every song earns points for how well it fits. The songs with the most points are recommended.

**What the system looks at.** For each song: genre, mood, energy, valence, and tempo. (Danceability and acousticness are in the data but are not used yet.) For the listener: a favorite genre and mood, plus target energy, valence and tempo.

**How a song earns points (maximum 6):**

- **Genre:** 2 points if it matches the favorite genre, otherwise 0.
- **Mood:** 1 point if it matches the favorite mood, otherwise 0.
- **Energy, valence and tempo:** up to 1 point each. The closer the song is to the target, the closer to 1 point it gets. A song that is exactly on target gets the full point, and a song that is far away gets very little. Tempo is measured against the full range of speeds in the catalog (60 to 172 beats per minute), so it counts on the same scale as the others.

*Example:* for a listener who wants happy pop at energy 0.8, valence 0.8 and 120 BPM, "Sunrise City" gets 2 (genre) + 1 (mood) + about 1 point each for energy, valence and tempo, for a total of 5.92 out of 6.

**How the top songs are chosen.** The system scores every song, lines them up from highest to lowest, and keeps the first five. If two songs tie, the one that comes first in the catalog wins, so the result is the same every time. Each recommendation also lists the points it earned, so you can see why it was picked.

**Changes from the starter logic.** The starter only returned the first few songs in the file and a placeholder explanation. Now every song is scored, and the explanation shows the real reasons. I also added a valence and tempo target to the listener profile and 8 new songs to the catalog.

---

#### 4. Data  

- **Size:** 18 songs. The original 10 were provided, and 8 were added to cover more styles.
- **Genres and moods:** 15 genres (pop, indie pop, lofi, rock, ambient, jazz, synthwave, hip hop, classical, metal, country, r&b, edm, reggae, blues) and 14 moods (for example happy, chill, intense, sad, romantic, angry).
- **Balance:** lofi has 3 songs, pop has 2, and every other genre has just 1.
- **What each song has:** title, artist, genre, mood, energy, tempo, valence, danceability and acousticness. The numbers are hand-written estimates, not measurements from real audio.
- **What is missing:** lyrics, language, artist popularity, release year, and anything about what real people listen to. Common styles such as Latin or K-pop are not represented, and sad, quiet music is covered by only two songs.

---

#### 5. Strengths  

- **Tastes with several matching songs.** The Chill Lo-fi profile gets a sensible top 3 (Midnight Coding 5.92, Library Rain 5.91, Focus Flow 4.93), because the catalog has 3 lofi and 3 chill songs.
- **Different tastes give different lists.** The lofi list shares no songs with the pop or rock lists. The pop and rock lists share only three high-energy songs (Gym Hero, Storm Runner and Laser Garden).
- **Close numbers can find songs outside the favorite genre.** The lofi listener gets Coffee Shop Stories (jazz) at #5 and Spacewalk Thoughts (ambient) at #4, because their energy, valence and tempo are close.
- **Every result can be explained.** Each song lists the points it earned, so an odd result like Gym Hero for the rock listener can be traced to one mood match.
- **It is repeatable.** The same profile always gives the same list, because ties are broken by song id.
- **It fails gently.** A genre that is not in the catalog ("k-pop") still returns sensible songs, and a tempo outside the catalog range (200 BPM) does not break the scores.

---

#### 6. Limitations and Bias 

- **Genre counts for a lot.** A genre match is 2 of the 6 points, and it must match exactly. "Pop" and "indie pop" are treated as different, so for a pop/happy listener, "Gym Hero" (pop, intense) outranks "Rooftop Lights" (indie pop, happy) even though Rooftop Lights fits the mood better.
- **Labels are all or nothing.** "Chill" and "relaxed" count as a complete mismatch, even though they sound alike.
- **Some tastes are served better than others.** A lofi fan has 3 songs to match, but someone who likes jazz or metal has only 1, and someone who likes a genre not in the catalog never earns any genre points.
- **One profile is one taste.** A listener who likes both lofi and metal cannot be described.
- **Energy and tempo overlap.** Fast songs tend to be high energy, so "intensity" is partly counted twice.
- **It only repeats what you ask for.** It has no listening history and no surprise, so it can trap a listener in a filter bubble.
- **Fixed tempo range.** Tempo is scaled to 60 to 172 BPM, so songs outside that range would need the scale updated.
- **Hand-made data.** The moods and numbers are one person's judgment, so the results reflect those choices.

**What the evaluation showed.** Genre and mood labels together can earn 3 of the 6 points, so a song with the right labels but the wrong sound can outrank a song that sounds right (the conflicting lofi profile and Gym Hero for the rock fan). Taste in genres with only one song, like rock, depends almost entirely on that one song, and a genre missing from the catalog earns nothing. Valence varies the least across songs (a spread of 0.11 to 0.17, compared with 0.19 to 0.24 for energy and tempo), so it has the weakest say in the ranking even though it is what separates a bright song from a dark one. Energy and tempo also move together, so a song's intensity is partly counted twice. The results are only as good as the 18 hand-made songs and the labels attached to them.

---

#### 7. Evaluation  

I tested three user profiles, three edge cases, and two experiments on the 18-song catalog. The two unit tests in `tests/test_recommender.py` pass. They only check that results come back sorted and that an explanation exists, so the profile results below were checked by running the recommender and reading the scores. Everything below can be reproduced by running `python scripts/evaluate.py` from the project root (the output is the same every time).

##### Results for three profiles

| Profile | Genre / mood | Energy | Valence | Tempo |
|---|---|---|---|---|
| High-Energy Pop | pop / happy | 0.90 | 0.80 | 128 BPM |
| Chill Lo-fi | lofi / chill | 0.38 | 0.58 | 76 BPM |
| Deep Intense Rock | rock / intense | 0.92 | 0.35 | 150 BPM |

| # | High-Energy Pop | Chill Lo-fi | Deep Intense Rock |
|---|---|---|---|
| 1 | Sunrise City 5.79 | Midnight Coding 5.92 | Storm Runner 5.84 |
| 2 | Gym Hero 4.90 | Library Rain 5.91 | Gym Hero 3.41 |
| 3 | Rooftop Lights 3.81 | Focus Flow 4.93 | Iron Tide 2.65 |
| 4 | Laser Garden 2.95 | Spacewalk Thoughts 3.69 | Night Drive Loop 2.33 |
| 5 | Storm Runner 2.46 | Coffee Shop Stories 2.73 | Laser Garden 2.32 |

##### Interesting observations

- **Chill Lo-fi works best.** The catalog has 3 lofi and 3 chill songs, so the top 3 are all sensible. Midnight Coding and Library Rain are almost tied (5.92 vs 5.91). Coffee Shop Stories (jazz) shows up at #5 because its numbers are so close, which is a good cross-genre find.
- **Gym Hero keeps appearing where it may not belong.** It is a bright, upbeat pop song (valence 0.77). It ranks #2 for the pop fan because genre matches, which is reasonable. It also ranks #2 for the *rock* fan, who asked for something dark (valence 0.35), only because its mood is "intense" (+1 point).
- **The best sound match for the rock fan is only #3.** Iron Tide (metal, angry) has energy 0.97, valence 0.25 and 172 BPM, which is closest to a "deep, intense" sound. It ranks below Gym Hero because "metal" is not "rock" and "angry" is not "intense".
- **Scores fall off a cliff after #1 or #3.** The rock profile drops from 5.84 to 3.41, and the pop profile drops from 3.81 to 2.95. Only songs that match the labels score high, and everything else clusters between about 2 and 3.
- **Rock has only one song to match.** After Storm Runner, the rest of the list is chosen almost entirely by numbers.

##### Edge cases

| Case | What happened |
|---|---|
| Genre not in the catalog ("k-pop") | No song can earn the 2 genre points, so the best possible score is 4. The results still look reasonable (Sunrise City 3.92, Rooftop Lights 3.91) because mood and numbers carry it. |
| Conflicting profile (lofi/chill but energy 0.95, valence 0.9, 170 BPM) | The top 3 are still the slow lofi songs (4.31, 4.22, 3.34), even though their energy is around 0.4. The genre and mood labels (up to 3 points) outweigh poor numeric fits. |
| Tempo above the catalog range (200 BPM) | It works. Tempo similarity is clamped at 0 so it never goes negative. Iron Tide wins with 5.75. |

##### Experiments

**Experiment 1: double the energy weight and halve the genre weight** (genre 1 point, energy up to 2 points).

| Profile | What changed |
|---|---|
| High-Energy Pop | Same top 3 order. The gap between Gym Hero and Rooftop Lights shrinks (4.87 vs 4.67). Storm Runner climbs from 2.46 to 3.45. |
| Chill Lo-fi | Library Rain and Midnight Coding swap places (both about 5.88). Spacewalk Thoughts (4.59) and Coffee Shop Stories (3.73) move much closer to the leaders. |
| Deep Intense Rock | Top 3 stay the same. Laser Garden and Night Drive Loop swap at #4 and #5. Gym Hero stays at #2 (4.40) because its energy is almost perfect, so more energy weight helps it even more. |

Result: the #1 song did not change for any profile, so mood plus a smaller genre bonus still decides the winner. The lower ranks changed. More energy weight did not fix the Gym Hero problem, because energy cannot tell Gym Hero from Iron Tide. Valence can (0.58 vs 0.90 similarity), and valence was not weighted more.

**Experiment 2: remove mood matching** (mood worth 0 points).

| Profile | What changed |
|---|---|
| High-Energy Pop | Gym Hero (4.90) now ranks **above** Sunrise City (4.79). The "happy vs intense" difference disappears, and Rooftop Lights drops from #3 to #4. |
| Chill Lo-fi | Focus Flow, Midnight Coding and Library Rain become a three-way near-tie (4.93, 4.92, 4.91). Spacewalk Thoughts falls out of the top 5, and Velvet Hours (r&b, romantic) enters at #5. |
| Deep Intense Rock | The ranking gets **better**: Iron Tide moves up to #2 (2.65) and Gym Hero falls to #3 (2.41). |

Result: mood helps the pop and lofi profiles but hurts the rock profile. It is the main thing that lets Gym Hero beat Iron Tide, because the labels "intense" and "angry" do not match even though the songs sound alike.

---

#### 8. Future Work  

- **Partial credit for similar labels.** Let "pop" and "indie pop", "rock" and "metal", or "chill" and "relaxed" earn some points instead of none. This would help Iron Tide, which sounds the most like what the rock listener asked for but only ranks #3.
- **Better use of the features.** Give valence more weight, since it is what separates Gym Hero from Iron Tide, and try danceability and acousticness. The `likes_acoustic` field exists in the profile but is not used in scoring yet. Energy and tempo overlap, so one of them could count for less.
- **Better explanations.** Show each score as a share of the maximum, and explain why a song did not make the list (for example, why Iron Tide ranked below Gym Hero).
- **More variety in the top results.** Avoid repeating an artist. The lofi top 3 includes two songs by LoRoom (Midnight Coding and Focus Flow).
- **More complex tastes.** Allow a profile with more than one taste, use a bigger catalog with measured audio features, and eventually learn from likes and skips.
- **Tests.** Add tests for exact scores, ranking order and tie-breaking, since the current two tests only check sorting and that an explanation exists.

---

#### 9. Personal Reflection  

**Understanding recommenders.** I started by researching how Spotify, YouTube and TikTok recommend content and the difference between content-based and collaborative filtering. I built a content-based recommender because I only have song attributes, not listening data from many users.

**Dataset analysis.** I went through `songs.csv` column by column. Energy, tempo and acousticness move together, while valence is what separates songs with similar energy (Gym Hero vs. Storm Runner). The catalog had no sad, classical or metal songs, so I expanded it from 10 to 18 songs to cover those gaps.

**Algorithm and weight decisions.** I designed the score as a points system: genre 2, mood 1, and energy, valence and tempo by closeness to the listener's targets, with tempo scaled by its range so it counts like the others. I compared an earlier mood-heavy weighting with the final genre 2 / mood 1 version and chose the final one. I knew it would rank Gym Hero (pop, intense) above Rooftop Lights (indie pop, happy) for a pop/happy listener.

**Testing and evaluation.** I defined three profiles (High-Energy Pop, Chill Lo-fi, Deep Intense Rock), three edge cases, and two experiments (energy weight doubled with genre halved, and mood removed). The results were more interesting than I expected:
- Gym Hero showed up at #2 for the rock listener only because its mood matched, while Iron Tide, the closest sound match, was #3.
- Removing mood fixed the rock list but made the pop list worse.
- Doubling energy did not change the #1 song for any profile.
- Valence varies the least across songs, so it has the weakest say, even though it separates bright songs from dark ones.
- Genre and mood together are worth up to 3 of the 6 points, so a song with the right labels can beat one that sounds right.

**Using AI assistance.** I used an AI coding assistant to implement the functions, the command-line runner and the evaluation script, and to help draft the documentation. I directed it step by step. I set the formula and the test profiles, had it propose changes before it touched any file, and required the tests and the program to actually run, with real output, before any results went into this card. Reviewing its work caught real problems: a README claim that was wrong (pop has two songs, not one), a mismatch between the README run command and the import in `main.py`, and a starter test that passed only by accident. I made the design decisions and checked the results, and the assistant did much of the typing.

**Next.** I would give partial credit for similar labels (rock and metal, chill and relaxed), put more weight on valence, avoid repeating an artist in the top results, and add tests that check exact scores.
