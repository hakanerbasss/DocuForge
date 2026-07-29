"""Photo Story feature — upload comic-strip panels, add SFX, render video."""

import html
import io
import json
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image
from pydantic import BaseModel, Field

from app.services.photo_story_service import PhotoStoryService

router = APIRouter()

PHOTO_STORIES_ROOT = Path("photo_stories")
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

TRANSITION_OPTIONS = [
    ("crossfade", "Yavaş Geçiş (Crossfade)"),
    ("fade_black", "Karartarak Geçiş"),
    ("cut", "Sert Kesim"),
]


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _load_config(project_dir: Path) -> dict[str, Any]:
    p = project_dir / "photo_story.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_config(project_dir: Path, config: dict[str, Any]) -> None:
    (project_dir / "photo_story.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_project_dir(slug: str) -> Path:
    PHOTO_STORIES_ROOT.mkdir(parents=True, exist_ok=True)
    d = (PHOTO_STORIES_ROOT / slug).resolve()
    if PHOTO_STORIES_ROOT.resolve() not in d.parents or not d.is_dir():
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")
    return d


def _slug_from_title(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = s.strip("-")[:50]
    return s or "hikaye"


def _page(body: str, active: str = "/photo-story") -> str:
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Fotoğraf Hikayesi · DocuForge</title>
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#2166f3">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="DocuForge">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
<style>
*{{box-sizing:border-box}}
body{{margin:0;padding-bottom:76px;min-height:100vh;background:#f3f6fb;color:#172033;
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{padding:14px 18px;background:white;border-bottom:1px solid #e1e8f2}}
.hinner{{width:min(860px,calc(100% - 28px));margin:auto;display:flex;
    align-items:center;gap:10px}}
main{{width:min(860px,calc(100% - 28px));margin:24px auto 60px}}
.back{{color:#245ec7;text-decoration:none;font-weight:700;font-size:14px}}
.card{{padding:20px;background:white;border:1px solid #e0e7f1;
    border-radius:18px;box-shadow:0 8px 28px rgba(34,54,80,.07);margin-bottom:16px}}
h1{{margin:0 0 6px;font-size:clamp(22px,5vw,32px)}}
h3{{margin:18px 0 6px;font-size:13px;color:#445;text-transform:uppercase;
    letter-spacing:.05em}}
.muted{{color:#66758c;font-size:13px}}
label{{display:block;margin-top:12px;margin-bottom:4px;font-weight:700;font-size:14px}}
input,select,textarea{{width:100%;min-height:40px;padding:0 10px;
    border:1px solid #cbd6e5;border-radius:9px;background:white;color:#172033;font:inherit}}
textarea{{padding:8px 10px;resize:vertical}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.row3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
button{{width:100%;min-height:44px;margin-top:12px;border:0;border-radius:12px;
    background:#2166f3;color:white;font-size:15px;font-weight:800;cursor:pointer}}
button.secondary{{background:#eef3fb;color:#1e3a62;border:1px solid #c6d8f5}}
button.danger{{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}}
button.sm{{min-height:34px;font-size:12px;padding:0 12px;width:auto;margin-top:0}}
button:disabled{{opacity:.55;cursor:wait}}
.hint{{font-size:12px;color:#8899aa;margin-top:3px}}
.slot-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-top:14px}}
.slot{{border:1px solid #dbe5f4;border-radius:12px;padding:12px;background:#fff}}
.slot-num{{font-weight:700;font-size:12px;color:#6b7a94;margin-bottom:8px}}
.slot-img{{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:8px;
    display:block;background:#f0f4f9}}
.slot-img.empty{{display:flex;align-items:center;justify-content:center;
    color:#94a3b8;font-size:28px;border:2px dashed #cbd6e5}}
.sfx-status{{font-size:11px;color:#059669;margin-top:4px;min-height:16px}}
.sfx-status.err{{color:#dc2626}}
.pill{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;
    font-weight:700}}
.pill.green{{color:#1f7a4d;background:#eaf8f0}}
.pill.red{{color:#9f2020;background:#ffe9e9}}
.pill.blue{{color:#1f5ea8;background:#eaf2fb}}
.status-box{{padding:14px;border-radius:12px;background:#edf4ff;margin-top:14px}}
.status-box.ok{{background:#e8f8ee;color:#08763a}}
.status-box.err{{background:#ffe9e9;color:#9f2020}}
.bottom-nav{{position:fixed;left:0;right:0;bottom:0;display:flex;background:white;
    border-top:1px solid #e2e8f0;box-shadow:0 -6px 20px rgba(20,30,60,.06);
    z-index:100;padding-bottom:env(safe-area-inset-bottom,0)}}
.bottom-nav a{{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;
    padding:9px 4px 10px;text-decoration:none;color:#7c8aa0;font-size:11px;font-weight:700}}
.bottom-nav a .nav-icon{{font-size:21px;line-height:1}}
.bottom-nav a.active{{color:#2166f3}}
</style>
</head>
<body>
<header><div class="hinner">
    <a class="back" href="/">← Projelere dön</a>
</div></header>
<main>
{body}
</main>
<nav class="bottom-nav">
    <a href="/"><span class="nav-icon">🏠</span>Ana Sayfa</a>
    <a href="/photo-story" class="{"active" if active == "/photo-story" else ""}"><span class="nav-icon">🎞</span>Foto Hikaye</a>
    <a href="/voice-test"><span class="nav-icon">🎤</span>Ses Testi</a>
    <a href="/settings"><span class="nav-icon">⚙</span>Ayarlar</a>
</nav>
<script>
if ("serviceWorker" in navigator) {{
    navigator.serviceWorker.register("/static/sw.js").catch(() => {{}});
}}
</script>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# List page                                                                    #
# --------------------------------------------------------------------------- #

@router.get("/photo-story", response_class=HTMLResponse)
def photo_story_list() -> HTMLResponse:
    PHOTO_STORIES_ROOT.mkdir(parents=True, exist_ok=True)

    projects = []
    for d in sorted(PHOTO_STORIES_ROOT.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        cfg = _load_config(d)
        if not cfg:
            continue
        slug = d.name
        title = html.escape(str(cfg.get("title") or slug))
        panel_count = int(cfg.get("panel_count") or 0)
        slots_done = sum(
            1 for s in (cfg.get("slots") or {}).values()
            if s.get("panel_file")
        )
        has_video = (d / "render" / "photo_story.mp4").exists()
        badge = (
            '<span class="pill green">✅ Video Hazır</span>'
            if has_video else
            f'<span class="pill blue">{slots_done}/{panel_count} panel</span>'
        )
        projects.append(
            f'<a href="/photo-story/{slug}" style="display:block;text-decoration:none;'
            f'color:inherit;border:1px solid #dbe5f4;border-radius:12px;padding:14px;'
            f'background:#fff;margin-bottom:10px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<strong style="font-size:15px">{title}</strong>{badge}</div>'
            f'<div class="muted" style="margin-top:4px">{slug}</div>'
            f'</a>'
        )

    items_html = "\n".join(projects) if projects else (
        '<div class="muted" style="text-align:center;padding:40px 0">'
        'Henüz fotoğraf hikayesi yok. Yeni bir tane oluştur!</div>'
    )

    body = f"""
    <div class="card">
        <h1>🎞 Fotoğraf Hikayesi</h1>
        <p class="muted">PhotoSplit ile böldüğün panel görsellerini yükle, her panele Freesound ses efekti ekle ve tek videoya dönüştür.</p>
        <a href="/photo-story/new" style="display:inline-flex;align-items:center;
            min-height:44px;padding:0 18px;background:#2166f3;color:white;
            text-decoration:none;border-radius:12px;font-weight:700;margin-top:10px">
            + Yeni Hikaye Oluştur
        </a>
    </div>
    <div style="margin-top:6px">{items_html}</div>
    """
    return HTMLResponse(_page(body))


# --------------------------------------------------------------------------- #
# New story page                                                               #
# --------------------------------------------------------------------------- #

@router.get("/photo-story/new", response_class=HTMLResponse)
def new_photo_story_page() -> HTMLResponse:
    body = """
    <div class="card">
        <h1>Yeni Fotoğraf Hikayesi</h1>
        <p class="muted">PhotoSplit veya benzeri bir uygulamayla böldüğün
        fotoğraflar için bir proje oluştur. Her panele ses efekti ekleyip
        video olarak render edebilirsin.</p>

        <label for="title">Proje Başlığı</label>
        <input id="title" placeholder="Örnek: Antik Roma — Çizgi Fotoğraf" required maxlength="120">

        <div class="row">
            <div>
                <label for="panel_count">Panel Sayısı</label>
                <input id="panel_count" type="number" value="15" min="2" max="100">
                <div class="hint">3×5 grid = 15 panel</div>
            </div>
            <div>
                <label for="panel_duration">Her Panel Süresi (sn)</label>
                <input id="panel_duration" type="number" value="5" min="1" max="60">
            </div>
        </div>

        <label for="transition">Sahne Geçişi</label>
        <select id="transition">
            <option value="crossfade" selected>Yavaş Geçiş (Crossfade)</option>
            <option value="fade_black">Karartarak Geçiş</option>
            <option value="cut">Sert Kesim</option>
        </select>

        <button type="button" onclick="createStory()" id="createBtn">
            🎞 Hikaye Oluştur
        </button>
        <div id="msg" style="display:none" class="status-box"></div>
    </div>

    <script>
    async function createStory() {
        const title = document.getElementById('title').value.trim();
        if (!title) { alert('Başlık gerekli.'); return; }
        const btn = document.getElementById('createBtn');
        btn.disabled = true;
        btn.textContent = 'Oluşturuluyor...';
        const resp = await fetch('/api/photo-story/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                title,
                panel_count: parseInt(document.getElementById('panel_count').value) || 15,
                panel_duration: parseFloat(document.getElementById('panel_duration').value) || 5,
                transition: document.getElementById('transition').value,
            }),
        });
        const data = await resp.json();
        if (data.slug) {
            window.location.href = '/photo-story/' + data.slug;
        } else {
            const msg = document.getElementById('msg');
            msg.style.display = 'block';
            msg.className = 'status-box err';
            msg.textContent = data.detail || 'Hata oluştu.';
            btn.disabled = false;
            btn.textContent = '🎞 Hikaye Oluştur';
        }
    }
    </script>
    """
    return HTMLResponse(_page(body))


# --------------------------------------------------------------------------- #
# Create (API)                                                                 #
# --------------------------------------------------------------------------- #

class CreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    panel_count: int = Field(default=15, ge=2, le=100)
    panel_duration: float = Field(default=5.0, ge=1.0, le=60.0)
    transition: str = Field(default="crossfade")


@router.post("/api/photo-story/create")
def create_photo_story(req: CreateRequest) -> dict:
    PHOTO_STORIES_ROOT.mkdir(parents=True, exist_ok=True)

    base_slug = _slug_from_title(req.title)
    slug = base_slug
    i = 1
    while (PHOTO_STORIES_ROOT / slug).exists():
        slug = f"{base_slug}-{i}"
        i += 1

    project_dir = PHOTO_STORIES_ROOT / slug
    project_dir.mkdir(parents=True)
    (project_dir / "panels").mkdir()
    (project_dir / "sfx").mkdir()

    config: dict[str, Any] = {
        "title": req.title,
        "slug": slug,
        "panel_count": req.panel_count,
        "panel_duration": req.panel_duration,
        "transition": req.transition,
        "slots": {
            str(i): {"panel_file": None, "sfx_keyword": "", "sfx_file": None,
                     "sfx_track_name": "", "duration": None}
            for i in range(1, req.panel_count + 1)
        },
    }
    _save_config(project_dir, config)

    return {"slug": slug}


# --------------------------------------------------------------------------- #
# Project detail page                                                          #
# --------------------------------------------------------------------------- #

def _render_slot(slug: str, num: int, slot: dict[str, Any],
                 project_dir: Path) -> str:
    n = num
    panel_file = slot.get("panel_file")
    sfx_keyword = html.escape(str(slot.get("sfx_keyword") or ""), quote=True)
    sfx_file = slot.get("sfx_file")
    sfx_track = html.escape(str(slot.get("sfx_track_name") or ""))
    slot_dur = slot.get("duration")

    if panel_file and (project_dir / panel_file).exists():
        img_html = (
            f'<img class="slot-img" '
            f'src="/photo-story-files/{slug}/{panel_file}" '
            f'onerror="this.src=\'\'">'
        )
    else:
        img_html = '<div class="slot-img empty">📷</div>'

    sfx_label = (
        f'<div class="sfx-status">🔊 {sfx_track}</div>'
        if sfx_file and (project_dir / sfx_file).exists()
        else '<div class="sfx-status" id="sfxStatus_{n}"></div>'.replace("{n}", str(n))
    )

    return f"""
    <div class="slot" id="slot_{n}">
        <div class="slot-num">Panel {n}</div>
        {img_html}

        <label style="font-size:12px;display:flex;align-items:center;
            justify-content:center;min-height:30px;border:1px solid #cbd6e5;
            border-radius:8px;cursor:pointer;background:#f4f8ff;
            font-weight:700;margin-top:8px;text-align:center;padding:4px 8px">
            ⬆ Görsel Yükle
            <input type="file" accept="image/*" style="display:none"
                onchange="uploadPanel({n}, this)">
        </label>

        <label style="font-size:12px;margin-top:8px;margin-bottom:2px;font-weight:700">
            Ses Efekti Kelimesi
        </label>
        <input type="text" id="sfxKw_{n}" value="{sfx_keyword}"
            placeholder="örn: whoosh, explosion, birds"
            style="font-size:12px;min-height:34px"
            onblur="saveSfxKeyword({n})">
        <button onclick="fetchSfx({n})" style="margin-top:6px;background:#059669">
            🔊 Ses Ara &amp; İndir
        </button>
        {sfx_label}
        <button class="sm danger" onclick="removeSfx({n})" style="display:{'block' if sfx_file else 'none'};margin-top:4px" id="rmSfx_{n}">
            ✕ Sesi Kaldır
        </button>
    </div>
    """


@router.get("/photo-story/{slug}", response_class=HTMLResponse)
def photo_story_detail(slug: str) -> HTMLResponse:
    project_dir = _safe_project_dir(slug)
    config = _load_config(project_dir)
    if not config:
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")

    title = html.escape(str(config.get("title") or slug))
    panel_count = int(config.get("panel_count") or 0)
    transition = str(config.get("transition") or "crossfade")
    panel_duration = float(config.get("panel_duration") or 5.0)
    slots: dict[str, Any] = config.get("slots") or {}

    slots_html = "\n".join(
        _render_slot(slug, n, slots.get(str(n)) or {}, project_dir)
        for n in range(1, panel_count + 1)
    )

    transition_opts = "\n".join(
        f'<option value="{v}" {"selected" if v == transition else ""}>{l}</option>'
        for v, l in TRANSITION_OPTIONS
    )

    has_video = (project_dir / "render" / "photo_story.mp4").exists()
    download_btn = (
        f'<a href="/photo-story/{slug}/download" style="display:inline-flex;'
        f'align-items:center;min-height:40px;padding:0 16px;background:#059669;'
        f'color:white;text-decoration:none;border-radius:10px;font-weight:700;'
        f'font-size:13px;margin-top:10px">⬇ Videoyu İndir</a>'
        if has_video else ""
    )

    body = f"""
    <div class="card">
        <h1>{title}</h1>
        <div class="muted" style="margin-bottom:10px">{slug} · {panel_count} panel</div>

        <div class="row3">
            <div>
                <label>Geçiş Efekti</label>
                <select id="globalTransition" onchange="saveGlobal()">
                    {transition_opts}
                </select>
            </div>
            <div>
                <label>Panel Süresi (sn)</label>
                <input id="globalDuration" type="number" value="{panel_duration}"
                    min="1" max="60" step="0.5" onblur="saveGlobal()">
            </div>
            <div style="display:flex;flex-direction:column;justify-content:flex-end">
                <button onclick="fetchAllSfx()" class="secondary sm"
                    style="width:100%;min-height:40px;margin-top:0">
                    🔊 Tüm SFX'leri İndir
                </button>
            </div>
        </div>

        <button onclick="startRender()" id="renderBtn" style="margin-top:14px">
            🎬 Video Oluştur
        </button>
        <div id="renderStatus" style="display:none" class="status-box"></div>
        {download_btn}
    </div>

    <div class="card" id="splitCard">
        <h3>✂️ Izgara Böl</h3>
        <p class="muted" style="margin-top:0">
            Fotoğrafı yükle, mavi/turuncu çizgileri parmakla panel sınırına sürükle, sonra <b>Kırp</b>.
        </p>
        <div class="row" style="margin-bottom:10px">
            <div>
                <label>Satır</label>
                <input id="gridRows" type="number" value="5" min="1" max="20"
                    onchange="updateLines()">
                <div class="hint">Dikey → 5</div>
            </div>
            <div>
                <label>Sütun</label>
                <input id="gridCols" type="number" value="3" min="1" max="20"
                    onchange="updateLines()">
                <div class="hint">Dikey → 3</div>
            </div>
        </div>
        <label style="display:flex;align-items:center;justify-content:center;
            min-height:44px;border:2px dashed #2166f3;border-radius:12px;
            cursor:pointer;background:#f4f8ff;font-weight:700;color:#2166f3">
            📤 Izgara Fotoğrafını Seç
            <input id="gridFileInput" type="file" accept="image/*" style="display:none"
                onchange="loadGrid(this.files[0])">
        </label>
        <div id="splitStatus" style="display:none;margin-top:10px" class="status-box"></div>

        <div id="cropArea" style="display:none;margin-top:14px">
            <div id="cropCanvas" style="position:relative;overflow:hidden;
                user-select:none;border-radius:8px;border:1px solid #dbe5f4">
                <img id="cropImg" style="width:100%;display:block">
            </div>
            <div class="hint" style="margin-top:6px;text-align:center;font-size:11px">
                🔵 Mavi = satır sınırı &nbsp;|&nbsp; 🟠 Turuncu = sütun sınırı — parmakla sürükle
            </div>
            <div style="display:flex;gap:8px;margin-top:10px">
                <button type="button" class="secondary" id="reverseBtn"
                    onclick="toggleCropReverse()" style="flex:1;margin-top:0">
                    ↕ Sırayı Ters Çevir
                </button>
                <button type="button" onclick="confirmCrop()" style="flex:2;margin-top:0">
                    ✂️ Kırp &amp; Kaydet
                </button>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>📸 Paneller</h3>
        <div class="slot-grid" id="slotGrid">
            {slots_html}
        </div>
    </div>

    <script>
    const SLUG = {json.dumps(slug)};

    async function uploadPanel(num, input) {{
        if (!input.files[0]) return;
        const fd = new FormData();
        fd.append('file', input.files[0]);
        const resp = await fetch(`/api/photo-story/${{SLUG}}/upload-panel/${{num}}`, {{
            method: 'POST', body: fd,
        }});
        const data = await resp.json();
        if (data.ok) {{
            const img = document.querySelector(`#slot_${{num}} .slot-img`);
            if (img) {{
                img.src = data.url + '?t=' + Date.now();
                img.classList.remove('empty');
            }}
        }} else {{
            alert('Yükleme başarısız: ' + (data.detail || '?'));
        }}
    }}

    async function saveSfxKeyword(num) {{
        const kw = document.getElementById('sfxKw_' + num)?.value || '';
        await fetch(`/api/photo-story/${{SLUG}}/slot/${{num}}`, {{
            method: 'PATCH',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{sfx_keyword: kw}}),
        }});
    }}

    async function saveGlobal() {{
        const transition = document.getElementById('globalTransition').value;
        const duration = parseFloat(document.getElementById('globalDuration').value);
        await fetch(`/api/photo-story/${{SLUG}}/settings`, {{
            method: 'PATCH',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{transition, panel_duration: duration}}),
        }});
    }}

    async function fetchSfx(num) {{
        const kw = document.getElementById('sfxKw_' + num)?.value?.trim();
        if (!kw) {{ alert('Önce anahtar kelime gir.'); return; }}
        const statusEl = document.getElementById('sfxStatus_' + num)
            || document.querySelector(`#slot_${{num}} .sfx-status`);
        if (statusEl) {{ statusEl.textContent = '⏳ Aranıyor...'; statusEl.className = 'sfx-status'; }}
        const resp = await fetch(`/api/photo-story/${{SLUG}}/fetch-sfx/${{num}}`, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{sfx_keyword: kw}}),
        }});
        const data = await resp.json();
        if (statusEl) {{
            if (data.ok) {{
                statusEl.textContent = '🔊 ' + (data.track_name || 'İndirildi');
                statusEl.className = 'sfx-status';
                const rmBtn = document.getElementById('rmSfx_' + num);
                if (rmBtn) rmBtn.style.display = 'block';
            }} else {{
                statusEl.textContent = '❌ ' + (data.detail || 'Bulunamadı');
                statusEl.className = 'sfx-status err';
            }}
        }}
    }}

    async function removeSfx(num) {{
        await fetch(`/api/photo-story/${{SLUG}}/slot/${{num}}`, {{
            method: 'PATCH',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{clear_sfx: true}}),
        }});
        const statusEl = document.querySelector(`#slot_${{num}} .sfx-status`);
        if (statusEl) {{ statusEl.textContent = ''; }}
        const rmBtn = document.getElementById('rmSfx_' + num);
        if (rmBtn) rmBtn.style.display = 'none';
    }}

    async function fetchAllSfx() {{
        const total = {panel_count};
        for (let i = 1; i <= total; i++) {{
            const kw = document.getElementById('sfxKw_' + i)?.value?.trim();
            if (kw) await fetchSfx(i);
        }}
        alert('Tüm SFX indirme işlemleri tamamlandı.');
    }}

    async function startRender() {{
        const btn = document.getElementById('renderBtn');
        const box = document.getElementById('renderStatus');
        btn.disabled = true;
        btn.textContent = '⏳ Render başlatılıyor...';
        box.style.display = 'block';
        box.className = 'status-box';
        box.textContent = 'Video oluşturma kuyruğa alındı...';

        const resp = await fetch(`/api/photo-story/${{SLUG}}/render`, {{method: 'POST'}});
        const data = await resp.json();
        if (!data.job_id) {{
            box.className = 'status-box err';
            box.textContent = data.detail || 'Render başlatılamadı.';
            btn.disabled = false;
            btn.textContent = '🎬 Video Oluştur';
            return;
        }}

        pollRender(data.job_id);
    }}

    // --- Manuel kırpma ---
    let _hFracs = [];
    let _vFracs = [];
    let _cropReversed = false;

    function updateLines() {{
        if (document.getElementById('cropArea').style.display === 'none') return;
        const rows = parseInt(document.getElementById('gridRows').value) || 5;
        const cols = parseInt(document.getElementById('gridCols').value) || 3;
        _hFracs = Array.from({{length: rows - 1}}, (_, i) => (i + 1) / rows);
        _vFracs = Array.from({{length: cols - 1}}, (_, i) => (i + 1) / cols);
        renderCropLines();
    }}

    function toggleCropReverse() {{
        _cropReversed = !_cropReversed;
        const btn = document.getElementById('reverseBtn');
        btn.style.background = _cropReversed ? '#2166f3' : '';
        btn.style.color = _cropReversed ? 'white' : '';
        btn.style.border = _cropReversed ? 'none' : '';
    }}

    async function loadGrid(file) {{
        if (!file) return;
        const st = document.getElementById('splitStatus');
        st.style.display = 'block';
        st.className = 'status-box';
        st.textContent = '⏳ Yükleniyor...';

        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch(`/api/photo-story/${{SLUG}}/upload-grid`, {{method: 'POST', body: fd}});
        const data = await resp.json();
        if (!resp.ok) {{
            st.className = 'status-box err';
            st.textContent = data.detail || 'Yükleme hatası';
            return;
        }}
        st.style.display = 'none';

        const img = document.getElementById('cropImg');
        img.src = data.url + '?t=' + Date.now();
        img.onload = () => {{
            const rows = parseInt(document.getElementById('gridRows').value) || 5;
            const cols = parseInt(document.getElementById('gridCols').value) || 3;
            _hFracs = Array.from({{length: rows - 1}}, (_, i) => (i + 1) / rows);
            _vFracs = Array.from({{length: cols - 1}}, (_, i) => (i + 1) / cols);
            document.getElementById('cropArea').style.display = 'block';
            renderCropLines();
        }};
    }}

    function renderCropLines() {{
        const canvas = document.getElementById('cropCanvas');
        canvas.querySelectorAll('.crop-line').forEach(e => e.remove());

        _hFracs.forEach((frac, idx) => {{
            const el = document.createElement('div');
            el.className = 'crop-line';
            el.style.cssText = `position:absolute;left:0;right:0;height:4px;
                background:rgba(33,102,243,0.9);top:${{frac * 100}}%;
                cursor:ns-resize;touch-action:none;z-index:20;
                box-shadow:0 0 0 1px rgba(255,255,255,.6)`;
            el.innerHTML = `<span style="position:absolute;left:4px;top:-10px;
                background:#2166f3;color:#fff;font-size:9px;font-weight:900;
                padding:0 5px;border-radius:3px;line-height:18px;pointer-events:none">
                H${{idx + 1}}</span>`;
            makeDraggable(el, 'h', idx);
            canvas.appendChild(el);
        }});

        _vFracs.forEach((frac, idx) => {{
            const el = document.createElement('div');
            el.className = 'crop-line';
            el.style.cssText = `position:absolute;top:0;bottom:0;width:4px;
                background:rgba(220,80,10,0.9);left:${{frac * 100}}%;
                cursor:ew-resize;touch-action:none;z-index:20;
                box-shadow:0 0 0 1px rgba(255,255,255,.6)`;
            el.innerHTML = `<span style="position:absolute;top:4px;left:-10px;
                background:#dc500a;color:#fff;font-size:9px;font-weight:900;
                padding:0 5px;border-radius:3px;line-height:18px;pointer-events:none">
                V${{idx + 1}}</span>`;
            makeDraggable(el, 'v', idx);
            canvas.appendChild(el);
        }});
    }}

    function makeDraggable(el, axis, idx) {{
        el.addEventListener('pointerdown', e => {{
            e.preventDefault();
            el.setPointerCapture(e.pointerId);
            const canvas = document.getElementById('cropCanvas');

            const onMove = ev => {{
                const rect = canvas.getBoundingClientRect();
                if (axis === 'h') {{
                    const f = Math.max(0.01, Math.min(0.99,
                        (ev.clientY - rect.top) / rect.height));
                    _hFracs[idx] = f;
                    el.style.top = (f * 100) + '%';
                }} else {{
                    const f = Math.max(0.01, Math.min(0.99,
                        (ev.clientX - rect.left) / rect.width));
                    _vFracs[idx] = f;
                    el.style.left = (f * 100) + '%';
                }}
            }};
            const onUp = () => {{
                el.removeEventListener('pointermove', onMove);
                el.removeEventListener('pointerup', onUp);
            }};
            el.addEventListener('pointermove', onMove);
            el.addEventListener('pointerup', onUp);
        }});
    }}

    async function confirmCrop() {{
        const st = document.getElementById('splitStatus');
        st.style.display = 'block';
        st.className = 'status-box';
        st.textContent = '✂️ Kırpılıyor, kaydediliyor...';

        const params = new URLSearchParams({{
            h_fracs: _hFracs.join(','),
            v_fracs: _vFracs.join(','),
            reversed: _cropReversed ? '1' : '0',
        }});
        const resp = await fetch(
            `/api/photo-story/${{SLUG}}/confirm-split?${{params}}`,
            {{method: 'POST'}}
        );
        const data = await resp.json();
        if (data.ok) {{
            st.className = 'status-box ok';
            st.textContent = `✅ ${{data.saved}} panel kaydedildi! Sayfa yenileniyor...`;
            setTimeout(() => location.reload(), 1200);
        }} else {{
            st.className = 'status-box err';
            st.textContent = '❌ ' + (data.detail || 'Hata oluştu');
        }}
    }}

    function pollRender(jobId) {{
        const btn = document.getElementById('renderBtn');
        const box = document.getElementById('renderStatus');

        const iv = setInterval(async () => {{
            const resp = await fetch(`/api/photo-story/${{SLUG}}/status/${{jobId}}`);
            const data = await resp.json();
            const status = data.status;

            if (status === 'running') {{
                box.textContent = '⏳ Video hazırlanıyor...';
            }} else if (status === 'completed') {{
                clearInterval(iv);
                box.className = 'status-box ok';
                box.innerHTML = '✅ Video hazır! <a href="/photo-story/' + SLUG + '/download"'
                    + ' style="color:inherit;font-weight:700;margin-left:8px">⬇ İndir</a>';
                btn.textContent = '🎬 Yeniden Oluştur';
                btn.disabled = false;
            }} else if (status === 'failed') {{
                clearInterval(iv);
                box.className = 'status-box err';
                box.textContent = '❌ Hata: ' + (data.error || '?');
                btn.disabled = false;
                btn.textContent = '🎬 Video Oluştur';
            }}
        }}, 2000);
    }}
    </script>
    """
    return HTMLResponse(_page(body))


# --------------------------------------------------------------------------- #
# File serving                                                                 #
# --------------------------------------------------------------------------- #

@router.get("/photo-story-files/{slug}/{rest:path}")
def serve_photo_story_file(slug: str, rest: str) -> FileResponse:
    project_dir = _safe_project_dir(slug)
    file_path = (project_dir / rest).resolve()

    if project_dir.resolve() not in file_path.parents and file_path != project_dir.resolve():
        raise HTTPException(status_code=403)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404)

    return FileResponse(
        file_path,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/photo-story/{slug}/download")
def download_video(slug: str) -> FileResponse:
    project_dir = _safe_project_dir(slug)
    video_path = project_dir / "render" / "photo_story.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video henüz hazır değil.")

    config = _load_config(project_dir)
    title = str(config.get("title") or slug)
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:60]

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{safe_title}.mp4",
    )


# --------------------------------------------------------------------------- #
# API — panel upload                                                           #
# --------------------------------------------------------------------------- #

@router.post("/api/photo-story/{slug}/upload-panel/{num}")
async def upload_panel(slug: str, num: int, file: UploadFile) -> dict:
    project_dir = _safe_project_dir(slug)
    config = _load_config(project_dir)
    slots: dict[str, Any] = config.get("slots") or {}

    if str(num) not in slots:
        raise HTTPException(status_code=400, detail="Geçersiz panel numarası.")

    ext = Path(file.filename or "panel.jpg").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"

    panels_dir = project_dir / "panels"
    panels_dir.mkdir(exist_ok=True)
    dest = panels_dir / f"panel_{num:03d}{ext}"

    content = await file.read()
    dest.write_bytes(content)

    rel = f"panels/panel_{num:03d}{ext}"
    slots[str(num)]["panel_file"] = rel
    config["slots"] = slots
    _save_config(project_dir, config)

    return {"ok": True, "url": f"/photo-story-files/{slug}/{rel}"}


# --------------------------------------------------------------------------- #
# API — grid split: preview + confirm                                          #
# --------------------------------------------------------------------------- #

def _find_band_ranges(
    line_means: list[float],
    threshold: float = 240.0,
) -> list[tuple[int, int]]:
    """Return (start, end) pixel ranges for every white band in *line_means*.

    A white band is a contiguous run of values >= *threshold*.
    """
    ranges: list[tuple[int, int]] = []
    in_band = False
    band_start = 0
    for i, b in enumerate(line_means):
        if b >= threshold and not in_band:
            band_start = i
            in_band = True
        elif b < threshold and in_band:
            ranges.append((band_start, i))
            in_band = False
    if in_band:
        ranges.append((band_start, len(line_means)))
    return ranges


def _band_ranges_to_regions(
    band_ranges: list[tuple[int, int]],
    total: int,
    expected_seps: int,
) -> list[tuple[int, int]]:
    """Convert separator band ranges into content-region (start, end) pairs.

    Content starts where the previous separator *ends* and stops where the
    next separator *starts* — so no separator pixel ever ends up inside a cell.
    Falls back to even division when the detected band count is wrong.
    """
    n = expected_seps + 1
    if len(band_ranges) != expected_seps:
        # Fallback: even grid
        return [(round(i * total / n), round((i + 1) * total / n)) for i in range(n)]

    regions: list[tuple[int, int]] = []
    prev_end = 0
    for sep_start, sep_end in band_ranges:
        regions.append((prev_end, sep_start))
        prev_end = sep_end
    regions.append((prev_end, total))
    return regions


def _trim_white(cell: "Image.Image", threshold: float = 250.0) -> "Image.Image":
    """Trim any remaining near-pure-white padding from cell edges."""
    import numpy as np
    gray = np.array(cell.convert("L"), dtype=float)
    row_bright = gray.mean(axis=1)
    col_bright = gray.mean(axis=0)
    rows_ok = (row_bright < threshold).nonzero()[0]
    cols_ok = (col_bright < threshold).nonzero()[0]
    if rows_ok.size < 4 or cols_ok.size < 4:
        return cell
    return cell.crop((int(cols_ok[0]), int(rows_ok[0]),
                      int(cols_ok[-1]) + 1, int(rows_ok[-1]) + 1))


def _crop_cells(
    img: "Image.Image",
    rows: int,
    cols: int,
    swap_axes: bool,
    reverse_order: bool,
) -> list["Image.Image"]:
    """Divide img into rows×cols cells using white-border detection.

    Finds each white separator band and cuts exactly at its edges so that
    no separator pixel is included in any panel.  Falls back to even grid
    division when detection finds the wrong number of bands.
    """
    import numpy as np

    r, c = (cols, rows) if swap_axes else (rows, cols)

    gray = np.array(img.convert("L"), dtype=float)   # h × w

    h_bands = _find_band_ranges(gray.mean(axis=1).tolist())
    v_bands = _find_band_ranges(gray.mean(axis=0).tolist())

    h_regions = _band_ranges_to_regions(h_bands, img.height, r - 1)
    v_regions = _band_ranges_to_regions(v_bands, img.width,  c - 1)

    cells: list["Image.Image"] = []
    for ri in range(r):
        y0, y1 = h_regions[ri]
        for ci in range(c):
            x0, x1 = v_regions[ci]
            cells.append(_trim_white(img.crop((x0, y0, x1, y1))))

    if reverse_order:
        cells.reverse()

    return cells


@router.post("/api/photo-story/{slug}/upload-grid")
async def upload_grid(slug: str, file: UploadFile) -> dict:
    """Save the raw grid image so the user can draw crop lines on it."""
    project_dir = _safe_project_dir(slug)
    raw = await file.read()
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Görsel açılamadı: {exc}")
    grid_path = project_dir / "preview_grid.jpg"
    img.save(grid_path, "JPEG", quality=95)
    return {
        "url": f"/photo-story-files/{slug}/preview_grid.jpg",
        "width": img.width,
        "height": img.height,
    }


@router.post("/api/photo-story/{slug}/confirm-split")
def confirm_split(
    slug: str,
    h_fracs: str = "",
    v_fracs: str = "",
    reversed: int = 0,
    inset: int = 5,
) -> dict:
    """Crop the stored grid image at the given line positions and save panels.

    inset — pixels to trim from all 4 edges of every panel after cutting,
            removing any separator bleed or JPEG edge artefacts.
    """

    project_dir = _safe_project_dir(slug)
    grid_path = project_dir / "preview_grid.jpg"
    if not grid_path.exists():
        raise HTTPException(status_code=400, detail="Önce ızgara fotoğrafı yükle.")

    try:
        img = Image.open(grid_path).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Görsel açılamadı: {exc}")

    W, H = img.size

    def _parse_cuts(s: str, total: int) -> list[int]:
        pts = []
        for tok in s.split(","):
            tok = tok.strip()
            if tok:
                try:
                    pts.append(int(float(tok) * total))
                except ValueError:
                    pass
        return sorted(pts)

    h_cuts = [0] + _parse_cuts(h_fracs, H) + [H]
    v_cuts = [0] + _parse_cuts(v_fracs, W) + [W]

    panels_dir = project_dir / "panels"
    panels_dir.mkdir(exist_ok=True)

    pad = max(0, inset)
    cells: list[tuple[int, int, int, int]] = []
    for ri in range(len(h_cuts) - 1):
        for ci in range(len(v_cuts) - 1):
            x0, y0 = v_cuts[ci] + pad, h_cuts[ri] + pad
            x1, y1 = v_cuts[ci + 1] - pad, h_cuts[ri + 1] - pad
            cells.append((x0, y0, x1, y1))

    if reversed:
        cells.reverse()

    config = _load_config(project_dir)
    slots: dict[str, Any] = config.get("slots") or {}
    saved = 0

    for i, box in enumerate(cells, start=1):
        cell = img.crop(box)
        dest = panels_dir / f"panel_{i:03d}.jpg"
        cell.save(dest, "JPEG", quality=92)
        slot = slots.setdefault(str(i), {})
        slot["panel_file"] = f"panels/panel_{i:03d}.jpg"
        slot.setdefault("sfx_keyword", "")
        slot.setdefault("sfx_file", None)
        slot.setdefault("sfx_track_name", "")
        slot.setdefault("duration", None)
        saved += 1

    config["panel_count"] = saved
    config["slots"] = slots
    _save_config(project_dir, config)

    return {"ok": True, "saved": saved}


# --------------------------------------------------------------------------- #
# API — slot settings                                                          #
# --------------------------------------------------------------------------- #

class SlotPatch(BaseModel):
    sfx_keyword: str | None = None
    duration: float | None = None
    clear_sfx: bool = False


@router.patch("/api/photo-story/{slug}/slot/{num}")
def patch_slot(slug: str, num: int, req: SlotPatch) -> dict:
    project_dir = _safe_project_dir(slug)
    config = _load_config(project_dir)
    slots: dict[str, Any] = config.get("slots") or {}
    slot = slots.setdefault(str(num), {})

    if req.sfx_keyword is not None:
        slot["sfx_keyword"] = req.sfx_keyword
    if req.duration is not None:
        slot["duration"] = req.duration
    if req.clear_sfx:
        sfx_rel = slot.get("sfx_file")
        if sfx_rel:
            sfx_path = project_dir / sfx_rel
            sfx_path.unlink(missing_ok=True)
        slot["sfx_file"] = None
        slot["sfx_track_name"] = ""

    config["slots"] = slots
    _save_config(project_dir, config)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# API — global settings                                                        #
# --------------------------------------------------------------------------- #

class GlobalSettings(BaseModel):
    transition: str | None = None
    panel_duration: float | None = None


@router.patch("/api/photo-story/{slug}/settings")
def patch_settings(slug: str, req: GlobalSettings) -> dict:
    project_dir = _safe_project_dir(slug)
    config = _load_config(project_dir)

    if req.transition is not None:
        config["transition"] = req.transition
    if req.panel_duration is not None:
        config["panel_duration"] = req.panel_duration

    _save_config(project_dir, config)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# API — SFX fetch                                                              #
# --------------------------------------------------------------------------- #

class SfxRequest(BaseModel):
    sfx_keyword: str


@router.post("/api/photo-story/{slug}/fetch-sfx/{num}")
def fetch_sfx(slug: str, num: int, req: SfxRequest) -> dict:
    project_dir = _safe_project_dir(slug)
    config = _load_config(project_dir)
    slots: dict[str, Any] = config.get("slots") or {}

    keyword = req.sfx_keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Anahtar kelime gerekli.")

    sfx_dir = project_dir / "sfx"
    sfx_dir.mkdir(exist_ok=True)
    sfx_path = sfx_dir / f"sfx_{num:03d}.mp3"

    svc = PhotoStoryService()
    meta = svc.search_sfx(keyword, sfx_path)

    if meta is None:
        raise HTTPException(
            status_code=502,
            detail="Freesound'dan ses bulunamadı. Farklı bir anahtar kelime dene veya Freesound API anahtarını kontrol et.",
        )

    slot = slots.setdefault(str(num), {})
    slot["sfx_keyword"] = keyword
    slot["sfx_file"] = f"sfx/sfx_{num:03d}.mp3"
    slot["sfx_track_name"] = f"{meta['name']} ({meta['artist']})"
    config["slots"] = slots
    _save_config(project_dir, config)

    return {
        "ok": True,
        "track_name": slot["sfx_track_name"],
        "duration": meta.get("duration"),
    }


# --------------------------------------------------------------------------- #
# API — render                                                                 #
# --------------------------------------------------------------------------- #

def _execute_render(job_id: str, project_dir: Path) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"

    try:
        svc = PhotoStoryService()
        output = svc.render(project_dir)
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "completed",
                "output": str(output),
                "error": None,
            })
    except Exception as exc:
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "failed",
                "error": str(exc),
            })


@router.post("/api/photo-story/{slug}/render")
def start_render(slug: str) -> dict:
    project_dir = _safe_project_dir(slug)
    config = _load_config(project_dir)
    slots: dict[str, Any] = config.get("slots") or {}

    has_panel = any(s.get("panel_file") for s in slots.values())
    if not has_panel:
        raise HTTPException(
            status_code=400,
            detail="En az bir panel yüklemeden render başlatılamaz.",
        )

    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"job_id": job_id, "status": "queued", "error": None}

    thread = threading.Thread(
        target=_execute_render,
        args=(job_id, project_dir),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@router.get("/api/photo-story/{slug}/status/{job_id}")
def get_render_status(slug: str, job_id: str) -> dict:
    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")

    return {
        "status": job["status"],
        "error": job.get("error"),
    }
