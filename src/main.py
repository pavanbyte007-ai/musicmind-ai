"""
Command line runner for the Music Recommender Simulation.

Loads the song catalog, scores every song against a default user profile,
and prints the top recommendations with the reasons behind each score.

Run from the project root with: python -m src.main
"""

from src.recommender import load_songs, recommend_songs


def main() -> None:
    songs = load_songs("data/songs.csv")

    # Starter example profile
    user_prefs = {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "valence": 0.8,
        "tempo_bpm": 120,
    }

    k = 5
    recommendations = recommend_songs(user_prefs, songs, k=k)

    print(f"Loaded {len(songs)} songs.")
    print(
        f"User profile: genre={user_prefs['genre']}, mood={user_prefs['mood']}, "
        f"energy={user_prefs['energy']}, valence={user_prefs['valence']}, "
        f"tempo={user_prefs['tempo_bpm']} BPM"
    )
    print(f"\nTop {k} recommendations:\n")
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"{rank}. {song['title']} by {song['artist']}  (Score: {score:.2f})")
        for reason in explanation.split("; "):
            print(f"   - {reason}")
        print()


if __name__ == "__main__":
    main()
