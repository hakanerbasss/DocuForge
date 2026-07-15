# DocuForge — Proje Durumu

Son güncelleme: 15 Temmuz 2026

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
7. Media Builder
8. Scene Narrations
9. Voice Generation
10. FFmpeg Render

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
- Supertonic M1/M2/M3/F1/F2/F3 sesleri
- CLI üzerinde provider, voice ve speed seçenekleri
- Basit web panel
- Proje listesi
- Final videoyu tarayıcıda oynatma
- İlk yeni proje formu

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
- Varsayılan olmayacak

### Supertonic

- Doğrudan DocuForge ortamında çalışıyor
- Instagram botuna bağlı değil
- M1/M2/M3/F1/F2/F3
- Kullanıcı M1 testini beğendi
- Varsayılan ses sağlayıcısı olması planlanıyor

### XTTS-v2

- Kullanıcının diğer projesinde çalışan klon ses kodu mevcut
- DocuForge içine henüz bağımsız provider olarak eklenmedi
- Referans ses yükleme arayüzü henüz yapılmadı

---

## Web panelinin mevcut durumu

### Var

- Proje listesi
- Proje detay sayfası
- Final video oynatıcı
- Pipeline aşamalarını gösterme
- Basit yeni proje sayfası

### Eksik

- Kalıcı arka plan servisi
- Gerçek canlı log
- Çalışan işlerin yeniden başlatmada korunması
- Ses sağlayıcısı seçimi
- Ses seçimi
- Video süresi seçimi
- İçerik türü seçimi
- Medya modu seçimi
- Ayarlar ekranı
- Provider kurulum ekranı
- Resume butonu
- İptal butonu
- Yeniden üretme butonları
- Sesleri arayüzden dinleme
- Sahne ve medya düzenleme

---

## Henüz yapılmayan ana özellikler

- Haber şablonu
- Shorts/Reels şablonu
- Bilgi videosu şablonu
- Hedef süre sistemi
- Sadece video / sadece fotoğraf / karma medya modu
- Arka plan müziği
- Otomatik ducking
- Ses temizleme
- Ses normalizasyonu ve mastering
- XTTS klon ses provider
- Referans ses yükleme
- Altyazı ve SRT
- Thumbnail üretimi
- Thumbnail düzenleme
- Başlık, açıklama ve etiket üretimi
- YouTube yükleme
- Instagram/Reels sürümü
- Kalıcı iş kuyruğu
- Kullanıcı hesabı ve güvenlik

---

## Kilitli geliştirme sırası

Yeni fikir eklenmeden şu sırayla ilerlenir:

### Faz 1 — Sistemi kullanılabilir ve kalıcı yap

1. Web panelini systemd servisi yap
2. Kalıcı job sistemi
3. Canlı pipeline durumu
4. Resume ve hata ekranı
5. Proje ayar modelini genişlet

### Faz 2 — Gerçek yeni proje sihirbazı

1. İçerik türü
   - documentary
   - news
   - shorts
   - informational
2. Hedef süre
3. Dil
4. Medya modu
   - video
   - image
   - mixed
5. Voice provider
6. Voice name
7. Speed
8. Resolution ve FPS

Alanlar yalnızca arayüzde gösterilmeyecek; project.json ve pipeline davranışına gerçekten bağlanacaktır.

### Faz 3 — TTS merkezi

1. Supertonic varsayılan
2. Sesleri arayüzden test etme
3. XTTS provider
4. Referans ses yükleme
5. Varsayılan ses ayarı
6. TTS otomatik kurulum sistemi

### Faz 4 — Video kalitesi

1. Ses normalizasyonu
2. Gürültü temizleme
3. Arka plan müziği
4. Ducking
5. Fade
6. Geçiş efektleri

### Faz 5 — Yayına hazırlık

1. Thumbnail
2. Altyazı
3. Başlık
4. Açıklama
5. Etiketler
6. Chapters
7. YouTube yükleme

---

## Geliştirme kuralları

- Bir özellik tamamen bitmeden diğerine geçilmez.
- Arayüzde görünen ayar pipeline’a gerçekten bağlı olmalıdır.
- Büyük model dosyaları GitHub reposuna eklenmez.
- Kurulum komutları modelleri otomatik indirir.
- Instagram botu veya başka proje zorunlu bağımlılık olamaz.
- Her aşama test edilmeden tamamlandı denmez.
- Her stabil aşamadan sonra commit ve push yapılır.
- Yeni sohbet başladığında önce bu dosya okunur.
