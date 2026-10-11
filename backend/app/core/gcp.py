from functools import lru_cache

from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.cloud import firestore, storage

from app.core.config import get_settings

# Clients are created on first use so the server can start even before credentials are set up.


@lru_cache
def gemini() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.project_id, location=s.gemini_location)


@lru_cache
def docai() -> documentai.DocumentProcessorServiceClient:
    s = get_settings()
    # A processor in asia-south1 is only reachable through its regional endpoint.
    return documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{s.docai_location}-documentai.googleapis.com")
    )


def docai_processor_name() -> str:
    s = get_settings()
    return docai().processor_path(s.project_id, s.docai_location, s.docai_processor_id)


@lru_cache
def db() -> firestore.Client:
    s = get_settings()
    return firestore.Client(project=s.project_id, database=s.firestore_db)


@lru_cache
def bucket() -> storage.Bucket:
    s = get_settings()
    return storage.Client(project=s.project_id).bucket(s.gcs_bucket)
