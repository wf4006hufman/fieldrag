"""Single source of truth for config. Reads env (.env locally)."""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Models ---
GEN_MODEL = os.getenv("GEN_MODEL", "gemini-2.5-pro")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))
TOP_K = int(os.getenv("TOP_K", "5"))

# Optional Gemini Developer API key. Useful for local/free-tier testing or
# server-side demos without Vertex ADC. Client-supplied keys can also be passed
# per request and are not read from this env var.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
REQUIRE_API_KEY_FOR_RAG = os.getenv("REQUIRE_API_KEY_FOR_RAG", "").lower() in {
    "1",
    "true",
    "yes",
}

# --- DB ---
DB_NAME = os.getenv("DB_NAME", "fieldrag")
DB_USER = os.getenv("DB_USER", "fieldrag")
DB_PASSWORD = os.getenv("DB_PASSWORD", "fieldrag")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# When set, we're on Cloud Run talking to Cloud SQL via Unix socket.
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME", "").strip()
