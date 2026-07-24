# 🎬 DocuForge

> AI-powered documentary/shorts/news video production platform.

DocuForge turns a topic into a finished MP4 through a single 11-stage pipeline:

1. Research
2. Script
3. Storyboard
4. Image Prompts
5. Video Prompts
6. Narration
7. SEO Metadata (title suggestions, description, tags)
8. Media Builder (Pexels image/video download)
9. Scene Narrations
10. Voice Generation (TTS)
11. FFmpeg Render

An optional 12th stage (**Thumbnail**) runs when enabled on the project.

---

# Features

## Working

- ✅ DeepSeek text generation — via a Provider Registry
- ✅ Image/video: Pexels, Pixabay, Unsplash (free stock) plus DALL-E, Google Imagen/Veo, and fal.ai (Flux/Kling/hundreds more) for AI generation — selectable in the web wizard, `MediaBuilder` resolves whichever is configured with no code changes needed
- ✅ Generation providers get fed the *right* prompt: `image_prompts.json`/`video_prompts.json` (from ImagePromptAgent/VideoPromptAgent) were being generated but silently discarded — `MediaBuilder` now uses each scene's richer AI-crafted prompt (video prompts also fold in `camera_motion`) when the configured provider is a generator, falling back to the storyboard's short `visual` text otherwise. Stock providers (pexels/pixabay/unsplash) still get that short search-style query unchanged, since a full generation prompt makes a poor keyword search.
- ✅ Modular Agent Architecture + Build Pipeline with resume (`pipeline_state.json`)
- ✅ Content settings that actually change agent/pipeline behavior, not just metadata:
  - `content_type` (documentary / news / shorts / informational) shapes the research, script, storyboard and narration prompts differently per type
  - `target_duration_seconds` drives script length and storyboard scene count/duration targets
  - For documentary/informational content, the storyboard's last scene is instructed to be a genuine closing shot (a wide, symbolic composition that resolves the story, still tied to the actual topic) rather than just another topic-illustrating scene -- flows through to image/video generation unchanged since it's just a `visual` field like any other scene's
  - `media_mode` (video / image / mixed) controls what MediaBuilder actually fetches
  - `resolution` (720p / 1080p / vertical / 4k) and `fps` are read by RenderService and used in the real FFmpeg filters — nothing is hardcoded
- ✅ AI topic suggestions on `/new`: a "💡 Konu Önerisi Al" button next to the manual topic field calls `TopicSuggestionAgent` (DeepSeek), which returns 8 title ideas tailored to the selected content type/language, each with a one-line click-through hook and an optional split-contrast visual hint (left/right). Ordered best-to-worst, top 3 get a medal callout. Clicking a suggestion fills the topic field -- manual entry is untouched, this is purely an assist
- ✅ Voice: eSpeak, Piper (Turkish Fahrettin model), Supertonic (M1–M5 / F1–F5), **XTTS voice clone** — provider, voice name and speed are all honored
- ✅ Turkish TTS text normalization (`app/utils/tr_tts_normalize.py`, no dependencies): numbers, ordinals, decimals, percentages, times, dates, temperatures, currency/unit abbreviations and institution acronyms are spelled out into correct Turkish words — with the right dative/locative/ablative/genitive suffix attached — right before the text reaches *any* voice provider (`VoiceService.generate()` is the single chokepoint, so this applies uniformly across eSpeak/Piper/Supertonic/XTTS). Ported from the same fix already running in production in the Instagram bot project
- ✅ Background music: if `background_music_enabled` is set, it's looped/trimmed to the video length, mixed in below narration volume, and faded out. Source is either a local file (`projects/<slug>/music/` or an explicit `music_track` path/URL) or a `music_provider`: `local` (default), `jamendo` (royalty-free search API) or `mubert` (AI-generated music from a mood prompt derived from `content_type`) — selectable per-project from the wizard or the render step's "Yeniden Üret" form; API keys go in `/settings`
- ✅ Listen-and-pick music browser, on both `/new` **and** the project page's "Yeniden Üret" for the render step (Jamendo is the default music provider once "Arka Plan Müziği Ekle" is checked): a "🎧 Ara" search box calls `GET /api/music-search` (defaults the query to a content-type mood if left blank) and lists candidate tracks with an inline `<audio>` preview player, artist, duration, and license. Picking one sets `music_track` to that track's direct download URL, which `RenderService` downloads at render time instead of running the automatic mood-based search — the automatic per-content-type search is still the fallback whenever nothing is explicitly picked. Below the search box, `GET /api/music-mood` returns a handful of short, individual topic-relevant English mood tags (one lightweight DeepSeek call, falls back to the plain content-type mood split into words if it fails) rendered as clickable chips whenever the topic changes; clicking a chip appends it to the search box instead of overwriting it, since Jamendo's tag search matches much better on a couple of short standalone tags than on one long AND-ed phrase
- ✅ Jamendo license awareness: `JamendoMusicProvider` parses each track's `license_ccurl` into a plain-language label and a `commercial_ok` flag (Jamendo's catalog mixes CC BY/BY-SA/BY-ND, which are fine for a monetized YouTube channel, with CC BY-NC variants, which aren't). Confirmed non-commercial tracks are dropped from results entirely (not just badged); tracks with an undetermined license still show with a ⚠️ badge. Jamendo search also tries progressively looser strategies (`fuzzytags` → `search` → no filter) since a strict tag match came back empty far more often than not
- ✅ ElevenLabs Music provider (`ElevenLabsMusicProvider`, `POST /v1/music`): unlike Jamendo/Mubert's catalog search, every result is a real, billed AI generation -- purpose-built for "ambient background, no vocals" rather than Jamendo's general song catalog. The query is wrapped in an ambient/no-vocals/documentary-underscore framing before being sent as the prompt. A fixed 90-second track is generated (long enough to loop via the render step's existing `-stream_loop -1`, short enough to keep cost/latency down) and cached to disk by a hash of (prompt, duration) so repeating a search or an automatic render-time pick reusing the same query never re-generates. Selectable as a `music_provider` alongside Jamendo/Mubert; the listen-and-pick browser dispatches to it via `GET /api/music-search?provider=elevenlabs` and serves cached previews from `GET /music-cache/elevenlabs/{filename}`
- ✅ Freesound provider (`FreesoundMusicProvider`, `GET /apiv2/search/text/`): a free, Creative-Commons community audio library -- unlike Jamendo's independent-musician song catalog, most Freesound content is field recordings/atmospheres/sound design, i.e. actual "fon sesi" rather than song-structured tracks. Filters to results at least 15s long by default (skipping one-shot SFX blips), falling back to an unfiltered search if that comes up empty. Same non-commercial-license filtering as Jamendo (CC BY-NC/Sampling+ dropped from results entirely). No generation cost -- a real catalog search like Jamendo, not billed per-request like ElevenLabs
- ✅ Music volume control: a `music_volume` slider (0-50%, default 18%) next to the music provider picker sets how loud the background track plays relative to the narration in the ffmpeg `amix` mix -- previously hardcoded at a fixed 18% with no way to adjust it. `amix` now also runs with `normalize=0` -- its default auto-normalize was silently rebalancing (boosting) the music during narration pauses, undermining whatever level was actually set
- ✅ Music swell into the ending: instead of a flat volume until the final fade-out, the last few seconds ramp the music up to roughly 2.5x the base level (capped at 55%) before the existing fade-out carries it to silence -- a "swell into the ending" rather than an abrupt cut. Scene-to-scene gaps are too short (~0.35s) for a swell to read as anything but a glitch, so this only targets the one genuinely quiet stretch: after narration has finished. Falls back to the flat volume on very short videos without enough tail room. A music-mixing failure of any kind (bad track, ffmpeg filter issue) now degrades to a video without music instead of failing the whole render
- ✅ Subtitles: if `subtitles_enabled` is set, a scene-timed `subtitles.srt` is written next to the final video, along with a plain-paragraph `subtitles.txt` transcript (same narration, no timestamps/chunking, for copy-paste into a description or offline reading) — both downloadable from the project page; if `subtitles_burn_in` is also set, a second FFmpeg pass burns the `.srt` into the video itself (`subtitles` filter, libass) with a semi-transparent dark box behind the text (`BorderStyle=3`) rather than just a thin outline, since the outline alone wasn't reliably readable over bright/busy scenes, instead of leaving it as a sidecar file
- ✅ Thumbnail: if `thumbnail_enabled` is set, DocuForge produces high-CTR compositions from `thumbnail_source`: `split_contrast`, `mystery_focus`, `documentary_cinematic`, `breaking_discovery` — each with its own crop, color grade, gradient/vignette/blur treatment, and text placement, never just the same layout with the text moved. `thumbnail_source` controls where the background comes from and, deliberately, how many variants get made: `ai` (DALL-E, per-template prompt from an SEO creative brief) generates only **1** variant to keep the paid API cost fixed and low; `pexels` (stock photo search) and `scene` (the strongest real scene frame, auto-picked via a Pillow edge/contrast heuristic) are free and generate all **4**. `auto` (default) picks whichever free source is configured before ever defaulting to the paid one. On-image text is always a short 3-6 word hook (never the full title), drawn locally with Pillow (bold font, stroke, shadow, auto-shrink-to-fit instead of truncating) so Turkish diacritics render correctly. One variant becomes the canonical `thumbnail.jpg`, and the project page shows every generated variant side by side to download or pick from
- ✅ Project deletion: `DELETE /api/projects/{slug}` removes a project directory entirely (refuses while a build/regenerate job for it is still running); a confirm-guarded "🗑 Sil" button is available both on the dashboard project cards and the project detail page
- ✅ SEO Metadata: `seo.json` with 3 title suggestions, a full description, 10-20 tags, and a thumbnail creative brief (`thumbnail_hook`, `main_subject`, `emotional_trigger`, `visual_contrast`, `text_overlay`, `avoid_elements`) — generated from the finished script and shown on the project detail page
- ✅ FastAPI web panel (not Flask): project list (with a "+ Yeni Proje" link and a live "⏳ Devam eden üretimler" section), project detail with a video player, thumbnail preview, subtitle download, and a new-project wizard exposing content type, duration, media mode, resolution, fps, voice settings, and the music/subtitles/thumbnail toggles
- ✅ Installable as a PWA on iOS/Android (`app/static/manifest.json` + `sw.js`, served via `/static`) — "Add to Home Screen" gives a standalone, full-screen icon. The service worker deliberately only cache-first's the static shell (manifest/icons); every page and `/api/`/`/files/` request always goes straight to the network, since DocuForge's HTML *is* live job/project state and must never be served stale. Requires HTTPS in front of the app (a plain reverse proxy over HTTP won't register a service worker, `localhost` excepted)
- ✅ Per-stage regenerate from the web UI: each stage has its own "Yeniden Üret" button that invalidates that stage plus everything downstream of it and regenerates just that stage immediately, so you can review it before continuing with "▶ Devam Et". Each step now also shows when it last finished (converted to Europe/Istanbul time), so it's obvious whether a "completed" step reflects your latest change or an older run -- there was previously no way to tell the two apart from duration alone. Steps with settings worth changing (voice, media, render, research) show an editable form first — pick a different voice, a different image/video provider, a different resolution, etc. — instead of blindly rerunning with the same values
- ✅ Job state survives a web service restart: builds *and* per-stage regenerations are persisted to `jobs/<job_id>.json` and resumed automatically on startup instead of silently vanishing. In-progress jobs are visible from `/` and `/new` regardless of which page started them, polling `/api/jobs/active` every few seconds — so navigating away and back no longer looks like the build vanished
- ✅ Creating a project with a title that collides with an existing one gets a `_2`, `_3`, ... suffix instead of silently overwriting it
- ✅ `/settings` page for API keys (DeepSeek, Pexels, Pixabay, Unsplash, OpenAI, Google, fal.ai, XTTS reference audio, closing image) — no `.env` editing or restart needed
- ✅ Uploadable documentary closing image: an alternative to the AI-generated closing shot (above) for anyone who wants one consistent, hand-designed ending (e.g. made in ChatGPT/DALL-E) across every video instead of a fresh one each time. Upload it once in `/settings`, then flip the separate "Belgesellerin sonuna ekle" switch on -- uploading alone isn't enough, the switch is the actual on/off for whether it gets used, so a design can sit there ready without affecting renders until you deliberately turn it on. When on, `RenderService` swaps it in for the last scene's visual on any `documentary` project -- narration audio for that scene is untouched, only the image changes. Off by default; "Değiştir" replaces the uploaded image any time
- ✅ Selectable scene transitions: `scene_transition` (`cut` / `crossfade` / `fade_black`, default `crossfade`) controls how consecutive scenes are joined, set on `/new` or changed via the render step's "Yeniden Üret". Crossfade/fade_black merge clips **pairwise** (the running combined clip so far + the next scene) rather than feeding every clip into one ffmpeg filtergraph at once -- the single-pass version OOM-killed a real 23-scene render (~5.6GB RSS in one ffmpeg process), so peak memory now stays roughly constant regardless of scene count at the cost of more total encode time on long videos
- ✅ Automatic cold open: for documentary/informational/news videos with enough scenes, the storyboard agent flags the single most visually striking scene (never the first or last) as `hook_worthy`; RenderService trims a short muted teaser off that scene's own clip and hard-cuts it onto the front of the video before the real opening. Falls back silently (no cold open) on any failure. Subtitle timestamps account for both the cold-open offset and the timeline-shortening effect of scene transitions -- they're computed from each scene's real start time in the rendered output, not a naive sum of raw scene durations
- ✅ Render output validation: a render interrupted mid-encode (OOM kill, service restart, disk full) can leave a truncated MP4 that's non-empty on disk but has no moov atom and won't play. `RenderService.is_valid_output()` (ffprobe-based) is now part of the resume/regenerate completeness check, so a broken file gets correctly re-rendered instead of silently accepted as finished output
- ✅ Bolder thumbnail text (all 4 templates: bigger font, thicker outline, shadow scaled to font size, a translucent highlight bar behind text on busier backgrounds) and a `thumbnail_hook_override` field -- pick one of the SEO agent's suggested titles from a dropdown when regenerating the thumbnail step, and the cover's on-image text matches that exact title instead of a separately-generated hook
- ✅ `/storage` page: disk usage, RAM usage (`/proc/meminfo`), and per-project disk footprint (sorted largest-first) with a delete button reusing the existing project-delete endpoint -- linked from every page's header. `/settings/{field}/clear` for file-backed settings (XTTS reference audio, closing image) now deletes the underlying file too, not just the config pointer

## Not implemented yet

- ❌ Piper crackle/audio-quality cleanup (loudnorm, crossfade, DC offset)
- ❌ None of the new AI generation providers (DALL-E, Imagen, Veo, fal.ai) have been exercised against live traffic in this codebase — verified against documented API shapes with mocked HTTP only. Try each with a real key before depending on it.
- ❌ YouTube upload (SEO metadata is generated but nothing pushes it or the video to YouTube)

---

# Installation

```bash
git clone https://github.com/hakanerbasss/DocuForge.git
cd DocuForge

python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The web panel additionally needs `fastapi`, `uvicorn` and `pydantic` (not yet pinned in `pyproject.toml` — install manually):

```bash
pip install fastapi uvicorn pydantic python-multipart
```

FFmpeg and ffprobe must be available on `PATH`. For Piper/Supertonic voices, see their respective setup docs under `models/`.

For the XTTS voice-clone provider (optional, only needed if you select `voice_provider: xtts`):

```bash
pip install coqui-tts torch torchaudio
```

This is a heavy dependency (torch) — nothing else in DocuForge needs it, so it's not in `pyproject.toml` by default. XTTS-v2 also needs considerably more RAM than the rest of the pipeline; if it's fighting for memory with everything else on the same box, that will show up as the model failing to load rather than a clear error.

---

# Configuration

Create a `.env` file:

```env
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=YOUR_KEY
PEXELS_API_KEY=YOUR_KEY

# Optional overrides
TEXT_PROVIDER=deepseek
IMAGE_PROVIDER=pexels
VIDEO_PROVIDER=pexels
VOICE_PROVIDER=local_tts
MODEL=deepseek-v4-flash

# Only needed for voice_provider: xtts
XTTS_REFERENCE_AUDIO=/path/to/your/reference_voice.wav

# Only needed for the image/video providers you actually select
PIXABAY_API_KEY=YOUR_KEY          # image_provider/video_provider: pixabay
UNSPLASH_ACCESS_KEY=YOUR_KEY      # image_provider: unsplash
OPENAI_API_KEY=YOUR_KEY           # image_provider: dalle (separate from DEEPSEEK_API_KEY)
GOOGLE_API_KEY=YOUR_KEY           # image_provider: google_imagen, video_provider: google_veo
FAL_KEY=YOUR_KEY                  # image_provider/video_provider: fal
```

If `XTTS_REFERENCE_AUDIO` isn't set, the XTTS provider falls back to
`models/xtts/reference.wav` relative to the working directory. Either way, you
need a 20–30s clean recording of the voice to clone (same approach as the
`ses-klonu` reference audio in the Instagram bot project).

Pixabay and Unsplash are free (rate-limited); DALL-E, Google Imagen/Veo, and fal.ai
charge per generation — check current pricing before turning one on for a real
project. None of the five have been tested against a live account in this codebase;
see [ARCHITECTURE.md](ARCHITECTURE.md) for what was and wasn't verified.

All of the keys above can also be entered from the web panel at `/settings` instead of
editing `.env` — they're written to `secrets.json` (gitignored) and take effect
immediately, no restart needed. An env var with the same name always wins over
whatever's saved through the settings page.

---

# CLI Commands

```bash
docuforge version

# Full pipeline (basic options only — see the web wizard for full settings)
docuforge build "Black Holes" --language tr --template documentary

# Resume an interrupted/incomplete project
docuforge resume projects/black_holes

# Individual stages
docuforge research projects/black_holes
docuforge script projects/black_holes
docuforge storyboard projects/black_holes
docuforge images projects/black_holes
docuforge videos projects/black_holes
docuforge narration projects/black_holes
docuforge media projects/black_holes
docuforge narration-scenes projects/black_holes
docuforge voice projects/black_holes
docuforge render projects/black_holes
```

Note: `docuforge build` only exposes `--language`/`--template` today. The full settings
(`target_duration_seconds`, `media_mode`, voice/resolution/fps, music/subtitles/thumbnail
toggles) are only reachable through the web wizard's `POST /api/builds`, or by writing a
`project.json` by hand and running `docuforge resume`.

---

# Web Panel

FastAPI app, served with uvicorn:

```bash
uvicorn app.web:app --host 0.0.0.0 --port 8090
```

In production this typically runs as a systemd service (e.g. `docuforge-web.service`).

**PWA / HTTPS:** uvicorn itself serves plain HTTP. For the manifest+service-worker to actually register (a browser requirement, not something DocuForge can work around) put a reverse proxy in front with a real TLS certificate -- e.g. nginx + `certbot --nginx -d your.domain.com` proxying to `127.0.0.1:8090`, or a domain proxied through Cloudflare (any SSL/TLS mode works; "Full (strict)" additionally needs a valid cert on the origin, which is exactly what certbot provides). Without HTTPS in front, the site still works fine in a normal browser tab -- it just won't be installable as a home-screen app.

Routes:

- `GET /` — project list, with a "+ Yeni Proje" button
- `GET /projects/{slug}` — project detail: pipeline progress per stage (with a "Yeniden
  Üret" button each), final video player, thumbnail preview, subtitle download, a
  "▶ Devam Et" (resume) button
- `GET /files/{slug}/{file_path}` — serve project files (e.g. the rendered video)
- `GET /new` — new-project wizard (content type, duration, media mode, resolution, fps,
  voice provider/name/speed including xtts, background music/subtitles/thumbnail toggles)
- `POST /api/builds` — start a build; runs in a background thread, state persisted to
  `jobs/<job_id>.json`
- `GET /api/builds/{job_id}` — poll build/regenerate/resume progress (reads
  `pipeline_state.json`)
- `GET /api/jobs/active` — every still-running job with live progress, read from disk
  state (not tied to any one page's in-memory job_id). The dashboard polls this every
  4s and shows a "⏳ Devam eden üretimler" section — so navigating away from `/new` and
  back to `/` no longer looks like the build vanished, since it was never actually tied
  to that page in the first place (it's a background thread; only the *visibility* was
  missing before)
- `GET /api/projects/{slug}/step-options/{step_key}` — which project.json fields can be
  changed before regenerating this step (per `STEP_ALLOWED_OVERRIDES`), their current
  values, and — for provider fields — the choices actually registered right now. Drives
  the "Yeniden Üret" form on the project page
- `POST /api/projects/{slug}/regenerate/{step_key}` — body `{"overrides": {...}}`
  (optional, defaults to `{}`); invalidates one stage and everything downstream of it,
  applies any overrides to project.json first, then regenerates just that stage.
  Unknown override keys for the given step are rejected with 400
- `POST /api/projects/{slug}/resume` — continue an existing project from its first
  incomplete stage
- `GET /settings` — API key management (DeepSeek, Pexels, Pixabay, Unsplash, OpenAI,
  Google, fal.ai, XTTS reference audio path); linked from the header on every page
- `POST /settings/{field_key}`, `POST /settings/{field_key}/clear` — save/clear a key,
  written to `secrets.json` and applied immediately (no restart needed). An env var
  with the same name always takes priority and can't be overridden from this page.

---

# Output Structure

```
projects/
└── black_holes/
    ├── project.json
    ├── pipeline_state.json
    ├── research.md
    ├── script.md
    ├── storyboard.json
    ├── image_prompts.json
    ├── video_prompts.json
    ├── narration.txt
    ├── media/
    │   └── scene_001/, scene_002/, ...
    ├── audio/
    │   └── manifest.json
    ├── music/                 # optional, drop an mp3/wav here
    ├── thumbnail.jpg          # if thumbnail_enabled
    ├── thumbnail_vertical.jpg # shorts/vertical projects only
    └── render/
        ├── clips/
        ├── final_video.mp4
        └── subtitles.srt      # if subtitles_enabled
```

---

# Pipeline

```
Topic
  │
  ▼
Research → Script → Storyboard → Image Prompts → Video Prompts → Narration
  │
  ▼
Media Builder → Scene Narrations → Voice Generation → FFmpeg Render → [Thumbnail]
```

`BuildPipeline` runs agent stages first, then service stages. Each stage's output file
is checked before re-running it, so `resume()` skips whatever is already done.

---

# Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md).

---

# License

MIT License
