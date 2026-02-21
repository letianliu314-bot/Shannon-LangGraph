# Shannon Web Debug UI

This folder provides a Next.js web UI for debugging Shannon orchestration runs.

## What it does

- Starts workflows by calling `POST /runs`
- Subscribes to `GET /threads/{thread_id}/events/stream` (SSE) for real-time events
- Fetches `GET /threads/{thread_id}/state` and `GET /threads/{thread_id}/state_db` for live/persisted snapshots

## Run in local web mode

1. Start backend services from repository root:

```bash
make run-orchestration
make run-llm
```

2. Start web UI:

```bash
cd desktop
cp -n .env.example .env.local
npm install
npm run dev
```

3. Open browser: `http://localhost:3000`

## Environment

- `SHANNON_ORCH_BASE_URL`: Orchestrator API base URL, default `http://127.0.0.1:8000`
