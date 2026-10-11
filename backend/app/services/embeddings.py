from google.genai import types

from app.core.config import get_settings
from app.core.gcp import gemini

EMBED_DIM = 768  # must match the Firestore vector index (infra/gcp-bootstrap.sh)
_BATCH = 25


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """task_type: RETRIEVAL_DOCUMENT for clauses, RETRIEVAL_QUERY for user questions."""
    model = get_settings().embedding_model
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH):
        result = gemini().models.embed_content(
            model=model,
            contents=texts[i:i + _BATCH],
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIM),
        )
        vectors.extend(e.values for e in result.embeddings)
    return vectors
