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
| `RenderService` | Builds one FFmpeg clip per scene (video loop+audio mux, or image+pad), sized/timed from `resolution`/`fps`/scene durations, concatenates them into `render/final_video.mp4`, then optionally mixes in background music and/or writes `render/subtitles.srt`. Music comes from a local file if one exists, otherwise from the `music` provider registry (`jamendo`/`mubert`) if `music_provider` is set to one, using a mood query built from `content_type`. |
| `ThumbnailService` | Optional. Builds an SEO creative brief (`thumbnail_hook`/`main_subject`/`emotional_trigger`/`visual_contrast`/`avoid_elements` from `seo.json`, with fallbacks). Picks the strongest real scene frame via a Pillow edge/contrast heuristic (`_score_frame`) across all scenes as a fallback background source. `thumbnail_source` (`auto`/`ai`/`pexels`/`scene`) picks where backgrounds come from *and* how many of the 4 templates (`split_contrast`, `mystery_focus`, `documentary_cinematic`, `breaking_discovery`) get generated: `ai` costs a real DALL-E call per template, so only the one variant that would become canonical is built; `pexels` (stock search, one query per template) and `scene` (real frame) are free and always build all 4; `auto` resolves to whichever free source is configured, only falling to `ai` if neither is. Any background fetch failure falls back to the real scene frame for that template. Composites the final image with Pillow (gradients, blur/vignette, dutch-angle rotation, split color-grading, stroke+shadow text, auto-shrink-to-fit wrapping) -- text is never the full title, always a short hook. Writes whichever `thumbnail_1..4.png` it generated (clearing stale ones from a previous mode first), copies one to the canonical `thumbnail.jpg` (+ `thumbnail_vertical.jpg` for shorts/vertical, recomposited from the same background, no extra API call), and records the pick as `thumbnail_selected` in `project.json`. The project page shows every generated variant; `POST /api/projects/{slug}/thumbnail/select` lets the user swap which one is canonical. |
| `ProjectService` | Creates/loads/saves `project.json`. Resolves a collision-free slug (`_2`, `_3`, ...) so a repeated title never silently overwrites an existing project. |

---

# Provider Registry

`ProviderRegistry` is a plain category→key→factory map (`app/providers/registry.py`).
`register_default_providers()` in `app/providers/defaults.py` registers the built-ins:

| Category | Registered keys |
|---|---|
| `text` | `deepseek` |
| `image` | `pexels`, `pixabay`, `unsplash`, `dalle`, `google_imagen`, `fal` |
| `video` | `pexels`, `pixabay`, `google_veo`, `fal` |
| `voice` | `espeak`, `local_tts` (alias for eSpeak), `piper`, `supertonic`, `xtts` |

`image_provider`/`video_provider` are threaded through the project model,
`BuildPipeline`, and `MediaBuilder` (which resolves them from the registry by key —
adding a provider only requires registering it, no MediaBuilder changes). The web
wizard's `/new` page exposes both as real dropdowns.

Split into two families:

- **Free stock** (query-based, same shape as Pexels): `pixabay` (image + video),
  `unsplash` (image only — no video API).
- **AI generation** (prompt-based — `query` becomes the generation prompt, not a
  search term): `dalle` (OpenAI's `gpt-image-1` via the `openai` package already
  required for DeepSeek), `google_imagen`/`google_veo` (Gemini API plain REST, no new
  SDK — Veo is a `predictLongRunning` operation: submit, poll `operations.get`, then
  download), `fal` (fal.ai's queue REST API — one integration exposes hundreds of
  hosted models; which specific model runs is an options kwarg, defaulting to
  `fal-ai/flux/schnell` for images and `fal-ai/kling-video/v1.6/standard/
  text-to-video` for video).

Each needs its own API key (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `FAL_KEY`,
`PIXABAY_API_KEY`, `UNSPLASH_ACCESS_KEY`) and none of them have been exercised against
live traffic in this codebase — every provider was built and verified against the
*documented* request/response shapes with mocked HTTP, not a real account. Veo's
response field path in particular
(`response.generateVideoResponse.generatedSamples[0].video.uri`) is flagged in its
docstring as the least certain of the bunch — validate before relying on it.

`MediaBuilder` now branches on provider type via `_is_generation_provider()` — a plain
`hasattr(provider, "search")` check, since stock providers (Pexels/Pixabay/Unsplash)
expose `.search()` in addition to the `ImageProvider`/`VideoProvider` interface, and
generation providers only implement `get_images()`/`get_videos()`. For generation
providers, it looks up the current scene's prompt from `image_prompts.json`/
`video_prompts.json` (loaded once per `build()` call via `_load_image_prompts_by_scene`/
`_load_video_prompts_by_scene`; video prompts fold in `camera_motion` since that's
meaningful generation guidance a stock query never carried), falling back to the
storyboard's short `visual` text if the scene is missing from the prompts file. Stock
providers are untouched — they still call `.search()` with the short query and a real
`MediaAsset` (author/license/page_url) exactly as before. This also fixed a bug beyond
just "prompts unused": `MediaBuilder` previously called `provider.search()` directly,
which no generation provider implements at all — a generation provider selected before
this change would have crashed with `AttributeError`, not just ignored its prompt file.

`VoiceProvider.synthesize()` takes `text`, `output_path`, and `**options` (language,
voice_name, speed, ...); each provider reads whichever options it understands.
`XTTSVoiceProvider` (`app/providers/voice/xtts.py`) is a port of the same approach
already running in the Instagram bot project
(`hakanerbasss.github.io`, `supertonic-web/xtts_clone.py`, branch
`claude/arduino-smart-home-uj82ef`): Coqui XTTS-v2, `speaker_wav` cloning from a
reference recording, sentence-chunking to stay under XTTS's ~400 token limit per call.
`torch`/`TTS.api` are imported lazily inside the provider so the rest of DocuForge
doesn't need them installed. Reference audio resolves in order: an explicit
`reference_audio` option, the `XTTS_REFERENCE_AUDIO` env var, then
`models/xtts/reference.wav`.

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

## Regenerating a single stage

`BuildPipeline.regenerate_step(project_path, step_key)` lets you redo one stage (e.g.
you don't like the script) without redoing the whole project:

1. Determine the fixed step order (agent steps + service steps, same as
   `_run_pipeline`).
2. Delete the output file (and drop the `pipeline_state.json` entry) for every step
   *after* `step_key`, so a later `resume()` naturally regenerates them — the agent/
   service runners both treat "output file missing" as "needs to run," independent of
   state.
3. Regenerate `step_key` itself immediately, via the same `_run_agent_step`/
   `_run_service_step` machinery `_run_pipeline` uses, and return.

`voice` is a deliberate special case: its registered "output" file
(`audio/manifest.json`) is the *same file* `narration_scenes` writes, and
`VoiceService.generate()` reads it as an input (raises if missing). Regenerating
`voice` on its own resets each scene's `status` back to `"text_ready"` in-place
instead of deleting the manifest, so the scene text survives and only the audio gets
redone. Regenerating anything *upstream* of `voice` (e.g. `script`) still deletes the
manifest outright, since `narration_scenes` will recreate it from scratch anyway.

### Regenerating with different settings

`regenerate_step(project_path, step_key, overrides=None)` applies `overrides` to
`project.json` *before* the invalidate/regenerate sequence above, so "I don't like this
voice, try a different one" doesn't require a whole new project. `STEP_ALLOWED_OVERRIDES`
(module-level dict in `build_pipeline.py`) is the single source of truth for which
fields are safe to change per step — `research` (language/content_type/duration, since
changing these should cascade through the whole downstream chain anyway), `voice`
(provider/name/speed), `media` (image_provider/video_provider/media_mode), `render`
(resolution/fps/background_music_enabled/subtitles_enabled/subtitles_burn_in). Anything
not in that set is rejected with `ValueError` (surfaced as HTTP 400 from the web layer)
rather than silently ignored, since a step's action wouldn't read an unlisted field
anyway. `_apply_overrides` round-trips through `DocumentaryProject.from_dict()`, so
invalid values (e.g. an unregistered voice_provider) fail with the model's own
validation message, not a confusing downstream crash.

`GET /api/projects/{slug}/step-options/{step_key}` exposes this to the frontend:
allowed fields, their current values, and — for provider fields — the choices actually
registered in `ProviderRegistry` right now (so a newly added provider needs no frontend
change to show up). The project page's "Yeniden Üret" button fetches this first; if
`allowed_fields` is non-empty it renders a small form (select for provider/enum fields,
checkbox for booleans, number/text otherwise) before submitting
`POST .../regenerate/{step_key}` with `{"overrides": {...}}`.

---

# Web Layer

FastAPI, not Flask. `app/web.py` owns project list/detail/file-serving; the new-project
wizard and build API live in `app/web_new_project.py` (`APIRouter`, mounted via
`app.include_router(...)`).

Build jobs run in a background `threading.Thread` per request (no task queue). Job
records are kept in an in-memory `JOBS` dict for fast polling, but are also persisted to
`jobs/<job_id>.json` on every status change. Each record carries a `kind`
(`"build"` or `"regenerate"`) so recovery dispatches to the right function. On process
startup, `_recover_jobs_from_disk()` reloads those records and restarts any job still
`queued`/`running` — `kind: "build"` via `BuildPipeline.resume()` if `project.json`
already exists (or a fresh `.run()` using the saved request payload if the process
crashed before the project was even created), `kind: "regenerate"` via
`BuildPipeline.regenerate_step()`. This means a systemd restart mid-build (or
mid-regeneration) no longer silently loses the job.

Two more endpoints besides `/api/builds`: `POST /api/projects/{slug}/regenerate/{step_key}`
(calls `regenerate_step`) and `POST /api/projects/{slug}/resume` (calls `resume`, reusing
`_execute_build` — its "does project.json already exist" check naturally takes the
resume branch). Both return a `job_id` pollable via the same `/api/builds/{job_id}`
endpoint used for full builds. `PIPELINE_STEP_ORDER` (a fixed list of
`(step_key, display_label)` pairs, minus `thumbnail` unless `thumbnail_enabled`) is the
single source of truth both the progress-percentage math and the project detail page's
per-stage buttons use — defined once in `app/web_new_project.py` and imported into
`app/web.py`.

`app/web_settings.py` is the third router (`GET/POST /settings`), for managing API keys
without touching `.env`. It's a standalone HTML page like `web_new_project.py` — not
built on `web.py`'s shared `page()` template — specifically to avoid a circular import
(`web.py` already imports from it to mount the router). A "⚙ Ayarlar" link in the
header of every page (`web.py`'s `page()` template and `web_new_project.py`'s `/new`
page each define it separately, same reasoning) points here.

## PWA

`app.mount("/static", StaticFiles(directory=...))` in `web.py` serves `app/static/`:
`manifest.json`, `sw.js`, `icons/` (SVG + 192/512/180 PNG, generated with Pillow to
match the in-page blue "D" logo). Each of the three independent `<head>` blocks
(`web.py`'s `page()`, `web_new_project.py`'s `/new`, `web_settings.py`'s `/settings`)
links the manifest and registers the service worker separately, same reasoning as the
"⚙ Ayarlar" link above (no shared template across all three). `sw.js` is deliberately
conservative: it only cache-first's `/static/*`; every page render and every
`/api/`/`/files/` request bypasses the cache entirely, because DocuForge's HTML is
live server-rendered job/project state, not a static app shell — caching it would mean
showing a stale build status offline or online. The service worker mainly exists to
satisfy the "installable" requirement, not to provide real offline functionality.
Requires HTTPS in front (reverse proxy + a real cert, e.g. certbot) — service workers
refuse to register on plain HTTP outside `localhost`.

---

# project.json Schema

Backed by `app.models.project.DocumentaryProject` (a dataclass). Key fields:

```
title, language, content_type, target_duration_seconds, media_mode,
text_provider, image_provider, video_provider,
voice_provider, voice_name, voice_speed,
resolution, fps,
background_music_enabled, music_track, music_provider,
subtitles_enabled, subtitles_burn_in, thumbnail_enabled, thumbnail_source,
status, created_at
```

`content_type` is the single source of truth; `template` is kept as a read-only alias
for backward compatibility with older `project.json` files. `width`/`height` are
computed properties derived from `resolution`. `from_dict()` also accepts the legacy
`template`/`duration` keys from pre-existing projects.

---

# Secrets and Settings

`app/core/config.py`'s `Settings` dataclass resolves each API key at process start as
`os.getenv(ENV_NAME) or secrets.json[key]`, so an explicit env var always wins and can't
be overridden from the web UI. `SECRET_FIELDS` maps each env var name to its
`secrets.json`/dataclass field name — the single source of truth both `Settings` and
`app/web_settings.py` use, so adding a new manageable secret means updating one dict
plus one `FIELD_LABELS` entry, not touching provider code.

`Settings.save_secret(key, value)` does two things: writes `secrets.json` (gitignored,
never committed) so the value survives a restart, and `setattr`s the *live* singleton
so it takes effect immediately for any provider instantiated afterward in the same
process — no restart required. `is_configured(key)` is a plain truthiness check, used to
decide whether `/settings` shows "✓ configured / Değiştir" or an input+save form for
each field, mirroring the pattern already proven in the Instagram bot project
(`hakanerbasss.github.io`, `supertonic-web/app.py`'s `/api/*/config` endpoints) — small
JSON-backed config, masked status instead of ever echoing the key back to the browser.

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

- Subtitle burn-in (`_burn_in_subtitles`, the `subtitles` ffmpeg filter via libass) has
  not been run against a real ffmpeg/libass install in this codebase — verified only by
  inspecting the constructed command. No `FontName` is forced in `force_style`
  deliberately (letting fontconfig resolve a default is more portable than guessing a
  font file's internal family name), but that also means Turkish characters' rendering
  quality depends on whatever fontconfig picks on the server.
- Piper output has known crackle between sentences; no audio-cleanup pass
  (loudnorm/highpass/crossfade) has been added yet — needs validation against real
  audio before changing.
- None of the new AI generation providers (DALL-E, Imagen, Veo, fal.ai) have been
  exercised against live traffic — verified against documented API shapes with mocked
  HTTP only.
- XTTS reference audio must already exist on disk (configured via `/settings` or
  `XTTS_REFERENCE_AUDIO`) — there's no upload flow for the audio file itself, unlike the
  Instagram bot's admin API for managing its reference recording.
- `STEP_ALLOWED_OVERRIDES` only covers research/voice/media/render. Regenerating
  script/storyboard/images/videos/narration/seo/thumbnail always reuses the existing
  settings verbatim — there was no clearly "editable" setting for those to expose yet
  (e.g. a custom instruction/prompt override for script would be a reasonable follow-up).
