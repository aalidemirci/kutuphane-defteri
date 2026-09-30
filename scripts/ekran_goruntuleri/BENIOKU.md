# Ekran görüntüleri

okulapp.org program sayfasının ekran görüntülerini **uydurma veriyle** ve tek komutla
yeniden üretir. Her şey Docker'da koşar; host'a Python ya da Node kurulmaz.

```bash
bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh             # site görüntüleri (2x PNG + WebP)
bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh --kesif     # bütün ekranlar, 1x (seçim için)
bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh --sahne katalog --sahne raporlar
KD_EKRAN_DERLE=0 bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh   # ön yüzü yeniden derleme
```

Çıktı `dist/ekran-goruntuleri/` altındadır (`dist/` `.gitignore`'dadır):

| Klasör | İçerik |
|---|---|
| `png/` | 1440×900 görünüm alanı, aygıt piksel oranı 2 → 2880×1800 PNG (Genel Bakış'ta alt kenar kartlar arasındaki boşluğa alınır: 16:10 korunarak biraz küçük, ör. 1416×885) |
| `webp/` | Site için 1280×800 WebP, kalite 90 (kardeş sayfaların görüntüleriyle aynı ölçü) |
| `kesif/` | `--kesif` ile: bütün ekranlar 1x, hangi görüntünün siteye gideceğini seçmek için |

Görüntüler (`ekran_cekimi.py::SAHNELER`): `genel-bakis`, `katalog` (Türkçe arama ve
sıralama), `dolasim-masasi` (üye kartı + kitap etiketi → ödünç), `etiketler` (basım
kuyruğu), `ag-katalogu` (tahta kipinde arama), `raporlar` (kişisiz istatistik); seçenek
olarak `ag-katalogu-vitrin` (tahta kipinde ana sayfa) ve `eser-ayrintisi`.

## Adımlar

1. **Ön yüz derlemesi** — `frontend` kabında `npm run build` (programın sunduğu arayüz).
2. **Geçici Playwright imajı** — Microsoft'un resmî `mcr.microsoft.com/playwright/python`
   imajı + `playwright` paketi + Inter ve DejaVu yazı tipleri. **Depo bağımlılığı değildir:**
   `requirements*.txt`'ye, PyInstaller spec'ine ve lisans listesine girmez, pakete
   girmez; yalnız bu betiğin yerel imajıdır (`docker rmi kd-ekran-playwright:1.49.1`).
   İlk koşu imajı indirir (ağ ister, ~3,5 GB).
3. **Program** — `ekran_sunucusu.py` backend kabında programı **gerçek masaüstü
   yolundan** kaldırır (`scripts/ag_katalogu_provasi.py`'nin `sun` adımı gibi): açılışa
   özel oturum belirteci, `prepare_django` + göç, yönetim sunucusu 127.0.0.1'de
   rastgele portta (belirteç koruması ve sağlık denetimiyle), Ağ Kataloğu
   `KatalogKontrol` ile 8765'te. Güvenlik kuralı gevşetilmez: tarayıcı pencerenin
   belirteçli açılış adresini açar, belirteç `HttpOnly` çereze geçer.
4. **Görüntüler** — `ekran_cekimi.py` Playwright kabında, program kabının **ağ ad
   alanında** (`--network container:kd-ekran`) koşar; dışarıya hiçbir port açılmaz.
   Türkçe yerel ayar, Europe/Istanbul, açık tema. Tam Chromium'un yeni başsız kipi
   kullanılır: yerleşik tarih kutuları yalnız onda Türkçe (gg.aa.yyyy) basılır. Ağ
   Kataloğu ayrı tarayıcı bağlamında açılır (tahta başka bir bilgisayardır; çerezler
   portlar arasında yalıtılmaz).
5. **WebP** — `webp_cevir.py` backend kabında Pillow ile (Pillow programın zaten
   bağımlılığıdır).

## Veri (hepsi uydurma — CLAUDE.md §2-12)

- Kurulum sihirbazının üç adımı servislerle: yönetici parolası (uydurma, geçici) ve
  kurtarma anahtarı doğrulaması, okul bilgileri ("Örnek Anadolu Lisesi", "Örnek İlçe"),
  2026-2027 ders yılı, iki dönem, resmî/dini tatiller, öğrenciye kapalı günler.
- `scripts/deneme_verisi.py`'nin e-Okul öğrenci ve personel listeleri ile ~2.000
  eserlik katalog Excel'i, programın gerçek içe aktarıcılarından (`test_deneme_verisi.py`
  ile aynı yol). Kişi adları ad ve soyad havuzlarının rastgele birleşimidir.
- Eylül'ün okul günleri boyunca üyelik, ödünç ve iade (saat o güne sabitlenerek;
  servisler tarihi kendileri yazar), bir kısmı gecikmiş açık ödünç, sınıf kitaplığına ve
  bir öğretmene teslim, çok okunanlar hesabı (en az k farklı üye), yıl sonu sayımının
  taslağı, Ağ Kataloğu "Aç"; Başlangıç Yol Haritası tamamlanıp gizlenmiş.
- Görüntü günü 30.09.2026'dır; tohum sabittir, her koşu aynı veriyi üretir (kapta
  saat gerçek saattir: "bugün" o günün tarihidir).

Veri dizini kabın `/tmp`'sindedir ve kapla silinir; depoya veri girmez. Durum dosyası
(`dist/ekran-goruntuleri/durum.json`: belirteçli açılış adresi, sahne verisi) sunum
bitince silinir.

**Kişi adı görünen görüntü** yalnız `dolasim-masasi`dır (uydurma üye); öbürleri kişi adı
göstermez (katalogdaki yazar ve çevirmen adları da uydurma künyedir, klasikler dışında).
Herkese açık metinde gerçek kurum, kişi ve IP yazılmaz.

## Bilinen farklar

- Yazı tipi: program Windows'ta "Segoe UI Variable" ile görünür; kapta o yazı tipi
  yoktur, arayüzün yığınındaki **Inter** kullanılır. Ağ Kataloğu yığınının ilk yazı
  tipiyle, **DejaVu Sans** ile görünür (Pardus'lu etkileşimli tahtadaki gibi).
- Üst çubuktaki "Yönetici kipi m:ss" geri sayımı gerçek davranıştır (boşta süre, §4.4);
  sunucu masadaki etkinliği iki saniyede bir tazelediği için tam süreye yakın görünür.
- Görüntü, programın o sürümdeki arayüzüdür; ekran metni ya da düzen değişince betik
  yeniden koşulur ve sitedeki kareler (`okulapp.org/public/kutuphane-defteri/`) ile
  açıklamaları (`docs/site-icerigi.md` §8) birlikte güncellenir.
