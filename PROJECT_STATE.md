# DocuForge — Proje Durumu

Son güncelleme: 17 Temmuz 2026 (Türkçe TTS sayı/kısaltma okuma normalizasyonu — Instagram bot projesinden devralınan `clean_tts_text` tüm ses sağlayıcılarına tek noktadan entegre edildi)

## Ana hedef

DocuForge; konu girildiğinde araştırma, senaryo, storyboard, medya, seslendirme, render, thumbnail, altyazı ve YouTube hazırlık dosyalarını üreten, tamamen arayüzden yönetilen bağımsız bir video üretim platformu olacaktır.

Proje hiçbir Instagram botuna, haber botuna veya harici çalışan kişisel servise zorunlu olarak bağlı olmayacaktır.

---

## Şu anda çalışan özellikler

### Çekirdek pipeline

1. Research
2. Script
3. Storyboard
4. Image Prompts
5. Video Prompts
6. Narration
7. SEO Metadata (başlık önerileri, açıklama, etiketler)
8. Media Builder
9. Scene Narrations
10. Voice Generation
11. FFmpeg Render
12. Thumbnail (opsiyonel, `thumbnail_enabled` ise çalışır)

### Çalışan özellikler

- DeepSeek metin sağlayıcısı
- Çok dilli proje metadata sistemi
- Türkçe araştırma, senaryo ve narration üretimi
- Storyboard visual alanlarının İngilizce oluşturulması
- Pexels görsel arama
- Pexels video arama ve indirme
- Sahne bazlı medya klasörleri
- Sahne bazlı narration metinleri
- Ses süresine göre sahne süresini ayarlama
- FFmpeg ile sesli final MP4 üretme
- Pipeline state kaydı
- Hatalı projeyi resume etme
- Tamamlanan aşamaları atlama
- eSpeak provider
- Piper provider
- Supertonic provider
- Supertonic M1/M2/M3/M4/M5/F1/F2/F3/F4/F5 sesleri
- CLI üzerinde provider, voice ve speed seçenekleri (temel `build` komutu hâlâ sadece `--language`/`--template` alıyor; tam ayarlar sadece web wizard üzerinden)
- **`content_type` gerçekten prompt davranışını değiştiriyor** — documentary/news/shorts/informational için research/script/storyboard/narration prompt'ları farklı
- **`target_duration_seconds` gerçekten script uzunluğunu ve storyboard sahne sayısını etkiliyor** (prompt seviyesinde; kod tarafında sert bir sahne-sayısı validator'ı yok)
- **`media_mode` gerçekten MediaBuilder'ı yönlendiriyor** — video/image/mixed modlarına göre doğru sağlayıcılar çağrılıyor, mixed'te video-önce + foto fallback
- **`resolution`/`fps` gerçekten RenderService'e bağlı** — project.json'dan okunuyor, ffmpeg filtrelerinde kullanılıyor, hardcoded 1280x720 yok
- **`voice_name` artık gerçekten TTS provider'a gidiyor** (önceden parametre alınıyordu ama synthesize()'a hiç geçilmiyordu — düzeltildi)
- **Aynı başlıkla ikinci proje açılırsa artık sessizce üzerine yazmıyor** — `_2`, `_3` gibi çakışmasız slug veriliyor
- **Web servisi restart olursa job durumu kaybolmuyor** — `jobs/<job_id>.json`'a yazılıyor, başlangıçta `queued`/`running` işler otomatik devam ettiriliyor
- **`background_music_enabled` gerçekten çalışıyor** — `projects/<proje>/music/` klasöründeki (veya `music_track` ile belirtilen) dosya loop/trim edilip narration'dan düşük seviyede mixleniyor, sonunda fade-out var
- **`subtitles_enabled` gerçekten çalışıyor** — sahne bazlı zamanlamalı `render/subtitles.srt` üretiliyor (Türkçe karakterler doğru). Henüz videoya burn-in edilmiyor, sadece sidecar dosya.
- **`thumbnail_enabled` gerçekten çalışıyor** — yeni `ThumbnailService`, ffmpeg ile 1280x720 YouTube kapağı + shorts/dikey projelerde ek 1080x1920 kapak üretiyor (Pillow değil, sadece ffmpeg drawtext)
- Web wizard artık içerik türü, hedef süre, medya modu, çözünürlük, FPS, ses sağlayıcısı/ismi/hızı, müzik/altyazı/thumbnail toggle'larını gösteriyor
- **XTTS klon ses provider eklendi** — Instagram bot projesindeki (`hakanerbasss.github.io`, `supertonic-web/xtts_clone.py`, branch `claude/arduino-smart-home-uj82ef`) çalışan yaklaşımın birebir portu: Coqui XTTS-v2, referans sesten klonlama, cümle bazlı chunking. `torch`/`TTS` sadece gerektiğinde import ediliyor, DocuForge'un geri kalanına bağımlılık eklemiyor. Referans ses `XTTS_REFERENCE_AUDIO` env var veya `models/xtts/reference.wav`'dan okunuyor.
- **Web sitesinde her aşamayı ayrı ayrı yeniden üretme artık var** — proje detay sayfasında her aşamanın yanında "Yeniden Üret" butonu var (o aşamayı VE sonrasındaki her şeyi geçersiz kılıp sadece o aşamayı hemen yeniden üretiyor), artı "▶ Devam Et" butonu kalanını tamamlıyor. `BuildPipeline.regenerate_step()` bunun arkasındaki mantık.
- Ana sayfaya "+ Yeni Proje" butonu eklendi (önceden `/new`'e giden hiçbir link yoktu)
- Proje detay sayfasında artık thumbnail görseli ve subtitles.srt indirme linki gösteriliyor
- İlerleme çubuğu artık gerçek aşama ismini gösteriyor, toplam aşama sayısı thumbnail'e göre dinamik (10 veya 11)

---

## Doğrulanmış çıktılar

### Kara Delikler

- 25 sahne
- Pexels videoları
- Sahne bazlı ses
- Sesli final video
- Resume çalışıyor

### Volkanların Gizli Dünyası

- Türkçe research
- Türkçe script ve narration
- İngilizce visual aramaları
- 25 sahne
- Pexels videoları
- Supertonic testi başarılı
- Final video üretildi
- Resume 10/10 aşamayı atlıyor

### Ayarların gerçekten bağlı olduğu doğrulama (cloud dev container, izole testler)

Gerçek uçtan uca bir render bu ortamda test edilemedi (DeepSeek/Pexels API anahtarı,
Piper/Supertonic modelleri ve ffmpeg bu container'da yok). Bunun yerine her düzeltme
stub/mock provider'larla izole test edildi:

- Slug çakışma koruması (`_2`, `_3` ekleniyor) — geçti
- `voice_name`'in gerçekten `synthesize()`'a gittiği — geçti
- Restart sonrası job'ın `resume()`/`run()` ile devam ettirildiği — geçti
- Müzik mixleme ffmpeg komutunun doğru kurulduğu (volume, fade, amix) — geçti
- SRT zamanlamasının gerçek sahne sürelerine göre doğru hesaplandığı, Türkçe karakterlerin korunduğu — geçti
- Thumbnail için sahne görseli/video kare çıkarma ve metin escape'lemesi — geçti
- XTTS metin chunking (400 token limiti için cümle/virgül bölme), referans ses çözümleme (explicit path → env var → default path → hata) — geçti
- `regenerate_step()`: script'i yeniden üretince storyboard/media/audio/render/thumbnail'in silindiği, `voice`'u yeniden üretince SADECE ses dosyasının silinip narration metninin korunduğu (manifest silinmeden status resetleniyor) — geçti
- Web endpoint'leri (`/api/projects/{slug}/regenerate/{step}`, `/resume`) ve restart-sonrası "kind"a göre doğru fonksiyona dispatch edilmesi — geçti

**Bir sonraki oturumda gerçek bir VPS build'i (shorts/vertical/mixed, gerçek API anahtarlarıyla) çalıştırılıp çıktı gözle doğrulanmalı. XTTS de gerçek referans sesle bir kere denenmeli.**

---

## Mevcut ses sağlayıcıları

### eSpeak

- Çalışıyor
- Kalitesi düşük
- Acil yedek

### Piper

- Çalışıyor
- Türkçe Fahrettin modeli kuruldu
- Cümle boşluklarında cızırtı gözlendi
- **Henüz düzeltilmedi** — gerçek ses dinlemeden (loudnorm/highpass/crossfade gibi) kör düzeltme yapılmadı, kasıtlı olarak ertelendi
- Varsayılan olmayacak

### Supertonic

- Doğrudan DocuForge ortamında çalışıyor
- Instagram botuna bağlı değil
- M1/M2/M3/M4/M5/F1/F2/F3/F4/F5
- Kullanıcı M1 testini beğendi
- `voice_name` artık gerçekten iletiliyor (önceki bug düzeltildi)
- Varsayılan ses sağlayıcısı

### XTTS-v2

- **Eklendi** — `app/providers/voice/xtts.py`, provider registry'de `"xtts"` olarak kayıtlı
- Instagram bot'taki çalışan koddan birebir port edildi (chunking, speaker_wav cloning, sample rate 24000)
- Web wizard'da ses sağlayıcısı olarak seçilebiliyor
- **Test edilmedi** — bu container'da torch/coqui-tts/gerçek referans ses yok; sadece saf Python mantığı (chunking, referans ses çözümleme, hız normalizasyonu) izole test edildi. VPS'de gerçek bir referans ses dosyasıyla ilk kullanımda doğrulanmalı.
- RAM notu: Instagram bot'un kendi `ses-klonu/README.md`'si eski/farklı bir sunucu planını (CX23, 4GB) varsayıp XTTS-v2 için yetersiz olabileceğini söylüyordu, ama kullanıcı gerçek sunucusunun **Hetzner CX33 (8GB RAM)** olduğunu doğruladı — bu, XTTS-v2'nin CPU üzerinde çalışması için genelde yeterli (model + inference tipik olarak 4-6GB civarı kullanıyor). Yine de web paneli + diğer servisler (varsa Instagram/haber botları) aynı anda çalışıyorsa dikkatli olunmalı; ilk kullanımda gerçek bir referans sesle denenip RAM sorunu çıkıp çıkmadığı kontrol edilmeli.

---

## Web panelinin mevcut durumu

### Var

- Proje listesi + "+ Yeni Proje" butonu
- Proje detay sayfası: final video oynatıcı, thumbnail önizleme, subtitles.srt indirme
- Pipeline aşamalarını gösterme — gerçek aşama ismiyle, dinamik toplam sayıyla
- Tam yeni proje formu: içerik türü, hedef süre, medya modu, çözünürlük, FPS, ses sağlayıcısı/ismi/hızı (xtts dahil), müzik/altyazı/thumbnail toggle'ları
- Job durumu kalıcı (`jobs/<job_id>.json`), restart sonrası kayıp yok (build VE regenerate işleri için)
- **Resume butonu ("▶ Devam Et")** — proje detay sayfasında, `POST /api/projects/{slug}/resume`
- **Yeniden üretme butonları** — her aşama için ayrı "Yeniden Üret", `POST /api/projects/{slug}/regenerate/{step_key}`
- **`/settings` sayfası** — Instagram bot'taki (`supertonic-web/app.py`'nin `/api/*/config` endpoint'leri) aynı deseni izliyor: her API key için ✓ yapılandırılmış / Değiştir durumu ya da input+Kaydet formu. `secrets.json`'a yazılıyor (gitignore'da), hemen etkili oluyor — restart gerekmiyor. Bir env var aynı isimde ayarlıysa o öncelikli olur ve arayüzden değiştirilemez. Her sayfanın header'ında "⚙ Ayarlar" linki var. **Yeni bağımlılık:** `python-multipart` (form POST'ları için) — kuruluma eklendi.
- **Ana sayfada "Devam eden üretimler" bölümü** — kullanıcı "üretim başlatıp ana sayfaya geçince her şey kayboluyor" diye bildirdi. Kök neden muhtemelen backend'in ölmesi değil (systemd servis dosyası kontrol edildi: `--reload` yok, tek worker, temiz), sadece hiçbir yerde görünürlüğü yoktu — `/new` sayfasının ilerleme takibi o sayfanın JS belleğinde yaşıyordu, oradan ayrılınca kayboluyordu, ana sayfa da yeni başlayan projeler için anlamlı bir durum göstermiyordu ("Durum: created"). Yeni `GET /api/jobs/active` endpoint'i `jobs/*.json`'dan disk üzerinden okuyor (hiçbir sayfaya bağlı değil), ana sayfa 4 saniyede bir polling yapıp gerçek ilerlemeyi gösteriyor. **Doğrulanmadı** — kullanıcının bunu VPS'de tekrar denemesi bekleniyor; eğer üretim GERÇEKTEN duruyorsa (sadece görünmüyor değil), bu düzeltme yeterli olmayacak ve `jobs/*.json` + `journalctl -u docuforge-web` çıktısına daha derin bakılması gerekecek.

### Eksik

- Gerçek canlı log (sadece pipeline_state.json polling var)
- İptal butonu (çalışan bir işi durdurma)
- Sesleri arayüzden dinleme
- Sahne ve medya düzenleme
- ~~Müzik dosyası yükleme arayüzü~~ — kısmen: dosyayı hâlâ SSH ile `music/` klasörüne koymak gerekiyor, ama artık alternatif olarak Jamendo/Mubert sağlayıcılarından otomatik müzik çekilebiliyor (bkz. "Thumbnail indirme, SEO kopyalama, XTTS ses yükleme/kayıt, müzik sağlayıcıları")
- ~~XTTS referans ses dosyasının kendisini yükleme arayüzü~~ ✅ tamamlandı — `/settings`'ten dosya yükleme ve mikrofon kaydı
- **Yeniden Üret'te ayar değiştirme eklendi** — kullanıcı "sesi/görseli/dili beğenmezsem değiştirebilmeliyim" dedi. Artık `research` (dil/içerik türü/süre), `voice` (sağlayıcı/isim/hız), `media` (görsel/video sağlayıcı), `render` (çözünürlük/fps/müzik/altyazı/burn-in) aşamalarını yeniden üretirken ayarları değiştirebiliyorsun — "Yeniden Üret" butonu artık önce ilgili ayarları gösteren bir form açıyor. `GET /api/projects/{slug}/step-options/{step_key}` hangi alanların değişebileceğini ve mevcut değerleri dönüyor.
- **Altyazı burn-in eklendi** — `subtitles_burn_in` ayarı, ffmpeg'in `subtitles` filtresiyle (libass) videoya gerçekten gömüyor. **Test edilmedi** — bu container'da gerçek ffmpeg/libass yok, sadece komut kurulumu doğrulandı. VPS'de gerçek bir video ile denenmeli.
- **`/new` ve ana sayfa artık aktif işleri gösteriyor** — kullanıcı "üretim başlatıp sayfa değiştirince kayboluyor" diye bildirdi. `journalctl` logu incelendi: üretim ASLA durmamış, sadece hiçbir yerde görünmüyordu. `GET /api/jobs/active` artık her iki sayfada da 4 saniyede bir poll ediliyor.

---

## Henüz yapılmayan ana özellikler

- Otomatik ducking (şu an sabit düşük seviye, sidechain compress değil)
- Piper ses temizleme / normalizasyon / mastering
- ~~XTTS referans ses yükleme arayüzü~~ ✅ tamamlandı
- ~~Kapak üzerine çarpıcı/trend başlık yazısı + birden fazla dönüşümlü şablon~~ ✅ tamamlandı — bkz. "Thumbnail şablonları + çarpıcı başlık tasarımı"
- Thumbnail düzenleme (arayüzden başlığı/şablonu manuel değiştirme) — şu an tamamen otomatik, kullanıcı müdahale edemiyor
- ~~Başlık, açıklama ve etiket (SEO) üretimi~~ ✅ tamamlandı — `SEOAgent`, `seo.json`, proje detay sayfasında gösteriliyor
- ~~`image_prompts.json`/`video_prompts.json`'ın AI üretim sağlayıcılarına bağlanması~~ ✅ tamamlandı — `MediaBuilder` artık provider tipine göre ayrım yapıyor (`_is_generation_provider`: stock sağlayıcılarda `.search()` var, üretim sağlayıcılarında yok). Üretim sağlayıcısı seçiliyse sahnenin zengin prompt'u kullanılıyor (video prompt'larında `camera_motion` da ekleniyor), stock sağlayıcılarda eskisi gibi kısa storyboard `visual` metni kullanılıyor. Bonus: bu düzeltmeden önce `MediaBuilder` doğrudan `provider.search()` çağırıyordu — üretim sağlayıcılarında bu metod hiç yok, yani prompt'u görmezden gelmenin ötesinde, seçilse muhtemelen `AttributeError` ile çökerdi.
- YouTube yükleme
- Instagram/Reels sürümü
- Kalıcı iş kuyruğu (şu an per-request thread + disk üzerinde JSON; gerçek bir queue değil)
- Kullanıcı hesabı ve güvenlik

## Ek görsel/video üretim araçları

**Tamamlandı** — Pexels artık tek seçenek değil. Temmuz 2026 itibariyle piyasa araştırması yapıldı (fiyat/kalite karşılaştırması), kullanıcı 4 kategoriden hepsini seçti, hepsi eklendi:

- **Ücretsiz stok:** Pixabay (görsel+video), Unsplash (sadece görsel) — Pexels ile aynı arama tabanlı yaklaşım
- **DALL-E / OpenAI Images** (`gpt-image-1`) — `openai` paketi zaten bağımlılık (DeepSeek için), en kolay entegrasyon
- **Google Imagen (görsel) + Veo (video)** — Gemini API düz REST, yeni SDK yok. Veo async: submit → `operations.get` ile poll → indir
- **fal.ai aggregator** (görsel+video) — queue REST API, tek entegrasyonla Flux/Kling/yüzlerce model. Hangi model kullanılacağı `options["model"]` ile seçiliyor (varsayılan: `fal-ai/flux/schnell` görsel, `fal-ai/kling-video/v1.6/standard/text-to-video` video)

**Doğrulanmadı:** Bu container'da hiçbirinin gerçek API anahtarı yok, gerçek trafiğe karşı test edilemedi — sadece dokümante edilmiş request/response şekillerine göre mock HTTP ile test edildi. Özellikle Veo'nun `response.generateVideoResponse.generatedSamples[0].video.uri` alanının gerçekten indirilebilir bir URL mi yoksa Files API mi gerektirdiği belirsiz — gerçek anahtarla doğrulanmalı.

**Bonus bug fix:** Bu işi test ederken `/new` sayfasının (yeni proje sihirbazı) TAMAMEN bozuk olduğunu keşfettim — kodda üç yerde gerçek emoji yerine bozuk `📝` gibi lone-surrogate escape'ler vardı (JS/JSON'da geçerli ama Python'da astral karaktere birleşmiyor), bu yüzden `GET /new` her istekte `UnicodeEncodeError` ile 500 veriyordu. Muhtemelen daha önce kimse sayfayı gerçekten render edip test etmemiş. Düzeltildi.

---

## Thumbnail indirme, SEO kopyalama, XTTS ses yükleme/kayıt, müzik sağlayıcıları

Kullanıcının "thumbnail indirme özelliği, başlık/etiket/açıklama için ayrı kopyalama butonları, klon ses için referans ses yükleme+kayıt, müzik için telifsiz/AI sağlayıcı seçimi" talebi üzerine eklendi:

- **Thumbnail indirme** — proje detay sayfasında her kapak görselinin altında görünür "⬇ İndir (16:9)" / "⬇ İndir (9:16)" butonu var (önceden sadece görsele tıklayınca yeni sekmede açılıyordu).
- **SEO kopyalama butonları** — her başlık önerisi, açıklama ve etiketler (virgülle birleştirilmiş) için ayrı "📋 Kopyala" butonu (`copyToClipboard`, tarayıcı Clipboard API).
- **XTTS referans ses yükleme + kayıt** — `/settings` sayfasında XTTS alanı artık sadece dosya yolu yazmakla kalmıyor: dosya yükleme (`POST /settings/xtts_reference_audio/upload`, ffmpeg ile `-ar 24000 -ac 1` mono WAV'a çeviriyor) ve tarayıcıdan doğrudan mikrofonla kayıt (`MediaRecorder`/`getUserMedia`) destekleniyor. **Önemli kısıtlama:** mikrofon kaydı sadece güvenli bağlamda (HTTPS veya localhost) çalışır — site şu an düz HTTP olduğu için kullanıcı tarayıcıda mikrofon izni alamayabilir; JS bunu algılayıp uyarı veriyor, dosya yükleme her durumda çalışır.
- **Müzik sağlayıcıları** — `background_music_enabled` açıkken artık bir "Müzik Sağlayıcı" seçimi var: `local` (mevcut `music/` klasörü davranışı, varsayılan), `jamendo` (Jamendo — telifsiz müzik API'si, `client_id` ile arama/indirme), `mubert` (Mubert — yapay zeka ile prompt'tan müzik üretimi). Sağlayıcı seçiliyse `RenderService` render aşamasında `content_type`'a göre bir mood sorgusu oluşturup (`documentary`→"cinematic documentary ambient" vb.) o sağlayıcıdan müzik indiriyor; `music/` klasöründe zaten dosya varsa veya `local` seçiliyse eskisi gibi davranıyor. API anahtarları (`JAMENDO_CLIENT_ID`, `MUBERT_COMPANY_ID`, `MUBERT_LICENSE_TOKEN`) `/settings` sayfasından girilebiliyor. `render` adımını "Yeniden Üret" ile de değiştirilebiliyor.
  - **Test edilmedi:** Jamendo ve Mubert'in gerçek API çağrıları bu container'da denenmedi (API key yok) — sadece dokümante edilmiş request/response şekline göre mock HTTP testleriyle doğrulandı.
  - **Mubert özellikle belirsiz:** API şeması (2 adımlı auth: `/customers` → `/public/tracks`) resmi dokümantasyon yerine genel bilgiye dayanarak yazıldı, gerçek bir Mubert hesabıyla doğrulanmadı. Gerçek kullanımdan önce mutlaka kontrol edilmeli.

---

## Thumbnail şablonları + çarpıcı başlık tasarımı (v2 — tam yeniden yazım)

İlk versiyon (ffmpeg `drawtext`/`drawbox` ile 4 basit rotasyonlu şablon, sadece metin konumu değişen) kullanıcının referans görselleriyle ("SON DAKİKA" tarzı Instagram haber botu tasarımları) karşılaştırıldığında yetersiz bulundu: "resim + altta siyah bant + küçük yazı kabul edilmeyecek" dendi. `ThumbnailService` sıfırdan, Pillow tabanlı olarak yeniden yazıldı:

- **SEO creative brief:** `SEOAgent` artık `titles`/`description`/`tags`'e ek olarak `thumbnail_hook` (3-6 kelime, video başlığının aynısı DEĞİL), `main_subject`, `emotional_trigger`, `visual_contrast`, `text_overlay`, `avoid_elements` üretiyor (`app/prompts/seo.txt`, `app/agents/seo.py`). Bu alanlar best-effort: eksik/bozuk gelirse boş string'e düşer, `titles`/`description`/`tags` üretimini asla bozmaz. `ThumbnailService._build_brief()` bunlardan bir "brief" oluşturuyor, eksik alanlar için mantıklı varsayılanlara (proje başlığından kısaltma vb.) düşüyor.
- **En güçlü kare seçimi:** `_select_best_frame()` her sahneden bir aday görsel/video-karesi toplayıp (`_score_frame`) kenar yoğunluğu (Pillow `FIND_EDGES`) + kontrast (stddev) skoruna göre en güçlüsünü seçiyor — ayrı bir CV/ML bağımlılığı yok, salt Pillow.
- **4 tamamen farklı kompozisyon** (`app/services/thumbnail_service.py`, sırasıyla `thumbnail_1..4.png`):
  - **Split Contrast** — dikey ikiye bölünmüş kare (sol soğuk/gri tonlama, sağ sıcak/doygun), beyaz ayraç çizgisi, üstte ortalanmış sarı vurgu başlık.
  - **Mystery Focus** — merkeze odaklı "tilt-shift" efekti (Pillow radial mask ile net merkez + bulanık/karanlık kenar), vignette, alt-sol köşede beyaz başlık.
  - **Documentary Cinematic** — üstten aşağı doğru kararan gradient (alt bant YOK), üst-solda başlık, sinematik renk/kontrast ayarı.
  - **Breaking Discovery** — hafif "dutch angle" döndürme (oversample + `expand=True` rotate + merkezi crop — döndürme köşelerinde siyah boşluk kalmaması için özenle hesaplandı), sağ-üstte kırmızı vurgu etiketi (`emotional_trigger` metni), başlıkta rakam varsa o kelime ayrıca çok büyük punto ile basılıyor ("Büyük Sayı" efekti).
- **Arka plan görseli:** kompozisyona özel bir prompt ile (video başlığı DEĞİL, `main_subject`/`emotional_trigger`/`visual_contrast` temelli sahne tarifi — örn. "Split-screen photorealistic composition... leave clean negative space for a short title... No text, no watermark") `dalle` sağlayıcısından (provider registry üzerinden, `app/providers/image/dalle.py`) görsel üretiliyor. Görsel API'sinden **kesinlikle metin istenmiyor** (Türkçe yazım hatası riski) — başlık her zaman ayrıca Pillow ile ekleniyor. Üretim başarısız olursa (yakalanıp loglanıyor), o şablon otomatik olarak gerçek sahne karesine düşüyor.
- **Başlık kuralları:** Metin her zaman kısa hook (3-6 kelime, `thumbnail_hook`), asla video başlığının tamamı değil. Kalın font + siyah stroke + gölge, Pillow `draw.text(..., stroke_width=, stroke_fill=)` ile. **Otomatik küçülterek sığdırma** (`_fit_text_lines`): metin verilen satır sayısına sığmıyorsa kelime KIRPILMIYOR, font küçültülüyor (min %45'e kadar) — önceki versiyonda uzun hook'ların son kelimesi sessizce siliniyordu, bu düzeltildi.
- **Türkçe büyük harf düzeltmesi:** Python'un `str.upper()`'ı Türkçe 'i'yi 'I' yapıp noktalı 'İ'yi kaybediyor — `_turkish_upper()` bunu düzeltiyor.
- **4 varyant + seçim:** Her üretimde `thumbnail_1.png`..`thumbnail_4.png` oluşuyor, `content_type`'a göre biri (news/shorts→Breaking Discovery, documentary→Documentary Cinematic, informational→Split Contrast) otomatik olarak `thumbnail.jpg` (kanonik) yapılıyor ve `project.json`'a `thumbnail_selected` yazılıyor. Proje sayfasında 4'ü de yan yana gösteriliyor, her birinin **İndir** butonu var, **Bunu Seç** butonuyla (`POST /api/projects/{slug}/thumbnail/select`) kullanıcı istediğini kanonik yapabiliyor. Dikey kapak (`thumbnail_vertical.jpg`, shorts/dikey projelerde) seçilen varyantın aynı arka planından yeniden komponse ediliyor — ek bir AI çağrısı gerekmiyor.
- **Eski projelerle uyumluluk:** Sadece tek `thumbnail.jpg`'si olan (yeni varyant sistemi öncesi) projeler proje sayfasında hâlâ gösteriliyor — varyant kartları yoksa eski görsel + indir butonu tek başına render ediliyor.
- **Test edildi (bu container'da gerçek OpenAI key/ffmpeg yok):** SEO brief fallback mantığı, en-güçlü-kare skorlama, 4 şablonun her biri (sahte oluşturulmuş PNG sahne görselleriyle) gerçekten farklı kompozisyon üretiyor mu (görsel olarak da kontrol edildi), döndürme köşelerinde siyah artefakt kalmadığı, uzun hook metninin kırpılmadan küçültüldüğü, seçim endpoint'i (path traversal / geçersiz varyant reddediliyor), `BuildPipeline`'ın thumbnail adımını hâlâ doğru çalıştırdığı, `_invalidate_step`'in artık 4 varyant + dikey dosyayı da temizlediği. **Doğrulanamadı:** gerçek bir OpenAI API anahtarıyla gerçek gpt-image-1 çağrısı (maliyet + bu ortamda anahtar yok) — VPS'de `OPENAI_API_KEY` girilip ilk üretimde kontrol edilmeli.

---

## Proje silme + maliyet-bilinçli kapak kaynağı seçimi

Kullanıcı sunucu disk alanının birikmesini sordu ("üretilen içerikler sunucuda birikip yer mi kaplıyor, silme özelliği var mı") ve iki ek talep verdi: (1) proje silme özelliği, (2) thumbnail'de ücretli AI kullanılıyorsa maliyeti azaltmak için sadece 1 kapak, ücretsizse 4 kapak üretilsin, ayrıca Pexels stok görseli de bir kaynak seçeneği olsun.

- **Proje silme:** `DELETE /api/projects/{slug}` (`app/web_new_project.py`) — proje klasörünü tamamen siliyor (`shutil.rmtree`). O proje için `queued`/`running` durumda bir iş varsa **409** ile reddediyor (arka plan thread'i silinen bir klasöre yazmaya çalışıp çökmesin diye). Path traversal'a karşı `PROJECTS_ROOT` sınırı kontrol ediliyor. Hem proje detay sayfasında ("🗑 Projeyi Sil") hem ana sayfadaki her proje kartında ("🗑 Sil") onay diyaloglu (`confirm()`) buton olarak eklendi — geri alınamaz olduğu açıkça belirtiliyor.
- **`thumbnail_source` ayarı** (`project.json`, `DocumentaryProject.THUMBNAIL_SOURCES = {"auto","ai","pexels","scene"}`):
  - `ai` — sadece **1 kapak** üretir (o an `content_type`'a göre seçilecek varsayılan şablon), OpenAI'ye tek bir gpt-image-1 çağrısı gider. Maliyeti sabit ve düşük tutmak için diğer 3 şablon hiç denenmiyor.
  - `pexels` — **4 kapak**, her şablon için ayrı bir Pexels arama sorgusuyla (`main_subject` + şablona özgü ruh hali kelimesi: "contrast"/"dark moody"/"cinematic"/"dramatic") stok fotoğraf indiriliyor. Ücretsiz (Pexels API key yeterli).
  - `scene` — **4 kapak**, hepsi gerçek sahne karesinden (eskisi gibi, hiç API çağrısı yok).
  - `auto` (varsayılan) — Pexels key varsa `pexels`, yoksa (sadece) OpenAI key varsa `ai`, o da yoksa `scene` — yani maliyetsiz seçenek varken otomatik olarak ücretliye geçmiyor; kullanıcı bilerek `ai` seçmedikçe para harcanmıyor.
  - Her `generate()` çağrısı önce mevcut `thumbnail_1..4.png` dosyalarını temizliyor, böylece bir moddan diğerine geçince (örn. `pexels`'in 4 varyantından `ai`'ın 1 varyantına) eski/uyumsuz dosyalar proje sayfasında görünmeye devam etmiyor.
  - `/new` sihirbazında "Kapak Görseli Kaynağı" açılır kutusu eklendi (thumbnail_enabled açıkken görünüyor); `render` adımına benzer şekilde `thumbnail` adımı da artık "Yeniden Üret" formunda bu ayarı değiştirmeye izin veriyor (`STEP_ALLOWED_OVERRIDES["thumbnail"] = {"thumbnail_source"}`).
- **Test edildi:** silme endpoint'i (normal silme, olmayan proje, path traversal, aktif iş varken engelleniyor, iş bitince tekrar denenince başarılı), her 3 kaynak modunun doğru varyant sayısını ürettiği (mock DALL-E/Pexels ile), `auto` çözümlemesinin doğru öncelik sırasını izlediği, mod değişince eski varyantların temizlendiği, `BuildPipeline.regenerate_step`'in `thumbnail_source` override'ını kabul edip diğer alanları reddettiği, tüm sayfaların (`/`, `/new`, `/settings`, proje detay) hâlâ hatasız render olduğu ve JS'in sözdizimsel olarak geçerli olduğu.

---

## Storyboard JSON kesilmesi düzeltmesi

Kullanıcı gerçek üretimde `Storyboard failed: ... Unterminated string ...` hatası aldı. Kök neden: `app/ai/deepseek.py`'de tüm metin üretimleri için `max_tokens=4000` sabitti. Türkçe metin İngilizce'ye göre token başına daha az karakter sığdırıyor, bu yüzden uzun belgesellerde (20-35 sahneli storyboard JSON'u) 4000 token dolup DeepSeek'in yanıtı bir string'in ortasında kesiliyordu — 3 deneme de aynı noktada takılıyordu çünkü aynı prompt her seferinde benzer uzunlukta çıktı istiyor. **Düzeltme:** `max_tokens` `deepseek-chat`'in izin verdiği maksimuma (`8192`) çıkarıldı. Çok daha uzun belgesellerde (40+ dakika, 50+ sahne) bu bile yetersiz kalabilir — böyle bir durum bildirilirse storyboard'u parçalı (birden fazla API çağrısıyla) üretecek kalıcı bir çözüm gerekir.

---

## Canlı üretim ilerlemesi (proje sayfası)

Kullanıcı "kalanları üret diyorum sıra hangisinde belli olmuyor hepsinde pending yazıyor" diye bildirdi. Kök neden: proje detay sayfasındaki aşama listesi `pipeline_state.json`'ın sayfa yüklenirken alınan statik bir görüntüsüydü — "Devam Et"/"Yeniden Üret" sırasında tamamlanmamış her aşama sadece "pending" gösteriyordu, hangisinin GERÇEKTEN çalıştığı belli olmuyordu, iş bitip sayfa yeniden yüklenene kadar donmuş gibi görünüyordu.

- `compute_pipeline_progress()` (`app/web_new_project.py`) artık `current_step_key` ve `failed_step_key` de döndürüyor (sadece biçimlendirilmiş bir etiket string'i değil, ham adım anahtarı).
- Proje sayfasındaki her aşama satırı `data-step-index`/`data-step-key` taşıyor. Yeni `applyStepProgress()` JS fonksiyonu, `current_step_key`'e denk gelen satırı vurguluyor ("şu an çalışıyor...", mavi arka plan), öncesindekileri ✅ tamamlandı yapıyor, `failed_step_key` varsa o satırı ❌ işaretliyor.
- `resumeProject`/`regenerateStep`'in her poll turunda bu fonksiyon çağrılıyor. Ayrıca yeni `checkForActiveJob()` sayfa yüklenirken çalışıyor: bu proje için başka bir yerden başlamış (örn. ana sayfadan) devam eden bir iş varsa onu da otomatik algılayıp canlı ilerlemeyi hemen gösteriyor, "Devam Et" butonunu geçici olarak devre dışı bırakıyor (yanlışlıkla ikinci bir üretim başlatılmasın diye).
- **Test edildi:** `current_step_key`/`failed_step_key` değerleri (çalışan ve başarısız durumlarda), yeni data attribute'ların ve JS fonksiyonlarının render edilen sayfada bulunduğu, tüm sayfaların hâlâ hatasız render olduğu.

---

## PWA desteği (iOS/Android'de "uygulama gibi" açılma)

Kullanıcı DocuForge web panelini telefonda ana ekrana eklenebilir, tam ekran açılan bir PWA yapmak istedi. Önce altyapı adımları birlikte tamamlandı:

- **Domain + HTTPS:** `docuforge.wizaicorp.com` (Cloudflare, Proxied) → `77.42.45.229` eklendi. Sunucuda nginx reverse proxy (`/etc/nginx/sites-available/docuforge`, `panel.wizaicorp.com` ile birebir aynı desen) `127.0.0.1:8090`'a yönlendiriyor; `certbot --nginx -d docuforge.wizaicorp.com` ile Let's Encrypt sertifikası kuruldu. Cloudflare SSL/TLS modu "Full (strict)" olduğu için sunucuda geçerli bir sertifika şarttı — certbot bunu sağlıyor.
- **PWA dosyaları** (`app/static/`, `web.py`'de `StaticFiles` ile mount edildi):
  - `manifest.json` — açık tema renkleri (`background_color: #f4f7fb`, `theme_color: #2166f3` — sitenin kendi renk şeması, karanlık tema YOK, kullanıcı özellikle istemedi), `display: standalone`.
  - `icons/icon.svg` + `icon-192.png`/`icon-512.png`/`icon-180.png` — Pillow ile üretildi, sitenin header'ındaki mavi kare + beyaz "D" logosunun birebir aynısı.
  - `sw.js` — **kasıtlı olarak minimal**: sadece `/static/*` (manifest, ikonlar) cache-first; her sayfa render'ı ve `/api/`/`/files/` istekleri HER ZAMAN doğrudan ağa gidiyor. Çünkü DocuForge'un HTML'i statik bir "app shell" değil, sunucu tarafında canlı üretilen durumun kendisi (iş ilerlemesi, proje listesi) — önbelleğe alınsa offline'da (hatta online'da) eski/yanlış bir durum gösterebilirdi. Service worker esasen "yüklenebilirlik" şartını karşılamak için var, gerçek offline işlevsellik sağlamıyor.
  - Üç bağımsız `<head>` bloğuna (`web.py`'nin `page()`'i, `/new`, `/settings`) manifest link + `apple-mobile-web-app-*` meta etiketleri + service worker kayıt script'i eklendi (paylaşılan tek bir template olmadığı için üçüne de ayrı ayrı, "⚙ Ayarlar" linkiyle aynı sebepten).
- **Test edildi:** `/static/manifest.json`/`sw.js`/ikonların doğru content-type ile servis edildiği, dört sayfanın da (`/`, `/new`, `/settings`, proje detay) manifest link + SW kayıt script'i içerdiği, tüm JS'in sözdizimsel geçerliliği. **Doğrulanamadı:** gerçek bir telefonda "Ana Ekrana Ekle" akışının uçtan uca denenmesi — kullanıcı `https://docuforge.wizaicorp.com`'u telefonunda ziyaret edip denemeli.

---

## Üretim iptal özelliği + stale "başarısız" gösterge hatası

Kullanıcı canlı bir üretimde şunu yaşadı: sunucuyu güncelleyip restart ederken render aşaması ortasında kesildi, "Devam Et" ile yeniden denedi, ama proje sayfası render'ı hâlâ kırmızı "başarısız" gösteriyordu ve ilerleme görünmüyordu — oysa `journalctl` render'ın gerçekten sahne sahne ilerlediğini gösteriyordu.

- **Kök neden bulundu:** `pipeline_state.json`'daki `failed_step` alanı sadece bir adım BAŞARILI olunca temizleniyordu (`_record_success`), bir adım yeniden denenmeye BAŞLARKEN temizlenmiyordu. Yani "Devam Et" ile render'ı yeniden denerken, o adım gerçekten çalışıyor olsa bile, canlı ilerleme sorgusu hâlâ önceki denemeden kalma "Hata: Video Render" bilgisini okuyup gösteriyordu — proje gerçekten takılı değildi, sadece eski hata bilgisi silinmemişti.
- **Düzeltme:** `_run_agent_step` ve `_run_service_step`, bir adımı gerçekten (yeniden) çalıştırmaya başlar başlamaz `state["failed_step"] = None` yazıp diske kaydediyor — artık canlı bir sorgu, adım gerçekten sürerken asla eski "başarısız" bilgisini görmüyor. Adım gerçekten yine başarısız olursa `_record_failure_and_raise` zaten doğru şekilde tekrar işaretliyor.
- **Üretim iptal özelliği** ("devredışı olduğunda iptal et seçeneği olabilir" isteği üzerine): Python thread'leri güvenle zorla durdurulamadığı için iptal **cooperative** (işbirlikçi) — sadece adımlar ARASINDA kontrol ediliyor, çalışan bir AI çağrısı veya ffmpeg render'ı anında kesilmiyor, mevcut adım bitince duruyor.
  - `BuildPipeline.PipelineCancelled` exception'ı + `run()`/`resume()`'a eklenen opsiyonel `cancel_event: threading.Event` parametresi, `_run_pipeline`'da her adımdan önce kontrol ediliyor (`_check_cancelled`).
  - `regenerate_step`'e eklenmedi — tek adımlık bir işlem olduğu için adımlar arası doğal bir durma noktası yok.
  - Backend: `CANCEL_EVENTS: dict[job_id, threading.Event]` (bellekte, JOBS gibi diske kalıcı değil — restart zaten eski thread'i öldürüyor, `_recover_jobs_from_disk` yeniden başlattığı işler için taze bir event oluşturuyor). Yeni `POST /api/builds/{job_id}/cancel` endpoint'i event'i set ediyor. İş `PipelineCancelled` ile biterse job durumu `"cancelled"` oluyor (`"failed"`'dan ayrı).
  - Frontend: `/new` sihirbazının durum kutusunda, hem `/new` hem ana sayfadaki "Devam eden üretim(ler)" kartlarında, proje detay sayfasında "Devam Et" yanında — hepsinde "⏹ İptal Et" butonu, onay diyaloglu, "mevcut adım bitince duracak" uyarısıyla.
- **Test edildi:** stale-failed-step düzeltmesi (mock bir action'ın ÇALIŞMA SIRASINDA diskteki `failed_step`'in zaten `None` olduğu doğrulandı), tam pipeline'ın cancel_event set edilince doğru adımdan sonra durduğu (adımlar arası, adım ortasında değil), `/api/builds/{job_id}/cancel` endpoint'i (normal iptal, olmayan iş, zaten bitmiş iş), `_execute_build`'in `PipelineCancelled`'ı yakalayıp `"cancelled"` olarak işaretlediği ve `CANCEL_EVENTS`'ten temizlediği, tüm sayfaların JS sözdizimi.

---

## Tasarımsal SEO açıklaması + kopyalama düzeltmeleri

Kullanıcı üç şey istedi: (1) açıklama metni maddeler/emoji/sembollerle daha "tasarımsal" ve Google'ın düz AI-metni algılamasını önleyecek şekilde yazılsın, (2) kopyalanınca paragraf/madde başları (boş satırlar) korunsun, (3) her etiket ayrı ayrı kopyalanabilsin.

- **SEO prompt'u güncellendi** (`app/prompts/seo.txt`): açıklama artık düz tek paragraf değil — 1-2 cümlelik kanca, boş satır, bağlama uygun emojilerle başlayan 3-6 madde (🔍🌍⚡🎯📌🧠🔥⏳🧬 gibi, her satırda aynısı tekrarlanmadan), boş satır, kısa bir kapanış çağrısı, opsiyonel hashtag satırı — hepsi JSON string içinde gerçek `\n\n`/`\n` ile ayrılmış. Şablon gibi/genel AI diline karşı açık uyarı eklendi ("In this video, we explore..." tarzı klişeler yasak). Shorts için bu yapı atlanıyor (zaten çok kısa).
- **Kopyalama mekanizması düzeltildi:** Açıklama artık `data-copy` HTML attribute'u yerine görünür `<p id="seoDescription" style="white-space:pre-wrap">` elemanının `.textContent`'inden okunuyor (`copyElementText()` yeni JS fonksiyonu) — bu, HTML attribute içine gömmenin kırılgan olabileceği çoklu satır/boş satırların TAM olarak korunmasını garantiliyor. Ayrıca `white-space:pre-wrap` sayesinde açıklama artık proje sayfasında da düz metin yerine gerçek madde/paragraf yapısıyla görünüyor (önceden tarayıcı boşlukları/satır sonlarını görsel olarak yutuyordu).
- **Etiket başına kopyalama:** Her etiket rozeti artık tek başına tıklanabilir (kendi `data-copy` değeriyle `copyToClipboard`), üzerinde küçük 📋 ikonu var. Eski "hepsini virgülle kopyala" butonu da duruyor, kaldırılmadı — sadece ek olarak tekli kopyalama geldi.
- **Test edildi:** çok satırlı/emoji'li bir description'ın `_parse_and_validate`'den (SEOAgent) bozulmadan geçtiği, proje sayfasında `white-space:pre-wrap` + `#seoDescription` elemanının doğru render edildiği, her etiketin kendi `data-copy` değerine sahip olduğu, "hepsini kopyala" butonunun hâlâ çalıştığı, yeni `copyElementText` fonksiyonunun JS sözdizimi ve tüm sayfaların hatasız render olduğu.

---

## Türkçe TTS sayı/kısaltma okuma normalizasyonu

Kullanıcının Instagram bot projesindeki (`hakanerbasss.github.io`) ayrı bir Claude oturumu, Supertonic TTS'in Türkçe rakamları, tarihleri, saatleri, hal eklerini ve kurum kısaltmalarını doğru okuyamadığını canlıda tespit edip bağımsız (dış paket gerektirmeyen, sadece `re` kullanan) bir `tr_tts_normalize.py` modülü geliştirmişti. Bu oturuma "önce oku, sonra konuşalım" diyerek entegrasyon için devretti — o oturumun docuForge reposuna erişimi yok.

- **Kod inceleme:** DocuForge'da 4 ses sağlayıcısı var (`app/providers/voice/espeak.py`, `piper.py`, `supertonic.py`, `xtts.py`) — `supertonic.py` Instagram botundakiyle birebir aynı Supertonic SDK'sını çağırıyor, yani orada görülen sorun burada da aynen var. Diğer üçü de kendi başına sayı/tarih normalizasyonu yapmıyor.
- **Tek chokepoint bulundu:** `app/services/voice_service.py`'deki `VoiceService.generate()`, sahne metnini okuyup doğrudan `provider.synthesize()`'a geçiriyor — 4 sağlayıcının hepsi buradan geçiyor. Normalizasyon burada tek noktadan eklendi, tek tek provider'lara dokunmaya gerek kalmadı.
- **Entegrasyon:** `tr_tts_normalize.py`, `app/utils/tr_tts_normalize.py` olarak taşındı (`clean_tts_text` public fonksiyonu), `voice_service.py` sahne metnini okuduktan hemen sonra `text = clean_tts_text(text, lang=language)` çağırıyor. `language` zaten `project.json`'dan okunup sağlayıcıya geçirilen aynı değer olduğu için Türkçe olmayan projeler dokunulmadan geçiyor (fonksiyonun kendi `lang == "tr"` kapısı sayesinde).
- **Kapsam:** tam sayılar, sıra sayılar, ondalık sayılar (virgül/nokta), yüzde (+ aralık), saat (+ aralık), tarih, sıcaklık/derece, negatif sayılar, hal ekleri (kesme işaretinden sonraki -e/-de/-den/-in/-inde Türkçe ünlü uyumuyla doğru sayı sözcüğüne bağlanıyor), para birimi/ölçü/veri birimi kısaltmaları, kurum/sınav kısaltmaları (TBMM, YKS, SGK, ABD, vb. tam açılım + doğru hal ekiyle), sözlükte olmayan büyük harfli kısaltmalar (harf harf okunuyor, NATO/FETÖ gibi kelime-gibi-okunanlar hariç), markdown kalıntıları ve URL temizliği.
- **Bilinen sınırlama (kaynak modülden devralındı):** skor (3-1) ile sayı aralığı (10-15) ayrımı regex ile bağlamdan çözülemiyor, ikisi de düz yan yana okunuyor — tam çözüm için TTS öncesi bir LLM adımı gerekir, henüz uygulanmadı.
- **Test edildi:** `test_tr_tts_normalize.py` — normalizasyon senaryoları + Türkçe olmayan dilin dokunulmadan geçtiği doğrulandı. Ayrıca `VoiceService.generate()`'ın sahte bir `VoiceProvider`'a normalize edilmiş metni gönderdiği uçtan uca doğrulandı (mock provider + mock `_probe_duration`).

### Kullanıcının gerçek bir üretim altyazısıyla (`yapay_zeka_dogayi_kurtarabilir_mi`) bulduğu ek hatalar

Kullanıcı gerçek bir projenin `subtitles.srt` dosyasını paylaştı; modülü o metinle çalıştırıp 6 gerçek hata bulundu ve düzeltildi — hepsi regex/sözlük eksikliğiydi, gerçek bağlamsal belirsizlik değildi (LLM'e gerek kalmadı):

- **Enerji birimleri eksikti:** `MWh`, `Wh`, `TWh`, `kWh` sözlükte yoktu, olduğu gibi TTS'e gidiyordu → "megavat saat"/"vat saat"/"teravat saat"/"kilovat saat" olarak açılıyor.
- **`ppm` hiç tanınmıyordu**, eklenirken de önce yanlış yapıldı (sonek gibi "420 milyonda bir" değil, `%` ile aynı ÖNEK mantığıyla "milyonda dört yüz yirmi" olması gerekiyordu) — düzeltildi.
- **`NASA` harf harf okunuyordu** ("N A S Anın") — kelime gibi okunanlar listesine eklendi.
- **Harf-harf ayrılmış kısaltmalara gelen ek boşluksuz yapışıyordu:** `GPU'lar` → `G P Ular` (anlamsız) yerine artık `G P U lar` (ek ayrı kelime olarak boşlukla ekleniyor). `_harf_harf` artık kesme işaretli eki kendi regex'ine dahil edip (`_EKYAK`) doğru şekilde çözüyor.
- **`GPT-3` gibi harf-kodu+tire+rakam kalıpları** tireyi hiç temizlemiyordu (`G P T-üçün` gibi çıplak tire TTS'e gidiyordu) — son "özel semboller" adımına, saat/yüzde aralığı ve skor regex'lerinin bilerek ürettiği boşluklu " - " ayracına DOKUNMADAN, sadece bitişik/kalıntı tireleri temizleyen bir kural eklendi.
- **Ondalık nokta "nokta" diye okunuyordu:** DeepSeek üretimi script'lerde ondalıklar sık sık İngilizce noktayla yazılıyor (1.2, 4.3, 2.9 gibi) — artık noktalama işaretinin harfi harfine adı ("nokta") yerine Türkçe'de ondalık ayracın doğal okunuşu olan "virgül" ile okunuyor ("bir nokta iki derece" değil "bir virgül iki derece").
- **Çözülmeyen tek gerçek belirsizlik:** `1,287 MWh` gibi İngilizce binlik-ayıracı virgülü, zaten test edilmiş 3 haneli ondalık hassasiyet örneğiyle (`0,003`) regex düzeyinde ayırt edilemiyor (ikisi de virgülden sonra 3 hane). Regex ile riskli bir tahmin yapmak yerine kaynağında çözüldü: `app/prompts/script.txt`'e "Türkçe'de binlik ayıracı olarak virgül kullanma" talimatı eklendi.
- **Test edildi:** yukarıdaki 8 yeni senaryo `test_tr_tts_normalize.py`'ye eklendi (toplam 30 test), hepsi geçti; `VoiceService.generate()` uçtan uca tekrar doğrulandı.

---

## Altyazının yanına düz metin (.txt) transkript indirme

Kullanıcı isteği: "altyazı srt formatının yanına txt formatı da koyalım indirilebilir olsun".

- `RenderService._render()`, `subtitles_enabled` ise artık `subtitles.srt`'nin yanına `subtitles.txt` de yazıyor — yeni `_write_txt()` metodu, `.srt` üretiminde kullanılan aynı `subtitle_segments` listesini (sahne numarası, süre, metin) kullanıyor ama zaman kodu/indeks/8-kelimelik alt yazı parçalama olmadan, her sahne kendi paragrafı olacak şekilde `\n\n` ile birleştiriyor — kopyala-yapıştır transkript/açıklama metni için doğrudan kullanılabilir.
- Proje sayfasındaki "Altyazı" kartına, mevcut `subtitles.srt İndir` butonunun yanına `subtitles.txt İndir` butonu eklendi — sadece dosya varsa gösteriliyor (eski render'larda `.txt` olmayacağı için geriye dönük uyumlu, kırık link göstermiyor).
- **Test edildi:** `_write_txt()`'in None/boş metinli sahneleri atladığını ve paragrafları doğru ayırdığını, proje sayfasının hem `.txt` varken (her iki buton da görünüyor) hem yokken (sadece `.srt` butonu, `.txt` linki hiç render edilmiyor) doğru HTML ürettiğini FastAPI `TestClient` ile doğruladım.

---

## /new sayfasına AI konu önerisi özelliği

Kullanıcı isteği: konu kutusunun yanına DeepSeek'in konu önereceği bir özellik eklensin, basınca listelesin, seçince konu başlığına gelsin — ama manuel konu yazma kısmı kaldırılmasın.

- **Yeni agent:** `app/agents/topic.py` (`TopicSuggestionAgent`), diğer agent'larla aynı desen (`BaseAgent`, JSON parse-and-validate, 3 deneme, code-fence temizleme). Prompt (`app/prompts/topic_suggestions.txt`), seçili `content_type`/`language`'a göre 8 konu önerisi istiyor — her biri `title` (zorunlu), `hook` (tek cümlelik tıklama nedeni), `visual_left`/`visual_right` (opsiyonel, split-contrast kapak görseli için İngilizce kısa görsel ipucu — boş string olabilir) alanlarıyla, en yüksekten en düşük tıklama potansiyeline sıralı.
- **Endpoint:** `POST /api/topic-suggestions` (`content_type`, `language` gövdede) — agent'ı çağırıp JSON'u aynen döndürüyor, hata durumunda 502 + Türkçe hata mesajı.
- **`/new` sayfası:** Konu kutusunun hemen altına "💡 Konu Önerisi Al" butonu eklendi (manuel giriş kutusu dokunulmadan duruyor). Tıklayınca seçili içerik türü/dil ile isteği atıyor, sonuçları listeliyor — ilk 3 öneri 🥇🥈🥉 madalyalı ayrı bir "En yüksek tıklama potansiyeline sahip 3 konu" özet kutusunda, tüm liste altında (her satırda başlık + hook + varsa Sol/Sağ görsel ipucu) tıklanabilir kartlar halinde. Bir karta tıklayınca `#topic` input'u o başlıkla doluyor, öneri listesi kapanıyor.
- **Bilinen hata düzeltildi (bu özellik eklenirken bulundu):** Eklenen "💡" butonuna ait metin dosyaya yanlışlıkla eşleşmemiş bir surrogate-pair kaçış dizisi (`💡`) olarak yazılmış, bu da `/new` sayfasını (daha önce bu proje tarihinde bir kere daha görülen "lone-surrogate crash" sınıfından) UTF-8 encode hatasıyla çökertiyordu. Python string literal'lerinde ayrık `\uXXXX` kaçışları otomatik olarak tek bir astral karaktere birleşmiyor -- gerçek UTF-8 emoji karakteriyle değiştirilerek düzeltildi. Dosyanın geri kalanındaki tüm diğer emoji zaten ham UTF-8 karakter olarak duruyordu, sadece bu tek nokta etkilenmişti.
- **Test edildi:** `TopicSuggestionAgent`'ın sahte AI yanıtlarıyla (geçerli JSON, eksik/hatalı alanlar, code-fence'li yanıt, tamamen geçersiz JSON) doğru parse/validate/hata davranışı; `/api/topic-suggestions` endpoint'i FastAPI `TestClient` ile (başarılı, agent hatası → 502, varsayılan gövde); `/new` sayfasının hatasız render olduğu, manuel konu girişinin hâlâ zorunlu/çalışır durumda olduğu, iki `<script>` bloğunun da `node --check` ile sözdizimsel olarak geçerli olduğu doğrulandı.

---

## Dinleyip seçilebilen ücretsiz müzik arayüzü

Kullanıcı isteği: mevcut otomatik müzik seçimi yeterli değil, üretimden önce parçaları dinleyip elle seçebileceği bir arayüz istiyor.

- **`JamendoMusicProvider.search()`** (yeni): mevcut `get_music()` ile aynı Jamendo API'sini kullanıyor ama indirme yapmadan, en fazla `limit` adet aday parçayı `{id, name, artist, duration, preview_url, download_url}` olarak döndürüyor. `get_music()` artık bunu çağırıp ilk sonucu indiriyor (kod tekrarı kaldırıldı).
- **`RenderService._resolve_music_track()`** genişletildi: `music_track` alanı artık sadece yerel dosya yolu değil, `http(s)://` ile başlayan bir URL de olabiliyor — bu durumda `MediaDownloader` ile `music/selected_track.mp3`'e indiriliyor. İndirme başarısız olursa (link ölmüş, ağ hatası vb.) render'ı düşürmüyor, sadece müziksiz devam ediyor (mevcut hata toleransı deseniyle aynı).
- **`BuildPipeline.run()`** ve `STEP_ALLOWED_OVERRIDES["render"]`'a `music_track` eklendi — hem ilk üretimde hem render adımını "Yeniden Üret" ile tekrar çalıştırırken seçilebiliyor (render formunun kendisi bu turda genişletilmedi, sadece override olarak kabul ediliyor; `/new` sihirbazındaki tam dinle-seç arayüzü bu turun kapsamı).
- **`GET /api/music-search`** (yeni endpoint, `query`/`content_type` parametreleriyle): `query` boşsa `RenderService._build_music_query()`'deki aynı içerik-türü→mood eşlemesini kullanıyor (kod tekrarı yok), `JamendoMusicProvider.search()`'ü çağırıp sonucu döndürüyor; API key yoksa/arama başarısızsa 502 + Türkçe hata.
- **`/new` sayfası:** "Arka Plan Müziği Ekle" işaretli ve sağlayıcı "Jamendo" seçiliyken, sağlayıcı satırının altında bir arama kutusu + "🎧 Ara" butonu beliriyor. Sonuçlar, her biri parça adı/sanatçı/süre ve gömülü `<audio controls>` önizleme çalarıyla listeleniyor; "✅ Bu parçayı seç" butonuna basınca gizli `music_track` alanı o parçanın indirme URL'siyle doluyor ve seçim "🎵 Seçilen parça: ..." notuyla onaylanıyor. Sağlayıcı Jamendo dışına değiştirilirse veya müzik kapatılırsa seçim otomatik temizleniyor (build isteğine yanlışlıkla eski bir seçim gitmesin diye). Hiçbir parça seçilmezse davranış tamamen eskisi gibi — otomatik mood aramasına düşüyor.
- **Yine bulunan lone-surrogate hatası:** bu turda eklenen "🎧 Ara" buton metni de (💡 butonundaki gibi) dosyaya ayrık bir surrogate-pair kaçışı olarak yazılmış, `/new` sayfasını aynı UTF-8 encode hatasıyla çökertiyordu — gerçek UTF-8 karakteriyle değiştirilip düzeltildi, tüm dosya taranıp başka örneği kalmadığı doğrulandı.
- **Test edildi:** `JamendoMusicProvider.search()`'ün indirme linki olmayan sonuçları elediği ve `get_music()`'in ilk adayı indirdiği (mock `requests`/`MediaDownloader`); `_resolve_music_track()`'in bir URL'yi indirip `music/selected_track.mp3`'e yazdığı, indirme hatasında `None` döndürüp render'ı düşürmediği, mevcut yerel-yol davranışının bozulmadığı; `/api/music-search` endpoint'inin başarı/API-key-yok/boş-sorgu-mood-varsayılanı senaryoları (FastAPI `TestClient` + mock); `/new` sayfasının hatasız render olduğu ve iki `<script>` bloğunun `node --check` ile geçerli olduğu.

### Konuya göre otomatik arama terimi önerisi

Kullanıcı takip isteği: müzik önizleme çalışıyor, güzel — konu seçilince arama kutusu da konuya göre otomatik dolsun istedi (şu ana kadar sadece içerik türüne göre sabit bir mood kullanılıyordu, ör. her belgesel için "cinematic documentary ambient").

- **Yeni endpoint:** `GET /api/music-mood` (`topic`, `content_type`) — konu boşsa doğrudan `RenderService._build_music_query()`'deki sabit mood'u döndürüyor; konu varsa DeepSeek'e "bu konuya uygun 3-5 kısa İngilizce mood/tür anahtar kelimesi öner (Jamendo aramasında kullanılacak)" diye tek satırlık bir prompt gönderip yanıtı temizleyip döndürüyor. AI çağrısı başarısız olursa (API key yok, ağ hatası vb.) sessizce aynı sabit mood'a düşüyor — bu sadece bir kutuyu önceden dolduran bir öneri, hata verip build'i engellemesi anlamsız.
- **`/new` sayfası:** müzik arama kutusu artık konu her değiştiğinde (konu inputundan çıkınca/blur, ya da AI konu önerisinden bir başlık seçilince) otomatik olarak bu endpoint'i çağırıp kendini dolduruyor -- kullanıcı yine de "Ara"ya basmadan önce metni elle değiştirebiliyor, otomatik arama tetiklenmiyor. Sadece müzik açık + Jamendo seçiliyken (`musicBrowseRow` görünürken) çalışıyor, gereksiz çağrı yapmıyor.
- **Test edildi:** `/api/music-mood`'un boş konu/AI başarılı/AI başarısız üç senaryosu (FastAPI `TestClient` + mock `get_ai`), `/new` sayfasının yeni JS ile hatasız render olduğu ve sözdizimsel olarak geçerli olduğu.

### Etiketler kısaltıldı + tıklanabilir çip haline getirildi

Kullanıcı geri bildirimi: önizleme çalışıyor ama önceki tek-satır AI önerisi ("mysterious dark ambient tech cinematic" gibi 5 kelime birden) Jamendo'da sonuç getirmiyordu — Jamendo'nun `tags` parametresi tek uzun bir AND'lenmiş ifadeyle değil, birkaç kısa bağımsız etiketle çok daha iyi eşleşiyor. Kullanıcı ayrıca Jamendo'nun varsayılan sağlayıcı olmasını ve etiketlerin arama kutusuna tek tek eklenebilmesini istedi.

- **`GET /api/music-mood` artık `{"query": "..."}` değil `{"tags": [...]}` döndürüyor** — DeepSeek'e "6 tane KISA, BAĞIMSIZ mood/tür etiketi öner (1-2 kelime, ör. 'cinematic', 'dark ambient', 'epic')" diye soruluyor, virgülle ayrılmış liste olarak parse ediliyor. Konu boşsa veya AI başarısız olursa, sabit content-type mood'u kelimelere bölüp (`"cinematic documentary ambient"` → `["cinematic","documentary","ambient"]`) aynı liste formatını koruyor.
- **`/new` sayfası:** Müzik sağlayıcı `<select>`'inde artık **Jamendo varsayılan seçili** (önceden "Yerel"di). Arama kutusunun altına `musicMoodTags` adında bir çip alanı eklendi — konu değiştiğinde (blur/AI öneri seçimi) bu alan dolup her etiket ayrı, küçük, tıklanabilir bir "+ etiket" çipine dönüşüyor. Bir çipe tıklayınca (`addMusicTag`) etiket **arama kutusuna eklenir** (üzerine yazmaz, aynı etiket tekrar eklenmez), kullanıcı istediği kadar etiketi birleştirip "Ara"ya basabiliyor.
- **Test edildi:** `/api/music-mood`'un yeni `tags` listesi formatını (boş konu/AI başarılı — numaralandırma ve fazladan boşluk gibi gürültüyü temizleyerek/AI başarısız senaryoları), `/new` sayfasının Jamendo'nun varsayılan seçili olduğunu ve yeni çip render/ekleme fonksiyonlarının sözdizimsel geçerliliğini doğruladım.

### Müzik sesi seviyesi ayarı

Kullanıcı sordu: arka plan müziği konuşmayı bastırmaz mı? Cevap: hayır, zaten sabit %18'de karıştırılıyordu (`amix` filtresinde `volume=0.18`) — ama bu değer koddaydı, kullanıcı hiç değiştiremiyordu. Kullanıcı ayarlanabilir olmasını istedi.

- **`DocumentaryProject.music_volume: float = 0.18`** eklendi (`app/models/project.py`) — `__post_init__`'te float'a çevrilip `_validate()`'te 0.0-1.0 aralığı kontrol ediliyor, `from_dict` de okuyor.
- **`RenderService._apply_background_music()`**: hardcoded `volume=0.18` yerine artık `project_data.get("music_volume", 0.18)` okunuyor — geçersiz/eksik değerde (tip hatası, aralık dışı) sessizce 0.18'e düşüyor veya 0.0-1.0'a clamp'leniyor, render'ı asla düşürmüyor.
- **`BuildPipeline.run()`** ve `STEP_ALLOWED_OVERRIDES["render"]`'a `music_volume` eklendi — hem ilk üretimde hem render adımını yeniden üretirken ayarlanabiliyor.
- **`/new` sayfası:** Müzik sağlayıcı satırının altına "Müzik Sesi Seviyesi" kaydırıcısı eklendi (%0-%50 aralık, %5 adım, varsayılan %18) — `voice_speed` kaydırıcısıyla aynı görsel desende, canlı yüzde etiketiyle. Gönderilen build isteğinde `music_volume` 0.0-1.0 kesire çevriliyor.
- **Test edildi:** modelin varsayılan/geçerli/geçersiz `music_volume` değerlerini doğru işlediği ve `from_dict`'in okuduğu; `_apply_background_music()`'in gerçek bir ffmpeg komutu üretmeden (mock `_run`/`_probe_duration`/`_resolve_music_track`) doğru `volume=X.XXX` filtresini bastığı (özel değer, varsayılan, aralık-dışı clamp, tip hatası fallback); `/new` sayfasının kaydırıcıyla hatasız render olduğu ve JS'in geçerli olduğu.
- **Düzeltme (kullanıcı ekran görüntüsüyle bildirdi):** her "Bu parçayı seç" butonu zaten metninde sabit "✅" işareti taşıdığı için, hangi parçanın gerçekten seçili olduğu hiç belli olmuyordu — hepsi aynı görünüyordu. `selectMusicTrack()` artık tıklanınca ÖNCE tüm `.music-pick-btn` butonlarını nötr (mavi, "Bu parçayı seç") duruma resetliyor, SONRA tıklanan butonu yeşil "✅ Seçildi" yapıyor — tam olarak bir seçim her an görsel olarak işaretli.

---

## MS/yıl+nokta/Roma rakamı seslendirme hataları + amix normalize sorunu

Kullanıcı gerçek bir üretimin (`yeraltı_şehri` konulu) `subtitles.txt` dosyasını paylaştı: "MS kısmında seslendirme hatası var, diğer kısımlara da bakarsın" ve ayrıca "%18 ayarladım ama daha yüksek çıkıyor, konuşmayı bastırıyor" dedi. Metni `clean_tts_text`'ten geçirip 4 gerçek hata + 1 render (ffmpeg) hatası bulundu:

- **`MS`/`MÖ` (Milattan Sonra/Önce) sözlükte yoktu** — "MS 532'de" harf harf "M S beş yüz otuz ikide" okunuyordu. Kurum kısaltmaları sözlüğüne eklendi.
- **Sıra sayı/yıl+nokta karışıklığı (en ciddi bulgu):** `"1453. İstanbul fethedildi"` gibi bir yılın ardından cümle sonu noktası gelen kalıplar, mevcut sıra sayı regex'i tarafından yanlışlıkla "1453'üncü" (ordinal) diye okunuyordu — "bin dört yüz elli üçüncü İstanbul fethedildi" gibi anlamsız bir cümle çıkıyordu. Kök neden: eski regex `\d+\.` içeren HER durumu ordinal sayıyordu, nokta sonrası küçük/büyük harf ayrımı yapmıyordu. **Düzeltme:** nokta sonrası KÜÇÜK harfle aynı cümle içinde devam ediyorsa ("13. yüzyılda" gibi) hâlâ ordinal; BÜYÜK harfle yeni cümle başlıyorsa ya da metin bitiyorsa ("1453. İstanbul", "Yıl 330. Roma" gibi) sayı kelimeye çevrilip nokta (cümle arası duraklama için) korunuyor.
- **Roma rakamlı hükümdar numaraları hiç tanınmıyordu:** "I. Konstantin", "I. Justinianus" gibi kalıplar dokunulmadan TTS'e gidiyordu (harf gibi "ı" okunması bekleniyor). I-XX arası sabit bir ordinal sözlükle ("I. Ahmet" → "birinci Ahmet") çözüldü — büyük harfle devam eden isim öncesi Roma rakamı+nokta kalıbı yakalanıyor, sözlükte olmayan daha büyük/nadir bir rakama dokunulmuyor.
- **LIDAR/UNESCO gibi ek kelime-gibi-okunan kısaltmalar** kelime gibi okunanlar listesine eklendi (UNICEF, RADAR, SONAR, INTERPOL de eklendi) — önceden harf harf "L I D A R" okunuyordu.
- **Asıl "%18 ayarladım ama daha yüksek çıkıyor" sorunu TTS metniyle ilgili değildi, render/ffmpeg tarafındaydı:** `amix` filtresi varsayılan olarak `normalize=1` ile çalışıyor -- ffmpeg bunu, girdi sayısına göre seviyeleri OTOMATİK olarak dinamik şekilde yeniden dengeleyip clipping'i önlemek için kullanıyor; bu da bizim `volume=0.18` ile önceden ayarladığımız sabit oranı bozup, özellikle anlatımın SUSTUĞU anlarda müziği geri yukarı çekiyordu (daha az "aktif" girdi olduğunu düşünüp otomatik telafi ediyordu). `amix` filtresine `normalize=0` eklendi -- artık ses oranını SADECE bizim ayarladığımız `volume=X` belirliyor, ffmpeg'in kendi otomatik dengelemesi devre dışı.
- **Test edildi:** 6 yeni normalizasyon senaryosu `test_tr_tts_normalize.py`'ye eklendi (toplam 36, hepsi geçti) + tüm gerçek `subtitles.txt` transkripti satır satır tekrar çalıştırılıp gözle doğrulandı; `_apply_background_music()`'in ürettiği ffmpeg filtresinde artık `normalize=0` bulunduğu mock testle doğrulandı.

---

## Müzik "bitişe doğru yükselme" (swell) + belgesellerde tasarımlı kapanış sahnesi

Kullanıcının iki isteği: (1) "konuşmanın sustuğu anlarda müzik yükselsin, mantıklı olabilir" fikrine görüş, (2) belgesellerde son kare/sahne için güzel bir kapanış tasarımı. İkisini de uygulamamı, ama alternatif olarak ChatGPT'de tasarlanmış bir kapanış görselinin yüklenip kullanılabileceği fikrini de düşünmemi istedi.

### Müzik yükselmesi -- neden "her duraklamada" değil, "bitişe doğru"

Gerçek mimariye bakıldı: sahneler arasında sadece `AUDIO_PADDING_SECONDS = 0.35` saniyelik bir boşluk var (her sahne kendi anlatımı + bu kısa dolgu kadar sürüyor, sonra direkt bir sonraki sahne başlıyor) — bu kadar kısa bir pencerede bir yükselme kulağa "cırt" diye bir aksaklık gibi gelir, gerçek bir "nefes alma" hissi vermez. Buna karşılık, SON anlatım satırından sonra, videonun zaten var olan bitiş fade-out penceresi (`fade_duration = min(3.0, süre)`) boyunca gerçek bir sessiz/düşük-yoğunluklu an var. Bu yüzden yükselmeyi her sahne arasına değil, **bitişe doğru tek bir kez** uyguladım:

- **`RenderService._music_volume_stage()`** (yeni): sabit `volume=X` yerine, videonun son ~2 saniyesinde müziği kademeli olarak (base'in ~2.5 katına, en fazla %55'e) yükselten bir ffmpeg `volume=eval=frame:volume='if(...)'` ifadesi üretiyor — yükselme tam olarak mevcut fade-out'un başladığı ana denk geliyor, oradan itibaren zaten var olan `afade=out` bunu sessizliğe indiriyor. Matematiği (süreklilik, üst sınır) Python'da ffmpeg'in eval mantığını birebir taklit ederek doğruladım (t=0, yükselme başlangıcı, ortası, fade başlangıcı, fade ortası, video sonu noktalarında). Yeterli kuyruk süresi olmayan (çok kısa) videolarda veya müzik sesi 0 ise, eskisi gibi düz `volume=X`'e düşüyor.
- **Önemli dürüstlük notu:** bu ortamda gerçek bir ffmpeg kurulu değil, bu yüzden ifadeyi gerçek ffmpeg'e karşı test edemedim — sadece matematiği (Python'da) ve sözdizimini (mevcut `_burn_in_subtitles`'daki `force_style='...'` deseniyle aynı tek-tırnak kaçış yöntemini kullanarak) doğrulayabildim. Bunu telafi etmek için `render()`'daki `_apply_background_music()` çağrısı artık `try/except` ile sarmalandı — müzik karıştırma herhangi bir nedenle (bu ifade dahil) başarısız olursa render'ın tamamı düşmüyor, sadece müziksiz devam ediyor ve log'a uyarı yazıyor. **Sunucuda gerçek bir render ile doğrulanması gerekiyor** — eğer müzik hiç eklenmiyorsa (log'da "Arka plan müziği eklenemedi" uyarısı varsa) bana bildir, ifadeyi düzeltirim.
- **`amix` filtresine `normalize=0`** eklendi (önceki turda) zaten bu yükselmenin gerçekten duyulmasını sağlıyor — `normalize=1` olsaydı ffmpeg kendi otomatik dengelemesiyle bu bilinçli yükselmeyi de bozabilirdi.

### Belgesel kapanış sahnesi

`app/prompts/storyboard.txt`'e yeni bir kural eklendi: documentary/informational içerik türlerinde SON sahnenin `visual` alanı, diğer sahnelerden farklı olarak bilinçli bir "kapanış çekimi" olacak şekilde yazılmalı — geniş açılı, sembolik, hikayeyi görsel olarak sonuçlandıran bir kompozisyon (ör. ölçeği açığa çıkaran yavaş bir geri çekilme, gün doğumu/batımı, ışığın süzülmesi), ama yine de belgeselin GERÇEK konusuna bağlı kalarak (alakasız jenerik bir gün batımı değil). Metin/logo yok (bu bir arka plan çekimi, bitmiş bir end-card değil). Bu, yeni bir pipeline aşaması değil — mevcut `image_prompts`/`video_prompts` ajanları zaten her sahnenin `visual` metnini sinematik bir prompt'a çeviriyor, bu yüzden son sahnenin metni farklı yazıldığında otomatik olarak oraya akıyor.

### Değerlendirilen ama uygulanmayan alternatif: yüklenebilir kapanış görseli

Kullanıcı, ChatGPT'de tasarlanmış sabit bir kapanış görselinin `/settings`'ten yüklenip (XTTS referans ses yükleme özelliğiyle aynı desende) belgesel türü videoların sonuna otomatik eklenebileceği fikrini attı — tasarımı beğenmezse tekrar yükleyip değiştirebilir. Bu, AI'ın HER üretimde yeni bir kapanış görseli üretmesine (mevcut çözüm) karşı, KULLANICININ elle tasarladığı SABİT bir görseli kullanmanın alternatifi. İkisi birbirini dışlamıyor — ileride "otomatik AI kapanış" varsayılan kalırken, yüklenmiş bir görsel varsa onu önceliklendiren bir geçersiz kılma (override) eklenebilir, tıpkı XTTS referans sesinin çalışma şekli gibi. Şimdilik uygulanmadı, kullanıcı onaylarsa ayrı bir iş olarak eklenebilir.

- **Test edildi:** `_music_volume_stage()`'in dört dalının (uzun video→yükselme, kısa video→düz, sessiz müzik→düz, sınır değer→yükselme) doğru çalıştığı; üretilen tam `filter_complex` string'inin `eval=frame`, `normalize=0` içerdiği ve tırnak dengesinin doğru olduğu; yükselme+fade matematiğinin süreklilik/üst-sınır açısından doğru olduğu (Python mirror); `test_tr_tts_normalize.py`'nin (36 test) hâlâ geçtiği.

---

## Yüklenebilir kapanış görseli + altyazı okunabilirlik düzeltmesi

### Kapanış görseli yükleme (bir önceki turda konuşulan alternatif)

Kullanıcı, AI'ın her üretimde yeni bir kapanış çekimi üretmesine ek/alternatif olarak, `/settings`'ten sabit bir görsel yüklenip belgesel projelerinin son sahnesinde kullanılabilmesini istedi — tıpkı XTTS referans ses yükleme özelliğiyle aynı desende (yükle, "Yapılandırılmış" durumu göster, "Değiştir" ile üzerine yaz).

- **`app/core/config.py`**: `closing_image` yeni bir secret alanı — `CLOSING_IMAGE` env var / `secrets.json`'daki `closing_image` anahtarı, mevcut `_resolve_secret`/`save_secret`/`is_configured` mekanizmasıyla aynı şekilde çalışıyor.
- **`app/web_settings.py`**: `_render_closing_image_field()` (XTTS'in `_render_xtts_field()`'ıyla aynı desen, ses yerine `<img>` önizleme) — yapılandırılmışsa görsel önizleme + "Değiştir", değilse dosya seçici + "Yükle". `POST /settings/closing_image/upload` (ffmpeg transcode gerekmiyor, görsel doğrudan `models/closing/closing_image{uzantı}` olarak kaydediliyor, farklı bir uzantıyla yeniden yüklenirse eski dosya temizleniyor), `GET /settings/closing_image/file` (önizleme/render için servis ediyor). Temizleme (`/clear`) zaten var olan genel `POST /settings/{field_key}/clear` endpoint'i tarafından otomatik karşılanıyor (yeni kod gerekmedi).
- **`RenderService._resolve_closing_image(project_data, is_last_scene)`** (yeni): sadece SON sahnede VE `content_type == "documentary"` iken VE bir kapanış görseli yapılandırılıp dosyası gerçekten varsa o görselin yolunu döndürüyor, aksi tüm durumlarda `None` (herhangi bir sorunda — okunamama, dosya yok — sessizce normal sahne medyasına düşüyor, render'ı hiç düşürmüyor). `render()`'daki sahne döngüsünde, `closing_image_path` `None` değilse o sahnenin `video_files`/`image_files`'ı bu tek görselle değiştiriliyor — sahnenin kendi anlatım sesi/süresi AYNEN kullanılıyor, sadece görsel değişiyor.
- **Yapılandırılmazsa hiçbir şey değişmiyor** — varsayılan davranış hâlâ AI'ın otomatik ürettiği kapanış çekimi (bir önceki turda storyboard.txt'e eklenen kural).
- **Test edildi:** `_resolve_closing_image`'ın 5 dalı (son sahne değil, yanlış içerik türü, yapılandırılmamış, dosya eksik, başarılı) mock `settings` ile; `/settings` sayfasının yeni alanla hatasız render olduğu ve JS'in geçerli olduğu; uçtan uca yükleme akışı (`TestClient` ile gerçek dosya yükleme → önizleme → farklı uzantıyla değiştirme → temizleme, hepsi disk üzerinde doğrulanıp temizlendi); **tam bir `render()` çalıştırması** (2 sahneli sahte proje, mock `_image_to_clip`/`_run`) ile SADECE son sahnenin kaynak görselinin değiştiği, ilk sahnenin kendi medyasını kullanmaya devam ettiği doğrulandı.

**Takip isteği:** kullanıcı görsel yüklenmiş olsa bile, ayrı bir "kullan/kullanma" anahtarı kapalıyken hiç eklenmemesini istedi (yükleme = kullanıma otomatik hazır olması anlamına gelmemeli).

- **`closing_image_enabled`** yeni bir secret alanı olarak eklendi (`CLOSING_IMAGE_ENABLED` env var / `secrets.json`), mevcut `save_secret`/`is_configured` mekanizması "1"/"" değeriyle bir boolean gibi kullanılıyor — yeni bir mekanizma gerekmedi.
- **`save_setting`/`clear_setting` doğrulaması** `FIELD_LABELS` yerine `SECRET_FIELDS.values()`'a karşı kontrol eder oldu — `closing_image_enabled`'ın kendi başına sayfada bir bölüm olarak görünmesini istemedim (kapanış görseli alanının İÇİNE gömülü bir checkbox olması gerekiyordu), ama yine de genel kaydet/temizle endpoint'lerini kullanabilmesi gerekiyordu. Bu değişiklik daha doğru bir ayrım da yapıyor: `SECRET_FIELDS` gerçek geçerli anahtarların kaynağı, `FIELD_LABELS` sadece hangi alanların kendi bölümüyle gösterileceğinin UI kararı.
- **`/settings`:** kapanış görseli yapılandırılmışsa, önizlemenin altına "Belgesellerin sonuna ekle" checkbox'ı eklendi — `toggleClosingImageEnabled()` JS fonksiyonu değişiklikte anında `fetch` ile kaydediyor/temizliyor (sayfa yenilenmeden). Varsayılan: kapalı (görsel yüklense bile).
- **`RenderService._resolve_closing_image()`**: artık `closing_image_enabled` de `is_configured` kontrolünden geçmeden `None` dönüyor — görsel yüklü olsa bile anahtar kapalıysa AI'ın otomatik kapanış çekimine düşülüyor.
- **Test edildi:** üç senaryo (anahtar kapalı+yüklü→kullanılmıyor, anahtar açık+yüklü→kullanılıyor, anahtar açık+yüklenmemiş→kullanılmıyor) mock `settings` ile; `/settings` sayfasında checkbox'ın varsayılan kapalı render olduğu, `POST /settings/closing_image_enabled` ve `/clear` ile açılıp kapandığında sayfanın doğru `checked` durumunu yansıttığı, bilinmeyen bir alan adının hâlâ 404 döndüğü (gevşetilen doğrulamanın fazla gevşek olmadığı) `TestClient` ile doğrulandı.

### Altyazı okunabilirlik düzeltmesi

Kullanıcı bildirdi: videoya gömülen altyazının arkası şeffaf olduğu için bazı (parlak/karışık) sahnelerde okunamıyor. Kök neden: `_burn_in_subtitles()`'daki ASS `force_style`, `BorderStyle=1` (sadece ince siyah anahat, arka plan yok) kullanıyordu.

- **Düzeltme:** `BorderStyle=3`'e geçildi — bu, metnin arkasına OPAK bir kutu çiziyor (`BackColour` ile), sadece anahat değil. `BackColour=&H80000000` (ASS'in `&HAABBGGRR` formatında, alfa `80` ≈ %50 opaklık) ile "kapkara değil, hafif karartılmış" bir arka plan elde edildi — kullanıcının açıkça istediği gibi. `Outline` değeri `BorderStyle=3` modunda artık metin kalınlığı değil, kutunun metin etrafındaki iç boşluğu anlamına geliyor (3'e çıkarıldı, biraz nefes payı için).
- **Dürüstlük notu:** bu ortamda gerçek ffmpeg/libass kurulu değil (zaten bu fonksiyonun kendi docstring'i de bunu önceden not etmişti), bu yüzden gerçek bir render'da görsel olarak doğrulayamadım — sözdizimi ASS/libass'ın resmi `force_style` alan adlarına ve `&HAABBGGRR` renk formatına dayanıyor. **Sunucuda altyazı gömülü bir projeyi yeniden render edip gözle kontrol etmen gerekiyor.**

---

## Adım tamamlanma saati gösterimi

Kullanıcı, Video Render'ı "Yeniden Üret" ile ayar değiştirip çalıştırdıktan sonra kapanış görselinin gelmediğini fark etti. İncelerken iki ayrı şey ortaya çıktı:

1. **"Kapak Görseli" adımı "pending" kalmış olması beklenen bir davranış** — `regenerate_step()` zaten sadece hedef adımı hemen çalıştırıp SONRASINDAKİ tüm adımları geçersiz kılıyor (kullanıcı önizleyip "▶ Devam Et" ile devam etsin diye, tasarım gereği). Video Render'ı yeniden üretince Thumbnail'ın "pending" kalması bug değil.
2. **Asıl gerçek sorun:** hangi "completed" adımın YENİ (switch açıldıktan sonraki) çalıştırma olduğunu, hangisinin ESKİ olduğunu ayırt edecek hiçbir zaman bilgisi yoktu — sadece süre (`duration_seconds`) gösteriliyordu, ki bu iki farklı çalıştırma arasında neredeyse aynı olabilir. Kullanıcı haklı olarak "kapanış görseli gelmedi, ama bu render yeni mi eski mi bilmiyorum" dedi.

- **`BuildPipeline`**: `_record_success`, `_record_existing_completion`, `_record_failure_and_raise` artık her adımın state kaydına `finished_at` (ISO 8601, UTC) zaman damgası ekliyor. `_record_existing_completion` (diskte zaten var olan çıktıyı tanıma, gerçek bir çalıştırma değil) önceki `finished_at`'ı koruyor, yeni bir tane üretmiyor.
- **`app/web.py`**: yeni `format_finished_at()` yardımcı fonksiyonu bu UTC zaman damgasını **Europe/Istanbul** saatine çevirip `GG.AA SS:DD` formatında gösteriyor (kullanıcının telefon saatiyle bire bir eşleşsin diye — UTC olarak bıraksaydım 3 saat geride görünüp kafa daha da karışırdı). Proje detay sayfasındaki her adım satırında artık `completed · 428.45 sn · 17.07 16:06` gibi görünüyor.
- **Test edildi:** `format_finished_at()`'ın UTC→İstanbul dönüşümünü doğru yaptığı ve boş/hatalı girdilerde `None` döndürdüğü; `_record_success`'in `finished_at` yazdığı, `_record_existing_completion`'ın var olan `finished_at`'ı koruduğu; proje detay sayfasının bu zaman damgasını doğru render ettiği (`TestClient`).

---

## Render adımına da müzik dinle-seç arayüzü + Jamendo telif farkındalığı

Kullanıcı iki şey sordu: (1) render devam ederken, "Yeniden Üret" ile müziği sonradan değiştirebilir miyim (o an sadece ham bir URL kutusu vardı), (2) bu müziklerin YouTube'a yüklerken telif sorunu olur mu.

### Render'ın "Yeniden Üret" formuna müzik arayıcı

`/new` sihirbazındaki dinle-seç arayüzü (arama kutusu + mood etiketleri + önizlemeli sonuç listesi) sadece yeni proje oluştururken vardı; proje sayfasındaki render adımını yeniden üretirken `music_track` düz bir metin kutusuydu (elle URL yapıştırmak gerekiyordu).

- **`/api/projects/{slug}/step-options/{step_key}`** artık `content_type` ve `topic` (proje başlığı) da döndürüyor — mood etiketi önerisi (`/api/music-mood`) için gerekli bağlam.
- **`app/web.py`**: `showRegenerateForm()`'daki jenerik alan-oluşturucu döngüsüne `music_track` için özel bir dal eklendi — aynı arama kutusu/mood etiketi/sonuç listesi deseni, ama dinamik olarak oluşturulan modal içinde (`regenSearchMusic`, `regenRenderMusicResults`, `regenSelectMusicTrack`, `regenUpdateMusicMoodSuggestion`, `regenRenderMusicMoodTags`, `regenAddMusicTag` — `/new`'deki fonksiyonların bu modale uyarlanmış hali, ayrı script bağlamı olduğu için kod tekrarı kaçınılmazdı). Modal açılırken `music_track` alanı varsa mood etiketleri otomatik yükleniyor.
- **Test edildi:** `/api/projects/{slug}/step-options/render`'ın `content_type`/`topic` döndürdüğü; proje detay sayfasının yeni JS ile (f-string süslü parantez kaçışı dahil) hatasız render olduğu ve iki `<script>` bloğunun da `node --check` ile sözdizimsel olarak geçerli olduğu.

### Jamendo lisans farkındalığı

Kullanıcının sorusu yerinde: Jamendo'nun kataloğu **karışık lisanslarla** dolu — bazı parçalar CC BY/BY-SA/BY-ND (ticari kullanım serbest), bazıları CC BY-NC/BY-NC-SA/BY-NC-ND (**ticari kullanım YASAK** — parasal gelir elde eden bir YouTube kanalında kullanmak lisans ihlali olur). Bu, önemsenmesi gereken gerçek bir risk.

- **`JamendoMusicProvider._parse_license(url)`** (yeni): Jamendo API'sinin her parça için döndürdüğü `license_ccurl` alanını okuyup insan-okunur bir etiket (`"CC BY-NC (ticari kullanım YOK)"` gibi) ve bir `commercial_ok` bayrağı (True/False/bilinmiyorsa None) üretiyor. CC0 (kamu malı) ayrıca tanınıyor.
- **`search()`** artık her sonuca `license: {url, label, commercial_ok}` ekliyor.
- **`get_music()`** (otomatik seçim yolu, kullanıcı elle bir parça seçmediğinde devreye giren) artık en popüler 10 aday arasından **ticari kullanıma uygun olan ilkini** tercih ediyor — sadece en popüler (ama belki NC lisanslı) tek sonucu körlemesine almıyor.
- **Her iki arayüzde de** (`/new` ve render'ın "Yeniden Üret"'i) her sonucun altında ✅ (ticari kullanıma uygun) / ⚠️ (uygun değil) / gri (bilinmiyor) rozeti gösteriliyor, aramanın üstünde de genel bir uyarı notu var.
- **Test edildi:** `_parse_license`'ın BY / BY-NC-SA / CC0 / boş-lisans durumlarını doğru ayırt ettiği; `get_music()`'in en popüler sonuç NC lisanslı olsa bile listede sonra gelen ticari-uygun bir adayı doğru seçtiği (mock `requests`/`MediaDownloader`).

## Kapak tasarımı güçlendirme + konu önerisi önceliklendirme

Gerçek YouTube Studio verisiyle (Pamukkale/dolandırıcılık videoları soyut "yapay zeka" konularından 5-10 kat daha çok izlenme almış) desteklenen iki değişiklik.

- **`ThumbnailService`**: 4 şablonun tümünde yazı boyutu ~%20-30 büyütüldü, kontur kalınlaştırıldı, gölge artık font boyutuyla orantılı (`_draw_text_block` yeniden yazıldı). Arka planı karışık/açık renkli olabilecek şablonlara (Mystery Focus, Split Contrast) yazının arkasına yarı saydam koyu şerit eklendi (`highlight_alpha` parametresi).
- **`app/prompts/topic_suggestions.txt`**: Belgesel/bilgilendirici öneriler artık açıkça "somut yer + gizem" ve "kişisel risk/korunma" açılarını önceliklendiriyor, soyut/felsefi önerileri 8'de en fazla 1-2'yle sınırlayıp listenin altına koyuyor.

## Kapak başlığını SEO başlıklarından seçme

Kapak üzerindeki yazı (`thumbnail_hook`) ile kullanıcının seçtiği video başlığı birbirinden bağımsızdı, aynı olmaları garanti değildi.

- **`DocumentaryProject.thumbnail_hook_override`** (yeni alan, varsayılan `""`) — `STEP_ALLOWED_OVERRIDES["thumbnail"]`'a eklendi.
- **`ThumbnailService._build_brief()`**: override doluysa `thumbnail_hook`'un önüne geçiyor.
- **`step_options()`**: `thumbnail` adımı için `seo.json`'daki başlık listesini `choices["thumbnail_hook_override"]` olarak dolduruyor (+ "Otomatik" seçeneği) — proje sayfasındaki mevcut `<select>` deseni (branch 2) hiçbir JS değişikliği gerektirmeden bunu otomatik render ediyor.

## Kapanış görseli / XTTS önizleme önbellek hatası düzeltmesi

Kullanıcı yeni bir kapanış görseli yükleyip sayfayı yenilediğinde eski görsel gelmeye devam ediyordu — sebep sunucu değil, tarayıcı önbelleğiydi (aynı dosya adı üzerine yazılıyor, `<img src>` URL'i hiç değişmiyordu). `/settings/closing_image/file` ve `/settings/xtts_reference_audio/file` önizleme URL'lerine dosyanın `mtime`'ına dayalı bir sürüm parametresi (`?v=...`) eklendi, ayrıca `Cache-Control: no-store` eklendi.

## Seçilebilir sahne geçişleri + otomatik cold-open

Kullanıcının kendi önerisiyle: sahneler arasında sert kesim yerine seçilebilir geçiş türleri, artı çok izlenen YouTube kanallarının kullandığı "önce en çarpıcı anı göster, sonra baştan başla" (cold open) tekniği.

- **`scene_transition`** (yeni proje alanı: `cut` / `crossfade` / `fade_black`, varsayılan `crossfade`) — `/new`'de seçilebilir, render adımının "Yeniden Üret"inde değiştirilebilir.
- **Cold open**: `storyboard.txt` artık her senaryoda tam olarak bir sahneyi (asla ilk/son sahne değil) `"hook_worthy": true` diye işaretliyor. Render sırasında o sahnenin klibinden sessiz, ~3 saniyelik bir kesit alınıp videonun en başına sert kesimle ekleniyor (`_build_hook_clip`, `_find_hook_scene_number`). Herhangi bir adımda sorun olursa özellik sessizce atlanıyor.
- **Altyazı zamanlama düzeltmesi**: Geçişler videonun toplam süresini kısalttığı için (`amix`/`xfade` overlap), altyazı zaman damgaları artık gerçek sahne başlangıç ofsetlerinden (`_concat_with_transitions`'ın döndürdüğü `start_offsets`) hesaplanıyor, ham sahne sürelerinin naif toplamından değil — aksi halde her geçişte altyazı biraz daha kayardı.

## Crossfade OOM hatası ve düzeltmesi + yarım kalmış video tespiti

Gerçek bir VPS render'ında (23 sahneli video) crossfade özelliği tek ffmpeg komutunda 23 klibi aynı anda işlerken ~5.6GB RAM kullandı, kernel OOM-killer `docuforge-web` servisini düşürdü (`systemd: Failed with result 'oom-kill'`). Servis yeniden başlayınca yarım kalmış (`moov atom not found`) `final_video.mp4`'ü "tamamlanmış" sanıp render'ı atladı.

- **`_concat_with_transitions`** artık tüm klipleri tek seferde değil, **ikişer ikişer sıralı** birleştiriyor (büyüyen "şimdiye kadarki birleşik klip" + bir sonraki sahne) — bellek kullanımı sahne sayısından bağımsız, sabit kalıyor (test edildi: 23 sahnede bile ffmpeg'e aynı anda en fazla 2 girdi veriliyor). Ofset/süre matematiği değişmedi, sadece iş nasıl planlandığı değişti.
- **`RenderService.is_valid_output()`** (yeni, ffprobe tabanlı) + **`BuildPipeline._render_is_complete()`** artık sadece "dosya var mı ve boş değil mi" değil, gerçekten oynatılabilir bir video mu diye de kontrol ediyor — kesintiye uğramış bir render bir daha "tamamlandı" sayılıp atlanmıyor.

## Depolama sekmesi + dosya temizliği düzeltmeleri

- **`/settings/{field}/clear`** artık `xtts_reference_audio`/`closing_image` gibi dosya tabanlı alanlarda, sadece ayarı sıfırlamıyor, sunucudaki gerçek dosyayı da siliyor (önceden dosya öksüz kalıyordu).
- **Yeni `/storage` sayfası** (`app/web_storage.py`): disk (toplam/dolu/boş), RAM (`/proc/meminfo`), proje başına disk kullanımı (büyükten küçüğe sıralı) ve buradan doğrudan proje silme. Dashboard, proje detay sayfası, ayarlar ve `/new` sayfasının başlıklarına "📦 Depolama" linki eklendi.
- **Doğrulandı:** "Projeyi Sil" (`DELETE /api/projects/{slug}`) gerçekten `shutil.rmtree()` ile tüm dosyaları diskten kaldırıyor (test edildi) — disk şişmesi riski yaratmıyor.

---

## Kilitli geliştirme sırası

Yeni fikir eklenmeden şu sırayla ilerlenir:

### Faz 1 — Sistemi kullanılabilir ve kalıcı yap

1. ~~Web panelini systemd servisi yap~~ ✅ (VPS'de zaten çalışıyor)
2. ~~Kalıcı job sistemi~~ ✅ tamamlandı
3. Canlı pipeline durumu — kısmen (polling var, gerçek log yok)
4. ~~Resume ve hata ekranı~~ ✅ arayüzden de var artık ("▶ Devam Et" + "Yeniden Üret" butonları)
5. ~~Proje ayar modelini genişlet~~ ✅ tamamlandı

### Faz 2 — Gerçek yeni proje sihirbazı

✅ Tamamlandı — içerik türü, hedef süre, dil, medya modu, voice provider/name/speed,
resolution/FPS hepsi arayüzde var VE gerçekten project.json + pipeline davranışına bağlı.

### Faz 3 — TTS merkezi

1. ~~Supertonic varsayılan~~ ✅
2. Sesleri arayüzden test etme — yok
3. ~~XTTS provider~~ ✅ eklendi, VPS'de gerçek referans sesle henüz doğrulanmadı
4. Referans ses yükleme — yok (env var / sabit dosya yolu)
5. ~~Varsayılan ses ayarı~~ ✅
6. TTS otomatik kurulum sistemi — kısmen (Supertonic auto_download var)

### Faz 4 — Video kalitesi

1. Ses normalizasyonu — yok
2. Gürültü temizleme — yok, ertelendi (Piper cızırtısı için gerçek ses testi gerekiyor)
3. ~~Arka plan müziği~~ ✅ tamamlandı (sabit düşük ses + fade-out; sidechain ducking değil)
4. Ducking — yok (yukarıdaki gibi basit volume mix var)
5. ~~Fade~~ ✅ (müzik fade-out)
6. Geçiş efektleri — yok

### Faz 5 — Yayına hazırlık

1. ~~Thumbnail~~ ✅ tamamlandı
2. Altyazı — ✅ sidecar SRT tamamlandı, burn-in henüz yok
3. ~~Başlık~~ ✅ SEOAgent 3 başlık önerisi üretiyor
4. ~~Açıklama~~ ✅ SEOAgent üretiyor
5. ~~Etiketler~~ ✅ SEOAgent 10-20 etiket üretiyor
6. Chapters — yok
7. YouTube yükleme — yok

---

## Geliştirme kuralları

- Bir özellik tamamen bitmeden diğerine geçilmez.
- Arayüzde görünen ayar pipeline'a gerçekten bağlı olmalıdır.
- Büyük model dosyaları GitHub reposuna eklenmez.
- Kurulum komutları modelleri otomatik indirir.
- Instagram botu veya başka proje zorunlu bağımlılık olamaz.
- Her aşama test edilmeden tamamlandı denmez.
- Her stabil aşamadan sonra commit ve push yapılır.
- Yeni sohbet başladığında önce bu dosya okunur.
