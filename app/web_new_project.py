import json
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.agents.shorts_split import ShortsSplitAgent
from app.agents.topic import TopicSuggestionAgent
from app.pipeline.build_pipeline import (
    STEP_ALLOWED_OVERRIDES,
    BuildPipeline,
    PipelineCancelled,
)
from app.pipeline.exceptions import PipelineAwaitingUpload
from app.services.media_builder import MediaBuilder
from app.services.project_service import ProjectService
from app.services.thumbnail_service import ThumbnailService


router = APIRouter()

PIPELINE_STEP_ORDER: list[tuple[str, str]] = [
    ("research", "📚 Araştırma"),
    ("script", "📝 Senaryo"),
    ("storyboard", "🎬 Storyboard"),
    ("images", "🖼 Görsel Prompt'ları"),
    ("videos", "🎥 Video Prompt'ları"),
    ("narration", "🎙 Anlatım Metni"),
    ("seo", "📈 SEO Metadata"),
    ("media", "📦 Medya İndirme"),
    ("narration_scenes", "📝 Sahne Metinleri"),
    ("voice", "🎙 Seslendirme"),
    ("render", "🎬 Video Render"),
    ("thumbnail", "🖼 Kapak Görseli"),
]

PROJECTS_ROOT = Path("projects")
JOBS_DIR = Path("jobs")
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

# Cancellation is cooperative (checked between pipeline steps, see
# BuildPipeline._check_cancelled) so only "build" jobs (run/resume, which
# loop over many steps) get an event -- a single-step "regenerate" job has
# no natural in-between point to check at. Not persisted to disk: a
# process restart already kills the old thread, and _recover_jobs_from_disk
# creates a fresh event for whatever it restarts.
CANCEL_EVENTS: dict[str, threading.Event] = {}


class BuildRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    source_material: str = Field(default="", max_length=8000)
    source_citation: str = Field(default="", max_length=500)
    language: str = Field(default="tr")
    content_type: str = Field(default="documentary")
    target_duration_seconds: int = Field(default=900, ge=10, le=7200)
    media_mode: str = Field(default="mixed")
    image_provider: str = Field(default="pexels")
    video_provider: str = Field(default="pexels")
    voice_provider: str = Field(default="supertonic")
    voice_name: str = Field(default="M1")
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    resolution: str = Field(default="720p")
    fps: int = Field(default=30)
    scene_transition: str = Field(default="crossfade")
    background_music_enabled: bool = Field(default=False)
    music_provider: str = Field(default="local")
    music_track: str = Field(default="")
    music_volume: float = Field(default=0.18, ge=0.0, le=1.0)
    subtitles_enabled: bool = Field(default=False)
    subtitles_burn_in: bool = Field(default=False)
    ai_disclosure_enabled: bool = Field(default=False)
    location_map_enabled: bool = Field(default=False)
    manual_upload_enabled: bool = Field(default=False)
    thumbnail_enabled: bool = Field(default=False)
    thumbnail_source: str = Field(default="auto")
    verbatim_script: bool = Field(default=False)


class RegenerateRequest(BaseModel):
    overrides: dict[str, Any] = Field(default_factory=dict)



def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _persist_job(job_id: str) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_file = JOBS_DIR / f"{job_id}.json"
    job_file.write_text(
        json.dumps(JOBS[job_id], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _execute_build(job_id: str, req: dict[str, Any], project_dir: Path) -> None:
    # The event is created by the caller (the endpoint, or job recovery)
    # before this thread starts, so a cancel request arriving the instant
    # after the job is queued can never race past a missing entry.
    cancel_event = CANCEL_EVENTS.get(job_id) or threading.Event()

    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        _persist_job(job_id)
    try:
        if (project_dir / "project.json").exists():
            # Project already created by a previous (possibly crashed) run.
            result_dir = BuildPipeline().resume(
                str(project_dir), cancel_event=cancel_event
            )
        else:
            result_dir = BuildPipeline().run(
                topic=req["topic"],
                source_material=req.get("source_material", ""),
                source_citation=req.get("source_citation", ""),
                language=req["language"],
                content_type=req["content_type"],
                target_duration_seconds=req["target_duration_seconds"],
                media_mode=req["media_mode"],
                image_provider=req["image_provider"],
                video_provider=req["video_provider"],
                voice_provider=req["voice_provider"],
                voice_name=req["voice_name"],
                voice_speed=req["voice_speed"],
                resolution=req["resolution"],
                fps=req["fps"],
                scene_transition=req.get("scene_transition", "crossfade"),
                background_music_enabled=req["background_music_enabled"],
                music_provider=req.get("music_provider", "local"),
                music_track=req.get("music_track", ""),
                music_volume=req.get("music_volume", 0.18),
                subtitles_enabled=req["subtitles_enabled"],
                subtitles_burn_in=req.get("subtitles_burn_in", False),
                ai_disclosure_enabled=req.get("ai_disclosure_enabled", False),
                location_map_enabled=req.get("location_map_enabled", False),
                manual_upload_enabled=req.get("manual_upload_enabled", False),
                thumbnail_enabled=req["thumbnail_enabled"],
                thumbnail_source=req.get("thumbnail_source", "auto"),
                verbatim_script=req.get("verbatim_script", False),
                cancel_event=cancel_event,
            )
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "completed",
                "project_path": str(result_dir),
                "error": None,
            })
    except PipelineCancelled as error:
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "cancelled",
                "error": str(error),
            })
    except PipelineAwaitingUpload as awaiting:
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "awaiting_upload",
                "awaiting_scenes": list(awaiting.missing_scenes),
                "error": str(awaiting),
            })
    except Exception as error:
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "failed",
                "error": str(error),
            })
    finally:
        CANCEL_EVENTS.pop(job_id, None)
        with JOBS_LOCK:
            _persist_job(job_id)


def _execute_regenerate(
    job_id: str,
    project_dir: Path,
    step_key: str,
    overrides: dict[str, Any] | None = None,
) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        _persist_job(job_id)
    try:
        result_dir = BuildPipeline().regenerate_step(
            str(project_dir),
            step_key,
            overrides=overrides,
        )
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "completed",
                "project_path": str(result_dir),
                "error": None,
            })
    except Exception as error:
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "failed",
                "error": str(error),
            })
    finally:
        with JOBS_LOCK:
            _persist_job(job_id)


def _recover_jobs_from_disk() -> None:
    """Reload job records after a service restart and resume unfinished builds."""

    if not JOBS_DIR.exists():
        return

    for job_file in sorted(JOBS_DIR.glob("*.json")):
        job = load_json(job_file)
        job_id = job.get("job_id")

        if not job_id:
            continue

        with JOBS_LOCK:
            JOBS[job_id] = job

        if job.get("status") not in ("queued", "running"):
            continue

        project_dir = Path(job["project_path"])

        if job.get("kind") == "regenerate":
            step_key = job.get("step_key")

            if not step_key:
                continue

            thread = threading.Thread(
                target=_execute_regenerate,
                args=(job_id, project_dir, step_key, job.get("overrides")),
                daemon=True,
            )
        else:
            req = job.get("request") or {}
            CANCEL_EVENTS[job_id] = threading.Event()

            thread = threading.Thread(
                target=_execute_build,
                args=(job_id, req, project_dir),
                daemon=True,
            )

        thread.start()


_recover_jobs_from_disk()


@router.get("/new", response_class=HTMLResponse)
def new_project_page() -> HTMLResponse:
    return HTMLResponse("""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Yeni Proje · DocuForge</title>
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#2166f3">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="DocuForge">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#f3f6fb;color:#172033;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:18px;background:white;border-bottom:1px solid #e1e8f2}
header div,main{width:min(760px,calc(100% - 28px));margin:auto}
main{padding:28px 0 70px}
.back{color:#245ec7;text-decoration:none;font-weight:700}
.card{margin-top:18px;padding:24px;background:white;border:1px solid #e0e7f1;border-radius:22px;box-shadow:0 12px 35px rgba(34,54,80,.08)}
h1{margin:0 0 8px;font-size:clamp(26px,6vw,38px)}
h3{margin:22px 0 6px;font-size:15px;color:#445;text-transform:uppercase;letter-spacing:.05em}
.muted{color:#66758c}
label{display:block;margin-top:14px;margin-bottom:5px;font-weight:700;font-size:14px}
input,select{width:100%;min-height:44px;padding:0 12px;border:1px solid #cbd6e5;border-radius:10px;background:white;color:#172033;font:inherit}
textarea{width:100%;padding:10px 12px;border:1px solid #cbd6e5;border-radius:10px;background:white;color:#172033;font:inherit;resize:vertical}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.hint{font-size:12px;color:#8899aa;margin-top:3px}
button{width:100%;min-height:50px;margin-top:20px;border:0;border-radius:13px;background:#2166f3;color:white;font-size:16px;font-weight:800;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}
.status{display:none;margin-top:20px;padding:17px;border-radius:14px;background:#edf4ff}
.progress{height:11px;margin:12px 0;overflow:hidden;border-radius:999px;background:#dbe5f4}
.progress>div{width:4%;height:100%;background:#2166f3;transition:width .4s ease}
.error{background:#ffe9e9;color:#9f2020}
.success{background:#e8f8ee;color:#08763a}
.open-project{display:none;margin-top:14px;color:#2166f3;font-weight:800;text-decoration:none}
body{padding-bottom:76px}
.bottom-nav{position:fixed;left:0;right:0;bottom:0;display:flex;background:white;border-top:1px solid #e2e8f0;box-shadow:0 -6px 20px rgba(20,30,60,.06);z-index:100;padding-bottom:env(safe-area-inset-bottom,0)}
.bottom-nav a{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;padding:9px 4px 10px;text-decoration:none;color:#7c8aa0;font-size:11px;font-weight:700}
.bottom-nav a .nav-icon{font-size:21px;line-height:1}
.bottom-nav a.active{color:#2166f3}
</style>
</head>
<body>
<header><div style="display:flex;align-items:center;justify-content:center"><a class="back" href="/">\u2190 Projelere d\u00f6n</a></div></header>
<main>
<div id="activeJobBanner"></div>
<section class="card">
<h1>Yeni Proje</h1>
<p class="muted">Konuyu ve ayarlar\u0131 se\u00e7. DocuForge ara\u015ft\u0131rma, senaryo, medya, seslendirme ve videoyu otomatik haz\u0131rlas\u0131n.</p>

<h3>📝 \u0130\u00e7erik</h3>
<label for="topic">Konu</label>
<input id="topic" placeholder="\u00d6rnek: Kara Deliklerin S\u0131rr\u0131" required minlength="2" maxlength="200">
<button type="button" id="topicSuggestBtn" onclick="fetchTopicSuggestions()" style="width:auto;min-height:38px;margin-top:8px;padding:0 16px;font-size:14px;font-weight:700;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5">💡 Konu \u00d6nerisi Al</button>
<div id="topicSuggestions" style="display:none;margin-top:12px"></div>

<label for="source_material" style="margin-top:12px">Kaynak Metin (opsiyonel)</label>
<textarea id="source_material" rows="6" placeholder="Hazır senaryonu veya kaynak metnini buraya yapıştır." onblur="deriveTopicFromSource(); updateVerbatimHint()"></textarea>
<div style="display:flex;align-items:center;gap:10px;margin-top:8px">
  <label class="toggle-switch" style="margin:0">
    <input type="checkbox" id="verbatim_script" onchange="updateVerbatimHint()">
    <span class="slider"></span>
  </label>
  <span style="font-size:14px;font-weight:600">Senaryoyu birebir kullan</span>
</div>
<div id="verbatimHint" class="hint" style="margin-top:4px">Kapalı: DocuForge kaynak metni referans alarak kendi senaryosunu yazar.</div>

<label for="source_citation" style="margin-top:12px">Kaynak (opsiyonel)</label>
<input id="source_citation" placeholder="Örnek: Sözcü, Milliyet, Uzmanpara.com" maxlength="500">
<div class="hint">Girilirse video açıklamasının sonuna otomatik olarak "📌 Kaynak: ..." satırı eklenir -- telif ve şeffaflık açısından önemli, özellikle haber ve gerçek yer içeriklerinde.</div>

<div class="row">
<div>
<label for="language">Dil</label>
<select id="language">
<option value="tr" selected>T\u00fcrk\u00e7e</option>
<option value="en">\u0130ngilizce</option>
<option value="de">Almanca</option>
<option value="fr">Frans\u0131zca</option>
<option value="es">\u0130spanyolca</option>
</select>
</div>
<div>
<label for="content_type">\u0130\u00e7erik T\u00fcr\u00fc</label>
<select id="content_type" onchange="onTypeChange()">
<option value="documentary">Belgesel</option>
<option value="news">Haber</option>
<option value="shorts">Shorts / Reels</option>
<option value="informational">Bilgi Videosu</option>
</select>
</div>
</div>

<label for="duration">Hedef S\u00fcre (saniye)</label>
<input id="duration" type="number" value="900" min="10" max="7200">
<div class="hint" id="durationHint">~15 dakika</div>

<h3>🎬 Medya</h3>
<div class="row">
<div>
<label for="media_mode">Medya Modu</label>
<select id="media_mode">
<option value="mixed" selected>Video + Foto\u011fraf</option>
<option value="video">Sadece Video</option>
<option value="image">Sadece Foto\u011fraf</option>
</select>
</div>
<div>
<label for="resolution">\u00c7\u00f6z\u00fcn\u00fcrl\u00fck</label>
<select id="resolution">
<option value="720p" selected>720p (1280x720)</option>
<option value="1080p">1080p (1920x1080)</option>
<option value="vertical">Dikey (1080x1920)</option>
<option value="4k">4K (3840x2160)</option>
</select>
</div>
</div>

<div class="row">
<div>
<label for="image_provider">G\u00f6rsel Sa\u011flay\u0131c\u0131</label>
<select id="image_provider">
<option value="pexels" selected>Pexels (\u00fccretsiz stok)</option>
<option value="pixabay">Pixabay (\u00fccretsiz stok)</option>
<option value="unsplash">Unsplash (\u00fccretsiz stok)</option>
<option value="dalle">DALL-E / OpenAI (AI \u00fcretim, \u00fccretli)</option>
<option value="google_imagen">Google Imagen (AI \u00fcretim, \u00fccretli)</option>
<option value="fal">fal.ai / Flux (AI \u00fcretim, \u00fccretli)</option>
</select>
</div>
<div>
<label for="video_provider">Video Sa\u011flay\u0131c\u0131</label>
<select id="video_provider">
<option value="pexels" selected>Pexels (\u00fccretsiz stok)</option>
<option value="pixabay">Pixabay (\u00fccretsiz stok)</option>
<option value="google_veo">Google Veo (AI \u00fcretim, \u00fccretli)</option>
<option value="fal">fal.ai / Kling (AI \u00fcretim, \u00fccretli)</option>
</select>
</div>
</div>
<div class="hint">AI \u00fcretim sa\u011flay\u0131c\u0131lar\u0131 ilgili API anahtar\u0131n\u0131 (.env) gerektirir: OPENAI_API_KEY, GOOGLE_API_KEY, FAL_KEY, PIXABAY_API_KEY, UNSPLASH_ACCESS_KEY.</div>

<label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-top:14px">
<input type="checkbox" id="manual_upload_enabled" style="width:auto;min-height:auto" onchange="onManualUploadToggle()">
\U0001F5BC G\u00f6rselleri elle y\u00fckle (opsiyonel \u2014 ChatGPT/AI ile \u00fcret)
</label>
<div id="manualUploadHint" class="hint" style="display:none;background:#eef5ff;border:1px solid #cfe0f7;border-radius:10px;padding:10px 12px;margin-top:6px">\u0130\u015faretlersen \u00fcretim medya ad\u0131m\u0131nda <b>durur</b> ve her sahne i\u00e7in bir y\u00fckleme kutusu a\u00e7\u0131l\u0131r (sistemin \u00fcretti\u011fi prompt'la birlikte). \u0130stedi\u011fin sahneleri ChatGPT'de \u00fcretip y\u00fckle; <b>bo\u015f b\u0131rakt\u0131klar\u0131n otomatik olarak yukar\u0131daki sa\u011flay\u0131c\u0131dan (Pexels/AI) indirilir</b> \u2014 hi\u00e7bir sahne zorunlu de\u011fil. Video+g\u00f6rsel modunda elle y\u00fckledi\u011fin g\u00f6rsel o sahneyi ezer.</div>

<label for="fps">Kare H\u0131z\u0131 (FPS)</label>
<select id="fps">
<option value="24">24</option>
<option value="30" selected>30</option>
<option value="60">60</option>
</select>

<label for="scene_transition">Sahne Ge\u00e7i\u015fi</label>
<select id="scene_transition">
<option value="cut">Sert Kesim</option>
<option value="crossfade" selected>Yumu\u015fak Ge\u00e7i\u015f (Crossfade)</option>
<option value="fade_black">Karartarak Ge\u00e7i\u015f</option>
</select>
<div class="hint">Sahneler aras\u0131nda nas\u0131l ge\u00e7ilece\u011fini belirler. Yumu\u015fak ge\u00e7i\u015f \u00e7o\u011fu belgesel i\u00e7in en do\u011fal g\u00f6r\u00fcnen se\u00e7enektir.</div>

<h3>🎙 Ses</h3>
<div class="row">
<div>
<label for="voice_provider">Ses Sa\u011flay\u0131c\u0131</label>
<select id="voice_provider" onchange="onProviderChange()">
<option value="supertonic" selected>Supertonic</option>
<option value="piper">Piper</option>
<option value="espeak">eSpeak</option>
<option value="xtts">XTTS (Klon Sesim)</option>
</select>
</div>
<div>
<label for="voice_name">Ses</label>
<select id="voice_name">
<option value="M1" selected>M1</option>
<option value="M2">M2</option>
<option value="M3">M3</option>
<option value="F1">F1</option>
<option value="F2">F2</option>
<option value="F3">F3</option>
</select>
</div>
</div>

<label for="voice_speed">Konu\u015fma H\u0131z\u0131: <span id="speedLabel">1.0x</span></label>
<input id="voice_speed" type="range" min="0.5" max="2.0" step="0.1" value="1.0" oninput="document.getElementById('speedLabel').textContent=parseFloat(this.value).toFixed(1)+'x'">

<h3>\u2728 Ek \u00d6zellikler</h3>
<label style="display:flex;align-items:center;gap:8px;font-weight:400">
<input type="checkbox" id="background_music_enabled" style="width:auto;min-height:auto" onchange="onMusicToggle()">
Arka plan m\u00fczi\u011fi ekle
</label>
<div class="hint">\u00dcretim s\u0131ras\u0131nda <code>projects/&lt;proje&gt;/music/</code> klas\u00f6r\u00fcne bir mp3/wav dosyas\u0131 koy (render a\u015famas\u0131na kadar vaktin var) ya da a\u015fa\u011f\u0131dan bir sa\u011flay\u0131c\u0131 se\u00e7; hi\u00e7biri yoksa m\u00fczik olmadan devam eder.</div>

<div id="musicProviderRow" style="display:none;margin-top:10px;margin-left:22px">
<label for="music_provider">M\u00fczik Sa\u011flay\u0131c\u0131</label>
<select id="music_provider" onchange="onMusicProviderChange()">
<option value="local">Yerel (music/ klas\u00f6r\u00fc)</option>
<option value="jamendo" selected>Jamendo (telifsiz)</option>
<option value="mubert">Mubert (yapay zeka m\u00fczi\u011fi)</option>
<option value="elevenlabs">ElevenLabs Music (yapay zeka, \u00fccretli)</option>
<option value="freesound">Freesound (\u00fccretsiz, CC lisansl\u0131)</option>
</select>
<div class="hint">Jamendo/Mubert/ElevenLabs/Freesound i\u00e7in <a href="/settings">Ayarlar</a> sayfas\u0131ndan API key girmen gerekir.</div>

<label for="music_volume" style="margin-top:12px">M\u00fczik Sesi Seviyesi (%)</label>
<input id="music_volume" type="number" min="0" max="50" step="1" value="18">
<div class="hint">Arka plan m\u00fczi\u011finin seslendirmeye g\u00f6re ses oran\u0131. D\u00fc\u015f\u00fck tut ki konu\u015fmay\u0131 bast\u0131rmas\u0131n (varsay\u0131lan %18 \u00f6nerilir).</div>

<div id="musicBrowseRow" style="display:none;margin-top:12px;padding:12px;border:1px solid #dbe5f4;border-radius:12px;background:#f8fbff">
<div class="hint" style="margin-bottom:8px">Ticari kullan\u0131ma kapal\u0131 (NC lisansl\u0131) par\u00e7alar listelenmiyor -- ama lisans\u0131 belirlenemeyenler ⚠️ ile i\u015faretli, y\u00fcklemeden \u00f6nce kontrol et.</div>
<div id="musicCostHint" class="hint" style="display:none;margin-bottom:8px;color:#9f5a00">⚡ ElevenLabs her \u00fcretim i\u00e7in \u00fccret al\u0131r -- ayn\u0131 arama tekrarlan\u0131rsa yeniden \u00fcretmez (\u00f6nbelleklenir), ama farkl\u0131 her arama yeni bir \u00fcretim demektir.</div>
<div style="display:flex;gap:8px">
<input id="musicSearchQuery" placeholder="\u00d6rnek: cinematic ambient (bo\u015f b\u0131rak\u0131rsan i\u00e7erik t\u00fcr\u00fcne g\u00f6re aran\u0131r)" style="flex:1">
<button type="button" id="musicSearchBtn" onclick="searchMusic()" style="width:auto;min-height:44px;margin-top:0;padding:0 16px;font-size:14px">🎧 Ara</button>
<button type="button" onclick="clearMusicSearch()" style="width:auto;min-height:44px;margin-top:0;padding:0 16px;font-size:14px">🗑 Temizle</button>
</div>
<div id="musicMoodTags" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"></div>
<div id="musicResults" style="margin-top:10px"></div>
<div id="musicSelectedInfo" class="hint" style="display:none;margin-top:10px;font-weight:700;color:#08763a"></div>
<div style="margin-top:10px;border-top:1px solid #dbe5f4;padding-top:10px">
<div style="display:flex;align-items:center;justify-content:space-between">
<strong style="font-size:13px">⭐ Favorilerim</strong>
<button type="button" id="favoritesToggleBtn" onclick="toggleFavoritesList()" style="width:auto;min-height:28px;margin-top:0;padding:0 10px;font-size:12px">G\u00f6ster</button>
</div>
<div id="musicFavoritesList" style="display:none;margin-top:8px"></div>
</div>
</div>
<input type="hidden" id="music_track" value="">
</div>

<label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-top:14px">
<input type="checkbox" id="subtitles_enabled" style="width:auto;min-height:auto" onchange="onSubtitlesToggle()">
Altyaz\u0131 (.srt) olu\u015ftur
</label>
<div class="hint">Sahne bazl\u0131 zamanlamal\u0131 .srt dosyas\u0131 render klas\u00f6r\u00fcne yaz\u0131l\u0131r.</div>

<label id="burnInLabel" style="display:none;align-items:center;gap:8px;font-weight:400;margin-top:10px;margin-left:22px">
<input type="checkbox" id="subtitles_burn_in" style="width:auto;min-height:auto">
Altyaz\u0131y\u0131 videoya g\u00f6m (burn-in)
</label>
<div id="burnInHint" class="hint" style="display:none;margin-left:22px">\u0130\u015faretlenmezse .srt ayr\u0131 dosya olarak kal\u0131r, video \u00fcst\u00fcnde g\u00f6r\u00fcnmez.</div>

<label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-top:14px">
<input type="checkbox" id="ai_disclosure_enabled" style="width:auto;min-height:auto">
\U0001F916 "Yapay zeka destekli i\u00e7erik" ibaresi ekle
</label>
<div class="hint">Videonun ilk 6 saniyesine k\u00fc\u00e7\u00fck bir uyar\u0131 band\u0131 g\u00f6m\u00fcl\u00fcr. Sadece yapay zeka \u00fcretimi g\u00f6rsel/anlat\u0131m kulland\u0131\u011f\u0131n videolarda i\u015faretle -- her videoda yapay zeka kullanm\u0131yorsan bo\u015f b\u0131rak.</div>

<label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-top:14px">
<input type="checkbox" id="location_map_enabled" style="width:auto;min-height:auto">
\U0001F5FA Konum haritas\u0131 ekle
</label>
<div class="hint">Videonun konusu belirli bir yere (\u015fehir, \u00fclke, b\u00f6lge) ba\u011fl\u0131ysa erken bir sahneye o konumu g\u00f6steren bir harita eklenir. SEO analizinde net bir konum bulunamazsa harita eklenmeden devam edilir.</div>

<label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-top:14px">
<input type="checkbox" id="thumbnail_enabled" style="width:auto;min-height:auto" onchange="onThumbnailToggle()">
Kapak g\u00f6rseli (thumbnail) olu\u015ftur
</label>
<div class="hint">4 farkl\u0131 tasar\u0131ml\u0131 kapak \u00fcretilir (1280x720, dikey projelerde ayr\u0131ca 1080x1920); birini proje sayfas\u0131ndan se\u00e7ebilirsin.</div>

<div id="thumbnailSourceRow" style="display:none;margin-top:10px;margin-left:22px">
<label for="thumbnail_source">Kapak G\u00f6rseli Kayna\u011f\u0131</label>
<select id="thumbnail_source">
<option value="auto" selected>Otomatik (\u00fccretsiz varsa onu kullan)</option>
<option value="ai">Yapay Zeka (OpenAI \u2014 \u00fccretli, sadece 1 kapak \u00fcretir)</option>
<option value="pexels">Pexels (\u00fccretsiz stok, 4 kapak \u00fcretir)</option>
<option value="scene">Sahne Karesi (tamamen yerel, 4 kapak \u00fcretir)</option>
</select>
<div class="hint">"Yapay Zeka" se\u00e7iliyse maliyeti azaltmak i\u00e7in sadece 1 kapak \u00fcretilir; di\u011fer se\u00e7enekler \u00fccretsiz oldu\u011fu i\u00e7in 4'\u00fc de \u00fcretir.</div>
</div>

<button id="startButton" onclick="startBuild()">\u00dcretimi Ba\u015flat</button>

<div id="statusBox" class="status">
<strong id="statusTitle">Proje haz\u0131rlan\u0131yor\u2026</strong>
<div class="progress"><div id="progressBar"></div></div>
<div id="statusText" class="muted">\u0130\u015f ba\u015flat\u0131l\u0131yor.</div>
<a id="openProject" class="open-project" href="#">Projeyi A\u00e7 \u2192</a>
<button
  id="cancelBuildButton"
  style="display:none;width:auto;margin-top:12px;padding:0 16px;min-height:40px;background:#fee2e2;color:#b91c1c;font-size:14px;font-weight:700"
  onclick="cancelBuild()"
>\u23f9 \u0130ptal Et</button>
</div>
</section></main>

<script>
let pollTimer=null;
let currentJobId=null;

async function checkActiveJobs(){
  try{
    const r=await fetch("/api/jobs/active");
    const data=await r.json();
    const banner=document.getElementById("activeJobBanner");
    if(!data.jobs||data.jobs.length===0){banner.innerHTML="";return;}
    const rows=data.jobs.map(job=>{
      const pct=Math.max(4,Math.min(100,Number(job.progress_percent||4)));
      const label=job.current_step||"Başlatılıyor...";
      const link=job.project_slug?`<a class="button secondary" href="/projects/${job.project_slug}">Projeyi Aç</a>`:"";
      return `<div style="padding:10px 0;border-bottom:1px solid #edf1f6">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px">
          <strong>${job.topic||job.project_slug||"Proje"}</strong>
          <span style="display:flex;gap:8px;align-items:center">
            ${link}
            <button
              style="width:auto;min-height:36px;margin-top:0;padding:0 12px;font-size:13px;background:#fee2e2;color:#b91c1c"
              onclick="cancelActiveJob('${job.job_id}',this)"
            >⏹ İptal</button>
          </span>
        </div>
        <div class="progress"><div style="width:${pct}%"></div></div>
        <div class="muted" style="font-size:13px;margin-top:4px">${job.completed_steps}/${job.total_steps} · ${label}</div>
      </div>`;
    }).join("");
    banner.innerHTML=`<section class="card" style="margin-bottom:18px">
      <h2 style="margin-bottom:10px">⏳ Devam eden üretim${data.jobs.length>1?"ler":""}</h2>
      <p class="muted" style="margin-bottom:6px">Bu sırada yeni bir proje de başlatabilirsin, ikisi birbirini etkilemez.</p>
      ${rows}
    </section>`;
  }catch(e){/* sessizce yut */}
}

async function cancelActiveJob(jobId,btn){
  if(!confirm("Üretimi iptal etmek istediğine emin misin? Mevcut adım bitene kadar durmaz, sonrasında duracak."))return;
  btn.disabled=true;
  btn.textContent="İptal ediliyor…";
  try{
    const r=await fetch(`/api/builds/${jobId}/cancel`,{method:"POST"});
    const res=await r.json();
    if(!r.ok)throw new Error(res.detail||"İptal edilemedi.");
  }catch(e){
    alert("Hata: "+e.message);
    btn.disabled=false;
    btn.textContent="⏹ İptal";
  }
}

checkActiveJobs();
setInterval(checkActiveJobs,4000);

function onTypeChange(){
  const t=document.getElementById("content_type").value;
  const d=document.getElementById("duration");
  const r=document.getElementById("resolution");
  const h=document.getElementById("durationHint");
  if(t==="shorts"){d.value=60;r.value="vertical";h.textContent="~1 dakika";}
  else if(t==="news"){d.value=180;r.value="720p";h.textContent="~3 dakika";}
  else if(t==="informational"){d.value=300;r.value="720p";h.textContent="~5 dakika";}
  else{d.value=900;r.value="720p";h.textContent="~15 dakika";}
  updateHint();
}

function onManualUploadToggle(){
  const on=document.getElementById("manual_upload_enabled").checked;
  document.getElementById("manualUploadHint").style.display=on?"block":"none";
}

function updateHint(){
  const s=parseInt(document.getElementById("duration").value)||0;
  const m=Math.floor(s/60),sec=s%60;
  document.getElementById("durationHint").textContent=
    m>0?(sec>0?`~${m} dk ${sec} sn`:`~${m} dakika`):`${s} saniye`;
}

function escapeHtml(s){
  const d=document.createElement("div");
  d.textContent=s==null?"":String(s);
  return d.innerHTML;
}

async function fetchTopicSuggestions(){
  const btn=document.getElementById("topicSuggestBtn");
  const box=document.getElementById("topicSuggestions");
  btn.disabled=true;
  btn.textContent="⏳ Öneriler hazırlanıyor…";
  box.style.display="block";
  box.innerHTML='<div class="hint">DeepSeek konu önerileri hazırlıyor, birkaç saniye sürebilir…</div>';
  try{
    const res=await fetch("/api/topic-suggestions",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        content_type:document.getElementById("content_type").value,
        language:document.getElementById("language").value,
      }),
    });
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||"Öneriler alınamadı.");
    renderTopicSuggestions(data.suggestions||[]);
  }catch(err){
    box.innerHTML=`<div class="hint" style="color:#9f2020">Öneriler alınamadı: ${escapeHtml(err.message)}</div>`;
  }finally{
    btn.disabled=false;
    btn.textContent="💡 Konu Önerisi Al";
  }
}

function renderTopicSuggestions(suggestions){
  const box=document.getElementById("topicSuggestions");
  if(!suggestions.length){
    box.innerHTML='<div class="hint">Öneri bulunamadı, tekrar dene.</div>';
    return;
  }
  const medals=["🥇","🥈","🥉"];
  const top3=suggestions.slice(0,3)
    .map((s,i)=>`<div>${medals[i]} ${escapeHtml(s.title)}</div>`)
    .join("");
  const rows=suggestions.map((s,i)=>{
    const medal=i<3?medals[i]+" ":"";
    const hasVisual=s.visual_left||s.visual_right;
    const visual=hasVisual
      ? `<div class="hint" style="margin-top:3px">Sol: ${escapeHtml(s.visual_left||"—")} · Sağ: ${escapeHtml(s.visual_right||"—")}</div>`
      : "";
    const hook=s.hook?`<div class="hint" style="margin-top:3px">${escapeHtml(s.hook)}</div>`:"";
    const hashtagList=Array.isArray(s.hashtags)?s.hashtags:[];
    const hashtagText=hashtagList.map(h=>"#"+h).join(" ");
    const hashtags=hashtagList.length
      ? `<div class="hint" style="margin-top:3px;color:#2166f3">${escapeHtml(hashtagText)}</div>`
      : "";
    return `<div class="topic-suggestion" data-title="${escapeHtml(s.title)}"
      style="padding:12px 14px;${i>0?"border-top:1px solid #eef1f6":""}"
      onmouseover="this.style.background='#f5f8fd'" onmouseout="this.style.background=''"
    >
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;cursor:pointer" onclick="pickTopicSuggestion(this.parentElement)">
        <div style="min-width:0">
          <div style="font-weight:700">${medal}${escapeHtml(s.title)}</div>
          ${hook}
          ${visual}
          ${hashtags}
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
        <button type="button" onclick="event.stopPropagation();markTopicDone(this)" data-title="${escapeHtml(s.title)}"
          style="width:auto;min-height:30px;padding:0 10px;font-size:12px;font-weight:700;background:#f4f5f7;color:#4b5568;border:1px solid #e2e5ea;border-radius:8px;cursor:pointer"
        >🚫 Bunu yaptım, bir daha önerme</button>
        ${hashtagList.length ? `<button type="button" onclick="event.stopPropagation();copyHashtags(this)" data-hashtags="${escapeHtml(hashtagText)}"
          style="width:auto;min-height:30px;padding:0 10px;font-size:12px;font-weight:700;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5;border-radius:8px;cursor:pointer"
        >📋 Etiketleri kopyala</button>` : ""}
      </div>
    </div>`;
  }).join("");
  box.innerHTML=`
    <div class="hint" style="margin-bottom:8px;font-weight:700">🏆 En yüksek tıklama potansiyeline sahip 3 konu</div>
    <div style="border:1px solid #dbe5f4;border-radius:12px;padding:10px 14px;margin-bottom:12px;background:#f8fbff">${top3}</div>
    <div style="border:1px solid #dbe5f4;border-radius:12px;overflow:hidden">${rows}</div>
  `;
}

function copyHashtags(btn){
  const text=btn.getAttribute("data-hashtags");
  navigator.clipboard.writeText(text).then(()=>{
    const original=btn.textContent;
    btn.textContent="✅ Kopyalandı";
    setTimeout(()=>{btn.textContent=original;},1500);
  }).catch(()=>{
    alert(text);
  });
}

function pickTopicSuggestion(el){
  document.getElementById("topic").value=el.getAttribute("data-title");
  document.getElementById("topicSuggestions").style.display="none";
  updateMusicMoodSuggestion();
}

async function markTopicDone(btn){
  const title=btn.getAttribute("data-title");
  btn.disabled=true;
  btn.textContent="⏳...";
  try{
    const res=await fetch("/api/topic-history",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({title}),
    });
    if(!res.ok)throw new Error("İşaretlenemedi.");
    const row=btn.closest(".topic-suggestion");
    if(row)row.remove();
  }catch(err){
    btn.disabled=false;
    btn.textContent="✅ Bunu yaptım, bir daha önerme";
    alert("Hata: "+err.message);
  }
}

function onMusicToggle(){
  const on=document.getElementById("background_music_enabled").checked;
  document.getElementById("musicProviderRow").style.display=on?"block":"none";
  if(!on)onMusicProviderChange();
}

function onMusicProviderChange(){
  const p=document.getElementById("music_provider").value;
  const isBrowsable=(p==="jamendo"||p==="elevenlabs"||p==="freesound")&&document.getElementById("background_music_enabled").checked;
  document.getElementById("musicBrowseRow").style.display=isBrowsable?"block":"none";
  const btn=document.getElementById("musicSearchBtn");
  if(btn)btn.textContent=p==="elevenlabs"?"🎵 Üret":"🎧 Ara";
  const costHint=document.getElementById("musicCostHint");
  if(costHint)costHint.style.display=p==="elevenlabs"?"block":"none";
  if(!isBrowsable){
    document.getElementById("music_track").value="";
    document.getElementById("musicResults").innerHTML="";
    document.getElementById("musicSelectedInfo").style.display="none";
  } else {
    updateMusicMoodSuggestion();
  }
}

async function updateMusicMoodSuggestion(){
  if(document.getElementById("musicBrowseRow").style.display!=="block")return;
  const topic=document.getElementById("topic").value.trim();
  const contentType=document.getElementById("content_type").value;
  const box=document.getElementById("musicMoodTags");
  box.innerHTML='<span class="hint">Etiketler hazırlanıyor…</span>';
  try{
    const params=new URLSearchParams({topic, content_type: contentType});
    const res=await fetch(`/api/music-mood?${params.toString()}`);
    const data=await res.json();
    renderMusicMoodTags(data.tags||[]);
  }catch(e){
    box.innerHTML="";
  }
}

function renderMusicMoodTags(tags){
  const box=document.getElementById("musicMoodTags");
  if(!tags.length){box.innerHTML="";return;}
  box.innerHTML=tags.map(tag=>
    `<button type="button" class="music-tag-btn" data-tag="${escapeHtml(tag)}" onclick="addMusicTag(this)" style="width:auto;min-height:30px;margin-top:0;padding:0 12px;font-size:12px;font-weight:700;background:white;color:#2166f3;border:1px solid #cbd6e5;border-radius:999px;cursor:pointer">+ ${escapeHtml(tag)}</button>`
  ).join("");
}

function addMusicTag(btn){
  const tag=btn.getAttribute("data-tag");
  const input=document.getElementById("musicSearchQuery");
  const current=input.value.split(/\s+/).map(t=>t.trim()).filter(Boolean);
  if(!current.includes(tag)){
    current.push(tag);
    input.value=current.join(" ");
  }
}

function clearMusicSearch(){
  document.getElementById("musicSearchQuery").value="";
  document.getElementById("musicResults").innerHTML="";
  document.getElementById("music_track").value="";
  const info=document.getElementById("musicSelectedInfo");
  info.style.display="none";
  info.textContent="";
}

async function searchMusic(){
  const btn=document.getElementById("musicSearchBtn");
  const box=document.getElementById("musicResults");
  const query=document.getElementById("musicSearchQuery").value.trim();
  const contentType=document.getElementById("content_type").value;
  const provider=document.getElementById("music_provider").value;
  const isElevenLabs=provider==="elevenlabs";
  lastMusicProvider=provider;
  btn.disabled=true;
  btn.textContent=isElevenLabs?"⏳ Üretiliyor…":"⏳ Aranıyor…";
  const catalogLabel=provider==="freesound"?"Freesound’da":"Jamendo’da";
  box.innerHTML=isElevenLabs
    ? '<div class="hint">ElevenLabs ile arka plan müziği üretiliyor, bu birkaç saniye sürebilir…</div>'
    : `<div class="hint">${catalogLabel} telifsiz parçalar aranıyor…</div>`;
  try{
    const params=new URLSearchParams({query, content_type: contentType, provider});
    const res=await fetch(`/api/music-search?${params.toString()}`);
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||"Arama başarısız.");
    renderMusicResults(data.tracks||[]);
  }catch(err){
    box.innerHTML=`<div class="hint" style="color:#9f2020">${escapeHtml(err.message)}</div>`;
  }finally{
    btn.disabled=false;
    btn.textContent=isElevenLabs?"🎵 Üret":"🎧 Ara";
  }
}

function musicLicenseBadge(license){
  if(!license||license.commercial_ok===null||license.commercial_ok===undefined){
    return `<span style="color:#8899aa">Lisans bilinmiyor -- yüklemeden önce kontrol et</span>`;
  }
  const color=license.commercial_ok?"#08763a":"#9f2020";
  const icon=license.commercial_ok?"✅":"⚠️";
  return `<span style="color:${color};font-weight:700">${icon} ${escapeHtml(license.label||"")}</span>`;
}

let lastMusicResults=[];
let lastMusicProvider="jamendo";

function renderMusicResults(tracks){
  lastMusicResults=tracks;
  const box=document.getElementById("musicResults");
  if(!tracks.length){
    box.innerHTML='<div class="hint">Sonuç bulunamadı, farklı bir arama dene.</div>';
    return;
  }
  box.innerHTML=tracks.map((t,i)=>{
    const dur=parseInt(t.duration)||0;
    const mins=Math.floor(dur/60);
    const secs=String(dur%60).padStart(2,"0");
    const label=`${t.name||"Untitled"} — ${t.artist||"Bilinmeyen sanatçı"}`;
    return `<div style="padding:10px 0;${i>0?"border-top:1px solid #eef1f6":""}">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
        <div>
          <div style="font-weight:700">${escapeHtml(t.name||"Untitled")}</div>
          <div class="hint">${escapeHtml(t.artist||"Bilinmeyen sanatçı")} · ${mins}:${secs}</div>
          <div class="hint" style="margin-top:2px">${musicLicenseBadge(t.license)}</div>
        </div>
        <div style="display:flex;gap:6px">
          <button type="button" onclick="addFavoriteFromResult(this,${i})" style="width:auto;min-height:36px;margin-top:0;padding:0 10px;font-size:13px;background:#fff;color:#9f5a00;border:1px solid #e2e7ee">☆ Favorile</button>
          <button type="button" class="music-pick-btn" data-url="${escapeHtml(t.download_url||"")}" data-label="${escapeHtml(label)}" onclick="selectMusicTrack(this)" style="width:auto;min-height:36px;margin-top:0;padding:0 14px;font-size:13px;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5">Bu parçayı seç</button>
        </div>
      </div>
      <audio class="df-audio-preview" onplay="pauseOtherAudio(this)" controls preload="none" src="${escapeHtml(t.preview_url||"")}" style="width:100%;margin-top:6px;height:34px"></audio>
    </div>`;
  }).join("");
}

function pauseOtherAudio(current){
  document.querySelectorAll("audio.df-audio-preview").forEach(a=>{
    if(a!==current) a.pause();
  });
}

async function addFavoriteFromResult(btn,index){
  const track=lastMusicResults[index];
  if(!track)return;
  btn.disabled=true;
  btn.textContent="⏳...";
  try{
    const res=await fetch("/api/music-favorites",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({provider:lastMusicProvider, ...track}),
    });
    if(!res.ok){
      const err=await res.json().catch(()=>({}));
      throw new Error(err.detail||"Favorilere eklenemedi.");
    }
    btn.textContent="★ Favoride";
    btn.style.background="#fff7e0";
    btn.style.color="#9f5a00";
    btn.style.border="1px solid #f0dca0";
    if(document.getElementById("musicFavoritesList").style.display==="block"){
      loadFavorites();
    }
  }catch(e){
    btn.disabled=false;
    btn.textContent="☆ Favorile";
    alert("Hata: "+e.message);
  }
}

function toggleFavoritesList(){
  const box=document.getElementById("musicFavoritesList");
  const btn=document.getElementById("favoritesToggleBtn");
  const showing=box.style.display==="block";
  box.style.display=showing?"none":"block";
  btn.textContent=showing?"Göster":"Gizle";
  if(!showing)loadFavorites();
}

async function loadFavorites(){
  const box=document.getElementById("musicFavoritesList");
  box.innerHTML='<div class="hint">Yükleniyor…</div>';
  try{
    const res=await fetch("/api/music-favorites");
    const data=await res.json();
    renderFavorites(data.favorites||[]);
  }catch(e){
    box.innerHTML='<div class="hint" style="color:#9f2020">Favoriler yüklenemedi.</div>';
  }
}

function renderFavorites(favorites){
  const box=document.getElementById("musicFavoritesList");
  if(!favorites.length){
    box.innerHTML='<div class="hint">Henüz favori yok -- sonuçların yanındaki ⭐ ile ekleyebilirsin.</div>';
    return;
  }
  box.innerHTML=favorites.map(f=>{
    const dur=parseInt(f.duration)||0;
    const mins=Math.floor(dur/60);
    const secs=String(dur%60).padStart(2,"0");
    const label=`${f.name||"Untitled"} — ${f.artist||"Bilinmeyen sanatçı"}`;
    return `<div style="padding:8px 0;border-top:1px solid #eef1f6">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap">
        <div>
          <div style="font-weight:700;font-size:13px">${escapeHtml(f.name||"Untitled")}</div>
          <div class="hint" style="font-size:12px">${escapeHtml(f.artist||"Bilinmeyen sanatçı")} · ${mins}:${secs} · ${escapeHtml(f.provider||"")}</div>
        </div>
        <div style="display:flex;gap:6px">
          <button type="button" class="fav-select-btn" data-url="${escapeHtml(f.download_url||"")}" data-label="${escapeHtml(label)}" onclick="selectFavorite(this)" style="width:auto;min-height:30px;margin-top:0;padding:0 10px;font-size:12px;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5">Seç</button>
          <button type="button" data-provider="${escapeHtml(f.provider||"")}" data-id="${escapeHtml(f.id||"")}" onclick="removeFavorite(this)" style="width:auto;min-height:30px;margin-top:0;padding:0 10px;font-size:12px;background:#fde8e8;color:#9f2020;border:1px solid #f3c9c9">🗑</button>
        </div>
      </div>
      <audio class="df-audio-preview" onplay="pauseOtherAudio(this)" controls preload="none" src="${escapeHtml(f.preview_url||"")}" style="width:100%;margin-top:6px;height:32px"></audio>
    </div>`;
  }).join("");
}

function selectFavorite(btn){
  document.getElementById("music_track").value=btn.dataset.url;
  const info=document.getElementById("musicSelectedInfo");
  info.style.display="block";
  info.textContent="🎵 Seçilen parça: "+btn.dataset.label;
}

async function removeFavorite(btn){
  try{
    const res=await fetch(`/api/music-favorites/${encodeURIComponent(btn.dataset.provider)}/${encodeURIComponent(btn.dataset.id)}`,{method:"DELETE"});
    if(!res.ok)throw new Error("Kaldırılamadı.");
    loadFavorites();
  }catch(e){
    alert("Hata: "+e.message);
  }
}

function selectMusicTrack(btn){
  document.querySelectorAll(".music-pick-btn").forEach(b=>{
    b.textContent="Bu parçayı seç";
    b.style.background="#eef3fc";
    b.style.color="#2166f3";
    b.style.border="1px solid #cbd6e5";
  });
  btn.textContent="✅ Seçildi";
  btn.style.background="#08763a";
  btn.style.color="white";
  btn.style.border="1px solid #08763a";

  const url=btn.getAttribute("data-url");
  const label=btn.getAttribute("data-label");
  document.getElementById("music_track").value=url;
  const info=document.getElementById("musicSelectedInfo");
  info.style.display="block";
  info.textContent="🎵 Seçilen parça: "+label;
}

function onSubtitlesToggle(){
  const on=document.getElementById("subtitles_enabled").checked;
  const label=document.getElementById("burnInLabel");
  const hint=document.getElementById("burnInHint");
  label.style.display=on?"flex":"none";
  hint.style.display=on?"block":"none";
  if(!on)document.getElementById("subtitles_burn_in").checked=false;
}

function onThumbnailToggle(){
  const on=document.getElementById("thumbnail_enabled").checked;
  document.getElementById("thumbnailSourceRow").style.display=on?"block":"none";
}

function onProviderChange(){
  const p=document.getElementById("voice_provider").value;
  const n=document.getElementById("voice_name");
  n.innerHTML="";
  if(p==="supertonic"){
    ["M1","M2","M3","F1","F2","F3"].forEach(v=>{
      const o=document.createElement("option");o.value=v;o.textContent=v;n.appendChild(o);
    });
  } else if(p==="xtts"){
    const o=document.createElement("option");o.value="clone";o.textContent="Klon Sesim";n.appendChild(o);
  } else {
    const o=document.createElement("option");o.value="default";o.textContent="Varsay\u0131lan";n.appendChild(o);
  }
}

document.getElementById("duration").addEventListener("input",updateHint);
document.getElementById("topic").addEventListener("blur",updateMusicMoodSuggestion);
onManualUploadToggle();

(function applyPendingPrefill(){
  const raw=sessionStorage.getItem("docuforge_prefill");
  if(!raw)return;
  sessionStorage.removeItem("docuforge_prefill");
  let prefill;
  try{prefill=JSON.parse(raw);}catch(e){return;}
  if(prefill.topic)document.getElementById("topic").value=prefill.topic;
  if(prefill.source_material)document.getElementById("source_material").value=prefill.source_material;
  if(prefill.source_citation)document.getElementById("source_citation").value=prefill.source_citation;
  if(prefill.content_type)document.getElementById("content_type").value=prefill.content_type;
  onTypeChange();
})();

function deriveTopicFromSource(){
  const topicEl=document.getElementById("topic");
  if(topicEl.value.trim())return;
  const src=document.getElementById("source_material").value.trim();
  if(!src)return;
  let firstLine=(src.split(String.fromCharCode(10)).find(l=>l.trim().length>0)||"").trim();
  if(firstLine.length>120)firstLine=firstLine.slice(0,120).trim();
  if(firstLine)topicEl.value=firstLine;
}

function updateVerbatimHint(){
  const on=document.getElementById("verbatim_script").checked;
  const hasSrc=document.getElementById("source_material").value.trim().length>0;
  const hint=document.getElementById("verbatimHint");
  if(on){
    hint.textContent=hasSrc
      ? "✅ Açık: Kaynak Metin birebir senaryo olarak kullanılacak. Araştırma ve senaryo yazma adımları atlanacak."
      : "⚠️ Açık ama Kaynak Metin boş — senaryonu yukarıya yapıştır.";
    hint.style.color=hasSrc?"#166534":"#92400e";
  }else{
    hint.textContent="Kapalı: DocuForge kaynak metni referans alarak kendi senaryosunu yazar.";
    hint.style.color="";
  }
}

async function startBuild(){
  const btn=document.getElementById("startButton");
  deriveTopicFromSource();
  const topic=document.getElementById("topic").value.trim();
  if(!topic){alert("Konu giriniz (ya da Kaynak Metin kutusuna bir metin yapıştır, konu otomatik doldurulsun).");return;}
  if(topic.length>200){alert("⚠️ Konu alanı en fazla 200 karakter olabilir.\\n\\nSenaryonu veya uzun metni 'Kaynak Metin' kutusuna yapıştır — Konu alanına sadece kısa bir başlık yaz (örn: 'Kuantum Fiziği').");return;}
  const verbatim=document.getElementById("verbatim_script").checked;
  if(verbatim&&!document.getElementById("source_material").value.trim()){alert("⚠️ 'Senaryoyu birebir kullan' açık ama Kaynak Metin boş.\\n\\nSenaryonu Kaynak Metin alanına yapıştır veya toggle'ı kapat.");return;}
  btn.disabled=true;
  const statusBox=document.getElementById("statusBox");
  statusBox.style.display="block";
  statusBox.className="status";
  document.getElementById("statusTitle").textContent="Proje olu\u015fturuluyor\u2026";
  document.getElementById("statusText").textContent="\u00dcretim i\u015fi sunucuya g\u00f6nderiliyor.";
  document.getElementById("progressBar").style.width="4%";
  document.getElementById("openProject").style.display="none";

  const payload={
    topic,
    source_material:document.getElementById("source_material").value.trim(),
    source_citation:document.getElementById("source_citation").value.trim(),
    verbatim_script:document.getElementById("verbatim_script").checked,
    language:document.getElementById("language").value,
    content_type:document.getElementById("content_type").value,
    target_duration_seconds:parseInt(document.getElementById("duration").value),
    media_mode:document.getElementById("media_mode").value,
    image_provider:document.getElementById("image_provider").value,
    video_provider:document.getElementById("video_provider").value,
    voice_provider:document.getElementById("voice_provider").value,
    voice_name:document.getElementById("voice_name").value,
    voice_speed:parseFloat(document.getElementById("voice_speed").value),
    resolution:document.getElementById("resolution").value,
    fps:parseInt(document.getElementById("fps").value),
    scene_transition:document.getElementById("scene_transition").value,
    background_music_enabled:document.getElementById("background_music_enabled").checked,
    music_provider:document.getElementById("music_provider").value,
    music_track:document.getElementById("music_track").value,
    music_volume:parseInt(document.getElementById("music_volume").value)/100,
    subtitles_enabled:document.getElementById("subtitles_enabled").checked,
    subtitles_burn_in:document.getElementById("subtitles_burn_in").checked,
    ai_disclosure_enabled:document.getElementById("ai_disclosure_enabled").checked,
    location_map_enabled:document.getElementById("location_map_enabled").checked,
    manual_upload_enabled:document.getElementById("manual_upload_enabled").checked,
    thumbnail_enabled:document.getElementById("thumbnail_enabled").checked,
    thumbnail_source:document.getElementById("thumbnail_source").value,
  };

  try{
    const r=await fetch("/api/builds",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const res=await r.json();
    if(!r.ok)throw new Error(_apiErr(res.detail)||"\u00dcretim ba\u015flat\u0131lamad\u0131.");
    document.getElementById("statusTitle").textContent="\u00dcretim devam ediyor";
    document.getElementById("statusText").textContent="Ara\u015ft\u0131rma, senaryo, medya, ses ve video haz\u0131rlan\u0131yor.";
    currentJobId=res.job_id;
    document.getElementById("cancelBuildButton").style.display="inline-block";
    document.getElementById("cancelBuildButton").disabled=false;
    document.getElementById("cancelBuildButton").textContent="\u23f9 \u0130ptal Et";
    pollJob(res.job_id);
  }catch(e){showError(e.message);}
}

async function cancelBuild(){
  if(!currentJobId)return;
  if(!confirm("\u00dcretimi iptal etmek istedi\u011fine emin misin? Mevcut ad\u0131m bitene kadar durmaz, sonras\u0131nda duracak."))return;

  const btn=document.getElementById("cancelBuildButton");
  btn.disabled=true;
  btn.textContent="\u0130ptal ediliyor\u2026";

  try{
    const r=await fetch(`/api/builds/${currentJobId}/cancel`,{method:"POST"});
    const res=await r.json();
    if(!r.ok)throw new Error(res.detail||"\u0130ptal edilemedi.");
    document.getElementById("statusText").textContent="\u0130ptal ediliyor\u2026 mevcut ad\u0131m bitince duracak.";
  }catch(e){
    alert("Hata: "+e.message);
    btn.disabled=false;
    btn.textContent="\u23f9 \u0130ptal Et";
  }
}

async function pollJob(jobId){
  clearTimeout(pollTimer);

  let r;
  try{
    r=await fetch(`/api/builds/${jobId}`);
  }catch(networkError){
    // Sekme arka plana at\u0131ld\u0131\u011f\u0131nda ya da ba\u011flant\u0131 ge\u00e7ici
    // kesildi\u011finde fetch() burada atar -- \u00fcretimin durdu\u011fu anlam\u0131na
    // gelmez, sunucuda arka planda \u00e7al\u0131\u015fmaya devam ediyor olabilir.
    // Sessizce yeniden dene, hemen ba\u015far\u0131s\u0131z say\u0131p durma.
    document.getElementById("statusText").textContent="Ba\u011flant\u0131 kontrol ediliyor\u2026";
    pollTimer=setTimeout(()=>pollJob(jobId),3000);
    return;
  }

  try{
    const job=await r.json();
    if(!r.ok)throw new Error(job.detail||"\u0130\u015f durumu al\u0131namad\u0131.");
    const pct=Math.max(4,Math.min(100,Number(job.progress_percent||4)));
    document.getElementById("progressBar").style.width=`${pct}%`;
    if(job.current_step)document.getElementById("statusText").textContent=`${job.completed_steps}/${job.total_steps||"?"} \u00b7 ${job.current_step}`;
    if(job.status==="completed"){
      const sb=document.getElementById("statusBox");
      sb.className="status success";
      document.getElementById("statusTitle").textContent="Video haz\u0131r";
      document.getElementById("statusText").textContent="T\u00fcm \u00fcretim a\u015famalar\u0131 tamamland\u0131.";
      document.getElementById("progressBar").style.width="100%";
      const op=document.getElementById("openProject");
      op.href=`/projects/${job.project_slug}`;
      op.style.display="inline-block";
      document.getElementById("startButton").disabled=false;
      return;
    }
    if(job.status==="failed"){showError(job.error||"\u00dcretim s\u0131ras\u0131nda hata olu\u015ftu.");return;}
    pollTimer=setTimeout(()=>pollJob(jobId),2500);
  }catch(e){showError(e.message);}
}

function _apiErr(detail){
  if(!detail)return "";
  if(typeof detail==="string")return detail;
  if(Array.isArray(detail))return detail.map(d=>d.msg||d.message||JSON.stringify(d)).join("; ");
  if(typeof detail==="object")return detail.msg||detail.message||detail.detail||JSON.stringify(detail);
  return String(detail);
}
function showError(msg){
  clearTimeout(pollTimer);
  const sb=document.getElementById("statusBox");
  sb.style.display="block";sb.className="status error";
  document.getElementById("statusTitle").textContent="\u00dcretim ba\u015far\u0131s\u0131z";
  document.getElementById("statusText").textContent=typeof msg==="string"?msg:_apiErr(msg);
  document.getElementById("progressBar").style.width="100%";
  document.getElementById("startButton").disabled=false;
}
</script>
<script>
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}
</script>
<nav class="bottom-nav">
    <a href="/"><span class="nav-icon">\U0001F3E0</span>Ana Sayfa</a>
    <a href="/voice-test"><span class="nav-icon">\U0001F3A4</span>Ses Testi</a>
    <a href="/storage"><span class="nav-icon">\U0001F4E6</span>Depolama</a>
    <a href="/settings"><span class="nav-icon">⚙</span>Ayarlar</a>
</nav>
</body></html>""")


class TopicSuggestionsRequest(BaseModel):
    content_type: str = Field(default="documentary")
    language: str = Field(default="tr")


@router.post("/api/topic-suggestions")
def topic_suggestions(request: TopicSuggestionsRequest) -> dict[str, Any]:
    from app.services.topic_history import get_avoid_titles

    try:
        raw = TopicSuggestionAgent().run(
            language=request.language,
            content_type=request.content_type,
            avoid_titles=get_avoid_titles(),
        )
        return json.loads(raw)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Konu önerileri alınamadı: {error}",
        ) from error


class TopicHistoryRequest(BaseModel):
    title: str


@router.post("/api/topic-history")
def mark_topic_done(request: TopicHistoryRequest) -> dict[str, Any]:
    from app.services.topic_history import mark_done

    try:
        return mark_done(request.title)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/api/music-mood")
def music_mood(topic: str = "", content_type: str = "documentary") -> dict[str, Any]:
    """Short, individual English mood/genre tags for the music search box,
    derived from the project topic -- Jamendo's tag search matches best on
    a handful of short standalone tags, not one long AND-ed phrase, so this
    returns a list the UI renders as clickable chips rather than a single
    query string. Falls back to the plain content-type mood (same one
    /api/music-search itself falls back to) split into words if the topic
    is empty or the AI call fails, since this only ever prefills a text
    box the user can still edit before searching."""

    from app.services.render_service import RenderService

    fallback_tags = RenderService()._build_music_query(
        {"content_type": content_type}
    ).split()

    topic = topic.strip()

    if not topic:
        return {"tags": fallback_tags}

    try:
        from app.ai.factory import get_ai

        prompt = (
            "Suggest 6 short, individual music mood/genre tags (1-2 words "
            "each, e.g. 'cinematic', 'dark ambient', 'epic', 'uplifting') "
            "for searching royalty-free background music on Jamendo, "
            f"fitting a {content_type} video about this topic:\n\n{topic}\n\n"
            "Return ONLY a comma-separated list, lowercase. "
            "No numbering, no explanation, no quotes."
        )
        response = str(get_ai().generate(prompt)).strip()
        tags = [tag.strip() for tag in response.split(",") if tag.strip()]

        return {"tags": tags[:8] or fallback_tags}
    except Exception:
        return {"tags": fallback_tags}


@router.get("/api/music-search")
def music_search(
    query: str = "",
    content_type: str = "documentary",
    provider: str = "jamendo",
) -> dict[str, Any]:
    from app.services.render_service import RenderService

    search_query = query.strip() or RenderService()._build_music_query(
        {"content_type": content_type}
    )

    provider_key = provider.strip().lower() or "jamendo"

    try:
        if provider_key == "elevenlabs":
            from app.providers.music.elevenlabs import ElevenLabsMusicProvider

            music_provider = ElevenLabsMusicProvider()
            # A real, billed generation -- never more than the one
            # result search() already caps itself to.
            tracks = music_provider.search(search_query, limit=1)
        elif provider_key == "freesound":
            from app.providers.music.freesound import FreesoundMusicProvider

            music_provider = FreesoundMusicProvider()
            tracks = music_provider.search(search_query, limit=12)
        else:
            from app.providers.music.jamendo import JamendoMusicProvider

            music_provider = JamendoMusicProvider()
            tracks = music_provider.search(search_query, limit=12)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Müzik araması başarısız: {error}",
        ) from error

    return {"query": search_query, "tracks": tracks}


class FavoriteTrackRequest(BaseModel):
    provider: str
    id: str
    name: str = ""
    artist: str = ""
    duration: int = 0
    preview_url: str = ""
    download_url: str = ""
    license: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/music-favorites")
def get_music_favorites() -> dict[str, Any]:
    from app.services.music_favorites import list_favorites

    return {"favorites": list_favorites()}


@router.post("/api/music-favorites")
def post_music_favorite(request: FavoriteTrackRequest) -> dict[str, Any]:
    from app.services.music_favorites import add_favorite

    if not request.provider.strip() or not request.id.strip():
        raise HTTPException(status_code=400, detail="Geçersiz parça bilgisi.")

    entry = add_favorite(request.model_dump(), request.provider.strip())

    return {"favorite": entry}


@router.delete("/api/music-favorites/{provider}/{track_id}")
def delete_music_favorite(provider: str, track_id: str) -> dict[str, Any]:
    from app.services.music_favorites import remove_favorite

    if not remove_favorite(provider, track_id):
        raise HTTPException(status_code=404, detail="Favori bulunamadı.")

    return {"removed": True}


@router.get("/music-cache/elevenlabs/{filename}")
def elevenlabs_music_cache_file(filename: str):
    from app.providers.music.elevenlabs import ElevenLabsMusicProvider

    cache_dir = ElevenLabsMusicProvider.CACHE_DIR.resolve()
    requested = (cache_dir / filename).resolve()

    if cache_dir not in requested.parents or not requested.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

    return FileResponse(requested)


@router.post("/api/builds")
def create_build(request: BuildRequest) -> dict[str, Any]:
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Proje konusu boş olamaz.")

    project_slug = ProjectService().resolve_unique_slug(topic)
    project_dir = PROJECTS_ROOT / project_slug
    job_id = uuid.uuid4().hex

    req = request.model_dump()
    req["topic"] = topic

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "kind": "build",
            "topic": topic,
            "project_slug": project_slug,
            "project_path": str(project_dir),
            "error": None,
            "request": req,
        }
        _persist_job(job_id)

    CANCEL_EVENTS[job_id] = threading.Event()

    thread = threading.Thread(
        target=_execute_build,
        args=(job_id, req, project_dir),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "queued", "project_slug": project_slug}


@router.post("/api/projects/{slug}/resume")
def resume_project(slug: str) -> dict[str, Any]:
    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "kind": "build",
            "topic": slug,
            "project_slug": slug,
            "project_path": str(project_dir),
            "error": None,
            "request": {},
        }
        _persist_job(job_id)

    CANCEL_EVENTS[job_id] = threading.Event()

    thread = threading.Thread(
        target=_execute_build,
        args=(job_id, {}, project_dir),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "queued", "project_slug": slug}


@router.get("/api/projects/{slug}/manual-media")
def manual_media_status(slug: str) -> dict[str, Any]:
    """List each scene's image prompt + whether a manual image is uploaded.

    Drives the "elle yükleme" card on the project page: the user reads each
    prompt, generates the image (e.g. in ChatGPT), uploads it, then resumes.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    project_data = load_json(project_dir / "project.json")
    is_manual = bool(project_data.get("manual_upload_enabled"))

    storyboard = load_json(project_dir / "storyboard.json")
    scenes_raw = (
        storyboard.get("scenes") if isinstance(storyboard, dict) else None
    )

    builder = MediaBuilder()
    prompts = builder._load_image_prompts_by_scene(project_dir)
    prompt_items = builder._load_image_prompt_items_by_scene(project_dir)

    # Rich per-scene guidance from ImagePromptAgent.
    guidance_by_scene: dict[int, dict[str, Any]] = {}
    image_prompts_raw = load_json(project_dir / "image_prompts.json")

    for item in image_prompts_raw.get("images", []) or []:
        if not isinstance(item, dict):
            continue

        scene_no = item.get("scene")

        if not isinstance(scene_no, int):
            continue

        guidance_by_scene[scene_no] = {
            "visual_summary": str(
                item.get("visual_summary") or ""
            ).strip(),
            "generation_goal": str(
                item.get("generation_goal") or ""
            ).strip(),
            "recommended_source": str(
                item.get("recommended_source") or "stock"
            ).strip().lower(),
            "recommendation_reason": str(
                item.get("recommendation_reason") or ""
            ).strip(),
            "visual_category": str(
                item.get("visual_category") or "general"
            ).strip(),
            "authenticity_note": str(
                item.get("authenticity_note") or ""
            ).strip(),
            "sensitive": bool(item.get("sensitive")),
            "sensitive_reason": str(
                item.get("sensitive_reason") or ""
            ).strip(),
        }

    scenes: list[dict[str, Any]] = []

    if isinstance(scenes_raw, list):
        for index, scene in enumerate(scenes_raw, start=1):
            scene_number = (
                scene.get("scene", index)
                if isinstance(scene, dict)
                else index
            )
            scene_dir = (
                project_dir / "media" / f"scene_{scene_number:03d}"
            )
            uploaded = builder.find_manual_upload(scene_dir)

            title = ""
            if isinstance(scene, dict):
                title = str(scene.get("title") or "")

            guidance = guidance_by_scene.get(
                scene_number,
                {},
            )

            prompt_item = prompt_items.get(scene_number)
            full_prompt = (
                builder.compose_full_image_prompt(prompt_item)
                if prompt_item is not None
                else prompts.get(scene_number, "")
            )

            scenes.append({
                "scene": scene_number,
                "title": title,
                "prompt": prompts.get(scene_number, ""),
                "full_prompt": full_prompt,
                "visual_summary": guidance.get(
                    "visual_summary",
                    "",
                ),
                "generation_goal": guidance.get(
                    "generation_goal",
                    "",
                ),
                "recommended_source": guidance.get(
                    "recommended_source",
                    "stock",
                ),
                "recommendation_reason": guidance.get(
                    "recommendation_reason",
                    "",
                ),
                "visual_category": guidance.get(
                    "visual_category",
                    "general",
                ),
                "authenticity_note": guidance.get(
                    "authenticity_note",
                    "",
                ),
                "uploaded": uploaded is not None,
                "sensitive": bool(
                    guidance.get("sensitive", False)
                ),
                "sensitive_reason": guidance.get(
                    "sensitive_reason",
                    "",
                ),
                "url": (
                    f"/files/{slug}/media/"
                    f"scene_{scene_number:03d}/{uploaded.name}"
                    if uploaded is not None
                    else None
                ),
            })

    all_uploaded = bool(scenes) and all(
        item["uploaded"] for item in scenes
    )

    final_video = project_dir / "render" / "final_video.mp4"
    render_done = (
        final_video.exists() and final_video.stat().st_size > 0
    )

    # "awaiting" = the media step is paused for the user's upload decision:
    # manual enabled, they haven't pressed Devam Et yet (marker absent), and
    # the video isn't already rendered.
    marker = project_dir / "media" / MediaBuilder.MANUAL_READY_MARKER
    awaiting = is_manual and not marker.exists() and not render_done

    return {
        "manual": is_manual,
        "scenes": scenes,
        "all_uploaded": all_uploaded,
        "render_done": render_done,
        "awaiting": awaiting,
    }


@router.post("/api/projects/{slug}/manual-media/{scene}/upload")
async def manual_media_upload(
    slug: str,
    scene: int,
    file: UploadFile,
) -> dict[str, Any]:
    """Save a hand-supplied image for one scene (manual image provider)."""

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    extension_by_type = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    extension = extension_by_type.get((file.content_type or "").lower())

    if extension is None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png", ".webp"):
            extension = ".jpg" if suffix == ".jpeg" else suffix

    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Sadece JPG, PNG veya WEBP görsel yükleyebilirsin.",
        )

    data = await file.read()

    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya.")

    if len(data) > 20_000_000:
        raise HTTPException(
            status_code=400,
            detail="Görsel çok büyük (en fazla 20 MB).",
        )

    scene_dir = project_dir / "media" / f"scene_{scene:03d}"
    scene_dir.mkdir(parents=True, exist_ok=True)

    # Clear anything already sitting in this scene's directory (an
    # earlier manual upload, or an auto-picked image.jpg/scene.mp4 if
    # this scene had already gone through the normal provider flow at
    # some point) -- otherwise a stale file could keep winning
    # RenderService's/current_scene_asset's own picker over this upload.
    MediaBuilder().clear_scene_media(scene_dir)

    destination = scene_dir / f"manual{extension}"
    destination.write_bytes(data)

    return {
        "ok": True,
        "scene": scene,
        "url": f"/files/{slug}/media/scene_{scene:03d}/{destination.name}",
    }


@router.post("/api/projects/{slug}/manual-media/continue")
def manual_media_continue(slug: str) -> dict[str, Any]:
    """Finish the manual-upload step and resume the build.

    Writes the "ready" marker so the media step no longer pauses -- scenes
    the user uploaded use their image, the rest fall back to the configured
    provider -- then resumes the pipeline from the media step onward.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    media_dir = project_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / MediaBuilder.MANUAL_READY_MARKER).write_text(
        json.dumps({"ready": True}, ensure_ascii=False),
        encoding="utf-8",
    )

    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "kind": "build",
            "topic": slug,
            "project_slug": slug,
            "project_path": str(project_dir),
            "error": None,
            "request": {},
        }
        _persist_job(job_id)

    CANCEL_EVENTS[job_id] = threading.Event()

    thread = threading.Thread(
        target=_execute_build,
        args=(job_id, {}, project_dir),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "queued", "project_slug": slug}


SCENE_MEDIA_EXTENSION_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
}


def _provider_search_capable(category: str, key: str) -> bool:
    """Whether this configured provider supports browsing multiple
    results (stock search) vs. only ever producing one fresh AI
    generation per call. Any failure to even construct the provider
    (e.g. missing API key) is treated as "not browsable" -- the review
    UI just hides the browse button rather than erroring.
    """

    try:
        from app.providers.defaults import register_default_providers
        from app.providers.registry import ProviderRegistry

        register_default_providers()
        provider = ProviderRegistry.create(category=category, key=key)
        return hasattr(provider, "search")
    except Exception:
        return False


@router.get("/api/projects/{slug}/scene-media")
def scene_media_status(slug: str) -> dict[str, Any]:
    """Per-scene current media + prompt/guidance for the always-available
    "Sahne Medyasını Düzenle" review UI.

    Unlike /manual-media (which only shows while the media step is
    paused, pre-render, waiting on optional hand-uploads), this works any
    time after the media step has produced something -- including after
    the final video is already rendered -- so a single mismatched scene
    (e.g. a stock search returning an irrelevant clip) can be reviewed
    and fixed without redoing the whole build.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    media_dir = project_dir / "media"
    manifest_path = media_dir / "manifest.json"

    if not manifest_path.exists():
        return {"available": False, "scenes": []}

    storyboard = load_json(project_dir / "storyboard.json")
    scenes_raw = (
        storyboard.get("scenes") if isinstance(storyboard, dict) else None
    )

    builder = MediaBuilder()
    image_prompts = builder._load_image_prompts_by_scene(project_dir)
    image_prompt_items = builder._load_image_prompt_items_by_scene(project_dir)
    video_prompts = builder._load_video_prompts_by_scene(project_dir)

    guidance_by_scene: dict[int, dict[str, Any]] = {}
    image_prompts_raw = load_json(project_dir / "image_prompts.json")

    for item in image_prompts_raw.get("images", []) or []:
        if not isinstance(item, dict):
            continue

        scene_no = item.get("scene")

        if not isinstance(scene_no, int):
            continue

        guidance_by_scene[scene_no] = {
            "visual_summary": str(
                item.get("visual_summary") or ""
            ).strip(),
            "generation_goal": str(
                item.get("generation_goal") or ""
            ).strip(),
            "recommended_source": str(
                item.get("recommended_source") or "stock"
            ).strip().lower(),
            "recommendation_reason": str(
                item.get("recommendation_reason") or ""
            ).strip(),
            "authenticity_note": str(
                item.get("authenticity_note") or ""
            ).strip(),
            "sensitive": bool(item.get("sensitive")),
            "sensitive_reason": str(
                item.get("sensitive_reason") or ""
            ).strip(),
        }

    manifest = load_json(manifest_path)
    manifest_by_scene: dict[int, dict[str, Any]] = {}

    for item in manifest.get("scenes", []) or []:
        if isinstance(item, dict) and isinstance(item.get("scene"), int):
            manifest_by_scene[item["scene"]] = item

    project_data = load_json(project_dir / "project.json")

    image_search_capable = _provider_search_capable(
        "image", str(project_data.get("image_provider", "pexels"))
    )
    video_search_capable = _provider_search_capable(
        "video", str(project_data.get("video_provider", "pexels"))
    )

    scenes: list[dict[str, Any]] = []

    if isinstance(scenes_raw, list):
        for index, scene in enumerate(scenes_raw, start=1):
            scene_number = (
                scene.get("scene", index)
                if isinstance(scene, dict)
                else index
            )
            scene_dir = media_dir / f"scene_{scene_number:03d}"
            title = (
                str(scene.get("title") or "")
                if isinstance(scene, dict)
                else ""
            )

            current_path = builder.current_scene_asset(scene_dir)
            manifest_entry = manifest_by_scene.get(scene_number, {})

            current_media_type = None
            current_url = None

            if current_path is not None:
                current_media_type = (
                    "video"
                    if current_path.suffix.lower() == ".mp4"
                    else "image"
                )
                current_url = (
                    f"/files/{slug}/media/"
                    f"scene_{scene_number:03d}/{current_path.name}"
                )

            current_provider = manifest_entry.get("provider")
            guidance = guidance_by_scene.get(scene_number, {})

            prompt_item = image_prompt_items.get(scene_number)
            full_image_prompt = (
                builder.compose_full_image_prompt(prompt_item)
                if prompt_item is not None
                else image_prompts.get(scene_number, "")
            )

            scenes.append({
                "scene": scene_number,
                "title": title,
                "image_prompt": image_prompts.get(scene_number, ""),
                "full_image_prompt": full_image_prompt,
                "video_prompt": video_prompts.get(scene_number, ""),
                "visual_summary": guidance.get("visual_summary", ""),
                "generation_goal": guidance.get("generation_goal", ""),
                "recommended_source": guidance.get(
                    "recommended_source", "stock"
                ),
                "recommendation_reason": guidance.get(
                    "recommendation_reason", ""
                ),
                "authenticity_note": guidance.get(
                    "authenticity_note", ""
                ),
                "sensitive": bool(guidance.get("sensitive", False)),
                "sensitive_reason": guidance.get("sensitive_reason", ""),
                "current_media_type": current_media_type,
                "current_url": current_url,
                "current_provider": current_provider,
                "current_query": manifest_entry.get("query", ""),
                "current_status": manifest_entry.get("status"),
                "current_local_path": manifest_entry.get("local_path"),
                "is_manual": current_provider == "manual",
            })

    return {
        "available": True,
        "image_search_capable": image_search_capable,
        "video_search_capable": video_search_capable,
        "scenes": scenes,
    }


@router.post("/api/projects/{slug}/scene-media/{scene}/upload")
async def scene_media_upload(
    slug: str,
    scene: int,
    file: UploadFile,
) -> dict[str, Any]:
    """Replace one scene's media with a hand-supplied image or video --
    e.g. an AI image generated (in ChatGPT or elsewhere) from the
    scene's own prompt, or any other file the user picked -- without
    touching any other scene. This is the "Yeniden Üret" fix flow, not
    the pre-build manual-upload pause: it works after the video is
    already rendered too.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    extension = SCENE_MEDIA_EXTENSION_BY_TYPE.get(
        (file.content_type or "").lower()
    )

    if extension is None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png", ".webp", ".mp4"):
            extension = ".jpg" if suffix == ".jpeg" else suffix

    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Sadece JPG, PNG, WEBP görsel veya MP4 video yükleyebilirsin.",
        )

    data = await file.read()

    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya.")

    max_size = 200_000_000 if extension == ".mp4" else 20_000_000

    if len(data) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya çok büyük (en fazla {max_size // 1_000_000} MB).",
        )

    builder = MediaBuilder()

    try:
        asset, path = builder.save_manual_scene_media(
            str(project_dir), scene, data, extension
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "ok": True,
        "scene": scene,
        "media_type": asset.media_type,
        "url": f"/files/{slug}/media/scene_{scene:03d}/{path.name}",
    }


@router.post("/api/projects/{slug}/scene-media/{scene}/regenerate")
def scene_media_regenerate(slug: str, scene: int) -> dict[str, Any]:
    """Automatically try a different pick for one scene -- stock search
    excludes the currently-used result, AI generation is naturally
    different each call. The "Otomatik Başka Dene" action.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    builder = MediaBuilder()

    try:
        asset, path = builder.regenerate_scene(str(project_dir), scene)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {
        "ok": True,
        "scene": scene,
        "media_type": asset.media_type,
        "provider": asset.provider,
        "url": f"/files/{slug}/media/scene_{scene:03d}/{path.name}",
    }


@router.get("/api/projects/{slug}/scene-media/{scene}/alternatives")
def scene_media_alternatives(
    slug: str,
    scene: int,
    media_type: str = "image",
) -> dict[str, Any]:
    """List alternate stock candidates for one scene -- the "Başka Stok
    Seç" browse action. Only meaningful for search-based providers.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    builder = MediaBuilder()

    try:
        results = builder.search_scene_alternatives(
            str(project_dir), scene, media_type, limit=6
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {"scene": scene, "media_type": media_type, "results": results}


class SceneMediaSelectRequest(BaseModel):
    asset_id: str
    provider: str
    media_type: str
    download_url: str
    preview_url: str | None = None
    page_url: str | None = None
    author: str | None = None
    license: str | None = None
    width: float | None = None
    height: float | None = None
    duration: float | None = None


@router.post("/api/projects/{slug}/scene-media/{scene}/select")
def scene_media_select(
    slug: str,
    scene: int,
    request: SceneMediaSelectRequest,
) -> dict[str, Any]:
    """Download a candidate the user picked from the alternatives list
    and make it this scene's canonical asset.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    builder = MediaBuilder()

    try:
        asset, path = builder.select_scene_alternative(
            str(project_dir), scene, request.model_dump()
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {
        "ok": True,
        "scene": scene,
        "media_type": asset.media_type,
        "url": f"/files/{slug}/media/scene_{scene:03d}/{path.name}",
    }


VALID_OVERLAY_STYLES = {"bold", "regular", "bold_italic"}
VALID_OVERLAY_POSITIONS = {
    "top_left", "top_center", "top_right",
    "middle_left", "center", "middle_right",
    "bottom_left", "bottom_center", "bottom_right",
}


class SceneTextOverlayRequest(BaseModel):
    text: str = Field(default="", max_length=200)
    color: str = Field(default="#ffffff")
    style: str = Field(default="bold")
    position: str = Field(default="bottom_center")


@router.post("/api/projects/{slug}/scene-text-overlays/{scene}")
def save_scene_text_overlay(
    slug: str,
    scene: int,
    request: SceneTextOverlayRequest,
) -> dict[str, Any]:
    """Save (or clear, if text is blank) one scene's custom on-screen
    text overlay. Burned into that exact scene's on-screen time window
    on the next render -- see RenderService._burn_scene_text_overlays.
    Lets each project look hand-designed instead of every video coming
    out of the same visual template.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    style = (
        request.style if request.style in VALID_OVERLAY_STYLES else "bold"
    )
    position = (
        request.position
        if request.position in VALID_OVERLAY_POSITIONS
        else "bottom_center"
    )
    color = request.color.strip() or "#ffffff"

    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise HTTPException(
            status_code=400,
            detail="Renk #RRGGBB formatında olmalı (örn. #ffcc00).",
        )

    overlays_path = project_dir / "text_overlays.json"
    data: dict[str, Any] = {}

    if overlays_path.exists():
        try:
            data = json.loads(overlays_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    scenes = data.get("scenes")

    if not isinstance(scenes, dict):
        scenes = {}

    text = request.text.strip()

    if text:
        scenes[str(scene)] = {
            "text": text,
            "color": color,
            "style": style,
            "position": position,
        }
    else:
        scenes.pop(str(scene), None)

    data["scenes"] = scenes

    overlays_path.parent.mkdir(parents=True, exist_ok=True)
    overlays_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"ok": True, "scene": scene, "cleared": not text}


@router.post("/api/projects/{slug}/regenerate/{step_key}")
def regenerate_project_step(
    slug: str,
    step_key: str,
    request: RegenerateRequest = RegenerateRequest(),
) -> dict[str, Any]:
    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    valid_keys = {key for key, _label in PIPELINE_STEP_ORDER}

    if step_key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz aşama: {step_key}",
        )

    overrides = request.overrides
    allowed = STEP_ALLOWED_OVERRIDES.get(step_key, set())
    unknown = set(overrides) - allowed

    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{step_key}' aşaması şu ayarları kabul etmiyor: "
                f"{', '.join(sorted(unknown))}. "
                f"İzin verilenler: {', '.join(sorted(allowed)) or '(yok)'}"
            ),
        )

    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "kind": "regenerate",
            "step_key": step_key,
            "overrides": overrides,
            "topic": slug,
            "project_slug": slug,
            "project_path": str(project_dir),
            "error": None,
        }
        _persist_job(job_id)

    thread = threading.Thread(
        target=_execute_regenerate,
        args=(job_id, project_dir, step_key, overrides),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "queued", "project_slug": slug}


def compute_pipeline_progress(
    project_dir: Path,
    job_status: str | None = None,
) -> dict[str, Any]:
    """Compute step-by-step progress for a project from disk state alone.

    Works from project_dir only (no job_id needed), so it's usable both
    by /api/builds/{job_id} and by anything listing projects/jobs that
    aren't tied to a specific in-memory job (e.g. the dashboard).
    """

    project_data = load_json(project_dir / "project.json")
    pipeline_state = load_json(project_dir / "pipeline_state.json")
    steps = pipeline_state.get("steps", {})

    thumbnail_enabled = bool(project_data.get("thumbnail_enabled"))
    active_steps = [
        (key, label)
        for key, label in PIPELINE_STEP_ORDER
        if key != "thumbnail" or thumbnail_enabled
    ]
    total_steps = len(active_steps)

    completed_steps = 0
    current_step = "İş sırası bekleniyor"
    current_step_key: str | None = None
    failed_step_key: str | None = None

    if isinstance(steps, dict):
        for key, _label in active_steps:
            step_info = steps.get(key)
            if isinstance(step_info, dict) and step_info.get("status") == "completed":
                completed_steps += 1
            else:
                break

        failed_step = pipeline_state.get("failed_step")

        if pipeline_state.get("status") == "cancelled":
            current_step = "İptal edildi"
        elif failed_step:
            failed_label = dict(active_steps).get(failed_step, failed_step)
            current_step = f"Hata: {failed_label}"
            failed_step_key = str(failed_step)
        elif completed_steps < total_steps:
            current_step_key = active_steps[completed_steps][0]
            current_step = f"{active_steps[completed_steps][1]} çalışıyor"
        else:
            current_step = "Tamamlandı"

    if job_status == "completed":
        completed_steps = total_steps
        current_step = "Tamamlandı"
        current_step_key = None
    elif job_status == "cancelled":
        current_step = "İptal edildi"
        current_step_key = None

    return {
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "current_step": current_step,
        "current_step_key": current_step_key,
        "failed_step_key": failed_step_key,
        "progress_percent": (
            round(min(completed_steps, total_steps) / total_steps * 100)
            if total_steps
            else 0
        ),
    }


@router.get("/api/projects/{slug}/step-options/{step_key}")
def step_options(slug: str, step_key: str) -> dict[str, Any]:
    """What can be changed before regenerating this step, and its current values.

    Drives the "Yeniden Üret" form on the project page: which fields are
    editable for this step (per STEP_ALLOWED_OVERRIDES), their current
    project.json values, and -- for provider fields -- the choices
    actually registered right now (so a newly added provider shows up
    with no frontend change needed).
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    allowed = STEP_ALLOWED_OVERRIDES.get(step_key, set())
    project_data = load_json(project_dir / "project.json")
    current = {field: project_data.get(field) for field in allowed}

    from app.providers.defaults import register_default_providers
    from app.providers.registry import ProviderRegistry

    register_default_providers()

    choices: dict[str, list[dict[str, str]]] = {}
    provider_categories = {
        "voice_provider": "voice",
        "image_provider": "image",
        "video_provider": "video",
        "music_provider": "music",
    }

    for field, category in provider_categories.items():
        if field in allowed:
            choices[field] = [
                {"key": definition.key, "name": definition.name}
                for definition in ProviderRegistry.all(category=category)
            ]

    if "music_provider" in choices:
        choices["music_provider"].insert(
            0,
            {"key": "local", "name": "Yerel (music/ klasörü)"},
        )

    if "thumbnail_hook_override" in allowed:
        seo_data = load_json(project_dir / "seo.json")
        titles = seo_data.get("titles")
        title_choices = [
            {"key": title.strip(), "name": title.strip()}
            for title in titles
            if isinstance(title, str) and title.strip()
        ] if isinstance(titles, list) else []

        choices["thumbnail_hook_override"] = [
            {"key": "", "name": "Otomatik (SEO önerisi)"},
            *title_choices,
        ]

    return {
        "step_key": step_key,
        "allowed_fields": sorted(allowed),
        "current": current,
        "choices": choices,
        "content_type": project_data.get("content_type", "documentary"),
        "topic": project_data.get("title", ""),
    }


THUMBNAIL_VARIANTS = set(ThumbnailService.VARIANT_NAMES)


@router.get("/api/projects/{slug}/shorts-split")
def get_shorts_split(slug: str) -> dict[str, Any]:
    """Return previously-generated Shorts ideas for this project, if any
    -- avoids re-triggering a paid AI call just from loading the page.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    cache_path = project_dir / "shorts_ideas.json"

    if not cache_path.exists():
        return {"shorts": []}

    return load_json(cache_path) or {"shorts": []}


@router.post("/api/projects/{slug}/shorts-split")
def create_shorts_split(slug: str) -> dict[str, Any]:
    """Repurpose this project's finished script into 10 independent
    Shorts ideas -- lets a single long-form production also seed
    several short-form uploads without writing new source material.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    script_path = project_dir / "script.md"

    if not script_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Bu proje için senaryo henüz üretilmemiş.",
        )

    script = script_path.read_text(encoding="utf-8").strip()

    if not script:
        raise HTTPException(
            status_code=400,
            detail="Senaryo dosyası boş.",
        )

    project_data = load_json(project_dir / "project.json")
    language = str(project_data.get("language", "tr")).strip().lower()

    try:
        raw = ShortsSplitAgent().run(
            script=script,
            language=language,
            count=10,
        )
        data = json.loads(raw)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Shorts üretilemedi: {error}",
        ) from error

    (project_dir / "shorts_ideas.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return data


class ThumbnailSelectRequest(BaseModel):
    variant: str


@router.post("/api/projects/{slug}/thumbnail/select")
def select_thumbnail(slug: str, req: ThumbnailSelectRequest) -> dict[str, Any]:
    """Make one of the 4 generated thumbnail variants canonical
    (thumbnail.jpg), for the "pick a cover" gallery on the project page.
    """

    project_dir = PROJECTS_ROOT / slug

    if not (project_dir / "project.json").exists():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    if req.variant not in THUMBNAIL_VARIANTS:
        raise HTTPException(status_code=400, detail="Geçersiz kapak seçimi.")

    variant_path = project_dir / req.variant

    if not variant_path.is_file():
        raise HTTPException(status_code=404, detail="Kapak dosyası bulunamadı.")

    from PIL import Image

    with Image.open(variant_path) as image:
        image.convert("RGB").save(
            project_dir / "thumbnail.jpg", format="JPEG", quality=92
        )

    project_data = load_json(project_dir / "project.json")
    project_data["thumbnail_selected"] = req.variant
    (project_dir / "project.json").write_text(
        json.dumps(project_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"selected": req.variant}


@router.delete("/api/projects/{slug}")
def delete_project(slug: str) -> dict[str, Any]:
    """Permanently remove a project directory and everything in it.

    Refuses while a build/regenerate job for this project is still
    queued or running, so a background thread never gets its working
    directory pulled out from under it mid-write.
    """

    project_dir = (PROJECTS_ROOT / slug).resolve()

    if (
        PROJECTS_ROOT.resolve() not in project_dir.parents
        or not project_dir.is_dir()
    ):
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    with JOBS_LOCK:
        active_job = next(
            (
                job for job in JOBS.values()
                if job.get("project_slug") == slug
                and job.get("status") in ("queued", "running")
            ),
            None,
        )

    if active_job is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu proje için devam eden bir üretim işi var. "
                "Silmeden önce işin bitmesini bekleyin."
            ),
        )

    shutil.rmtree(project_dir)

    return {"deleted": slug}


@router.get("/api/builds/{job_id}")
def build_status(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Üretim işi bulunamadı.")
        result = dict(job)

    project_dir = Path(result["project_path"])
    result.update(
        compute_pipeline_progress(project_dir, result.get("status"))
    )
    return result


@router.post("/api/builds/{job_id}/cancel")
def cancel_build(job_id: str) -> dict[str, Any]:
    """Request cancellation of a running/queued build.

    Cooperative: the pipeline only checks between steps, so this stops
    it before the *next* step starts, not instantly -- an in-flight AI
    call or ffmpeg render always finishes first.
    """

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Üretim işi bulunamadı.")

        if job.get("status") not in ("queued", "running"):
            return {"job_id": job_id, "status": job.get("status"), "cancelling": False}

    event = CANCEL_EVENTS.get(job_id)

    if event is None:
        raise HTTPException(
            status_code=409,
            detail="Bu iş için iptal edilebilecek aktif bir işlem bulunamadı.",
        )

    event.set()

    return {"job_id": job_id, "status": "running", "cancelling": True}


@router.get("/api/jobs/active")
def active_jobs() -> dict[str, Any]:
    """List jobs still queued/running, with live progress -- for the dashboard."""

    with JOBS_LOCK:
        snapshot = list(JOBS.values())

    active: list[dict[str, Any]] = []

    for job in snapshot:
        if job.get("status") not in ("queued", "running"):
            continue

        job_copy = dict(job)
        job_copy.pop("request", None)

        project_dir = Path(job_copy["project_path"])
        job_copy.update(
            compute_pipeline_progress(project_dir, job_copy.get("status"))
        )
        active.append(job_copy)

    return {"jobs": active}
