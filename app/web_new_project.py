import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agents.topic import TopicSuggestionAgent
from app.pipeline.build_pipeline import (
    STEP_ALLOWED_OVERRIDES,
    BuildPipeline,
    PipelineCancelled,
)
from app.services.project_service import ProjectService


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
    thumbnail_enabled: bool = Field(default=False)
    thumbnail_source: str = Field(default="auto")


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
                thumbnail_enabled=req["thumbnail_enabled"],
                thumbnail_source=req.get("thumbnail_source", "auto"),
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
</style>
</head>
<body>
<header><div style="display:flex;align-items:center;justify-content:space-between;gap:16px"><a class="back" href="/">\u2190 Projelere d\u00f6n</a><a class="back" href="/storage">\U0001F4E6 Depolama</a><a class="back" href="/settings">\u2699 Ayarlar</a></div></header>
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
</select>
<div class="hint">Jamendo/Mubert i\u00e7in <a href="/settings">Ayarlar</a> sayfas\u0131ndan API key girmen gerekir.</div>

<label for="music_volume" style="margin-top:12px">M\u00fczik Sesi Seviyesi: <span id="musicVolumeLabel">%18</span></label>
<input id="music_volume" type="range" min="0" max="50" step="5" value="18" oninput="document.getElementById('musicVolumeLabel').textContent='%'+this.value">
<div class="hint">Arka plan m\u00fczi\u011finin seslendirmeye g\u00f6re ses oran\u0131. D\u00fc\u015f\u00fck tut ki konu\u015fmay\u0131 bast\u0131rmas\u0131n (varsay\u0131lan %18 \u00f6nerilir).</div>

<div id="musicBrowseRow" style="display:none;margin-top:12px;padding:12px;border:1px solid #dbe5f4;border-radius:12px;background:#f8fbff">
<div class="hint" style="margin-bottom:8px">Ticari kullan\u0131ma kapal\u0131 (NC lisansl\u0131) par\u00e7alar listelenmiyor -- ama lisans\u0131 belirlenemeyenler ⚠️ ile i\u015faretli, y\u00fcklemeden \u00f6nce kontrol et.</div>
<div style="display:flex;gap:8px">
<input id="musicSearchQuery" placeholder="\u00d6rnek: cinematic ambient (bo\u015f b\u0131rak\u0131rsan i\u00e7erik t\u00fcr\u00fcne g\u00f6re aran\u0131r)" style="flex:1">
<button type="button" id="musicSearchBtn" onclick="searchMusic()" style="width:auto;min-height:44px;margin-top:0;padding:0 16px;font-size:14px">🎧 Ara</button>
<button type="button" onclick="clearMusicSearch()" style="width:auto;min-height:44px;margin-top:0;padding:0 16px;font-size:14px">🗑 Temizle</button>
</div>
<div id="musicMoodTags" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"></div>
<div id="musicResults" style="margin-top:10px"></div>
<div id="musicSelectedInfo" class="hint" style="display:none;margin-top:10px;font-weight:700;color:#08763a"></div>
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
    return `<div class="topic-suggestion" data-title="${escapeHtml(s.title)}" onclick="pickTopicSuggestion(this)"
      style="padding:12px 14px;cursor:pointer;${i>0?"border-top:1px solid #eef1f6":""}"
      onmouseover="this.style.background='#f5f8fd'" onmouseout="this.style.background=''"
    >
      <div style="font-weight:700">${medal}${escapeHtml(s.title)}</div>
      ${hook}
      ${visual}
    </div>`;
  }).join("");
  box.innerHTML=`
    <div class="hint" style="margin-bottom:8px;font-weight:700">🏆 En yüksek tıklama potansiyeline sahip 3 konu</div>
    <div style="border:1px solid #dbe5f4;border-radius:12px;padding:10px 14px;margin-bottom:12px;background:#f8fbff">${top3}</div>
    <div style="border:1px solid #dbe5f4;border-radius:12px;overflow:hidden">${rows}</div>
  `;
}

function pickTopicSuggestion(el){
  document.getElementById("topic").value=el.getAttribute("data-title");
  document.getElementById("topicSuggestions").style.display="none";
  updateMusicMoodSuggestion();
}

function onMusicToggle(){
  const on=document.getElementById("background_music_enabled").checked;
  document.getElementById("musicProviderRow").style.display=on?"block":"none";
  if(!on)onMusicProviderChange();
}

function onMusicProviderChange(){
  const p=document.getElementById("music_provider").value;
  const isJamendo=p==="jamendo"&&document.getElementById("background_music_enabled").checked;
  document.getElementById("musicBrowseRow").style.display=isJamendo?"block":"none";
  if(!isJamendo){
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
  btn.disabled=true;
  btn.textContent="⏳ Aranıyor…";
  box.innerHTML='<div class="hint">Jamendo’da telifsiz parçalar aranıyor…</div>';
  try{
    const params=new URLSearchParams({query, content_type: contentType});
    const res=await fetch(`/api/music-search?${params.toString()}`);
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||"Arama başarısız.");
    renderMusicResults(data.tracks||[]);
  }catch(err){
    box.innerHTML=`<div class="hint" style="color:#9f2020">${escapeHtml(err.message)}</div>`;
  }finally{
    btn.disabled=false;
    btn.textContent="🎧 Ara";
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

function renderMusicResults(tracks){
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
        <button type="button" class="music-pick-btn" data-url="${escapeHtml(t.download_url||"")}" data-label="${escapeHtml(label)}" onclick="selectMusicTrack(this)" style="width:auto;min-height:36px;margin-top:0;padding:0 14px;font-size:13px;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5">Bu parçayı seç</button>
      </div>
      <audio controls preload="none" src="${escapeHtml(t.preview_url||"")}" style="width:100%;margin-top:6px;height:34px"></audio>
    </div>`;
  }).join("");
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

async function startBuild(){
  const btn=document.getElementById("startButton");
  const topic=document.getElementById("topic").value.trim();
  if(!topic){alert("Konu giriniz.");return;}
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
    thumbnail_enabled:document.getElementById("thumbnail_enabled").checked,
    thumbnail_source:document.getElementById("thumbnail_source").value,
  };

  try{
    const r=await fetch("/api/builds",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const res=await r.json();
    if(!r.ok)throw new Error(res.detail||"\u00dcretim ba\u015flat\u0131lamad\u0131.");
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

function showError(msg){
  clearTimeout(pollTimer);
  const sb=document.getElementById("statusBox");
  sb.style.display="block";sb.className="status error";
  document.getElementById("statusTitle").textContent="\u00dcretim ba\u015far\u0131s\u0131z";
  document.getElementById("statusText").textContent=msg;
  document.getElementById("progressBar").style.width="100%";
  document.getElementById("startButton").disabled=false;
}
</script>
<script>
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}
</script>
</body></html>""")


class TopicSuggestionsRequest(BaseModel):
    content_type: str = Field(default="documentary")
    language: str = Field(default="tr")


@router.post("/api/topic-suggestions")
def topic_suggestions(request: TopicSuggestionsRequest) -> dict[str, Any]:
    try:
        raw = TopicSuggestionAgent().run(
            language=request.language,
            content_type=request.content_type,
        )
        return json.loads(raw)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Konu önerileri alınamadı: {error}",
        ) from error


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
def music_search(query: str = "", content_type: str = "documentary") -> dict[str, Any]:
    from app.providers.music.jamendo import JamendoMusicProvider
    from app.services.render_service import RenderService

    search_query = query.strip() or RenderService()._build_music_query(
        {"content_type": content_type}
    )

    try:
        provider = JamendoMusicProvider()
        tracks = provider.search(search_query, limit=12)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Müzik araması başarısız: {error}",
        ) from error

    return {"query": search_query, "tracks": tracks}


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


THUMBNAIL_VARIANTS = {"thumbnail_1.png", "thumbnail_2.png", "thumbnail_3.png", "thumbnail_4.png"}


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
