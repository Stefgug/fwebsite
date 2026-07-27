# fwebsite

Demo e-commerce + blog stack used to showcase an AI-assisted test automation pipeline.

- `frontend/` — Next.js 15 (App Router, Tailwind, Zustand)
- `backend/` — Strapi 5 (SQLite, auto-seeded content)
- `scripts/` — dev launcher, mock Strapi, and the Python automation/reporting scripts
- `.github/workflows/` — CI, AI test pipeline, and GitHub Pages report publishing

## Quick start

From the repository root:

```bash
npm run dev
```

This single command will:

1. install `frontend/` and `backend/` dependencies if they are missing,
2. pick free ports for both services,
3. start Strapi and Next.js together,
4. print the URLs to open.

Stop everything with `Ctrl+C` — both services shut down together.

### Default URLs

| Service | Default URL |
| --- | --- |
| Site (Next.js) | http://localhost:3000 |
| Strapi API | http://localhost:1338 |
| Strapi admin | http://localhost:1338/admin |

Ports are only defaults. If one is busy, the launcher picks the next free port
and prints the URL it actually used. Override them with the `FRONTEND_PORT` and
`PORT` environment variables.

### Seeded content

On first boot Strapi seeds categories, products, tags and articles into a local
SQLite database (`backend/.tmp/data.db`), and grants the **public** role read
access to products, categories, articles and tags plus create access for
contacts. Delete `backend/.tmp/` to reset the demo data.

## Other commands

| Command | Description |
| --- | --- |
| `npm run install:all` | Install backend and frontend dependencies |
| `npm run dev:backend` | Start only Strapi |
| `npm run dev:frontend` | Start only Next.js |
| `npm --prefix backend run build` | Build the Strapi admin panel |
| `npm --prefix frontend run build` | Production build of the site |
| `npm --prefix frontend run lint` | ESLint |
| `npm --prefix frontend run test:unit` | Vitest unit tests |
| `npm --prefix frontend run test:coverage` | Unit tests with coverage thresholds |
| `npm --prefix frontend run test` | Playwright end-to-end tests |

End-to-end tests run against a mock Strapi (`scripts/mock-strapi.js`) rather than
the real backend, so they do not need a seeded database. Override the ports with
`PLAYWRIGHT_FRONTEND_PORT` and `MOCK_STRAPI_PORT` if the defaults are taken.

## Environment variables

`backend/.env.example` lists the Strapi secrets. Copy it to `backend/.env` for a
real setup; local development falls back to safe development defaults if the
file is absent.

The frontend reads `NEXT_PUBLIC_STRAPI_URL` (injected automatically by
`npm run dev`) and the optional `STRAPI_API_TOKEN`.

## Continuous integration

| Workflow | Purpose |
| --- | --- |
| `unit-tests-ci.yml` | Unit tests with coverage threshold on push/PR to `main` |
| `code-change-analysis.yml` | AI analysis of app changes, publishes a report |
| `epic-test-pipeline.yml` | Full AI test pipeline triggered from a Jira epic |
| `publish-pages.yml` | Reusable workflow that assembles and deploys reports to GitHub Pages |

Both report-producing pipelines call `publish-pages.yml`, so the Pages
assemble/upload/retry logic exists in exactly one place.
