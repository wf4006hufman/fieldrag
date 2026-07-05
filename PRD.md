# PRD — FieldRAG: a grounded RAG + agent assistant for NGS field support

**Owner:** Woong-Jae Jung
**Goal of this document:** define *what* FieldRAG is and *why* it exists as a portfolio project, so the scope stays focused and the result is a coherent, self-contained demonstration.

---

## 1. Why this project exists

1. **A concrete, end-to-end demonstration of applied GenAI engineering.** FieldRAG shows a full grounded-RAG system working end to end on Google Cloud: a document-ingestion + embedding pipeline into a vector database, semantic retrieval, grounded generation with citations, a multi-step agent, an evaluation harness, and observability — all deployed live on GCP. It is meant to stand on its own as evidence that the pieces fit together, not as a toy chatbot.

2. **Domain-authentic, not generic.** Instead of a general-purpose assistant, FieldRAG answers questions grounded in **public NGS / bioinformatics documentation** (variant-calling guides, pipeline docs, tool manuals). Grounding the demo in a real technical domain makes retrieval quality and citation behavior meaningful, and mirrors the kind of internal-knowledge assistant a support/field team would actually build.

## 2. What it is (one sentence)

A web/API service where a field engineer asks a natural-language question and gets a **grounded, cited answer** synthesized by Gemini from a curated corpus of technical docs, retrieved via semantic search over a vector database — with an **agent mode** that can take multiple steps and use tools, and an **eval + observability layer** proving it actually works.

## 3. Users & top user stories

| User | Story |
|---|---|
| Field engineer (primary) | "I ask *'What QC metrics indicate sample contamination in a germline NGS run?'* and get a concise answer **with the source doc + section cited**, so I can trust and forward it." |
| Field engineer | "When a question needs two lookups (e.g. compare two tools), the **agent** does the multi-step retrieval instead of me re-asking." |
| Maintainer | "I run `eval.py` and see **retrieval hit-rate and groundedness scores**, so I know the system is accurate, not just plausible." |
| Operator | "I open Cloud Logging and see **per-request latency, retrieved doc IDs, and token usage** — real observability." |

## 4. Scope

### In scope
- **Ingestion pipeline**: load docs → chunk → embed → store in pgvector.
- **RAG query**: embed question → vector search top-k → Gemini grounded answer with citations.
- **Agent mode**: LangGraph ReAct agent with a `search_docs` tool + a `list_sources` tool.
- **Evaluation**: golden Q/A set → retrieval hit@k + LLM-judge groundedness score → printed report.
- **Observability**: structured JSON logs (latency, retrieved IDs, token usage) that surface in Cloud Logging.
- **Demo UI**: a polished single-page FastAPI HTML interface with English copy, RAG/Agent mode selection, source display, and retrieval diagnostics.
- **Deployment**: containerized FastAPI on **Cloud Run**, vector store on **Cloud SQL for PostgreSQL + pgvector**.
- **Optional**: expose `search_docs` as an **MCP server**.

### Out of scope (scope guardrails)
- Auth / multi-tenant / user accounts.
- A full product frontend, design system, dashboard suite, or React/Vite migration; the UI remains a single polished demo page served by FastAPI.
- Fine-tuning, re-ranking models, hybrid search, streaming responses.
- Ingesting proprietary/vendor-internal docs — **public sources only** (avoids IP issues; keeps it shareable on GitHub).
- Cost optimization, autoscaling tuning, CI/CD.

## 5. Success criteria (definition of done)

**Must-have:**
- [ ] `ingest.py` loads the public docs into pgvector; row count verified.
- [ ] Asking a question returns a grounded answer **with at least one correct citation**.
- [ ] Service is **live on a public Cloud Run URL** talking to Cloud SQL pgvector.
- [ ] `eval.py` prints retrieval hit@k and a groundedness score over ≥10 golden questions.
- [ ] Cloud Logging shows structured per-request logs with latency + retrieved doc IDs.
- [ ] The root web page gives a portfolio-ready demo view with answer, sources, mode, latency, and retrieved IDs.

**Nice-to-have:**
- [ ] LangGraph agent answers a 2-hop question correctly.
- [ ] MCP server exposes `search_docs`.
- [ ] Short `README.md` with an architecture diagram and the eval numbers.

## 6. What the finished project shows

A single, self-contained artifact that demonstrates, honestly and verifiably:

> **FieldRAG** — a Gemini-based RAG assistant on **GCP Cloud Run** over a **pgvector** vector database, with a **LangGraph** agent, an **LLM-judge evaluation harness** (retrieval hit-rate + groundedness), and **Cloud Logging** observability.

Every component in that description is implemented in this repo and runs on the live deployment linked from the README.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Cloud SQL networking complexity | Use Cloud Run's built-in `--add-cloudsql-instances` (Unix socket) — no VPC/proxy setup. Fallback: keep pgvector in a local Docker Postgres and still deploy the *app* to Cloud Run pointing at it later. |
| GCP billing | Use `gemini-2.5-pro` through Gemini Developer API / visitor BYOK for the free-tier demo path, keep Cloud SQL on the smallest tier, and **delete resources** when done (teardown section in guide). |
| Model IDs drift | Guide centralizes model IDs in `app/config.py`; verify against Model Garden if a call 404s. |
| Scope creep | A working RAG path *locally* comes first. Everything else is layered on only once that is green. |
