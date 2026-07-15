# 🎬 DocuForge

> AI-powered documentary production platform.

DocuForge is an end-to-end AI pipeline for creating documentary content.

Instead of using multiple AI tools manually, a single command generates:

- Research
- Documentary Script
- Storyboard
- Image Prompts
- Video Prompts
- Narration

---

# Features

- ✅ DeepSeek AI integration
- ✅ Modular Agent Architecture
- ✅ Build Pipeline
- ✅ Resume Pipeline
- ✅ Automatic retry
- ✅ JSON validation
- ✅ Prompt templates (Jinja2)
- ✅ Progress tracking
- ✅ Pipeline state recovery

---

# Installation

```bash
git clone https://github.com/hakanerbasss/DocuForge.git

cd DocuForge

python3.12 -m venv .venv

source .venv/bin/activate

pip install -e .
```

---

# Configuration

Create a `.env` file.

```env
AI_PROVIDER=deepseek

DEEPSEEK_API_KEY=YOUR_KEY
```

---

# Commands

## Version

```bash
docuforge version
```

---

## Create Project

```bash
docuforge generate "Black Holes"
```

---

## Full Pipeline

```bash
docuforge build "Black Holes"
```

This generates:

```
research.md

script.md

storyboard.json

image_prompts.json

video_prompts.json

narration.txt
```

---

## Resume

```bash
docuforge resume projects/black_holes
```

Continues from the first incomplete step.

---

## Individual Commands

Research

```bash
docuforge research projects/black_holes
```

Script

```bash
docuforge script projects/black_holes
```

Storyboard

```bash
docuforge storyboard projects/black_holes
```

Image Prompts

```bash
docuforge images projects/black_holes
```

Video Prompts

```bash
docuforge videos projects/black_holes
```

Narration

```bash
docuforge narration projects/black_holes
```

---

# Output Structure

```
projects/

└── black_holes

    ├── project.json

    ├── research.md

    ├── script.md

    ├── storyboard.json

    ├── image_prompts.json

    ├── video_prompts.json

    ├── narration.txt

    └── pipeline_state.json
```

---

# Pipeline

```
Topic

↓

Research

↓

Script

↓

Storyboard

↓

Image Prompts

↓

Video Prompts

↓

Narration
```

---

# Current Architecture

```
BaseAgent

├── ResearchAgent

├── ScriptAgent

├── StoryboardAgent

├── ImagePromptAgent

├── VideoPromptAgent

└── NarrationAgent
```

---

# Roadmap

## ✅ Completed

- Build Pipeline
- Resume
- Research Agent
- Script Agent
- Storyboard Agent
- Image Prompt Agent
- Video Prompt Agent
- Narration Agent
- Agent Registry
- JSON Validation
- Retry System

## 🚧 Next

- Thumbnail Agent
- YouTube SEO Agent
- Provider Registry
- FastAPI API
- Web Studio
- FFmpeg Integration
- ElevenLabs
- Veo / Kling Integration
- YouTube Upload

---

# License

MIT License
