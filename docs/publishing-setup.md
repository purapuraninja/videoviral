# Publishing setup (M6)

Publishing runs **on the render PC**, where the video file lives. The VPS never
receives video bytes and never stores platform credentials — it only records the
outcome (platform, status, post URL).

Every platform is optional. A platform with no credentials is reported as
`manual_required`: the admin downloads the video from the dashboard preview,
uploads it by hand, and pastes the post URL back into the dashboard. That path
needs no API access at all.

All variables below are set **on the PC** (e.g. in `scripts/start-agent-pc.ps1`
or the PC's environment), never in the VPS `.env`.

## How the flow works

1. Render finishes → job `completed`, video on the PC.
2. Admin opens the job, picks platforms + mode, clicks **Publish** →
   `POST /api/v1/render-jobs/{id}/publish` creates one `publish_target` per
   platform with status `pending`, job becomes `publishing`.
3. The agent's poll loop calls `POST /api/v1/agents/claim-publish`, receives the
   local path + metadata, and runs each publisher.
4. The agent reports outcomes via
   `POST /api/v1/agents/jobs/{id}/publish-result`.
5. Job resolves to `published` (at least one platform live, none outstanding),
   stays `publishing` while any target is `manual_required`, or becomes
   `publish_failed` if everything failed terminally.

Statuses per target: `pending → publishing → published`, or `failed`
(retryable via the dashboard) / `manual_required` / `skipped`.

## YouTube Shorts — YouTube Data API v3

Free. Quota: 100 uploads/day (each `videos.insert` costs 1 unit of the upload
bucket, 1600 units of the 10 000 daily quota).

1. Google Cloud Console → new project → enable **YouTube Data API v3**.
2. OAuth consent screen: External, add yourself as a test user.
3. Credentials → **OAuth client ID** → type *Desktop app*. Note the client ID and
   secret.
4. Get a refresh token once (scope `https://www.googleapis.com/auth/youtube.upload`).
   The OAuth Playground works: gear icon → *Use your own OAuth credentials* →
   authorize the scope → exchange the code → copy the **refresh token**.
5. Set on the PC:
   ```env
   VVF_YOUTUBE_CLIENT_ID=...apps.googleusercontent.com
   VVF_YOUTUBE_CLIENT_SECRET=...
   VVF_YOUTUBE_REFRESH_TOKEN=1//...
   VVF_YOUTUBE_CATEGORY_ID=25
   ```

**Restriction to expect:** projects created after 2020-07-28 that have not passed
Google's API audit have every uploaded video forced to **private**, regardless of
what we request. The upload still succeeds and we return the post URL. Request an
audit to lift it.

The publisher declares `containsSyntheticMedia: true` (AI-generated disclosure)
and `selfDeclaredMadeForKids: false`.

## TikTok — Content Posting API (Direct Post)

Free. Local bytes are supported via `FILE_UPLOAD`, so no hosting is needed.
Rate limits: 6 init calls/min, 30 status calls/min per user token.

1. developers.tiktok.com → create an app.
2. Add the **Content Posting API** product and enable **Direct Post**.
3. Request the `video.publish` scope; complete Login Kit so a user can authorize.
4. Obtain a **user access token** for the target account and set:
   ```env
   VVF_TIKTOK_ACCESS_TOKEN=act....
   VVF_TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE
   ```

**Restriction to expect:** until your app passes TikTok's audit, all posts are
forced to private (`SELF_ONLY`) and TikTok returns **no public post id**. The
publisher handles this: it queries `creator_info` first, downgrades
`privacy_level` to whatever the account actually allows, and — when no post id is
available — reports `manual_required` so you can record the real URL.

The publisher sets `is_aigc: true` (AI-generated content label) and honours the
account's `comment/duet/stitch` toggles, as TikTok's terms require.

Note: access tokens expire (typically 24 h) and need refreshing. Long-running
setups should store a refresh token and rotate it; currently the publisher uses
the access token as-is and reports `manual_required` if it is rejected.

## Instagram Reels — Instagram Graph API

Free, but the trickiest one.

**The constraint:** Meta cURLs media from a public URL when creating a container.
The only way to push local bytes is the resumable upload host
`rupload.facebook.com`, which Meta documents as available **only to apps using
Facebook Login for Business** with a Page access token. Apps on *Instagram Login*
(`graph.instagram.com`) must host the file at a public HTTPS URL — which this
project deliberately does not do.

So:

- **Facebook Login for Business** → automatic publishing works from the PC.
- **Instagram Login** → the publisher returns `manual_required`. Use the manual
  fallback (this is expected, not a bug).

Setup for the working path:

1. The Instagram account must be **professional** (Business or Creator) and
   connected to a Facebook Page.
2. developers.facebook.com → app → add **Instagram** (Facebook Login for
   Business).
3. Permissions: `instagram_basic`, `instagram_content_publish`,
   `pages_read_engagement`. Your user needs `MANAGE` or `CREATE_CONTENT` on the
   Page.
4. Get the Page access token and the Instagram user id, then set:
   ```env
   VVF_INSTAGRAM_ACCESS_TOKEN=EAA...
   VVF_INSTAGRAM_USER_ID=1784...
   VVF_INSTAGRAM_API_VERSION=v24.0
   VVF_INSTAGRAM_SHARE_TO_FEED=1
   ```

Limits: 100 API posts per account per 24 h; reels ≤ 300 MB, 3 s–15 min, max width
1920. Page Publishing Authorization on the connected Page blocks publishing until
completed, and there is no API to detect it.

## Manual fallback

Nothing to configure. When a target is `manual_required`:

1. Open the job in the dashboard and play/download the video (streamed from the
   PC over Tailscale).
2. Upload it to the platform by hand.
3. Paste the post URL into the target's field and click **Record URL** →
   `POST /api/v1/publish-targets/{id}/manual`. The target becomes `published`
   with `mode=manual`, and the URL is recorded against the job's provenance.

**Retry** re-queues a `failed`/`manual_required` target for another automatic
attempt (useful after adding credentials).

## Verify on the VPS

```bash
bash scripts/verify_m6_vps.sh            # schema, routes, auth, queue targets
bash scripts/publish_status.sh [job_id]  # per-platform status + post URLs
bash scripts/e2e_m6_manual.sh            # manual-fallback flow incl. URL validation
bash scripts/cleanup_publish_test.sh <job_id>   # undo verification runs
```

## Security notes

- Credentials live only in the PC's environment. They are never sent to the VPS,
  never written to the database, and never included in a publish outcome (there
  is a test asserting a token cannot leak into an outcome).
- Publish outcomes carry only platform, status, post URL/id, and an error string.
- The publish endpoints require an admin session; the agent protocol uses its own
  per-agent bearer token.
