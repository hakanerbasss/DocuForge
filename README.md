# 🎬 DocuForge

> AI-powered documentary/shorts/news video production platform.

DocuForge turns a topic into a finished MP4 through a single 10-stage pipeline:

1. Research
2. Script
3. Storyboard
4. Image Prompts
5. Video Prompts
6. Narration
7. Media Builder (Pexels image/video download)
8. Scene Narrations
9. Voice Generation (TTS)
10. FFmpeg Render

An optional 11th stage (**Thumbnail**) runs when enabled on the project.

---

# Features

## Working

- ✅ DeepSeek text generation, Pexels image/video search — via a Provider Registry
- ✅ Modular Agent Architecture + Build Pipeline with resume (`pipeline_state.json`)
- ✅ Content settings that actually change agent/pipeline behavior, not just metadata:
  - `content_type` (documentary / news / shorts / informational) shapes the research, script, storyboard and narration prompts differently per type
  - `target_duration_seconds` drives script length and storyboard scene count/duration targets
  - `media_mode` (video / image / mixed) controls what MediaBuilder actually fetches
  - `resolution` (720p / 1080p / vertical / 4k) and `fps` are read by RenderService and used in the real FFmpeg filters — nothing is hardcoded
- ✅ Voice: eSpeak, Piper (Turkish Fahrettin model), Supertonic (M1–M5 / F1–F5) — provider, voice name and speed are all honored
- ✅ Background music: if `background_music_enabled` is set and an audio file exists in `projects/<slug>/music/` (or an explicit `music_track` path), it's looped/trimmed to the video length, mixed in below narration volume, and faded out
- ✅ Subtitles: if `subtitles_enabled` is set, a scene-timed `subtitles.srt` is written next to the final video (sidecar only — not burned into the video yet)
- ✅ Thumbnail: if `thumbnail_enabled` is set, a 1280x720 YouTube thumbnail is generated from a scene frame with a title overlay (plus a 1080x1920 cover for shorts/vertical projects) — pure FFmpeg, no extra dependency
- ✅ FastAPI web panel (not Flask): project list, project detail with a video player, and a new-project wizard exposing content type, duration, media mode, resolution, fps, voice settings, and the music/subtitles/thumbnail toggles
- ✅ Job state survives a web service restart: builds are persisted to `jobs/<job_id>.json` and resumed automatically on startup instead of silently vanishing
- ✅ Creating a project with a title that collides with an existing one gets a `_2`, `_3`, ... suffix instead of silently overwriting it

## Not implemented yet

- ❌ Subtitle burn-in (currently sidecar `.srt` only)
- ❌ XTTS voice cloning
- ❌ Piper crackle/audio-quality cleanup (loudnorm, crossfade, DC offset)
- ❌ A second image/video provider (only Pexels exists today, so `image_provider`/`video_provider` have nothing else to select)
- ❌ Title/description/tag generation, YouTube upload

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
pip install fastapi uvicorn pydantic
```

FFmpeg and ffprobe must be available on `PATH`. For Piper/Supertonic voices, see their respective setup docs under `models/`.

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
```

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

- `GET /` — project list
- `GET /projects/{slug}` — project detail, pipeline progress, final video player
- `GET /files/{slug}/{file_path}` — serve project files (e.g. the rendered video)
- `GET /new` — new-project wizard (content type, duration, media mode, resolution, fps,
  voice provider/name/speed, background music/subtitles/thumbnail toggles)
- `POST /api/builds` — start a build; runs in a background thread, state persisted to
  `jobs/<job_id>.json`
- `GET /api/builds/{job_id}` — poll build progress (reads `pipeline_state.json`)

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
