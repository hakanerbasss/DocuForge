import json
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.pipeline.build_pipeline import BuildPipeline


router = APIRouter()

PROJECTS_ROOT = Path("projects")
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


class BuildRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    language: str = Field(default="tr", min_length=2, max_length=10)
    template: str = Field(default="documentary", min_length=2, max_length=30)


def slugify(title: str) -> str:
    replacements = str.maketrans(
        {
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
            "İ": "i",
            "Ğ": "g",
            "Ü": "u",
            "Ş": "s",
            "Ö": "o",
            "Ç": "c",
        }
    )

    slug = title.translate(replacements).lower()
    slug = "_".join(slug.split())

    if not slug:
        raise ValueError("Geçerli bir proje konusu girilmelidir.")

    return slug


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def run_build_job(
    job_id: str,
    topic: str,
    language: str,
    template: str,
    project_dir: Path,
) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"

    try:
        result_dir = BuildPipeline().run(
            topic=topic,
            language=language,
            template=template,
        )

        with JOBS_LOCK:
            JOBS[job_id].update(
                {
                    "status": "completed",
                    "project_path": str(result_dir),
                    "error": None,
                }
            )

    except Exception as error:
        with JOBS_LOCK:
            JOBS[job_id].update(
                {
                    "status": "failed",
                    "error": str(error),
                }
            )


@router.get("/new", response_class=HTMLResponse)
def new_project_page() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html>
<html lang="tr">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Yeni Proje · DocuForge</title>

    <style>
        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            background: #f3f6fb;
            color: #172033;
            font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        }

        header {
            padding: 18px;
            background: white;
            border-bottom: 1px solid #e1e8f2;
        }

        header div,
        main {
            width: min(760px, calc(100% - 28px));
            margin: auto;
        }

        main {
            padding: 28px 0 70px;
        }

        .back {
            color: #245ec7;
            text-decoration: none;
            font-weight: 700;
        }

        .card {
            margin-top: 18px;
            padding: 24px;
            background: white;
            border: 1px solid #e0e7f1;
            border-radius: 22px;
            box-shadow: 0 12px 35px rgba(34, 54, 80, .08);
        }

        h1 {
            margin: 0 0 8px;
            font-size: clamp(29px, 6vw, 42px);
        }

        .muted {
            color: #66758c;
        }

        label {
            display: block;
            margin-top: 18px;
            margin-bottom: 7px;
            font-weight: 750;
        }

        input,
        select {
            width: 100%;
            min-height: 48px;
            padding: 0 13px;
            border: 1px solid #cbd6e5;
            border-radius: 12px;
            background: white;
            color: #172033;
            font: inherit;
        }

        button {
            width: 100%;
            min-height: 50px;
            margin-top: 23px;
            border: 0;
            border-radius: 13px;
            background: #2166f3;
            color: white;
            font-size: 16px;
            font-weight: 800;
            cursor: pointer;
        }

        button:disabled {
            opacity: .6;
            cursor: wait;
        }

        .status {
            display: none;
            margin-top: 20px;
            padding: 17px;
            border-radius: 14px;
            background: #edf4ff;
        }

        .progress {
            height: 11px;
            margin: 12px 0;
            overflow: hidden;
            border-radius: 999px;
            background: #dbe5f4;
        }

        .progress > div {
            width: 4%;
            height: 100%;
            background: #2166f3;
            transition: width .4s ease;
        }

        .error {
            background: #ffe9e9;
            color: #9f2020;
        }

        .success {
            background: #e8f8ee;
            color: #08763a;
        }

        .open-project {
            display: none;
            margin-top: 14px;
            color: #2166f3;
            font-weight: 800;
            text-decoration: none;
        }
    </style>
</head>

<body>
<header>
    <div>
        <a class="back" href="/">← Projelere dön</a>
    </div>
</header>

<main>
    <section class="card">
        <h1>Yeni Proje</h1>
        <p class="muted">
            Konuyu ve üretim dilini seç. DocuForge araştırma,
            senaryo, medya, seslendirme ve videoyu otomatik hazırlasın.
        </p>

        <form id="buildForm">
            <label for="topic">Belgesel konusu</label>
            <input
                id="topic"
                name="topic"
                placeholder="Örnek: Amazon Ormanlarının Gizli Dünyası"
                required
                minlength="2"
                maxlength="200"
            >

            <label for="language">İçerik dili</label>
            <select id="language" name="language">
                <option value="tr" selected>Türkçe</option>
                <option value="en">İngilizce</option>
                <option value="de">Almanca</option>
                <option value="fr">Fransızca</option>
                <option value="es">İspanyolca</option>
            </select>

            <label for="template">Şablon</label>
            <select id="template" name="template">
                <option value="documentary" selected>
                    Belgesel
                </option>
            </select>

            <button id="startButton" type="submit">
                Üretimi Başlat
            </button>
        </form>

        <div id="statusBox" class="status">
            <strong id="statusTitle">Proje hazırlanıyor…</strong>

            <div class="progress">
                <div id="progressBar"></div>
            </div>

            <div id="statusText" class="muted">
                İş başlatılıyor.
            </div>

            <a id="openProject" class="open-project" href="#">
                Projeyi Aç →
            </a>
        </div>
    </section>
</main>

<script>
const form = document.getElementById("buildForm");
const button = document.getElementById("startButton");
const statusBox = document.getElementById("statusBox");
const statusTitle = document.getElementById("statusTitle");
const statusText = document.getElementById("statusText");
const progressBar = document.getElementById("progressBar");
const openProject = document.getElementById("openProject");

let pollTimer = null;

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    button.disabled = true;
    statusBox.style.display = "block";
    statusBox.className = "status";
    statusTitle.textContent = "Proje oluşturuluyor…";
    statusText.textContent = "Üretim işi sunucuya gönderiliyor.";
    progressBar.style.width = "4%";
    openProject.style.display = "none";

    const payload = {
        topic: document.getElementById("topic").value.trim(),
        language: document.getElementById("language").value,
        template: document.getElementById("template").value,
    };

    try {
        const response = await fetch("/api/builds", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Üretim başlatılamadı.");
        }

        statusTitle.textContent = "Üretim devam ediyor";
        statusText.textContent =
            "Araştırma, senaryo, medya, ses ve video hazırlanıyor.";

        pollJob(result.job_id);

    } catch (error) {
        showError(error.message);
    }
});

async function pollJob(jobId) {
    clearTimeout(pollTimer);

    try {
        const response = await fetch(`/api/builds/${jobId}`);
        const job = await response.json();

        if (!response.ok) {
            throw new Error(job.detail || "İş durumu alınamadı.");
        }

        const progress = Math.max(
            4,
            Math.min(100, Number(job.progress_percent || 4))
        );

        progressBar.style.width = `${progress}%`;

        if (job.current_step) {
            statusText.textContent =
                `${job.completed_steps}/10 · ${job.current_step}`;
        }

        if (job.status === "completed") {
            statusBox.className = "status success";
            statusTitle.textContent = "Video hazır";
            statusText.textContent = "Tüm üretim aşamaları tamamlandı.";
            progressBar.style.width = "100%";
            openProject.href = `/projects/${job.project_slug}`;
            openProject.style.display = "inline-block";
            button.disabled = false;
            return;
        }

        if (job.status === "failed") {
            showError(job.error || "Üretim sırasında hata oluştu.");
            return;
        }

        pollTimer = setTimeout(() => pollJob(jobId), 2500);

    } catch (error) {
        showError(error.message);
    }
}

function showError(message) {
    clearTimeout(pollTimer);
    statusBox.style.display = "block";
    statusBox.className = "status error";
    statusTitle.textContent = "Üretim başarısız";
    statusText.textContent = message;
    progressBar.style.width = "100%";
    button.disabled = false;
}
</script>
</body>
</html>"""
    )


@router.post("/api/builds")
def create_build(request: BuildRequest) -> dict[str, Any]:
    topic = request.topic.strip()
    language = request.language.strip().lower()
    template = request.template.strip().lower()

    if not topic:
        raise HTTPException(
            status_code=400,
            detail="Proje konusu boş olamaz.",
        )

    project_slug = slugify(topic)
    project_dir = PROJECTS_ROOT / project_slug
    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "topic": topic,
            "language": language,
            "template": template,
            "project_slug": project_slug,
            "project_path": str(project_dir),
            "error": None,
        }

    thread = threading.Thread(
        target=run_build_job,
        args=(
            job_id,
            topic,
            language,
            template,
            project_dir,
        ),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "project_slug": project_slug,
    }


@router.get("/api/builds/{job_id}")
def build_status(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Üretim işi bulunamadı.",
            )

        result = dict(job)

    project_dir = Path(result["project_path"])
    pipeline_state = load_json(
        project_dir / "pipeline_state.json"
    )

    steps = pipeline_state.get("steps", {})
    completed_steps = 0
    current_step = "İş sırası bekleniyor"

    if isinstance(steps, dict):
        completed_steps = sum(
            isinstance(value, dict)
            and value.get("status") == "completed"
            for value in steps.values()
        )

        failed_step = pipeline_state.get("failed_step")

        if failed_step:
            current_step = f"Hata: {failed_step}"
        elif completed_steps:
            current_step = f"{completed_steps + 1}. aşama hazırlanıyor"

    if result["status"] == "completed":
        completed_steps = 10
        current_step = "Tamamlandı"

    result["completed_steps"] = completed_steps
    result["current_step"] = current_step
    result["progress_percent"] = round(
        min(completed_steps, 10) / 10 * 100
    )

    return result
