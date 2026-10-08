from functools import lru_cache

from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_similarity_model():
    # Load once and reuse for later comparisons.
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def text_similarity(first_text: str, second_text: str) -> float:
    if not first_text.strip() or not second_text.strip():
        return 0.0

    model = get_similarity_model()

    embeddings = model.encode(
        [first_text, second_text],
        normalize_embeddings=True,
    )

    # For normalized vectors, the dot product is cosine similarity.
    score = float(embeddings[0] @ embeddings[1])

    return max(-1.0, min(1.0, score))