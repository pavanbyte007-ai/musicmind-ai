# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**Vibe Matcher 1.0**: a small, content-based music recommender that runs from the command line (`python -m src.main`).

---

## 2. Intended Use  

Vibe Matcher suggests the top 5 songs from an 18-song catalog for one listener at a time.

- **What it recommends:** songs whose genre, mood, energy, valence (how positive it sounds) and tempo are close to what the listener asked for.
- **Assumptions about the user:** they can name a favorite genre and mood and pick target energy, valence and tempo, and their taste is one fixed point (not a mix of different tastes).
- **Who it is for:** classroom exploration. It is a simulation to learn how recommenders work, not a tool for real listeners.

---

## 3. How the Model Works  

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

## 4. Data  

- **Size:** 18 songs. The original 10 were provided, and 8 were added to cover more styles.
- **Genres and moods:** 15 genres (pop, indie pop, lofi, rock, ambient, jazz, synthwave, hip hop, classical, metal, country, r&b, edm, reggae, blues) and 14 moods (for example happy, chill, intense, sad, romantic, angry).
- **Balance:** lofi has 3 songs, pop has 2, and every other genre has just 1.
- **What each song has:** title, artist, genre, mood, energy, tempo, valence, danceability and acousticness. The numbers are hand-written estimates, not measurements from real audio.
- **What is missing:** lyrics, language, artist popularity, release year, and anything about what real people listen to. Common styles such as Latin or K-pop are not represented, and sad, quiet music is covered by only two songs.

---

## 5. Strengths  

Where does your system seem to work well  

Prompts:  

- User types for which it gives reasonable results  
- Any patterns you think your scoring captures correctly  
- Cases where the recommendations matched your intuition  

---

## 6. Limitations and Bias 

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

## 7. Evaluation  

I tested three user profiles, three edge cases, and two experiments on the 18-song catalog. The two unit tests in `tests/test_recommender.py` pass. They only check that results come back sorted and that an explanation exists, so the profile results below were checked by running the recommender and reading the scores.

### Results for three profiles

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

### Interesting observations

- **Chill Lo-fi works best.** The catalog has 3 lofi and 3 chill songs, so the top 3 are all sensible. Midnight Coding and Library Rain are almost tied (5.92 vs 5.91). Coffee Shop Stories (jazz) shows up at #5 because its numbers are so close, which is a good cross-genre find.
- **Gym Hero keeps appearing where it may not belong.** It is a bright, upbeat pop song (valence 0.77). It ranks #2 for the pop fan because genre matches, which is reasonable. It also ranks #2 for the *rock* fan, who asked for something dark (valence 0.35), only because its mood is "intense" (+1 point).
- **The best sound match for the rock fan is only #3.** Iron Tide (metal, angry) has energy 0.97, valence 0.25 and 172 BPM, which is closest to a "deep, intense" sound. It ranks below Gym Hero because "metal" is not "rock" and "angry" is not "intense".
- **Scores fall off a cliff after #1 or #3.** The rock profile drops from 5.84 to 3.41, and the pop profile drops from 3.81 to 2.95. Only songs that match the labels score high, and everything else clusters between about 2 and 3.
- **Rock has only one song to match.** After Storm Runner, the rest of the list is chosen almost entirely by numbers.

### Edge cases

| Case | What happened |
|---|---|
| Genre not in the catalog ("k-pop") | No song can earn the 2 genre points, so the best possible score is 4. The results still look reasonable (Sunrise City 3.92, Rooftop Lights 3.91) because mood and numbers carry it. |
| Conflicting profile (lofi/chill but energy 0.95, valence 0.9, 170 BPM) | The top 3 are still the slow lofi songs (4.31, 4.22, 3.34), even though their energy is around 0.4. The genre and mood labels (up to 3 points) outweigh poor numeric fits. |
| Tempo above the catalog range (200 BPM) | It works. Tempo similarity is clamped at 0 so it never goes negative. Iron Tide wins with 5.75. |

### Experiments

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

## 8. Future Work  

Ideas for how you would improve the model next.  

Prompts:  

- Additional features or preferences  
- Better ways to explain recommendations  
- Improving diversity among the top results  
- Handling more complex user tastes  

---

## 9. Personal Reflection  

**What I learned.** A recommender is a short chain: data, then features, then a score, then a ranking, then an explanation. Even a tiny version forces real decisions about which features to use, how to compare them, and how much each one counts. The weights turned out to be opinions, not facts. Making genre worth 2 points and mood 1 decided whether Gym Hero or Rooftop Lights ranked second for the pop listener. Printing the "because" reasons for every song made the system much easier to understand and debug, because I could see exactly where each point came from.

**What surprised me.**
- A bright pop workout song, Gym Hero, showed up at #2 for a rock listener who wanted something dark, only because its mood label matched. The song that sounds most like what they asked for, Iron Tide, was #3.
- Removing the mood rule made the rock results better but the pop results worse, so one rule helped some listeners and hurt others.
- Doubling the energy weight did not change the #1 song for any profile, and it did not fix the Gym Hero problem. Valence was the feature that could, and it has the smallest spread across songs.
- The lo-fi listener got a jazz song (Coffee Shop Stories) at #5 just because its numbers were close, which felt like a real "discovery".

**Challenges.**
- The starter code had two designs side by side: song and profile objects (used by the tests) and plain dictionaries (used by the command-line runner). I kept one scoring function and made the object version reuse it.
- With only 18 songs and no real listeners, it was hard to tell whether a set of weights was "right". I could only check whether the results matched my own sense of how the songs sound.
- All the song numbers and mood labels are my own estimates, so the results can only be as good as those choices.

**What I would improve next.**
- Let similar labels count partly (pop and indie pop, chill and relaxed) instead of all or nothing.
- Give valence more say, and test danceability and acousticness, since tempo and energy partly repeat each other.
- Avoid showing the same artist twice and mix in some variety in the top results.
- Use a bigger catalog, allow profiles with more than one taste, and eventually learn from likes and skips instead of a typed-in profile.
- Add tests that check exact scores and ranking order.

**How this changed how I see music apps.** A "recommended for you" list is the result of choices someone made about what to measure and how much it matters. When an app suggests something odd, I now wonder which label or number pulled it in, and whose choices shaped that.
