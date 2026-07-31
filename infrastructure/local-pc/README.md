# Local PC install notes

This directory documents how to install MoneyPrinterTurbo and the VVF local
render agent on the render PC. See `docs/deployment-local-pc.md` for the full
guide.

## Quick start

```bash
# 1. Clone and configure MoneyPrinterTurbo (separate repo, do not modify)
git clone https://github.com/harry0703/MoneyPrinterTurbo
cd MoneyPrinterTurbo
cp config.example.toml config.toml
# edit config.toml: listen_host=127.0.0.1, video_source, LLM + TTS keys
python main.py   # http://127.0.0.1:8080

# 2. In the VVF repo, install the local agent
pip install -e ./packages/contracts ./packages/shared \
            ./integrations/money-printer-turbo ./apps/local-render-agent

# 3. Run it
VVF_API_URL=https://api.your-vps.example VVF_AGENT_NAME=render-pc-01 vvf-local-agent
```

## Idempotency

The agent uses the render job's `idempotency_key` so that a network retry on
`claim-job` cannot create a duplicate rendered video.
