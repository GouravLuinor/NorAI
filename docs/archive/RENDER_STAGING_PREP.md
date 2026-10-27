# Render Staging — Pre-Deploy Hardening Checklist

Tracked execution plan for the 2026-08-16 pre-deploy audit. Every item has been
done **and tested** before the Render web service is created.

## Phase A — seed_data into git (WAL-checkpointed) — [COMPLETED]

- [x] A1. `PRAGMA wal_checkpoint(TRUNCATE)` on the 3 `seed_data/*/tutor/checkpoints.sqlite` files; delete the now-empty `-wal`/`-shm` sidecars
- [x] A2. `git add -f seed_data` (all 435 demo files incl. `chroma.sqlite3`)
- [x] A3. Verify: `git ls-files seed_data | wc -l` == 435 and **no** `*-wal`/`*-shm` staged

## Phase B — Dockerfile — [COMPLETED]

- [x] B1. Frontend stage: `ARG VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY VITE_API_BASE_URL` + `ENV` before `npm run build` (Render auto-translates service env vars → build args)
- [x] B2. Pin `node:22-alpine`
- [x] B3. Runtime `CMD` → `python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}` (honors Render `PORT=10000`)
- [x] B4. `ENV NORAI_ENV=production` default in runtime stage

## Phase C — env / stale dist cleanup — [COMPLETED]

- [x] C1. Removed the fake `VITE_API_BASE_URL=https://your-production-backend-domain.com` from root `.env.production`
- [x] C2. Rebuilt clean `frontend/dist/` without poisoned variables

## Phase D — GC + seed robustness — [COMPLETED]

- [x] D1. `backend/jobs.py` `gc_sweep()` skips the 3 demo lecture IDs
- [x] D2. `backend/main.py` `sync_demo_seed_data()` re-copies when a demo dir is incomplete (missing `tutor/chroma/chroma.sqlite3`)

## Phase E — DB hardening — [COMPLETED]

- [x] E1. `backend/db/database.py`: strip `sslmode=`/unknown query params; rewrite `postgres://` → `postgresql+asyncpg://`
- [x] E2. `statement_cache_size: 0` when URL port is 6543 (Supabase Transaction Pooler / PgBouncer)
- [x] E3. Loud warning on SQLite fallback when `NORAI_ENV != development`; `command_timeout` 10 → 30

## Phase F — minor cleanup — [COMPLETED]

- [x] F1. `.dockerignore`: added `.tmp/`, `chroma_db/`
- [x] F2. Deleted stale duplicate `backend/requirements.txt`
- [x] F3. Disabled Chroma telemetry (`Settings(anonymized_telemetry=False)`) across indexers, orchestrator, and retriever

## Phase H — verification (before deploy) — [COMPLETED]

- [x] H1. Frontend build validated: `VITE_*` build args support verified in `Dockerfile`
- [x] H2. `scripts/run-tests.sh` (39/39 offline tests passed, 0 failed)
- [x] H3. `cd frontend && npm run lint && npm run build` (`oxlint` 0 errors, `tsc -b && vite build` 0 errors, built in 593ms)
- [x] H4. Ready to commit + push

## Render dashboard config (post-code)

- [ ] G1. Env vars: `GEMINI_API_KEY`, `DATABASE_URL` (Session Pooler 5432 preferred, no `sslmode`), `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `NORAI_ENV=staging`, `NORAI_DEV_ACCESS=0`, `NORAI_DEV_INSECURE_AUTH=0`, `MAX_FREE_DURATION_MIN=15`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (leave `VITE_API_BASE_URL` unset)
- [ ] G2. Instance ≥1 GB, single instance, port auto via `$PORT`, no persistent disk (ephemeral OK — demos re-seed each boot)