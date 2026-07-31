# Viral Video Factory

Self-hosted workflow that finds timely video/news topics from configurable keywords on a VPS, lets an administrator select one of five curated candidates, and renders an approved topic into a vertical **9:16 (`1080x1920`)** video on a local PC using [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) and [wigolo](https://github.com/KnockOutEZ/wigolo). The rendered file **stays on the local PC** — the dashboard previews it by streaming over **Tailscale**, and the PC **publishes** the video straight to TikTok, YouTube Shorts, and Instagram Reels.

> Full design: [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md)

## Direction (decided)

- **No VPS video storage.** Rendered videos are never uploaded to the VPS. The VPS keeps only metadata, provenance, and published post URLs.
- **Preview via Tailscale.** VPS + render PC join a private tailnet; the VPS reverse-proxies (streams) the video from the PC on demand. No public inbound port, nothing stored on the VPS.
- **Publishing = free official APIs (auto) + manual fallback.** Prefer YouTube Data API v3, TikTok Content Posting API, and Instagram Graph API (free, one-time OAuth). If an API/OAuth path is unavailable, fall back to manual download + record the post URL.

## Current status (true state)

Pipeline is **deployed and works end-to-end with real videos, including dashboard preview streamed from the render PC over Tailscale**. Publishing (M6) is the remaining phase. Below is the honest per-milestone state.

| Phase | Status | True state |
| --- | --- | --- |
| M0 — Foundation | ✅ done | Monorepo, Docker, contracts, DB/Alembic, seed, CI; 28 tests passing |
| M1 — Discovery MVP | 🟡 partial | wigolo adapter + worker work; **runs on mock wigolo** (always Bali-gempa sample data). Real wigolo image **not enabled/verified** |
| M2 — Approval & Queue | ✅ done | Approve/reject, render profiles, immutable render jobs, job-detail screen with live polled progress |
| M3 — Local PC Rendering | ✅ done | `vvf-local-agent` + MoneyPrinterTurbo produce real `1080x1920` Indonesian MP4s (verified: ~23 MB, Edge TTS `id-ID-ArdiNeural`, Pexels footage, subtitles, ffmpeg) |
| M4 — Output Management (**no VPS storage**) | ✅ done | VPS-upload path removed. Video stays on PC; VPS stores metadata only. Verified live end-to-end: real render → `completed` → dashboard `<video>` streams from PC over Tailscale through the VPS proxy (full 31 MB GET + `206` Range seek via public nginx, `401` when unauthenticated, **zero MP4 bytes on VPS disk**) |
| M5 — Reliability & Scale | ⬜ not started | Batch, retries, dead-letter, notifications, usage/cost metrics, multiple PCs |
| **M6 — Publishing** | ⬜ not started | Publish finished video to YouTube/TikTok/Instagram via **free official APIs** (auto) with **manual fallback**; track post URLs |
| **Real wigolo** | ⬜ not started | Keyword-accurate candidates. Enable: `VVF_WIGOLO_USE_MOCK=0` + `--profile wigolo` |

### Live deployment
- **Dashboard:** https://app.purapuraninja.my.id
- **API + docs:** https://api.purapuraninja.my.id (`/docs`)
- VPS `153.76.249.141` — Docker Compose stack + nginx reverse proxy + Let's Encrypt TLS
- Local PC — MoneyPrinterTurbo (Docker, CPU image) + `vvf-local-agent` (host Python 3.14)
- **Tailscale tailnet (M4):** VPS `100.101.49.38`, PC `100.96.233.10` — connected ✅

### What currently works (verified live)
Login → create research run → discovery (mock) → 5 candidates → approve one → immutable render job queued → local agent claims → MoneyPrinterTurbo renders a real 9:16 Indonesian video (~31 MB) → job `completed` with full progress timeline → **dashboard plays the video streamed from the PC over Tailscale**. The MP4 never leaves the PC (`MoneyPrinterTurbo/storage/tasks/{task_id}/final-1.mp4`); the VPS stores only `local_path`, `agent_id`, size and provenance, and proxies bytes on demand (verified: full GET 31 247 442 B, `206` Range seek at arbitrary offsets, `401` without a session, and no `*.mp4` anywhere on VPS disk).

## Roadmap to "final"

1. **M6 — Publishing** — publish the local file to platforms using **free official APIs** (YouTube Data API v3, TikTok Content Posting API, Instagram Graph API) for automatic posting, with a **manual fallback** (download from Tailscale preview + record post URL). Report post URLs + provenance to the VPS.
2. **Real wigolo** — flip mock off + pull the image; verify keyword-accurate candidates end-to-end.
3. **M5 reliability** — batch, retries, dead-letter, notifications, metrics, multiple render PCs.
4. Hardening — auth (beyond single-admin), rate limits, provenance verification, content-policy enforcement at scale.


## Pipeline

1. Admin enters a keyword + prompt in the dashboard.
2. VPS searches/collects sources via **wigolo** (adapter).
3. System normalizes, deduplicates, scores, presents the best 5 candidates.
4. Admin reviews sources/facts and approves one candidate.
5. VPS creates an immutable render job (`queued`).
6. Local PC agent claims the job (outbound HTTPS + long polling).
7. Agent drives **MoneyPrinterTurbo** → script, footage, TTS, subtitles, music, final video.
8. The rendered file **stays on the PC**; the agent reports only progress + metadata (path, size, duration, provenance) to the VPS.
9. Admin **previews** the video in the dashboard — the VPS reverse-proxies a live stream from the PC over **Tailscale** (never stored on the VPS).
10. Agent **publishes** the video to YouTube/TikTok/Instagram (free official APIs, auto; manual fallback) and reports post URLs + provenance to the VPS.

## Monorepo layout

```text
viral-video-factory/
├── apps/
│   ├── dashboard/              # Next.js + TypeScript admin UI (auth gate, runs, jobs, profiles, outputs)
│   ├── api/                     # FastAPI: auth, research, render, agent protocol, Tailscale preview proxy
│   ├── discovery-worker/        # Redis consumer: wigolo retrieval + candidate scoring
│   └── local-render-agent/      # Local PC service: claim → MPT → local file → Tailscale preview → publish
├── packages/
│   ├── contracts/               # Pydantic schemas (shared source of truth)
│   ├── database/                # SQLAlchemy models + Alembic migrations + seed
│   ├── shared/                  # config, logging, security
│   └── prompt-templates/        # research / validation / script templates
├── integrations/
│   ├── wigolo/                  # wigolo MCP client + result mapper (+ Mock)
│   └── money-printer-turbo/     # MPT REST adapter + state mapping (+ Mock)
├── publishers/                  # (M6) YouTube / TikTok / Instagram official-API uploaders + manual fallback
├── infrastructure/
│   ├── vps/                     # prod compose, nginx, Caddyfile, .env.vps
│   └── local-pc/                # MPT + agent install notes
├── docs/                        # architecture, api-contract, deployments, content-policy
├── scripts/                     # deploy.sh, verify/e2e checks, state+events inspection, agent launcher
├── tests/                       # unit + integration (28 tests, all passing)
├── docker-compose.dev.yml        # local dev stack
├── docker-compose.prod.yml       # production stack (VPS)
└── README.md
```


## Quickstart — local development

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build      # postgres, redis, wigolo(opt), api, dashboard, worker
docker compose -f docker-compose.dev.yml exec api bash -lc "cd /app/packages/database && alembic upgrade head"
docker compose -f docker-compose.dev.yml exec api python -m vvf_database.seed
```

Default admin: `admin` / `VVF_ADMIN_PASSWORD` (default `changeme`). Tests: `pytest` (28 tests). No object storage needed — video never touches the VPS.

## Production deployment (VPS)

```bash
# On the VPS, repo at /opt/viral-video-factory/repo/vvf
bash scripts/deploy.sh        # idempotent: generates .env secrets, builds, migrates, seeds, health-checks
docker compose -f docker-compose.prod.yml logs -f api
bash /tmp/e2e_check.sh        # cookie-based end-to-end check (login → run → candidates)
```

- nginx reverse-proxies `api.*` → `127.0.0.1:8000` and `app.*` → `127.0.0.1:3000`.
- TLS via `certbot --nginx` (auto-renew).
- Video preview is streamed on demand from the render PC over **Tailscale** (VPS reverse-proxies, Range-supported); **nothing is stored on the VPS**.
- Enable **real wigolo**: `VVF_WIGOLO_USE_MOCK=0` + `docker compose -f docker-compose.prod.yml --profile wigolo up -d`.

### Verification scripts (run on the VPS)

```bash
bash scripts/verify_m4_vps.sh                     # schema, routes, Tailscale reachability
bash scripts/state_check.sh                       # agents, runs, candidates, jobs, outputs
bash scripts/events_check.sh <job_id>             # per-job event timeline
bash scripts/create_render_job.sh                 # queue a job from newest approved candidate
bash scripts/e2e_m4_preview.sh                    # outputs metadata + preview 200/206 + no VPS files
bash scripts/full_preview_check.sh <job_id>       # stream the entire file through the proxy
bash scripts/public_preview_check.sh <job_id>     # public nginx path: Range seek + 401 without auth
```

## Local PC rendering (MoneyPrinterTurbo + agent)

```bash
# 1. MoneyPrinterTurbo (Docker, CPU image)
git clone --depth 1 https://github.com/harry0703/MoneyPrinterTurbo
cd MoneyPrinterTurbo && cp config.example.toml config.toml
#    config.toml: llm_provider="openai" + openai_* key/base_url/model_name,
#    pexels_api_keys=["..."], subtitle_provider="edge", video_source="pexels"
docker compose up -d --build api      # http://127.0.0.1:8080

# 2. VVF local agent (host Python 3.11+)
pip install -e packages/contracts packages/shared integrations/money-printer-turbo apps/local-render-agent

# PC with Tailscale (this repo's reference deployment) — one line:
powershell -File scripts/start-agent-pc.ps1

# or manually elsewhere:
VVF_API_URL=https://api.<your-domain> \
VVF_AGENT_NAME=render-pc-01 \
MPT_BASE_URL=http://127.0.0.1:8080 \
VVF_PREVIEW_HOST=<tailscale-ip-of-this-pc> \
VVF_PREVIEW_PORT=8090 \
VVF_PREVIEW_ROOT=/abs/path/MoneyPrinterTurbo/storage/tasks \
python -m vvf_local_agent.main
```

The agent registers (advertising its Tailscale `preview_base_url`), heartbeats every 30 s, long-polls `claim-job`, and drives MPT per job. Idempotency keys prevent duplicate renders on retry. The rendered file stays on the PC; the agent reports metadata to the VPS, serves preview over Tailscale, and (M6) publishes to platforms. Verify preview reachability from the VPS before relying on it; full checklist: [`docs/deployment-tailscale-preview.md`](./docs/deployment-tailscale-preview.md).

## Key facts / gotchas (learned during deployment)

- **MPT = OpenAI-compatible LLM + Pexels footage + Edge TTS (free).** Whisper subtitle mode needs NVIDIA CUDA; use `subtitle_provider="edge"` on CPU/AMD PCs.
- **Do not pass unrelated text as MPT `custom_system_prompt`** — it overrides MPT's tuned system prompt and the LLM returns empty content (`returned empty text content`, job → `retry_waiting`). Creative direction belongs in `video_script_prompt`; music profile maps to `bgm_type`.
- **`NEXT_PUBLIC_*` is inlined at Next.js build time** — set it as a build ARG (`Dockerfile.prod`), not just runtime env, or the dashboard rewrite proxies to the wrong host.
- **Dashboard auth is cookie-based** (`vvf_session`); the API accepts either the cookie or `Authorization: Bearer` (used by the agent/curl).
- **MPT accepts VideoParams directly** (no `video_params` envelope); create = `POST /api/v1/videos`, status = `GET /api/v1/tasks/{id}` (state `1`=success, `-1`=error, `4`=in progress).
- **VPS never renders** (explicit non-goal) — rendering always happens on the local PC.
- **The preview proxy must use an async streaming client.** A sync `httpx.Client` inside a sync FastAPI handler yields 0 bytes for full-file GETs (Range still worked, masking the bug); use `httpx.AsyncClient` + `BackgroundTask` cleanup so the connection outlives the handler.
- **Agent registration advertises `preview_base_url`** — if `VVF_PREVIEW_HOST` is loopback at start-up, the agent registers without a preview URL and the dashboard shows no player. Set the Tailscale IP *before* starting the agent.

## Next steps

See the **Roadmap to "final"** above for the ordered plan. Summary of what's left:

- [x] **M4 — Preview over Tailscale**: done and verified live (metadata-only outputs, PC preview server, VPS proxy stream, dashboard `<video>`).
- [ ] **M6 — Publishing**: publish to YouTube/TikTok/Instagram via free official APIs (auto) with manual fallback; record post URLs.
- [ ] **Real wigolo**: keyword-accurate candidates (mock off + `--profile wigolo`).
- [ ] **M5 — Reliability**: batch, retries, dead-letter, notifications, usage/cost metrics, multiple render PCs.
- [ ] SSE progress stream (currently polled every 3 s).
- [ ] Auth hardening beyond single-admin.

## License

TBD — orchestration code only. Upstream integrations retain their own licenses (wigolo: AGPL-3.0, MoneyPrinterTurbo: MIT).

