#!/usr/bin/env bash
# Builds the monolith (Angular + FastAPI) in Cloud Build and deploys it to Cloud Run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PROJECT="project-796a7c44-1092-4e43-ba6"
REGION="asia-south1"
SERVICE="carenest"
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
# The scheduled job must not retain a digest that Artifact Registry later deletes.
# A moving protected tag retains exactly the image currently used for cleanup.
if gcloud run jobs describe carenest-guest-cleanup --project "$PROJECT" --region "$REGION" >/dev/null 2>&1; then
  REVISION="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.latestReadyRevisionName)')"
  IMAGE="$(gcloud run revisions describe "$REVISION" --project "$PROJECT" --region "$REGION" --format 'value(status.imageDigest)')"
  gcloud artifacts docker tags add "$IMAGE" "${IMAGE%@*}:runtime-cleanup" --project "$PROJECT" --quiet
  gcloud run jobs update carenest-guest-cleanup --project "$PROJECT" --region "$REGION" --image "$IMAGE"
fi
echo
echo "Deployed: $URL"
echo "Check: $URL/api/health  and  $URL/api/diag"
