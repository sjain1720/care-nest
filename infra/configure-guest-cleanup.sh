#!/usr/bin/env bash
# Deploy after the application image includes app.cleanup. Daily cleanup uses
# the existing runtime identity; invocation is restricted to this one job.
set -euo pipefail
PROJECT="project-796a7c44-1092-4e43-ba6"
REGION="asia-south1"
JOB="carenest-guest-cleanup"
SA="ppm-runner@${PROJECT}.iam.gserviceaccount.com"
REVISION="$(gcloud run services describe carenest --project "$PROJECT" --region "$REGION" --format 'value(status.latestReadyRevisionName)')"
IMAGE="$(gcloud run revisions describe "$REVISION" --project "$PROJECT" --region "$REGION" --format 'value(status.imageDigest)')"
gcloud artifacts docker tags add "$IMAGE" "${IMAGE%@*}:runtime-cleanup" --project "$PROJECT" --quiet
gcloud services enable cloudscheduler.googleapis.com --project "$PROJECT"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --service-account "$SA" --command python --args=-m,app.cleanup \
  --tasks 1 --max-retries 2 --task-timeout 600 --memory 512Mi \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${PROJECT}-docs,DOCAI_PROCESSOR_ID=771975839b0e4376"
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${SA}" --role roles/run.invoker
URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB" --project "$PROJECT" --location "$REGION" \
    --schedule '0 3 * * *' --time-zone Asia/Kolkata --uri "$URI" \
    --http-method POST --oauth-service-account-email "$SA"
else
  gcloud scheduler jobs create http "$JOB" --project "$PROJECT" --location "$REGION" \
    --schedule '0 3 * * *' --time-zone Asia/Kolkata --uri "$URI" \
    --http-method POST --oauth-service-account-email "$SA"
fi
