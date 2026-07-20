import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.services.thumbnail_service import ThumbnailService
from app.web_new_project import PIPELINE_STEP_ORDER
from app.web_new_project import router as new_project_router
from app.web_settings import router as settings_router
from app.web_storage import router as storage_router
from app.web_voice_test import router as voice_test_router


app = FastAPI(
    title="DocuForge Web Panel",
    version="0.1.0",
)

app.include_router(new_project_router)
app.include_router(settings_router)
app.include_router(storage_router)
app.include_router(voice_test_router)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

PROJECTS_ROOT = Path("projects").resolve()

# Turkish display names for the rotating thumbnail templates -- keyed
# off ThumbnailService.TEMPLATE_ORDER so thumbnail_1.png..thumbnail_N.png
# always map to the right label even if that order ever changes.
THUMBNAIL_TEMPLATE_LABELS: dict[str, str] = {
    "split_contrast": "Split Contrast",
    "mystery_focus": "Mystery Focus",
    "documentary_cinematic": "Documentary Cinematic",
    "breaking_discovery": "Breaking Discovery",
    "headline_highlight": "Başlık Vurgulu",
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


def format_finished_at(value: str | None) -> str | None:
    """Render a step's ISO completion timestamp in the user's local
    time (Türkiye) -- otherwise "Yeniden Üret" gives no way to tell a
    fresh run from a stale one when a step's duration alone doesn't
    make that obvious."""

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None

    try:
        parsed = parsed.astimezone(ZoneInfo("Europe/Istanbul"))
    except Exception:
        pass

    return parsed.strftime("%d.%m %H:%M")


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

        .button:disabled,
        button:disabled {{
            opacity: .55;
            cursor: not-allowed;
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

        body {{
            padding-bottom: 76px;
        }}

        .bottom-nav {{
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            display: flex;
            background: white;
            border-top: 1px solid #e2e8f0;
            box-shadow: 0 -6px 20px rgba(20, 30, 60, .06);
            z-index: 100;
            padding-bottom: env(safe-area-inset-bottom, 0);
        }}

        .bottom-nav a {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            padding: 9px 4px 10px;
            text-decoration: none;
            color: #7c8aa0;
            font-size: 11px;
            font-weight: 700;
        }}

        .bottom-nav a .nav-icon {{
            font-size: 21px;
            line-height: 1;
        }}

        .bottom-nav a.active {{
            color: #2166f3;
        }}
    </style>
</head>

<body>
<header>
    <div class="inner" style="display:flex;align-items:center;justify-content:center">
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

<nav class="bottom-nav">
    <a href="/" class="active"><span class="nav-icon">🏠</span>Ana Sayfa</a>
    <a href="/voice-test"><span class="nav-icon">🎤</span>Ses Testi</a>
    <a href="/storage"><span class="nav-icon">📦</span>Depolama</a>
    <a href="/settings"><span class="nav-icon">⚙</span>Ayarlar</a>
</nav>

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

        if final_video.exists():
            video_size_mb = final_video.stat().st_size / (1024 * 1024)
            video_badge = (
                f'<span class="badge success">🎬 Video hazır '
                f'({video_size_mb:.1f} MB)</span>'
            )
        else:
            video_badge = '<span class="badge warning">⏳ Video yok</span>'

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

    async function cancelActiveJob(jobId, btn) {{
        if (!confirm(
            "Üretimi iptal etmek istediğine emin misin? Mevcut adım " +
            "bitene kadar durmaz, sonrasında duracak."
        )) return;

        btn.disabled = true;
        btn.textContent = "İptal ediliyor…";

        try {{
            const r = await fetch(`/api/builds/${{jobId}}/cancel`, {{method: "POST"}});
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "İptal edilemedi.");
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = "⏹ İptal";
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
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px;flex-wrap:wrap">
                        <strong style="min-width:0;flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{job.topic || job.project_slug || "Proje"}}</strong>
                        <span style="display:flex;gap:8px;flex-shrink:0">
                            ${{slugLink}}
                            <button
                                class="button secondary"
                                style="min-height:34px;padding:0 12px;font-size:13px;color:#b91c1c"
                                onclick="cancelActiveJob('${{job.job_id}}',this)"
                            >⏹ İptal</button>
                        </span>
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
        video_size_mb = final_video.stat().st_size / (1024 * 1024)
        # Cache-busting: the render always writes final_video.mp4 at the
        # exact same path, so without a query param that changes, browsers
        # (mobile Chrome especially) keep playing the OLD cached copy after
        # a regenerate -- same class of bug already fixed for
        # closing_image/channel_logo/xtts_reference_audio below, just
        # missed here for the main output itself. This is what made a
        # genuinely-changed voice/render look like "regenerate did nothing."
        video_version = int(final_video.stat().st_mtime)

        video_section = f"""
        <section class="card">
            <h2>Final video <span class="muted" style="font-weight:400;font-size:15px">({video_size_mb:.1f} MB)</span></h2>

            <video controls preload="metadata">
                <source
                    src="/files/{quote(project_dir.name)}/render/final_video.mp4?v={video_version}"
                    type="video/mp4"
                >
            </video>

            <div class="buttons">
                <a
                    class="button"
                    href="/files/{quote(project_dir.name)}/render/final_video.mp4?v={video_version}"
                    download
                >
                    Videoyu İndir ({video_size_mb:.1f} MB)
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

        # Cache-busting: regenerating overwrites this exact filename, so
        # without a query param that changes, browsers keep showing the
        # old cached design even after a fresh regenerate + page reload.
        variant_version = int(variant_path.stat().st_mtime)
        variant_url = (
            f"/files/{quote(project_dir.name)}/{variant_name}"
            f"?v={variant_version}"
        )

        variant_cards += f"""
        <div style="width:280px">
            <img
                src="{variant_url}"
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
                    href="{variant_url}"
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
        legacy_version = int(thumbnail_path.stat().st_mtime)
        legacy_url = (
            f"/files/{quote(project_dir.name)}/thumbnail.jpg"
            f"?v={legacy_version}"
        )
        legacy_card = f"""
        <div style="width:280px">
            <img
                src="{legacy_url}"
                alt="Kapak görseli"
                style="width:100%;border-radius:12px;display:block"
            >
            <a
                class="button secondary"
                href="{legacy_url}"
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
            vertical_version = int(thumbnail_vertical_path.stat().st_mtime)
            vertical_url = (
                f"/files/{quote(project_dir.name)}/thumbnail_vertical.jpg"
                f"?v={vertical_version}"
            )
            vertical_card = f"""
            <div style="width:160px">
                <img
                    src="{vertical_url}"
                    alt="Dikey kapak"
                    style="width:100%;border-radius:12px;display:block"
                >
                <div style="margin-top:6px">
                    <strong style="font-size:14px">Dikey (9:16)</strong>
                </div>
                <a
                    class="button secondary"
                    href="{vertical_url}"
                    download
                    style="margin-top:6px;font-size:13px;padding:0 10px;
                    min-height:32px;display:inline-flex"
                >
                    ⬇ İndir (9:16)
                </a>
            </div>
            """

        gallery_hint = (
            f"""<p class="muted">
                {len(ThumbnailService.TEMPLATE_ORDER)} farklı tasarım otomatik üretildi -- birini seçip
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

    media_warnings_path = project_dir / "render" / "media_warnings.json"
    media_warning_section = ""

    if media_warnings_path.exists():
        try:
            warning_data = json.loads(
                media_warnings_path.read_text(encoding="utf-8")
            )
            placeholder_scenes = warning_data.get("placeholder_scenes", [])
        except (OSError, json.JSONDecodeError):
            placeholder_scenes = []

        if placeholder_scenes:
            scenes_text = ", ".join(
                str(number) for number in placeholder_scenes
            )
            media_warning_section = f"""
            <section class="card" style="border-color:#f0c96a;background:#fffaf0">
                <h2 style="color:#8a5a00">⚠ Bazı sahnelerde görsel/video üretilemedi</h2>
                <p class="muted">
                    Sahne {html.escape(scenes_text)} için görsel veya video
                    oluşturulamadığından o sahnelerde düz renkli bir arka plan
                    kullanıldı -- anlatım sesi kaybolmadı, sadece görsel eksik.
                    "📦 Medya İndirme" adımını Yeniden Üret ile tekrar
                    denetebilir veya videoyu bu haliyle kullanabilirsin.
                </p>
            </section>
            """

    subtitles_path = project_dir / "render" / "subtitles.srt"
    subtitles_txt_path = project_dir / "render" / "subtitles.txt"
    subtitles_section = ""

    if subtitles_path.exists():
        burned_in = bool(project.get("subtitles_burn_in"))
        burn_in_note = (
            "Altyazı videoya gömüldü (final videoyu izlediğinde görünür)."
            if burned_in
            else "Sahne bazlı zamanlamalı .srt dosyası (videoya gömülü değil, ayrı dosya)."
        )

        # Cache-busting: regenerating render can rewrite these exact
        # filenames, so without a query param that changes, browsers keep
        # offering the old cached download at this exact URL.
        subtitles_version = int(subtitles_path.stat().st_mtime)

        txt_button = ""
        if subtitles_txt_path.exists():
            txt_version = int(subtitles_txt_path.stat().st_mtime)
            txt_button = f"""
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/render/subtitles.txt?v={txt_version}"
                    download
                >
                    subtitles.txt İndir
                </a>
            """

        subtitles_section = f"""
        <section class="card">
            <h2>Altyazı</h2>
            <p class="muted">
                {burn_in_note}
            </p>
            <div class="buttons">
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/render/subtitles.srt?v={subtitles_version}"
                    download
                >
                    subtitles.srt İndir
                </a>
                {txt_button}
            </div>
        </section>
        """

    shorts_section = ""

    if (project_dir / "script.md").exists():
        shorts_section = """
        <section class="card">
            <h2>🎬 Uzun Videodan Shorts Üret</h2>
            <p class="muted">
                Bu videonun senaryosundan birbirinden bağımsız 10 kısa video
                (Shorts) fikri çıkar -- her biri kendi başına izlenebilir,
                kendi kancası olan ayrı bir video. Beğendiğini "Proje Olarak
                Oluştur" ile /new sayfasına aktarabilirsin (dikey/yatay format
                dahil tüm ayarları orada seçersin).
            </p>
            <button class="button" id="shortsSplitBtn" onclick="generateShortsSplit()">
                🎬 10 Shorts Üret
            </button>
            <div id="shortsSplitResults" style="margin-top:14px"></div>
        </section>
        """

    manual_media_section = ""

    if bool(project.get("manual_upload_enabled")):
        manual_media_section = """
        <section class="card" id="manualMediaCard" style="display:none">
            <h2>🖼 Sahne Görsellerini Yükle (Elle — Opsiyonel)</h2>
            <p class="muted">
                İstediğin sahne için aşağıdaki prompt'u ChatGPT'de (veya başka
                bir görsel aracında) üret, çıkan görseli ilgili sahnenin
                kutusuna yükle. <b>Boş bıraktığın sahneler otomatik olarak
                seçili sağlayıcıdan (Pexels/AI) indirilir</b> — hiçbiri zorunlu
                değil. Hazır olunca "Devam Et"e bas; üretim medya adımından
                itibaren sürer.
            </p>
            <div id="manualMediaGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-top:14px"></div>
            <div style="margin-top:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                <button class="button" id="manualContinueBtn" onclick="manualContinue(this)">▶ Devam Et (kalanları otomatik üret)</button>
                <span id="manualMediaStatus" class="muted"></span>
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

        def copy_element_button(element_id: str, label: str = "📋 Kopyala") -> str:
            # Reads .textContent from a sibling element instead of an
            # HTML attribute -- attributes are fine for a single short
            # line (titles, tags), but the description has real \n\n
            # paragraph/bullet breaks that need to survive exactly as
            # typed, which textContent guarantees and an attribute value
            # doesn't reliably.
            return (
                '<button type="button" class="button secondary" '
                'style="min-height:34px;padding:0 12px;font-size:13px;'
                'white-space:nowrap" '
                f'onclick="copyElementText(\'{element_id}\',this)">'
                f'{label}</button>'
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
            f'<span class="badge" style="cursor:pointer" '
            f'data-copy="{html.escape(str(tag), quote=True)}" '
            f'onclick="copyToClipboard(this)" '
            f'title="Kopyalamak için tıkla">{html.escape(str(tag))} 📋</span>'
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
                <p id="seoDescription" style="margin:0;flex:1;white-space:pre-wrap">{html.escape(description)}</p>
                {copy_element_button("seoDescription")}
            </div>

            <h3 style="font-size:15px;margin-bottom:6px">Etiketler</h3>
            <p class="muted" style="margin:0 0 8px;font-size:13px">Tek bir etikete tıklayınca sadece o kopyalanır.</p>
            <div class="badges" style="margin-bottom:10px">{tag_badges}</div>
            <div class="buttons" style="margin-bottom:0">
                {copy_button(tags_csv)}
                <span class="muted" style="font-size:13px;align-self:center">← hepsini virgülle kopyala</span>
            </div>

            <div class="buttons">
                <a
                    class="button secondary"
                    href="/files/{quote(project_dir.name)}/seo.json?v={int(seo_path.stat().st_mtime)}"
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
    project_source_citation_js = json.dumps(
        str(project.get("source_citation", ""))
    )

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
        finished_at = format_finished_at(
            info.get("finished_at") if isinstance(info, dict) else None
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
                        {f'· {html.escape(finished_at)}' if finished_at else ''}
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
                id="cancelProjectBuildButton"
                class="button secondary"
                style="display:none;color:#b91c1c"
                onclick="cancelProjectBuild()"
            >
                ⏹ İptal Et
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

    {media_warning_section}
    {video_section}
    {thumbnail_section}
    {subtitles_section}
    {seo_section}
    {manual_media_section}
    {shorts_section}

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
        scene_transition: "Sahne Geçişi",
        background_music_enabled: "Arka Plan Müziği",
        music_provider: "Müzik Sağlayıcı",
        subtitles_enabled: "Altyazı (.srt) Üret",
        subtitles_burn_in: "Altyazıyı Videoya Göm",
        ai_disclosure_enabled: "Yapay Zeka İbaresi Ekle",
        location_map_enabled: "Konum Haritası Ekle",
        manual_upload_enabled: "Görselleri Elle Yükle",
        thumbnail_source: "Kapak Görseli Kaynağı",
        thumbnail_hook_override: "Kapak Üzerindeki Başlık",
        music_volume: "Müzik Sesi Seviyesi (%)",
    }};

    // Mirrors /new's onProviderChange() voice-name choices exactly --
    // voice_name has no free-form valid values, it's one of a fixed set
    // per provider, so the regen form must offer a picker here too
    // instead of a bare pre-filled text box (which is easy to leave
    // untouched, or to mistype into an invalid value the chosen
    // provider doesn't recognize).
    const VOICE_NAME_OPTIONS = {{
        supertonic: [["M1","M1"],["M2","M2"],["M3","M3"],["F1","F1"],["F2","F2"],["F3","F3"]],
        xtts: [["clone","Klon Sesim"]],
        piper: [["default","Varsayılan"]],
        espeak: [["default","Varsayılan"]],
        local_tts: [["default","Varsayılan"]],
    }};

    const STATIC_CHOICES = {{
        language: [["tr","Türkçe"],["en","İngilizce"],["de","Almanca"],["fr","Fransızca"],["es","İspanyolca"]],
        content_type: [["documentary","Belgesel"],["news","Haber"],["shorts","Shorts / Reels"],["informational","Bilgi Videosu"]],
        media_mode: [["mixed","Video + Fotoğraf"],["video","Sadece Video"],["image","Sadece Fotoğraf"]],
        resolution: [["720p","720p (1280x720)"],["1080p","1080p (1920x1080)"],["vertical","Dikey (1080x1920)"],["4k","4K (3840x2160)"]],
        fps: [["24","24"],["30","30"],["60","60"]],
        scene_transition: [
            ["cut","Sert Kesim"],
            ["crossfade","Yumuşak Geçiş (Crossfade)"],
            ["fade_black","Karartarak Geçiş"],
        ],
        thumbnail_source: [
            ["auto","Otomatik (ücretsiz varsa onu kullan)"],
            ["ai","Yapay Zeka (OpenAI — ücretli, 1 kapak)"],
            ["pexels","Pexels (ücretsiz stok, 4 kapak)"],
            ["scene","Sahne Karesi (yerel, 4 kapak)"],
        ],
    }};

    const NUMERIC_FIELDS = new Set(["fps","target_duration_seconds","voice_speed"]);

    let currentRegenOpts = null;

    function showRegenerateForm(opts) {{
        currentRegenOpts = opts;
        return new Promise(resolve => {{
            const overlay = document.createElement("div");
            overlay.style.cssText = "position:fixed;inset:0;background:rgba(10,20,35,.55);z-index:200;display:flex;align-items:center;justify-content:center;padding:16px";

            const box = document.createElement("div");
            box.style.cssText = "background:white;border-radius:18px;padding:24px;width:min(420px,100%);max-height:88vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.3)";

            let fieldsHtml = "";
            for (const field of opts.allowed_fields) {{
                const label = FIELD_LABELS_TR[field] || field;
                const current = opts.current[field];

                if (field === "voice_name") {{
                    const providerNow = opts.current["voice_provider"] || "supertonic";
                    const nameOptions = VOICE_NAME_OPTIONS[providerNow] || VOICE_NAME_OPTIONS.supertonic;
                    const options = nameOptions.map(([key, name]) =>
                        `<option value="${{key}}" ${{key===current?"selected":""}}>${{name}}</option>`
                    ).join("");
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <select data-field="voice_name" id="regenVoiceNameSelect" style="width:100%;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 10px;font:inherit">${{options}}</select>`;
                    continue;
                }}

                if (field === "music_volume") {{
                    const percent = Math.round((typeof current === "number" ? current : 0.18) * 100);
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <input type="number" min="0" max="50" step="1" data-field="music_volume" data-percent="1" value="${{percent}}" style="width:100%;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 10px;font:inherit">`;
                    continue;
                }}

                if (field === "music_track") {{
                    fieldsHtml += `<label style="display:block;margin-top:14px;font-weight:700;font-size:13px">${{label}}</label>
                        <div style="margin-top:6px;padding:12px;border:1px solid #dbe5f4;border-radius:12px;background:#f8fbff">
                        <div class="muted" style="font-size:12px;margin-bottom:8px">Ticari kullanıma kapalı (NC lisanslı) parçalar listelenmiyor -- ama lisansı belirlenemeyenler ⚠️ ile işaretli, yüklemeden önce kontrol et.</div>
                        <div style="display:flex;gap:8px">
                            <input type="text" id="regenMusicQuery" placeholder="Örnek: cinematic ambient (boş bırakırsan otomatik aranır)" style="flex:1;min-height:40px;border:1px solid #cbd6e5;border-radius:8px;padding:0 10px;font:inherit">
                            <button type="button" id="regenMusicSearchBtn" onclick="regenSearchMusic()" style="width:auto;min-height:40px;padding:0 14px;font-size:13px">🎧 Ara</button>
                            <button type="button" onclick="regenClearMusicSearch()" style="width:auto;min-height:40px;padding:0 14px;font-size:13px">🗑 Temizle</button>
                        </div>
                        <div id="regenMusicMoodTags" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"></div>
                        <div id="regenMusicResults" style="margin-top:10px;max-height:280px;overflow:auto"></div>
                        <div id="regenMusicSelectedInfo" class="muted" style="display:none;margin-top:8px;font-weight:700;font-size:12px;color:#08763a"></div>
                        <div style="margin-top:10px;border-top:1px solid #dbe5f4;padding-top:10px">
                            <div style="display:flex;align-items:center;justify-content:space-between">
                                <strong style="font-size:13px">⭐ Favorilerim</strong>
                                <button type="button" id="regenFavoritesToggleBtn" onclick="regenToggleFavoritesList()" style="width:auto;min-height:28px;margin-top:0;padding:0 10px;font-size:12px">Göster</button>
                            </div>
                            <div id="regenMusicFavoritesList" style="display:none;margin-top:8px;max-height:280px;overflow:auto"></div>
                        </div>
                        </div>
                        <input type="hidden" data-field="music_track" id="regenMusicTrackValue" value="${{current ?? ""}}">`;
                    continue;
                }}

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

            if (opts.allowed_fields.includes("music_track")) {{
                regenUpdateMusicMoodSuggestion();
            }}

            // Voice name is a fixed set per provider (M1-M3/F1-F3 for
            // Supertonic, "clone" for XTTS, "default" otherwise) -- when
            // the provider dropdown is also in this form, changing it
            // must refresh the name picker's options live, exactly like
            // /new's onProviderChange(), or the submitted voice_name can
            // end up invalid/stale for the newly chosen provider.
            const regenVoiceProviderEl = box.querySelector('[data-field="voice_provider"]');
            const regenVoiceNameEl = box.querySelector('#regenVoiceNameSelect');
            if (regenVoiceProviderEl && regenVoiceNameEl) {{
                regenVoiceProviderEl.addEventListener("change", () => {{
                    const nameOptions = VOICE_NAME_OPTIONS[regenVoiceProviderEl.value] || VOICE_NAME_OPTIONS.supertonic;
                    regenVoiceNameEl.innerHTML = nameOptions.map(([key, name]) =>
                        `<option value="${{key}}">${{name}}</option>`
                    ).join("");
                }});
            }}

            box.querySelector("#regenCancel").onclick = () => {{ overlay.remove(); resolve(null); }};
            box.querySelector("#regenSubmit").onclick = () => {{
                const overrides = {{}};
                box.querySelectorAll("[data-field]").forEach(el => {{
                    const field = el.dataset.field;
                    if (el.type === "checkbox") overrides[field] = el.checked;
                    else if (el.dataset.percent === "1") overrides[field] = parseFloat(el.value) / 100;
                    else if (NUMERIC_FIELDS.has(field)) overrides[field] = parseFloat(el.value);
                    else overrides[field] = el.value;
                }});
                overlay.remove();
                resolve(overrides);
            }};
        }});
    }}

    function escapeHtmlLocal(s) {{
        const d = document.createElement("div");
        d.textContent = s == null ? "" : String(s);
        return d.innerHTML;
    }}

    async function regenUpdateMusicMoodSuggestion() {{
        const box = document.getElementById("regenMusicMoodTags");
        if (!box) return;
        const topic = (currentRegenOpts && currentRegenOpts.topic) || "";
        const contentType = (currentRegenOpts && currentRegenOpts.content_type) || "documentary";
        box.innerHTML = '<span class="muted" style="font-size:12px">Etiketler hazırlanıyor…</span>';
        try {{
            const params = new URLSearchParams({{topic, content_type: contentType}});
            const res = await fetch(`/api/music-mood?${{params.toString()}}`);
            const data = await res.json();
            regenRenderMusicMoodTags(data.tags || []);
        }} catch (e) {{
            box.innerHTML = "";
        }}
    }}

    function regenRenderMusicMoodTags(tags) {{
        const box = document.getElementById("regenMusicMoodTags");
        if (!box) return;
        if (!tags.length) {{ box.innerHTML = ""; return; }}
        box.innerHTML = tags.map(tag =>
            `<button type="button" data-tag="${{escapeHtmlLocal(tag)}}" onclick="regenAddMusicTag(this)" style="width:auto;min-height:28px;margin-top:0;padding:0 10px;font-size:12px;font-weight:700;background:white;color:#2166f3;border:1px solid #cbd6e5;border-radius:999px;cursor:pointer">+ ${{escapeHtmlLocal(tag)}}</button>`
        ).join("");
    }}

    function regenAddMusicTag(btn) {{
        const tag = btn.getAttribute("data-tag");
        const input = document.getElementById("regenMusicQuery");
        const current = input.value.split(/\s+/).map(t => t.trim()).filter(Boolean);
        if (!current.includes(tag)) {{
            current.push(tag);
            input.value = current.join(" ");
        }}
    }}

    async function regenSearchMusic() {{
        const btn = document.getElementById("regenMusicSearchBtn");
        const box = document.getElementById("regenMusicResults");
        const query = document.getElementById("regenMusicQuery").value.trim();
        const contentType = (currentRegenOpts && currentRegenOpts.content_type) || "documentary";
        const providerEl = document.querySelector('[data-field="music_provider"]');
        const provider = providerEl ? providerEl.value : "jamendo";
        lastRegenMusicProvider = provider;
        const isElevenLabs = provider === "elevenlabs";
        btn.disabled = true;
        btn.textContent = isElevenLabs ? "⏳ Üretiliyor…" : "⏳ Aranıyor…";
        const catalogLabel = provider === "freesound" ? "Freesound’da" : "Jamendo’da";
        box.innerHTML = isElevenLabs
            ? '<div class="muted" style="font-size:13px">ElevenLabs ile arka plan müziği üretiliyor, bu birkaç saniye sürebilir…</div>'
            : `<div class="muted" style="font-size:13px">${{catalogLabel}} telifsiz parçalar aranıyor…</div>`;
        try {{
            const params = new URLSearchParams({{query, content_type: contentType, provider}});
            const res = await fetch(`/api/music-search?${{params.toString()}}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Arama başarısız.");
            regenRenderMusicResults(data.tracks || []);
        }} catch (err) {{
            box.innerHTML = `<div class="muted" style="font-size:13px;color:#9f2020">${{escapeHtmlLocal(err.message)}}</div>`;
        }} finally {{
            btn.disabled = false;
            btn.textContent = isElevenLabs ? "🎵 Üret" : "🎧 Ara";
        }}
    }}

    function regenClearMusicSearch() {{
        document.getElementById("regenMusicQuery").value = "";
        document.getElementById("regenMusicResults").innerHTML = "";
        document.getElementById("regenMusicTrackValue").value = "";
        const info = document.getElementById("regenMusicSelectedInfo");
        info.style.display = "none";
        info.textContent = "";
    }}

    function regenMusicLicenseBadge(license) {{
        if (!license || license.commercial_ok === null || license.commercial_ok === undefined) {{
            return '<span style="color:#8899aa">Lisans bilinmiyor</span>';
        }}
        const color = license.commercial_ok ? "#08763a" : "#9f2020";
        const icon = license.commercial_ok ? "✅" : "⚠️";
        return `<span style="color:${{color}};font-weight:700">${{icon}} ${{escapeHtmlLocal(license.label || "")}}</span>`;
    }}

    let lastRegenMusicResults = [];
    let lastRegenMusicProvider = "jamendo";

    function regenRenderMusicResults(tracks) {{
        lastRegenMusicResults = tracks;
        const box = document.getElementById("regenMusicResults");
        if (!tracks.length) {{
            box.innerHTML = '<div class="muted" style="font-size:13px">Sonuç bulunamadı, farklı bir arama dene.</div>';
            return;
        }}
        box.innerHTML = tracks.map((t, i) => {{
            const dur = parseInt(t.duration) || 0;
            const mins = Math.floor(dur / 60);
            const secs = String(dur % 60).padStart(2, "0");
            const label = `${{t.name || "Untitled"}} — ${{t.artist || "Bilinmeyen sanatçı"}}`;
            return `<div style="padding:10px 0;${{i > 0 ? "border-top:1px solid #eef1f6" : ""}}">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
                    <div>
                        <div style="font-weight:700;font-size:13px">${{escapeHtmlLocal(t.name || "Untitled")}}</div>
                        <div class="muted" style="font-size:12px">${{escapeHtmlLocal(t.artist || "Bilinmeyen sanatçı")}} · ${{mins}}:${{secs}}</div>
                        <div style="font-size:12px;margin-top:2px">${{regenMusicLicenseBadge(t.license)}}</div>
                    </div>
                    <div style="display:flex;gap:6px">
                        <button type="button" onclick="regenAddFavoriteFromResult(this,${{i}})" style="width:auto;min-height:32px;margin-top:0;padding:0 10px;font-size:12px;background:#fff;color:#9f5a00;border:1px solid #e2e7ee">☆ Favorile</button>
                        <button type="button" class="regen-music-pick-btn" data-url="${{escapeHtmlLocal(t.download_url || "")}}" data-label="${{escapeHtmlLocal(label)}}" onclick="regenSelectMusicTrack(this)" style="width:auto;min-height:32px;margin-top:0;padding:0 12px;font-size:12px;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5">Seç</button>
                    </div>
                </div>
                <audio class="df-audio-preview" onplay="pauseOtherAudio(this)" controls preload="none" src="${{escapeHtmlLocal(t.preview_url || "")}}" style="width:100%;margin-top:6px;height:32px"></audio>
            </div>`;
        }}).join("");
    }}

    function pauseOtherAudio(current) {{
        document.querySelectorAll("audio.df-audio-preview").forEach(a => {{
            if (a !== current) a.pause();
        }});
    }}

    async function regenAddFavoriteFromResult(btn, index) {{
        const track = lastRegenMusicResults[index];
        if (!track) return;
        btn.disabled = true;
        btn.textContent = "⏳...";
        try {{
            const res = await fetch("/api/music-favorites", {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{provider: lastRegenMusicProvider, ...track}}),
            }});
            if (!res.ok) {{
                const err = await res.json().catch(() => ({{}}));
                throw new Error(err.detail || "Favorilere eklenemedi.");
            }}
            btn.textContent = "★ Favoride";
            btn.style.background = "#fff7e0";
            btn.style.color = "#9f5a00";
            btn.style.border = "1px solid #f0dca0";
            if (document.getElementById("regenMusicFavoritesList").style.display === "block") {{
                regenLoadFavorites();
            }}
        }} catch (e) {{
            btn.disabled = false;
            btn.textContent = "☆ Favorile";
            alert("Hata: " + e.message);
        }}
    }}

    function regenToggleFavoritesList() {{
        const box = document.getElementById("regenMusicFavoritesList");
        const btn = document.getElementById("regenFavoritesToggleBtn");
        const showing = box.style.display === "block";
        box.style.display = showing ? "none" : "block";
        btn.textContent = showing ? "Göster" : "Gizle";
        if (!showing) regenLoadFavorites();
    }}

    async function regenLoadFavorites() {{
        const box = document.getElementById("regenMusicFavoritesList");
        box.innerHTML = '<div class="muted" style="font-size:13px">Yükleniyor…</div>';
        try {{
            const res = await fetch("/api/music-favorites");
            const data = await res.json();
            regenRenderFavorites(data.favorites || []);
        }} catch (e) {{
            box.innerHTML = '<div class="muted" style="font-size:13px;color:#9f2020">Favoriler yüklenemedi.</div>';
        }}
    }}

    function regenRenderFavorites(favorites) {{
        const box = document.getElementById("regenMusicFavoritesList");
        if (!favorites.length) {{
            box.innerHTML = '<div class="muted" style="font-size:13px">Henüz favori yok -- sonuçların yanındaki ⭐ ile ekleyebilirsin.</div>';
            return;
        }}
        box.innerHTML = favorites.map(f => {{
            const dur = parseInt(f.duration) || 0;
            const mins = Math.floor(dur / 60);
            const secs = String(dur % 60).padStart(2, "0");
            const label = `${{f.name || "Untitled"}} — ${{f.artist || "Bilinmeyen sanatçı"}}`;
            return `<div style="padding:8px 0;border-top:1px solid #eef1f6">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap">
                    <div>
                        <div style="font-weight:700;font-size:13px">${{escapeHtmlLocal(f.name || "Untitled")}}</div>
                        <div class="muted" style="font-size:12px">${{escapeHtmlLocal(f.artist || "Bilinmeyen sanatçı")}} · ${{mins}}:${{secs}} · ${{escapeHtmlLocal(f.provider || "")}}</div>
                    </div>
                    <div style="display:flex;gap:6px">
                        <button type="button" data-url="${{escapeHtmlLocal(f.download_url || "")}}" data-label="${{escapeHtmlLocal(label)}}" onclick="regenSelectFavorite(this)" style="width:auto;min-height:30px;margin-top:0;padding:0 10px;font-size:12px;background:#eef3fc;color:#2166f3;border:1px solid #cbd6e5">Seç</button>
                        <button type="button" data-provider="${{escapeHtmlLocal(f.provider || "")}}" data-id="${{escapeHtmlLocal(f.id || "")}}" onclick="regenRemoveFavorite(this)" style="width:auto;min-height:30px;margin-top:0;padding:0 10px;font-size:12px;background:#fde8e8;color:#9f2020;border:1px solid #f3c9c9">🗑</button>
                    </div>
                </div>
                <audio class="df-audio-preview" onplay="pauseOtherAudio(this)" controls preload="none" src="${{escapeHtmlLocal(f.preview_url || "")}}" style="width:100%;margin-top:6px;height:32px"></audio>
            </div>`;
        }}).join("");
    }}

    function regenSelectFavorite(btn) {{
        document.getElementById("regenMusicTrackValue").value = btn.dataset.url;
        const info = document.getElementById("regenMusicSelectedInfo");
        info.style.display = "block";
        info.textContent = "🎵 Seçilen parça: " + btn.dataset.label;
    }}

    async function regenRemoveFavorite(btn) {{
        try {{
            const res = await fetch(`/api/music-favorites/${{encodeURIComponent(btn.dataset.provider)}}/${{encodeURIComponent(btn.dataset.id)}}`, {{method: "DELETE"}});
            if (!res.ok) throw new Error("Kaldırılamadı.");
            regenLoadFavorites();
        }} catch (e) {{
            alert("Hata: " + e.message);
        }}
    }}

    function regenSelectMusicTrack(btn) {{
        document.querySelectorAll(".regen-music-pick-btn").forEach(b => {{
            b.textContent = "Seç";
            b.style.background = "#eef3fc";
            b.style.color = "#2166f3";
            b.style.border = "1px solid #cbd6e5";
        }});
        btn.textContent = "✅ Seçildi";
        btn.style.background = "#08763a";
        btn.style.color = "white";
        btn.style.border = "1px solid #08763a";

        const url = btn.getAttribute("data-url");
        const label = btn.getAttribute("data-label");
        document.getElementById("regenMusicTrackValue").value = url;
        const info = document.getElementById("regenMusicSelectedInfo");
        info.style.display = "block";
        info.textContent = "🎵 Seçilen parça: " + label;
    }}

    function copyToClipboard(btn) {{
        const text = btn.getAttribute("data-copy") || "";
        navigator.clipboard.writeText(text).then(() => {{
            const original = btn.textContent;
            btn.textContent = "✓ Kopyalandı";
            setTimeout(() => {{ btn.textContent = original; }}, 1500);
        }}).catch(() => alert("Kopyalanamadı — panoya erişim engellendi olabilir."));
    }}

    function copyElementText(elementId, btn) {{
        const el = document.getElementById(elementId);
        const text = el ? el.textContent : "";
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
            let r;
            try {{
                r = await fetch(`/api/builds/${{jobId}}`);
            }} catch (networkError) {{
                // Sekme arka plana atıldığında ya da bağlantı geçici
                // kesildiğinde fetch() burada atar -- işin durduğu
                // anlamına gelmez, sunucuda arka planda çalışmaya devam
                // ediyor olabilir. Sessizce yeniden dene.
                document.getElementById("actionStatus").textContent =
                    "Bağlantı kontrol ediliyor…";
                await new Promise(resolve => setTimeout(resolve, 3000));
                continue;
            }}

            const job = await r.json();
            applyStepProgress(job);
            if (job.status === "completed") return;
            if (job.status === "failed") {{
                throw new Error(job.error || "İşlem başarısız oldu.");
            }}
            await new Promise(resolve => setTimeout(resolve, 2000));
        }}
    }}

    let activeBuildJobId = null;

    async function checkForActiveJob() {{
        const slug = "{escaped_slug_js}";

        try {{
            const r = await fetch("/api/jobs/active");
            const data = await r.json();
            const job = (data.jobs || []).find(j => j.project_slug === slug);
            if (!job) return;

            activeBuildJobId = job.job_id;
            applyStepProgress(job);
            document.getElementById("actionStatus").textContent =
                "Bu proje için arka planda bir üretim devam ediyor...";
            const resumeBtn = document.getElementById("resumeButton");
            if (resumeBtn) resumeBtn.disabled = true;
            const cancelBtn = document.getElementById("cancelProjectBuildButton");
            if (cancelBtn) {{
                cancelBtn.style.display = "inline-flex";
                cancelBtn.disabled = false;
                cancelBtn.textContent = "⏹ İptal Et";
            }}

            await pollUntilDone(job.job_id);
            location.reload();
        }} catch (e) {{
            // sessizce yut -- sayfanın geri kalanı çalışmaya devam etsin
        }}
    }}

    async function cancelProjectBuild() {{
        if (!activeBuildJobId) return;
        if (!confirm(
            "Üretimi iptal etmek istediğine emin misin? Mevcut adım " +
            "bitene kadar durmaz, sonrasında duracak."
        )) return;

        const btn = document.getElementById("cancelProjectBuildButton");
        btn.disabled = true;
        btn.textContent = "İptal ediliyor…";

        try {{
            const r = await fetch(`/api/builds/${{activeBuildJobId}}/cancel`, {{method: "POST"}});
            const res = await r.json();
            if (!r.ok) throw new Error(res.detail || "İptal edilemedi.");
            document.getElementById("actionStatus").textContent =
                "İptal ediliyor… mevcut adım bitince duracak.";
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = "⏹ İptal Et";
        }}
    }}

    checkForActiveJob();
    loadShortsSplit();
    loadManualMedia();

    async function loadManualMedia() {{
        const card = document.getElementById("manualMediaCard");
        if (!card) return;
        try {{
            const r = await fetch(`/api/projects/{escaped_slug_js}/manual-media`);
            if (!r.ok) return;
            const data = await r.json();
            if (!data.manual || !data.awaiting || !data.scenes || !data.scenes.length) {{
                card.style.display = "none";
                return;
            }}
            renderManualMedia(data);
            card.style.display = "";
        }} catch (e) {{
            // sessizce yut
        }}
    }}

    function renderManualMedia(data) {{
        const grid = document.getElementById("manualMediaGrid");
        window.__manualPrompts = {{}};

        const sourceMeta = {{
            stock: {{
                label: "Stok önerilir",
                color: "#1f7a4d",
                bg: "#eaf8f0",
            }},
            generated: {{
                label: "AI üretimi önerilir",
                color: "#6b3fa0",
                bg: "#f3ecfb",
            }},
            infographic: {{
                label: "İnfografik önerilir",
                color: "#1f5ea8",
                bg: "#eaf2fb",
            }},
            archive: {{
                label: "Gerçek arşiv gerekir",
                color: "#a14d00",
                bg: "#fff1e3",
            }},
        }};

        data.scenes.forEach(s => {{
            window.__manualPrompts[s.scene] = s.prompt || "";
        }});

        grid.innerHTML = data.scenes.map(s => {{
            const done = s.uploaded;
            const source = sourceMeta[s.recommended_source]
                || sourceMeta.stock;

            const preview = (done && s.url)
                ? `<img src="${{s.url}}?t=${{Date.now()}}" style="width:100%;border-radius:8px;margin-top:10px">`
                : "";

            const sensitive = s.sensitive
                ? `<div style="margin-top:10px;background:#fff4e5;border:1px solid #ffd8a8;border-radius:8px;padding:8px 10px;font-size:12px;color:#8a5a00">⚠ Telif/gerçeklik açısından hassas${{s.sensitive_reason ? ': ' + escapeHtmlJs(s.sensitive_reason) : ''}}</div>`
                : "";

            const summary = s.visual_summary
                ? `<div style="margin-top:10px"><strong>Görselde ne olacak?</strong><div style="margin-top:4px;color:#334155">${{escapeHtmlJs(s.visual_summary)}}</div></div>`
                : "";

            const goal = s.generation_goal
                ? `<div style="margin-top:10px"><strong>Bu görselle ne anlatılacak?</strong><div style="margin-top:4px;color:#334155">${{escapeHtmlJs(s.generation_goal)}}</div></div>`
                : "";

            const reason = s.recommendation_reason
                ? `<div style="margin-top:10px"><strong>Neden bu yöntem?</strong><div style="margin-top:4px;color:#334155">${{escapeHtmlJs(s.recommendation_reason)}}</div></div>`
                : "";

            const authenticity = s.authenticity_note
                ? `<div style="margin-top:10px;background:#f8fafc;border-left:4px solid #94a3b8;padding:8px 10px;border-radius:6px"><strong>Gerçeklik notu</strong><div style="margin-top:4px;color:#475569">${{escapeHtmlJs(s.authenticity_note)}}</div></div>`
                : "";

            const statusLabel = done
                ? "✅ Özel görsel yüklendi"
                : "Otomatik tamamlanacak";

            return `
            <div style="border:1px solid ${{done ? '#bfe3c6' : '#dbe5f4'}};border-radius:12px;padding:14px;background:${{done ? '#f2fbf4' : '#ffffff'}}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
                    <div>
                        <strong>Sahne ${{s.scene}}${{s.title ? ' — ' + escapeHtmlJs(s.title) : ''}}</strong>
                        <div style="margin-top:6px">
                            <span style="display:inline-block;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:700;color:${{source.color}};background:${{source.bg}}">
                                ${{source.label}}
                            </span>
                        </div>
                    </div>
                    <span style="font-size:12px;color:#475569;text-align:right">${{statusLabel}}</span>
                </div>

                ${{sensitive}}
                ${{summary}}
                ${{goal}}
                ${{reason}}
                ${{authenticity}}

                <details style="margin-top:12px">
                    <summary style="cursor:pointer;font-weight:700;color:#245ec7">
                        Tam üretim promptunu göster
                    </summary>
                    <div style="font-size:12px;color:#334155;margin-top:8px;max-height:220px;overflow:auto;white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px">${{escapeHtmlJs(s.prompt || '(prompt yok)')}}</div>
                </details>

                <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">
                    <button type="button" onclick="copyManualPrompt(this, ${{s.scene}})" style="flex:1;min-height:34px;font-size:12px">
                        📋 Promptu Kopyala
                    </button>
                    <label style="flex:1;min-height:34px;display:flex;align-items:center;justify-content:center;font-size:12px;border:1px solid #cbd6e5;border-radius:8px;cursor:pointer;background:#f4f8ff">
                        ${{done ? '🔄 Görseli Değiştir' : '⬆ Görsel Yükle'}}
                        <input type="file" accept="image/*" style="display:none" onchange="uploadManualScene(${{s.scene}}, this)">
                    </label>
                </div>

                <div style="margin-top:8px;font-size:12px;color:#64748b">
                    Boş bırakırsan seçili otomatik sağlayıcı bu sahneyi tamamlar.
                </div>

                ${{preview}}
            </div>`;
        }}).join("");

        const status = document.getElementById("manualMediaStatus");
        const uploaded = data.scenes.filter(s => s.uploaded).length;
        const auto = data.scenes.length - uploaded;

        status.textContent =
            `${{uploaded}} / ${{data.scenes.length}} sahneye özel görsel yüklendi`
            + (auto > 0
                ? ` — kalan ${{auto}} sahne otomatik tamamlanacak`
                : "");
    }}

    function escapeHtmlJs(s) {{
        const d = document.createElement("div");
        d.textContent = s == null ? "" : String(s);
        return d.innerHTML;
    }}

    async function copyManualPrompt(btn, scene) {{
        const p = (window.__manualPrompts || {{}})[scene] || "";
        try {{
            await navigator.clipboard.writeText(p);
            const o = btn.textContent;
            btn.textContent = "✅ Kopyalandı";
            setTimeout(() => {{ btn.textContent = o; }}, 1200);
        }} catch (e) {{
            alert("Kopyalanamadı: " + e.message);
        }}
    }}

    async function uploadManualScene(scene, input) {{
        if (!input.files || !input.files[0]) return;
        const fd = new FormData();
        fd.append("file", input.files[0]);
        const status = document.getElementById("manualMediaStatus");
        status.textContent = `Sahne ${{scene}} yükleniyor…`;
        try {{
            const r = await fetch(`/api/projects/{escaped_slug_js}/manual-media/${{scene}}/upload`, {{method: "POST", body: fd}});
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || "Yüklenemedi.");
            await loadManualMedia();
        }} catch (e) {{
            alert("Hata: " + e.message);
            status.textContent = "";
        }}
    }}

    async function manualContinue(btn) {{
        btn.disabled = true;
        btn.textContent = "⏳ Devam ediliyor…";
        try {{
            const r = await fetch(`/api/projects/{escaped_slug_js}/manual-media/continue`, {{method: "POST"}});
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || "Devam edilemedi.");
            document.getElementById("manualMediaCard").style.display = "none";
            location.reload();
        }} catch (e) {{
            alert("Hata: " + e.message);
            btn.disabled = false;
            btn.textContent = "▶ Devam Et (kalanları otomatik üret)";
        }}
    }}

    async function loadShortsSplit() {{
        const box = document.getElementById("shortsSplitResults");
        if (!box) return;
        try {{
            const r = await fetch(`/api/projects/{escaped_slug_js}/shorts-split`);
            if (!r.ok) return;
            const data = await r.json();
            if (data.shorts && data.shorts.length) renderShortsSplit(data.shorts);
        }} catch (e) {{
            // sessizce yut -- sayfanın geri kalanı çalışmaya devam etsin
        }}
    }}

    async function generateShortsSplit() {{
        const btn = document.getElementById("shortsSplitBtn");
        const original = btn.textContent;
        btn.disabled = true;
        btn.textContent = "⏳ Üretiliyor…";
        try {{
            const r = await fetch(`/api/projects/{escaped_slug_js}/shorts-split`, {{method: "POST"}});
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || "Üretilemedi.");
            renderShortsSplit(data.shorts || []);
        }} catch (e) {{
            alert("Hata: " + e.message);
        }} finally {{
            btn.disabled = false;
            btn.textContent = original;
        }}
    }}

    function renderShortsSplit(shorts) {{
        window.__shortsSplitData = shorts;
        const box = document.getElementById("shortsSplitResults");
        box.innerHTML = shorts.map((s, i) => `
            <div style="padding:12px 0;${{i > 0 ? "border-top:1px solid #eef1f6" : ""}}">
                <div style="font-weight:700">${{i + 1}}. ${{escapeHtmlLocal(s.title)}}</div>
                <div class="muted" style="font-size:13px;margin-top:4px">${{escapeHtmlLocal(s.script)}}</div>
                <button
                    class="button secondary"
                    style="margin-top:8px;min-height:34px;padding:0 12px;font-size:13px"
                    onclick="createShortAsProject(${{i}})"
                >
                    ➕ Proje Olarak Oluştur
                </button>
            </div>
        `).join("");
    }}

    function createShortAsProject(index) {{
        const s = window.__shortsSplitData[index];
        sessionStorage.setItem("docuforge_prefill", JSON.stringify({{
            topic: s.title,
            source_material: s.script,
            content_type: "shorts",
            source_citation: {project_source_citation_js},
        }}));
        window.location.href = "/new";
    }}

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
