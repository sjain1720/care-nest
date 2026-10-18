from google.genai import types
from google.genai.errors import ClientError

from app.core.config import get_settings
from app.core.gcp import gemini

EMBED_DIM = 768  # must match the Firestore vector index (infra/gcp-bootstrap.sh)
MAX_BATCH_TEXTS = 50
_ESTIMATED_TOKEN_BUDGET = 19_000


def embedding_batches(texts: list[str]):
    """Pack whole passages; byte/3 is a conservative English token estimate, not a tokenizer.

    The API enforces the actual 20,000-token limit. Ingestion splits a rejected
    batch rather than shortening its passages or losing saved progress.
    """
    group, estimated_tokens = [], 0
    for text in texts:
        size = (len(text.encode('utf-8')) + 2) // 3
        if group and (len(group) >= MAX_BATCH_TEXTS or estimated_tokens + size > _ESTIMATED_TOKEN_BUDGET):
            yield group
            group, estimated_tokens = [], 0
        group.append(text)
        estimated_tokens += size
    if group:
        yield group


def is_token_limit_error(exc: ClientError) -> bool:
    return exc.code == 400 and 'token' in str(exc).lower()


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """task_type: RETRIEVAL_DOCUMENT for clauses, RETRIEVAL_QUERY for user questions."""
    model = get_settings().embedding_model
    vectors: list[list[float]] = []
    for group in embedding_batches(texts):
        result = gemini().models.embed_content(
            model=model,
            contents=group,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIM,
                                           auto_truncate=False),
        )
        if not result.embeddings or len(result.embeddings) != len(group):
            raise RuntimeError('Embedding API returned an incomplete result')
        vectors.extend(e.values for e in result.embeddings)
    return vectors
