"""Single-shot RAG: retrieve top-k chunks, answer grounded, with citations + logs."""
import hashlib
import json
import logging
import time

from . import config, db, gemini

log = logging.getLogger("fieldrag")

SYSTEM = (
    "You are a precise technical field-support assistant. "
    "Answer ONLY using the provided CONTEXT. "
    "Cite the source filename(s) you used inline like [source]. "
    "If the answer is not in the context, say you don't have that information. "
    "Be concise."
)


def retrieve(question: str, k: int | None = None, api_key: str | None = None):
    k = k or config.TOP_K
    qvec = gemini.embed([question], is_query=True, api_key=api_key)[0]
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, source, content, 1 - (embedding <=> %s::vector) AS score "
        "FROM chunks ORDER BY embedding <=> %s::vector LIMIT %s",
        (qvec, qvec, k),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "source": r[1], "content": r[2], "score": float(r[3])}
        for r in rows
    ]


def answer(question: str, k: int | None = None, api_key: str | None = None) -> dict:
    t0 = time.time()
    hits = retrieve(question, k, api_key=api_key)
    context = "\n\n".join(f"[{h['source']}]\n{h['content']}" for h in hits)
    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    text, usage = gemini.generate(prompt, system=SYSTEM, api_key=api_key)

    result = {
        "answer": text,
        "citations": sorted({h["source"] for h in hits}),
        "retrieved_ids": [h["id"] for h in hits],
        "latency_ms": int((time.time() - t0) * 1000),
        "auth_mode": "user_api_key" if api_key else "server",
    }
    log.info(json.dumps({
        "event": "ask",
        "mode": "rag",
        "q_hash": hashlib.sha1(question.encode()).hexdigest()[:8],
        "latency_ms": result["latency_ms"],
        "retrieved_ids": result["retrieved_ids"],
        "sources": result["citations"],
        **usage,
    }))
    return result
