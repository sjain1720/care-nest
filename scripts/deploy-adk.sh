#!/usr/bin/env bash
# Builds the monolith (Angular + FastAPI) in Cloud Build and deploys it to Cloud Run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PROJECT="project-796a7c44-1092-4e43-ba6"
REGION="asia-south1"
SERVICE="carenest-adk"
SA="ppm-runner@${PROJECT}.iam.gserviceaccount.com"

ENV_VARS="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${PROJECT}-docs,DOCAI_LOCATION=asia-south1,DOCAI_PROCESSOR_ID=771975839b0e4376,FIRESTORE_DB=(default),GEMINI_MODEL=gemini-3.1-flash-lite,EMBEDDING_MODEL=text-embedding-005,MAX_POLICY_PAGES=100,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=global"

cd "$ROOT"
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --source . \
  --region "$REGION" \
  --service-account "$SA" \
  --min-instances 0 \
  --max-instances 2 \
  --timeout 300 \
  --concurrency 8 \
  --memory 1Gi \
  --set-env-vars "$ENV_VARS" \
  --allow-unauthenticated

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
echo
echo "Deployed: $URL"
echo "Check: $URL/api/health  and  $URL/api/diag"
