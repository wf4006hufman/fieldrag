# TRD — FieldRAG technical design

Companion to `PRD.md`. Defines *how* it's built. All model IDs and knobs live in `app/config.py` so there's a single source of truth.

---

## 1. Architecture

```
                       ┌──────────────────────────────────────────┐
                       │                Cloud Run                  │
                       │        (FastAPI container, public URL)    │
   user ──HTTP──▶  /ask │  ┌────────────┐      ┌────────────────┐  │
                       │  │  rag.py     │      │  agent.py       │  │
                       │  │ (1-shot RAG)│      │ (LangGraph ReAct)│ │
                       │  └─────┬──────┘      └───────┬─────────┘  │
                       │        │  embed / generate    │           │
                       └────────┼──────────────────────┼───────────┘
                                │                      │
             ┌──────────────────▼──────┐   ┌───────────▼───────────────┐
             │  Vertex / Agent Platform │   │  Cloud SQL for PostgreSQL │
             │  Gemini (gen + embed)    │   │  + pgvector  (vector DB)  │
             └──────────────────────────┘   └───────────────────────────┘
                                │
                        Cloud Logging  ◀── structured JSON logs (latency, doc IDs, tokens)
```

**Two runtimes, same code:**
- **Local dev**: FastAPI on `localhost`, Postgres+pgvector in Docker (`docker-compose`), Gemini via either a server-side `GEMINI_API_KEY` or ADC.
- **Prod**: FastAPI on Cloud Run, pgvector on Cloud SQL (Unix socket), Gemini via either visitor-supplied BYOK for RAG mode or server-side credentials.

The browser UI is served by `GET /` and calls `POST /ask`; no separate frontend build is required.

The DB layer switches on one env var (`INSTANCE_CONNECTION_NAME`); everything else is identical.

## 2. Tech stack & why

| Concern | Choice | Why |
|---|---|---|
| LLM + embeddings | **Gemini via Gen AI SDK (`google-genai`), Agent Platform / Vertex backend** | One Google-native SDK covers both generation and embeddings; runs on GCP end to end. |
| Gen model | `gemini-2.5-pro` | Advanced reasoning model. Free-tier use is through Gemini Developer API / BYOK, not server-side Vertex billing. |
| Embedding model | `gemini-embedding-001`, `output_dimensionality=768` | 768-dim keeps the pgvector index small/fast. |
| Vector DB | **pgvector on Cloud SQL for PostgreSQL** | Managed, GCP-native vector store; plain SQL for the cosine search, no extra service to run. |
| DB driver | `psycopg2-binary` + `pgvector.psycopg2` | Same driver local & prod (Unix socket in prod). |
| API | **FastAPI + uvicorn** | Async, auto Swagger at `/docs`, trivial to containerize. |
| Agent | **LangGraph** `create_react_agent` + `langchain-google-vertexai` `ChatVertexAI` | Standard framework for multi-step / ReAct tool-use agents. |
| Eval | Custom `eval.py` — hit@k + Gemini-as-judge | Combines a deterministic retrieval metric with an LLM-native groundedness judge. |
| Observability | `logging` → JSON to stdout (Cloud Run → Cloud Logging) | Structured logs are picked up by Cloud Logging with zero extra wiring. |
| Demo UI | Dependency-free HTML/CSS/JS served by FastAPI | Keeps deployment simple while making retrieval evidence visible in the browser. |
| Container | Distroless-ish `python:3.12-slim` + `Dockerfile` | Standard Cloud Run path. |
| MCP (optional) | `mcp` (FastMCP) wrapping `search_docs` | Exposes retrieval as a reusable tool for any MCP client. |

## 3. Data model

**Table `chunks`:**

| column | type | note |
|---|---|---|
| `id` | `bigserial PK` | chunk id |
| `source` | `text` | filename / doc title |
| `chunk_index` | `int` | order within doc |
| `content` | `text` | the chunk text |
| `embedding` | `vector(768)` | pgvector column |

Index: `ivfflat (embedding vector_cosine_ops)` (or `hnsw` if available) for approximate NN search. Cosine distance (`<=>`).

## 4. Core flows

### 4.1 Ingestion (`ingest.py`)
1. Walk `corpus/` for `.md` / `.txt` (PDFs optional via `pypdf`).
2. Chunk: ~800 chars, ~150 overlap, split on paragraph boundaries.
3. Batch-embed with `task_type="RETRIEVAL_DOCUMENT"`.
4. `INSERT` rows into `chunks`.
5. Idempotent: `TRUNCATE chunks` at start (small corpus, simplest correct behavior).

### 4.2 RAG query (`rag.py`)
1. Embed question with `task_type="RETRIEVAL_QUERY"`.
2. `SELECT ... ORDER BY embedding <=> %s LIMIT k` (k=5).
3. Build a grounded prompt: system instruction = "answer ONLY from context; cite `source`; if not in context, say you don't know."
4. `generate_content` → return `{answer, citations:[source...], latency_ms, retrieved_ids}`.
5. Log the structured record.

### 4.3 Agent (`agent.py`, stretch)
- Tools: `search_docs(query)->str` (wraps 4.2 retrieval), `list_sources()->list` (distinct sources).
- `create_react_agent(llm, tools)`; the model decides when/how many times to search.
- Used for multi-hop questions ("compare X and Y").

### 4.4 Eval (`eval.py`)
- Input: `eval/golden.jsonl` — `{question, expect_source, expect_keywords[]}`.
- **Retrieval hit@k**: is `expect_source` among retrieved chunks' sources? → hit rate.
- **Groundedness (LLM judge)**: Gemini scores 1–5 whether the answer is supported by retrieved context. Report mean.
- **Keyword recall** (cheap sanity): fraction of `expect_keywords` present in answer.
- Output: table + aggregate metrics to stdout (and `eval/report.json`).

### 4.5 Web UI (`api.py`)
- `GET /` serves a dependency-free single-page interface embedded as `HOME_HTML`.
- UI copy is English only and follows a scientific workbench style: query console, optional personal Gemini API key, RAG/Agent segmented mode, top-k input, answer, sources, diagnostics, and raw JSON.
- The page calls `POST /ask` with `{question, k, agent, api_key?}` and renders whichever fields are present.
- A client-supplied API key is used only for that request's query embedding and generation path; it is not stored and is not included in structured logs.
- Agent responses may not include citations or retrieved IDs, so the UI shows graceful empty states for those diagnostics.

## 5. Config & secrets

`app/config.py` reads env:
```
GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global, GOOGLE_GENAI_USE_VERTEXAI=true
GEMINI_API_KEY                                  # optional server-side Developer API key
GEN_MODEL=gemini-2.5-pro
EMBED_MODEL=gemini-embedding-001
EMBED_DIM=768
DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD      # local
INSTANCE_CONNECTION_NAME=proj:region:instance            # prod (Cloud SQL Unix socket)
TOP_K=5
REQUIRE_API_KEY_FOR_RAG=true                  # public demo: require visitor BYOK for free-tier RAG
```
- **No secrets in code.** Local: `.env`. Prod: Secret Manager. Never commit `.env`.
- Auth supports two paths: server-side credentials (`GEMINI_API_KEY` or Vertex ADC) and visitor BYOK for RAG mode. The public portfolio deployment sets `REQUIRE_API_KEY_FOR_RAG=true` so Gemini 2.5 Pro uses the Gemini Developer API free-tier path only when a visitor supplies a key. Cloud Run uses its service account for Cloud SQL and optional Vertex agent mode; grant `roles/aiplatform.user` only if using Vertex-backed server calls.

## 6. Deployment (Cloud Run + Cloud SQL)

- Cloud SQL: `db-f1-micro` Postgres 16 on Cloud SQL Enterprise edition, one DB `fieldrag`, user `fieldrag`, `CREATE EXTENSION vector`.
- Cloud Run: `gcloud run deploy` with `--add-cloudsql-instances INSTANCE` (mounts Unix socket at `/cloudsql/INSTANCE`), env vars, service account with `aiplatform.user` + `cloudsql.client`.
- Ingestion in prod: run `ingest.py` once locally **against Cloud SQL** (via the Cloud SQL Auth Proxy) OR add a `/admin/ingest` endpoint hit once. Guide uses the proxy — cleaner.

## 7. Observability spec

Every `/ask` emits one JSON log line:
```json
{"event":"ask","q_hash":"...","latency_ms":812,"retrieved_ids":[12,7,33],
 "sources":["gatk_qc.md"],"prompt_tokens":1450,"output_tokens":180,"mode":"rag"}
```
Cloud Run ships stdout to Cloud Logging automatically → filter by `jsonPayload.event="ask"`. Optional stretch: OpenTelemetry → Cloud Trace for spans (embed / search / generate).

## 8. Repo layout
```
fieldrag/
  PRD.md  TRD.md  GUIDE.md  README.md
  requirements.txt  Dockerfile  docker-compose.yml  schema.sql  .env.example
  corpus/            # public docs you drop in
  eval/golden.jsonl  # golden questions (edit to match your corpus)
  app/
    config.py  db.py  gemini.py  ingest.py  rag.py  api.py  agent.py  eval.py  mcp_server.py
```

## 9. Build order (maps to GUIDE.md)
1. Local Postgres+pgvector up → `schema.sql`.
2. `config.py`, `db.py`, `gemini.py` (clients).
3. `ingest.py` → verify row count. **← first checkpoint**
4. `rag.py` + `api.py` → ask a question locally. **← Day-1 done**
5. Polish the single-page `GET /` demo UI for screenshots.
6. `eval.py` → metrics.
7. Cloud SQL + Cloud Run deploy → public URL. **← live deployment**
8. `agent.py` (LangGraph), `mcp_server.py` — optional bonuses.
