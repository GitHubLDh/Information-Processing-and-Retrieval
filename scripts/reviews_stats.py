"""
Descriptive statistics on the cleaned reviews, for the report's Characterization
section (M1, 25% of the grade).

Computes:
  - reviews per movie (mean/median/min/max), including movies with zero reviews
  - review length in words (mean/median/min/max)
  - correlation between a movie's average review length and its rating
  - most frequent words across all reviews (stopwords removed), overall and per genre

Usage: python3 scripts/reviews_stats.py
"""

import csv
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"

STOPWORDS = {
    # articles, conjunctions, prepositions
    "the", "a", "an", "and", "or", "but", "nor", "to", "of", "in", "on", "for",
    "with", "as", "at", "by", "from", "about", "into", "onto", "out", "up", "down",
    "over", "under", "between", "through", "during", "before", "after", "above",
    "below", "off", "against", "while", "since", "because", "though", "although",
    "unless", "until", "whether",
    # pronouns
    "it", "its", "it's", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "his", "her", "hers", "their", "theirs", "our", "ours", "your",
    "yours", "my", "mine", "me", "him", "them", "us", "who", "whom", "whose",
    "which", "what", "whoever", "whatever", "someone", "somebody", "something",
    "anyone", "anybody", "anything", "everyone", "everybody", "everything", "none",
    # auxiliary / modal verbs + contractions
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did",
    "doing", "done", "have", "has", "had", "having", "will", "would", "can",
    "could", "should", "shall", "may", "might", "must", "don't", "doesn't",
    "didn't", "isn't", "wasn't", "weren't", "aren't", "won't", "can't", "couldn't",
    "wouldn't", "shouldn't", "that's", "there's", "here's", "what's", "who's",
    "they're", "you're", "we're", "i'm", "he's", "she's", "i've", "we've",
    "they've", "you've", "i'd", "you'd", "he'd", "she'd", "we'd", "they'd", "i'll",
    "you'll", "he'll", "she'll", "we'll", "they'll",
    # generic adverbs / intensifiers / discourse filler
    "not", "no", "so", "if", "than", "then", "there", "here", "just", "all",
    "some", "any", "one", "two", "three", "also", "very", "more", "most", "much",
    "many", "few", "less", "least", "too", "only", "even", "still", "yet",
    "already", "again", "further", "really", "actually", "basically", "quite",
    "rather", "pretty", "somewhat", "almost", "always", "never", "sometimes",
    "often", "ever", "once", "now", "well", "like", "way", "ways", "thing",
    "things", "lot", "lots", "bit", "kind", "sort", "first", "last", "how", "why",
    "when", "where",
    # generic verbs that carry little content on their own
    "get", "gets", "got", "getting", "go", "goes", "going", "went", "gone", "come",
    "comes", "coming", "came", "make", "makes", "made", "making", "see", "sees",
    "seeing", "saw", "seen", "know", "knows", "knew", "known", "think", "thinks",
    "thought", "want", "wants", "wanted", "say", "says", "said", "saying", "take",
    "takes", "took", "taken", "taking", "give", "gives", "gave", "given", "giving",
    "find", "finds", "found", "finding", "put", "puts", "putting", "let", "lets",
    "need", "needs", "needed",
    # domain-generic (true of every review regardless of content)
    "film", "films", "movie", "movies",
}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tokenize(text):
    """Lowercase, split into words, drop stopwords and very short tokens."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def reviews_per_movie_stats(movies, reviews):
    """How many reviews does a typical movie have, including movies with none?"""
    counts_by_movie = Counter(r["movie_id"] for r in reviews)
    counts = [counts_by_movie.get(m["movie_id"], 0) for m in movies]
    return {
        "mean": statistics.mean(counts),
        "median": statistics.median(counts),
        "min": min(counts),
        "max": max(counts),
        "zero_review_movies": sum(1 for c in counts if c == 0),
        "total_movies": len(movies),
    }


def review_length_stats(reviews):
    """How long is a typical review, in words?"""
    lengths = [len(r["content"].split()) for r in reviews]
    return {
        "mean": statistics.mean(lengths),
        "median": statistics.median(lengths),
        "min": min(lengths),
        "max": max(lengths),
    }


def length_vs_rating_correlation(movies, reviews):
    """Do movies with longer average reviews tend to be rated higher or lower?"""
    lengths_by_movie = defaultdict(list)
    for r in reviews:
        lengths_by_movie[r["movie_id"]].append(len(r["content"].split()))

    avg_lengths, ratings = [], []
    for m in movies:
        movie_review_lengths = lengths_by_movie.get(m["movie_id"])
        if not movie_review_lengths:
            continue
        try:
            rating = float(m["vote_average"])
        except (TypeError, ValueError):
            continue
        avg_lengths.append(statistics.mean(movie_review_lengths))
        ratings.append(rating)

    return {
        "pearson_r": statistics.correlation(avg_lengths, ratings),
        "movies_used": len(avg_lengths),
    }


def frequent_words(reviews, top_n=25):
    """Most common meaningful words across every review."""
    counter = Counter()
    for r in reviews:
        counter.update(tokenize(r["content"]))
    return counter.most_common(top_n)


def frequent_words_by_genre(movies, reviews, top_n=15):
    """Same as frequent_words, but split per genre."""
    genres_by_movie = {m["movie_id"]: m["genres"].split(",") for m in movies if m["genres"]}
    reviews_by_movie = defaultdict(list)
    for r in reviews:
        reviews_by_movie[r["movie_id"]].append(r)

    counters_by_genre = defaultdict(Counter)
    for movie_id, genres in genres_by_movie.items():
        tokens = []
        for r in reviews_by_movie.get(movie_id, []):
            tokens.extend(tokenize(r["content"]))
        for genre in genres:
            counters_by_genre[genre].update(tokens)

    return {genre: counter.most_common(top_n) for genre, counter in counters_by_genre.items()}


def main():
    movies = read_csv(INTERIM_DIR / "movies_clean.csv")
    reviews = read_csv(INTERIM_DIR / "reviews_clean.csv")

    per_movie = reviews_per_movie_stats(movies, reviews)
    length = review_length_stats(reviews)
    correlation = length_vs_rating_correlation(movies, reviews)
    top_words = frequent_words(reviews)
    by_genre = frequent_words_by_genre(movies, reviews)

    print("=== Reviews per movie ===")
    print(f"mean={per_movie['mean']:.2f}  median={per_movie['median']}  "
          f"min={per_movie['min']}  max={per_movie['max']}")
    print(f"movies with zero reviews: {per_movie['zero_review_movies']} / {per_movie['total_movies']}")

    print("\n=== Review length (words) ===")
    print(f"mean={length['mean']:.1f}  median={length['median']}  "
          f"min={length['min']}  max={length['max']}")

    print("\n=== Review length vs. rating ===")
    print(f"Pearson r = {correlation['pearson_r']:.3f}  (n={correlation['movies_used']} movies)")

    print("\n=== Top 25 words across all reviews ===")
    for word, count in top_words:
        print(f"  {word}: {count}")

    print("\n=== Top 10 words for the 5 most-reviewed genres ===")
    genre_review_counts = Counter()
    genres_by_movie = {m["movie_id"]: m["genres"].split(",") for m in movies if m["genres"]}
    reviews_by_movie = Counter(r["movie_id"] for r in reviews)
    for movie_id, genres in genres_by_movie.items():
        for genre in genres:
            genre_review_counts[genre] += reviews_by_movie.get(movie_id, 0)

    for genre, _ in genre_review_counts.most_common(5):
        words = ", ".join(w for w, _ in by_genre[genre][:10])
        print(f"  {genre}: {words}")


if __name__ == "__main__":
    main()
