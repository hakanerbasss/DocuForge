# 🏗 DocuForge Architecture

## Overview

DocuForge is an AI-powered documentary production platform built around a modular pipeline architecture.

Every stage is implemented as an independent AI Agent.

```
Topic
   │
   ▼
Research
   │
   ▼
Script
   │
   ▼
Storyboard
   │
   ▼
Image Prompts
   │
   ▼
Video Prompts
   │
   ▼
Narration
```

---

# Project Structure

```
app/

agents/
ai/
cli/
core/
models/
pipeline/
prompts/
services/
utils/
```

---

# Agent Architecture

All agents inherit from BaseAgent.

```
BaseAgent

├── ResearchAgent

├── ScriptAgent

├── StoryboardAgent

├── ImagePromptAgent

├── VideoPromptAgent

└── NarrationAgent
```

Responsibilities of BaseAgent:

- AI Provider access
- Retry logic
- Response validation
- Common utilities

---

# Agent Registry

AgentRegistry is the central catalog for all agents.

Each agent defines:

- key
- name
- icon
- output file
- factory

Example:

Research

↓

research.md

↓

ResearchAgent

---

# Pipeline

BuildPipeline executes agents sequentially.

```
Build

↓

Research

↓

Script

↓

Storyboard

↓

Images

↓

Videos

↓

Narration
```

ResumePipeline skips completed steps using:

```
pipeline_state.json
```

---

# AI Layer

Current Provider

- DeepSeek

Future Providers

- OpenAI GPT-5
- Claude
- Gemini
- Qwen

Provider selection will be controlled by:

```
.env
```

---

# Prompt System

Prompt templates use Jinja2.

```
app/prompts/
```

Current prompts

- research.txt
- script.txt
- storyboard.txt
- image.txt
- video.txt

---

# Output

Each project contains

```
project.json

research.md

script.md

storyboard.json

image_prompts.json

video_prompts.json

narration.txt

pipeline_state.json
```

---

# Future Architecture

Provider Registry

↓

Plugin System

↓

FastAPI Backend

↓

Web Studio

↓

Cloud Workers

↓

Distributed Rendering
