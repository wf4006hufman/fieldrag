"""Ingest corpus/ into pgvector.

Incremental by default: files already present in the `chunks` table (matched by
filename) are skipped, so re-running only ingests newly added or previously
failed documents.

Usage:
  python -m app.ingest             # incremental: only new/missing files
  python -m app.ingest --force     # re-ingest everything (rebuild all)
  python -m app.ingest --only NAME # (re)ingest just one file by name
"""
import glob
import os
import sys
from . import db, gemini

CHUNK_CHARS = 800
OVERLAP = 150
BATCH = 32


def list_files(corpus_dir: str) -> list[tuple[str, str]]:
    """Return [(path, name)] for every ingestible file in corpus/."""
    files = []
    for path in sorted(glob.glob(os.path.join(corpus_dir, "**", "*"), recursive=True)):
        if os.path.isdir(path):
            continue
        if path.lower().endswith((".md", ".txt", ".pdf")):
            files.append((path, os.path.basename(path)))
    return files


def load_text(path: str, name: str) -> str | None:
    """Extract text from one file. Returns None if nothing usable could be read."""
    if path.lower().endswith((".md", ".txt")):
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    # PDF: read leniently and salvage per page so one bad page (or a partially
    # damaged file) doesn't discard the whole document.
    try:
        from pypdf import PdfReader
        reader = PdfReader(path, strict=False)
        pages = []
        for pg in reader.pages:
            try:
                pages.append(pg.extract_text() or "")
            except Exception:  # noqa
                continue  # skip only the unreadable page
        text = "\n".join(pages).strip()
        if not text:
            print(f"  skip {name}: no extractable text")
            return None
        return text
    except Exception as e:  # noqa  (truncated/corrupt file, etc.)
        print(f"  skip {name}: {e}")
        return None


def chunk(text: str) -> list[str]:
    text = " ".join(text.split())
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + CHUNK_CHARS])
        i += CHUNK_CHARS - OVERLAP
    return [c for c in out if c.strip()]


def ingest_one(cur, source: str, text: str) -> int:
    """Replace any existing rows for `source`, then insert fresh chunks. Returns count."""
    cur.execute("DELETE FROM chunks WHERE source = %s", (source,))
    chunks = chunk(text)
    for b in range(0, len(chunks), BATCH):
        batch = chunks[b:b + BATCH]
        vecs = gemini.embed(batch, is_query=False)
        for idx, (c, v) in enumerate(zip(batch, vecs), start=b):
            cur.execute(
                "INSERT INTO chunks (source, chunk_index, content, embedding) "
                "VALUES (%s, %s, %s, %s)",
                (source, idx, c, v),
            )
    return len(chunks)


def main():
    force = "--force" in sys.argv
    only = None
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        only = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

    corpus_dir = os.path.join(os.path.dirname(__file__), "..", "corpus")
    files = list_files(corpus_dir)
    if not files:
        raise SystemExit("No docs in corpus/. Drop some .md/.txt/.pdf files there first.")

    conn = db.connect()
    cur = conn.cursor()

    # Which sources are already ingested?
    cur.execute("SELECT DISTINCT source FROM chunks;")
    existing = {r[0] for r in cur.fetchall()}

    ingested = skipped = failed = 0
    for path, name in files:
        if only and name != only:
            continue
        if name in existing and not force and name != only:
            print(f"  skip {name}: already ingested")
            skipped += 1
            continue

        text = load_text(path, name)
        if text is None:
            failed += 1
            continue

        n = ingest_one(cur, name, text)
        conn.commit()  # commit per file so progress survives a later failure
        print(f"  {name}: {n} chunks")
        ingested += 1

    cur.execute("SELECT count(*) FROM chunks;")
    total_rows = cur.fetchone()[0]
    print(
        f"Done. ingested {ingested} file(s), skipped {skipped} already-present, "
        f"{failed} unreadable. rows in chunks = {total_rows}"
    )
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
