#!/usr/bin/env bash
# Rebuilds the whole Google Cloud side of the project, idempotently.
#
# This exists because a README paragraph is not reproducible. It was first
# written under BigQuery sandbox mode, which expired every table 60 days after 
# creation; the project now carries a billing account and that pressure is 
# gone, but rebuilding the cloud side from one command is worth having on its
# own - and the IAM assertion at the end is the only machine-checked statement
# of the security invariant.
#
# Prerequisites:
#   - gcloud authenticated: `gcloud auth login`
#     and `gcloud auth application-default login`
#   - data/raw/activities.json present (`uv run scripts/strava_fetch.py`)
#
# Usage: ./scripts/setup_gcp.sh

set -euo pipefail

PROJECT="trail-insight-agent"
DATASET="trail_insight"
LOCATION="EU"
SA_NAME="trail-agent"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
USER_EMAIL="$(gcloud config get-value account)"

step() { printf '\n==> %s\n' "$1"; }

step "Enabling the impersonation API"
gcloud services enable iamcredentials.googleapis.com --project="$PROJECT"

step "Dataset ${DATASET} in ${LOCATION}"
if bq --project_id="$PROJECT" show --dataset "${PROJECT}:${DATASET}" >/dev/null 2>&1; then
  echo "    already exists"
else
  bq --project_id="$PROJECT" --location="$LOCATION" mk --dataset \
     --description="Strava training history: raw landing zone + curated view" \
     "${PROJECT}:${DATASET}"
fi

step "Deriving the NDJSON payload and the BigQuery schema"
uv run scripts/build_bq_schema.py
uv run scripts/build_ndjson.py

step "Loading activities_raw (clustered, full replace)"
# Clustered, not partitioned: 3,301 rows over 15 years would give ~2,850
# partitions of ~170 bytes each, which costs more in metadata than it saves in
# scanning. Under sandbox mode there was a second, sharper reason - partition 
# expiry counted from the partition date, so the whole history would have been 
# deleted at creation. That one no longer applies.
bq --project_id="$PROJECT" load \
   --replace \
   --source_format=NEWLINE_DELIMITED_JSON \
   --clustering_fields=sport_type,start_date_local \
   "${PROJECT}:${DATASET}.activities_raw" \
   data/processed/activities.ndjson \
   schema/activities_raw.json

step "Creating the curated view"
bq --project_id="$PROJECT" query --nouse_legacy_sql < sql/v_activities.sql

step "Service account ${SA_NAME}"
if gcloud iam service-accounts describe "$SA" --project="$PROJECT" >/dev/null 2>&1; then
  echo "    already exists"
else
  gcloud iam service-accounts create "$SA_NAME" --project="$PROJECT" \
     --display-name="trail-insight-agent MCP server"
fi

step "Granting bigquery.jobUser at project scope (runs queries, reads no data)"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/bigquery.jobUser" \
  --condition=None >/dev/null

step "Granting bigquery.dataViewer on v_activities only"
# Deliberately NOT at project scope: the dataset's default access already
# contains specialGroup projectReaders, which would grant the raw table too.
bq --project_id="$PROJECT" add-iam-policy-binding \
   --member="serviceAccount:${SA}" \
   --role="roles/bigquery.dataViewer" \
   "${PROJECT}:${DATASET}.v_activities" >/dev/null

step "Declaring v_activities an authorized view"
# Without this, the view would read the underlying table with the CALLER's
# rights, so the service account would get a permission error instead of data.
tmp="$(mktemp)"
bq --project_id="$PROJECT" show --format=prettyjson "${PROJECT}:${DATASET}" > "$tmp"
python3 - "$tmp" "$PROJECT" "$DATASET" <<'PY'
import json, sys
path, project, dataset = sys.argv[1:4]
d = json.load(open(path))
entry = {"view": {"projectId": project, "datasetId": dataset,
                  "tableId": "v_activities"}}
access = d.setdefault("access", [])
if entry in access:
    print("    already authorized")
else:
    access.append(entry)
    json.dump(d, open(path, "w"), indent=2)
    print("    authorization added")
PY
bq --project_id="$PROJECT" update --source "$tmp" "${PROJECT}:${DATASET}"
rm -f "$tmp"

step "Letting ${USER_EMAIL} impersonate the service account"
# Impersonation, not a key file: no non-expiring private key on disk,
# and revoking access is removing a binding rather than hunting a file.
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --project="$PROJECT" \
  --member="user:${USER_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" >/dev/null

step "Asserting the security invariant"
# Tested at the IAM layer, agent removed: a green obtained through the agent
# cannot distinguish "IAM blocked it" from "the agent never tried".
TOKEN="$(gcloud auth print-access-token --impersonate-service-account="$SA")"
python3 - "$TOKEN" "$PROJECT" "$DATASET" "$LOCATION" <<'PY'
import json, sys, urllib.error, urllib.request

token, project, dataset, location = sys.argv[1:5]

def run(sql):
    body = json.dumps({"query": sql, "useLegacySql": False,
                       "location": location}).encode()
    req = urllib.request.Request(
        f"https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries",
        data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as exc:
        return json.load(exc)

view = run(f"SELECT COUNT(*) AS n FROM `{project}.{dataset}.v_activities`")
if "rows" not in view:
    sys.exit("    v_activities   : FAILED - "
             + view.get("error", {}).get("message", "")[:120])
print("    v_activities   :", view["rows"][0]["f"][0]["v"], "rows")

raw = run(f"SELECT id FROM `{project}.{dataset}.activities_raw` LIMIT 1")
if raw.get("error", {}).get("code") != 403:
    sys.exit("    activities_raw : READABLE - least privilege is broken")
print("    activities_raw : 403 denied, as expected")
PY

printf '\nDone. Smoke-test the agent with:\n'
printf '  toolbox --config mcp/tools.yaml invoke describe_dataset\n'
