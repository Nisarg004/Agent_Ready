# AgentReady: AI Readiness Checker

Paste a website URL and find out how well AI crawlers and assistants (GPTBot, ClaudeBot, PerplexityBot and others) can read it. The scanner returns a 0–100 score, a letter grade, and ready-to-paste code for every check that failed.

This project was copied out of the [codenixlabs](https://github.com/shubhamsiddhapura/codenixlabs) repo (`production` branch) so the feature can be developed on its own. The original repo is unchanged.

## Structure

| Folder | What it is |
|---|---|
| `agentready-api/` | Backend: Node + TypeScript + Express + MongoDB. The scan engine, lead capture and report emails. Port 5100. See [`agentready-api/ARCHITECTURE.md`](agentready-api/ARCHITECTURE.md). |
| `web/` | Frontend: React + Vite + Tailwind. The scan page and report UI. Port 5173. |

## Run locally

Requires Node 18 or newer.

```bash
npm install
npm run install:all
npm run dev
```

Then open http://localhost:5173.

`npm run dev` starts the API with a temporary in-memory MongoDB, so you don't need a database to try it. To use a real database, set it up as below.

## Configuration

- Backend: copy `agentready-api/.env.example` to `agentready-api/.env` and fill in `MONGODB_URI`, `RESEND_API_KEY` and the other values.
- Frontend: copy `web/.env.example` to `web/.env` and set `VITE_AGENTREADY_API_URL` if the API isn't on `http://localhost:5100`.

## Useful scripts

Backend (`cd agentready-api`):

- `npm run dev`: API using `MONGODB_URI` from `.env`
- `npm run dev:memory`: API with an in-memory MongoDB
- `npm run scan -- https://example.com`: scan a site from the command line
- `npm run build` / `npm start`: production build and run

Frontend (`cd web`):

- `npm run dev`, `npm run build`, `npm run typecheck`
