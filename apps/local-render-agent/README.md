# VVF local render agent

Runs **on the local PC** (never on the VPS). It does **not** expose a public
inbound port: it connects outward to the VPS API over HTTPS and claims render
jobs through long polling, then drives a local [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)
instance to produce the final 9:16 video.

## Responsibilities (IMPLEMENTATION_PLAN.md §11)

- authenticate with a per-agent token stored locally
- send heartbeat every 30 seconds
- claim only one job at a time (MVP)
- verify available disk and MPT health before claiming
- download the job payload and optional local assets
- invoke the MoneyPrinterTurbo adapter
- report each stage and append structured logs
- upload only final artifacts and selected debug files
- retry transient failures with exponential backoff
- never upload secret configuration or API keys
- use idempotency keys so a network retry cannot create duplicate videos

## Configuration (environment)

| Variable | Default | Purpose |
| --- | --- | --- |
| `VVF_API_URL` | `http://localhost:8000` | VPS API base URL |
| `VVF_AGENT_NAME` | `render-pc-01` | Agent display name |
| `VVF_AGENT_TOKEN` | (issued at first run) | Per-agent bearer token |
| `MPT_BASE_URL` | `http://127.0.0.1:8080` | Local MoneyPrinterTurbo URL |
| `VVF_HEARTBEAT_INTERVAL` | `30` | Heartbeat seconds |
| `VVF_POLL_INTERVAL` | `5` | claim-job poll seconds |
| `VVF_MPT_USE_MOCK` | `0` | `1` to use MockMPTClient |

## Run

```bash
pip install -e ./packages/contracts ./packages/shared ./integrations/money-printer-turbo ./apps/local-render-agent
vvf-local-agent
```
