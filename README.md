# DocFetch Security Lab

Document retrieval and authorized security-testing lab. Fetch a PDF from any target, and run the lab engine against targets you explicitly own to surface real authorization/security gaps — backed by observed server behavior, never fabricated data.

Built from the Stitch design *"Verdant Cipher"* (see `stitch_docfetch_security_lab(1)(1)/DESIGN.md`).

## Stack

| Layer | Tech | Location |
| --- | --- | --- |
| Web app | React 18 + Vite + PWA | `apps/web` |
| Desktop shell | Tauri 2 (Rust) | `apps/desktop` |
| API | FastAPI + SQLAlchemy + Alembic | `apps/api` |
| Shared types | TS mirror of the API schema | `packages/types` |
| API client | typed `DocFetchClient` | `packages/core` |
| Document validation | magic-byte PDF checks | `packages/document-engine` |
| UI primitives | chips, status dots, verdicts | `packages/ui` |
| Lab targets | zero-dependency stdlib servers | `lab-target/` |
| DB | SQLite (dev) / PostgreSQL (docker) | — |

## Quick start

```bash
# 1. Backend
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 2. Lab targets (kept in a second terminal)
bash scripts/run_lab_targets.sh          # 9101/9102/9103
bash scripts/stop_lab_targets.sh         # when done

# 3. Web app (kept in a third terminal)
npm install
npm run dev                              # http://localhost:5173 (proxies /api → :8000)
```

Then open http://localhost:5173, go to **Security Lab**, pick a target and run a profile.

## The lab targets

| Target | Port | Vuln class |
| --- | --- | --- |
| `secure-paywall` | 9101 | Server-side auth enforced (control / "pass") |
| `weak-client-paywall` | 9102 | Client-side-only access control (HIGH) |
| `weak-direct-file` | 9103 | Direct protected file access (HIGH) |

All targets serve the same real sample PDF (`lab-target/shared/sample-document.pdf`) behind a *different* authorization posture, so findings reflect genuinely observed responses. The engine identifies itself with `Authorization: Bearer lab-authorized`; only hosts in `AUTHORIZED_LAB_TARGETS` (or loopback, which you own) can be registered.

## Commands

| Command | What it does |
| --- | --- |
| `npm run dev` / `dev:api` | Web dev server / API |
| `npm run build` | Build web app (PWA + manifest) |
| `npm run typecheck` | TS check all workspaces |
| `npm test` / `test:api` | Vitest packages / pytest API |
| `npm run test:integration` | Fullstack integration (`tests/integration/run.sh`) |
| `npm run lab:up` / `lab:down` | Start / stop lab targets |
| `npm run desktop:dev` / `desktop:build` | Tauri dev / release |
| `npm run db:migrate` | Apply Alembic migrations |

## Docker

```bash
docker compose up --build        # API + Postgres + lab targets
docker compose up api db         # API + Postgres only
```

The API container runs migrations on start (`alembic upgrade head`), then serves uvicorn.

## Security model

- **Authorized lab targets only.** External hosts are rejected unless listed in `AUTHORIZED_LAB_TARGETS`. Loopback is auto-authorized because you own it.
- **SSRF hard-block.** The fetch engine blocks loopback/private/metadata networks by default; per-hop redirect re-validation.
- **No credential persistence.** Header redaction (`[REDACTED]`), request/response evidnce only, no cookies/tokens stored.
- **Upload validation.** Client + server both check PDF magic bytes; MIME/extension never trusted alone.

## Tests

```bash
cd apps/api && pytest -q             # 39 unit/integration tests
npm run test                         # vitest package tests
npm run test:integration             # running-system check (api + lab + frontend)
bash scripts/smoke_e2e.sh            # quick stack smoke
```

## Packaging

`packaging/PKGBUILD` + `packaging/docfetch-security-lab.desktop` build the desktop shell for Arch (`.deb`/`.AppImage`/`.rpm` via `tauri build`). CI: `.github/workflows/ci.yml`.

## Layout

```
apps/api            FastAPI backend, Alembic migration, security engine
apps/desktop        Tauri 2 shell around the web bundle
apps/web            React SPA (Verdant Cipher theme, PWA-ready)
packages/*          Shared TS types, client, validation, UI kit
lab-target/         Authorized training targets (stdlib-only)
scripts/            Lab + e2e lifecycle helpers
tests/integration   Fullstack integration runner
packaging/          Arch PKGBUILD + desktop entry
```# Docfetch_security_lab
