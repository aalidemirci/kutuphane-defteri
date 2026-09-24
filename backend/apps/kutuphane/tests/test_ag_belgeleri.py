"""Ağ Kataloğu belgeleri (F5-D, tasarım §5.6, §5.9, §10 E3).

- Katalog afişi: tek sayfa (en uzun adres ve en uzun saat metniyle), adres
  birincil, dayanak yazılmaz; afiş adresi `son_afis_ip` olarak kaydedilir.
- Ağ Hizmeti Bilgi Notu: §5.9'un bütün maddeleri; künye sorgusu açık/kapalı
  durumuna göre giden bağlantılar satırı; Yönerge alıntıları depodaki metinle
  BİREBİR; BTR ilk geçişte açılır; en uzun gerçekçi veride en çok iki sayfa.
- Yer imi dosyaları ve PYS talep metni.
- Hiçbir belgede kişisel veri geçmez (sentetik öğrenci adı aranır).

Sayfa bütçesi testleri GERÇEK UZUNLUKTA veriyle koşar (CLAUDE.md §3): kısa
fixture yanlış yeşil verir.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from django.template.loader import get_template
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import ag_belgeleri
from apps.kutuphane.models import LibraryPolicy
from apps.kutuphane.services import ag_doktoru
from apps.kutuphane.services import katalog_ayari as ayar_servisi
from apps.kutuphane.tests.test_ag_doktoru import ADAY_1, SahteDenetci
from apps.okul import masaustu_kanca
from apps.okul.models import SchoolConfig, Student

pytestmark = pytest.mark.django_db

KOK = "/api/v1/library/network-catalog/"
UZUN_OKUL = "Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 2
EN_UZUN_ADRES_IP = "192.168.100.200"
OGRENCI_AD = "Örnekad"
OGRENCI_SOYAD = "Sentetiksoyad"


#: pypdf "T" harfinden sonraki çekirdek aralığını boşluk sanar ("T est", "T urizm").
_T_ARALIGI = re.compile(r"T (?=[a-zçğıöşü])")


def _metin(icerik: bytes) -> str:
    ham = "\n".join(sayfa.extract_text() or "" for sayfa in PdfReader(io.BytesIO(icerik)).pages)
    return _T_ARALIGI.sub("T", ham)


def _sayfa(icerik: bytes) -> int:
    return len(PdfReader(io.BytesIO(icerik)).pages)


def _tek_bosluk(metin: str) -> str:
    return " ".join(metin.split())


class BelgeDenetcisi(SahteDenetci):
    """Güvenlik duvarı denetimi dolu dönen sahte denetçi (Windows kuralı)."""

    def __init__(
        self,
        *,
        platform: str = "windows",
        bloklar: list[str] | None = None,
        ek_kurallar: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.platform = platform
        self.bloklar = bloklar or []
        self.ek_kurallar = ek_kurallar or []

    def guvenlik_duvari(self) -> dict[str, Any]:
        if self.platform == "linux":
            return {
                "platform": "linux",
                "dinlemeye_izin": True,
                "maddeler": [],
                "kural": None,
                "ag_profilleri": [],
                "hata": None,
                "linux": {
                    "arac": "ufw",
                    "etkin": True,
                    "komut": "sudo ufw allow from 192.168.10.0/24 to any app 'Kutuphane Defteri'",
                },
            }
        kural = {
            "ad": "Kutuphane Defteri Katalog",
            "program": r"C:\Program Files\Kutuphane Defteri\kutuphane-defteri.exe",
            "yerel_port": ["8765"],
            "uzak_adres": ["LocalSubnet", *self.bloklar],
            "profil": "Domain, Private, Public",
            "etkin": True,
        }
        return {
            "platform": "windows",
            "dinlemeye_izin": True,
            "maddeler": [
                {
                    "kod": "etkin",
                    "baslik": "Kural var ve etkin",
                    "durum": "gecti",
                    "aciklama": "Etkin.",
                },
                {
                    "kod": "kapsam",
                    "baslik": "Kural bu ağ profilini kapsıyor",
                    "durum": "uyari",
                    "aciklama": "Uzak adres her yer.",
                },
            ],
            "kural": kural,
            "kurallar": [kural, *self.ek_kurallar],
            "ag_profilleri": ["Public"],
            "hata": None,
            "linux": {},
        }


@pytest.fixture(autouse=True)
def _kanca() -> Iterator[None]:
    masaustu_kanca.kaldir()
    yield
    masaustu_kanca.kaldir()


@pytest.fixture
def denetci() -> BelgeDenetcisi:
    sahte = BelgeDenetcisi()
    masaustu_kanca.kaydet(katalog=sahte)
    return sahte


@pytest.fixture
def okul() -> SchoolConfig:
    config: SchoolConfig
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.school_name = "Örnek Anadolu Lisesi"
    config.district = "Örnek İlçe"
    config.principal_name = "Örnek Müdür"
    config.demirbas_no = "DMB-2026-0042"
    config.save()
    return config


# ======================================================================== afiş


def test_afis_tek_sayfa_adres_birincil_ve_adres_kaydedilir(
    denetci: BelgeDenetcisi, okul: SchoolConfig
) -> None:
    yanit = APIClient().post(KOK + "poster/", {}, format="json")

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert "Katalog-Af" in yanit["Content-Disposition"]
    icerik = b"".join(yanit.streaming_content)  # type: ignore[attr-defined]
    metin = _tek_bosluk(_metin(icerik))
    assert _sayfa(icerik) == 1
    assert f"http://{ADAY_1}:8765/" in metin
    assert "KÜTÜPHANE KATALOĞU" in metin
    assert "Örnek Anadolu Lisesi" in metin
    # Dayanak yazılmaz (§10 E3) ve kişisel veri göstermediğini söyler.
    assert not re.search(r"\bMd\.|Yönetmelik|Yönerge", metin)
    assert "kişisel veri göstermez" in metin
    assert ayar_servisi.katalog_ayari().son_afis_ip == ADAY_1


def test_afis_en_uzun_adres_ve_saatlerle_tek_sayfa(okul: SchoolConfig) -> None:
    okul.school_name = UZUN_OKUL
    okul.kutuphane_saatleri = ("Pazartesi-Cuma 08.30-12.00 ve 13.00-16.30; " * 12)[:500]
    okul.save()
    ayar_servisi.update_katalog_ayari(port=65535)

    icerik = ag_belgeleri.afis_pdf(EN_UZUN_ADRES_IP)

    assert _sayfa(icerik) == 1
    assert f"http://{EN_UZUN_ADRES_IP}:65535/" in _tek_bosluk(_metin(icerik))


def test_adres_puntosu_uzun_adreste_kuculur_ama_okunur_kalir() -> None:
    kisa = ag_belgeleri.adres_puntosu("http://10.0.0.5:8765/")
    uzun = ag_belgeleri.adres_puntosu(f"http://{EN_UZUN_ADRES_IP}:65535/")

    assert kisa > uzun >= 24.0


def test_afis_masaustu_yokken_ayardaki_adresle_basilir(okul: SchoolConfig) -> None:
    ayar_servisi.update_katalog_ayari(son_afis_ip="10.3.3.3")

    yanit = APIClient().post(KOK + "poster/", {}, format="json")

    assert yanit.status_code == 200


def test_qr_svg_kare_ve_sessiz_bolgeli() -> None:
    svg = ag_belgeleri.qr_svg("http://10.0.0.5:8765/", 20.0)

    assert svg.startswith("<svg") and 'width="20.000mm"' in svg
    boyut = len(ag_doktoru.qr_satirlari("http://10.0.0.5:8765/"))
    assert f'viewBox="0 0 {boyut + 8} {boyut + 8}"' in svg


# ============================================================ Ağ Hizmeti Bilgi Notu


def test_bilgi_notu_bes_maddeli_icerik_ve_imza_alanlari(
    denetci: BelgeDenetcisi, okul: SchoolConfig
) -> None:
    ayar_servisi.update_katalog_ayari(tahta_cidrleri=["10.60.0.0/22"])
    denetci.bloklar = ["10.60.0.0/22"]

    yanit = APIClient().get(KOK + "info-note/")

    assert yanit.status_code == 200
    icerik = b"".join(yanit.streaming_content)  # type: ignore[attr-defined]
    metin = _tek_bosluk(_metin(icerik))
    # Başlık ve "izin değil bilgi" dili (sözlük, U10)
    assert "AĞ HİZMETİ BİLGİ NOTU" in metin
    assert "izin belgesi değildir" in metin
    # Demirbaş no, port ve gerekçesi, adres
    assert "DMB-2026-0042" in metin
    assert "TCP 8765" in metin and "varsayılan portudur" in metin
    assert f"http://{ADAY_1}:8765/" in metin
    # Kuraldaki GERÇEK uzak adres ve profil
    assert "LocalSubnet (yalnız yerel alt ağ), 10.60.0.0/22" in metin
    assert "Etki alanı, Özel, Genel" in metin
    assert "Genel" in metin  # etkin ağ profili
    # Ne sunulur / sunulmaz; kişisel veri yok
    assert "Sunulmaz:" in metin and "kart no" in metin
    assert "kişisel veri göstermez" in metin
    # Yönerge atıfları
    for madde in ("Md. 5/11", "Md. 11/16", "Md. 11/22", "Md. 11/7"):
        assert madde in metin
    # İmza alanları
    assert "Bilişim Teknolojileri Rehber Öğretmeni (BTR)" in metin
    assert "Okul Müdürü" in metin and "Örnek Müdür" in metin


GENIS_KURAL: dict[str, Any] = {
    "ad": "kutuphane-defteri.exe",
    "program": r"C:\Program Files\Kutuphane Defteri\kutuphane-defteri.exe",
    "yerel_port": ["Any"],
    "uzak_adres": ["Any"],
    "profil": "Public",
    "etkin": True,
}


def test_bilgi_notu_programin_butun_izin_kurallarini_basar(okul: SchoolConfig) -> None:
    """F5 düzeltmesi: yalnız ilk kural basılırsa geniş (Any) ikinci kural gizlenirdi.

    Windows herhangi bir izin kuralına uyan bağlantıyı kabul eder; BTR'nin
    imzaladığı notta kuraldaki GERÇEK uzak adreslerin hepsi görünmelidir (§5.9).
    """
    masaustu_kanca.kaydet(katalog=BelgeDenetcisi(ek_kurallar=[GENIS_KURAL]))

    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "Bu program için 2 izin kuralı var" in metin
    assert "LocalSubnet (yalnız yerel alt ağ)" in metin
    assert "uzak adres (remoteip): Any" in metin
    assert "kutuphane-defteri.exe" in metin


def test_bilgi_notu_eski_bicimdeki_tek_kurali_da_basar(okul: SchoolConfig) -> None:
    denetci = BelgeDenetcisi()
    okuma = denetci.guvenlik_duvari()
    okuma.pop("kurallar")

    assert [k["ad"] for k in ag_belgeleri._kural_listesi(okuma)] == ["Kutuphane Defteri Katalog"]
    assert ag_belgeleri._kural_listesi({"kural": None, "kurallar": []}) == []


def test_bilgi_notunda_btr_ilk_geciste_acilir(denetci: BelgeDenetcisi, okul: SchoolConfig) -> None:
    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    ilk = metin.index("BTR")
    assert metin[:ilk].endswith("bilişim teknolojileri rehber öğretmeninin (")


def test_kunye_kapaliyken_giden_baglanti_yalniz_guncelleme(
    denetci: BelgeDenetcisi, okul: SchoolConfig
) -> None:
    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "giden bağlantı yalnız güncelleme denetimidir" in metin
    assert "api.github.com" in metin
    assert "koha.ekutuphane.gov.tr" not in metin and "openlibrary.org" not in metin
    assert "Md. 11/12" not in metin and "Md. 11/19" not in metin
    assert "açılışta ağa çıkmaz" in metin


def test_kunye_acikken_hedefler_ve_11_12_11_19(denetci: BelgeDenetcisi, okul: SchoolConfig) -> None:
    politika = LibraryPolicy.load()
    politika.metadata_lookup_enabled = True
    politika.save()

    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "koha.ekutuphane.gov.tr (HTTP, 210)" in metin
    assert "openlibrary.org (HTTPS, 443)" in metin
    assert "dışarı yalnız kitabın ISBN'i gider" in metin
    assert "Test-NetConnection koha.ekutuphane.gov.tr -Port 210" in metin
    assert "Md. 11/12" in metin and "Md. 11/19" in metin
    assert "giden bağlantı yalnız güncelleme denetimidir" not in metin


def test_kunye_bayragi_acik_ama_iki_kaynak_kapaliyken_kapali_gibi_yazilir(
    denetci: BelgeDenetcisi, okul: SchoolConfig
) -> None:
    """F5 düzeltmesi: program dışarı künye isteği atmıyorsa not da yazmaz."""
    politika = LibraryPolicy.load()
    politika.metadata_lookup_enabled = True
    politika.metadata_lookup_ministry = False
    politika.metadata_lookup_openlibrary = False
    politika.save()

    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "ISBN ile künye getirme (açık)" not in metin
    assert "giden bağlantı yalnız güncelleme denetimidir" in metin
    assert "Md. 11/12" not in metin and "Md. 11/19" not in metin
    assert not any("koha" in k or "openlibrary" in k for k in ag_belgeleri.dis_komutlar(politika))


def test_guncelleme_hedefleri_indirme_yonlendirmesini_de_yazar(
    denetci: BelgeDenetcisi, okul: SchoolConfig
) -> None:
    """Sürüm eki indirmesi github.com'dan GitHub'ın içerik alanına yönlenir (urlopen izler)."""
    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "*.githubusercontent.com" in metin
    assert "Test-NetConnection github.com -Port 443" in metin


def test_port_gerekcesi_platforma_gore() -> None:
    """Pardus'ta program kural açmaz: "kuralı da günceller" yalnız Windows'ta yazılır."""
    windows = ag_belgeleri.port_gerekcesi(8765, "windows")
    linux = ag_belgeleri.port_gerekcesi(8765, "linux")

    assert "güvenlik duvarı kuralını da günceller" in windows
    assert "güvenlik duvarı kuralını da günceller" not in linux
    assert "komutu yeni portla yeniden çalıştırılır" in linux
    assert "BTR" not in windows and "BTR" not in linux


def test_pardusta_bilgi_notunun_port_gerekcesi_kural_guncellemez(okul: SchoolConfig) -> None:
    masaustu_kanca.kaydet(katalog=BelgeDenetcisi(platform="linux"))

    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "güvenlik duvarı kuralını da günceller" not in metin
    assert "yeni portla yeniden çalıştırılır" in metin


def test_bilgi_notu_en_uzun_veride_en_cok_iki_sayfa(okul: SchoolConfig) -> None:
    bloklar = [f"10.{i}.0.0/24" for i in range(100, 116)]
    okul.school_name = UZUN_OKUL
    okul.principal_name = "Örnek Uzunadlı Müdür Soyadıbirleşik"
    okul.save()
    ayar_servisi.update_katalog_ayari(tahta_cidrleri=bloklar, port=65535)
    politika = LibraryPolicy.load()
    politika.metadata_lookup_enabled = True
    politika.save()
    # İki izin kuralı: programın kendi kuralı + BTR'nin eklediği geniş kural (liste büyür).
    masaustu_kanca.kaydet(katalog=BelgeDenetcisi(bloklar=bloklar, ek_kurallar=[GENIS_KURAL]))

    icerik = ag_belgeleri.bilgi_notu_pdf(EN_UZUN_ADRES_IP)

    assert _sayfa(icerik) <= 2
    assert "Okul Müdürü" in _metin(icerik)


def test_kural_okunamazsa_elle_doldurulacak_alanlar(
    okul: SchoolConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ag_doktoru, "platform_adi", lambda platform=None: "windows")

    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(None)))

    assert "Kural bu bilgisayarda okunamadı" in metin
    assert "http://" in metin  # adres satırı çizgiyle basılır, not yine üretilir


def test_pardusta_komut_basilir(okul: SchoolConfig) -> None:
    masaustu_kanca.kaydet(katalog=BelgeDenetcisi(platform="linux"))

    metin = _tek_bosluk(_metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)))

    assert "Pardus'ta program güvenlik duvarı kuralı açmaz" in metin
    assert "sudo ufw allow from 192.168.10.0/24 to any app 'Kutuphane Defteri'" in metin


def test_bilgi_notu_masaustu_ve_adres_yokken_de_basilir(okul: SchoolConfig) -> None:
    yanit = APIClient().get(KOK + "info-note/")

    assert yanit.status_code == 200


def _yonerge_metni() -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / "docs" / "mevzuat" / "meb-bilgi-ve-sistem-guvenligi-yonergesi.md"
        if yol.is_file():
            return _tek_bosluk(yol.read_text(encoding="utf-8"))
    pytest.fail("Yönerge metni bulunamadı.")


def test_yonerge_alintilari_depodaki_metinle_birebir() -> None:
    """Şablondaki her “…” alıntısı docs/mevzuat'taki Yönerge metninde aynen geçer."""
    # Şablonun yolu Django'nun şablon yükleyicisinden alınır (dizin düzenine bağlı değil).
    kaynak = get_template(ag_belgeleri.BILGI_NOTU_SABLONU).origin.name  # type: ignore[attr-defined]
    sablon = Path(str(kaynak)).read_text(encoding="utf-8")
    alintilar = re.findall(r'<span class="alinti">“(.+?)”</span>', sablon, flags=re.S)
    yonerge = _yonerge_metni()

    assert len(alintilar) == 6
    for alinti in alintilar:
        assert _tek_bosluk(alinti) in yonerge, alinti


# ==================================================================== yer imleri


def test_yer_imi_dosyalari(denetci: BelgeDenetcisi, okul: SchoolConfig) -> None:
    yanit = APIClient().get(KOK + "bookmarks/")

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/zip"
    arsiv = zipfile.ZipFile(io.BytesIO(b"".join(yanit.streaming_content)))  # type: ignore[attr-defined]
    adlar = sorted(arsiv.namelist())
    assert adlar == [
        "BENIOKU.txt",
        "pardus-etap/kutuphane-katalogu-chromium.json",
        "pardus-etap/kutuphane-katalogu.desktop",
        "windows/Kutuphane-Katalogu-Tahta.url",
        "windows/Kutuphane-Katalogu.url",
    ]
    assert all(ad.isascii() for ad in adlar)
    tahta = f"http://{ADAY_1}:8765/?tahta=1"

    politika = json.loads(arsiv.read("pardus-etap/kutuphane-katalogu-chromium.json"))
    assert politika["ManagedBookmarks"][1] == {"name": "Kütüphane Kataloğu", "url": tahta}

    baslatici = arsiv.read("pardus-etap/kutuphane-katalogu.desktop").decode("utf-8")
    assert f'Exec=xdg-open "{tahta}"' in baslatici
    assert "Type=Application" in baslatici

    kisayol = arsiv.read("windows/Kutuphane-Katalogu.url")
    assert kisayol == f"[InternetShortcut]\r\nURL=http://{ADAY_1}:8765/\r\n".encode("ascii")
    assert b"?tahta=1" in arsiv.read("windows/Kutuphane-Katalogu-Tahta.url")

    benioku = arsiv.read("BENIOKU.txt").decode("utf-8")
    assert "rehber öğretmeninin (BTR)" in benioku
    assert "/etc/chromium/policies/managed/" in benioku
    # Politika yalnız ManagedBookmarks yazar: "yer imi çubuğunda görünür" koşulsuz vaat edilmez.
    assert "BookmarkBarEnabled" not in politika
    assert "yer imi çubuğunda görünür" not in benioku
    assert "yer imi çubuğu açıksa" in benioku
    assert "TEK dosyada birleştirilir" in benioku


# ================================================================== PYS metni


def test_pys_talep_metni(denetci: BelgeDenetcisi, okul: SchoolConfig) -> None:
    ayar_servisi.update_katalog_ayari(tahta_cidrleri=["10.60.0.0/22", "10.61.0.0/24"])

    metin = APIClient().get(KOK + "pys-text/").json()["metin"]

    assert metin.startswith("Konu: Yerel ağ VLAN düzenlemesi — tek yön, TCP/8765")
    assert f"Hedef: {ADAY_1} (kütüphane bilgisayarı), TCP 8765" in metin
    assert "Kaynak: 10.60.0.0/22, 10.61.0.0/24" in metin
    assert "internet ya da site erişimi talebi değildir" in metin
    assert "Kişisel veri içermez" in metin
    assert "Örnek Anadolu Lisesi" in metin


def test_pys_metni_bloklar_yokken_yer_tutucu(okul: SchoolConfig) -> None:
    metin = ag_belgeleri.pys_talep_metni(None)

    assert "tahta ağı bloğu; bilişim teknolojileri rehber öğretmeni (BTR) yazar" in metin
    assert "Hedef: ……………………" in metin


@pytest.mark.parametrize("bloklar", [[], ["10.60.0.0/22"]])
def test_pys_metninde_btr_ilk_geciste_acilir(okul: SchoolConfig, bloklar: list[str]) -> None:
    """Sözlük §2: BTR ilk geçişte açılır (metin il/ilçe birimine gider)."""
    ayar_servisi.update_katalog_ayari(tahta_cidrleri=bloklar)

    metin = ag_belgeleri.pys_talep_metni(ADAY_1)

    ilk = metin.index("BTR")
    assert metin[:ilk].endswith("bilişim teknolojileri rehber öğretmeni (") or metin[:ilk].endswith(
        "bilişim teknolojileri rehber öğretmeninin ("
    )
    assert metin.count("bilişim teknolojileri rehber öğretmen") == 1


# ============================================================== kişisel veri yok


def test_belgelerde_kisisel_veri_gecmez(denetci: BelgeDenetcisi, okul: SchoolConfig) -> None:
    Student.objects.create(first_name=OGRENCI_AD, last_name=OGRENCI_SOYAD)

    metinler = [
        _metin(ag_belgeleri.afis_pdf(ADAY_1)),
        _metin(ag_belgeleri.bilgi_notu_pdf(ADAY_1)),
        ag_belgeleri.pys_talep_metni(ADAY_1),
    ]
    arsiv = zipfile.ZipFile(io.BytesIO(ag_belgeleri.yer_imi_zip(ADAY_1)))
    metinler += [arsiv.read(ad).decode("utf-8") for ad in arsiv.namelist()]

    for metin in metinler:
        assert OGRENCI_AD not in metin and OGRENCI_SOYAD not in metin
