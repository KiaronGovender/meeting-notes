# Notetaker (Fathom rebuild)

## Run locally
```bash
cp .env.example .env            # fill in MEETINGBAAS_API_KEY and ASSEMBLYAI_API_KEY
docker compose up -d            # Postgres
ollama pull llama3.1:8b         # LLM for dev/testing

cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# second terminal: expose the webhook, then put the URL in PUBLIC_API_URL
ngrok http 8000

# third terminal
cd web && npm install && npm run dev
```
