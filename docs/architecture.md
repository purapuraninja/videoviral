# Architecture

Viral Video Factory is a self-hosted orchestration repo that integrates two
upstream projects **without modifying them**:

- **wigolo** (AGPL-3.0) — local-first web search/fetch/extract over an MCP
  HTTP transport, run on the VPS as a protected service.
- **MoneyPrinterTurbo** (MIT) — AI short-video generator, run locally on the
  render PC.

## Topology

```
Admin dashboard -> API (VPS) -> Discovery worker -> wigolo
                 -> PostgreSQL candidates/sources (metadata only)
                 -> Admin approval -> Redis job queue
                 -> Local render agent (outbound HTTPS, long polling)
                 -> MoneyPrinterTurbo -> local video file (stays on PC)
                 -> agent reports progress + metadata + post URLs -> API
Dashboard preview: API <-Tailscale-> PC preview server (proxied stream, not stored)
Publish: agent -> YouTube / TikTok / Instagram (free official APIs)
```

## Principles (IMPLEMENTATION_PLAN.md §2)

- Never merge/heavily modify upstream wigolo and MoneyPrinterTurbo codebases.
- Build a new orchestration repo integrating them through adapters.
- VPS does discovery, admin, **metadata** storage, and orchestration. **It never stores rendered video files.**
- Local PC does GPU-heavy rendering, keeps the rendered file locally, and publishes it.
- The local PC exposes **no public inbound port**; it connects outward. Preview is delivered over a private **Tailscale** tailnet, proxied by the VPS (no storage).
- Admin approval gate is mandatory before rendering.
- Preserve source URLs, publication times, and evidence for every video.

## Packages

| Path | Role |
| --- | --- |
| `packages/contracts` | Pydantic schemas shared across services |
| `packages/database` | SQLAlchemy models + Alembic migrations + seed |
| `packages/shared` | config, logging, security utilities |
| `packages/prompt-templates` | research/validation/script prompt templates |
| `integrations/wigolo` | wigolo MCP client + result mapper |
| `integrations/money-printer-turbo` | MPT API adapter + output parser |
| `apps/api` | FastAPI: auth, research, render, agent protocol |
| `apps/discovery-worker` | Redis consumer: wigolo retrieval + scoring |
| `apps/local-render-agent` | Local PC service: claim -> MPT -> local file -> Tailscale preview -> publish |
| `apps/dashboard` | Next.js admin UI |
| `publishers/*` | YouTube/TikTok/Instagram official-API uploaders + manual fallback (run on the PC) |

## Data flow (happy path)

1. Admin creates a research run (`POST /api/v1/research-runs`).
2. Admin starts it (`POST /research-runs/{id}/start`) -> API enqueues a Redis job.
3. Discovery worker dequeues, runs wigolo searches, normalizes/dedups sources,
   scores candidates, persists the best 5, marks the run completed.
4. Admin reviews 5 candidates and approves one (`POST /candidates/{id}/approve`).
5. Admin creates an immutable render job (`POST /candidates/{id}/render-jobs`).
6. Local agent claims the job (`POST /agents/claim-job`), runs it via MPT,
   posts stage events, and completes by reporting metadata (local path, size,
   duration, provenance) — **the video file stays on the PC**.
7. Admin previews the video in the dashboard (VPS proxies a live stream from the
   PC over Tailscale; nothing is stored on the VPS).
8. Admin queues publish targets; the agent claims them, publishes from the PC via
   the platforms' free official APIs (or reports `manual_required`), and post URLs
   are recorded against the job.

## Security model

- Single-admin credentials + signed session cookies (MVP).
- Per-agent tokens issued at registration, stored only as SHA-256 fingerprints.
- LLM/TTS keys and publishing OAuth/refresh tokens live only in server/local encrypted env config.
- Publishing credentials never leave the render PC: they are not sent to the VPS, not stored in the database, and not included in publish outcomes.
- The PC preview server binds to the **Tailscale interface only** (never public); the VPS proxies but never stores the stream.
- Blocked-domain list + content risk flags; admin approval mandatory.
- Provenance manifest recorded for every output, including published post URLs per platform.
- AI-generated disclosure is set where the platform supports it (YouTube `containsSyntheticMedia`, TikTok `is_aigc`).
