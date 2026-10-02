import json
import sys
from urllib.parse import urlparse

import httpx
from sqlalchemy import create_engine, text

from app.config import settings
from app.providers.llm import OpenAICompatClient

ok = True


def report(name: str, passed: bool, detail: str = ""):
    global ok
    ok = ok and passed
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))


# 1. Database (Neon)
url = settings.database_url
host = urlparse(url.replace("postgresql+psycopg", "postgresql")).hostname
if not url.startswith("postgresql+psycopg://"):
    report("DATABASE_URL format", False, "must start with postgresql+psycopg:// (not postgresql://)")
else:
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as c:
            c.execute(text("select 1"))
        report("Database connection", True, f"connected to {host}")
        from app.db import Base
        import app.models  # noqa: F401
        Base.metadata.create_all(engine)
        with engine.connect() as c:
            tables = c.execute(text("select count(*) from information_schema.tables where table_name='meetings'")).scalar()
        report("Tables created", tables == 1, "meetings table exists")
    except Exception as e:
        report("Database connection", False, str(e).splitlines()[0])

# 2. LLM (Groq)
if not settings.llm_api_key:
    report("LLM key", False, "LLM_API_KEY is empty (is .env in the project root?)")
else:
    base = settings.llm_base_url.rstrip("/")
    try:
        r = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {settings.llm_api_key}"}, timeout=30)
        if r.status_code == 401:
            report("LLM key", False, "401: key rejected")
        else:
            r.raise_for_status()
            ids = [m["id"] for m in r.json().get("data", [])]
            report("LLM key", True, f"{len(ids)} models available")
            report("Configured model listed", settings.llm_model in ids,
                   settings.llm_model if settings.llm_model in ids else f"{settings.llm_model} not found. Try one of: {', '.join(ids[:8])}")
    except Exception as e:
        report("LLM key", False, str(e).splitlines()[0])
    try:
        out = OpenAICompatClient().complete_json("Reply with JSON only.", 'Return {"status": "ok", "sum": 2+3 computed}.')
        report("JSON completion", isinstance(out, dict), json.dumps(out)[:100])
    except Exception as e:
        report("JSON completion", False, str(e)[:300])

print("\nAll good." if ok else "\nFix the FAIL lines above and run again.")
sys.exit(0 if ok else 1)