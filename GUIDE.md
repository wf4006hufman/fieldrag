# GUIDE — Build & deploy FieldRAG (step by step)

Every step has a **command** and a **✅ checkpoint** (what you should see). If a checkpoint
fails, stop there — don't move on. Times are rough.

**Overview**
- **Part 1 — run it locally (≈3–4 h):** local RAG working end-to-end + eval. This alone is the core artifact.
- **Part 2 — deploy to GCP (≈3–4 h):** Cloud Run + Cloud SQL. *Then* the optional agent/MCP extras.

Prereqs: a GCP project with **billing enabled**, `gcloud` CLI, `docker`, Python 3.12, and (Day 1) `psql` optional.

---

## STEP 0 — GCP project + APIs (15 min, do this first)

```bash
gcloud auth login
gcloud auth application-default login          # this gives your code ADC credentials
gcloud config set project YOUR_PROJECT_ID

gcloud services enable aiplatform.googleapis.com \
  run.googleapis.com sqladmin.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com
```

✅ **Checkpoint:** `gcloud services list --enabled | grep aiplatform` prints a line.

---

## STEP 1 — project setup (10 min)

```bash
cd "path/to/fieldrag"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`: set `GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID`. Leave DB values as the docker defaults, and leave `INSTANCE_CONNECTION_NAME` commented out.

✅ **Checkpoint:** `python -c "from app import config; print(config.GEN_MODEL, config.EMBED_DIM)"` prints `gemini-2.5-pro 768`.

---

## STEP 2 — local vector DB up (5 min)

```bash
docker compose up -d
# load schema:
docker compose exec -T db psql -U fieldrag -d fieldrag < schema.sql
```

✅ **Checkpoint:** `docker compose exec db psql -U fieldrag -d fieldrag -c "\dt"` lists the `chunks` table.

---

## STEP 3 — smoke-test Gemini (5 min)

```bash
python -c "from app import gemini; print(gemini.embed(['hello'], is_query=True)[0][:3]); print(gemini.generate('Say OK')[0])"
```

✅ **Checkpoint:** you see 3 floats and a short text reply.
> If you get a **404 on the model**, verify the current Gemini model IDs in the Gemini API docs or Vertex Model Garden and update `.env`.
> If you get **403 / permission**, re-run `gcloud auth application-default login`.

---

## STEP 4 — ingest the corpus (10 min)  ← FIRST REAL MILESTONE

The repo ships one placeholder doc so this runs immediately.

```bash
python -m app.ingest
```

✅ **Checkpoint:** ends with `rows in chunks = N` (N ≥ 1). You just built an embedding pipeline into a vector DB.

**Then make it real (worth 20 min):** drop 15–30 **public** docs into `corpus/` and re-run.
Good public sources (copy pages as `.md`/`.txt`, or PDFs):
- GATK Best Practices articles, `samtools`/`bcftools` manuals, Nextflow docs, nf-core pipeline docs, Biostars FAQ answers, Illumina *public* support pages.
- Avoid anything internal/proprietary — this repo is meant to be public on GitHub.
After adding docs, delete `corpus/sample_ngs_qc.md`, re-run `python -m app.ingest`, and update `eval/golden.jsonl` with 8–12 questions whose answers live in *your* docs.

---

## STEP 5 — build the ANN index (2 min)

Now that data exists, build the index for fast search:
```bash
docker compose exec db psql -U fieldrag -d fieldrag \
  -c "CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
```
✅ **Checkpoint:** command returns `CREATE INDEX`.

---

## STEP 6 — ask a question locally (10 min)  ← DAY-1 GOAL

```bash
uvicorn app.api:app --reload
```
Open http://localhost:8000 , ask *"What QC metric indicates possible sample contamination?"*

✅ **Checkpoint:** you get a grounded answer **with a `[source]` citation**, and the terminal prints a JSON log line with `latency_ms` and `retrieved_ids`. **That's a working RAG system.** Day 1 is essentially done.

---

## STEP 7 — run the evaluation (10 min)

```bash
python -m app.eval
```
✅ **Checkpoint:** prints per-question HIT/MISS + a SUMMARY with `retrieval_hit@k`, `keyword_recall`, `groundedness_mean`, and writes `eval/report.json`.
> Low hit-rate? Add more/better docs, raise `TOP_K`, or fix golden questions to match your corpus. Screenshot the SUMMARY for the README.

**🎉 End of Part 1.** You now have a RAG pipeline over a vector DB with an eval harness. Part 2 makes it *deployed on GCP*.

---

## STEP 8 — Cloud SQL (pgvector) (25 min)

```bash
REGION=asia-northeast3
gcloud sql instances create fieldrag-pg \
  --database-version=POSTGRES_16 \
  --edition=ENTERPRISE \
  --tier=db-f1-micro \
  --region=$REGION
```
> PostgreSQL 16+ defaults to Cloud SQL Enterprise Plus. `db-f1-micro` is a shared-core Enterprise tier, so this guide pins `--edition=ENTERPRISE`.

```bash
gcloud sql databases create fieldrag --instance=fieldrag-pg
gcloud sql users set-password postgres --instance=fieldrag-pg --password=TEMP_ADMIN_PW
gcloud sql users create fieldrag --instance=fieldrag-pg --password=STRONG_PW

# get the connection name (proj:region:instance):
gcloud sql instances describe fieldrag-pg --format='value(connectionName)'
```

Load schema + enable pgvector using the Cloud SQL Auth Proxy:
```bash
# download once if ./cloud-sql-proxy is not present:
#   default here is Linux x86_64.
#   macOS alternatives: cloud-sql-proxy.darwin.arm64 or cloud-sql-proxy.darwin.amd64
curl -L -o cloud-sql-proxy \
  https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.22.1/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

INSTANCE=$(gcloud sql instances describe fieldrag-pg --format='value(connectionName)')
./cloud-sql-proxy --port 5433 "$INSTANCE" &
PGPASSWORD=STRONG_PW psql -h 127.0.0.1 -p 5433 -U fieldrag -d fieldrag -f schema.sql
```
Use port `5433` to avoid colliding with the local Docker Postgres on `5432`.

✅ **Checkpoint:** `\dt` over the proxy shows `chunks`.

---

## STEP 9 — ingest into Cloud SQL (10 min)

Point your local ingest at Cloud SQL through the still-running proxy:
```bash
DB_HOST=127.0.0.1 DB_PORT=5433 DB_USER=fieldrag DB_PASSWORD=STRONG_PW python -m app.ingest
# then build the index:
PGPASSWORD=STRONG_PW psql -h 127.0.0.1 -p 5433 -U fieldrag -d fieldrag \
  -c "CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);"
```
✅ **Checkpoint:** `rows in chunks = N` against Cloud SQL.

---

## STEP 10 — deploy to Cloud Run (20 min)  ← LIVE ON GCP

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
INSTANCE=$(gcloud sql instances describe fieldrag-pg --format='value(connectionName)')
DB_PASSWORD='REPLACE_WITH_A_REAL_STRONG_PASSWORD'

gcloud sql users set-password fieldrag --instance=fieldrag-pg --password="$DB_PASSWORD"
gcloud services enable secretmanager.googleapis.com
printf '%s' "$DB_PASSWORD" > /tmp/fieldrag-db-password
if gcloud secrets describe fieldrag-db-password >/dev/null 2>&1; then
  gcloud secrets versions add fieldrag-db-password --data-file=/tmp/fieldrag-db-password
else
  gcloud secrets create fieldrag-db-password --data-file=/tmp/fieldrag-db-password --replication-policy=automatic
fi
rm /tmp/fieldrag-db-password

SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/aiplatform.user"
gcloud secrets add-iam-policy-binding fieldrag-db-password \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"

gcloud run deploy fieldrag \
  --source . \
  --region=$REGION \
  --allow-unauthenticated \
  --add-cloudsql-instances=$INSTANCE \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true,GEN_MODEL=gemini-2.5-pro,EMBED_MODEL=gemini-embedding-001,EMBED_DIM=768,TOP_K=5,REQUIRE_API_KEY_FOR_RAG=true,DB_NAME=fieldrag,DB_USER=fieldrag,INSTANCE_CONNECTION_NAME=$INSTANCE \
  --set-secrets=DB_PASSWORD=fieldrag-db-password:latest
```
Use `printf`, not `echo`, when writing the password to Secret Manager so no trailing newline becomes part of the secret.
`REQUIRE_API_KEY_FOR_RAG=true` makes the public demo use visitor-supplied Gemini API keys for RAG mode. That is the free-tier path for Gemini 2.5 Pro through the Gemini Developer API. `roles/aiplatform.user` is only needed for server-side Vertex/Gemini calls such as Agent mode.

✅ **Checkpoint:** deploy prints a public URL. Open it, ask a question → grounded answer. **This is now a live AI service on GCP.** Screenshot the URL working.

> Note in README: for real prod, `DB_PASSWORD` belongs in **Secret Manager** (`--set-secrets`), not `--set-env-vars`.

---

## STEP 11 — confirm observability (5 min)

```bash
gcloud run services logs read fieldrag --region=$REGION --limit=20 | grep '"event"'
```
Or in console: **Logging → Logs Explorer**, filter `jsonPayload.event="ask"`.
✅ **Checkpoint:** you see structured lines with `latency_ms`, `retrieved_ids`, token counts.

---

## STEP 12 (optional bonus) — LangGraph agent

Already wired: POST `/ask` with `{"question":"...","agent":true}` (or tick "agent mode" on the page).
Try a 2-hop question like *"Compare what low coverage vs high contamination each suggest."*
✅ **Checkpoint:** response has `"mode":"agent"` and a grounded answer — a working LangGraph ReAct agent.

## STEP 13 (optional bonus) — MCP server
```bash
python -m app.mcp_server
```
Connect from an MCP client (e.g. Claude Desktop config) via stdio. ✅ Retrieval is now exposed as an MCP tool.

---

## STEP 14 — publish (20 min)

1. `git init && git add . && git commit -m "FieldRAG: RAG+agent on GCP"` → push to a **public** GitHub repo.
2. Put in README: the architecture diagram, the eval SUMMARY numbers, and the live Cloud Run URL.
3. Double-check no secrets are committed (`.env` is gitignored) and that the demo URL in the README is live.

---

## STEP 15 — Take the demo offline (zero cloud billing)

Cloud Run scales to zero on its own, but **Cloud SQL bills even while idle**, so reaching truly $0 means deleting (or at least stopping) the database.

Option A — full teardown (truly $0; you re-create later):
```bash
REGION=asia-northeast3
gcloud run services delete fieldrag --region=$REGION -q     # stop serving
gcloud sql instances delete fieldrag-pg -q                  # delete DB → no idle billing
docker compose down -v                                      # (local) stop the dev DB too
```
Option B — pause (near-$0, keeps data for a fast restore):
```bash
gcloud sql instances patch fieldrag-pg --activation-policy=NEVER   # stop DB compute; only small storage cost remains
# Cloud Run already idles at zero; optionally remove it too:
# gcloud run services delete fieldrag --region=asia-northeast3 -q
```
(Keep the GitHub repo — that's the durable artifact.)

---

## STEP 16 — Bring the demo back live

From Option B (paused DB):
```bash
gcloud sql instances patch fieldrag-pg --activation-policy=ALWAYS  # start the DB
# If you also deleted the Cloud Run service, redeploy it (see STEP 10). Otherwise it's already live.
```
From Option A (full teardown) — recreate the instance, load schema, re-ingest, redeploy:
```bash
REGION=asia-northeast3
# 1) recreate Cloud SQL + db + user  (see STEP 8 for details)
gcloud sql instances create fieldrag-pg --database-version=POSTGRES_16 --edition=ENTERPRISE --tier=db-f1-micro --region=$REGION
gcloud sql databases create fieldrag --instance=fieldrag-pg
gcloud sql users create fieldrag --instance=fieldrag-pg --password=STRONG_PW
# 2) load schema + ingest through the Cloud SQL proxy (see STEP 8–9)
INSTANCE=$(gcloud sql instances describe fieldrag-pg --format='value(connectionName)')
./cloud-sql-proxy --port 5433 "$INSTANCE" &
PGPASSWORD=STRONG_PW psql -h 127.0.0.1 -p 5433 -U fieldrag -d fieldrag -f schema.sql
DB_HOST=127.0.0.1 DB_PORT=5433 DB_USER=fieldrag DB_PASSWORD=STRONG_PW python -m app.ingest
PGPASSWORD=STRONG_PW psql -h 127.0.0.1 -p 5433 -U fieldrag -d fieldrag \
  -c "CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);"
# 3) redeploy Cloud Run (see STEP 10 for the full env-vars/secrets command)
```
Note: full teardown (Option A) loses the ingested data, so restore requires re-running ingest as above — Option B avoids this.

---

### If a deploy step blocks you
If any Part 2 step blocks you, **keep the working local version as the artifact** and add a short "deploy notes" section. A working local RAG + eval is a complete, demonstrable result on its own; the deployment is an added layer on top.
