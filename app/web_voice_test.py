import hashlib
import html
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.providers.defaults import register_default_providers
from app.providers.registry import ProviderRegistry
from app.utils.tr_tts_normalize import clean_tts_text

router = APIRouter()

VOICE_TEST_DIR = Path("voice_test_cache")

# Medium-length Turkish paragraph deliberately packed with the categories
# tr_tts_normalize.py handles -- large numbers, decimals with virgul,
# percentages, dates, a negative temperature, a degree symbol, area/energy/
# file-size units, an ordinal, a currency amount, a ppm range, Roman-numeral
# ordinals, BC/AD era markers, acronyms with Turkish suffixes, and a score
# ratio -- so a single test run actually exercises the same normalization
# path every real narration goes through, not just plain prose.
DEFAULT_TEST_TEXT = (
    "1953 yılında kurulan bu tesis, %42'lik bir büyüme "
    "kaydederek 2027'ye kadar üretimini üç katına "
    "çıkarmayı hedefliyor. Geçen yıl 15.08.2026 "
    "tarihinde açılan yeni ünitede sıcaklık -5 "
    "dereceden 38°C'ye kadar değişebiliyor. NASA ve "
    "TBMM'nin ortak raporuna göre, alan 10 km²'lik bir "
    "bölgeyi kapsıyor ve günde 200 MWh enerji "
    "tüketiyor. Saat 14:30'da başlayan toplantıda, "
    "katılım oranının %13,52 arttığı "
    "açıklandı. Tesisin 3. bölümünde bulunan "
    "472 kişilik ekip, ürünleri 250 TL'ye satışa "
    "sunuyor. Verilere göre CO2 seviyesi 280 ppm'den 420 ppm'e "
    "yükseldi. İmparator I. Justinianus döneminde MS "
    "532'de temelleri atılan yapı, MÖ 660'ta kurulan "
    "antik şehrin kalıntıları üzerine "
    "inşa edildi. Wi-Fi altyapısı %99,9 kesintisiz "
    "çalışırken, GPU'lar ve TPU'lar sistemin "
    "kalbini oluşturuyor. Maç sonucu 3-1 ile tamamlandı "
    "ve dosya boyutu 5GB'a ulaştı."
)

# provider_key -> [(voice_name, display_label), ...]. XTTS is special:
# its two "voice_name" choices map to the two configured reference slots
# (see _resolve_xtts_reference_path), not literal engine voice names.
VOICE_TEST_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "supertonic": [
        ("M1", "M1"), ("M2", "M2"), ("M3", "M3"), ("M4", "M4"), ("M5", "M5"),
        ("F1", "F1"), ("F2", "F2"), ("F3", "F3"), ("F4", "F4"), ("F5", "F5"),
    ],
    "piper": [("default", "Varsayılan")],
    "espeak": [("default", "Varsayılan")],
    "local_tts": [("default", "Varsayılan")],
    "xtts": [("ref1", "Referans 1"), ("ref2", "Referans 2")],
}

PROVIDER_LABELS: dict[str, str] = {
    "supertonic": "Supertonic",
    "piper": "Piper TTS",
    "espeak": "eSpeak NG",
    "local_tts": "Local TTS (eSpeak NG)",
    "xtts": "XTTS Klon Ses",
}


class VoiceTestRequest(BaseModel):
    provider: str = Field(...)
    voice_name: str = Field(...)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    language: str = Field(default="tr")
    text: str = Field(..., min_length=1, max_length=4000)


def _xtts_reference_label(slot: str) -> str:
    name_field = "xtts_reference_name" if slot == "ref1" else "xtts_reference_name_2"
    name = str(getattr(settings, name_field, "") or "").strip()
    return name or ("Referans 1" if slot == "ref1" else "Referans 2")


def _resolve_xtts_reference_path(voice_name: str) -> str:
    """Map the test page's ref1/ref2 choice to a configured reference file.

    Explicit, not the "active reference" settings toggle -- the whole
    point of this page is comparing voices side by side, so each row must
    use exactly the slot it says it uses, regardless of which one is
    currently "active" elsewhere in the app.
    """

    field = "xtts_reference_audio" if voice_name == "ref1" else "xtts_reference_audio_2"
    configured = str(getattr(settings, field, "") or "").strip()

    if not configured:
        slot_label = "Referans 1" if voice_name == "ref1" else "Referans 2"
        raise HTTPException(
            status_code=400,
            detail=(
                f"XTTS {slot_label} henüz yüklenmemiş. "
                "Ayarlar sayfasından bir referans ses yükle."
            ),
        )

    path = Path(configured)

    if not path.exists():
        raise HTTPException(
            status_code=400,
            detail="XTTS referans ses dosyası bulunamadı.",
        )

    return str(path)


def _cache_filename(
    provider: str,
    voice_name: str,
    speed: float,
    language: str,
    text: str,
) -> str:
    digest = hashlib.sha1(
        f"{provider}|{voice_name}|{speed}|{language}|{text}".encode("utf-8")
    ).hexdigest()[:20]

    return f"{provider}_{voice_name}_{digest}.wav"


@router.post("/api/voice-test/synthesize")
def synthesize_voice_test(req: VoiceTestRequest) -> dict[str, Any]:
    provider_key = req.provider.strip().lower()
    voice_name = req.voice_name.strip()
    text = req.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Test metni boş olamaz.")

    if provider_key not in VOICE_TEST_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen ses sağlayıcı: {provider_key}")

    valid_names = {name for name, _label in VOICE_TEST_OPTIONS[provider_key]}
    if voice_name not in valid_names:
        raise HTTPException(status_code=400, detail=f"'{provider_key}' için geçersiz ses: {voice_name}")

    VOICE_TEST_DIR.mkdir(parents=True, exist_ok=True)
    filename = _cache_filename(provider_key, voice_name, req.speed, req.language, text)
    output_path = VOICE_TEST_DIR / filename

    if output_path.exists() and output_path.stat().st_size > 0:
        return {"url": f"/voice-test/audio/{filename}", "cached": True}

    register_default_providers()

    try:
        provider = ProviderRegistry.create(category="voice", key=provider_key)
    except KeyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    cleaned_text = clean_tts_text(text, lang=req.language)

    synth_kwargs: dict[str, Any] = {
        "language": req.language,
        "voice": req.language,
        "voice_name": voice_name,
        "speed": req.speed,
    }

    if provider_key == "xtts":
        synth_kwargs["reference_audio"] = _resolve_xtts_reference_path(voice_name)

    try:
        provider.synthesize(cleaned_text, output_path, **synth_kwargs)
    except Exception as error:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=502,
            detail=f"Ses üretilemedi ({PROVIDER_LABELS.get(provider_key, provider_key)}): {error}",
        ) from error

    return {"url": f"/voice-test/audio/{filename}", "cached": False}


@router.get("/voice-test/audio/{filename}")
def get_voice_test_audio(filename: str) -> FileResponse:
    requested = (VOICE_TEST_DIR / filename).resolve()
    base = VOICE_TEST_DIR.resolve()

    if base not in requested.parents or not requested.is_file():
        raise HTTPException(status_code=404, detail="Ses dosyası bulunamadı.")

    return FileResponse(requested, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.post("/api/voice-test/clear-cache")
def clear_voice_test_cache() -> dict[str, Any]:
    removed = 0

    if VOICE_TEST_DIR.exists():
        for file_path in VOICE_TEST_DIR.iterdir():
            if file_path.is_file():
                file_path.unlink(missing_ok=True)
                removed += 1

    return {"removed": removed}


@router.get("/voice-test", response_class=HTMLResponse)
def voice_test_page() -> HTMLResponse:
    register_default_providers()

    registered_voice_keys = {
        definition.key for definition in ProviderRegistry.all(category="voice")
    }

    rows_html = ""

    for provider_key, voices in VOICE_TEST_OPTIONS.items():
        if provider_key not in registered_voice_keys:
            continue

        provider_label = html.escape(PROVIDER_LABELS.get(provider_key, provider_key))

        for voice_name, voice_label in voices:
            display_label = (
                html.escape(_xtts_reference_label(voice_name))
                if provider_key == "xtts"
                else html.escape(voice_label)
            )

            row_id = f"{provider_key}_{voice_name}"

            rows_html += f"""
            <div class="voice-row" style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #edf1f6;flex-wrap:wrap">
                <div style="flex:1;min-width:160px">
                    <strong>{provider_label}</strong>
                    <span class="muted" style="margin-left:6px">{display_label}</span>
                </div>
                <button
                    type="button"
                    class="button secondary"
                    id="btn_{row_id}"
                    style="width:auto;min-height:36px;padding:0 14px;font-size:13px"
                    onclick="playVoiceTest('{provider_key}','{voice_name}','{row_id}')"
                >
                    \U0001F50A Dinle
                </button>
                <audio id="audio_{row_id}" controls preload="none" style="height:36px;max-width:260px;display:none"></audio>
                <span id="status_{row_id}" class="muted" style="font-size:12px"></span>
            </div>
            """

    if not rows_html:
        rows_html = '<p class="muted">Kayıtlı ses sağlayıcı bulunamadı.</p>'

    return HTMLResponse(f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Ses Testi · DocuForge</title>
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#2166f3">
<style>
* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    background: #f4f7fb;
    color: #152033;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.inner {{ max-width: 900px; margin: 0 auto; padding: 0 16px; }}
header {{
    background: linear-gradient(135deg, #2166f3, #1747b0);
    color: white;
    padding: 16px 0;
}}
header .inner {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap }}
.back {{ color: white; text-decoration: none; font-weight: 600; font-size: 14px; opacity: .92 }}
.button {{
    display: inline-flex; align-items: center; justify-content: center;
    background: #2166f3; color: white; border: none; border-radius: 10px;
    padding: 0 16px; min-height: 44px; font-size: 15px; font-weight: 700;
    cursor: pointer; text-decoration: none;
}}
.button.secondary {{ background: #eef2f9; color: #17284d; }}
.button:disabled {{ opacity: .55; cursor: default; }}
.card {{ background: white; border-radius: 16px; padding: 20px; margin-top: 16px; box-shadow: 0 1px 3px rgba(20,30,60,.08); }}
h1 {{ font-size: 22px; margin: 20px 0 4px; }}
h2 {{ font-size: 18px; margin: 0 0 10px; }}
.muted {{ color: #64748b; }}
textarea {{
    width: 100%; min-height: 140px; padding: 12px; border: 1px solid #cbd6e5;
    border-radius: 10px; background: white; color: #172033; font: inherit; resize: vertical;
}}
label {{ display: block; font-weight: 700; font-size: 13px; margin-bottom: 6px; }}
input[type="number"] {{
    min-height: 42px; border: 1px solid #cbd6e5; border-radius: 10px;
    padding: 0 12px; font: inherit; width: 140px;
}}
body {{ padding-bottom: 76px; }}
.bottom-nav {{
    position: fixed; left: 0; right: 0; bottom: 0; display: flex;
    background: white; border-top: 1px solid #e2e8f0;
    box-shadow: 0 -6px 20px rgba(20,30,60,.06); z-index: 100;
    padding-bottom: env(safe-area-inset-bottom, 0);
}}
.bottom-nav a {{
    flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px;
    padding: 9px 4px 10px; text-decoration: none; color: #7c8aa0;
    font-size: 11px; font-weight: 700;
}}
.bottom-nav a .nav-icon {{ font-size: 21px; line-height: 1; }}
.bottom-nav a.active {{ color: #2166f3; }}
</style>
</head>
<body>
<header>
<div class="inner">
<a class="back" href="/">← Projelere dön</a>
</div>
</header>
<main class="inner">
<h1>\U0001F3A4 Ses Testi</h1>
<p class="muted">
    Tüm ses sistemlerini aynı metinle kıyasla -- bir video baştan üretmeden hangi sesin daha iyi
    okuduğunu buradan hızlıca dinleyip seçebilirsin. Metin sayı, tarih, yüzde,
    sembol ve kısaltma içerir; gerçek anlatımda kullanılan aynı normalizasyon
    (sayıların yazıyla okunması vb.) burada da uygulanır.
</p>

<div class="card">
<h2>Test Metni</h2>
<textarea id="testText">{html.escape(DEFAULT_TEST_TEXT)}</textarea>
<div style="display:flex;gap:16px;margin-top:14px;flex-wrap:wrap;align-items:flex-end">
    <div>
        <label for="testLang">Dil</label>
        <select id="testLang" style="min-height:42px;border:1px solid #cbd6e5;border-radius:10px;padding:0 12px;font:inherit">
            <option value="tr" selected>Türkçe</option>
            <option value="en">English</option>
        </select>
    </div>
    <div>
        <label for="testSpeed">Konuşma Hızı</label>
        <input type="number" id="testSpeed" min="0.5" max="2.0" step="0.1" value="1.0">
    </div>
    <button type="button" class="button secondary" onclick="clearVoiceTestCache()" style="width:auto;min-height:42px;padding:0 14px;font-size:13px">
        \U0001F5D1 Test önbelleğini temizle
    </button>
</div>
<div class="muted" style="font-size:12px;margin-top:8px">
    Aynı metin/hız/ses kombinasyonu tekrar dinlenirse önceden üretilen dosya kullanılır --
    metni değiştirirsen her ses yeniden üretilir. XTTS ilk denemede model yüklediği için
    yavaş olabilir, sonrakiler hızlanır.
</div>
</div>

<div class="card">
<h2>Sesler</h2>
{rows_html}
</div>

</main>
<script>
async function playVoiceTest(provider, voiceName, rowId) {{
    const btn = document.getElementById("btn_" + rowId);
    const audioEl = document.getElementById("audio_" + rowId);
    const statusEl = document.getElementById("status_" + rowId);
    const text = document.getElementById("testText").value.trim();
    const language = document.getElementById("testLang").value;
    const speed = parseFloat(document.getElementById("testSpeed").value) || 1.0;

    if (!text) {{ alert("Test metni boş olamaz."); return; }}

    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "⏳ Üretiliyor...";
    statusEl.textContent = "";

    try {{
        const r = await fetch("/api/voice-test/synthesize", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{provider, voice_name: voiceName, speed, language, text}}),
        }});
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "Üretilemedi.");

        audioEl.src = data.url + "?t=" + Date.now();
        audioEl.style.display = "inline-block";
        statusEl.textContent = data.cached ? "✓ önbellekten" : "✓ üretildi";
        audioEl.play().catch(() => {{}});
    }} catch (e) {{
        statusEl.textContent = "";
        alert("Hata: " + e.message);
    }} finally {{
        btn.disabled = false;
        btn.textContent = original;
    }}
}}

async function clearVoiceTestCache() {{
    if (!confirm("Tüm test ses önbelleği silinsin mi?")) return;
    try {{
        const r = await fetch("/api/voice-test/clear-cache", {{method: "POST"}});
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "Silinemedi.");
        document.querySelectorAll("audio[id^='audio_']").forEach(el => {{ el.removeAttribute("src"); el.style.display = "none"; }});
        document.querySelectorAll("span[id^='status_']").forEach(el => {{ el.textContent = ""; }});
        alert(data.removed + " dosya silindi.");
    }} catch (e) {{
        alert("Hata: " + e.message);
    }}
}}

if ("serviceWorker" in navigator) {{
    navigator.serviceWorker.register("/static/sw.js").catch(() => {{}});
}}
</script>
<nav class="bottom-nav">
    <a href="/"><span class="nav-icon">🏠</span>Ana Sayfa</a>
    <a href="/voice-test" class="active"><span class="nav-icon">🎤</span>Ses Testi</a>
    <a href="/storage"><span class="nav-icon">📦</span>Depolama</a>
    <a href="/settings"><span class="nav-icon">⚙</span>Ayarlar</a>
</nav>
</body>
</html>""")
