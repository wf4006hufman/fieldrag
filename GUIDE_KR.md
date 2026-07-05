# 가이드 — FieldRAG 빌드 & 배포 (단계별)

각 단계마다 **명령어**와 **✅ 체크포인트**(이게 보이면 성공)가 있습니다. 체크포인트가 실패하면
거기서 멈추세요 — 다음으로 넘어가지 마세요. 소요 시간은 대략치입니다.

**개요**
- **Part 1 — 로컬에서 실행 (약 3–4시간):** 로컬에서 RAG를 끝까지 동작시키고 평가까지. 이것만으로도 핵심 산출물이 됩니다.
- **Part 2 — GCP 배포 (약 3–4시간):** Cloud Run + Cloud SQL. *그다음에* 선택 확장(에이전트/MCP).

사전 준비: 결제(billing)가 활성화된 GCP 프로젝트, `gcloud` CLI, `docker`, Python 3.12, (Day 1에서) `psql`은 선택.

---

## STEP 0 — GCP 프로젝트 + API 활성화 (15분, 제일 먼저)

```bash
gcloud auth login
gcloud auth application-default login          # 이 명령이 코드에 ADC 자격증명을 줍니다
gcloud config set project YOUR_PROJECT_ID

gcloud services enable aiplatform.googleapis.com \
  run.googleapis.com sqladmin.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com
```

✅ **체크포인트:** `gcloud services list --enabled | grep aiplatform` 이 한 줄을 출력.

---

## STEP 1 — 프로젝트 셋업 (10분)

```bash
cd "path/to/fieldrag"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` 편집: `GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID` 설정. DB 값은 docker 기본값 그대로 두고,
`INSTANCE_CONNECTION_NAME`은 주석 처리된 상태로 둡니다.

✅ **체크포인트:** `python -c "from app import config; print(config.GEN_MODEL, config.EMBED_DIM)"` 실행 시 `gemini-2.5-pro 768` 출력.

---

## STEP 2 — 로컬 벡터 DB 띄우기 (5분)

```bash
docker compose up -d
# 스키마 로드:
docker compose exec -T db psql -U fieldrag -d fieldrag < schema.sql
```

✅ **체크포인트:** `docker compose exec db psql -U fieldrag -d fieldrag -c "\dt"` 실행 시 `chunks` 테이블이 보임.

---

## STEP 3 — Gemini 연결 확인 (5분)

```bash
python -c "from app import gemini; print(gemini.embed(['hello'], is_query=True)[0][:3]); print(gemini.generate('Say OK')[0])"
```

✅ **체크포인트:** 실수(float) 3개와 짧은 텍스트 응답이 보임.
> 모델에서 **404**가 나면 Gemini API 문서나 Vertex **Model Garden**에서 현재 Gemini 모델 ID를 확인해 `.env`를 수정하세요.
> **403 / 권한** 오류면 `gcloud auth application-default login`을 다시 실행하세요.

---

## STEP 4 — 코퍼스 인제스트 (10분)  ← 첫 번째 실질 마일스톤

첫 실행이 바로 되도록 저장소에 샘플 문서 1개가 들어 있습니다.

```bash
python -m app.ingest
```

✅ **체크포인트:** 마지막에 `rows in chunks = N` (N ≥ 1). 방금 임베딩 파이프라인을 벡터 DB에 구축한 겁니다.

**그다음 실제 데이터로 만들기 (20분 투자할 가치 있음):** `corpus/`에 **공개(public)** 문서 15–30개를
`.md`/`.txt`(또는 PDF)로 넣고 다시 실행하세요.
추천 공개 출처:
- GATK Best Practices 문서, `samtools`/`bcftools` 매뉴얼, Nextflow 문서, nf-core 파이프라인 문서, Biostars FAQ 답변, Illumina *공개* 지원 페이지.
- 내부/독점 문서는 피하세요 — 이 저장소는 GitHub에 공개하는 것이 목적입니다.
문서를 추가한 뒤 `corpus/sample_ngs_qc.md`를 삭제하고, `python -m app.ingest`를 다시 실행하고,
`eval/golden.jsonl`을 *본인 문서*에 답이 있는 질문 8–12개로 갱신하세요.

---

## STEP 5 — ANN 인덱스 생성 (2분)

이제 데이터가 있으니 빠른 검색을 위한 인덱스를 만듭니다:
```bash
docker compose exec db psql -U fieldrag -d fieldrag \
  -c "CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
```
✅ **체크포인트:** 명령이 `CREATE INDEX` 반환.

---

## STEP 6 — 로컬에서 질문하기 (10분)  ← DAY-1 목표

```bash
uvicorn app.api:app --reload
```
http://localhost:8000 을 열고 *"What QC metric indicates possible sample contamination?"* 라고 질문.

✅ **체크포인트:** `[source]` 인용이 붙은 근거 기반 답변이 나오고, 터미널에 `latency_ms`와
`retrieved_ids`가 담긴 JSON 로그 한 줄이 출력됨. **이게 동작하는 RAG 시스템입니다.** Day 1은 사실상 완료.

---

## STEP 7 — 평가 실행 (10분)

```bash
python -m app.eval
```
✅ **체크포인트:** 질문별 HIT/MISS와 함께 `retrieval_hit@k`, `keyword_recall`, `groundedness_mean`이
담긴 SUMMARY가 출력되고 `eval/report.json`이 생성됨.
> hit-rate가 낮으면? 문서를 더/더 좋게 추가하거나, `TOP_K`를 올리거나, golden 질문을 코퍼스에 맞게 수정.
> 이 SUMMARY는 README용으로 스크린샷 찍어두세요.

**🎉 Part 1 끝.** 이제 벡터 DB 위에서 RAG 파이프라인 + 평가 하네스를 갖췄습니다.
Part 2는 이걸 *GCP에 배포된* 상태로 만듭니다.

---

## STEP 8 — Cloud SQL (pgvector) (25분)

```bash
REGION=asia-northeast3
gcloud sql instances create fieldrag-pg \
  --database-version=POSTGRES_16 \
  --edition=ENTERPRISE \
  --tier=db-f1-micro \
  --region=$REGION
```
> PostgreSQL 16 이상은 Cloud SQL Enterprise Plus가 기본값입니다. `db-f1-micro`는 shared-core Enterprise tier라서 이 가이드는 `--edition=ENTERPRISE`를 명시합니다.

```bash
gcloud sql databases create fieldrag --instance=fieldrag-pg
gcloud sql users set-password postgres --instance=fieldrag-pg --password=TEMP_ADMIN_PW
gcloud sql users create fieldrag --instance=fieldrag-pg --password=STRONG_PW

# 연결 이름(proj:region:instance) 얻기:
gcloud sql instances describe fieldrag-pg --format='value(connectionName)'
```

Cloud SQL Auth Proxy로 스키마 로드 + pgvector 활성화:
```bash
# ./cloud-sql-proxy 파일이 없으면 한 번 다운로드:
#   기본 예시는 Linux x86_64 기준입니다.
#   macOS 대안: cloud-sql-proxy.darwin.arm64 또는 cloud-sql-proxy.darwin.amd64
curl -L -o cloud-sql-proxy \
  https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.22.1/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

INSTANCE=$(gcloud sql instances describe fieldrag-pg --format='value(connectionName)')
./cloud-sql-proxy --port 5433 "$INSTANCE" &
PGPASSWORD=STRONG_PW psql -h 127.0.0.1 -p 5433 -U fieldrag -d fieldrag -f schema.sql
```
로컬 Docker Postgres가 `5432`를 쓰고 있을 수 있으므로, Cloud SQL proxy는 `5433`으로 엽니다.

✅ **체크포인트:** 프록시를 통해 `\dt` 하면 `chunks`가 보임.

---

## STEP 9 — Cloud SQL에 인제스트 (10분)

여전히 켜져 있는 프록시를 통해 로컬 인제스트를 Cloud SQL로 향하게 합니다:
```bash
DB_HOST=127.0.0.1 DB_PORT=5433 DB_USER=fieldrag DB_PASSWORD=STRONG_PW python -m app.ingest
# 그다음 인덱스 생성:
PGPASSWORD=STRONG_PW psql -h 127.0.0.1 -p 5433 -U fieldrag -d fieldrag \
  -c "CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);"
```
✅ **체크포인트:** Cloud SQL 대상으로 `rows in chunks = N`.

---

## STEP 10 — Cloud Run 배포 (20분)  ← GCP에 라이브

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
Secret Manager에 비밀번호를 쓸 때는 `echo`가 아니라 `printf`를 사용하세요. trailing newline이 secret 값에 포함되면 DB 인증이 실패합니다.
`REQUIRE_API_KEY_FOR_RAG=true`는 공개 데모의 RAG mode가 방문자 Gemini API key를 사용하도록 강제합니다. 이 경로가 Gemini Developer API를 통한 Gemini 2.5 Pro free-tier 사용 방식입니다. `roles/aiplatform.user`는 Agent mode 같은 서버 측 Vertex/Gemini 호출을 사용할 때만 필요합니다.

✅ **체크포인트:** 배포가 공개 URL을 출력. 열어서 질문 → 근거 기반 답변.
**이제 이건 GCP에 배포된 라이브 AI 서비스입니다.** URL이 동작하는 화면을 스크린샷.

> README에 메모: 실제 프로덕션에서는 `DB_PASSWORD`를 `--set-env-vars`가 아니라
> **Secret Manager**(`--set-secrets`)에 둬야 함.

---

## STEP 11 — 관측성(observability) 확인 (5분)

```bash
gcloud run services logs read fieldrag --region=$REGION --limit=20 | grep '"event"'
```
또는 콘솔에서: **Logging → Logs Explorer**, 필터 `jsonPayload.event="ask"`.
✅ **체크포인트:** `latency_ms`, `retrieved_ids`, 토큰 수가 담긴 구조화 로그가 보임.

---

## STEP 12 (선택 보너스) — LangGraph 에이전트

이미 연결돼 있음: POST `/ask` 에 `{"question":"...","agent":true}` (또는 페이지의 "agent mode" 체크).
*"Compare what low coverage vs high contamination each suggest."* 같은 2-hop 질문을 시도.
✅ **체크포인트:** 응답에 `"mode":"agent"`와 근거 기반 답변 — 동작하는 LangGraph ReAct 에이전트.

## STEP 13 (선택 보너스) — MCP 서버
```bash
python -m app.mcp_server
```
MCP 클라이언트(예: Claude Desktop 설정)에서 stdio로 연결. ✅ 이제 검색이 MCP 도구로 노출됩니다.

---

## STEP 14 — 공개(Publish) (20분)

1. `git init && git add . && git commit -m "FieldRAG: RAG+agent on GCP"` → **공개** GitHub 저장소에 푸시.
2. README에 넣기: 아키텍처 다이어그램, 평가 SUMMARY 수치, 라이브 Cloud Run URL.
3. 시크릿이 커밋되지 않았는지(`.env`는 gitignore) 확인하고, README의 데모 URL이 살아 있는지 확인.

---

## STEP 15 — 데모 오프라인 전환 (클라우드 비용 0)

Cloud Run은 스스로 0으로 스케일다운되지만, **Cloud SQL은 유휴 상태에서도 과금**됩니다. 따라서 진짜 $0에 도달하려면 데이터베이스를 삭제하거나 최소한 중지해야 합니다.

옵션 A — 완전 teardown (진짜 $0; 나중에 재생성):
```bash
REGION=asia-northeast3
gcloud run services delete fieldrag --region=$REGION -q     # stop serving
gcloud sql instances delete fieldrag-pg -q                  # delete DB → no idle billing
docker compose down -v                                      # (local) stop the dev DB too
```
옵션 B — 일시정지 (거의 $0, 빠른 복구를 위해 데이터 유지):
```bash
gcloud sql instances patch fieldrag-pg --activation-policy=NEVER   # stop DB compute; only small storage cost remains
# Cloud Run already idles at zero; optionally remove it too:
# gcloud run services delete fieldrag --region=asia-northeast3 -q
```
(GitHub 저장소는 남겨두세요 — 그게 지속되는 산출물입니다.)

---

## STEP 16 — 데모 다시 라이브로 되살리기

옵션 B(일시정지된 DB)에서:
```bash
gcloud sql instances patch fieldrag-pg --activation-policy=ALWAYS  # start the DB
# If you also deleted the Cloud Run service, redeploy it (see STEP 10). Otherwise it's already live.
```
옵션 A(완전 teardown)에서 — 인스턴스 재생성, 스키마 로드, 재인제스트, 재배포:
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
참고: 완전 teardown(옵션 A)은 인제스트된 데이터를 잃으므로, 복구하려면 위처럼 ingest를 다시 실행해야 합니다 — 옵션 B는 이를 피할 수 있습니다.

---

### 배포 단계에서 막히면
Part 2의 어떤 단계에서 막히면, **동작하는 로컬 버전을 산출물로 유지**하고 짧은 "배포 노트"
섹션을 추가하세요. 동작하는 로컬 RAG + 평가만으로도 그 자체로 완결된, 시연 가능한 결과이며,
배포는 그 위에 얹는 추가 계층입니다.
