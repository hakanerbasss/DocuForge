# DocuForge — Proje Durumu

Son güncelleme: 16 Temmuz 2026 (2. güncelleme aynı gün — XTTS, per-stage regenerate, web panel navigasyon düzeltmeleri)

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
- RAM notu: Instagram bot'un kendi `ses-klonu/README.md`'si CX23'ün (4GB) XTTS-v2 için yetersiz olabileceğini söylüyor, ama `supertonic-web/app.py` yine de doğrudan yerelde kullanıyor — bu server aynıysa dikkat, model yüklenirken RAM sorunu çıkabilir.

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
- Müzik dosyası yükleme arayüzü (şu an SSH ile `music/` klasörüne manuel kopyalama gerekiyor)
- XTTS referans ses dosyasının kendisini yükleme arayüzü (yolu artık `/settings`'ten girilebiliyor ama dosyanın kendisini upload etme yok — sunucuya SSH ile konması gerekiyor)
- **Yeniden Üret'te ayar değiştirme eklendi** — kullanıcı "sesi/görseli/dili beğenmezsem değiştirebilmeliyim" dedi. Artık `research` (dil/içerik türü/süre), `voice` (sağlayıcı/isim/hız), `media` (görsel/video sağlayıcı), `render` (çözünürlük/fps/müzik/altyazı/burn-in) aşamalarını yeniden üretirken ayarları değiştirebiliyorsun — "Yeniden Üret" butonu artık önce ilgili ayarları gösteren bir form açıyor. `GET /api/projects/{slug}/step-options/{step_key}` hangi alanların değişebileceğini ve mevcut değerleri dönüyor.
- **Altyazı burn-in eklendi** — `subtitles_burn_in` ayarı, ffmpeg'in `subtitles` filtresiyle (libass) videoya gerçekten gömüyor. **Test edilmedi** — bu container'da gerçek ffmpeg/libass yok, sadece komut kurulumu doğrulandı. VPS'de gerçek bir video ile denenmeli.
- **`/new` ve ana sayfa artık aktif işleri gösteriyor** — kullanıcı "üretim başlatıp sayfa değiştirince kayboluyor" diye bildirdi. `journalctl` logu incelendi: üretim ASLA durmamış, sadece hiçbir yerde görünmüyordu. `GET /api/jobs/active` artık her iki sayfada da 4 saniyede bir poll ediliyor.

---

## Henüz yapılmayan ana özellikler

- Otomatik ducking (şu an sabit düşük seviye, sidechain compress değil)
- Piper ses temizleme / normalizasyon / mastering
- XTTS referans ses yükleme arayüzü
- Thumbnail düzenleme (arayüzden başlık değiştirme vb.)
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
