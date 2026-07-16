# 🏗 DocuForge Architecture

## Overview

DocuForge is an AI-powered video production platform. A project moves through two
kinds of stages: **AI agent stages** (text generation, one prompt per stage) and
**production service stages** (media download, TTS, FFmpeg render). Both are
orchestrated by `BuildPipeline` and both use the same resume mechanism.

```
Topic
  │
  ▼
Research → Script → Storyboard → Image Prompts → Video Prompts → Narration   (agents)
  │
  ▼
Media Builder → Scene Narrations → Voice Generation → FFmpeg Render → [Thumbnail]  (services)
```

---

# Project Structure

```
app/
├── agents/       # BaseAgent + one class per AI-generation stage
├── ai/           # AI provider clients (DeepSeek) and factory
├── cli/          # (currently unused; CLI lives in main.py)
├── core/         # Settings (env vars)
├── models/       # DocumentaryProject dataclass
├── pipeline/     # BuildPipeline, step definitions, agent registry wiring
├── prompts/      # Jinja2 prompt templates, one per agent
├── providers/    # ProviderRegistry + text/image/video/voice provider implementations
├── services/     # Non-agent production stages (see below)
├── utils/        # Shared helpers (prompt loading, etc.)
├── main.py       # Typer CLI
├── web.py        # FastAPI app: project list/detail/file serving
└── web_new_project.py  # FastAPI router: new-project wizard + build job API
```

---

# Agent Layer

All agents inherit from `BaseAgent`, which provides AI provider access, retry logic,
and response validation.

```
BaseAgent
├── ResearchAgent
├── ScriptAgent
├── StoryboardAgent
├── ImagePromptAgent
├── VideoPromptAgent
└── NarrationAgent
```

`AgentRegistry` is the catalog: each agent is registered with a key, name, icon,
output filename and factory. `app/pipeline/definitions.py` defines the fixed agent
order and how each stage's input is loaded from the previous stage's output file.

Prompts live in `app/prompts/*.txt` as Jinja2 templates. `content_type` and
`target_duration_seconds` are passed into the research/script/storyboard/narration
templates and produce genuinely different prompt text per content type and duration
bucket (see `research.txt`, `script.txt`, `storyboard.txt`) — this is prompt-level
steering, not a hard-coded scene-count validator in code.

---

# Service Layer

These are **services**, not agents — they don't call an AI text provider, they run
deterministic production logic. Do not model them as `*Agent` classes.

| Service | Responsibility |
|---|---|
| `MediaBuilder` | Downloads scene images/videos via the image/video provider registry. Reads `media_mode` and only calls the providers that mode implies (`image` → images only, `video` → videos only with no image fallback, `mixed` → video-first with image fallback). Writes `media/manifest.json`. |
| `NarrationBuilder` | Splits narration into per-scene text files under `narration/`. |
| `VoiceService` | Synthesizes each scene's narration audio via the voice provider registry (eSpeak / Piper / Supertonic), using `voice_provider`, `voice_name`, `voice_speed` from `project.json`. Writes `audio/manifest.json` with per-scene duration. |
| `RenderService` | Builds one FFmpeg clip per scene (video loop+audio mux, or image+pad), sized/timed from `resolution`/`fps`/scene durations, concatenates them into `render/final_video.mp4`, then optionally mixes in background music and/or writes `render/subtitles.srt`. |
| `ThumbnailService` | Optional. Extracts a frame from the first usable scene (existing image, or a grabbed video frame), overlays the project title via FFmpeg `drawtext`, and writes `thumbnail.jpg` (+ `thumbnail_vertical.jpg` for shorts/vertical). |
| `ProjectService` | Creates/loads/saves `project.json`. Resolves a collision-free slug (`_2`, `_3`, ...) so a repeated title never silently overwrites an existing project. |

---

# Provider Registry

`ProviderRegistry` is a plain category→key→factory map (`app/providers/registry.py`).
`register_default_providers()` in `app/providers/defaults.py` registers the built-ins:

| Category | Registered keys |
|---|---|
| `text` | `deepseek` |
| `image` | `pexels` |
| `video` | `pexels` |
| `voice` | `espeak`, `local_tts` (alias for eSpeak), `piper`, `supertonic` |

`image_provider`/`video_provider` are already threaded through the project model and
`BuildPipeline`, but since only Pexels exists for each category today, there is
nothing else to select yet — this becomes meaningful once a second provider is added.

`VoiceProvider.synthesize()` takes `text`, `output_path`, and `**options` (language,
voice_name, speed, ...); each provider reads whichever options it understands.

---

# Pipeline Orchestration

`BuildPipeline.run()` creates a new `DocumentaryProject` (via `ProjectService`) and
calls `_run_pipeline()`. `BuildPipeline.resume(project_path)` calls the same
`_run_pipeline()` on an existing project directory.

`_run_pipeline()`:

1. Loads `project.json` and `pipeline_state.json`.
2. Runs the fixed agent stages in order, skipping any whose output file already exists
   (registering it as complete in the state file if it wasn't already).
3. Builds the service-stage list (`media`, `narration_scenes`, `voice`, `render`, and
   conditionally `thumbnail` if `thumbnail_enabled` is set), running each the same way.
4. Writes `pipeline_state.json` with per-step status/timing and a final `completed`
   status.

This is why a fully-completed project resumes in a fraction of a second — every step's
validator short-circuits once its output file is confirmed present.

---

# Web Layer

FastAPI, not Flask. `app/web.py` owns project list/detail/file-serving; the new-project
wizard and build API live in `app/web_new_project.py` (`APIRouter`, mounted via
`app.include_router(...)`).

Build jobs run in a background `threading.Thread` per request (no task queue). Job
records are kept in an in-memory `JOBS` dict for fast polling, but are also persisted to
`jobs/<job_id>.json` on every status change. On process startup,
`_recover_jobs_from_disk()` reloads those records and restarts any job still
`queued`/`running` — via `BuildPipeline.resume()` if `project.json` already exists, or a
fresh `.run()` (using the saved request payload) if the process crashed before the
project was even created. This means a systemd restart mid-build no longer silently
loses the job.

---

# project.json Schema

Backed by `app.models.project.DocumentaryProject` (a dataclass). Key fields:

```
title, language, content_type, target_duration_seconds, media_mode,
text_provider, image_provider, video_provider,
voice_provider, voice_name, voice_speed,
resolution, fps,
background_music_enabled, music_track,
subtitles_enabled, thumbnail_enabled,
status, created_at
```

`content_type` is the single source of truth; `template` is kept as a read-only alias
for backward compatibility with older `project.json` files. `width`/`height` are
computed properties derived from `resolution`. `from_dict()` also accepts the legacy
`template`/`duration` keys from pre-existing projects.

---

# Deployment

Typically run as a systemd service:

```bash
uvicorn app.web:app --host 0.0.0.0 --port 8090
```

```
systemctl restart docuforge-web
```

---

# Known Gaps

- Subtitles are sidecar `.srt` only — not burned into the video.
- No XTTS voice cloning provider yet.
- Piper output has known crackle between sentences; no audio-cleanup pass
  (loudnorm/highpass/crossfade) has been added yet — needs validation against real
  audio before changing.
- Only one image/video provider (Pexels) exists, so provider selection is currently a
  no-op in practice.
