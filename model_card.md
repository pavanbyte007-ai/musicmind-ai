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

---

## 7. Evaluation  

How you checked whether the recommender behaved as expected. 

Prompts:  

- Which user profiles you tested  
- What you looked for in the recommendations  
- What surprised you  
- Any simple tests or comparisons you ran  

No need for numeric metrics unless you created some.

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

A few sentences about your experience.  

Prompts:  

- What you learned about recommender systems  
- Something unexpected or interesting you discovered  
- How this changed the way you think about music recommendation apps  
