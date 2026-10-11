#!/usr/bin/env bash
# One-time GCP setup for CareNest. Run in Cloud Shell:  bash infra/gcp-bootstrap.sh
set -euo pipefail

PROJECT="project-796a7c44-1092-4e43-ba6"
BUCKET="gs://${PROJECT}-docs"
SA_NAME="ppm-runner"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT"
PROJECT_NUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"

echo "==> Runtime service account for Cloud Run"
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name="CareNest Cloud Run runtime"
fi

for ROLE in roles/aiplatform.user roles/documentai.apiUser roles/datastore.user roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${SA_EMAIL}" --role="$ROLE" --condition=None >/dev/null
  echo "   granted $ROLE"
done

gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectAdmin" >/dev/null
echo "   granted roles/storage.objectAdmin on $BUCKET"

echo "==> Let the default compute account build source deploys"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role="roles/run.builder" --condition=None >/dev/null

echo "==> Firestore vector index for clause search (768-dim, text-embedding-005)"
gcloud firestore indexes composite create \
  --collection-group=clauses \
  --query-scope=COLLECTION \
  --field-config='field-path=embedding,vector-config={"dimension":"768","flat":"{}"}' \
  --database="(default)" || echo "   (index may already exist)"

echo "==> Demo bucket folders: keep deleted files 0 days to avoid soft-delete storage cost"
gcloud storage buckets update "$BUCKET" --clear-soft-delete

echo
echo "Bootstrap done. Still to do in the console:"
echo "  - Billing > Budgets & alerts: create a \$25 budget with 50/90/100% alerts"
echo "  - After the first deploy: Artifact Registry > cloud-run-source-deploy > cleanup policy (keep 2 most recent)"
