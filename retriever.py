"""Find the help desk articles most relevant to a question with TF-IDF and cosine similarity."""
import glob
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class Retriever:
    """Loads the articles once, then ranks their lines against each question."""
    def __init__(self, docs_dir="docs"):
        self.chunks = []  # (source, text) pairs, one per line of each article
        for path in sorted(glob.glob(os.path.join(docs_dir, "*.md"))):
            name = os.path.basename(path)
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.chunks.append((name, line))
        # TF-IDF turns each line into a vector of word weights. Rare words count for more than common ones.
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([text for _, text in self.chunks])

    def search(self, query, k=4, min_score=0.05):
        """Return up to k (source, text, score) results above a minimum similarity."""
        # Compare the question's vector with every line. A higher score means more shared wording.
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        # Take the k best lines, then drop any below min_score so weak matches are never cited.
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.chunks[i][0], self.chunks[i][1], round(float(scores[i]), 3))
                for i in ranked if scores[i] >= min_score]
