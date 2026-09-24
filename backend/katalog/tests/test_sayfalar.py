"""Ağ Kataloğu sayfaları — arama, dizinler, eser sayfası, vitrin (tasarım §5.1-§5.4).

Koruma testleri: §5.10-5 (kişisel veri hiçbir sayfada yok), §5.10-6 (`sayfa`
ve `id` doğrulaması), §5.10-7 (eser adındaki `<script>` kaçırılır), §5.10-9
(program kilitliyken katalog 200), §5.10-16 (klavyesiz gezinme) ve TR arama
kapısı ("şiir"/"ŞİİR", "ılık"/"ILIK", "İnce"/"ince").
"""

from __future__ import annotations

import re
from collections import deque
from datetime import date

import pytest

from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    Copy,
    CopyStatus,
    DonationIntake,
    KatalogAyari,
    KatalogPopuler,
    PopulerPencereTuru,
    ResourceType,
)
from apps.kutuphane.tests.ortak import bolum, edinim, eser, karar, nusha
from apps.okul.models import Personnel, SchoolConfig, Student
from katalog import sabitler
from katalog.tests.conftest import KatalogIstemcisi

pytestmark = pytest.mark.django_db(transaction=True)


def _eser_idleri(metin: str) -> set[int]:
    return {int(i) for i in re.findall(r'href="/eser/(\d+)', metin)}


def _okul(**alanlar: object) -> SchoolConfig:
    config: SchoolConfig
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    for ad, deger in alanlar.items():
        setattr(config, ad, deger)
    config.save()
    return config


# ============================================================ TR arama kapısı (T7)


@pytest.mark.parametrize(
    ("sorgu", "beklenen"),
    [
        ("şiir", "Şiir Defteri"),
        ("ŞİİR", "Şiir Defteri"),
        ("ılık", "Ilık Rüzgâr"),
        ("ILIK", "Ilık Rüzgâr"),
        ("rüzgar", "Ilık Rüzgâr"),  # düzeltme işareti katlanır
        ("İnce", "İnce Memed"),
        ("ince", "İnce Memed"),
        ("memed ince", "İnce Memed"),  # sözcük sırası önemsiz (AND)
        ("yaşar", "İnce Memed"),  # yazar ekseni
    ],
)
def test_turkce_arama_kapisi(katalog: KatalogIstemcisi, sorgu: str, beklenen: str) -> None:
    for baslik, yazar in (
        ("Şiir Defteri", "Deneme Şair"),
        ("Ilık Rüzgâr", "Deneme Yazar"),
        ("İnce Memed", "Yaşar Kemal"),
        ("Isırgan Otu", "Deneme Yazar"),
    ):
        nusha(eser(title=baslik, authors=yazar))

    yanit = katalog.get("/ara?q=" + _kodla(sorgu))

    assert yanit.code == 200
    assert beklenen in yanit.text
    assert yanit.text.count('class="eser-baslik"') == 1


def _kodla(metin: str) -> str:
    from katalog.istek import yuzde_kodla

    return yuzde_kodla(metin)


def test_i_ile_ı_ayri_kalir(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Ilık Su"))
    nusha(eser(title="İlik Kemik"))

    assert "İlik Kemik" not in katalog.get("/ara?q=ılık").text
    assert "Ilık Su" not in katalog.get("/ara?q=ilik").text


def test_isbn_tireli_ve_tiresiz_bulunur(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Numaralı Kitap", isbn="978-605-00-0000-1"))

    assert "Numaralı Kitap" in katalog.get("/ara?q=978-605-00-0000-1").text
    assert "Numaralı Kitap" in katalog.get("/ara?q=9786050000001").text


def test_like_joker_karakterleri_kacirilir(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Sıradan Kitap"))

    for joker in ("%25", "_", "%5C"):
        assert katalog.get(f"/ara?q={joker}").text.count('class="eser-baslik"') == 0


def test_bos_arama_butun_kaynaklari_listeler_ve_arama_sayilir(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Birinci"))
    nusha(eser(title="İkinci"))

    yanit = katalog.get("/ara")

    assert "Bütün Kaynaklar" in yanit.text
    assert "2 kaynak bulundu." in yanit.text
    assert katalog.uygulama.sayaclar.gun()["arama"] == 1


def test_uzun_arama_100_karakterde_kirpilir(katalog: KatalogIstemcisi) -> None:
    yanit = katalog.get("/ara?q=" + "a" * 150)

    assert yanit.code == 200
    assert "100 karakterle sınırlandı" in yanit.text
    assert 'value="' + "a" * 100 + '"' in yanit.text


def test_tur_ve_konu_suzgeci(katalog: KatalogIstemcisi) -> None:
    roman = eser(title="Roman Eseri", classification_code="813.54")
    nusha(roman)
    tarih = eser(title="Tarih Eseri", classification_code="956.1")
    nusha(tarih)
    dijital = eser(title="Dijital Eser", resource_type=ResourceType.EBOOK)

    assert _eser_idleri(katalog.get("/ara?konu=8").text) == {roman.pk}
    assert _eser_idleri(katalog.get("/ara?konu=9").text) == {tarih.pk}
    assert _eser_idleri(katalog.get("/ara?tur=e-kitap").text) == {dijital.pk}
    assert _eser_idleri(katalog.get("/ara?tur=kitap&konu=8").text) == {roman.pk}


# ====================================================== §5.10-6 doğrulama ve sayfalama


@pytest.mark.parametrize(
    "adres",
    [
        "/eser/abc",
        "/eser/0",
        "/eser/007",
        "/eser/-1",
        "/eser/1.0",
        "/eser/%D9%A1",  # Arapça-Hint rakamı "١"
        "/eser/9999999999999",
        "/eser/424242",  # yok
        "/ara?tur=roman",
        "/ara?tur=BOOK",
        "/ara?konu=10",
        "/ara?konu=x",
        "/ara?sayfa=abc",
        "/ara?sayfa=-1",
        "/ara?sayfa=1234567",
        "/eserler/AA",
        "/eserler/%C3%A7",  # küçük "ç"
        "/yazarlar/1",
        "/konular/x",
        "/eserler?sayfa=x",
    ],
)
def test_gecersiz_parametre_404_doner(katalog: KatalogIstemcisi, adres: str) -> None:
    yanit = katalog.get(adres)

    assert yanit.code == 404, adres
    assert "Sayfa bulunamadı" in yanit.text


def test_sayfa_kirpilir_ve_sayfalama_baglantilari_dogru(katalog: KatalogIstemcisi) -> None:
    acquisition = edinim()
    for sira in range(25):
        nusha(eser(title=f"Eser {sira:02d}"), acquisition)

    ilk = katalog.get("/ara")
    son = katalog.get("/ara?sayfa=999")  # 2'ye kırpılır
    sifir = katalog.get("/ara?sayfa=0")  # 1'e kırpılır

    assert len(_eser_idleri(ilk.text)) == 20
    assert "Sayfa 1 / 2" in ilk.text
    assert "/ara?sayfa=2" in ilk.baglantilar()
    assert son.code == 200 and "Sayfa 2 / 2" in son.text
    assert len(_eser_idleri(son.text)) == 5
    assert "Sayfa 1 / 2" in sifir.text


def test_sayfa_sayisi_500de_tavanlanir() -> None:
    from katalog import veri

    assert veri.sayfa_kirp(10_000, 20 * 10_000) == (500, 500)
    assert veri.sayfa_kirp(3, 0) == (1, 1)
    assert veri.sayfa_kirp(2, 21) == (2, 2)


# ============================================================ §5.10-7 XSS


def test_eser_adindaki_betik_kacirilarak_basilir(katalog: KatalogIstemcisi) -> None:
    kotu = '<script>alert("x")</script> & "Tırnak" <b>kalın</b>'
    work = eser(title=kotu, authors="<img src=x onerror=alert(1)>", subjects="<i>konu</i>")
    nusha(work)

    sayfalar = [
        katalog.get(f"/eser/{work.pk}"),
        katalog.get("/ara?q=script"),
        katalog.get("/eserler/diger"),
        katalog.get("/ara"),
        katalog.get("/"),
    ]
    for yanit in sayfalar:
        assert yanit.code == 200
        assert "<script" not in yanit.text.lower()
        assert "<img" not in yanit.text.lower()
        assert "<b>kalın" not in yanit.text
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &quot;Tırnak&quot;" in (
        sayfalar[0].text
    )


def test_arama_metni_form_degerinde_kacirilir(katalog: KatalogIstemcisi) -> None:
    yanit = katalog.get("/ara?q=" + _kodla('"><script>x</script>'))

    assert "<script" not in yanit.text.lower()
    assert 'value="&quot;&gt;&lt;script&gt;x&lt;/script&gt;"' in yanit.text


# ============================================ §5.10-5 kişisel veri hiçbir sayfada yok


SENTINELLER = {
    "ogrenci_ad": "Zeynepkatalogdeneme",
    "ogrenci_soyad": "Soyadkatalogdeneme",
    "okul_no": "98765",
    "personel_ad": "Personelkatalogdeneme",
    "bagisci": "Bagiscikatalogdeneme",
    "bagis_on_kaydi": "Onkayitkatalogdeneme",
    "komisyon_baskani": "Baskankatalogdeneme",
    "tkys": "Tkyskatalogdeneme",
    "eski_kayit": "Eskikayitkatalogdeneme",
    "mudur": "Mudurkatalogdeneme",
    "demirbas": "Demirbaskatalogdeneme",
    "seçili_ip": "10.77.66.55",
}


def _gez(katalog: KatalogIstemcisi, baslangic: list[str], *, sinir: int = 400) -> dict[str, str]:
    """Katalog içi bütün bağlantıları izleyerek sayfaları toplar (adres → metin)."""
    gorulen: dict[str, str] = {}
    kuyruk = deque(baslangic)
    while kuyruk and len(gorulen) < sinir:
        adres = kuyruk.popleft()
        if adres in gorulen or not adres.startswith("/"):
            continue
        yanit = katalog.get(adres)
        gorulen[adres] = yanit.body.decode("utf-8", errors="replace")
        if yanit.header("Content-Type") == "text/html; charset=utf-8":
            kuyruk.extend(b for b in yanit.baglantilar() if b not in gorulen)
    return gorulen


def test_sentetik_kisi_verisi_hicbir_katalog_sayfasinda_gecmez(katalog: KatalogIstemcisi) -> None:
    Student.objects.create(
        first_name=SENTINELLER["ogrenci_ad"],
        last_name=SENTINELLER["ogrenci_soyad"],
        student_number=SENTINELLER["okul_no"],
        class_level=9,
        class_section="A",
    )
    Personnel.objects.create(first_name=SENTINELLER["personel_ad"], last_name="Deneme")
    karar_ = karar(chair_name=SENTINELLER["komisyon_baskani"])
    bagis = Acquisition.objects.create(
        method=AcquisitionMethod.DONATION,
        date=date(2026, 9, 1),
        source_note=SENTINELLER["bagisci"],
        commission_decision=karar_,
        unit_price="123.45",
    )
    DonationIntake.objects.create(
        donor_name=SENTINELLER["bagis_on_kaydi"], received_date=date(2026, 9, 2)
    )
    _okul(
        school_name="Örnek Anadolu Lisesi",
        principal_name=SENTINELLER["mudur"],
        demirbas_no=SENTINELLER["demirbas"],
        kutuphane_saatleri="Hafta içi 08.30-16.30",
    )
    KatalogAyari.objects.create(
        pk=KatalogAyari.SINGLETON_PK,
        dinleme_kipi="SELECTED",
        secili_ip=SENTINELLER["seçili_ip"],
    )
    work = eser(title="Kişisiz Eser", authors="Deneme Yazar", subjects="Tarih")
    copy = nusha(
        work,
        bagis,
        external_asset_ref=SENTINELLER["tkys"],
        old_register_no=SENTINELLER["eski_kayit"],
    )
    Copy.objects.filter(pk=copy.pk).update(status=CopyStatus.ON_LOAN)
    nusha(eser(title="Başka Eser", authors="Ali Veli"))
    KatalogPopuler.objects.create(
        eser=work,
        pencere_turu=PopulerPencereTuru.DONEM,
        pencere="2026-2027/1",
        sira=1,
        hesaplanma=date(2026, 9, 20),
    )

    sayfalar = _gez(
        katalog,
        ["/", "/ara", "/hakkinda", "/konular", "/ara?q=eser", "/ara?q=tarih", "/?tahta=1"],
    )
    barkodlar = list(Copy.all_objects.values_list("barcode", flat=True))

    assert f"/eser/{work.pk}" in sayfalar  # gezinti gerçekten veriye ulaştı
    assert "Örnek Anadolu Lisesi" in sayfalar["/"]
    for adres, metin in sayfalar.items():
        for ad, deger in SENTINELLER.items():
            assert deger.casefold() not in metin.casefold(), f"{ad} {adres} sayfasında geçti"
        for barkod in barkodlar:
            assert barkod not in metin, f"barkod {adres} sayfasında geçti"
        assert "123.45" not in metin and "123,45" not in metin  # fiyat


# ======================================= §5.10-9 program kilitliyken katalog çalışır


def test_program_kilitliyken_katalog_200_doner(
    katalog: KatalogIstemcisi, request: pytest.FixtureRequest
) -> None:
    from shared import crypto

    work = eser(title="Kilitte Okunan", authors="Deneme Yazar")
    nusha(work)
    request.getfixturevalue("kilitli")  # veri girildikten SONRA program kilitlenir
    assert not crypto.is_unlocked()

    for adres in ("/", "/ara?q=kilitte", f"/eser/{work.pk}", "/eserler/K", "/hakkinda"):
        yanit = katalog.get(adres)
        assert yanit.code == 200, adres
    assert "Kilitte Okunan" in katalog.get("/ara?q=kilitte").text


# ============================================== §5.10-16 klavyesiz gezinme (A-Z, konular)


def test_aramasiz_yalniz_baglantilarla_her_esere_ulasilir(katalog: KatalogIstemcisi) -> None:
    b = bolum(name="Edebiyat")
    eserler = [
        eser(title="Çalıkuşu", authors="Reşat Nuri Güntekin", classification_code="813"),
        eser(title="İnce Memed", authors="Yaşar Kemal", subjects="Roman"),
        eser(title="1984", authors="George Orwell"),
        eser(title="Şiirler", authors="", section=b),
        eser(title="Ansiklopedi", resource_type=ResourceType.EDATABASE),
    ]
    for work in eserler[:4]:
        nusha(work)

    gorulen: set[str] = set()
    kuyruk = deque(["/"])
    ulasilan: set[int] = set()
    while kuyruk:
        adres = kuyruk.popleft()
        if adres in gorulen:
            continue
        gorulen.add(adres)
        yanit = katalog.get(adres)
        assert yanit.code == 200, adres
        if not (yanit.header("Content-Type") or "").startswith("text/html"):
            continue
        for bag in yanit.baglantilar():
            # Arama metni taşıyan bağlantı YOK sayılır: ekran klavyesi kullanılmaz.
            if "q=" in bag or not bag.startswith("/") or bag in gorulen:
                continue
            eslesme = re.fullmatch(r"/eser/(\d+)", bag)
            if eslesme:
                ulasilan.add(int(eslesme.group(1)))
            kuyruk.append(bag)

    assert ulasilan == {w.pk for w in eserler}
    assert not any("q=" in adres for adres in gorulen)


def test_harf_cubugu_bos_harfi_baglanti_yapmaz(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Çalıkuşu"))

    yanit = katalog.get("/eserler")

    assert "/eserler/%C3%87" in yanit.baglantilar()  # Ç
    assert "/eserler/A" not in yanit.baglantilar()
    assert "<span>A</span>" in yanit.text


def test_harf_dizini_turk_alfabesi_sirasiyla(katalog: KatalogIstemcisi) -> None:
    for baslik in ("Ölçü", "Oda", "Otel", "Öykü"):
        nusha(eser(title=baslik))

    o = katalog.get("/eserler/O").text
    o_noktali = katalog.get("/eserler/%C3%96").text

    assert o.index("Oda") < o.index("Otel")
    assert "Ölçü" not in o
    assert o_noktali.index("Ölçü") < o_noktali.index("Öykü")


def test_yazar_dizini_soyada_gore(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Kitap A", authors="Sabahattin Ali"))
    nusha(eser(title="Kitap B", authors="Ali Sabahattin"))

    a = katalog.get("/yazarlar/A").text
    s = katalog.get("/yazarlar/S").text

    assert "Kitap A" in a and "Kitap B" not in a
    assert "Kitap B" in s


# ================================================================ eser sayfası


def test_eser_sayfasi_kunye_ve_nusha_durumlari(katalog: KatalogIstemcisi) -> None:
    b = bolum(name="Edebiyat", description="Roman ve öykü")
    work = eser(
        title="Kürk Mantolu Madonna",
        authors="Sabahattin Ali",
        publisher="Örnek Yayınevi",
        classification_code="813.54",
        section=b,
    )
    rafta = nusha(work, section=b)
    oduncte = nusha(work)
    sinifta = nusha(work)
    onarimda = nusha(work)
    danisma = nusha(work, is_reference=True)
    kayip = nusha(work)
    Copy.objects.filter(pk=oduncte.pk).update(status=CopyStatus.ON_LOAN)
    Copy.objects.filter(pk=sinifta.pk).update(status=CopyStatus.DELIVERED)
    Copy.objects.filter(pk=onarimda.pk).update(status=CopyStatus.IN_REPAIR)
    Copy.objects.filter(pk=kayip.pk).update(status=CopyStatus.LOST)

    metin = katalog.get(f"/eser/{work.pk}").text

    assert "Örnek Yayınevi" in metin
    assert "Dewey Onlu Sınıflama (DOS) ana sınıfı: 800 Edebiyat" in metin
    assert "Edebiyat — Roman ve öykü" in metin
    assert "5 nüsha · 2 rafta · 1 ödünçte · 1 sınıf kitaplığında · 1 onarımda" in metin
    for ad in ("Rafta", "Ödünçte", "Sınıf kitaplığında", "Onarımda", sabitler.ODUNC_VERILMEZ):
        assert ad in metin
    assert "Kayıp" not in metin
    for copy in (rafta, danisma):
        assert copy.barcode not in metin


def test_yalniz_danisma_nushasi_olan_eser_odunc_verilmez_der(katalog: KatalogIstemcisi) -> None:
    work = eser(title="Büyük Sözlük")
    nusha(work, is_reference=True)

    assert f"1 nüsha · 1 rafta · {sabitler.ODUNC_VERILMEZ}" in katalog.get("/ara").text


def test_dijital_ve_ciltsiz_sureli_yayin_kunye_olarak_listelenir(
    katalog: KatalogIstemcisi,
) -> None:
    eser(title="E-Kaynak", resource_type=ResourceType.EBOOK)
    eser(title="Aylık Dergi", resource_type=ResourceType.PERIODICAL)

    metin = katalog.get("/ara").text

    assert "Dijital kaynak — künye bilgisidir" in metin
    assert "Kütüphanede okunur." in metin


# ======================================================== vitrin, konular, hakkında


def test_vitrin_yeni_gelenler_ve_cok_okunanlar(katalog: KatalogIstemcisi) -> None:
    eski = eser(title="Eski Gelen")
    nusha(eski)
    yeni = eser(title="Yeni Gelen")
    nusha(yeni)
    silinen = eser(title="Silinen Popüler")
    nusha(silinen)
    for sira, work in enumerate((yeni, silinen, eski), start=1):
        KatalogPopuler.objects.create(
            eser=work,
            pencere_turu=PopulerPencereTuru.DONEM,
            pencere="2026-2027/1",
            sira=sira,
            hesaplanma=date(2026, 9, 20),
        )
    silinen.delete()

    metin = katalog.get("/").text

    assert "Yeni Gelenler" in metin and "Çok Okunanlar" in metin
    yeni_gelenler = metin.split("Yeni Gelenler", 1)[1].split("Çok Okunanlar", 1)[0]
    assert yeni_gelenler.index("Yeni Gelen") < yeni_gelenler.index("Eski Gelen")
    cok = metin.split("Çok Okunanlar", 1)[1]
    assert cok.index("Yeni Gelen") < cok.index("Eski Gelen")
    assert "Silinen Popüler" not in metin
    assert not re.search(r"\d+ kez|\d+ ödünç", metin)  # sayı gösterilmez


def test_vitrin_ve_konular_ayarla_kapanir(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Vitrin Eseri", subjects="Tarih"))
    KatalogAyari.objects.create(pk=KatalogAyari.SINGLETON_PK, vitrin_acik=False, konular_acik=False)

    ana = katalog.get("/")

    assert "Yeni Gelenler" not in ana.text
    assert "/konular" not in ana.baglantilar()
    assert katalog.get("/konular").code == 404
    assert katalog.get("/konular/T").code == 404


def test_konular_dos_ana_siniflari_ve_konu_dizini(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Roman", classification_code="813", subjects="Roman"))
    nusha(eser(title="Kodsuz", subjects="Tarih"))

    yanit = katalog.get("/konular")

    assert "Dewey Onlu Sınıflama (DOS) Ana Sınıfları" in yanit.text
    assert "/ara?konu=8" in yanit.baglantilar()
    assert "/ara?konu=1" not in yanit.baglantilar()  # boş sınıf bağlantı değil
    assert "Sınıflama kodu girilmemiş kaynaklar: 1" in yanit.text
    assert "/konular/T" in yanit.baglantilar()
    assert "Kodsuz" in katalog.get("/konular/T").text


def test_hakkinda_saatleri_ve_kisisel_veri_bildirimini_gosterir(
    katalog: KatalogIstemcisi,
) -> None:
    _okul(kutuphane_saatleri="Pazartesi-Cuma\n08.30-16.30")

    metin = katalog.get("/hakkinda").text

    assert "Pazartesi-Cuma<br>08.30-16.30" in metin
    assert "Ağ Kataloğu kişisel veri göstermez" in metin
    assert "yerel araç" in metin
    assert "Bakanlık" not in metin  # konum dili: yerine geçme iddiası yok


# =================================================================== tahta kipi


def test_tahta_kipi_buyuk_duzeni_secer_ve_baglantilarda_korunur(
    katalog: KatalogIstemcisi,
) -> None:
    work = eser(title="Tahta Eseri")
    nusha(work)

    for adres in ("/?tahta=1", "/ara?tahta=1", f"/eser/{work.pk}?tahta=1", "/eserler?tahta=1"):
        yanit = katalog.get(adres)
        assert '<body class="tahta">' in yanit.text, adres
        ic_baglantilar = [
            b for b in yanit.baglantilar() if b.startswith("/") and b != "/katalog.css"
        ]
        assert ic_baglantilar
        assert all("tahta=1" in b for b in ic_baglantilar), (adres, ic_baglantilar)
    form = katalog.get("/?tahta=1").text
    assert '<input type="hidden" name="tahta" value="1">' in form
    assert '<body class="tahta">' not in katalog.get("/").text


def test_stil_dokunmatik_ekranda_48_piksel_hedef_verir() -> None:
    css = sabitler_css()

    assert "@media (any-pointer: coarse)" in css
    assert "min-height: 48px" in css
    assert "display: grid" not in css and "var(--" not in css  # eski tarayıcı uyumu


def sabitler_css() -> str:
    from katalog.sayfalar import CSS_BAYTLARI

    return CSS_BAYTLARI.decode("utf-8")


# ================================================================ sayaçlar


def test_gunluk_sayaclar_kisisizdir(katalog: KatalogIstemcisi) -> None:
    nusha(eser(title="Sayılan"))

    katalog.get("/", istemci="10.9.8.7")
    katalog.get("/ara?q=sayilan", istemci="10.9.8.7")
    katalog.get("/yok", istemci="10.9.8.7")

    gun = katalog.uygulama.sayaclar.gun()
    assert gun["sayfa"] == 2 and gun["arama"] == 1 and gun["bulunamadi"] == 1
    ozet = repr(katalog.uygulama.sayaclar.ozet())
    assert "10.9.8.7" not in ozet and "sayilan" not in ozet.lower()
