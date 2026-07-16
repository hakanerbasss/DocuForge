import html
import json
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.services.thumbnail_service import ThumbnailService
from app.web_new_project import PIPELINE_STEP_ORDER
from app.web_new_project import router as new_project_router
from app.web_settings import router as settings_router


app = FastAPI(
    title="DocuForge Web Panel",
    version="0.1.0",
)

app.include_router(new_project_router)
app.include_router(settings_router)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

PROJECTS_ROOT = Path("projects").resolve()

# Turkish display names for the 4 rotating thumbnail templates -- keyed
# off ThumbnailService.TEMPLATE_ORDER so thumbnail_1.png..thumbnail_4.png
# always map to the right label even if that order ever changes.
THUMBNAIL_TEMPLATE_LABELS: dict[str, str] = {
    "split_contrast": "Split Contrast",
    "mystery_focus": "Mystery Focus",
    "documentary_cinematic": "Documentary Cinematic",
    "breaking_discovery": "Breaking Discovery",
}


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
        content="width=device-width, initial-scale=1, viewport-fit=cover"
    >
    <title>{html.escape(title)} · DocuForge</title>

    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#2166f3">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="DocuForge">
    <link rel="apple-touch-icon" href="/static/icons/icon-192.png">

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
    <div class="inner" style="display:flex;align-items:center;justify-content:space-between;gap:16px">
        <a class="brand" href="/">
            <div class="logo">D</div>
            <div>
                <strong>DocuForge</strong><br>
                <span class="muted">
                    Belgesel üretim paneli
                </span>
            </div>
        </a>
        <a class="button secondary" href="/settings">⚙ Ayarlar</a>
    </div>
</header>

<main>
    {body}
</main>

<script>
if ("serviceWorker" in navigator) {{
    navigator.serviceWorker.register("/static/sw.js").catch(() => {{}});
}}
</script>
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
                    <button
                        class="button secondary"
                        style="color:#b91c1c"
                        onclick="deleteProjectCard('{escaped_slug}',this)"
                    >
                        🗑 Sil
                    </button>
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

    <div id="activeJobs"></div>

    {content}

    <script>
    async function deleteProjectCard(slug, btn) {{
        if (!confirm(
            "Bu projeyi ve tüm dosyalarını (video, ses, görseller, " +
            "kapaklar) kalıcı olarak silmek istediğine emin misin? " +
            "Bu işlem geri alınamaz."
        )) return;

        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = "⏳ Siliniyor...";

        try {{
            const r = await fetch(`/api/projects/${{slug}}`, {{method: "DELETE"}});
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "Silinemedi.");
            location.reload();
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = original;
        }}
    }}

    async function refreshActiveJobs() {{
        try {{
            const r = await fetch("/api/jobs/active");
            const data = await r.json();
            const container = document.getElementById("activeJobs");

            if (!data.jobs || data.jobs.length === 0) {{
                container.innerHTML = "";
                return;
            }}

            const rows = data.jobs.map(job => {{
                const pct = Math.max(4, Math.min(100, Number(job.progress_percent || 4)));
                const label = job.current_step || "Başlatılıyor...";
                const slugLink = job.project_slug
                    ? `<a class="button secondary" style="min-height:34px;padding:0 12px;font-size:13px" href="/projects/${{job.project_slug}}">Projeyi Aç</a>`
                    : "";
                return `
                <div style="padding:12px 0;border-bottom:1px solid #edf1f6">
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px">
                        <strong>${{job.topic || job.project_slug || "Proje"}}</strong>
                        ${{slugLink}}
                    </div>
                    <div class="progress"><div style="width:${{pct}}%"></div></div>
                    <div class="muted" style="font-size:13px;margin-top:4px">${{job.completed_steps}}/${{job.total_steps}} · ${{label}}</div>
                </div>`;
            }}).join("");

            container.innerHTML = `
            <section class="card" style="margin-bottom:17px">
                <h2>⏳ Devam eden üretimler</h2>
                ${{rows}}
            </section>`;
        }} catch (e) {{
            // sessizce yut -- dashboard'un geri kalanı çalışmaya devam etsin
        }}
    }}

    refreshActiveJobs();
    setInterval(refreshActiveJobs, 4000);
    </script>
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
    selected_variant = str(project.get("thumbnail_selected", ""))

    thumbnail_section = ""

    variant_cards = ""
    for index, template_key in enumerate(ThumbnailService.TEMPLATE_ORDER, start=1):
        variant_name = f"thumbnail_{index}.png"
        variant_path = project_dir / variant_name

        if not variant_path.exists():
            continue

        label = THUMBNAIL_TEMPLATE_LABELS.get(template_key, template_key)
        is_selected = variant_name == selected_variant
        border = (
            "3px solid #2563eb" if is_selected else "3px solid transparent"
        )
        badge = (
            '<span style="background:#2563eb;color:#fff;font-size:12px;'
            'padding:2px 8px;border-radius:999px">Seçili</span>'
            if is_selected
            else ""
        )

        variant_cards += f"""
        <div style="width:280px">
            <img
                src="/files/{quote(project_dir.name)}/{variant_name}"
                alt="{html.escape(label, quote=True)}"
                style="width:100%;border-radius:12px;display:block;
                border:{border}"
            >
            <div style="display:flex;align-items:center;justify-content:
                space-between;margin-top:6px">
                <strong style="font-size:14px">{html.escape(label)}</strong>
                {badge}
            </div>
            <div class="buttons" style="margin-top:6px;gap:6px">
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/{variant_name}"
                    download
                    style="font-size:13px;padding:0 10px;min-height:32px"
                >
                    ⬇ İndir
                </a>
                <button
                    class="button secondary"
                    style="font-size:13px;padding:0 10px;min-height:32px"
                    onclick="selectThumbnail('{quote(project_dir.name)}','{variant_name}',this)"
                    {"disabled" if is_selected else ""}
                >
                    {"✓ Kapak Bu" if is_selected else "Bunu Seç"}
                </button>
            </div>
        </div>
        """

    legacy_card = ""
    if not variant_cards and thumbnail_path.exists():
        # Older projects made before the multi-template rewrite only have
        # a single thumbnail.jpg -- still show it, just without the
        # variant-picker UI since there's nothing to pick between.
        legacy_card = f"""
        <div style="width:280px">
            <img
                src="/files/{quote(project_dir.name)}/thumbnail.jpg"
                alt="Kapak görseli"
                style="width:100%;border-radius:12px;display:block"
            >
            <a
                class="button secondary"
                href="/files/{quote(project_dir.name)}/thumbnail.jpg"
                download
                style="margin-top:6px;font-size:13px;padding:0 10px;
                min-height:32px;display:inline-flex"
            >
                ⬇ İndir (16:9)
            </a>
        </div>
        """

    if variant_cards or legacy_card or thumbnail_vertical_path.exists():
        vertical_card = ""

        if thumbnail_vertical_path.exists():
            vertical_card = f"""
            <div style="width:160px">
                <img
                    src="/files/{quote(project_dir.name)}/thumbnail_vertical.jpg"
                    alt="Dikey kapak"
                    style="width:100%;border-radius:12px;display:block"
                >
                <div style="margin-top:6px">
                    <strong style="font-size:14px">Dikey (9:16)</strong>
                </div>
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/thumbnail_vertical.jpg"
                    download
                    style="margin-top:6px;font-size:13px;padding:0 10px;
                    min-height:32px;display:inline-flex"
                >
                    ⬇ İndir (9:16)
                </a>
            </div>
            """

        gallery_hint = (
            """<p class="muted">
                4 farklı tasarım otomatik üretildi -- birini seçip
                kapak olarak kullan.
            </p>"""
            if variant_cards
            else ""
        )

        thumbnail_section = f"""
        <section class="card">
            <h2>Kapak görselleri</h2>
            {gallery_hint}
            <div style="display:flex;gap:16px;flex-wrap:wrap">
                {variant_cards}
                {legacy_card}
                {vertical_card}
            </div>
        </section>
        """

    subtitles_path = project_dir / "render" / "subtitles.srt"
    subtitles_section = ""

    if subtitles_path.exists():
        burned_in = bool(project.get("subtitles_burn_in"))
        burn_in_note = (
            "Altyazı videoya gömüldü (final videoyu izlediğinde görünür)."
            if burned_in
            else "Sahne bazlı zamanlamalı .srt dosyası (videoya gömülü değil, ayrı dosya)."
        )

        subtitles_section = f"""
        <section class="card">
            <h2>Altyazı</h2>
            <p class="muted">
                {burn_in_note}
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

    seo_path = project_dir / "seo.json"
    seo_section = ""

    if seo_path.exists():
        seo_data = load_json(seo_path)
        titles = seo_data.get("titles")
        description = str(seo_data.get("description", ""))
        tags = seo_data.get("tags")

        def copy_button(text: str) -> str:
            return (
                '<button type="button" class="button secondary" '
                'style="min-height:34px;padding:0 12px;font-size:13px;'
                'white-space:nowrap" '
                f'data-copy="{html.escape(text, quote=True)}" '
                'onclick="copyToClipboard(this)">📋 Kopyala</button>'
            )

        title_rows = "".join(
            f"""
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid #edf1f6">
                <span>{html.escape(str(title))}</span>
                {copy_button(str(title))}
            </div>
            """
            for title in titles
        ) if isinstance(titles, list) else ""

        tag_badges = "".join(
            f'<span class="badge">{html.escape(str(tag))}</span>'
            for tag in tags
        ) if isinstance(tags, list) else ""

        tags_csv = ", ".join(str(tag) for tag in tags) if isinstance(tags, list) else ""

        seo_section = f"""
        <section class="card">
            <h2>SEO Metadata</h2>

            <h3 style="font-size:15px;margin-bottom:6px">Başlık önerileri</h3>
            <div style="margin-bottom:14px">{title_rows}</div>

            <h3 style="font-size:15px;margin-bottom:6px">Açıklama</h3>
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:14px">
                <p style="margin:0;flex:1">{html.escape(description)}</p>
                {copy_button(description)}
            </div>

            <h3 style="font-size:15px;margin-bottom:6px">Etiketler</h3>
            <div class="badges" style="margin-bottom:10px">{tag_badges}</div>
            <div class="buttons" style="margin-bottom:0">
                {copy_button(tags_csv)}
            </div>

            <div class="buttons">
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/seo.json"
                    download
                >
                    seo.json İndir
                </a>
            </div>
        </section>
        """

    steps = pipeline.get("steps", {})
    thumbnail_enabled = bool(project.get("thumbnail_enabled"))

    active_step_defs = [
        (key, label)
        for key, label in PIPELINE_STEP_ORDER
        if key != "thumbnail" or thumbnail_enabled
    ]

    step_rows: list[str] = []
    escaped_slug_js = quote(project_dir.name)

    for index, (key, label) in enumerate(active_step_defs):
        info = steps.get(key) if isinstance(steps, dict) else None
        status = (
            str(info.get("status", "pending"))
            if isinstance(info, dict)
            else "pending"
        )
        duration = (
            info.get("duration_seconds", 0)
            if isinstance(info, dict)
            else 0
        )

        icon = (
            "✅"
            if status == "completed"
            else "❌"
            if status == "failed"
            else "⏳"
        )
        escaped_label = html.escape(label, quote=True)

        step_rows.append(
            f"""
            <div class="status-row" data-step-index="{index}" data-step-key="{key}">
                <strong class="step-icon-label" data-base-label="{escaped_label}">
                    {icon} {html.escape(label)}
                </strong>
                <span style="display:flex;align-items:center;gap:10px">
                    <span class="muted step-status-text">
                        {html.escape(status)}
                        · {html.escape(str(duration))} sn
                    </span>
                    <button
                        class="button secondary"
                        style="min-height:34px;padding:0 12px;font-size:13px"
                        onclick="regenerateStep('{escaped_slug_js}','{key}',this)"
                    >
                        🔄 Yeniden Üret
                    </button>
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

        <div class="buttons">
            <button
                id="resumeButton"
                class="button"
                onclick="resumeProject('{escaped_slug_js}',this)"
            >
                ▶ Devam Et
            </button>
            <button
                class="button secondary"
                style="color:#b91c1c"
                onclick="deleteProject('{escaped_slug_js}',this)"
            >
                🗑 Projeyi Sil
            </button>
        </div>

        <div id="actionStatus" class="muted" style="margin-top:10px"></div>
    </section>

    {video_section}
    {thumbnail_section}
    {subtitles_section}
    {seo_section}

    <section
        class="grid"
        style="margin-top:17px"
    >
        <article class="card">
            <h2>Üretim aşamaları</h2>
            <p class="muted" style="margin-bottom:14px">
                Bir aşamayı beğenmediysen "Yeniden Üret" ile sadece onu ve
                sonrasındaki aşamaları sıfırlayıp yeniden çalıştırabilirsin.
                Ardından "▶ Devam Et" ile pipeline'ın geri kalanını
                tamamlayabilirsin.
            </p>
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

    <script>
    const FIELD_LABELS_TR = {{
        voice_provider: "Ses Sağlayıcı",
        voice_name: "Ses",
        voice_speed: "Konuşma Hızı",
        image_provider: "Görsel Sağlayıcı",
        video_provider: "Video Sağlayıcı",
        media_mode: "Medya Modu",
        language: "Dil",
        content_type: "İçerik Türü",
        target_duration_seconds: "Hedef Süre (saniye)",
        resolution: "Çözünürlük",
        fps: "FPS",
        background_music_enabled: "Arka Plan Müziği",
        music_provider: "Müzik Sağlayıcı",
        subtitles_enabled: "Altyazı (.srt) Üret",
        subtitles_burn_in: "Altyazıyı Videoya Göm",
        thumbnail_source: "Kapak Görseli Kaynağı",
    }};

    const STATIC_CHOICES = {{
        language: [["tr","Türkçe"],["en","İngilizce"],["de","Almanca"],["fr","Fransızca"],["es","İspanyolca"]],
        content_type: [["documentary","Belgesel"],["news","Haber"],["shorts","Shorts / Reels"],["informational","Bilgi Videosu"]],
        media_mode: [["mixed","Video + Fotoğraf"],["video","Sadece Video"],["image","Sadece Fotoğraf"]],
        resolution: [["720p","720p (1280x720)"],["1080p","1080p (1920x1080)"],["vertical","Dikey (1080x1920)"],["4k","4K (3840x2160)"]],
        fps: [["24","24"],["30","30"],["60","60"]],
        thumbnail_source: [
            ["auto","Otomatik (ücretsiz varsa onu kullan)"],
            ["ai","Yapay Zeka (OpenAI — ücretli, 1 kapak)"],
            ["pexels","Pexels (ücretsiz stok, 4 kapak)"],
            ["scene","Sahne Karesi (yerel, 4 kapak)"],
        ],
    }};

    const NUMERIC_FIELDS = new Set(["fps","target_duration_seconds","voice_speed"]);

    function showRegenerateForm(opts) {{
        return new Promise(resolve => {{
            const overlay = document.createElement("div");
            overlay.style.cssText = "position:fixed;inset:0;background:rgba(10,20,35,.55);z-index:200;display:flex;align-items:center;justify-content:center;padding:16px";

            const box = document.createElement("div");
            box.style.cssText = "background:white;border-radius:18px;padding:24px;width:min(420px,100%);max-height:88vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.3)";

            let fieldsHtml = "";
            for (const field of opts.allowed_fields) {{
                const label = FIELD_LABELS_TR[field] || field;
                const current = opts.current[field];
                const providerChoices = opts.choices[field];
                const staticChoices = STATIC_CHOICES[field];

                if (providerChoices) {{
                    const options = providerChoices.map(c =>
                        `<option value="${{c.key}}" ${{c.key===current?"selected":""}}>${{c.name}}</option>`
                    ).join("");
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <select data-field="${{field}}" style="width:100%;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 10px;font:inherit">${{options}}</select>`;
                }} else if (staticChoices) {{
                    const options = staticChoices.map(([key, name]) =>
                        `<option value="${{key}}" ${{String(current)===key?"selected":""}}>${{name}}</option>`
                    ).join("");
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <select data-field="${{field}}" style="width:100%;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 10px;font:inherit">${{options}}</select>`;
                }} else if (typeof current === "boolean") {{
                    fieldsHtml += `<label style="display:flex;align-items:center;gap:8px;margin-top:14px;font-size:14px;font-weight:400">
                        <input type="checkbox" data-field="${{field}}" ${{current?"checked":""}} style="width:auto;min-height:auto"> ${{label}}
                    </label>`;
                }} else if (typeof current === "number") {{
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <input type="number" step="any" data-field="${{field}}" value="${{current}}" style="width:100%;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 10px;font:inherit">`;
                }} else {{
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <input type="text" data-field="${{field}}" value="${{current ?? ""}}" style="width:100%;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 10px;font:inherit">`;
                }}
            }}

            box.innerHTML = `
                <h3 style="margin-top:0">Ayarları değiştir ve yeniden üret</h3>
                <p class="muted" style="font-size:13px">Bu aşama ve sonrasındaki her şey silinip yeni ayarlarla yeniden üretilecek.</p>
                ${{fieldsHtml}}
                <div style="display:flex;gap:8px;margin-top:20px">
                    <button type="button" id="regenCancel" class="button secondary" style="flex:1">Vazgeç</button>
                    <button type="button" id="regenSubmit" class="button" style="flex:1">Yeniden Üret</button>
                </div>
            `;

            overlay.appendChild(box);
            document.body.appendChild(overlay);

            box.querySelector("#regenCancel").onclick = () => {{ overlay.remove(); resolve(null); }};
            box.querySelector("#regenSubmit").onclick = () => {{
                const overrides = {{}};
                box.querySelectorAll("[data-field]").forEach(el => {{
                    const field = el.dataset.field;
                    if (el.type === "checkbox") overrides[field] = el.checked;
                    else if (NUMERIC_FIELDS.has(field)) overrides[field] = parseFloat(el.value);
                    else overrides[field] = el.value;
                }});
                overlay.remove();
                resolve(overrides);
            }};
        }});
    }}

    function copyToClipboard(btn) {{
        const text = btn.getAttribute("data-copy") || "";
        navigator.clipboard.writeText(text).then(() => {{
            const original = btn.textContent;
            btn.textContent = "✓ Kopyalandı";
            setTimeout(() => {{ btn.textContent = original; }}, 1500);
        }}).catch(() => alert("Kopyalanamadı — panoya erişim engellendi olabilir."));
    }}

    async function selectThumbnail(slug, variant, btn) {{
        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = "⏳...";

        try {{
            const r = await fetch(`/api/projects/${{slug}}/thumbnail/select`, {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{variant}}),
            }});
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "Seçilemedi.");
            location.reload();
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = original;
        }}
    }}

    function applyStepProgress(progress) {{
        document.querySelectorAll("[data-step-index]").forEach(row => {{
            const index = parseInt(row.getAttribute("data-step-index"), 10);
            const key = row.getAttribute("data-step-key");
            const labelEl = row.querySelector(".step-icon-label");
            const statusEl = row.querySelector(".step-status-text");
            const baseLabel = labelEl ? labelEl.getAttribute("data-base-label") : "";

            row.style.transition = "background .2s";

            if (progress.failed_step_key && key === progress.failed_step_key) {{
                row.style.background = "#fef2f2";
                if (labelEl) labelEl.textContent = `❌ ${{baseLabel}}`;
                if (statusEl) statusEl.textContent = "başarısız";
            }} else if (index < progress.completed_steps) {{
                row.style.background = "";
                if (labelEl) labelEl.textContent = `✅ ${{baseLabel}}`;
                if (statusEl) statusEl.textContent = "completed";
            }} else if (key === progress.current_step_key) {{
                row.style.background = "#eff6ff";
                if (labelEl) labelEl.textContent = `⏳ ${{baseLabel}}`;
                if (statusEl) statusEl.textContent = "şu an çalışıyor...";
            }} else {{
                row.style.background = "";
                if (labelEl) labelEl.textContent = `⏳ ${{baseLabel}}`;
                if (statusEl) statusEl.textContent = "pending";
            }}
        }});
    }}

    async function pollUntilDone(jobId) {{
        while (true) {{
            const r = await fetch(`/api/builds/${{jobId}}`);
            const job = await r.json();
            applyStepProgress(job);
            if (job.status === "completed") return;
            if (job.status === "failed") {{
                throw new Error(job.error || "İşlem başarısız oldu.");
            }}
            await new Promise(resolve => setTimeout(resolve, 2000));
        }}
    }}

    async function checkForActiveJob() {{
        const slug = "{escaped_slug_js}";

        try {{
            const r = await fetch("/api/jobs/active");
            const data = await r.json();
            const job = (data.jobs || []).find(j => j.project_slug === slug);
            if (!job) return;

            applyStepProgress(job);
            document.getElementById("actionStatus").textContent =
                "Bu proje için arka planda bir üretim devam ediyor...";
            const resumeBtn = document.getElementById("resumeButton");
            if (resumeBtn) resumeBtn.disabled = true;

            await pollUntilDone(job.job_id);
            location.reload();
        }} catch (e) {{
            // sessizce yut -- sayfanın geri kalanı çalışmaya devam etsin
        }}
    }}

    checkForActiveJob();

    async function regenerateStep(slug, stepKey, btn) {{
        let overrides = {{}};

        try {{
            const optRes = await fetch(`/api/projects/${{slug}}/step-options/${{stepKey}}`);
            const opts = await optRes.json();

            if (opts.allowed_fields && opts.allowed_fields.length > 0) {{
                const chosen = await showRegenerateForm(opts);
                if (chosen === null) return;
                overrides = chosen;
            }} else {{
                if (!confirm(
                    "Bu aşamayı ve sonrasındaki tüm aşamaları yeniden üretmek " +
                    "istediğine emin misin? Sonraki aşamaların çıktıları silinecek."
                )) return;
            }}
        }} catch (e) {{
            alert("Ayarlar alınamadı: " + e.message);
            return;
        }}

        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = "⏳ Üretiliyor...";
        document.getElementById("actionStatus").textContent =
            `${{stepKey}} yeniden üretiliyor...`;

        try {{
            const r = await fetch(
                `/api/projects/${{slug}}/regenerate/${{stepKey}}`,
                {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{overrides}}),
                }}
            );
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "Başlatılamadı.");
            await pollUntilDone(res.job_id);
            location.reload();
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = original;
            document.getElementById("actionStatus").textContent = "";
        }}
    }}

    async function resumeProject(slug, btn) {{
        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = "⏳ Devam ediyor...";
        document.getElementById("actionStatus").textContent =
            "Kalan aşamalar üretiliyor...";

        try {{
            const r = await fetch(
                `/api/projects/${{slug}}/resume`,
                {{method: "POST"}}
            );
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "Başlatılamadı.");
            await pollUntilDone(res.job_id);
            location.reload();
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = original;
            document.getElementById("actionStatus").textContent = "";
        }}
    }}

    async function deleteProject(slug, btn) {{
        if (!confirm(
            "Bu projeyi ve tüm dosyalarını (video, ses, görseller, " +
            "kapaklar) kalıcı olarak silmek istediğine emin misin? " +
            "Bu işlem geri alınamaz."
        )) return;

        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = "⏳ Siliniyor...";

        try {{
            const r = await fetch(`/api/projects/${{slug}}`, {{method: "DELETE"}});
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "Silinemedi.");
            location.href = "/";
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = original;
        }}
    }}
    </script>
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
