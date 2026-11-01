# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

This version is a content-based recommender. It compares each song's attributes in `data/songs.csv` to a user's taste profile, scores every song with a points system (maximum 6), and returns the top matches with a short reason for each.

---

## How The System Works

This recommender suggests songs by comparing each song's "vibe" to a user's taste profile. It is *content-based*: it only looks at song attributes, not at what other listeners do.

### The data

**Songs.** `data/songs.csv` holds 18 songs across 15 genres and 14 moods. Each song has: `id`, `title`, `artist`, `genre`, `mood`, `energy`, `tempo_bpm`, `valence`, `danceability` and `acousticness`. Energy, valence, danceability and acousticness are numbers from 0 to 1. Tempo is in beats per minute (60 to 172 in this catalog). Only genre, mood, energy, valence and tempo are used in scoring. Danceability and acousticness are kept for later.

**The user profile** describes one taste as a single set of targets:

```python
{"genre": "pop", "mood": "happy", "energy": 0.8, "valence": 0.8, "tempo_bpm": 120}
```

### Scoring one song

Each song earns points for how well it matches the profile:

| Feature | Points | How it is calculated |
|---|---|---|
| genre | 2 | 2 if it matches the favorite genre, otherwise 0 |
| mood | 1 | 1 if it matches the favorite mood, otherwise 0 |
| energy | up to 1 | `1 - abs(song energy - target)` |
| valence | up to 1 | `1 - abs(song valence - target)` |
| tempo | up to 1 | `1 - abs(song BPM - target BPM) / 112` |

The closer a number is to the target, the more points it earns. Tempo is divided by 112 (the 60 to 172 BPM range) so it counts on the same 0 to 1 scale as the others. The maximum score is 6.

*Example:* for the profile above, Sunrise City scores 2 (genre) + 1 (mood) + 0.98 (energy) + 0.96 (valence) + 0.98 (tempo) = **5.92**.

### Ranking: Top K

Every song is scored, the list is sorted from highest to lowest (ties go to the lower `id`, so results are repeatable), and the first *k* songs are returned. Each one comes with a "Because..." line listing the points it earned.

```
User profile + songs.csv -> score every song -> sort high to low -> top k -> show with reasons
```

### Biases and limitations

- **Genre carries a lot of weight.** A genre match is worth 2 of the 6 points, and the match is exact. "Pop" and "indie pop" count as different, and a rock fan gets no credit for a metal song.
- **Labels are all-or-nothing.** "Chill" and "relaxed" count as a complete mismatch, even though they sound alike.
- **The catalog is small and uneven.** Lofi has 3 songs and pop has 2. Every other genre has 1, so some tastes have almost nothing to match.
- **One profile is one taste.** Someone who likes both lofi and metal can't be described.
- **Energy and tempo overlap.** Fast songs tend to be high energy, so "intensity" is counted twice.
- **It keeps recommending what you already said you like.** There is no listening history, no popularity and no surprise, so it can create a filter bubble.
- **The data is hand-made.** The moods and numbers are subjective, so the results reflect the choices of whoever wrote them.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Actual output of `python -m src.main` for the default profile:

```
Loaded 18 songs.
User profile: genre=pop, mood=happy, energy=0.8, valence=0.8, tempo=120 BPM

Top 5 recommendations:

1. Sunrise City by Neon Echo  (Score: 5.92)
   - genre matches (pop) +2
   - mood matches (happy) +1
   - energy 0.82 vs target 0.80 +0.98
   - valence 0.84 vs target 0.80 +0.96
   - tempo 118 vs target 120 BPM +0.98

2. Gym Hero by Max Pulse  (Score: 4.73)
   - genre matches (pop) +2
   - energy 0.93 vs target 0.80 +0.87
   - valence 0.77 vs target 0.80 +0.97
   - tempo 132 vs target 120 BPM +0.89

3. Rooftop Lights by Indigo Parade  (Score: 3.91)
   - mood matches (happy) +1
   - energy 0.76 vs target 0.80 +0.96
   - valence 0.81 vs target 0.80 +0.99
   - tempo 124 vs target 120 BPM +0.96

4. Laser Garden by Pulse Theory  (Score: 2.78)
   - energy 0.95 vs target 0.80 +0.85
   - valence 0.80 vs target 0.80 +1.00
   - tempo 128 vs target 120 BPM +0.93

5. Concrete Crown by Kid Meridian  (Score: 2.57)
   - energy 0.78 vs target 0.80 +0.98
   - valence 0.62 vs target 0.80 +0.82
   - tempo 94 vs target 120 BPM +0.77
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

- **Genre worth more than mood.** In the final points system, genre is worth 2 and mood 1. For the pop/happy profile, Gym Hero (pop, intense) scores 4.73 and ranks above Rooftop Lights (indie pop, happy) at 3.91. In an earlier version where mood counted more than genre (mood 0.30, genre 0.10), the order was the other way round, and the happy song won. Which one is better depends on whether a genre label or a mood matters more to the listener.
- **Three different users.** With the 18-song catalog, a High-Energy Pop profile gets Sunrise City first, a Chill Lo-fi profile (energy 0.38, valence 0.58, 76 BPM) gets Midnight Coding, Library Rain and Focus Flow on top, and a Deep Intense Rock profile (energy 0.92, valence 0.35, 150 BPM) gets Storm Runner first. The lofi list shares no songs with the other two, so the profile can tell these tastes apart.
- **Genre is too strict.** For the Deep Intense Rock profile, the metal song Iron Tide (the closest match in sound) only ranks 3rd, behind Gym Hero (pop), because "metal" does not equal "rock" and "angry" does not equal "intense".
- **Two weight experiments.** Doubling the energy weight and halving the genre weight did not change the #1 song for any profile. Removing mood matching improved the rock list but made the pop list worse. Full results are in Section 7 of the [model card](model_card.md), and you can reproduce them with `python scripts/evaluate.py`.
- Not yet tried: adding danceability and acousticness to the score.

---

## Limitations and Risks

- It only works on a small catalog of 18 songs. Lofi has 3 songs, pop has 2, and every other genre has only one, so a user who likes jazz can match only one song.
- Genre is an exact text match, so "pop" and "indie pop" count as different even though Sunrise City and Rooftop Lights sound almost the same.
- It uses no listening history, so it cannot learn from likes or skips, and it has no collaborative filtering.
- Sad, low-energy taste is covered by only two songs (Quiet Hours and Rainy Window Blues).
- A profile is a single point, so a listener with two very different tastes (say lofi and metal) cannot be described.
- Danceability and acousticness are not used in the score.
- It does not understand lyrics or language, and the results can show the same artist twice.

More detail on biases and evaluation is in the [model card](model_card.md).

---

## Reflection

[**Model Card**](model_card.md) (full reflection in Section 9)

**How recommenders turn data into predictions.** My recommender turns each song's features and a typed-in listener profile into a score, then sorts the songs by that score. Even this small version produced believable lists, such as a sensible lofi top 3, because "closer to what you asked for" is a useful rule. But the weights are opinions, not facts. Making genre worth 2 points and mood 1 put Gym Hero (pop, intense) above Rooftop Lights (indie pop, happy) for a pop/happy listener, and one mood point was enough to put a bright pop song in a rock listener's top 5. Running different profiles and experiments showed me that every rule helps some listeners and hurts others.

**Where bias or unfairness can show up.** The score gives genre an exact-match 2 of 6 points, and genre and mood labels together can outweigh how a song actually sounds. The catalog is small and uneven: a lofi fan has 3 songs to match, a rock or jazz fan has 1, and a genre that is missing earns nothing. Valence, the feature that separates bright songs from dark ones, varies the least across songs, so it has the weakest say. The song numbers and moods are hand-made, so the results also reflect one person's judgment. Larger systems can show the same pattern when some tastes have far more data than others.



