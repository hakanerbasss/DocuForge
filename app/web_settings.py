import html

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings


router = APIRouter()

# field_key -> (label, env var name, description, input type, placeholder)
FIELD_LABELS: dict[str, tuple[str, str, str, str, str]] = {
    "deepseek_api_key": (
        "DeepSeek API Key",
        "DEEPSEEK_API_KEY",
        "Metin üretimi için zorunlu (research, script, storyboard, narration, SEO).",
        "password",
        "sk-...",
    ),
    "pexels_api_key": (
        "Pexels API Key",
        "PEXELS_API_KEY",
        "Ücretsiz stok görsel/video arama.",
        "password",
        "...",
    ),
    "pixabay_api_key": (
        "Pixabay API Key",
        "PIXABAY_API_KEY",
        "Ücretsiz stok görsel/video arama.",
        "password",
        "...",
    ),
    "unsplash_access_key": (
        "Unsplash Access Key",
        "UNSPLASH_ACCESS_KEY",
        "Ücretsiz stok görsel arama.",
        "password",
        "...",
    ),
    "openai_api_key": (
        "OpenAI API Key",
        "OPENAI_API_KEY",
        "DALL-E (gpt-image-1) görsel üretimi için. DeepSeek anahtarından farklıdır.",
        "password",
        "sk-...",
    ),
    "google_api_key": (
        "Google API Key",
        "GOOGLE_API_KEY",
        "Google Imagen (görsel) ve Veo (video) üretimi için.",
        "password",
        "...",
    ),
    "fal_api_key": (
        "fal.ai API Key",
        "FAL_KEY",
        "fal.ai aggregator (Flux, Kling ve yüzlerce model) için.",
        "password",
        "...",
    ),
    "xtts_reference_audio": (
        "XTTS Referans Ses Dosyası",
        "XTTS_REFERENCE_AUDIO",
        "Klon ses için referans ses dosyasının sunucudaki tam yolu (20-30 sn temiz kayıt).",
        "text",
        "/root/projects/DocuForge/models/xtts/reference.wav",
    ),
}


def _render_field(field_key: str) -> str:
    label, env_name, description, input_type, placeholder = FIELD_LABELS[
        field_key
    ]
    configured = settings.is_configured(field_key)

    if configured:
        body = f"""
        <div style="background:#e7f9ee;border:1px solid #b9e6c9;border-radius:10px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px">
            <span style="color:#087a38;font-weight:700">✓ Yapılandırılmış</span>
            <form method="post" action="/settings/{field_key}/clear" style="margin:0">
                <button class="button secondary" type="submit" style="min-height:34px;padding:0 12px;font-size:13px">Değiştir</button>
            </form>
        </div>
        """
    else:
        body = f"""
        <form method="post" action="/settings/{field_key}" style="display:flex;gap:8px">
            <input type="{input_type}" name="value" placeholder="{html.escape(placeholder)}" style="flex:1;min-height:42px;padding:0 12px;border:1px solid #cbd6e5;border-radius:10px;font:inherit" required>
            <button class="button" type="submit" style="white-space:nowrap">Kaydet</button>
        </form>
        """

    return f"""
    <div style="padding:16px 0;border-bottom:1px solid #edf1f6">
        <div style="font-weight:700;margin-bottom:2px">{html.escape(label)}</div>
        <div class="muted" style="font-size:13px;margin-bottom:10px">
            {html.escape(description)}
            (<code>{env_name}</code> ortam değişkeni ayarlıysa her zaman öncelikli olur ve buradan değiştirilemez.)
        </div>
        {body}
    </div>
    """


@router.get("/settings", response_class=HTMLResponse)
def settings_page() -> HTMLResponse:
    fields_html = "".join(
        _render_field(key) for key in FIELD_LABELS
    )

    return HTMLResponse(f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ayarlar · DocuForge</title>
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
code{{background:#eef3fb;padding:1px 5px;border-radius:5px;font-size:12px}}
</style>
</head>
<body>
<header><div style="display:flex;align-items:center;justify-content:space-between;gap:16px">
<a class="back" href="/">← Projelere dön</a>
</div></header>
<main>
<section class="card">
<h1>Ayarlar</h1>
<p class="muted">API anahtarları burada, sunucudaki <code>.env</code> dosyasına dokunmadan girilebilir ve hemen etkili olur (servis yeniden başlatmaya gerek yok).</p>
</section>
<section class="card">
{fields_html}
</section>
</main>
</body>
</html>""")


@router.post("/settings/{field_key}")
def save_setting(
    field_key: str,
    value: str = Form(...),
) -> RedirectResponse:
    if field_key not in FIELD_LABELS:
        raise HTTPException(status_code=404, detail="Bilinmeyen ayar.")

    value = value.strip()

    if not value:
        raise HTTPException(status_code=400, detail="Değer boş olamaz.")

    settings.save_secret(field_key, value)

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/{field_key}/clear")
def clear_setting(field_key: str) -> RedirectResponse:
    if field_key not in FIELD_LABELS:
        raise HTTPException(status_code=404, detail="Bilinmeyen ayar.")

    settings.save_secret(field_key, "")

    return RedirectResponse(url="/settings", status_code=303)
