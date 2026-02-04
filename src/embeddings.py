import logging
import numpy as np
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger("idea_gen")


def get_embeddings(
    texts: list[str],
    client: OpenAI,
    model: str = "openai/text-embedding-3-small",
    fallback: str = "tfidf",
) -> np.ndarray:
    """Get embeddings for texts. Primary: OpenRouter API. Fallback: TF-IDF.

    Args:
        texts: List of text strings to embed
        client: OpenAI client configured for OpenRouter
        model: Embedding model name on OpenRouter
        fallback: Fallback method ("tfidf")

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    try:
        return _get_openrouter_embeddings(texts, client, model)
    except Exception as e:
        logger.warning("OpenRouter embedding failed: %s. Falling back to TF-IDF.", e)
        if fallback == "tfidf":
            return _get_tfidf_embeddings(texts)
        raise


def _get_openrouter_embeddings(
    texts: list[str],
    client: OpenAI,
    model: str,
) -> np.ndarray:
    """Get embeddings via OpenRouter API."""
    response = client.embeddings.create(model=model, input=texts)
    embeddings = [item.embedding for item in response.data]
    return np.array(embeddings)


def _get_tfidf_embeddings(texts: list[str]) -> np.ndarray:
    """Get TF-IDF embeddings as fallback."""
    vectorizer = TfidfVectorizer(max_features=512)
    matrix = vectorizer.fit_transform(texts)
    return matrix.toarray()
