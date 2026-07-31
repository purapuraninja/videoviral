# Local PC deployment

The local render PC runs MoneyPrinterTurbo and the VVF local render agent. It
connects **outward** to the VPS API over HTTPS; it exposes no public port. The
rendered video **stays on this PC** — it is previewed by the dashboard over
Tailscale and published to platforms directly from here.

## Prerequisites

- Python 3.11+ (verified deployment currently runs 3.14)
- [Tailscale](https://tailscale.com/) installed and joined to the same tailnet as the VPS (for dashboard preview)
- MoneyPrinterTurbo installed and `config.toml` configured
  (see https://github.com/harry0703/MoneyPrinterTurbo). For Indonesian 9:16
  videos set `video_aspect = "9:16"` and an Edge TTS voice like
  `id-ID-ArdiNeural`.
- ffmpeg available on PATH (or `ffmpeg_path` in MPT's config.toml).
- Disk headroom for rendered MP4s.

## Steps

0. **Join the tailnet (required for dashboard preview).**
   - Install Tailscale on this PC and on the VPS, and log both into the same tailnet.
   - Get this PC's Tailscale IPv4: `tailscale ip -4` (e.g. `100.x.y.z`).
   - Set `VVF_PREVIEW_HOST` to that IP so the read-only preview server binds only to
     the Tailscale interface (never a public interface). The VPS proxies
     `https://api.<domain>/api/v1/render-jobs/{id}/preview` to this server.
1. Install VVF packages editable:
   ```bash
   pip install -e ./packages/contracts ./packages/shared \
               ./integrations/money-printer-turbo ./apps/local-render-agent
   ```
2. Start MoneyPrinterTurbo locally:
   ```bash
   cd MoneyPrinterTurbo && python main.py    # listens on 127.0.0.1:8080
   ```
   The rendered MP4s live under `MoneyPrinterTurbo/storage/tasks/<task_id>/`.
3. Configure the agent (env or `.env`):
   ```env
   VVF_API_URL=https://api.your-vps.example
   VVF_AGENT_NAME=render-pc-01
   MPT_BASE_URL=http://127.0.0.1:8080
   VVF_HEARTBEAT_INTERVAL=30
   VVF_POLL_INTERVAL=5
   # Tailscale preview (bind the read-only server to the Tailscale interface only)
   VVF_PREVIEW_HOST=100.x.y.z            # this PC's Tailscale IPv4
   VVF_PREVIEW_PORT=8090
   VVF_PREVIEW_ROOT=MoneyPrinterTurbo/storage/tasks
   ```
   Set these four values before first run and re-run so the VPS learns the
   `preview_base_url` during registration.
4. Run the agent:
   ```bash
   vvf-local-agent
   ```
   On first run it registers and prints/uses its per-agent token. Subsequent
   runs reuse `VVF_AGENT_TOKEN` (issue a fresh one via re-registration if lost).

## Verification

- Heartbeats appear in the dashboard's Agent Monitor.
- When an admin approves a candidate + creates a render job, the agent claims
  it, drives MPT, and reports the final metadata (local path, size, duration,
  provenance) back — **the MP4 stays on this PC and is not uploaded**.
- The dashboard preview plays the video by streaming it from this PC over
  Tailscale (VPS reverse-proxy). Ensure the PC's preview server is bound to the
  Tailscale interface only.
- (M6) Publishing posts the video to the configured platforms and records the
  resulting post URLs against the job.
