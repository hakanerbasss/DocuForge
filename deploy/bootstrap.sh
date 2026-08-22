#!/bin/bash
# ============================================================================
# DOCUFORGE — SIFIRDAN SUNUCU KURULUMU
# ============================================================================
# Boş bir Ubuntu sunucusunu tek komutla çalışır hâle getirir. Eski sunucuya
# hiçbir bağımlılığı yoktur. API key GEREKMEZ: panel açılır, DeepSeek/Pexels
# vb. anahtarlar sonradan /settings sayfasından girilir.
#
# Kullanım (yeni sunucuda root olarak):
#   curl -fsSL https://raw.githubusercontent.com/hakanerbasss/DocuForge/main/deploy/bootstrap.sh -o bootstrap.sh
#   bash bootstrap.sh
#
# Seçenekler:
#   DOMAIN=df.ornek.com   nginx kurulsun, panel bu adresten sunulsun
#   PANEL_USER / PANEL_PASS  nginx'te HTTP Basic Auth (DOMAIN ile birlikte)
#   SSL=1                 Let's Encrypt sertifikası da alınsın (DOMAIN şart)
#   WITH_XTTS=1           XTTS ses klonlama (torch — ağır, ~2 GB+)
#   PORT=8090             uygulamanın dinlediği port
#   FORCE=1               mevcut kurulumun üzerine yaz
#
# GÜVENLİK NOTU: DocuForge'da giriş ekranı YOKTUR. DOMAIN vermezsen panel
# 0.0.0.0'a bağlanır ve IP'yi bilen herkes /settings sayfasından API
# anahtarlarını okuyabilir. Bunu kurulum sonunda tekrar hatırlatıyor.
# ============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/hakanerbasss/DocuForge.git}"
APP_DIR="${APP_DIR:-/root/docuforge}"
PORT="${PORT:-8090}"
DOMAIN="${DOMAIN:-}"
PANEL_USER="${PANEL_USER:-docuforge}"
PANEL_PASS="${PANEL_PASS:-}"
SSL="${SSL:-0}"
WITH_XTTS="${WITH_XTTS:-0}"
FORCE="${FORCE:-0}"
SSL_EMAIL="${SSL_EMAIL:-wizaicorp@gmail.com}"

say() { echo ""; echo "==> $*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "HATA: root olarak çalıştır (sudo bash bootstrap.sh)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 0) Çalışan kurulumun üzerine yazma koruması
# ---------------------------------------------------------------------------
if [ "$FORCE" != "1" ] && [ -f /etc/systemd/system/docuforge-web.service ]; then
  cat >&2 <<'UYARI'
HATA: Bu sunucuda zaten bir DocuForge kurulumu var
      (/etc/systemd/system/docuforge-web.service mevcut).

Bu script boş sunucular içindir. Devam etmek systemd birimini (ve DOMAIN
verilmişse nginx yapılandırmasını) ÜZERİNE YAZAR: farklı port/dizin, elle
eklenmiş ayarlar, certbot'un ürettiği HTTPS blokları kaybolabilir. Servis
farklı bir dizinden çalışıyorsa mevcut projeler/işler de görünmez olur
(kod göreli yol kullanıyor).

Sadece kodu güncellemek istiyorsan:
    cd /root/docuforge && git pull \
      && .venv/bin/pip install -e ".[web,voices]" \
      && systemctl restart docuforge-web

Gerçekten sıfırdan kurmak istiyorsan önce yedek al, sonra FORCE=1 ver:
    cp /etc/systemd/system/docuforge-web.service ~/docuforge-web.service.bak
    FORCE=1 bash bootstrap.sh
UYARI
  exit 1
fi

# ---------------------------------------------------------------------------
# 1) Sistem paketleri
# ---------------------------------------------------------------------------
say "Sistem paketleri kuruluyor..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# ffmpeg + ffprobe: render, ses, thumbnail ve altyazı burn-in'in tamamı bunlara
#   dayanıyor (render_service, voice_service, thumbnail_service).
# espeak-ng: VARSAYILAN ses sağlayıcısı (app/main.py). Kurulu değilse hiçbir
#   ayar değiştirilmemiş bir projede seslendirme adımı patlar.
PKGS="git curl ca-certificates python3 python3-venv python3-pip ffmpeg espeak-ng"
[ -n "$DOMAIN" ] && PKGS="$PKGS nginx"
# shellcheck disable=SC2086
apt-get install -y -qq $PKGS

# ---------------------------------------------------------------------------
# 2) Kod
# ---------------------------------------------------------------------------
say "Kod indiriliyor: $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin main
  git -C "$APP_DIR" reset --hard origin/main
else
  git clone --depth 50 "$REPO_URL" "$APP_DIR"
fi

# ---------------------------------------------------------------------------
# 3) Python ortamı
# ---------------------------------------------------------------------------
say "Python ortamı kuruluyor..."
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
# [web]    : fastapi/uvicorn/pydantic/python-multipart — bunlar olmadan panel
#            "import app.web" satırında ModuleNotFoundError ile ölür.
# [voices] : supertonic — sihirbazda seçenek olarak duruyor, kurulu değilse
#            üretim anında patlar.
( cd "$APP_DIR" && "$APP_DIR/.venv/bin/pip" install -q -e ".[web,voices]" )

if [ "$WITH_XTTS" = "1" ]; then
  say "XTTS (ses klonlama) kuruluyor — torch indirilecek, uzun sürer..."
  ( cd "$APP_DIR" && "$APP_DIR/.venv/bin/pip" install -q -e ".[xtts]" ) \
    || echo "    UYARI: XTTS kurulamadı. Panelin geri kalanı etkilenmez."
fi

# Panel gerçekten import edilebiliyor mu? Servisi başlatıp systemd'yi sonsuz
# restart döngüsüne sokmadan ÖNCE anlaşılsın.
say "Kurulum doğrulanıyor..."
( cd "$APP_DIR" && "$APP_DIR/.venv/bin/python" -c "import app.web; print('    app.web: ok')" )
for bin in ffmpeg ffprobe espeak-ng; do
  command -v "$bin" >/dev/null && echo "    $bin: ok" || echo "    EKSİK: $bin"
done

# ---------------------------------------------------------------------------
# 4) systemd
# ---------------------------------------------------------------------------
# nginx varsa yalnız yerel arayüz dinlenir; yoksa panele IP ile ulaşılabilsin
# diye 0.0.0.0 (bugünkü davranış) — ama panelde giriş olmadığı için bu açık
# bir kurulumdur, sonda uyarılıyor.
if [ -n "$DOMAIN" ]; then BIND="127.0.0.1"; else BIND="0.0.0.0"; fi

say "systemd birimi yazılıyor (bind: $BIND:$PORT)..."
sed -e "s#__APP_DIR__#${APP_DIR}#g" \
    -e "s#__PORT__#${PORT}#g" \
    -e "s#__BIND__#${BIND}#g" \
    "$APP_DIR/deploy/systemd/docuforge-web.service" > /etc/systemd/system/docuforge-web.service
systemctl daemon-reload
systemctl enable --now docuforge-web
sleep 5

if curl -fsS --max-time 10 "http://127.0.0.1:${PORT}/" >/dev/null; then
  echo "    panel cevap veriyor"
else
  echo "HATA: panel 127.0.0.1:${PORT} üzerinde cevap vermiyor." >&2
  journalctl -u docuforge-web -n 30 --no-pager >&2 || true
  exit 1
fi

# ---------------------------------------------------------------------------
# 5) nginx (yalnızca DOMAIN verildiyse)
# ---------------------------------------------------------------------------
if [ -n "$DOMAIN" ]; then
  AUTH_BLOCK="# (Basic Auth kapalı — PANEL_PASS ile açılır)"
  if [ -n "$PANEL_PASS" ]; then
    apt-get install -y -qq apache2-utils
    htpasswd -bc /etc/nginx/docuforge.htpasswd "$PANEL_USER" "$PANEL_PASS" >/dev/null 2>&1
    AUTH_BLOCK='auth_basic "DocuForge"; auth_basic_user_file /etc/nginx/docuforge.htpasswd;'
  fi

  say "nginx yapılandırılıyor..."
  # Ayraç "|" — AUTH_BLOCK'un kapalı hâli "#" ile başlıyor ve "#" ayraçlı sed
  # bunu "unknown option to `s'" ile reddeder.
  sed -e "s|__DOMAIN__|${DOMAIN}|g" \
      -e "s|__PORT__|${PORT}|g" \
      -e "s|__AUTH__|${AUTH_BLOCK}|g" \
      "$APP_DIR/deploy/nginx/docuforge.conf" > /etc/nginx/sites-available/docuforge
  ln -sf /etc/nginx/sites-available/docuforge /etc/nginx/sites-enabled/docuforge
  nginx -t
  systemctl reload nginx

  if [ "$SSL" = "1" ]; then
    say "Let's Encrypt sertifikası alınıyor..."
    apt-get install -y -qq certbot python3-certbot-nginx
    certbot --nginx --non-interactive --agree-tos -m "$SSL_EMAIL" -d "$DOMAIN" \
      || echo "    UYARI: certbot başarısız (DNS henüz bu sunucuya bakmıyor olabilir)."
  fi
fi

IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo 'SUNUCU_IP')"

cat <<SUMMARY

============================================================================
KURULUM TAMAM
============================================================================
Servis : docuforge-web  (${BIND}:${PORT})
Dizin  : ${APP_DIR}
SUMMARY

if [ -n "$DOMAIN" ]; then
  echo "Adres  : http://${DOMAIN}/  (SSL=1 ile https)"
  [ -n "$PANEL_PASS" ] && echo "Giriş  : ${PANEL_USER} / (verdiğin şifre) — nginx Basic Auth"
else
  cat <<ACIK
Adres  : http://${IP}:${PORT}/

⚠️  DİKKAT — PANEL GİRİŞSİZ VE İNTERNETE AÇIK
    DocuForge'da giriş ekranı yok. Bu adresi bilen herkes /settings
    sayfasından DeepSeek, Pexels, OpenAI, fal.ai anahtarlarını görebilir
    ve değiştirebilir. En az birini yap:
      - Bir alan adı bağla ve şifre koy:
          DOMAIN=df.ornek.com PANEL_PASS=birsifre SSL=1 bash bootstrap.sh
      - Ya da güvenlik duvarında ${PORT} portunu yalnız kendi IP'ne aç:
          ufw allow from <SENIN_IP> to any port ${PORT}
          ufw deny ${PORT}
ACIK
fi

cat <<SONRAKI

SIRADAKİ ADIMLAR:

  1. Panelde /settings → DeepSeek (zorunlu) ve Pexels anahtarını gir.
     Kurulumda hiçbir anahtar gerekmedi, hepsi buradan giriliyor.

  2. Piper sesi kullanacaksan modelini indir:
       ${APP_DIR}/models/piper/tr_TR-fahrettin-medium/
     (Supertonic ve eSpeak kuruldu, ek bir şey gerekmez.)

  3. XTTS ses klonlama isteniyorsa:  WITH_XTTS=1 bash bootstrap.sh
     Referans sesi /settings'ten yükle. Tarayıcıdan mikrofonla kayıt
     YALNIZCA HTTPS'te çalışır — o yüzden DOMAIN + SSL=1 gerekir.

Güncelleme:
  cd ${APP_DIR} && git pull \\
    && .venv/bin/pip install -e ".[web,voices]" \\
    && systemctl restart docuforge-web
============================================================================
SONRAKI
