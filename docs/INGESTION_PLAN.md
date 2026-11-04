# Two editions, one codebase: local demo + hosted multi-format intake

Decided 2026-11-04. Status of each step is kept in the table at the bottom.

## The decision

NorAI ships in two forms:

- **Local** (the public GitHub demo): anyone clones the repo, pastes their own
  Gemini key, and runs everything on their PC. YouTube works, since yt-dlp
  works from home IPs.
- **Hosted** (the VPS): no YouTube (yt-dlp is blocked on every server IP we
  probed on 2026-11-01, and paid transcript APIs are out). Intake moves to
  uploads, cloud links, documents and web pages, matching Mindgrasp minus YouTube.

These are **not two branches**. They are one trunk (`master`, public on
`github.com/GouravLuinor/NorAI`) run under two settings:

| Setting | Local | Hosted |
|---|---|---|
| `NORAI_MODE` | `local`: no login (everything runs as the single local user), no quotas, SQLite, no marketing/pricing pages | `hosted` (default): Supabase login, quotas, rate limits |
| `NORAI_SOURCES` (default) | every source, YouTube included | everything except `youtube` |

Why not two long-lived branches: production would delete YouTube and demo
would keep it, so every later "merge production features into demo" would try
to delete YouTube from demo again and conflict in the same files
(`ingest/ingest.py`, `backend/main.py`, `UploadPage.tsx`). With flags,
production features reach the demo the moment they land.

"YouTube removed from production" therefore means: the source is off in config,
`/process` and `/estimate` reject it, the UI doesn't offer it, and the
production image drops yt-dlp and the PO-token binary. The code stays for local.

The backend refuses to start with `NORAI_MODE=local` (or the older
`NORAI_DEV_ACCESS=1`) when `NORAI_ENV=production`, because local mode turns off
lecture ownership checks.

## How it's wired (step 1, done)

- `config.py`: `run_mode()`, `is_local_mode()`, `dev_access()` (local mode or
  the developer flags `NORAI_DEV_ACCESS` / `NORAI_DEV_INSECURE_AUTH`; every
  ownership/quota bypass reads this one function), `enabled_sources()`.
- `GET /system/config` → `{"mode", "sources"}`, public. The frontend's
  `useAppConfigStore` loads it once at startup.
- `/estimate` and `/process`: `_require_enabled_source` returns 400 for an
  unknown source and for one switched off, with a "upload the file instead" message.
- Frontend in local mode: `initAuth` sets the local session (token `dev`, which
  the backend maps to `DEV_USER_ID`) without touching Supabase; `/`, `/login`,
  `/signup`, `/pricing`, `/billing` redirect to `/app`; the sidebar shows
  "Local install" instead of plan/quota/sign-out. In both modes the upload page
  offers only the enabled sources.
- `scripts/setup-local.sh`: checks prerequisites, creates venv, installs both
  dependency sets, writes `.env` with `NORAI_MODE=local`, downloads the embedding model.

## Multi-format intake for hosted (steps 2–5, planned)

### Documents go through the existing content pipeline

The content stages already work on a list of timestamped text segments, and
already run without keyframes (`run_content_stages(..., keyframes_meta=None)`).
So documents don't get a new chain. An **adapter** turns each document into
the same transcript JSON:

- one segment per paragraph (split to ~40 words), with a synthetic time from
  the word offset at 150 words per minute, plus a `loc` label (`p. 4`,
  `Slide 7`, a heading);
- chunking, the structure call, chapter sizing (`chapter_count_range` on
  "duration"), the per-chapter call, the tutor index and quota metering then run
  unchanged. A 6,000-word PDF counts as a 40-minute lecture: words ÷ 150 is the
  one quota unit, shown honestly in the UI ("uses 12 min").

What does change:

- **Prompts** get a source-kind variant ("lecture/transcript/lecturer said" →
  "document/text/author"; ~22 places in `lean/` and `tutor/prompts.py`), and
  location tags replace `[MM:SS]` (`section_start` maps them back).
- **No images** for non-video sources: no keyframes are sent, so no
  screenshots are picked and notes have none.
- **Tutor citations** show the page/slide/heading instead of a timestamp.
- **Workspace**: the video player and seek controls hide when the lecture has
  no video (`useVideoStore.embeddable` already gates part of this); the
  lecture's `source_kind` goes into its metadata.

### Extractors (all permissive licences)

| Input | Library | Notes |
|---|---|---|
| PDF | `pypdfium2` (not PyMuPDF, which is AGPL) | No text layer (scanned) → send the PDF to Gemini natively instead |
| DOCX | `python-docx` | Headings become section boundaries |
| PPTX | `python-pptx` | Slide text + speaker notes, `loc` = slide number |
| Web page | `trafilatura` | Main-content extraction; JS-only pages fail, said plainly |
| `.doc` / `.ppt` | — | Rejected with "save as .docx/.pptx": LibreOffice is too heavy for the shared 1-vCPU box |

### Cloud links

Google Drive already works (`gdown`). Add Google Docs/Slides export
(`/export?format=docx|pptx`), Dropbox (rewrite to `dl=1`), and direct file
URLs. Every server-side fetch of a user URL goes through an SSRF guard
(resolve, reject private/link-local/loopback ranges, re-check on redirect),
a size cap and a content-type check.

### Parallel runs

`backend/jobs.py` claims work under one global cap (`MAX_CONCURRENT_PIPELINES`,
1 on the VPS). Split it into two lanes, derived from the source type:

- **video**: ffmpeg + transcription, 1 slot on the VPS;
- **document**: parsing + Gemini only, ~2 slots.

A PDF then doesn't wait behind a 5-minute video. The Gemini RPM policy in
`backend/gemini_client.py` is already shared across both.

### Intake UI

One box: drop any file or paste any link; the type is detected (extension +
magic bytes for files, host rules for links) and shown as a chip
("PDF · 23 pages · uses 12 min"). Simpler than more tabs, and the
`sources` allowlist filters what it accepts.

## Steps

| # | Step | Status |
|---|---|---|
| 0 | Merge `ux-launch` into `master` | done 2026-11-04 (fast-forward) |
| 1 | Local mode + `NORAI_SOURCES` + `/system/config` + `setup-local.sh` + README quickstart | done 2026-11-04 (not pushed) |
| 2 | Source-kind abstraction in the content pipeline (adapter, prompt variants, citations, hide video UI) | planned |
| 3 | Extractors: PDF, DOCX, PPTX, web, then cloud links (+ SSRF guard) | planned |
| 4 | Auto-detect intake box, two job lanes, word-based quota | planned |
| 5 | Hosted deploy with YouTube off and the slimmer image (no yt-dlp / bgutil-pot) | planned |

Open for the local demo: yt-dlp is pinned to 2026.6.9, which only gets 360p
(Android client) without a PO-token server, so local screenshots are low-res.
The 2026-11-01 probe got 720p with 2026.10.26 and the default client.
