# Notetaker

An AI meeting notetaker, built as a 24-hour rebuild of [Fathom](https://fathom.video/). A bot joins a Meet, Zoom or Teams call, records it, and afterwards you get a speaker-labelled transcript synced to playback, AI summaries in several templates, action items, and highlights.

- **Live app:** `https://meeting-notes-omega.vercel.app/`

> The live app runs on free tiers. If the API has been idle it can take up to a minute to wake on the first request.

## What it does

- **Capture.** Paste a meeting link and a real recording bot joins the call (via Meeting BaaS). Status updates live: joining, recording, processing, done.
- **Transcript.** Speaker-labelled and timestamped (AssemblyAI). Click any line to jump the video to it. The current line highlights as it plays. Search within a transcript.
- **Summaries.** Four templates (General, Sales call, 1:1, Standup), written from the transcript. Long meetings are handled with chunked map-reduce, so an hour-long, 8-person call fits the model's context.
- **Action items.** Extracted with owner and timestamp, de-duplicated across chunks. Click one to jump to the moment.
- **Highlights.** Bookmark a moment (button or the `H` key). It saves a 30-second clip with an optional note, shown as markers on a timeline.
- **Meetings list.** Status badges that refresh automatically, with delete.

## Architecture

```
Browser (Next.js, Vercel)
      |
      v
FastAPI (Render) ---- Postgres (Neon)
  |        |
  |        +-- Meeting BaaS: send bot, recording links, status
  |        +-- AssemblyAI: transcription with speaker labels
  |        +-- LLM (Groq, OpenAI-compatible; Ollama locally)
  ^
  |  completion callback (shared secret)
Meeting BaaS
```

**Flow:** `POST /meetings` sends a bot, and Meeting BaaS calls back when the recording is ready. The API then fetches the audio, transcribes it, and stores the segments. Summaries are generated on first view and cached.

**Stack:** Next.js 15 (React 19, TypeScript), FastAPI, SQLAlchemy 2, PostgreSQL, Meeting BaaS API v2, AssemblyAI, Groq (`openai/gpt-oss-120b`).

## Product decisions

- **Real capture, not a stub.** The bot path is built end to end, because everything else depends on real transcripts.
- **Transcription is separate from capture.** Meeting BaaS only records. AssemblyAI does the transcription, which keeps the provider swappable.
- **The callback is not trusted on its own.** Opening a meeting also reconciles status with Meeting BaaS, so a missed or late callback can't leave a meeting stuck.
- **Cheap template switching.** The expensive note-taking pass over the transcript runs once per meeting and is cached. Each template is only one extra model call.
- **Recording links expire.** Meeting BaaS download links are short-lived, so playback fetches fresh ones each time instead of storing them.
- **Provider interface for the LLM.** Ollama for local development, any OpenAI-compatible API in production.
- **Plain CSS, no component library,** to keep the build small and fast.

## Not built

- Cross-meeting search
- Sharing links for meetings and clips (the tables exist, with no endpoints or UI)
- Calendar connection and auto-join
- Sign-in and per-user data
- Live highlighting during a call. Highlights are added when reviewing a recording.
- Speaker renaming. Speakers appear as "Speaker A, B..." and action-item owners are often blank for that reason.

## Run locally

Requirements: Python 3.12+, Node 20+, Docker (for local Postgres), and optionally [Ollama](https://ollama.com).

```bash
cp .env.example .env              # then fill in the keys (see below)
docker compose up -d              # local Postgres

# API
cd api
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.check_env       # verifies database and LLM keys
uvicorn app.main:app --reload --port 8000

# tunnel, so Meeting BaaS can reach your callback (set PUBLIC_API_URL to its https URL)
ngrok http 8000

# Web (new terminal)
cd web
cp .env.local.example .env.local
npm install
npm run dev                       # http://localhost:3000
```

The API reads `.env` from the project root. Restart uvicorn after changing it.

## Environment variables

| Variable                                   | Purpose                                                                                     |
| ------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                             | Postgres connection string. A plain `postgresql://` URL is rewritten for the psycopg driver |
| `FRONTEND_ORIGIN`                          | Allowed web origins for CORS, comma-separated                                               |
| `PUBLIC_API_URL`                           | Public URL of the API, used as the callback address                                         |
| `WEBHOOK_SECRET`                           | Shared secret Meeting BaaS sends back in the `x-mb-secret` header. Use a long random value  |
| `MEETINGBAAS_API_KEY`                      | Meeting BaaS API key                                                                        |
| `ASSEMBLYAI_API_KEY`                       | AssemblyAI API key                                                                          |
| `LLM_PROVIDER`                             | `openai` (any OpenAI-compatible API) or `ollama`                                            |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | OpenAI-compatible settings. Defaults point at Groq                                          |
| `OLLAMA_URL`, `OLLAMA_MODEL`               | Local Ollama settings                                                                       |
| `READ_ONLY`                                | `true` blocks creating and deleting meetings (for a public demo)                            |
| `NEXT_PUBLIC_API_URL`                      | (web) API base URL                                                                          |

## API

| Method         | Path                        | Purpose                                                    |
| -------------- | --------------------------- | ---------------------------------------------------------- |
| POST           | `/meetings`                 | Send a bot to a meeting URL                                |
| GET            | `/meetings`                 | List meetings                                              |
| GET            | `/meetings/{id}`            | Meeting with transcript and highlights (reconciles status) |
| GET            | `/meetings/{id}/media`      | Fresh video and audio links                                |
| POST           | `/meetings/{id}/summary`    | Summary and action items for a template (cached)           |
| POST           | `/meetings/{id}/highlights` | Add a highlight                                            |
| PATCH / DELETE | `/highlights/{id}`          | Edit a note / delete                                       |
| DELETE         | `/meetings/{id}`            | Delete a meeting and all its data                          |
| POST           | `/webhooks/meetingbaas`     | Recording-finished callback (secret required)              |
| GET            | `/health`                   | Health check                                               |

Interactive docs are at `/docs` on the running API.

## Seeding data

Import a public recording through the same pipeline, without needing a live call:

```bash
cd api
python -m scripts.ingest_url "https://example.com/meeting.mp3" "City council meeting"
```

Set `DATABASE_URL` to the production database to seed the live app, then open each meeting once so its summary is generated and cached.

## Deploy

All on free tiers.

1. **Database:** create a [Neon](https://neon.tech) project and copy the connection string.
2. **LLM:** create a key at [console.groq.com](https://console.groq.com).
3. **API:** Render web service, root directory `api`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, with a single worker. Set the environment variables above.
4. **Web:** Vercel project with root directory `web` and `NEXT_PUBLIC_API_URL` set to the Render URL. Then add the Vercel URL to `FRONTEND_ORIGIN` on Render.
5. **Keep it awake:** point a free uptime monitor at `/health` every 5 to 10 minutes, since Render's free tier sleeps when idle.

## Known limitations

- Free-tier rate limits on the LLM can slow summaries on very long meetings. The client retries automatically.
- Summaries are generated on first view, so the first visitor to a new meeting waits.
- Recordings imported by URL play from their original link. Recordings made by the bot are served through Meeting BaaS.
- No authentication: anyone with the link can use the app. Set `READ_ONLY=true` on a public deployment.

## AI assistance

`<Describe how you used AI tools here.>`
