"""Görev devri (F11; tasarım §4.4 SU-25, §10 E18) — tek akış ve Görev devri notu.

Kanıtlanan maddeler:

* **Tek akış**: `POST library/handover/start/` parolayı VE kurtarma anahtarını tek
  atomik yazımda yeniler; eski parola ve eski anahtar kilidi açmaz, yenileri açar;
  önceki güvenlik dosyası arşive KOPYALANIR; yeni anahtar yanıtla bir kez döner
  (`no-store`); yanlış mevcut parola ve aynı parola hiçbir dosyayı değiştirmez.
* **DEK değişmez** (TB17, TB23): kayıtlar ve kör indeks devirden sonra da okunur.
  Sınır sabitlenir (F11 düzeltme turu): eski parola eski bir başlıkla devirden SONRA
  alınan yedeği ve (arşiv yerine konunca) kilidi açar — metinler bunu söyler.
* **Not ancak doğrulamadan sonra**: devir + doğrulama damgası yoksa 409
  `gorev_devri_eksik`; sonraki "Kurtarma anahtarını yenile" devir damgasını düşürür.
* **E18 içeriği**: devir ve doğrulama anları, teslim edilenler (boş kutu), açık işlerin
  kişisiz sayıları, eski yedeklerin ve arşivin sayısı, dürüst sınır cümlesi; adlar
  yalnız PDF'tedir (saklanmaz, günlüğe ve dosya adına girmez); sayfa bütçesi gerçek
  uzunlukta veriyle en çok iki sayfa; "imha" sözcüğü yok (sözlük §1).
* **Mevzuat atfı metinden doğrulanır** (KVKK 12/4, Yönerge 6/4).
* **Kapılar**: görevli kipinde 403, kilitliyken 423.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import gorev_devri
from apps.kutuphane.tests.dolasim_ortak import odunc_ver, ogrenci, uye
from apps.okul.kip import KIP
from apps.okul.models import Student
from apps.okul.services import app_password, persons
from conftest import TEST_KURTARMA_ANAHTARI, TEST_PAROLA
from shared import crypto

BASLAT = "/api/v1/library/handover/start/"
NOT = "/api/v1/library/handover/note/"
DURUM = "/api/v1/library/handover/"
YENI_PAROLA = "Devralan-Yeni-Parola-9"

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _baslat(client: APIClient, mevcut: str = TEST_PAROLA, yeni: str = YENI_PAROLA) -> Any:
    return client.post(BASLAT, {"current_password": mevcut, "new_password": yeni}, format="json")


def _arsivler() -> list[Path]:
    return sorted(
        app_password.state_path().parent.glob(f"{app_password.STATE_ARCHIVE_PREFIX}*.json")
    )


def _metin(icerik: bytes) -> str:
    return "\n".join(sayfa.extract_text() or "" for sayfa in PdfReader(BytesIO(icerik)).pages)


def _pdf(yanit: Any) -> bytes:
    return b"".join(yanit.streaming_content)


def _devri_tamamla(client: APIClient) -> str:
    yanit = _baslat(client)
    assert yanit.status_code == 200, yanit.content
    anahtar: str = yanit.json()["recovery_key"]
    app_password.confirm_recovery_key(anahtar)
    return anahtar


# ============================================================ tek akış


def test_parola_ve_anahtar_birlikte_yenilenir_eskileri_acmaz(client: APIClient) -> None:
    onceki = app_password.state_path().read_bytes()

    yanit = _baslat(client)

    assert yanit.status_code == 200
    assert yanit["Cache-Control"] == "no-store"
    govde = yanit.json()
    yeni_anahtar = govde["recovery_key"]
    assert re.fullmatch(r"[A-Z2-7]{4}(-[A-Z2-7]{4}){7}", yeni_anahtar)
    assert govde["recovery_key_confirmed"] is False
    assert govde["handover"]["started_at"]
    assert govde["handover"]["note_available"] is False
    # Önceki dosya arşive kopyalandı (asıl dosya hiçbir an yok olmadı).
    arsivler = _arsivler()
    assert len(arsivler) == 1 and arsivler[0].read_bytes() == onceki

    # Yeni parola ve yeni anahtar açar; eskiler açmaz.
    with pytest.raises(app_password.AppPasswordError, match="Parola hatalı"):
        app_password.verify_password(TEST_PAROLA)
    app_password.verify_password(YENI_PAROLA)
    with pytest.raises(app_password.AppPasswordError, match="Kurtarma anahtarı hatalı"):
        app_password.verify_recovery_key(TEST_KURTARMA_ANAHTARI)
    assert app_password.verify_recovery_key(yeni_anahtar)


def test_dek_degismez_kayitlar_ve_kor_indeks_okunur(client: APIClient) -> None:
    kayit = ogrenci(first_name="Deneme Çağrı", last_name="Işıkoğlu", student_number="880011")
    parmak = crypto.active_fingerprint()

    _devri_tamamla(client)

    assert crypto.active_fingerprint() == parmak
    okunan = Student.objects.get(pk=kayit.pk)
    assert (okunan.first_name, okunan.last_name) == ("Deneme Çağrı", "Işıkoğlu")
    from apps.okul import selectors

    assert selectors.find_student_by_number("880011") == kayit
    # Kilit yeni parolayla açılır, aynı veri okunur.
    app_password.lock()
    app_password.unlock(password=YENI_PAROLA)
    assert Student.objects.get(pk=kayit.pk).first_name == "Deneme Çağrı"


def test_sinir_eski_parola_eski_baslikla_devirden_sonraki_yedegi_ve_kilidi_acar(
    client: APIClient,
) -> None:
    """Sınır SABİTLENİR (TB17, TB23; F11 düzeltme turu): görev devri DEK'i değiştirmez.

    Eski parola, eski bir güvenlik başlığıyla (arşivlenen dosya ya da devirden önceki
    yedeğin başlığı) DEK'i verir; yedeklerin anahtar çifti DEK'ten türediği için devirden
    SONRA alınan bir yedek de açılır, arşiv `guvenlik.json` yerine konursa eski parola
    güncel veritabanının kilidini açar. E18, kılavuz ve kurulum belgesi bu yüzden "eski
    parola kilidi artık açmaz" DEMEZ ve masa hesabının parolasının değiştirilmesini ister.
    DEK döndürme gelirse bu test ve o metinler birlikte değişir.
    """
    from desktop.backup_crypto import decrypt_bytes, encrypt_bytes, load_public_key

    _devri_tamamla(client)
    (arsiv,) = _arsivler()
    eski_durum = json.loads(arsiv.read_text(encoding="utf-8"))
    veri_dizini = app_password.state_path().parent

    # Devirden SONRA alınan yedek (güncel açık anahtarla mühürlenmiş) eski DEK'le açılır.
    yedek = encrypt_bytes(b"devirden-sonra", load_public_key(veri_dizini))
    eski_dek = app_password._unwrap_with_password(eski_durum, TEST_PAROLA)
    assert decrypt_bytes(yedek, eski_dek) == b"devirden-sonra"

    # Arşiv güncel dosyanın yerine konursa eski parola bu bilgisayarın kilidini açar.
    guncel = app_password.state_path().read_bytes()
    try:
        app_password.lock()
        app_password.state_path().write_bytes(arsiv.read_bytes())
        app_password.unlock(password=TEST_PAROLA)
        assert not app_password.is_locked()
    finally:
        app_password.state_path().write_bytes(guncel)
        app_password.lock()
        app_password.unlock(password=YENI_PAROLA)


def test_yanlis_mevcut_parola_hicbir_dosyayi_degistirmez(client: APIClient) -> None:
    onceki = app_password.state_path().read_bytes()

    yanit = _baslat(client, mevcut="yanlis-parola-1")

    assert yanit.status_code == 400
    assert "Parola hatalı" in yanit.json()["message"]
    assert app_password.state_path().read_bytes() == onceki
    assert _arsivler() == []
    assert "recovery_key" not in yanit.json()


def test_yeni_parola_eskisiyle_ayni_olamaz(client: APIClient) -> None:
    onceki = app_password.state_path().read_bytes()

    yanit = _baslat(client, yeni=TEST_PAROLA)

    assert yanit.status_code == 400
    assert "eskisinden farklı" in yanit.json()["message"]
    assert app_password.state_path().read_bytes() == onceki


def test_kisa_yeni_parola_reddedilir(client: APIClient) -> None:
    yanit = _baslat(client, yeni="kisa")

    assert yanit.status_code == 400
    assert "en az 8 karakter" in yanit.json()["message"]


def test_yeni_anahtar_gunluge_dusmez(client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        anahtar = _baslat(client).json()["recovery_key"]

    tum = "\n".join(kayit.getMessage() for kayit in caplog.records)
    assert anahtar not in tum
    assert anahtar.replace("-", "") not in tum.replace("-", "")
    assert YENI_PAROLA not in tum


# ============================================================ not kapısı


def test_not_devir_ve_dogrulama_olmadan_basilmaz(client: APIClient) -> None:
    yanit = client.post(NOT, {}, format="json")
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "gorev_devri_eksik"

    # Devir başladı ama yeni anahtar doğrulanmadı.
    _baslat(client)
    yanit = client.post(NOT, {}, format="json")
    assert yanit.status_code == 409
    assert client.get(DURUM).json()["note_available"] is False


def test_sonraki_anahtar_yenilemesi_devir_damgasini_dusurur(client: APIClient) -> None:
    _devri_tamamla(client)
    assert client.get(DURUM).json()["note_available"] is True

    app_password.renew_recovery_key(password=YENI_PAROLA)

    durum = client.get(DURUM).json()
    assert durum["started_at"] is None
    assert durum["note_available"] is False
    assert client.post(NOT, {}, format="json").status_code == 409


def test_dogrulama_devir_damgasini_korur(client: APIClient) -> None:
    anahtar = _baslat(client).json()["recovery_key"]
    baslangic = app_password.handover_info()
    assert baslangic is not None and baslangic["confirmed_at"] is None

    app_password.confirm_recovery_key(anahtar)

    bilgi = app_password.handover_info()
    assert bilgi is not None
    assert bilgi["started_at"] == baslangic["started_at"]
    assert bilgi["confirmed_at"]


# ============================================================ E18 içeriği


def test_not_icerigi_durust_ve_kisisiz_sayilidir(client: APIClient) -> None:
    uyelik = uye()
    odunc_ver(uyelik)
    _devri_tamamla(client)

    yanit = client.post(
        NOT,
        {
            "outgoing_name": "Deneme Devreden Öğretmen",
            "incoming_name": "Deneme Devralan Öğretmen",
            "note": "Okuyucu masanın sol çekmecesinde.",
        },
        format="json",
    )

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert yanit["Cache-Control"] == "no-store"
    ad = unquote(yanit["Content-Disposition"])
    assert re.search(r"Görev-Devri-Notu_\d{2}\.\d{2}\.\d{4}\.pdf", ad)
    assert "Deneme" not in ad
    metin = re.sub(r"\s+", " ", _metin(_pdf(yanit)))
    for beklenen in (
        "GÖREV DEVRİ NOTU",
        "Görevi devreden",
        "Deneme Devreden Öğretmen",
        "Deneme Devralan Öğretmen",
        "PROGRAMDA YAPILANLAR",
        "Yeni kurtarma anahtarının saklandığı doğrulandı",
        "Kayıtların şifreleme anahtarı değişmedi",
        "TESLİM EDİLENLER",
        # F11 düzeltme turu: yeni parolayı görevi devralan belirler; masa hesabının
        # parolası değişir (Yönerge 6/4 "erişim hakları kaldırılır").
        "görevi devralan belirledi",
        "Kütüphane masası Windows hesabının parolası değiştirildi",
        "Barkod okuyucu",
        # Sayılar basım anınındır: başlık dürüst.
        "NOTUN DÜZENLENDİĞİ GÜN AÇIK İŞLER",
        "İade edilmemiş ödünç 1",
        "şifreleme anahtarını değiştirmez",
        "devirden SONRA alınan yedekleri de",
        "erişimi kesildiğinde anlam taşır",
        "parola kurulurken alınan yedek kendiliğinden silinmez",
        "Eski anahtar —",
        # Atıflar fıkranın öznesine ve koşuluna bağlı.
        "Çalışması sona eren kullanıcı",
        "görev değişikliğinde kıyasen uygulanır",
        "Veri sorumluları ile veri işleyenler",
        "6698 sayılı Kanun md. 12/4",
        "Yönergesi md. 6/4",
        "Okuyucu masanın sol çekmecesinde.",
        "Adlar programda saklanmaz",
    ):
        assert beklenen in metin, beklenen
    # Gerçeğe aykırı güvenlik iddiası ve genişletilmiş atıf yok.
    assert "kilidi artık açmaz" not in metin
    assert "DEVİR GÜNÜ AÇIK İŞLER" not in metin
    assert "Görevi sona eren kullanıcı" not in metin
    assert "kapalı zarfla" in metin and "görevi devralana ve parolayı bilen" not in metin
    # Kişi ve kitap adı yok (yalnız sayı); sözlük §1: "imha" yalnız imha tutanağında.
    assert "Deneme Öğrenci" not in metin
    assert "imha" not in metin.casefold()


def test_adlar_saklanmaz_ve_gunluge_dusmez(
    client: APIClient, caplog: pytest.LogCaptureFixture
) -> None:
    _devri_tamamla(client)
    ad = "Deneme Zzyzx Devreden"

    with caplog.at_level(logging.DEBUG):
        yanit = client.post(NOT, {"outgoing_name": ad, "incoming_name": ad}, format="json")

    assert yanit.status_code == 200
    assert ad not in "\n".join(kayit.getMessage() for kayit in caplog.records)
    veri_dizini = app_password.state_path().parent
    for dosya in veri_dizini.rglob("*"):
        if dosya.is_file():
            assert "Zzyzx" not in dosya.read_bytes().decode("utf-8", "replace"), dosya.name


def test_bos_adlar_elle_doldurulacak_cizgiyle_basilir(client: APIClient) -> None:
    _devri_tamamla(client)

    yanit = client.post(NOT, {}, format="json")

    assert yanit.status_code == 200
    assert "………" in _metin(_pdf(yanit))


_TEK_PARAGRAF_NOT = (
    "Anahtar dolabı müdür yardımcısı odasındadır; etiket tabakaları raftadır. " * 12
)[: gorev_devri.NOT_EN_COK]
#: Kısa satırlarla yazılmış teslim listesi: 600 karakter içinde 46 satır (F11 düzeltme turu).
_SATIRLI_NOT = "\n".join(f"Raf {i:02d} tamam" for i in range(1, 47))[: gorev_devri.NOT_EN_COK]
#: Gerçekçi olmayan ama geçerli: 300 satır.
_UC_YUZ_SATIR = "\n".join("x" for _ in range(300))[: gorev_devri.NOT_EN_COK]


@pytest.mark.parametrize(
    "ek_not", [_TEK_PARAGRAF_NOT, _SATIRLI_NOT, _UC_YUZ_SATIR], ids=["paragraf", "46", "300"]
)
def test_sayfa_butcesi_gercek_uzunlukta_veriyle_en_cok_iki_sayfa(
    client: APIClient, ek_not: str
) -> None:
    from apps.okul.models import SchoolConfig

    config = SchoolConfig.load()
    config.school_name = (
        "Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 3
    )[:255]
    config.district = ("Büyükçekmeceoğulları Örnek İlçesi " * 3)[:64]
    config.principal_name = (
        "Mümtazhan Gülşehriye Şükriyenur Ümmügülsüm Büyükçekmeceoğulları Karamehmetoğlu " * 2
    )[:128]
    config.save()
    for _ in range(4):  # arşiv dosyaları birikmiş bir kurulum
        app_password.renew_recovery_key(password=TEST_PAROLA)
    _devri_tamamla(client)
    uzun_ad = ("Deneme Çağlayan Şükriye Gülümser Özdemiroğlu-Karaağaçlıoğlu " * 3)[
        : gorev_devri.AD_EN_COK
    ]

    yanit = client.post(
        NOT,
        {"outgoing_name": uzun_ad, "incoming_name": uzun_ad, "note": ek_not},
        format="json",
    )

    assert yanit.status_code == 200
    sayfalar = PdfReader(BytesIO(_pdf(yanit))).pages
    assert len(sayfalar) <= 2
    # İmza bloğu kesilmedi: son sayfada üç rol de var.
    son = sayfalar[-1].extract_text() or ""
    for rol in ("Görevi devreden", "Görevi devralan", "Okul müdürü"):
        assert rol in son


def test_ek_notun_fazla_satiri_son_satirda_birlesir_metin_kaybolmaz() -> None:
    """Satır sayısı karakter sınırından bağımsız olarak sayfayı uzatır (F11 düzeltme turu)."""
    metin = gorev_devri._temiz(
        "\n".join(f"s{i}" for i in range(12)), 600, en_cok_satir=gorev_devri.NOT_SATIR_EN_COK
    )
    satirlar = metin.split("\n")
    assert len(satirlar) == gorev_devri.NOT_SATIR_EN_COK == 8
    assert satirlar[-1] == "s7 · s8 · s9 · s10 · s11"
    # Sınırın altındaki not olduğu gibi kalır.
    assert gorev_devri._temiz("bir\n\niki", 600, en_cok_satir=8) == "bir\niki"


def test_uzun_ad_ve_not_sinirda_reddedilir(client: APIClient) -> None:
    _devri_tamamla(client)

    yanit = client.post(NOT, {"outgoing_name": "x" * (gorev_devri.AD_EN_COK + 1)}, format="json")
    assert yanit.status_code == 400
    yanit = client.post(NOT, {"note": "x" * (gorev_devri.NOT_EN_COK + 1)}, format="json")
    assert yanit.status_code == 400


def test_durum_ucu_kisisiz_sayilari_ve_eski_yedekleri_verir(client: APIClient) -> None:
    uyelik = uye()
    odunc_ver(uyelik)
    yedek_dizini = app_password.backup_dir()
    yedek_dizini.mkdir(parents=True, exist_ok=True)
    (yedek_dizini / "gunluk-2026-09-20.kdbak").write_bytes(b"KDBAK")

    durum = client.get(DURUM).json()

    assert set(durum) == {
        "started_at",
        "confirmed_at",
        "note_available",
        "open_work",
        "old_backup_count",
        "oldest_backup",
        "archive_count",
    }
    sayilar = {satir["key"]: satir["count"] for satir in durum["open_work"]}
    assert sayilar["acik_odunc"] == 1
    assert sayilar["acik_teslim"] == 0
    assert sayilar["saklama_onayi"] == 0
    assert durum["old_backup_count"] == 1
    json.dumps(durum)  # yalnız düz değerler


def test_saklama_onayi_bekleyen_kayit_acik_isler_arasindadir(client: APIClient) -> None:
    """F11 bağlantısı (§6.4 ↔ §4.4): saklama onayı ve altı ay sınırı görevi devralana
    kalır; açık işler özeti onu kişisiz sayı olarak taşır (ad yok)."""
    kisi = ogrenci(first_name="Deneme", last_name="Saklamasoyad")
    persons.leave_student(kisi)
    Student.all_objects.filter(pk=kisi.pk).update(left_at=date(2020, 1, 10))

    durum = client.get(DURUM)

    sayilar = {satir["key"]: satir["count"] for satir in durum.json()["open_work"]}
    assert sayilar["saklama_onayi"] == 1
    assert "Saklamasoyad" not in durum.content.decode("utf-8")


# ============================================================ mevzuat atfı


def _mevzuat(dosya: str) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / "docs" / "mevzuat" / dosya
        if yol.is_file():
            return re.sub(r"\s+", " ", yol.read_text(encoding="utf-8"))
    pytest.fail(f"{dosya} bulunamadı")


def test_notun_atiflari_mevzuat_metnine_dayanir() -> None:
    kvkk = _mevzuat("6698-kvkk.md")
    madde_12 = kvkk[kvkk.index("MADDE 12-") : kvkk.index("MADDE 13-")]
    assert (
        "(4) Veri sorumluları ile veri işleyen kişiler, öğrendikleri kişisel verileri" in madde_12
    )
    assert "Bu yükümlülük görevden ayrılmalarından sonra da devam eder." in madde_12
    assert "işleme amacı dışında kullanamazlar" in madde_12

    yonerge = _mevzuat("meb-bilgi-ve-sistem-guvenligi-yonergesi.md")
    madde_6 = yonerge[yonerge.index("MADDE 6 -") : yonerge.index("MADDE 7-")]
    assert "(4) Kullanıcı, çalışmalarının sonlandırılması ile birlikte" in madde_6
    assert "bilişim sistemleri kullanımına yönelik tüm şifreleri" in madde_6
    assert "erişim hakları kaldırılır" in madde_6

    # F11 düzeltme turu: aktarım fıkranın ÖZNESİNE ve KOŞULUNA bağlıdır. 12/4'ün öznesi
    # veri sorumluları ile veri işleyenlerdir (okulun personeli 3/1-ğ'deki veri işleyen
    # değildir); 6/4 "çalışmalarının sonlandırılması"nı anlatır, görev değişikliğinde
    # kıyasen uygulanır. Şablon yükümlülüğü doğrudan "görevi devreden"e yüklemez.
    sablon = " ".join(_mevzuat_disi("backend/templates/documents/gorev_devri_notu.html").split())
    assert "Veri sorumluları ile veri işleyenler öğrendikleri kişisel verileri" in sablon
    assert "Görevi devreden, görevi sırasında öğrendiği kişisel verileri Kanuna aykırı" not in (
        sablon
    )
    assert "Çalışması sona eren kullanıcı" in sablon and "kıyasen uygulanır" in sablon
    assert "Görevi sona eren kullanıcı" not in sablon


# ============================================================ kapılar


def test_gorevli_kipinde_kapali(client: APIClient) -> None:
    KIP.gorevliye_gec()

    for yanit in (client.get(DURUM), _baslat(client), client.post(NOT, {}, format="json")):
        assert yanit.status_code == 403
        assert yanit.json()["code"] == "kip_yetkisiz"


def test_kilitliyken_kapali(kilitli: Path, client: APIClient) -> None:
    for yanit in (client.get(DURUM), _baslat(client), client.post(NOT, {}, format="json")):
        assert yanit.status_code == 423


def test_on_yuzdeki_ad_ve_not_sinirlari_sunucuyla_aynidir() -> None:
    """Ön yüz sınırı elle kopyalanmıştır (`GorevDevri.tsx`); iki kopya ayrışmasın."""
    kaynak = _mevzuat_disi("frontend/src/modules/guvenlik/GorevDevri.tsx")
    assert f"const AD_EN_COK = {gorev_devri.AD_EN_COK};" in kaynak
    assert f"const NOT_EN_COK = {gorev_devri.NOT_EN_COK};" in kaynak


def _mevzuat_disi(goreli: str) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / goreli
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    pytest.fail(f"{goreli} bulunamadı")
