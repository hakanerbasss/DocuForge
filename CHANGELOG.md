# Changelog

All notable changes to DocuForge will be documented in this file.

This project follows Semantic Versioning.

---

# Unreleased

## Added

- **From-scratch server install (`deploy/`)** — `deploy/bootstrap.sh` takes an
  empty Ubuntu box to a running panel in one command: system packages
  (`ffmpeg`, `espeak-ng`), venv, `docuforge-web` systemd unit, and optionally
  nginx + Let's Encrypt + HTTP Basic Auth. No API keys are needed to install.
  The systemd unit and nginx config previously existed only on the live server,
  so the repo could not rebuild it.
- **`[web]`, `[voices]` and `[xtts]` optional dependencies** in
  `pyproject.toml`.

## Fixed

- **`pip install -e .` produced a dead web panel.** fastapi/uvicorn/pydantic/
  python-multipart were only listed as a manual README step, so a fresh install
  raised `ModuleNotFoundError: No module named 'fastapi'` on `import app.web`.
  They are now the `[web]` extra.
- **Supertonic was selectable but never installed.** The wizard offers it as a
  voice and the provider imports it lazily, so on a fresh box the failure
  surfaced only mid-build. It is now the `[voices]` extra, installed by default
  by the bootstrap.

## Security

- Documented, and made the installer account for, the fact that **the web panel
  has no authentication**: `/settings` shows and edits the DeepSeek, Pexels,
  OpenAI and fal.ai keys. With `DOMAIN` the service binds `127.0.0.1` behind
  nginx (optionally with Basic Auth via `PANEL_PASS`); without it the installer
  binds `0.0.0.0` as before but prints a clear warning and the firewall command.

---

# v0.5.0 (Current Development)

## Added

- Agent Registry
- BaseAgent architecture
- Build Pipeline
- Resume Pipeline
- Step timing
- Pipeline state tracking
- JSON validation
- Automatic retry
- Image Prompt Agent
- Video Prompt Agent
- Narration Agent
- Jinja2 prompt templates
- DeepSeek AI provider

## Improved

- Modular project structure
- Shared AI utilities
- Common validation logic
- Better CLI output
- Rich progress reporting

---

# v0.4.0

## Added

- Storyboard Agent
- Script Agent
- Research Agent
- AI Factory
- Prompt Loader

---

# v0.3.0

## Added

- DeepSeek integration
- Configuration system
- Project loading
- CLI improvements

---

# v0.2.0

## Added

- Project Generator
- Typer CLI
- Initial project templates

---

# v0.1.0

## Initial Release

Features

- Basic CLI
- Project creation
- Repository setup

---

# Planned (v0.6)

## Agents

- Thumbnail Agent
- YouTube SEO Agent
- Chapter Agent

## Architecture

- Provider Registry
- Plugin System
- Event Bus

## Integrations

- OpenAI GPT-5
- Claude
- Gemini
- Flux
- SDXL
- Veo
- Kling
- ElevenLabs

## Platform

- FastAPI
- Web Studio
- REST API
- Docker
- Cloud Deployment
