import json
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.pipeline.build_pipeline import STEP_ALLOWED_OVERRIDES, BuildPipeline
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


class BuildRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    language: str = Field(default="tr")
    content_type: str = Field(default="documentary")
    target_duration_seconds: int = Field(default=600, ge=10, le=7200)
    media_mode: str = Field(default="mixed")
    image_provider: str = Field(default="pexels")
    video_provider: str = Field(default="pexels")
    voice_provider: str = Field(default="supertonic")
    voice_name: str = Field(default="M1")
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    resolution: str = Field(default="720p")
    fps: int = Field(default=30)
    background_music_enabled: bool = Field(default=False)
    music_provider: str = Field(default="local")
    subtitles_enabled: bool = Field(default=False)
    subtitles_burn_in: bool = Field(default=False)
    thumbnail_enabled: bool = Field(default=False)


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
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        _persist_job(job_id)
    try:
        if (project_dir / "project.json").exists():
            # Project already created by a previous (possibly crashed) run.
            result_dir = BuildPipeline().resume(str(project_dir))
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
                background_music_enabled=req["background_music_enabled"],
                music_provider=req.get("music_provider", "local"),
                subtitles_enabled=req["subtitles_enabled"],
                subtitles_burn_in=req.get("subtitles_burn_in", False),
                thumbnail_enabled=req["thumbnail_enabled"],
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yeni Proje · DocuForge</title>
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
<header><div style="display:flex;align-items:center;justify-content:space-between;gap:16px"><a class="back" href="/">\u2190 Projelere d\u00f6n</a><a class="back" href="/settings">\u2699 Ayarlar</a></div></header>
<main>
<div id="activeJobBanner"></div>
<section class="card">
<h1>Yeni Proje</h1>
<p class="muted">Konuyu ve ayarlar\u0131 se\u00e7. DocuForge ara\u015ft\u0131rma, senaryo, medya, seslendirme ve videoyu otomatik haz\u0131rlas\u0131n.</p>

<h3>📝 \u0130\u00e7erik</h3>
<label for="topic">Konu</label>
<input id="topic" placeholder="\u00d6rnek: Kara Deliklerin S\u0131rr\u0131" required minlength="2" maxlength="200">

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
<input id="duration" type="number" value="600" min="10" max="7200">
<div class="hint" id="durationHint">~10 dakika</div>

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
<select id="music_provider">
<option value="local" selected>Yerel (music/ klas\u00f6r\u00fc)</option>
<option value="jamendo">Jamendo (telifsiz)</option>
<option value="mubert">Mubert (yapay zeka m\u00fczi\u011fi)</option>
</select>
<div class="hint">Jamendo/Mubert i\u00e7in <a href="/settings">Ayarlar</a> sayfas\u0131ndan API key girmen gerekir.</div>
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
<input type="checkbox" id="thumbnail_enabled" style="width:auto;min-height:auto">
Kapak g\u00f6rseli (thumbnail) olu\u015ftur
</label>
<div class="hint">1280x720 YouTube kapak g\u00f6rseli \u00fcretilir; dikey projelerde ayr\u0131ca 1080x1920 kapak da eklenir.</div>

<button id="startButton" onclick="startBuild()">\u00dcretimi Ba\u015flat</button>

<div id="statusBox" class="status">
<strong id="statusTitle">Proje haz\u0131rlan\u0131yor\u2026</strong>
<div class="progress"><div id="progressBar"></div></div>
<div id="statusText" class="muted">\u0130\u015f ba\u015flat\u0131l\u0131yor.</div>
<a id="openProject" class="open-project" href="#">Projeyi A\u00e7 \u2192</a>
</div>
</section></main>

<script>
let pollTimer=null;

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
          <strong>${job.topic||job.project_slug||"Proje"}</strong>${link}
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
  else{d.value=600;r.value="720p";h.textContent="~10 dakika";}
  updateHint();
}

function updateHint(){
  const s=parseInt(document.getElementById("duration").value)||0;
  const m=Math.floor(s/60),sec=s%60;
  document.getElementById("durationHint").textContent=
    m>0?(sec>0?`~${m} dk ${sec} sn`:`~${m} dakika`):`${s} saniye`;
}

function onMusicToggle(){
  const on=document.getElementById("background_music_enabled").checked;
  document.getElementById("musicProviderRow").style.display=on?"block":"none";
}

function onSubtitlesToggle(){
  const on=document.getElementById("subtitles_enabled").checked;
  const label=document.getElementById("burnInLabel");
  const hint=document.getElementById("burnInHint");
  label.style.display=on?"flex":"none";
  hint.style.display=on?"block":"none";
  if(!on)document.getElementById("subtitles_burn_in").checked=false;
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
    background_music_enabled:document.getElementById("background_music_enabled").checked,
    music_provider:document.getElementById("music_provider").value,
    subtitles_enabled:document.getElementById("subtitles_enabled").checked,
    subtitles_burn_in:document.getElementById("subtitles_burn_in").checked,
    thumbnail_enabled:document.getElementById("thumbnail_enabled").checked,
  };

  try{
    const r=await fetch("/api/builds",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const res=await r.json();
    if(!r.ok)throw new Error(res.detail||"\u00dcretim ba\u015flat\u0131lamad\u0131.");
    document.getElementById("statusTitle").textContent="\u00dcretim devam ediyor";
    document.getElementById("statusText").textContent="Ara\u015ft\u0131rma, senaryo, medya, ses ve video haz\u0131rlan\u0131yor.";
    pollJob(res.job_id);
  }catch(e){showError(e.message);}
}

async function pollJob(jobId){
  clearTimeout(pollTimer);
  try{
    const r=await fetch(`/api/builds/${jobId}`);
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
</body></html>""")


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

    if isinstance(steps, dict):
        for key, _label in active_steps:
            step_info = steps.get(key)
            if isinstance(step_info, dict) and step_info.get("status") == "completed":
                completed_steps += 1
            else:
                break

        failed_step = pipeline_state.get("failed_step")

        if failed_step:
            failed_label = dict(active_steps).get(failed_step, failed_step)
            current_step = f"Hata: {failed_label}"
        elif completed_steps < total_steps:
            current_step = f"{active_steps[completed_steps][1]} çalışıyor"
        else:
            current_step = "Tamamlandı"

    if job_status == "completed":
        completed_steps = total_steps
        current_step = "Tamamlandı"

    return {
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "current_step": current_step,
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

    return {
        "step_key": step_key,
        "allowed_fields": sorted(allowed),
        "current": current,
        "choices": choices,
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
