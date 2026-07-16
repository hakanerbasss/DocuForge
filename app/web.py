import html
import json
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.web_new_project import router as new_project_router


app = FastAPI(
    title="DocuForge Web Panel",
    version="0.1.0",
)

app.include_router(new_project_router)

PROJECTS_ROOT = Path("projects").resolve()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def safe_project_dir(slug: str) -> Path:
    project_dir = (PROJECTS_ROOT / slug).resolve()

    if (
        PROJECTS_ROOT not in project_dir.parents
        or not project_dir.is_dir()
    ):
        raise HTTPException(
            status_code=404,
            detail="Proje bulunamadı.",
        )

    return project_dir


def page(title: str, body: str) -> HTMLResponse:
    document = f"""<!doctype html>
<html lang="tr">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>{html.escape(title)} · DocuForge</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: #f4f7fb;
            color: #152033;
            font-family:
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        header {{
            background: linear-gradient(
                135deg,
                #ffffff,
                #eaf2ff
            );
            border-bottom: 1px solid #dfe7f3;
            padding: 22px 18px;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        header .inner,
        main {{
            width: min(1100px, calc(100% - 28px));
            margin: auto;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: #152033;
        }}

        .logo {{
            width: 44px;
            height: 44px;
            border-radius: 14px;
            display: grid;
            place-items: center;
            background: #2166f3;
            color: white;
            font-size: 23px;
            font-weight: 800;
            box-shadow: 0 9px 24px rgba(33, 102, 243, .25);
        }}

        h1, h2, h3, p {{
            margin-top: 0;
        }}

        main {{
            padding: 28px 0 60px;
        }}

        .hero {{
            background: white;
            padding: 25px;
            border-radius: 22px;
            box-shadow: 0 10px 32px rgba(28, 51, 84, .08);
            margin-bottom: 22px;
        }}

        .hero h1 {{
            font-size: clamp(28px, 5vw, 43px);
            margin-bottom: 8px;
        }}

        .muted {{
            color: #64748b;
        }}

        .grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(260px, 1fr));
            gap: 17px;
        }}

        .card {{
            background: white;
            border: 1px solid #e3eaf4;
            border-radius: 19px;
            padding: 19px;
            box-shadow: 0 8px 25px rgba(30, 52, 80, .06);
        }}

        .card h2 {{
            font-size: 20px;
            margin-bottom: 9px;
        }}

        .badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            margin: 13px 0;
        }}

        .badge {{
            padding: 6px 10px;
            border-radius: 999px;
            background: #edf3ff;
            color: #2157b5;
            font-size: 13px;
            font-weight: 700;
        }}

        .badge.success {{
            background: #e7f9ee;
            color: #087a38;
        }}

        .badge.warning {{
            background: #fff3db;
            color: #946000;
        }}

        .button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 42px;
            padding: 0 15px;
            border-radius: 12px;
            background: #2166f3;
            color: white;
            text-decoration: none;
            font-weight: 750;
            border: 0;
        }}

        .button.secondary {{
            background: #eef3fb;
            color: #1e3a62;
        }}

        .buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 9px;
            margin-top: 16px;
        }}

        video {{
            width: 100%;
            max-height: 70vh;
            border-radius: 16px;
            background: black;
        }}

        pre {{
            white-space: pre-wrap;
            word-break: break-word;
            background: #101827;
            color: #e6edf7;
            border-radius: 15px;
            padding: 16px;
            overflow: auto;
        }}

        .status-row {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 12px;
            align-items: center;
            border-bottom: 1px solid #edf1f6;
            padding: 11px 0;
        }}

        .status-row:last-child {{
            border-bottom: 0;
        }}

        .empty {{
            text-align: center;
            padding: 45px 20px;
        }}
    </style>
</head>

<body>
<header>
    <div class="inner">
        <a class="brand" href="/">
            <div class="logo">D</div>
            <div>
                <strong>DocuForge</strong><br>
                <span class="muted">
                    Belgesel üretim paneli
                </span>
            </div>
        </a>
    </div>
</header>

<main>
    {body}
</main>
</body>
</html>
"""

    return HTMLResponse(document)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    PROJECTS_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    cards: list[str] = []

    for project_dir in sorted(
        PROJECTS_ROOT.iterdir(),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        if not project_dir.is_dir():
            continue

        project = load_json(
            project_dir / "project.json"
        )
        pipeline = load_json(
            project_dir / "pipeline_state.json"
        )

        title = str(
            project.get("title", project_dir.name)
        )
        language = str(
            project.get("language", "—")
        )
        template = str(
            project.get("template", "—")
        )
        status = str(
            pipeline.get(
                "status",
                project.get("status", "unknown"),
            )
        )

        final_video = (
            project_dir
            / "render"
            / "final_video.mp4"
        )

        video_badge = (
            '<span class="badge success">🎬 Video hazır</span>'
            if final_video.exists()
            else '<span class="badge warning">⏳ Video yok</span>'
        )

        escaped_slug = quote(project_dir.name)

        cards.append(
            f"""
            <article class="card">
                <h2>{html.escape(title)}</h2>

                <div class="badges">
                    <span class="badge">
                        🌐 {html.escape(language)}
                    </span>
                    <span class="badge">
                        🧩 {html.escape(template)}
                    </span>
                    <span class="badge">
                        Durum: {html.escape(status)}
                    </span>
                    {video_badge}
                </div>

                <div class="buttons">
                    <a
                        class="button"
                        href="/projects/{escaped_slug}"
                    >
                        Projeyi Aç
                    </a>
                </div>
            </article>
            """
        )

    if cards:
        content = '<div class="grid">' + "".join(cards) + "</div>"
    else:
        content = """
        <section class="card empty">
            <h2>Henüz proje bulunamadı</h2>
            <p class="muted">
                projects klasöründeki projeler burada görünecek.
            </p>
        </section>
        """

    body = f"""
    <section class="hero">
        <h1>Projelerin</h1>
        <p class="muted">
            Üretilen videoları izle, proje aşamalarını ve
            dosyaları tek ekrandan kontrol et.
        </p>
        <div class="buttons">
            <a class="button" href="/new">+ Yeni Proje</a>
        </div>
    </section>

    {content}
    """

    return page(
        "Projeler",
        body,
    )


@app.get(
    "/projects/{slug}",
    response_class=HTMLResponse,
)
def project_detail(slug: str) -> HTMLResponse:
    project_dir = safe_project_dir(slug)

    project = load_json(
        project_dir / "project.json"
    )
    pipeline = load_json(
        project_dir / "pipeline_state.json"
    )
    audio_manifest = load_json(
        project_dir / "audio" / "manifest.json"
    )

    title = str(
        project.get("title", project_dir.name)
    )

    final_video = (
        project_dir
        / "render"
        / "final_video.mp4"
    )

    video_section = """
    <section class="card">
        <h2>Final video</h2>
        <p class="muted">
            Bu proje için henüz final_video.mp4 bulunamadı.
        </p>
    </section>
    """

    if final_video.exists():
        video_section = f"""
        <section class="card">
            <h2>Final video</h2>

            <video controls preload="metadata">
                <source
                    src="/files/{quote(project_dir.name)}/render/final_video.mp4"
                    type="video/mp4"
                >
            </video>

            <div class="buttons">
                <a
                    class="button"
                    href="/files/{quote(project_dir.name)}/render/final_video.mp4"
                    download
                >
                    Videoyu İndir
                </a>
            </div>
        </section>
        """

    thumbnail_path = project_dir / "thumbnail.jpg"
    thumbnail_vertical_path = project_dir / "thumbnail_vertical.jpg"

    thumbnail_section = ""

    if thumbnail_path.exists() or thumbnail_vertical_path.exists():
        thumbnail_images = ""

        if thumbnail_path.exists():
            thumbnail_images += f"""
            <a
                href="/files/{quote(project_dir.name)}/thumbnail.jpg"
                download
            >
                <img
                    src="/files/{quote(project_dir.name)}/thumbnail.jpg"
                    alt="Thumbnail"
                    style="max-width:320px;width:100%;border-radius:12px"
                >
            </a>
            """

        if thumbnail_vertical_path.exists():
            thumbnail_images += f"""
            <a
                href="/files/{quote(project_dir.name)}/thumbnail_vertical.jpg"
                download
            >
                <img
                    src="/files/{quote(project_dir.name)}/thumbnail_vertical.jpg"
                    alt="Dikey kapak"
                    style="max-width:180px;width:100%;border-radius:12px"
                >
            </a>
            """

        thumbnail_section = f"""
        <section class="card">
            <h2>Kapak görseli</h2>
            <div style="display:flex;gap:14px;flex-wrap:wrap">
                {thumbnail_images}
            </div>
        </section>
        """

    subtitles_path = project_dir / "render" / "subtitles.srt"
    subtitles_section = ""

    if subtitles_path.exists():
        subtitles_section = f"""
        <section class="card">
            <h2>Altyazı</h2>
            <p class="muted">
                Sahne bazlı zamanlamalı .srt dosyası (henüz videoya gömülmüyor).
            </p>
            <div class="buttons">
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/render/subtitles.srt"
                    download
                >
                    subtitles.srt İndir
                </a>
            </div>
        </section>
        """

    steps = pipeline.get("steps", {})
    step_rows: list[str] = []

    if isinstance(steps, dict):
        for key, value in steps.items():
            if not isinstance(value, dict):
                continue

            status = str(
                value.get("status", "unknown")
            )
            duration = value.get(
                "duration_seconds",
                0,
            )

            icon = (
                "✅"
                if status == "completed"
                else "❌"
                if status == "failed"
                else "⏳"
            )

            step_rows.append(
                f"""
                <div class="status-row">
                    <strong>
                        {icon} {html.escape(str(key))}
                    </strong>
                    <span class="muted">
                        {html.escape(status)}
                        · {html.escape(str(duration))} sn
                    </span>
                </div>
                """
            )

    if not step_rows:
        step_rows.append(
            """
            <p class="muted">
                Pipeline durumu bulunamadı.
            </p>
            """
        )

    voice_provider = str(
        audio_manifest.get(
            "voice_provider",
            "—",
        )
    )
    voice_name = str(
        audio_manifest.get(
            "voice_name",
            "—",
        )
    )

    body = f"""
    <section class="hero">
        <a
            class="button secondary"
            href="/"
        >
            ← Projelere Dön
        </a>

        <h1 style="margin-top:18px">
            {html.escape(title)}
        </h1>

        <div class="badges">
            <span class="badge">
                🌐 {html.escape(str(project.get("language", "—")))}
            </span>
            <span class="badge">
                🧩 {html.escape(str(project.get("template", "—")))}
            </span>
            <span class="badge">
                🎙 {html.escape(voice_provider)}
            </span>
            <span class="badge">
                🗣 {html.escape(voice_name)}
            </span>
        </div>
    </section>

    {video_section}
    {thumbnail_section}
    {subtitles_section}

    <section
        class="grid"
        style="margin-top:17px"
    >
        <article class="card">
            <h2>Üretim aşamaları</h2>
            {''.join(step_rows)}
        </article>

        <article class="card">
            <h2>Proje ayarları</h2>
            <pre>{html.escape(json.dumps(
                project,
                ensure_ascii=False,
                indent=2,
            ))}</pre>
        </article>
    </section>
    """

    return page(
        title,
        body,
    )


@app.get("/files/{slug}/{file_path:path}")
def project_file(
    slug: str,
    file_path: str,
) -> FileResponse:
    project_dir = safe_project_dir(slug)
    requested = (project_dir / file_path).resolve()

    if (
        project_dir not in requested.parents
        or not requested.is_file()
    ):
        raise HTTPException(
            status_code=404,
            detail="Dosya bulunamadı.",
        )

    return FileResponse(requested)
