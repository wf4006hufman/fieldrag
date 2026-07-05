-- Run once per database (local and Cloud SQL).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,
    chunk_index  INT  NOT NULL,
    content      TEXT NOT NULL,
    embedding    VECTOR(768)
);

-- Approximate-NN index for cosine distance.
-- ivfflat needs data before building; the guide builds it AFTER ingest.
-- CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
