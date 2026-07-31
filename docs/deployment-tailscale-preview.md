# Checklist Deploy — M4: Preview via Tailscale (tanpa VPS storage)

Checklist untuk menerapkan perubahan M4 ke deployment yang sudah berjalan:

- **VPS**: `153.76.249.141` — Docker Compose stack + nginx (`api.` / `app.purapuraninja.my.id`), repo di `/opt/viral-video-factory/repo/vvf`
- **PC lokal**: MoneyPrinterTurbo (Docker, port 8080) + `vvf-local-agent` (Python host)

Hasil akhir: video hasil render **tetap di PC**, dashboard memutarnya lewat
stream proxied `/api/v1/render-jobs/{id}/preview`, dan **tidak ada file video yang tersimpan di VPS**.

---

## A. Tailscale (VPS + PC)

### A1. VPS
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4          # catat IP tailnet VPS, mis. 100.64.0.1
```

### A2. PC lokal (Windows)
1. Install Tailscale (https://tailscale.com/download/windows), login **akun/tailnet yang sama** dengan VPS.
2. PowerShell:
   ```powershell
   tailscale ip -4        # catat IP tailnet PC, mis. 100.64.0.2
   ```

### A3. Verifikasi konektivitas tailnet
```bash
# dari VPS:
ping 100.64.0.2          # IP tailnet PC
# dari PC (PowerShell):
ping 100.64.0.1          # IP tailnet VPS
```
Keduanya harus reply. Kalau tidak, cek akun sama + ACL di admin console Tailscale.

---

## B. Update VPS

### B1. Pull kode terbaru
```bash
cd /opt/viral-video-factory/repo/vvf
git pull
```

### B2. Deploy ulang stack (minio dihapus, volume /outputs dihapus)
```bash
bash scripts/deploy.sh
```
> Catatan: kalau ada container `minio` lama, berhenti otomatis karena sudah
> tidak ada di compose. Data lama `/opt/viral-video-factory/data/minio` dan
> `/opt/viral-video-factory/data/outputs` boleh dihapus manual (opsional,
> backup dulu kalau ragu):
> ```bash
> docker compose -f docker-compose.prod.yml rm -f -s minio 2>/dev/null || true
> sudo rm -rf /opt/viral-video-factory/data/{minio,outputs}
> ```

### B3. Migrasi DB (kolom baru: `agents.preview_base_url`, `video_outputs.agent_id`)
```bash
docker compose -f docker-compose.prod.yml exec -T api \
  bash -lc "cd /app/packages/database && alembic upgrade head"
```
Harapkan terlihat `0002_no_vps_storage` di output (migrasi ini no-op-safe).

### B4. Bersihkan nginx (opsional tapi disarankan)
Blok `location /outputs/ { ... }` di `/etc/nginx/sites-available/vvf` sudah
tidak dipakai (script yang menambahkannya sudah dihapus dari repo):
```bash
sudo nano /etc/nginx/sites-available/vvf   # hapus blok location /outputs/
sudo nginx -t && sudo systemctl reload nginx
```

---

## C. Update PC lokal

### C1. Pull + reinstall paket agent
```powershell
cd <repo>
git pull
pip install -e packages/contracts -e packages/shared -e integrations/money-printer-turbo -e apps/local-render-agent
```

### C2. Set env preview (penting: IP Tailscale PC, bukan 127.0.0.1)
```powershell
$env:VVF_API_URL      = "https://api.purapuraninja.my.id"
$env:VVF_AGENT_NAME   = "render-pc-01"
$env:MPT_BASE_URL     = "http://127.0.0.1:8080"
$env:VVF_PREVIEW_HOST = "100.64.0.2"          # IP tailnet PC (dari A2)
$env:VVF_PREVIEW_PORT = "8090"
$env:VVF_PREVIEW_ROOT = "C:\path\to\MoneyPrinterTurbo\storage\tasks"   # path ABSOLUT host, bukan di dalam container
```
> `VVF_PREVIEW_ROOT` harus menunjuk folder tasks MPT **di host** (yang di-mount
> ke container MPT). Kalau salah, preview akan 404 dan ukuran file tidak terdeteksi.
> Jangan pernah set `0.0.0.0` atau IP publik di `VVF_PREVIEW_HOST`.

### C3. Restart agent
```powershell
python -m vvf_local_agent.main
```
Log harus menunjukkan:
- `preview server listening on 100.64.0.2:8090 ...`
- `registered as agent ag_...` (re-register memperbarui `preview_base_url` di DB)

### C4. Verifikasi preview server dari VPS
Jalankan **dari dalam container API di VPS** (karena proxy jalan dari sana):
```bash
docker compose -f docker-compose.prod.yml exec -T api \
  python -c "import urllib.request; print(urllib.request.urlopen('http://100.64.0.2:8090/', timeout=5).status)"
```
`200`/`403`/`404` = koneksi OK (index dir apa pun). Timeout = cek Tailscale/ACL.

---

## D. Verifikasi end-to-end

1. Buat research run → approve kandidat → buat render job (pakai MPT asli, bukan mock).
2. Tunggu sampai job `completed`. Event `uploading` sekarang berbunyi `recording output metadata` — **tidak ada upload MP4 lagi**.
3. Di halaman job detail dashboard:
   - Pemutar `<video>` muncul dan bisa memutar video (stream via Tailscale, mendukung seek).
   - Daftar artifacts menampilkan `mp4 (preview)` + ukuran file.
4. Cek langsung endpoint proxy (Range):
   ```bash
   curl -I -H "Range: bytes=0-1023" -H "Cookie: vvf_session=<cookie>" \
     https://api.purapuraninja.my.id/api/v1/render-jobs/<job_id>/preview
   # harapkan: 206 Partial Content + Content-Range
   ```
5. Cek DB: `video_outputs` berisi `agent_id` terisi dan `local_path` berbentuk
   `<task_id>/final-1.mp4`; **tidak ada** file baru di mana pun di disk VPS.

## Troubleshooting

| Gejala | Penyebab umum |
| --- | --- |
| `<video>` tidak muncul | Agent register pakai `preview_base_url` kosong → `VVF_PREVIEW_HOST` masih `127.0.0.1` saat agent start. Set env lalu restart agent. |
| Preview 502 | VPS tidak bisa reach IP tailnet PC dari dalam container API (cek langkah C4). |
| Preview 404 | `VVF_PREVIEW_ROOT` salah sehingga `<task_id>/final-1.mp4` tidak ada di root; atau file MPT sudah dihapus. |
| Seek lambat/buffering | Tambahkan `proxy_buffering off;` di block nginx `location /api/` untuk `api.*`, lalu `nginx -t && systemctl reload nginx`. |
