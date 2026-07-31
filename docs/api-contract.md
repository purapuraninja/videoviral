# API Contract

Versioned REST under `/api/v1`. OpenAPI available at `/openapi.json` and
Swagger UI at `/docs` when the API is running.

## Auth

| Method | Path | Body | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | `{username,password}` | Issue session cookie + token |
| POST | `/api/v1/auth/logout` | — | Clear session |
| GET  | `/api/v1/auth/me` | — | Current admin (requires token) |

Admin endpoints expect `Authorization: Bearer <session_token>`.

## Research runs + candidates

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/research-runs` | Create a run |
| GET  | `/api/v1/research-runs` | List runs |
| POST | `/api/v1/research-runs/{id}/start` | Enqueue discovery |
| GET  | `/api/v1/research-runs/{id}` | Get run status |
| GET  | `/api/v1/research-runs/{id}/candidates` | List up to 5 candidates |
| POST | `/api/v1/candidates/{id}/approve` | Approve a candidate |
| POST | `/api/v1/candidates/{id}/reject` | Reject a candidate |

## Render profiles + jobs

| Method | Path | Purpose |
| --- | --- | --- |
| GET  | `/api/v1/render-profiles` | List presets |
| POST | `/api/v1/render-profiles` | Create a preset |
| POST | `/api/v1/candidates/{id}/render-jobs?profile_name=...` | Create immutable render job |
| GET  | `/api/v1/render-jobs/{id}` | Get job |
| POST | `/api/v1/render-jobs/{id}/cancel` | Cancel job |
| GET  | `/api/v1/render-jobs/{id}/events` | List job events |
| GET  | `/api/v1/render-jobs/{id}/outputs` | List output metadata (no files stored on VPS) |
| GET  | `/api/v1/render-jobs/{id}/preview` | Stream the video proxied from the PC over Tailscale (Range-supported; nothing stored) |
| GET  | `/api/v1/render-jobs/{id}/publish-targets` | List per-platform publish status + post URLs |
| POST | `/api/v1/render-jobs/{id}/publish` | Queue publish targets (platforms, mode, hashtags) |
| POST | `/api/v1/publish-targets/{id}/manual` | Record a hand-uploaded post URL (manual fallback) |
| POST | `/api/v1/publish-targets/{id}/retry` | Re-queue a failed/manual target |

## Local render agent protocol

Agents authenticate with `Authorization: Bearer <agent_token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/agents/register` | Register a local PC, get a token |
| POST | `/api/v1/agents/heartbeat` | Report health/disk/active job/Tailscale reachability |
| POST | `/api/v1/agents/claim-job` | Claim the oldest queued job |
| POST | `/api/v1/agents/jobs/{id}/events` | Post a stage event |
| POST | `/api/v1/agents/jobs/{id}/complete` | Complete by reporting metadata + local path (**no file upload**) |
| POST | `/api/v1/agents/jobs/{id}/fail` | Fail (optionally retryable) |
| POST | `/api/v1/agents/claim-publish` | Claim pending publish targets for a job whose video this PC holds |
| POST | `/api/v1/agents/jobs/{id}/publish-result` | Report platform + post URL (or `manual_required`) |

> Note: there is **no** artifact-upload endpoint. Rendered video never leaves the PC; the VPS stores metadata only and previews the file by proxying a Tailscale stream.
>
> Publishing also runs on the PC. `claim-publish` returns the local file path plus title/description/hashtags; the agent uploads to the platforms and reports outcomes. Platform credentials stay on the PC and are never sent to the VPS.

### Publish target lifecycle

```text
pending -> publishing -> published
                     \-> failed            (retryable from the dashboard)
                     \-> manual_required   (admin uploads by hand, records URL)
```

Render job publish statuses: `publishing`, `published`, `publish_failed`. A job
stays `publishing` while any target is `pending`, `publishing`, or
`manual_required`.

## Render job payload

See `packages/contracts/src/vvf_contracts/render.py` (`RenderJobPayload`).
Matches the example in IMPLEMENTATION_PLAN.md §10:

```json
{
  "job_id": "rj_...",
  "idempotency_key": "...",
  "candidate": { "title": "...", "facts": [...], "sources": [...] },
  "video": { "aspect_ratio": "9:16", "resolution": "1080x1920", "duration_seconds": 45, "language": "id-ID", "platforms": [...] },
  "creative": { "hook": null, "tone": "informative-fast", "voice": "id-ID-ArdiNeural", "subtitle_style": "bold-center", "music_profile": "news-modern", "video_source": "pexels" },
  "sources": [...]
}
```
