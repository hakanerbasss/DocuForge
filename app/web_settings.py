import html
import subprocess
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.core.config import SECRET_FIELDS, settings

XTTS_REFERENCE_DIR = Path("models/xtts")
XTTS_REFERENCE_PATH = XTTS_REFERENCE_DIR / "reference.wav"
XTTS_REFERENCE_PATH_2 = XTTS_REFERENCE_DIR / "reference2.wav"

# Which reference slot (field key) each upload target writes to.
XTTS_SLOTS: dict[str, Path] = {
    "xtts_reference_audio": XTTS_REFERENCE_PATH,
    "xtts_reference_audio_2": XTTS_REFERENCE_PATH_2,
}

CLOSING_IMAGE_DIR = Path("models/closing")
CHANNEL_LOGO_DIR = Path("models/logo")


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
    "xtts_reference_audio_2": (
        "XTTS Referans Ses 2 (opsiyonel)",
        "XTTS_REFERENCE_AUDIO_2",
        "İkinci bir klon ses referansı (ör. farklı bir kişi). Yüklersen aşağıdan hangisinin kullanılacağını seçebilirsin.",
        "text",
        "/root/projects/DocuForge/models/xtts/reference2.wav",
    ),
    "jamendo_client_id": (
        "Jamendo Client ID",
        "JAMENDO_CLIENT_ID",
        "Telifsiz arka plan müziği araması için (jamendo.com/developer üzerinden ücretsiz alınır).",
        "password",
        "...",
    ),
    "mubert_company_id": (
        "Mubert Company ID",
        "MUBERT_COMPANY_ID",
        "Yapay zeka ile müzik üretimi için (mubert.com API erişimi gerekir).",
        "password",
        "...",
    ),
    "mubert_license_token": (
        "Mubert License Token",
        "MUBERT_LICENSE_TOKEN",
        "Mubert hesabıyla birlikte verilen lisans anahtarı.",
        "password",
        "...",
    ),
    "elevenlabs_api_key": (
        "ElevenLabs API Key",
        "ELEVENLABS_API_KEY",
        "Yapay zeka ile arka plan/fon müziği üretimi için (elevenlabs.io -- anahtarı oluştururken sadece 'Music' erişimini aç). Her arama gerçek, ücretli bir üretim isteğidir -- Jamendo gibi ücretsiz bir katalog taraması değildir.",
        "password",
        "...",
    ),
    "freesound_api_key": (
        "Freesound API Key",
        "FREESOUND_API_KEY",
        "Ücretsiz Creative Commons ses/atmosfer kütüphanesi araması için (freesound.org/apiv2/apply). Jamendo'dan farklı olarak çoğu içerik şarkı değil, doğrudan atmosfer/fon sesi kaydı.",
        "password",
        "...",
    ),
    "closing_image": (
        "Belgesel Kapanış Görseli",
        "CLOSING_IMAGE",
        "Belgesel türündeki videoların son sahnesinde otomatik üretilen kapanış çekimi yerine kullanılacak sabit bir görsel (ör. ChatGPT/DALL-E'de tasarladığın bir kapanış karesi). Anlatım sesi yine o sahnenin metniyle çalar, sadece görsel değişir. Yüklemek yetmez -- aşağıdaki 'Belgesellerin sonuna ekle' anahtarı da açık olmalı; kapalıyken (veya hiç yüklenmemişse) AI'ın kendi ürettiği kapanış çekimi kullanılır.",
        "image",
        "",
    ),
    "channel_logo": (
        "Kanal Logosu",
        "CHANNEL_LOGO",
        "Üretilen tüm kapak (thumbnail) tasarımlarının sağ alt köşesine eklenecek küçük marka logosu. En iyi sonuç için arka planı şeffaf (PNG) ve yuvarlak/kare bir logo kullan -- yüklediğin görsel neyse aynen o şekliyle basılır, otomatik yuvarlatma yapılmaz. Yüklemek yetmez -- aşağıdaki 'Kapaklara ekle' anahtarı da açık olmalı.",
        "image",
        "",
    ),
}


def _xtts_name_field_key(slot: int) -> str:
    return "xtts_reference_name" if slot == 1 else "xtts_reference_name_2"


def _xtts_ref_display_name(slot: int) -> str:
    """The user's label for a reference, or a generic fallback."""

    name = str(
        getattr(settings, _xtts_name_field_key(slot), "") or ""
    ).strip()
    return name or f"Referans {slot}"


def _render_xtts_slot(field_key: str, slot: int) -> str:
    """Render one XTTS reference slot (upload/record or the configured player)."""

    label, env_name, description, _input_type, _placeholder = FIELD_LABELS[
        field_key
    ]
    configured = settings.is_configured(field_key)
    current_path = Path(getattr(settings, field_key)) if configured else None

    name_field_key = _xtts_name_field_key(slot)
    current_name = str(
        getattr(settings, name_field_key, "") or ""
    ).strip()

    name_row = f"""
    <div style="margin-bottom:10px">
        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:12px;color:#4a5568">Bu sesin ismi (kime ait?)</label>
        <div style="display:flex;align-items:center;gap:8px">
            <input type="text" id="{name_field_key}Input" value="{html.escape(current_name)}" placeholder="ör. Eşim, Ben, Sunucu"
                onchange="setXttsRefName('{name_field_key}', this.value)"
                style="flex:1;min-height:40px;padding:0 12px;border:1px solid #cbd6e5;border-radius:10px;font:inherit;box-sizing:border-box">
            <span id="{name_field_key}Saved" class="muted" style="font-size:12px;white-space:nowrap"></span>
        </div>
    </div>
    """

    if configured and current_path is not None and current_path.exists():
        audio_version = int(current_path.stat().st_mtime)
        body = f"""
        <div style="background:#e7f9ee;border:1px solid #b9e6c9;border-radius:10px;padding:12px 14px">
            <div style="color:#087a38;font-weight:700;margin-bottom:8px">✓ Yapılandırılmış</div>
            <audio controls preload="metadata" style="width:100%;margin-bottom:10px">
                <source src="/settings/{field_key}/file?v={audio_version}" type="audio/wav">
            </audio>
            <form method="post" action="/settings/{field_key}/clear" style="margin:0">
                <button class="button secondary" type="submit" style="min-height:34px;padding:0 12px;font-size:13px">Değiştir</button>
            </form>
        </div>
        """
    else:
        body = f"""
        <div style="display:flex;flex-direction:column;gap:14px">
            <div>
                <label style="display:block;margin-bottom:6px;font-weight:700;font-size:13px">Ses veya video dosyası yükle</label>
                <div style="display:flex;gap:8px">
                    <input type="file" id="xttsFileInput{slot}" accept="audio/*,video/*" style="flex:1;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:8px">
                    <button type="button" class="button" onclick="uploadXttsFile({slot})" style="white-space:nowrap">Yükle</button>
                </div>
                <div class="muted" style="font-size:12px;margin-top:6px">Video de yükleyebilirsin — sesi otomatik çıkarılır (mp4, mov, m4a, wav, mp3…).</div>
            </div>
            <div>
                <label style="display:block;margin-bottom:6px;font-weight:700;font-size:13px">Veya mikrofonla kaydet (20-30 sn, sessiz ortamda doğal konuş)</label>
                <div style="display:flex;align-items:center;gap:10px">
                    <button type="button" id="xttsStartRecord{slot}" class="button" onclick="startXttsRecording({slot})">🎙 Kaydı Başlat</button>
                    <button type="button" id="xttsStopRecord{slot}" class="button secondary" style="display:none" onclick="stopXttsRecording({slot})">⏹ Durdur ve Yükle</button>
                    <span id="xttsRecordStatus{slot}" class="muted" style="font-size:13px"></span>
                </div>
            </div>
        </div>
        """

    display_name = current_name or f"Referans {slot}"

    return f"""
    <div style="margin-top:{'0' if slot == 1 else '18'}px">
        <div style="font-weight:700;margin-bottom:2px;font-size:14px">
            {html.escape(display_name)}
            <span class="muted" style="font-weight:400;font-size:12px">— {html.escape(label)}</span>
        </div>
        <div class="muted" style="font-size:13px;margin-bottom:10px">
            {html.escape(description)}
            (<code>{env_name}</code> ortam değişkeni ayarlıysa her zaman öncelikli olur ve buradan değiştirilemez.)
        </div>
        {name_row}
        {body}
    </div>
    """


def _render_xtts_active_selector() -> str:
    """A radio selector for which configured reference narrations should use.

    Only shown when both slots hold a usable file -- with a single reference
    there is nothing to choose between.
    """

    has_1 = (
        settings.is_configured("xtts_reference_audio")
        and Path(settings.xtts_reference_audio).exists()
    )
    has_2 = (
        settings.is_configured("xtts_reference_audio_2")
        and Path(settings.xtts_reference_audio_2).exists()
    )

    if not (has_1 and has_2):
        return ""

    active = str(settings.xtts_active_reference or "1").strip() or "1"
    checked_1 = "checked" if active != "2" else ""
    checked_2 = "checked" if active == "2" else ""

    name_1 = html.escape(_xtts_ref_display_name(1))
    name_2 = html.escape(_xtts_ref_display_name(2))

    return f"""
    <div style="margin-top:18px;background:#eef5ff;border:1px solid #cfe0f7;border-radius:10px;padding:12px 14px">
        <div style="font-weight:700;font-size:13px;margin-bottom:8px">🎚 Kullanılacak referans ses</div>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:6px">
            <input type="radio" name="xttsActiveRef" value="1" {checked_1} onchange="setActiveXttsReference('1')" style="width:auto;min-height:auto">
            {name_1}
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <input type="radio" name="xttsActiveRef" value="2" {checked_2} onchange="setActiveXttsReference('2')" style="width:auto;min-height:auto">
            {name_2}
        </label>
        <div class="muted" style="font-size:12px;margin-top:8px">Klon ses üretiminde seçtiğin referans kullanılır.</div>
    </div>
    """


def _render_xtts_field() -> str:
    return f"""
    <div style="padding:16px 0;border-bottom:1px solid #edf1f6">
        {_render_xtts_slot("xtts_reference_audio", 1)}
        {_render_xtts_slot("xtts_reference_audio_2", 2)}
        {_render_xtts_active_selector()}
    </div>
    """


def _render_closing_image_field() -> str:
    label, env_name, description, _input_type, _placeholder = FIELD_LABELS[
        "closing_image"
    ]
    configured = settings.is_configured("closing_image")
    current_path = Path(settings.closing_image) if configured else None
    enabled = settings.is_configured("closing_image_enabled")

    if configured and current_path is not None and current_path.exists():
        checked = "checked" if enabled else ""
        # Cache-busting: same filename gets overwritten on every re-upload,
        # so without a query param that changes, browsers keep showing the
        # old cached image at this exact URL even after a hard refresh.
        image_version = int(current_path.stat().st_mtime)
        body = f"""
        <div style="background:#e7f9ee;border:1px solid #b9e6c9;border-radius:10px;padding:12px 14px">
            <div style="color:#087a38;font-weight:700;margin-bottom:8px">✓ Yapılandırılmış</div>
            <img src="/settings/closing_image/file?v={image_version}" alt="Kapanış görseli" style="max-width:100%;max-height:280px;border-radius:8px;display:block;margin-bottom:12px">
            <label style="display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;margin-bottom:12px;cursor:pointer">
                <input type="checkbox" id="closingImageEnabledToggle" {checked} onchange="toggleClosingImageEnabled(this)" style="width:auto;min-height:auto">
                Belgesellerin sonuna ekle
            </label>
            <div class="muted" style="font-size:12px;margin-bottom:10px">
                Kapalıyken görsel yüklü kalır ama kullanılmaz -- AI'ın kendi ürettiği kapanış çekimi devreye girer.
            </div>
            <form method="post" action="/settings/closing_image/clear" style="margin:0">
                <button class="button secondary" type="submit" style="min-height:34px;padding:0 12px;font-size:13px">Değiştir</button>
            </form>
        </div>
        """
    else:
        body = """
        <div>
            <label style="display:block;margin-bottom:6px;font-weight:700;font-size:13px">Görsel yükle</label>
            <div style="display:flex;gap:8px">
                <input type="file" id="closingImageFileInput" accept="image/*" style="flex:1;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:8px">
                <button type="button" class="button" onclick="uploadClosingImageFile()" style="white-space:nowrap">Yükle</button>
            </div>
        </div>
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


def _render_channel_logo_field() -> str:
    label, env_name, description, _input_type, _placeholder = FIELD_LABELS[
        "channel_logo"
    ]
    configured = settings.is_configured("channel_logo")
    current_path = Path(settings.channel_logo) if configured else None
    enabled = settings.is_configured("channel_logo_enabled")

    if configured and current_path is not None and current_path.exists():
        checked = "checked" if enabled else ""
        # Cache-busting: same filename gets overwritten on every re-upload,
        # so without a query param that changes, browsers keep showing the
        # old cached image at this exact URL even after a hard refresh.
        image_version = int(current_path.stat().st_mtime)
        body = f"""
        <div style="background:#e7f9ee;border:1px solid #b9e6c9;border-radius:10px;padding:12px 14px">
            <div style="color:#087a38;font-weight:700;margin-bottom:8px">✓ Yapılandırılmış</div>
            <img src="/settings/channel_logo/file?v={image_version}" alt="Kanal logosu" style="max-width:140px;max-height:140px;border-radius:8px;display:block;margin-bottom:12px;background:repeating-conic-gradient(#eee 0% 25%,#fff 0% 50%) 50%/16px 16px">
            <label style="display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;margin-bottom:12px;cursor:pointer">
                <input type="checkbox" id="channelLogoEnabledToggle" {checked} onchange="toggleChannelLogoEnabled(this)" style="width:auto;min-height:auto">
                Kapaklara ekle
            </label>
            <div class="muted" style="font-size:12px;margin-bottom:10px">
                Kapalıyken logo yüklü kalır ama kapak tasarımlarına basılmaz.
            </div>
            <form method="post" action="/settings/channel_logo/clear" style="margin:0">
                <button class="button secondary" type="submit" style="min-height:34px;padding:0 12px;font-size:13px">Değiştir</button>
            </form>
        </div>
        """
    else:
        body = """
        <div>
            <label style="display:block;margin-bottom:6px;font-weight:700;font-size:13px">Logo yükle</label>
            <div style="display:flex;gap:8px">
                <input type="file" id="channelLogoFileInput" accept="image/*" style="flex:1;min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:8px">
                <button type="button" class="button" onclick="uploadChannelLogoFile()" style="white-space:nowrap">Yükle</button>
            </div>
        </div>
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


def _render_field(field_key: str) -> str:
    if field_key == "xtts_reference_audio":
        return _render_xtts_field()

    if field_key == "xtts_reference_audio_2":
        # Rendered together with slot 1 inside _render_xtts_field(); skip the
        # standalone text-field rendering the generic path would produce.
        return ""

    if field_key == "closing_image":
        return _render_closing_image_field()

    if field_key == "channel_logo":
        return _render_channel_logo_field()

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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Ayarlar · DocuForge</title>
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
code{{background:#eef3fb;padding:1px 5px;border-radius:5px;font-size:12px}}
</style>
</head>
<body>
<header><div style="display:flex;align-items:center;justify-content:space-between;gap:16px">
<a class="back" href="/">← Projelere dön</a>
<a class="button secondary" href="/voice-test" style="min-height:34px;padding:0 12px;font-size:13px">🎤 Ses Testi</a>
<a class="button secondary" href="/storage" style="min-height:34px;padding:0 12px;font-size:13px">📦 Depolama</a>
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
<script>
let xttsRecorder = null;
let xttsChunks = [];

function xttsUploadUrl(slot) {{
    return slot === 2
        ? "/settings/xtts_reference_audio_2/upload"
        : "/settings/xtts_reference_audio/upload";
}}

async function uploadXttsFile(slot) {{
    const input = document.getElementById("xttsFileInput" + slot);
    if (!input.files || !input.files.length) {{ alert("Bir ses dosyası seç."); return; }}
    const fd = new FormData();
    fd.append("file", input.files[0]);
    await submitXttsUpload(fd, slot);
}}

async function startXttsRecording(slot) {{
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
        alert("Tarayıcı mikrofon erişimine izin vermiyor. Bu genellikle sitenin HTTPS olmamasından kaynaklanır (mikrofon sadece güvenli bağlantıda çalışır) — bunun yerine dosya yükleme kullan.");
        return;
    }}
    try {{
        const stream = await navigator.mediaDevices.getUserMedia({{audio: true}});
        xttsChunks = [];
        xttsRecorder = new MediaRecorder(stream);
        xttsRecorder.ondataavailable = e => {{ if (e.data.size > 0) xttsChunks.push(e.data); }};
        xttsRecorder.start();
        document.getElementById("xttsStartRecord" + slot).style.display = "none";
        document.getElementById("xttsStopRecord" + slot).style.display = "inline-flex";
        document.getElementById("xttsRecordStatus" + slot).textContent = "🔴 Kayıt yapılıyor...";
    }} catch (e) {{
        alert("Mikrofona erişilemedi: " + e.message);
    }}
}}

async function stopXttsRecording(slot) {{
    document.getElementById("xttsRecordStatus" + slot).textContent = "⏳ Yükleniyor...";
    document.getElementById("xttsStopRecord" + slot).style.display = "none";

    const blob = await new Promise(resolve => {{
        xttsRecorder.onstop = () => resolve(new Blob(xttsChunks, {{type: "audio/webm"}}));
        xttsRecorder.stop();
        xttsRecorder.stream.getTracks().forEach(t => t.stop());
    }});

    const fd = new FormData();
    fd.append("file", blob, "recorded_reference.webm");
    await submitXttsUpload(fd, slot);
}}

async function submitXttsUpload(formData, slot) {{
    try {{
        const r = await fetch(xttsUploadUrl(slot), {{method: "POST", body: formData}});
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Yükleme başarısız.");
        }}
        location.href = "/settings";
    }} catch (e) {{
        alert("Hata: " + e.message);
        const status = document.getElementById("xttsRecordStatus" + slot);
        if (status) status.textContent = "";
        const start = document.getElementById("xttsStartRecord" + slot);
        if (start) start.style.display = "inline-flex";
    }}
}}

async function setActiveXttsReference(value) {{
    const fd = new URLSearchParams();
    fd.append("value", value);
    try {{
        const r = await fetch("/settings/xtts_active_reference", {{
            method: "POST",
            headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
            body: fd,
        }});
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Kaydedilemedi.");
        }}
    }} catch (e) {{
        alert("Hata: " + e.message);
    }}
}}

async function setXttsRefName(fieldKey, value) {{
    // Save silently WITHOUT reloading -- a reload here would wipe a file the
    // user had already picked in the upload box, making the next "Yükle"
    // report "Dosya seçilmedi". The header/selector labels pick up the new
    // name on the next natural reload (e.g. after an upload).
    const name = (value || "").trim();
    const saved = document.getElementById(fieldKey + "Saved");
    try {{
        let r;
        if (name) {{
            const fd = new URLSearchParams();
            fd.append("value", name);
            r = await fetch("/settings/" + fieldKey, {{
                method: "POST",
                headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
                body: fd,
            }});
        }} else {{
            r = await fetch("/settings/" + fieldKey + "/clear", {{method: "POST"}});
        }}
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Kaydedilemedi.");
        }}
        if (saved) {{
            saved.textContent = "✓ kaydedildi";
            saved.style.color = "#087a38";
            setTimeout(() => {{ saved.textContent = ""; }}, 2000);
        }}
    }} catch (e) {{
        if (saved) {{ saved.textContent = ""; }}
        alert("Hata: " + e.message);
    }}
}}

async function toggleClosingImageEnabled(checkbox) {{
    checkbox.disabled = true;
    try {{
        let r;
        if (checkbox.checked) {{
            const fd = new URLSearchParams();
            fd.append("value", "1");
            r = await fetch("/settings/closing_image_enabled", {{
                method: "POST",
                headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
                body: fd,
            }});
        }} else {{
            r = await fetch("/settings/closing_image_enabled/clear", {{method: "POST"}});
        }}
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Kaydedilemedi.");
        }}
    }} catch (e) {{
        alert("Hata: " + e.message);
        checkbox.checked = !checkbox.checked;
    }} finally {{
        checkbox.disabled = false;
    }}
}}

async function uploadClosingImageFile() {{
    const input = document.getElementById("closingImageFileInput");
    if (!input.files || !input.files.length) {{ alert("Bir görsel seç."); return; }}
    const fd = new FormData();
    fd.append("file", input.files[0]);
    try {{
        const r = await fetch("/settings/closing_image/upload", {{method: "POST", body: fd}});
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Yükleme başarısız.");
        }}
        location.href = "/settings";
    }} catch (e) {{
        alert("Hata: " + e.message);
    }}
}}

async function toggleChannelLogoEnabled(checkbox) {{
    checkbox.disabled = true;
    try {{
        let r;
        if (checkbox.checked) {{
            const fd = new URLSearchParams();
            fd.append("value", "1");
            r = await fetch("/settings/channel_logo_enabled", {{
                method: "POST",
                headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
                body: fd,
            }});
        }} else {{
            r = await fetch("/settings/channel_logo_enabled/clear", {{method: "POST"}});
        }}
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Kaydedilemedi.");
        }}
    }} catch (e) {{
        alert("Hata: " + e.message);
        checkbox.checked = !checkbox.checked;
    }} finally {{
        checkbox.disabled = false;
    }}
}}

async function uploadChannelLogoFile() {{
    const input = document.getElementById("channelLogoFileInput");
    if (!input.files || !input.files.length) {{ alert("Bir görsel seç."); return; }}
    const fd = new FormData();
    fd.append("file", input.files[0]);
    try {{
        const r = await fetch("/settings/channel_logo/upload", {{method: "POST", body: fd}});
        if (!r.ok) {{
            const err = await r.json().catch(() => ({{}}));
            throw new Error(err.detail || "Yükleme başarısız.");
        }}
        location.href = "/settings";
    }} catch (e) {{
        alert("Hata: " + e.message);
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


@router.post("/settings/{field_key}")
def save_setting(
    field_key: str,
    value: str = Form(...),
) -> RedirectResponse:
    if field_key not in SECRET_FIELDS.values():
        raise HTTPException(status_code=404, detail="Bilinmeyen ayar.")

    value = value.strip()

    if not value:
        raise HTTPException(status_code=400, detail="Değer boş olamaz.")

    settings.save_secret(field_key, value)

    return RedirectResponse(url="/settings", status_code=303)


FILE_BACKED_FIELDS = {
    "xtts_reference_audio",
    "xtts_reference_audio_2",
    "closing_image",
    "channel_logo",
}


@router.post("/settings/{field_key}/clear")
def clear_setting(field_key: str) -> RedirectResponse:
    if field_key not in SECRET_FIELDS.values():
        raise HTTPException(status_code=404, detail="Bilinmeyen ayar.")

    # These fields store a filesystem path, not the value itself --
    # clearing the pointer without deleting the file would leave the
    # actual upload (ses/görsel dosyası) orphaned on disk indefinitely.
    if field_key in FILE_BACKED_FIELDS and settings.is_configured(field_key):
        try:
            Path(getattr(settings, field_key)).unlink(missing_ok=True)
        except OSError:
            pass

    settings.save_secret(field_key, "")

    return RedirectResponse(url="/settings", status_code=303)


def _xtts_field_key_for_slot(slot: int) -> str:
    if slot == 1:
        return "xtts_reference_audio"
    if slot == 2:
        return "xtts_reference_audio_2"
    raise HTTPException(status_code=404, detail="Geçersiz referans slotu.")


@router.get("/settings/xtts_reference_audio/file")
def get_xtts_reference_audio() -> FileResponse:
    return _serve_xtts_reference(1)


@router.get("/settings/xtts_reference_audio_2/file")
def get_xtts_reference_audio_2() -> FileResponse:
    return _serve_xtts_reference(2)


def _serve_xtts_reference(slot: int) -> FileResponse:
    field_key = _xtts_field_key_for_slot(slot)

    if not settings.is_configured(field_key):
        raise HTTPException(status_code=404, detail="Referans ses ayarlı değil.")

    path = Path(getattr(settings, field_key))

    if not path.exists():
        raise HTTPException(status_code=404, detail="Referans ses dosyası bulunamadı.")

    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.post("/settings/xtts_reference_audio/upload")
async def upload_xtts_reference_audio(
    file: UploadFile = File(...),
) -> RedirectResponse:
    return await _store_xtts_reference(1, file)


@router.post("/settings/xtts_reference_audio_2/upload")
async def upload_xtts_reference_audio_2(
    file: UploadFile = File(...),
) -> RedirectResponse:
    return await _store_xtts_reference(2, file)


async def _store_xtts_reference(
    slot: int,
    file: UploadFile,
) -> RedirectResponse:
    field_key = _xtts_field_key_for_slot(slot)
    destination = XTTS_SLOTS[field_key]

    XTTS_REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload").suffix or ".webm"
    temp_path = XTTS_REFERENCE_DIR / f"_upload{slot}{suffix}"

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş.")

    temp_path.write_bytes(content)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(temp_path),
                # Drop any video stream and keep only mono 24kHz audio, so a
                # phone video (mp4/mov) works as a reference just like a wav.
                "-vn",
                "-ar",
                "24000",
                "-ac",
                "1",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail="FFmpeg sunucuda bulunamadı.",
        ) from error
    except subprocess.CalledProcessError as error:
        raise HTTPException(
            status_code=400,
            detail=f"Ses dosyası işlenemedi: {error.stderr}",
        ) from error
    finally:
        temp_path.unlink(missing_ok=True)

    settings.save_secret(field_key, str(destination.resolve()))

    return RedirectResponse(url="/settings", status_code=303)


@router.get("/settings/closing_image/file")
def get_closing_image() -> FileResponse:
    if not settings.is_configured("closing_image"):
        raise HTTPException(status_code=404, detail="Kapanış görseli ayarlı değil.")

    path = Path(settings.closing_image)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Kapanış görseli dosyası bulunamadı.")

    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.post("/settings/closing_image/upload")
async def upload_closing_image(
    file: UploadFile = File(...),
) -> RedirectResponse:
    CLOSING_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload").suffix.lower()

    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        suffix = ".jpg"

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş.")

    # Eski yüklemeden kalma farklı uzantılı bir dosya varsa (ör. önce .png
    # yüklenip şimdi .jpg yükleniyorsa) karışıklık olmasın diye temizleniyor.
    for old_file in CLOSING_IMAGE_DIR.glob("closing_image.*"):
        old_file.unlink(missing_ok=True)

    destination = CLOSING_IMAGE_DIR / f"closing_image{suffix}"
    destination.write_bytes(content)

    settings.save_secret(
        "closing_image",
        str(destination.resolve()),
    )

    return RedirectResponse(url="/settings", status_code=303)


@router.get("/settings/channel_logo/file")
def get_channel_logo() -> FileResponse:
    if not settings.is_configured("channel_logo"):
        raise HTTPException(status_code=404, detail="Kanal logosu ayarlı değil.")

    path = Path(settings.channel_logo)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Kanal logosu dosyası bulunamadı.")

    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.post("/settings/channel_logo/upload")
async def upload_channel_logo(
    file: UploadFile = File(...),
) -> RedirectResponse:
    CHANNEL_LOGO_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload").suffix.lower()

    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        suffix = ".png"

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş.")

    # Eski yüklemeden kalma farklı uzantılı bir dosya varsa (ör. önce .png
    # yüklenip şimdi .jpg yükleniyorsa) karışıklık olmasın diye temizleniyor.
    for old_file in CHANNEL_LOGO_DIR.glob("channel_logo.*"):
        old_file.unlink(missing_ok=True)

    destination = CHANNEL_LOGO_DIR / f"channel_logo{suffix}"
    destination.write_bytes(content)

    settings.save_secret(
        "channel_logo",
        str(destination.resolve()),
    )

    return RedirectResponse(url="/settings", status_code=303)
