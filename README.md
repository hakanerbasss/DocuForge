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
  - `media_mode` (video / image / mixed) controls what MediaBuilder actually fetches
  - `resolution` (720p / 1080p / vertical / 4k) and `fps` are read by RenderService and used in the real FFmpeg filters — nothing is hardcoded
- ✅ Voice: eSpeak, Piper (Turkish Fahrettin model), Supertonic (M1–M5 / F1–F5), **XTTS voice clone** — provider, voice name and speed are all honored
- ✅ Background music: if `background_music_enabled` is set and an audio file exists in `projects/<slug>/music/` (or an explicit `music_track` path), it's looped/trimmed to the video length, mixed in below narration volume, and faded out
- ✅ Subtitles: if `subtitles_enabled` is set, a scene-timed `subtitles.srt` is written next to the final video (sidecar only — not burned into the video yet)
- ✅ Thumbnail: if `thumbnail_enabled` is set, a 1280x720 YouTube thumbnail is generated from a scene frame with a title overlay (plus a 1080x1920 cover for shorts/vertical projects) — pure FFmpeg, no extra dependency
- ✅ SEO Metadata: `seo.json` with 3 title suggestions, a full description, and 10-20 tags, generated from the finished script and shown on the project detail page
- ✅ FastAPI web panel (not Flask): project list (with a "+ Yeni Proje" link), project detail with a video player, thumbnail preview, subtitle download, and a new-project wizard exposing content type, duration, media mode, resolution, fps, voice settings, and the music/subtitles/thumbnail toggles
- ✅ Per-stage regenerate from the web UI: each stage has its own "Yeniden Üret" button that invalidates that stage plus everything downstream of it and regenerates just that stage immediately, so you can review it before continuing with "▶ Devam Et"
- ✅ Job state survives a web service restart: builds *and* per-stage regenerations are persisted to `jobs/<job_id>.json` and resumed automatically on startup instead of silently vanishing
- ✅ Creating a project with a title that collides with an existing one gets a `_2`, `_3`, ... suffix instead of silently overwriting it

## Not implemented yet

- ❌ Subtitle burn-in (currently sidecar `.srt` only)
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
MODEL=deepseek-chat

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
- `POST /api/projects/{slug}/regenerate/{step_key}` — invalidate one stage and everything
  downstream of it, then regenerate just that stage
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
