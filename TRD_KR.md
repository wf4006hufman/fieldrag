# TRD — FieldRAG 기술 설계

`PRD_KR.md`의 짝 문서. *어떻게* 만드는지 정의한다. 모든 모델 ID와 설정값은 `app/config.py`에 모여
단일 진실 공급원(single source of truth)을 이룬다.

---

## 1. 아키텍처

```
                       ┌──────────────────────────────────────────┐
                       │                Cloud Run                  │
                       │        (FastAPI 컨테이너, 공개 URL)        │
   user ──HTTP──▶  /ask │  ┌────────────┐      ┌────────────────┐  │
                       │  │  rag.py     │      │  agent.py       │  │
                       │  │ (단발 RAG)  │      │ (LangGraph ReAct)│ │
                       │  └─────┬──────┘      └───────┬─────────┘  │
                       │        │  embed / generate    │           │
                       └────────┼──────────────────────┼───────────┘
                                │                      │
             ┌──────────────────▼──────┐   ┌───────────▼───────────────┐
             │  Vertex / Agent Platform │   │  Cloud SQL for PostgreSQL │
             │  Gemini (생성 + 임베딩)  │   │  + pgvector  (벡터 DB)    │
             └──────────────────────────┘   └───────────────────────────┘
                                │
                        Cloud Logging  ◀── 구조화 JSON 로그 (지연시간, 문서 ID, 토큰)
```

**런타임 둘, 코드 하나:**
- **로컬 개발**: FastAPI를 `localhost`에, Postgres+pgvector를 Docker(`docker-compose`)에, Gemini는 서버 측 `GEMINI_API_KEY` 또는 ADC로.
- **프로덕션**: FastAPI를 Cloud Run에, pgvector를 Cloud SQL(Unix 소켓)에, Gemini는 RAG mode의 visitor BYOK 또는 서버 측 자격증명으로.

브라우저 UI는 `GET /`에서 제공하고 같은 페이지가 `POST /ask`를 호출한다. 별도 프론트엔드 빌드 단계는 없다.

DB 계층은 환경변수 하나(`INSTANCE_CONNECTION_NAME`)로 전환된다. 나머지는 전부 동일.

## 2. 기술 스택 & 이유

| 관심사 | 선택 | 이유 |
|---|---|---|
| LLM + 임베딩 | **Gemini via Gen AI SDK (`google-genai`), Agent Platform / Vertex 백엔드** | 하나의 Google 네이티브 SDK로 생성과 임베딩을 모두 처리하고, 전 구간이 GCP에서 돈다. |
| 생성 모델 | `gemini-2.5-pro` | 고급 reasoning 모델. free-tier 사용은 서버 측 Vertex 과금이 아니라 Gemini Developer API / BYOK 경로 기준. |
| 임베딩 모델 | `gemini-embedding-001`, `output_dimensionality=768` | 768차원이 pgvector 인덱스를 작고 빠르게 유지. |
| 벡터 DB | **pgvector on Cloud SQL for PostgreSQL** | 관리형 GCP 네이티브 벡터 저장소; 코사인 검색을 순수 SQL로 처리해 별도 서비스가 필요 없음. |
| DB 드라이버 | `psycopg2-binary` + `pgvector.psycopg2` | 로컬·프로덕션 동일 드라이버(프로덕션은 Unix 소켓). |
| API | **FastAPI + uvicorn** | 비동기, `/docs` 자동 Swagger, 컨테이너화 간단. |
| 에이전트 | **LangGraph** `create_react_agent` + `langchain-google-vertexai` `ChatVertexAI` | 멀티 스텝 / ReAct 도구 사용 에이전트를 위한 표준 프레임워크. |
| 평가 | 커스텀 `eval.py` — hit@k + Gemini-as-judge | 결정론적 검색 지표와 LLM 기반 근거성 판정을 결합. |
| 관측성 | `logging` → stdout에 JSON (Cloud Run → Cloud Logging) | 구조화 로그가 별도 설정 없이 Cloud Logging에 그대로 수집됨. |
| 데모 UI | FastAPI가 제공하는 무의존성 HTML/CSS/JS | 배포를 단순하게 유지하면서 검색 근거를 브라우저에서 그대로 보이게 함. |
| 컨테이너 | `python:3.12-slim` + `Dockerfile` | 표준 Cloud Run 경로. |
| MCP (선택) | `mcp` (FastMCP)로 `search_docs` 래핑 | 검색을 어떤 MCP 클라이언트든 쓸 수 있는 재사용 도구로 노출. |

## 3. 데이터 모델

**테이블 `chunks`:**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | `bigserial PK` | 청크 id |
| `source` | `text` | 파일명 / 문서 제목 |
| `chunk_index` | `int` | 문서 내 순서 |
| `content` | `text` | 청크 본문 |
| `embedding` | `vector(768)` | pgvector 컬럼 |

인덱스: `ivfflat (embedding vector_cosine_ops)` (가능하면 `hnsw`) — 근사 최근접 검색. 코사인 거리(`<=>`).

## 4. 핵심 흐름

### 4.1 인제스트 (`ingest.py`)
1. `corpus/`에서 `.md` / `.txt` 탐색 (PDF는 `pypdf`로 선택 지원).
2. 청킹: 약 800자, 약 150자 오버랩, 문단 경계 기준.
3. `task_type="RETRIEVAL_DOCUMENT"`로 배치 임베딩.
4. `chunks`에 행 INSERT.
5. 멱등(idempotent): 시작 시 `TRUNCATE chunks` (작은 코퍼스, 가장 단순하고 올바른 동작).

### 4.2 RAG 쿼리 (`rag.py`)
1. `task_type="RETRIEVAL_QUERY"`로 질문 임베딩.
2. `SELECT ... ORDER BY embedding <=> %s LIMIT k` (k=5).
3. 근거 프롬프트 구성: 시스템 지시 = "컨텍스트에서만 답하라; `source`를 인용하라; 컨텍스트에 없으면 모른다고 하라."
4. `generate_content` → `{answer, citations:[source...], latency_ms, retrieved_ids}` 반환.
5. 구조화 레코드 로깅.

### 4.3 에이전트 (`agent.py`, 스트레치)
- 도구: `search_docs(query)->str` (4.2 검색 래핑), `list_sources()->list` (distinct source).
- `create_react_agent(llm, tools)`; 모델이 언제/몇 번 검색할지 스스로 결정.
- 다중 홉 질문("X와 Y 비교")에 사용.

### 4.4 평가 (`eval.py`)
- 입력: `eval/golden.jsonl` — `{question, expect_source, expect_keywords[]}`.
- **검색 hit@k**: `expect_source`가 검색된 청크의 source에 있는가? → hit rate.
- **Groundedness (LLM judge)**: Gemini가 답변이 검색 컨텍스트로 뒷받침되는지 1–5점. 평균 리포트.
- **키워드 재현율** (저비용 새너티): `expect_keywords` 중 답변에 등장한 비율.
- 출력: 표 + 집계 지표를 stdout(및 `eval/report.json`)에.

### 4.5 웹 UI (`api.py`)
- `GET /`는 `HOME_HTML`에 내장된 무의존성 단일 페이지 인터페이스를 제공한다.
- UI 문구는 영어만 사용하고, scientific workbench 스타일을 따른다: query console, optional personal Gemini API key, RAG/Agent segmented mode,
  top-k input, answer, sources, diagnostics, raw JSON.
- `{question, k, agent, api_key?}`로 `POST /ask`를 호출해 응답에 존재하는 필드를 렌더링한다.
- 클라이언트가 제공한 API key는 해당 요청의 query embedding과 generation에만 사용하고, 저장하지 않으며 구조화 로그에도 넣지 않는다.
- Agent 응답에는 citations나 retrieved IDs가 없을 수 있으므로, 해당 진단 정보는 graceful empty state로 표시한다.

## 5. 설정 & 시크릿

`app/config.py`가 env를 읽음:
```
GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global, GOOGLE_GENAI_USE_VERTEXAI=true
GEMINI_API_KEY                                  # 선택: 서버 측 Developer API key
GEN_MODEL=gemini-2.5-pro
EMBED_MODEL=gemini-embedding-001
EMBED_DIM=768
DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD      # 로컬
INSTANCE_CONNECTION_NAME=proj:region:instance            # 프로덕션 (Cloud SQL Unix 소켓)
TOP_K=5
REQUIRE_API_KEY_FOR_RAG=true                  # 공개 데모: free-tier RAG를 위해 visitor BYOK 강제
```
- **코드에 시크릿 금지.** 로컬: `.env`. 프로덕션: Secret Manager. `.env`는 절대 커밋하지 않음.
- 인증은 서버 측 자격증명(`GEMINI_API_KEY` 또는 Vertex ADC)과 RAG mode의 visitor BYOK를 지원한다. 공개 포트폴리오 배포는 `REQUIRE_API_KEY_FOR_RAG=true`를 설정해 방문자가 key를 제공할 때만 Gemini Developer API free-tier 경로로 Gemini 2.5 Pro를 사용한다. Cloud Run 서비스 계정은 Cloud SQL과 선택적 Vertex agent mode에 사용하며, Vertex 서버 호출을 쓸 때만 `roles/aiplatform.user`를 부여한다.

## 6. 배포 (Cloud Run + Cloud SQL)

- Cloud SQL: Cloud SQL Enterprise edition의 `db-f1-micro` Postgres 16, DB `fieldrag`, 사용자 `fieldrag`, `CREATE EXTENSION vector`.
- Cloud Run: `gcloud run deploy`에 `--add-cloudsql-instances INSTANCE`(`/cloudsql/INSTANCE`에 Unix 소켓
  마운트), env, `aiplatform.user` + `cloudsql.client` 가진 서비스 계정.
- 프로덕션 인제스트: `ingest.py`를 Cloud SQL 대상으로 로컬에서 한 번 실행(Cloud SQL Auth Proxy 경유)
  하거나 `/admin/ingest` 엔드포인트를 한 번 호출. 가이드는 프록시 방식 사용 — 더 깔끔.

## 7. 관측성 스펙

`/ask`마다 JSON 로그 한 줄:
```json
{"event":"ask","q_hash":"...","latency_ms":812,"retrieved_ids":[12,7,33],
 "sources":["gatk_qc.md"],"prompt_tokens":1450,"output_tokens":180,"mode":"rag"}
```
Cloud Run은 stdout을 Cloud Logging으로 자동 전송 → `jsonPayload.event="ask"`로 필터.
선택 스트레치: OpenTelemetry → Cloud Trace로 스팬(embed / search / generate).

## 8. 저장소 구조
```
fieldrag/
  PRD.md  TRD.md  GUIDE.md  README.md  (+ *_KR.md 한글판)
  requirements.txt  Dockerfile  docker-compose.yml  schema.sql  .env.example
  corpus/            # 넣는 공개 문서
  eval/golden.jsonl  # golden 질문 (코퍼스에 맞게 편집)
  app/
    config.py  db.py  gemini.py  ingest.py  rag.py  api.py  agent.py  eval.py  mcp_server.py
```

## 9. 빌드 순서 (GUIDE에 매핑)
1. 로컬 Postgres+pgvector 기동 → `schema.sql`.
2. `config.py`, `db.py`, `gemini.py` (클라이언트).
3. `ingest.py` → 행 수 검증. **← 첫 체크포인트**
4. `rag.py` + `api.py` → 로컬에서 질문. **← Day-1 완료**
5. `GET /` 단일 페이지 데모 UI를 스크린샷용으로 polish.
6. `eval.py` → 지표.
7. Cloud SQL + Cloud Run 배포 → 공개 URL. **← 라이브 배포**
8. `agent.py` (LangGraph), `mcp_server.py` — 선택 보너스.
