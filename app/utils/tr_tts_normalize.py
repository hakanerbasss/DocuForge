"""
Türkçe TTS metin normalizasyonu.

TTS motoruna (Supertonic, Piper, eSpeak, XTTS -- veya başka bir Türkçe TTS)
metin göndermeden hemen önce çağır -- rakamları, tarihleri, saatleri, hal
eklerini ve kurum/sınav kısaltmalarını TAM Türkçe sözcüğe çevirir. TTS
modelinin kendisine dokunmaz, sadece ona giden metni önceden temizler.

Kullanım:
    from app.utils.tr_tts_normalize import clean_tts_text
    temiz_metin = clean_tts_text(ham_metin, lang="tr")
    # temiz_metin'i TTS motoruna gönder

Bağımlılık yok -- sadece Python standart kütüphanesi (re).

Kaynak: hakanerbasss/hakanerbasss.github.io reposundaki Instagram botu
(supertonic-web) için geliştirilip canlıda doğrulanmış, buraya olduğu gibi
taşınmıştır.
"""

_TR_ONES = ['', 'bir', 'iki', 'üç', 'dört', 'beş', 'altı', 'yedi', 'sekiz', 'dokuz']
_TR_TENS = ['', 'on', 'yirmi', 'otuz', 'kırk', 'elli', 'altmış', 'yetmiş', 'seksen', 'doksan']


def _tr_num_to_words(n: int) -> str:
    """Tam sayıyı Türkçe sözcüklere çevirir. Örn: 1500 → bin beş yüz"""
    if n == 0:
        return 'sıfır'
    if n < 0:
        return 'eksi ' + _tr_num_to_words(-n)
    parts = []
    if n >= 1_000_000_000:
        b = n // 1_000_000_000; n %= 1_000_000_000
        parts.append(('bir' if b == 1 else _tr_num_to_words(b)) + ' milyar')
    if n >= 1_000_000:
        m = n // 1_000_000; n %= 1_000_000
        parts.append(('bir' if m == 1 else _tr_num_to_words(m)) + ' milyon')
    if n >= 1_000:
        t = n // 1_000; n %= 1_000
        parts.append(('' if t == 1 else _tr_num_to_words(t) + ' ') + 'bin')
    if n >= 100:
        h = n // 100; n %= 100
        parts.append(('' if h == 1 else _TR_ONES[h] + ' ') + 'yüz')
    if n >= 10:
        parts.append(_TR_TENS[n // 10]); n %= 10
    if n > 0:
        parts.append(_TR_ONES[n])
    return ' '.join(p.strip() for p in parts if p.strip())


# Sıra sayı eki her zaman sayının SON kelimesine eklenir (ör. "yüz yirmi üç" → "yüz
# yirmi üçüncü") ve Türkçe'de ünlü uyumu + ünsüz yumuşaması içerir (dört→dördüncü).
# Son kelime her zaman bu sabit listelerden biri olduğu için (birler/onlar/yüz/bin/
# milyon/milyar), tam algoritma yerine sonlu bir sözlük yeterli ve daha güvenilir.
_TR_ORDINAL_MAP = {
    'sıfır': 'sıfırıncı', 'bir': 'birinci', 'iki': 'ikinci', 'üç': 'üçüncü',
    'dört': 'dördüncü', 'beş': 'beşinci', 'altı': 'altıncı', 'yedi': 'yedinci',
    'sekiz': 'sekizinci', 'dokuz': 'dokuzuncu',
    'on': 'onuncu', 'yirmi': 'yirminci', 'otuz': 'otuzuncu', 'kırk': 'kırkıncı',
    'elli': 'ellinci', 'altmış': 'altmışıncı', 'yetmiş': 'yetmişinci',
    'seksen': 'sekseninci', 'doksan': 'doksanıncı',
    'yüz': 'yüzüncü', 'bin': 'bininci', 'milyon': 'milyonuncu', 'milyar': 'milyarıncı',
}


def _tr_ordinal_words(n: int) -> str:
    """Sıra sayı sözcüğü üretir. Örn: 13 → on üçüncü, 1 → birinci."""
    words = _tr_num_to_words(n).split(' ')
    words[-1] = _TR_ORDINAL_MAP.get(words[-1], words[-1] + 'ıncı')
    return ' '.join(words)


# Kaynak metinde sayı/birimden sonra kesme işaretiyle gelen hal ekleri (14:30'DA,
# 250 TL'YE, 2027'DE gibi) SİLİNMEMELİ — ek cümledeki iki sayıyı birbirinden ayıran
# tek şey, eksik olunca "on dört otuz dokuz" gibi anlamsız bitişik okuma oluyor.
# Sayı sözcüğünün SON kelimesi her zaman bu sabit listelerden biri olduğu için
# (birler/onlar/yüz/bin/milyon/milyar + enjekte ettiğimiz birim sözcükleri), genel
# bir ünlü-uyumu algoritması yerine sonlu bir sözlük kullanılıyor — Türkçe'de
# ünsüz yumuşaması (dört→dörde) bazı kelimelerde düzensiz, sözlük daha güvenilir.
_TR_DATIVE = {          # -a/-e/-ya/-ye ("...e/a", "'a kadar" gibi)
    'sıfır':'sıfıra','bir':'bire','iki':'ikiye','üç':'üçe','dört':'dörde','beş':'beşe',
    'altı':'altıya','yedi':'yediye','sekiz':'sekize','dokuz':'dokuza',
    'on':'ona','yirmi':'yirmiye','otuz':'otuza','kırk':'kırka','elli':'elliye',
    'altmış':'altmışa','yetmiş':'yetmişe','seksen':'seksene','doksan':'doksana',
    'yüz':'yüze','bin':'bine','milyon':'milyona','milyar':'milyara',
    'santigrat':'santigrada','derece':'dereceye','fahrenheit':'fahrenheite',
    'lira':'liraya','kilometre':'kilometreye','kilogram':'kilograma',
    'metrekare':'metrekareye','metreküp':'metreküpe',
    'dolar':'dolara','euro':'euroya','sterlin':'sterline','saat':'saate','nesil':'nesile',
    'gigabayt':'gigabayta','megabayt':'megabayta','kilobayt':'kilobayta','terabayt':'terabayta',
    'gigabit':'gigabite','megabit':'megabite','kilobit':'kilobite',
}
_TR_LOCATIVE = {        # -da/-de/-ta/-te ("...da/de")
    'sıfır':'sıfırda','bir':'birde','iki':'ikide','üç':'üçte','dört':'dörtte','beş':'beşte',
    'altı':'altıda','yedi':'yedide','sekiz':'sekizde','dokuz':'dokuzda',
    'on':'onda','yirmi':'yirmide','otuz':'otuzda','kırk':'kırkta','elli':'ellide',
    'altmış':'altmışta','yetmiş':'yetmişte','seksen':'seksende','doksan':'doksanda',
    'yüz':'yüzde','bin':'binde','milyon':'milyonda','milyar':'milyarda',
    'santigrat':'santigratta','derece':'derecede','fahrenheit':'fahrenheitte',
    'lira':'lirada','kilometre':'kilometrede','kilogram':'kilogramda',
    'metrekare':'metrekarede','metreküp':'metreküpte',
    'dolar':'dolarda','euro':'euroda','sterlin':'sterlinde','saat':'saatte','nesil':'nesilde',
    'gigabayt':'gigabaytta','megabayt':'megabaytta','kilobayt':'kilobaytta','terabayt':'terabaytta',
    'gigabit':'gigabitte','megabit':'megabitte','kilobit':'kilobitte',
}
_TR_ABLATIVE = {        # -dan/-den/-tan/-ten ("...dan/den")
    'sıfır':'sıfırdan','bir':'birden','iki':'ikiden','üç':'üçten','dört':'dörtten','beş':'beşten',
    'altı':'altıdan','yedi':'yediden','sekiz':'sekizden','dokuz':'dokuzdan',
    'on':'ondan','yirmi':'yirmiden','otuz':'otuzdan','kırk':'kırktan','elli':'elliden',
    'altmış':'altmıştan','yetmiş':'yetmişten','seksen':'seksenden','doksan':'doksandan',
    'yüz':'yüzden','bin':'binden','milyon':'milyondan','milyar':'milyardan',
    'santigrat':'santigrattan','derece':'dereceden','fahrenheit':'fahrenheitten',
    'lira':'liradan','kilometre':'kilometreden','kilogram':'kilogramdan',
    'metrekare':'metrekareden','metreküp':'metreküpten',
    'dolar':'dolardan','euro':'eurodan','sterlin':'sterlinden','saat':'saatten','nesil':'nesilden',
    'gigabayt':'gigabayttan','megabayt':'megabayttan','kilobayt':'kilobayttan','terabayt':'terabayttan',
    'gigabit':'gigabitten','megabit':'megabitten','kilobit':'kilobitten',
}
_TR_POSS_LOC = {        # "ayın 5'inde" → "ayın beşinde" (iyelik+bulunma birleşik eki)
    'sıfır':'sıfırında','bir':'birinde','iki':'ikisinde','üç':'üçünde','dört':'dördünde','beş':'beşinde',
    'altı':'altısında','yedi':'yedisinde','sekiz':'sekizinde','dokuz':'dokuzunda',
    'on':'onunda','yirmi':'yirmisinde','otuz':'otuzunda','kırk':'kırkında','elli':'ellisinde',
    'altmış':'altmışında','yetmiş':'yetmişinde','seksen':'sekseninde','doksan':'doksanında',
    'yüz':'yüzünde','bin':'bininde','milyon':'milyonunda','milyar':'milyarında',
}
_TR_GENITIVE = {        # "2026'nın ilk çeyreğinde" → "iki bin yirmi altının ilk çeyreğinde"
    'sıfır':'sıfırın','bir':'birin','iki':'ikinin','üç':'üçün','dört':'dördün','beş':'beşin',
    'altı':'altının','yedi':'yedinin','sekiz':'sekizin','dokuz':'dokuzun',
    'on':'onun','yirmi':'yirminin','otuz':'otuzun','kırk':'kırkın','elli':'ellinin',
    'altmış':'altmışın','yetmiş':'yetmişin','seksen':'sekseninin','doksan':'doksanın',
    'yüz':'yüzün','bin':'binin','milyon':'milyonun','milyar':'milyarın',
}


def _classify_tr_suffix(raw: str) -> str:
    """Kesme işaretinden sonraki ek harflerine bakıp ek TÜRÜNÜ tahmin eder."""
    s = raw.lower()
    if s.endswith('nde') or s.endswith('nda'):
        return 'possloc'
    if s.endswith('nin') or s.endswith('nın') or s.endswith('nun') or s.endswith('nün') \
       or s in ('in', 'ın', 'un', 'ün'):
        return 'genitive'  # 'nin' (ünlüyle biten kök, tampon n) veya 'in' (ünsüzle biten kök)
    if s.endswith('den') or s.endswith('dan') or s.endswith('ten') or s.endswith('tan'):
        return 'ablative'
    if s.endswith('de') or s.endswith('da') or s.endswith('te') or s.endswith('ta'):
        return 'locative'
    if s in ('a', 'e', 'ya', 'ye'):
        return 'dative'
    return ''


def _tr_attach_suffix(phrase: str, raw_suffix: str) -> str:
    """Dönüştürülmüş sayı ifadesinin (ör. 'otuz dört') SON kelimesine, orijinal
    kesme işaretli ekin türüne göre doğru Türkçe hal ekini bağlar. Tanınmayan/az
    rastlanan ek türlerinde (ör. '-lik', '-ini' iyelik-belirtme) güvenli şekilde
    eksiz bırakır — yanlış ek eklemek, hiç eklememekten daha kötü bir okuma
    hatasına yol açar."""
    if not raw_suffix:
        return phrase
    kind = _classify_tr_suffix(raw_suffix)
    table = {'dative': _TR_DATIVE, 'locative': _TR_LOCATIVE, 'ablative': _TR_ABLATIVE,
             'possloc': _TR_POSS_LOC, 'genitive': _TR_GENITIVE}.get(kind)
    if not table:
        return phrase
    words = phrase.split(' ')
    last = words[-1]
    if last in table:
        words[-1] = table[last]
        return ' '.join(words)
    return phrase


def _clean_tts_text(text: str, lang: str = "tr") -> str:
    """TTS'e gitmeden önce metni temizle — sayı/format hatalarını düzelt."""
    import re

    # Markdown kalıntılarını kaldır
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    if lang == "tr":
        # URL'leri kaldır (daha önce olmalı — rakam regex'lerinden önce)
        text = re.sub(r'https?://\S+', '', text)

        # Kurum/sınav kısaltmaları — DeepSeek promptunda 'bunları asla yazma,
        # tam adını yaz' kuralı zaten var ama LLM talimatlara her zaman uymuyor
        # (aynı 'rakam yazma' talimatının tutmaması gibi). Metin tarafında da
        # bir güvenlik ağı: kaçan kısaltmalar burada açılıyor. Büyük/küçük harf
        # duyarlı — bu kısaltmalar Türkçe metinde her zaman büyük harfle yazılır,
        # rastgele kelime çakışmasını önler.
        _TR_KISALTMA_ACILIM = {
            'TBMM': 'Türkiye Büyük Millet Meclisi',
            'YKS': 'Yükseköğretim Kurumları Sınavı',
            'LGS': 'Liselere Geçiş Sınavı',
            'ÖSS': 'Öğrenci Seçme Sınavı',
            'ÖSYM': 'Ölçme, Seçme ve Yerleştirme Merkezi',
            'SGK': 'Sosyal Güvenlik Kurumu',
            'ABD': 'Amerika Birleşik Devletleri',
            'AKP': 'Adalet ve Kalkınma Partisi',
            'CHP': 'Cumhuriyet Halk Partisi',
            'MHP': 'Milliyetçi Hareket Partisi',
            'TÜBİTAK': 'Türkiye Bilimsel ve Teknolojik Araştırma Kurumu',
            'MEB': 'Milli Eğitim Bakanlığı',
            'TÜİK': 'Türkiye İstatistik Kurumu',
            'TCMB': 'Türkiye Cumhuriyet Merkez Bankası',
            'BM': 'Birleşmiş Milletler',
            'AB': 'Avrupa Birliği',
            'MS': 'Milattan Sonra',
            'MÖ': 'Milattan Önce',
            'AI': 'Yapay Zeka',
        }
        # Açılımın SON kelimesi ünlüyle bittiği için hal eki tampon 'n' ister
        # (Kurumu'ndan, Meclisi'nde gibi) — genel güvenlik ağı sadece apostrofu
        # silip harfleri bitiştirdiği için tampon kayboluyordu ('Kurumudan').
        # Sayılardaki _tr_attach_suffix ile aynı mantık, açılımların son
        # kelimesine özel küçük bir sözlükle uygulanıyor.
        _TR_KISALTMA_SON_KELIME_EKI = {
            'Meclisi':    {'dative':'Meclisine','locative':'Meclisinde','ablative':'Meclisinden','genitive':'Meclisinin'},
            'Kurumu':     {'dative':'Kurumuna','locative':'Kurumunda','ablative':'Kurumundan','genitive':'Kurumunun'},
            'Devletleri': {'dative':'Devletlerine','locative':'Devletlerinde','ablative':'Devletlerinden','genitive':'Devletlerinin'},
            'Partisi':    {'dative':'Partisine','locative':'Partisinde','ablative':'Partisinden','genitive':'Partisinin'},
            'Bankası':    {'dative':'Bankasına','locative':'Bankasında','ablative':'Bankasından','genitive':'Bankasının'},
            'Milletler':  {'dative':'Milletlere','locative':'Milletlerde','ablative':'Milletlerden','genitive':'Milletlerin'},
            'Birliği':    {'dative':'Birliğine','locative':'Birliğinde','ablative':'Birliğinden','genitive':'Birliğinin'},
            'Sınavı':     {'dative':'Sınavına','locative':'Sınavında','ablative':'Sınavından','genitive':'Sınavının'},
            'Bakanlığı':  {'dative':'Bakanlığına','locative':'Bakanlığında','ablative':'Bakanlığından','genitive':'Bakanlığının'},
            'Zeka':       {'dative':'Zekaya','locative':'Zekada','ablative':'Zekadan','genitive':'Zekanın'},
        }
        def _kisaltma_ek_bagla(acilim, raw_suffix):
            if not raw_suffix:
                return acilim
            kind = _classify_tr_suffix(raw_suffix)
            forms = _TR_KISALTMA_SON_KELIME_EKI.get(acilim.split(' ')[-1])
            if kind and forms and kind in forms:
                words = acilim.split(' ')
                words[-1] = forms[kind]
                return ' '.join(words)
            return acilim
        _EKYAK_ERKEN = r"(?:['’]([a-zçğıöşüA-ZÇĞİÖŞÜ]{1,4}))?"
        for _kis, _acilim in _TR_KISALTMA_ACILIM.items():
            def _repl(m, _ac=_acilim):
                return _kisaltma_ek_bagla(_ac, m.group(1) or '')
            # IGNORECASE: DeepSeek her zaman tam büyük harfle yazmıyor ('Yks',
            # 'yks' gibi karışık/küçük harfli varyantlar da kaçmasın diye.
            # Bu kısaltmaların hiçbiri gerçek Türkçe kelimeyle çakışmadığı için
            # (ab/bm/yks vb. tek başına anlamlı kelime değil) risksiz.
            text = re.sub(rf'\b{re.escape(_kis)}\b' + _EKYAK_ERKEN, _repl, text, flags=re.IGNORECASE)

        # Yabancı marka adları / teknoloji terimleri — Türkçe TTS motoru
        # harf-ses eşlemesini İngilizce imlaya göre değil Türkçe imlaya göre
        # yapıyor, bu yüzden "Airbnb", "Wi-Fi" gibi kelimeler olduğu gibi
        # gönderilince yanlış/garip telaffuz ediliyor. Gerçek bir üretim
        # transkriptinde (Airbnb gizli kamera videosu) doğrulanmış hatalar.
        # Kesme işaretiyle gelen bir ek varsa (Airbnb'de gibi) buradaki
        # regex ona dokunmuyor -- aşağıdaki genel kesme işareti güvenlik ağı
        # (bu fonksiyonun sonunda) onu yeni yazılışa doğru şekilde bitiştiriyor.
        _TR_YABANCI_TELAFFUZ = {
            'Airbnb': 'Eyırbienbi',
            'Wi-Fi': 'Vayfay',
            'WiFi': 'Vayfay',
        }
        for _yab, _telaffuz in _TR_YABANCI_TELAFFUZ.items():
            text = re.sub(rf'\b{re.escape(_yab)}\b', _telaffuz, text, flags=re.IGNORECASE)

        # Sayıya BİTİŞİK yazılan birim kısaltmalarının arasına boşluk sok
        # (5GB → 5 GB) — aşağıdaki birim regex'lerinin hepsi \b sınırına
        # dayanıyor, bitişik yazımda "5GB" tek kelime sayılıp hiç açılmıyordu.
        # NOT: bare 'G' (5G nesil göstergesi) BİLEREK bu listede yok — o özel
        # olarak bitişik kalmalı, aşağıda ayrıca ele alınıyor.
        _BITISIK_BIRIMLER = ['Gbps','Mbps','Kbps','GB','MB','KB','TB','TL',
                             'km/s','km²','km³','km','kg','cm²','cm³','cm','mm²','mm']
        for _birim in _BITISIK_BIRIMLER:
            text = re.sub(rf'(?<=\d)({re.escape(_birim)})\b', r' \1', text, flags=re.IGNORECASE)

        # Para birimleri: $50 → 50 dolar, €50 → 50 euro, £50 → 50 sterlin
        text = re.sub(r'\$\s*(\d[\d.,]*)', r'\1 dolar', text)
        text = re.sub(r'€\s*(\d[\d.,]*)', r'\1 euro', text)
        text = re.sub(r'£\s*(\d[\d.,]*)', r'\1 sterlin', text)

        # Saat aralığı: 14:00-16:00 → saat on dört - saat on altı. TEKİL saat
        # regex'inden ÖNCE işlenmeli, yoksa aradaki tire çıplak kalır
        # ("saat on dört -saat on altı" gibi bitişik/garip okuma).
        def _saat_phrase(h, mn):
            p = 'saat ' + _tr_num_to_words(h)
            if mn:
                p += ' ' + _tr_num_to_words(mn)
            return p
        def _saat_araligi(m):
            h1, mn1, h2, mn2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            return _saat_phrase(h1, mn1) + ' - ' + _saat_phrase(h2, mn2)
        text = re.sub(r'\b(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\b', _saat_araligi, text)

        # Saat: 14:30 → saat on dört otuz. Kaynak metinde önünde zaten "saat"
        # kelimesi varsa (ör. "saat 14:30'da") onu da yutuyoruz — yoksa "saat
        # saat on dört otuz" gibi tekrar oluyordu. Arkasındaki hal eki (14:30'DA)
        # doğru ünlü uyumuyla son kelimeye bağlanır — dakika sıfırsa (14:00'te
        # gibi tam saatlerde) sondaki boşluk _tr_attach_suffix'i şaşırtmasın
        # diye strip() ile temizlenir (son kelime 'sıfır'/saat sözü olsun).
        def _saat(m):
            h, mn = int(m.group(1)), int(m.group(2))
            phrase = _saat_phrase(h, mn)
            return _tr_attach_suffix(phrase, m.group(3) or '')
        text = re.sub(r"(?:\bsaat\s+)?\b(\d{1,2}):(\d{2})\b(?:['’]([a-zçğıöşüA-ZÇĞİÖŞÜ]{1,4}))?",
                      _saat, text, flags=re.IGNORECASE)

        # Tarih: 12.07.2026 veya 12/07/2026 → on iki temmuz iki bin yirmi altı
        _AYLAR = {1:'ocak',2:'şubat',3:'mart',4:'nisan',5:'mayıs',6:'haziran',
                  7:'temmuz',8:'ağustos',9:'eylül',10:'ekim',11:'kasım',12:'aralık'}
        def _tarih(m):
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31 and y > 1900:
                return _tr_num_to_words(d) + ' ' + _AYLAR[mo] + ' ' + _tr_num_to_words(y)
            return m.group(0)
        text = re.sub(r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', _tarih, text)

        # Yüzde aralığı: %10-15 → yüzde on - on beş. TEKİL yüzde regex'inden
        # ÖNCE işlenmeli — yoksa ilk sayı %'den ayrı çevrilip aradaki tire
        # çıplak kalıyordu ("yüzde on-on beş" gibi bitişik okuma).
        text = re.sub(r'%\s*(\d+)-(\d+)',
                      lambda m: 'yüzde ' + _tr_num_to_words(int(m.group(1))) + ' - ' + _tr_num_to_words(int(m.group(2))),
                      text)

        # Yüzde: %85 → yüzde seksen beş, %13,52 → yüzde on üç virgül elli iki
        # ÖNCE işlenmeli — ondalık virgül regex'i "%13,52" içindeki "13,52"yi
        # kendi başına yakalayıp "%" işaretini boşta bırakıyordu.
        def _yuzde(m):
            out = 'yüzde ' + _tr_num_to_words(int(m.group(1)))
            if m.group(2):
                out += ' virgül ' + _tr_num_to_words(int(m.group(2)))
            return out
        text = re.sub(r'%\s*(\d+)(?:,(\d{1,2}))?', _yuzde, text)

        # Sıra sayılar: "13. yüzyılda" gibi, arkasından KÜÇÜK harfle aynı
        # cümle içinde devam eden "X." kalıbı → "on üçüncü" (nokta hiç
        # okunmaz, ordinal ekiyle birleşik okunur). ÖNCE işlenmeli — aksi
        # halde "13." önce "on üç." olur, sıra anlamı kaybolur.
        #
        # Arkasından BÜYÜK harfle yeni bir cümle başlıyorsa ("1453. İstanbul
        # fethedildi.", "Yıl 330. Roma İmparatoru..." gibi) bu bir sıra sayı
        # DEĞİL, bir yıl/sayının ardından gelen cümle sonu noktasıdır --
        # gerçek üretim script'inde canlı yakalanan bug: "1453." yanlışlıkla
        # "bin dört yüz elli üçüncü" diye (1453'üncü anlamında) okunuyordu.
        # Bu durumda sayı kelimeye çevrilir VE nokta (cümle arası duraklama
        # için) korunur.
        def _sira_sayi(m):
            return _tr_ordinal_words(int(m.group(1)))
        text = re.sub(r'\b(\d{1,4})\.(?=\s[a-zçğıöşü])', _sira_sayi, text)

        def _yil_nokta(m):
            return _tr_num_to_words(int(m.group(1))) + '.'
        text = re.sub(r'\b(\d{1,4})\.(?=\s[A-ZÇĞİÖŞÜ]|$)', _yil_nokta, text)

        # Roma rakamlı hükümdar/sıra numaraları: "I. Konstantin", "III.
        # Selim" gibi -- Türkçe tarih/belgesel metinlerinde hükümdar
        # numaralandırması hemen hemen her zaman Roma rakamıyla yazılır
        # (Arap rakamlı sıra sayı yukarıda ayrıca ele alınıyor, ikisi
        # karışmıyor: biri Roma harfleri, biri rakam). Kapsam I-XX
        # (pratikte hükümdar numaralandırmasının neredeyse tamamını
        # kapsıyor) -- listede olmayan daha büyük/nadir bir Roma rakamı
        # dokunulmadan bırakılır, yanlış tahmin etmek hiç dönüştürmemekten
        # daha kötü bir okuma hatasına yol açar.
        _ROMA_SIRA_SAYI = {
            'I': 'birinci', 'II': 'ikinci', 'III': 'üçüncü', 'IV': 'dördüncü',
            'V': 'beşinci', 'VI': 'altıncı', 'VII': 'yedinci', 'VIII': 'sekizinci',
            'IX': 'dokuzuncu', 'X': 'onuncu', 'XI': 'on birinci', 'XII': 'on ikinci',
            'XIII': 'on üçüncü', 'XIV': 'on dördüncü', 'XV': 'on beşinci',
            'XVI': 'on altıncı', 'XVII': 'on yedinci', 'XVIII': 'on sekizinci',
            'XIX': 'on dokuzuncu', 'XX': 'yirminci',
        }
        def _roma_sira_sayi(m):
            return _ROMA_SIRA_SAYI[m.group(1)]
        _roma_pattern = '|'.join(
            sorted(_ROMA_SIRA_SAYI, key=len, reverse=True)
        )
        text = re.sub(
            rf'\b({_roma_pattern})\.(?=\s[A-ZÇĞİÖŞÜ])',
            _roma_sira_sayi,
            text,
        )

        _EKYAK = r"(?:['’]([a-zçğıöşüA-ZÇĞİÖŞÜ]{1,4}))?"  # kesme işaretli ek — yakalanır, silinmez

        # ppm (milyonda bir): "%" ile aynı mantık, ÖNEK biçiminde okunur -- "X
        # ppm" -> "milyonda X" ("X milyonda bir" değil). Büyük sayı
        # dönüşümünden ÖNCE işlenmeli, yoksa rakam zaten sözcüğe çevrilmiş
        # olur ve bu regex hiç eşleşmez.
        def _ppm(m):
            out = 'milyonda ' + _tr_num_to_words(int(m.group(1)))
            return _tr_attach_suffix(out, m.group(2) or '')
        text = re.sub(r'\b(\d+)\s*ppm\b' + _EKYAK, _ppm, text, flags=re.IGNORECASE)

        # Mobil nesil: 5G → beşinci nesil. Genel büyük-sayı dönüşümünden ÖNCE
        # işlenmeli — yoksa '5' sözcüğe çevrilir ama bitişik 'G' harfi öylece
        # kalır ('beşG' gibi tek garip token oluşur, TTS'i şaşırtır). Arkasındaki
        # ek de (5G'YE gibi) yakalanıp doğru bağlanır — yoksa güvenlik ağı sadece
        # apostrofu silip 'nesilye' gibi kuralsız bir bitişik bırakıyordu.
        _TR_NESIL = {1:'birinci',2:'ikinci',3:'üçüncü',4:'dördüncü',5:'beşinci',6:'altıncı'}
        def _nesil(m):
            n = int(m.group(1))
            phrase = _TR_NESIL.get(n, _tr_ordinal_words(n)) + ' nesil'
            return _tr_attach_suffix(phrase, m.group(2) or '')
        text = re.sub(r'\b([1-9])[Gg]\b' + _EKYAK, _nesil, text)

        # İki sayı arası tire: hem maç skoru (3-1) hem aralık (10-15 derece)
        # anlamına gelebilir — bağlamdan ayırt etmek güvenilir değil. İlk
        # denemede skora göre "e" hali eklemiştim ("ona on beş derece" gibi
        # aralıklarda anlamsız çıktı verdi). Güvenli ortak çözüm: ikisi de
        # doğal okunan düz yan yana biçim — "üç bir" (skor, doğru), "on on
        # beş" (aralık, "arasında" ile birlikte anlaşılır kalıyor).
        text = re.sub(r'\b(\d+)-(\d+)\b',
                      lambda m: _tr_num_to_words(int(m.group(1))) + ' ' + _tr_num_to_words(int(m.group(2))),
                      text)

        # Sıcaklık/derece — BÜYÜK SAYI'DAN ÖNCE işlenmeli, yoksa rakam zaten
        # sözcüğe çevrilmiş olur ve "\d+°C" deseni artık eşleşmez (35°C → "otuz
        # beş°C" kalır, °C hiç açılmaz). Ondalık sıcaklık da desteklenir (36,6°C).
        # Arkasındaki hal eki (38°C'YE) doğru ünlü uyumuyla bağlanır, silinmez.
        def _sicaklik(birim):
            def _f(m):
                whole = _tr_num_to_words(int(m.group(1)))
                if m.group(2):
                    whole += ' virgül ' + _tr_num_to_words(int(m.group(2)))
                return _tr_attach_suffix(whole + ' ' + birim, m.group(3) or '')
            return _f
        text = re.sub(r'(-?\d+)(?:[.,](\d{1,2}))?°C' + _EKYAK, _sicaklik('derece'), text)
        text = re.sub(r'(-?\d+)(?:[.,](\d{1,2}))?°F' + _EKYAK, _sicaklik('fahrenheit'), text)
        text = re.sub(r'(-?\d+)(?:[.,](\d{1,2}))?°' + _EKYAK, _sicaklik('derece'), text)
        # Eksi işaretini (sıcaklık dışı bağlamda da) sözcüğe çevir: -5 → eksi beş,
        # -3,5 → eksi üç virgül beş (ondalık kısmı da TEK regex'te yakalanmalı —
        # ayrı geçseydi ondalık virgül regex'i "-" den sonraki rakamı bulamazdı).
        def _eksi_sayi(m):
            out = 'eksi ' + _tr_num_to_words(int(m.group(1)))
            if m.group(2):
                out += ' virgül ' + _tr_num_to_words(int(m.group(2)))
            return _tr_attach_suffix(out, m.group(3) or '')
        text = re.sub(r'(?<![\w])-(\d+)(?:,(\d{1,2}))?(?!\d)' + _EKYAK, _eksi_sayi, text)

        # Ondalık kısım sözcüğe çevrilirken: 1-2 haneliyse tek sayı olarak
        # ("52" → "elli iki"), 3+ haneliyse hassasiyet kaybolmasın diye hane
        # hane okunur ("003" → "sıfır sıfır üç" — "üç" desek 0,003 ile 0,3
        # birbirine karışırdı, baştaki sıfırların anlamı kaybolurdu).
        def _tr_ondalik_kisim(frac: str) -> str:
            if len(frac) <= 2:
                return _tr_num_to_words(int(frac))
            return ' '.join(_tr_num_to_words(int(c)) for c in frac)

        # Ondalık sayı — ÖNCE binlik ayırıcıdan önce işlenmeli. NOKTA burada {1,2}
        # İLE SINIRLI KALMALI (virgül gibi {1,4}'e ÇIKARILMAMALI) — Türkçe'de
        # binlik ayıracı da NOKTA olduğu için ('2.500.000'), 3 haneli bir grup
        # gelince bunu ondalık sanıp 'iki nokta beş yüz' gibi tamamen yanlış
        # okuyordu (gerçek bug, canlıda yakalandı). {1,2} sınırı, 3 haneli
        # binlik gruplarının bu regex'e hiç takılmayıp aşağıdaki binlik ayırıcı
        # adımına düşmesini sağlayan örtük ayrım mekanizması — bilerek dar tutulur.
        # 3.5 → üç virgül beş. DeepSeek üretimi Türkçe metinlerde ondalıkları sık
        # sık İngilizce noktayla yazıyor (1.2, 4.3, 2.9 gibi) -- bunları harfiyen
        # "nokta" diye (noktalama işaretinin adı) değil, Türkçe'de ondalık ayracın
        # doğal okunuşu olan "virgül" ile okumak gerçek üretim script'lerinde çok
        # daha doğal sesleniyor ("bir nokta iki derece" değil "bir virgül iki
        # derece"). Nokta hâlâ binlik ayıracı olarak (3 haneli gruplar) ayrı bir
        # regex'te kaldırılıyor, bu regex'e hiç takılmıyor.
        def _ondalik_nokta(m):
            out = _tr_num_to_words(int(m.group(1))) + ' virgül ' + _tr_ondalik_kisim(m.group(2))
            return _tr_attach_suffix(out, m.group(3) or '')
        text = re.sub(r'\b(\d+)\.(\d{1,2})(?!\d)' + _EKYAK, _ondalik_nokta, text)
        # 3,5 → üç virgül beş
        def _ondalik_virgul(m):
            out = _tr_num_to_words(int(m.group(1))) + ' virgül ' + _tr_ondalik_kisim(m.group(2))
            return _tr_attach_suffix(out, m.group(3) or '')
        text = re.sub(r'\b(\d+),(\d{1,4})(?!\d)' + _EKYAK, _ondalik_virgul, text)

        # Binlik nokta ayırıcıyı kaldır: 1.500 → 1500
        text = re.sub(r'(\d)\.(\d{3})\b', r'\1\2', text)

        # Büyük sayıları sözcüğe çevir: TÜM rakamlar çevrilir (Supertonic hiçbir
        # rakamı — 1000 altı dahil — doğru okuyamıyor, eşik kaldırıldı). Arkasındaki
        # hal eki (2027'DE, 5'İNDE gibi) doğru ünlü uyumuyla bağlanır.
        def _buyuk_sayi(m):
            n = int(m.group(1).replace('.', ''))
            return _tr_attach_suffix(_tr_num_to_words(n), m.group(2) or '')
        text = re.sub(r'\b(\d[\d.]*)' + _EKYAK, _buyuk_sayi, text)

        # Kısaltmalar — rakam zaten yukarıda sözcüğe çevrildi, burada sadece birim
        # kısaltması açılıyor. Arkasındaki hal eki (TL'YE, m³'LÜK gibi) doğru ünlü
        # uyumuyla bağlanır (lira'ye değil liraya, metreküp'lük değil metreküpe vb.).
        def _kisaltma(kelime):
            def _f(m):
                return _tr_attach_suffix(kelime, m.group(1) or '')
            return _f
        text = re.sub(r'\bTL\b' + _EKYAK, _kisaltma('lira'), text)
        text = re.sub(r'\bkm/s\b' + _EKYAK, _kisaltma('kilometre saat'), text, flags=re.IGNORECASE)
        # ² / ³'lü birimler ÖNCE işlenmeli — yoksa \bkm\b gibi eksiz kalıplar
        # önce eşleşip "km²" içindeki "km"yi tek başına yer, "²" açılmadan kalır.
        text = re.sub(r'\bkm²\b' + _EKYAK, _kisaltma('kilometrekare'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bkm³\b' + _EKYAK, _kisaltma('kilometreküp'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bcm²\b' + _EKYAK, _kisaltma('santimetrekare'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bcm³\b' + _EKYAK, _kisaltma('santimetreküp'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bmm²\b' + _EKYAK, _kisaltma('milimetrekare'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bkm\b' + _EKYAK, _kisaltma('kilometre'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bcm\b' + _EKYAK, _kisaltma('santimetre'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bmm\b' + _EKYAK, _kisaltma('milimetre'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bkg\b' + _EKYAK, _kisaltma('kilogram'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bm²\b' + _EKYAK, _kisaltma('metrekare'), text)
        text = re.sub(r'\bm³\b' + _EKYAK, _kisaltma('metreküp'), text)

        # Veri birimleri — bps'li (hız) birimler ÖNCE işlenmeli, yoksa \bMB\b gibi
        # kısa kalıp "Mbps" içindeki "Mb"yi yanlışlıkla yer (sınır kontrolü çoğu
        # zaman engeller ama önce işlemek daha güvenli/açık).
        text = re.sub(r'\bGbps\b' + _EKYAK, _kisaltma('gigabit'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bMbps\b' + _EKYAK, _kisaltma('megabit'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bKbps\b' + _EKYAK, _kisaltma('kilobit'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bTB\b' + _EKYAK, _kisaltma('terabayt'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bGB\b' + _EKYAK, _kisaltma('gigabayt'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bMB\b' + _EKYAK, _kisaltma('megabayt'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bKB\b' + _EKYAK, _kisaltma('kilobayt'), text, flags=re.IGNORECASE)

        # Enerji/konsantrasyon birimleri -- belgesel/haber script'lerinde sık
        # geçiyor (enerji tüketimi, iklim istatistikleri) ama sözlükte yoktu,
        # olduğu gibi TTS'e gidip garip okunuyordu. "saat" son kelimesi zaten
        # yukarıdaki hal eki sözlüklerinde var, bileşik "X saat" biçimi hal
        # ekini doğru bağlıyor (ör. "megavat saate" gibi). TWh/MWh/kWh, tek
        # harfli \bWh\b'den ÖNCE işlenmeli -- yoksa \bWh\b onların içindeki
        # "Wh" kısmını tek başına eşleştirip önekleri (T/M/k) açıklamasız bırakır.
        text = re.sub(r'\bTWh\b' + _EKYAK, _kisaltma('teravat saat'), text)
        text = re.sub(r'\bMWh\b' + _EKYAK, _kisaltma('megavat saat'), text)
        text = re.sub(r'\bkWh\b' + _EKYAK, _kisaltma('kilovat saat'), text, flags=re.IGNORECASE)
        text = re.sub(r'\bWh\b' + _EKYAK, _kisaltma('vat saat'), text)

        # Kısaltma sözlüğümüzde olmayan (ÇYDD, PKK, TRT, KHK gibi — sonsuz
        # sayıda olabilecek) büyük harfli kısaltmalar için son çare: harfleri
        # boşlukla ayır ki Supertonic her harfi ayrı ayrı Türkçe harf ismiyle
        # okusun ('Ç Y D D'), tek bitişik "kelime" gibi okuyup İngilizce
        # telaffuza kaçmasın. İSTİSNA: bazı kısaltmalar Türkçe'de tek kelime
        # gibi okunur (NATO → "nato", FETÖ → "fetö") — onları bölersek bozulur,
        # o yüzden ayrı bir listede tutulup dokunulmuyor.
        _TR_KISALTMA_KELIME_GIBI = {
            'NATO','FETÖ','UEFA','FIFA','AFAD','ASELSAN','TUSAŞ','ROKETSAN','NASA',
            'UNESCO','UNICEF','LIDAR','RADAR','SONAR','INTERPOL',
        }
        # Ardından kesme işaretiyle gelen bir ek varsa (ör. GPU'lar, NASA'nın) onu
        # da bu regex'e yakalatıyoruz -- yoksa ek, aşağıdaki genel güvenlik ağına
        # kalıp harf harf ayrılmış SON harfe boşluksuz yapışıyordu ("G P U'lar" ->
        # "G P Ular" gibi anlamsız/garip bir okunuşa yol açıyordu). Kelime gibi
        # okunanlarda (NASA vb.) ek zaten doğrudan bitişik yazılır (Türkçe'de
        # kesme işareti sadece imla kuralı, telaffuzu etkilemez); harf harf
        # ayrılanlarda ek boşlukla ayrı bir kelime olarak eklenir.
        def _harf_harf(m):
            kelime = m.group(1)
            suffix = m.group(2) or ''
            if kelime.upper() in _TR_KISALTMA_KELIME_GIBI:
                return kelime + suffix
            spelled = ' '.join(kelime)
            return f'{spelled} {suffix}' if suffix else spelled
        text = re.sub(r'\b([A-ZÇĞİÖŞÜ]{2,6})\b' + _EKYAK, _harf_harf, text)

        # Son güvenlik ağı: sayı/birim dışındaki kelimelerde de (özel adlar,
        # "Meteoroloji'den" gibi) kesme işareti+ek kalıyordu — bunlar bizim sayı
        # sözlüğümüzde olmadığı için yukarıdaki _tr_attach_suffix hiç devreye
        # girmiyordu. ÇÖZÜM: eki SİLMEK değil, sadece kesme işaretini kaldırıp
        # ekin harflerini kelimeye BİTİŞİK bırakmak — Türkçe'de kesme işareti
        # zaten yalnızca yazım kuralı, telaffuzu etkilemiyor, bu yüzden
        # "Meteoroloji'den" → "Meteorolojiden" tamamen doğru ve ek korunmuş okunur.
        text = re.sub(r"(?<=\w)['’](?=[a-zçğıöşüA-ZÇĞİÖŞÜ]{1,4}\b)", '', text)

    # URL'leri kaldır (lang != tr için de)
    text = re.sub(r'https?://\S+', '', text)
    # Özel semboller
    text = re.sub(r'[#@|_~^\\<>{}[\]]', ' ', text)
    # Bir kelimeye/rakama bitişik kalan kalıntı tireler (ör. "GPT-3" gibi harf
    # kodu+rakam birleşimlerinden kalan "-üçün") -- saat/yüzde aralığı ve skor
    # regex'lerinin BİLEREK ürettiği " - " (boşluklu, okunabilir duraklama)
    # ayracına DOKUNMUYOR, sadece boşluksuz/bitişik tireleri temizliyor.
    text = re.sub(r'(?<!\s)-(?!\s)', ' ', text)
    # Birden fazla boşluk → tek boşluk
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# Dışa açık, "public" isim — DocuForge tarafında bunu import et.
clean_tts_text = _clean_tts_text
