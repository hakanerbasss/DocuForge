# DocuForge — Proje Durumu

Son güncelleme: 16 Temmuz 2026 (10. güncelleme aynı gün — tasarımsal SEO açıklaması + paragraf/emoji korunan kopyalama + etiket başına kopyalama)

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
