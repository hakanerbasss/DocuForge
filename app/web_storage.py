import html
import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

PROJECTS_ROOT = Path("projects")
MODELS_ROOT = Path("models")


def _format_bytes(num_bytes: float) -> str:
    value = float(num_bytes)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return (
                f"{int(value)} {unit}"
                if unit == "B"
                else f"{value:.1f} {unit}"
            )
        value /= 1024

    return f"{value:.1f} TB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0

    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                pass

    return total


def _read_meminfo() -> dict[str, int]:
    """Parse /proc/meminfo (values in kB) -- Linux-only, best effort.
    Returns an empty dict (rather than raising) on any other platform
    or if the file is unreadable, so the page still renders with just
    the disk section.
    """

    result: dict[str, int] = {}

    try:
        raw = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return result

    for line in raw.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.strip().split()

        if not parts:
            continue

        try:
            result[key] = int(parts[0]) * 1024
        except ValueError:
            continue

    return result


def _project_title(project_dir: Path) -> str:
    project_json = project_dir / "project.json"

    if project_json.exists():
        try:
            data = json.loads(project_json.read_text(encoding="utf-8"))
            title = str(data.get("title") or "").strip()

            if title:
                return title
        except (OSError, json.JSONDecodeError):
            pass

    return project_dir.name


def _list_projects_by_size() -> list[tuple[str, str, int]]:
    if not PROJECTS_ROOT.exists():
        return []

    projects = [
        (project_dir.name, _project_title(project_dir), _dir_size(project_dir))
        for project_dir in sorted(PROJECTS_ROOT.iterdir())
        if project_dir.is_dir()
    ]

    projects.sort(key=lambda item: item[2], reverse=True)

    return projects


def _usage_bar(used_fraction: float, color: str) -> str:
    pct = max(0.0, min(100.0, used_fraction * 100))
    danger = pct >= 90

    bar_color = "#d92626" if danger else color

    return f"""
    <div style="background:#eef3fb;border-radius:999px;height:10px;overflow:hidden;margin-top:8px">
        <div style="width:{pct:.1f}%;height:100%;background:{bar_color};border-radius:999px"></div>
    </div>
    """


@router.get("/storage", response_class=HTMLResponse)
def storage_page() -> HTMLResponse:
    disk_root = PROJECTS_ROOT if PROJECTS_ROOT.exists() else Path(".")
    disk_total, disk_used, disk_free = shutil.disk_usage(disk_root)

    mem = _read_meminfo()
    mem_total = mem.get("MemTotal", 0)
    mem_available = mem.get("MemAvailable", 0)
    mem_used = max(0, mem_total - mem_available)

    projects = _list_projects_by_size()
    projects_total = sum(size for _, _, size in projects)
    models_size = _dir_size(MODELS_ROOT)

    disk_fraction = (disk_used / disk_total) if disk_total else 0.0
    mem_fraction = (mem_used / mem_total) if mem_total else 0.0

    disk_section = f"""
    <div style="padding:16px 0;border-bottom:1px solid #edf1f6">
        <div style="display:flex;justify-content:space-between;font-weight:700">
            <span>💾 Disk</span>
            <span class="muted" style="font-weight:400">
                {_format_bytes(disk_used)} / {_format_bytes(disk_total)}
                ({_format_bytes(disk_free)} boş)
            </span>
        </div>
        {_usage_bar(disk_fraction, "#2166f3")}
    </div>
    """

    if mem_total:
        memory_section = f"""
        <div style="padding:16px 0;border-bottom:1px solid #edf1f6">
            <div style="display:flex;justify-content:space-between;font-weight:700">
                <span>🧠 Bellek (RAM)</span>
                <span class="muted" style="font-weight:400">
                    {_format_bytes(mem_used)} / {_format_bytes(mem_total)}
                </span>
            </div>
            {_usage_bar(mem_fraction, "#08763a")}
        </div>
        """
    else:
        memory_section = """
        <div style="padding:16px 0;border-bottom:1px solid #edf1f6">
            <div style="font-weight:700">🧠 Bellek (RAM)</div>
            <div class="muted" style="font-size:13px">Okunamadı (Linux dışı ortam olabilir).</div>
        </div>
        """

    if projects:
        project_rows = "".join(
            f"""
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid #edf1f6">
                <div style="min-width:0">
                    <a href="/projects/{html.escape(slug)}" style="font-weight:700;color:#152033;text-decoration:none;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                        {html.escape(title)}
                    </a>
                    <span class="muted" style="font-size:12px">{_format_bytes(size)}</span>
                </div>
                <button class="button secondary" style="min-height:34px;padding:0 12px;font-size:13px;white-space:nowrap"
                    onclick="deleteProjectFromStorage('{html.escape(slug)}', this)">
                    🗑 Sil
                </button>
            </div>
            """
            for slug, title, size in projects
        )
    else:
        project_rows = '<p class="muted">Henüz proje yok.</p>'

    projects_section = f"""
    <div style="padding-top:6px">
        <div style="display:flex;justify-content:space-between;align-items:baseline">
            <h2 style="margin:0;font-size:18px">Projeler</h2>
            <span class="muted" style="font-size:13px">Toplam {_format_bytes(projects_total)}</span>
        </div>
        <div style="margin-top:8px">
            {project_rows}
        </div>
    </div>
    """

    models_section = f"""
    <div style="padding:16px 0;border-bottom:1px solid #edf1f6">
        <div style="display:flex;justify-content:space-between">
            <span class="muted">📦 Modeller (sesler, kapanış görseli vb.)</span>
            <span class="muted">{_format_bytes(models_size)}</span>
        </div>
    </div>
    """

    return HTMLResponse(f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Depolama · DocuForge</title>
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#2166f3">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="DocuForge">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
<style>
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;background:#f4f7fb;color:#152033;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{padding:22px 18px;background:linear-gradient(135deg,#ffffff,#eaf2ff);border-bottom:1px solid #dfe7f3}}
header div,main{{width:min(760px,calc(100% - 28px));margin:auto}}
main{{padding:28px 0 70px}}
.back{{color:#245ec7;text-decoration:none;font-weight:700}}
.card{{margin-top:18px;padding:24px;background:white;border:1px solid #e0e7f1;border-radius:22px;box-shadow:0 12px 35px rgba(34,54,80,.08)}}
h1{{margin:0 0 8px;font-size:clamp(26px,6vw,38px)}}
.muted{{color:#64748b}}
.button{{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 15px;border-radius:12px;background:#2166f3;color:white;text-decoration:none;font-weight:750;border:0;cursor:pointer;font:inherit}}
.button.secondary{{background:#eef3fb;color:#1e3a62}}
</style>
</head>
<body>
<header><div style="display:flex;align-items:center;justify-content:space-between;gap:16px">
<a class="back" href="/">← Projelere dön</a>
<a class="button secondary" href="/voice-test" style="min-height:34px;padding:0 12px;font-size:13px">🎤 Ses Testi</a>
<a class="button secondary" href="/settings" style="min-height:34px;padding:0 12px;font-size:13px">⚙ Ayarlar</a>
</div></header>
<main>
<section class="card">
<h1>Depolama</h1>
<p class="muted">Sunucudaki disk ve bellek durumu, proje başına ne kadar yer kaplandığı ve istersen buradan silme.</p>
</section>
<section class="card">
{disk_section}
{memory_section}
{models_section}
</section>
<section class="card">
{projects_section}
</section>
</main>
<script>
async function deleteProjectFromStorage(slug, btn) {{
    if (!confirm("Bu projeyi ve tüm dosyalarını (video, ses, görseller) kalıcı olarak silmek istediğine emin misin?")) return;
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "⏳...";
    try {{
        const r = await fetch(`/api/projects/${{slug}}`, {{method: "DELETE"}});
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Silinemedi.");
        }}
        location.reload();
    }} catch (e) {{
        alert("Hata: " + e.message);
        btn.disabled = false;
        btn.textContent = original;
    }}
}}
</script>
<script>
if ("serviceWorker" in navigator) {{
    navigator.serviceWorker.register("/static/sw.js").catch(() => {{}});
}}
</script>
</body>
</html>""")
