# VPS deployment

The VPS runs the VPS-side of the stack: PostgreSQL, Redis, MinIO, the FastAPI
API, the Next.js dashboard, wigolo, and the discovery worker.

> Use the development stack first: `docker compose -f docker-compose.dev.yml up --build`.

## Production checklist

1. **Set strong secrets** in `.env`:
   - `VVF_SECRET_KEY`, `VVF_ADMIN_PASSWORD`, `POSTGRES_PASSWORD`,
     `REDIS_PASSWORD`, `STORAGE_SECRET_KEY`.
2. **TLS**: terminate TLS with Caddy/Nginx in front of the API + dashboard.
   See `infrastructure/vps/Caddyfile.example`.
3. **Migrate + seed** after first boot:
   ```bash
   docker compose exec api python -m vvf_database.migrate upgrade head
   docker compose exec api python -m vvf_database.seed
   ```
4. **CORS**: set `VVF_CORS_ORIGINS` to the dashboard domain only.
5. **wigolo**: keep it bound to the compose network; do not publish its port
   publicly. The discovery worker reaches it via `http://wigolo:3000`.
6. **Backups**: snapshot the `postgres_data` and `minio_data` volumes.

## Notes

- Rendering never runs on the VPS. The local render agent lives on a separate
  PC and connects outward.
- The local PC has no inbound port; it polls `claim-job`.
