# MoneyPrinterTurbo integration

Adapter around [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo),
an all-in-one AI short-video generator (script, footage, TTS, subtitles, music,
final render) exposed as a local FastAPI service on port 8080.

MPT runs **only on the local render PC** and is never exposed to the public
internet. The local render agent talks to it through this adapter; the upstream
codebase is **never** modified (MIT).

## API surface used

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/v1/videos`        | POST    | Create a render task from `MPTVideoParams` |
| `/api/v1/tasks/{id}`    | GET     | Poll state/progress/script/outputs |
| `/api/v1/tasks/{id}`    | DELETE  | Cancel/remove a task |
| `/api/v1/videos/script` | POST    | Generate an LLM script for a subject |
| `/api/v1/videos/terms`  | POST    | Generate search terms for a subject |
| `/api/v1/voices`        | GET     | List supported TTS voices |

## Task state mapping

MPT numeric states are normalized into VVF `RenderJobStatus`:

| MPT state | Meaning | VVF status |
| --- | --- | --- |
| `-1` | error | `failed` |
| `0`  | not started | `scripting` |
| `9`  | in progress | staged by progress (`assets`/`tts`/`rendering`/`uploading`) |
| `1`  | success | `completed` |

## Usage

```python
from vvf_contracts import RenderJobPayload
from vvf_mpt import MPTClient, MockMPTClient, MPTVideoParams

client = MockMPTClient()
params = MPTVideoParams.from_payload(payload, script="<script>")
task_id = client.create_video(params)
status = client.wait_for_completion(task_id)
```
