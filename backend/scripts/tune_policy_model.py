"""Validate synthetic policy splits, estimate cost, and optionally submit one tuning job."""
import argparse
import hashlib
import json
from pathlib import Path

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.gcp import bucket, gemini

BASE_MODEL = "gemini-3.1-flash-lite"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    client = genai.Client(vertexai=True, project=settings.project_id, location=args.region,
                          http_options=types.HttpOptions(api_version="v1", timeout=180000))
    saved_job = args.dataset / "tuning-job.json"
    if saved_job.exists():
        previous = json.loads(saved_job.read_text())
        job = client.tunings.get(name=previous["name"])
        saved_job.write_text(job.model_dump_json(indent=2))
        print(job.name, job.state)
        return
    records = [json.loads(line) for line in (args.dataset / "annotations.jsonl").read_text().splitlines()]
    policies = {split: {r["policyId"] for r in records if r["split"] == split}
                for split in ("train", "validation", "test")}
    if any(policies[a] & policies[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        raise ValueError("Policy leakage between splits")
    for record in records:
        if record["reviewStatus"] != "machine_checked_not_human_reviewed":
            raise ValueError("Unverified draft present")
    data = {}
    for split in ("train", "validation", "test"):
        data[split] = [json.loads(line) for line in (args.dataset / f"{split}.jsonl").read_text().splitlines()]
        if len(data[split]) != sum(r["split"] == split for r in records):
            raise ValueError("Export count mismatch")
        for row in data[split]:
            if [c["role"] for c in row["contents"]] != ["user", "model"]:
                raise ValueError("Invalid conversation roles")
            if not all(c["parts"][0].get("text") for c in row["contents"]):
                raise ValueError("Empty training content")
    if len(data["train"]) < 100 or not data["validation"] or not data["test"]:
        raise ValueError("Need at least 100 training examples and separate validation/test records")
    # Counting serialized records intentionally includes JSON overhead, giving a conservative estimate.
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in data["train"])
    token_count = sum(gemini().models.count_tokens(model=BASE_MODEL, contents="\n".join(json.dumps(r, ensure_ascii=False) for r in data["train"][i:i+10])).total_tokens for i in range(0, len(data["train"]), 10))
    estimate = token_count * 0.003 / 1000  # Current standard SFT USD rate, one epoch.
    estimate_report = {"baseModel": BASE_MODEL, "region": args.region, "epochCount": 1,
                       "counts": {k: len(v) for k, v in data.items()}, "countedTokensWithJsonOverhead": token_count,
                       "estimatedTrainingUsd": round(estimate, 4), "trainingCostCeilingUsd": 5,
                       "labelSource": "synthetic; machine checked; not human reviewed",
                       "excludes": ["draft generation", "evaluation", "storage", "tax", "other project usage"],
                       "pricingSource": "https://cloud.google.com/vertex-ai/generative-ai/pricing"}
    (args.dataset / "training-estimate.json").write_text(json.dumps(estimate_report, indent=2))
    print(json.dumps(estimate_report, indent=2), flush=True)
    if estimate > 5:
        raise ValueError("Estimated training cost exceeds the $5 ceiling")
    if not args.submit:
        return
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    uris = {}
    for split in ("train", "validation"):
        name = f"training/tuning/{digest}/{split}.jsonl"
        bucket().blob(name).upload_from_filename(str(args.dataset / f"{split}.jsonl"), content_type="application/jsonl")
        uris[split] = f"gs://{settings.gcs_bucket}/{name}"
    job = client.tunings.tune(
        base_model=BASE_MODEL, training_dataset=types.TuningDataset(gcs_uri=uris["train"]),
        config=types.CreateTuningJobConfig(tuned_model_display_name=f"carenest-policy-evidence-{digest}",
                                          epoch_count=1, export_last_checkpoint_only=True,
                                          validation_dataset=types.TuningValidationDataset(gcs_uri=uris["validation"])))
    saved_job.write_text(job.model_dump_json(indent=2))
    print(job.name, job.state, flush=True)


if __name__ == "__main__":
    main()
