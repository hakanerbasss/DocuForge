# DocuForge AI Development Guide

This file defines the development rules for every AI agent working on DocuForge.

Every AI assistant (ChatGPT, Codex or other coding agents) MUST read this file before modifying the project.

---

# Mission

DocuForge is NOT a simple CLI.

It is an AI Content Factory capable of generating complete content pipelines.

The architecture must always remain modular.

---

# Core Principles

Never break existing features.

Prefer extension over modification.

Small commits.

Small pull requests.

Readable code.

Document every major change.

---

# Existing Pipeline

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

Upcoming

↓

Thumbnail

↓

YouTube SEO

↓

Render

↓

Upload

---

# Architecture Rules

Use BaseAgent.

Never duplicate code.

Every new AI feature must be an Agent.

Agents are registered using AgentRegistry.

Every provider must implement a common interface.

Never hardcode provider-specific logic.

---

# Provider Philosophy

DocuForge must support BOTH

Local tools

and

Cloud APIs

Examples

Local

- Pexels
- Local TTS
- Cloned Voice
- FFmpeg
- Supertonic

Cloud

- GPT
- Claude
- Gemini
- Flux
- Veo
- ElevenLabs

The user must be able to switch providers without changing the code.

---

# Existing Local Infrastructure

The project MUST preserve compatibility with the user's existing production workflow.

Current local workflow includes

- Supertonic
- Pexels Images
- Pexels Videos
- Local TTS
- Local cloned voice

Do NOT remove or replace them.

Integrate them as Providers.

---

# Template Engine

The project must support multiple templates.

Examples

Documentary

News

Shorts

Finance

Technology

Educational

Templates change prompts.

Templates may also change pipeline stages.

---

# Future Provider Registry

Text Providers

Image Providers

Video Providers

Voice Providers

Render Providers

All Providers must share common interfaces.

---

# Coding Style

Type hints

Docstrings

Readable functions

No giant files

Prefer composition over inheritance.

---

# Testing

Never mark a task complete without testing.

Run CLI commands whenever possible.

Do not break Build Pipeline.

Do not break Resume Pipeline.

---

# Documentation

Every significant feature must update

README.md

CHANGELOG.md

ARCHITECTURE.md

---

# Git

Never commit secrets.

Never commit .env.

Never commit API keys.

Prefer feature branches.

Keep commit messages meaningful.

---

# Long-term Vision

DocuForge is evolving into an AI Content Factory.

The system should generate

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

Voice

↓

Render

↓

Thumbnail

↓

SEO

↓

Upload

using interchangeable providers and templates.

Every architectural decision should support this vision.
