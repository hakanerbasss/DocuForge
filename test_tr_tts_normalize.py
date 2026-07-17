from app.utils.tr_tts_normalize import clean_tts_text

cases = [
    ("472 kişi katıldı.", "dört yüz yetmiş iki kişi katıldı."),
    ("13. yüzyılda yaşandı.", "on üçüncü yüzyılda yaşandı."),
    ("Oran 0,003 olarak ölçüldü.", "Oran sıfır virgül sıfır sıfır üç olarak ölçüldü."),
    ("Katılım %13,52 arttı.", "Katılım yüzde on üç virgül elli iki arttı."),
    ("Oran %10-15 arasında.", "Oran yüzde on - on beş arasında."),
    ("Toplantı 14:30'da başladı.", "Toplantı saat on dört otuzda başladı."),
    ("Saatler 14:00-16:00 arasında.", "Saatler saat on dört - saat on altı arasında."),
    ("Olay 15.08.2026 tarihinde oldu.", "Olay on beş ağustos iki bin yirmi altı tarihinde oldu."),
    ("Hava 38°C'ye çıktı.", "Hava otuz sekiz dereceye çıktı."),
    ("Sıcaklık -5 dereceye düştü.", "Sıcaklık eksi beş dereceye düştü."),
    ("2027'de tamamlanacak.", "iki bin yirmi yedide tamamlanacak."),
    ("250 TL'ye satıldı.", "iki yüz elli liraya satıldı."),
    ("Alan 10 km²'lik bir bölge.", "Alan on kilometrekare bir bölge."),
    ("Dosya 5GB boyutunda.", "Dosya beş gigabayt boyutunda."),
    ("5G'ye geçti.", "beşinci nesile geçti."),
    ("Maç 3-1 bitti.", "Maç üç bir bitti."),
    (
        "TBMM'de görüşüldü.",
        "Türkiye Büyük Millet Meclisinde görüşüldü.",
    ),
    ("YKS'ye hazırlanıyor.", "Yükseköğretim Kurumları Sınavına hazırlanıyor."),
    ("ÇYDD toplantı yaptı.", "Ç Y D D toplantı yaptı."),
    ("NATO zirvesi yapıldı.", "NATO zirvesi yapıldı."),
    ("**kalın** ve `kod` metin.", "kalın ve metin."),
    # Gerçek üretim script'inde (yapay_zeka_dogayi_kurtarabilir_mi) bulunan,
    # daha önce yanlış okunan kalıplar.
    ("Sıcaklık 1.2 derece arttı.", "Sıcaklık bir virgül iki derece arttı."),
    ("Bir sorgu 2.9 Wh enerji tüketiyor.", "Bir sorgu iki virgül dokuz vat saat enerji tüketiyor."),
    ("Tüketim 85 ile 134 TWh arasında.", "Tüketim seksen beş ile yüz otuz dört teravat saat arasında."),
    ("Eğitim 200 MWh enerji tüketti.", "Eğitim iki yüz megavat saat enerji tüketti."),
    ("280 ppm iken 420 ppm'e ulaştı.", "milyonda iki yüz seksen iken milyonda dört yüz yirmiye ulaştı."),
    ("NASA'nın verilerine göre.", "NASAnın verilerine göre."),
    ("GPU'lar ve TPU'lar yenileniyor.", "G P U lar ve T P U lar yenileniyor."),
    ("GPT-3'ün eğitimi uzun sürdü.", "G P T üçün eğitimi uzun sürdü."),
]

failures = []
for source, expected in cases:
    actual = clean_tts_text(source, lang="tr")
    status = "OK" if actual == expected else "FAIL"
    if status == "FAIL":
        failures.append((source, expected, actual))
    print(f"[{status}] {source!r} -> {actual!r}")

# Türkçe olmayan dil dokunulmadan geçmeli (sadece markdown/URL temizliği).
en_source = "There are 472 people here."
en_result = clean_tts_text(en_source, lang="en")
en_status = "OK" if en_result == en_source else "FAIL"
if en_status == "FAIL":
    failures.append((en_source, en_source, en_result))
print(f"[{en_status}] lang=en passthrough -> {en_result!r}")

if failures:
    print(f"\n{len(failures)} test(s) failed:")
    for source, expected, actual in failures:
        print(f"  source:   {source!r}")
        print(f"  expected: {expected!r}")
        print(f"  actual:   {actual!r}")
    raise SystemExit(1)

print(f"\nAll {len(cases) + 1} tests passed.")
