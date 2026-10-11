import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Local dev reads backend/.env; on Cloud Run the values come from --set-env-vars.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    project_id: str
    gcs_bucket: str
    docai_location: str
    docai_processor_id: str
    firestore_db: str
    gemini_location: str
    gemini_model: str
    embedding_model: str
    max_policy_pages: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        project_id=os.environ["GCP_PROJECT_ID"],
        gcs_bucket=os.environ["GCS_BUCKET"],
        docai_location=os.environ.get("DOCAI_LOCATION", "asia-south1"),
        docai_processor_id=os.environ["DOCAI_PROCESSOR_ID"],
        firestore_db=os.environ.get("FIRESTORE_DB", "(default)"),
        gemini_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "text-embedding-005"),
        max_policy_pages=int(os.environ.get("MAX_POLICY_PAGES", "100")),
    )
