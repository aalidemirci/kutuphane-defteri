"""Kütüphane istatistiği ve Md. 7/1 bilgi kartı (F10 — tasarım §14.1 F10, §3 profil yasağı).

- **Kişisel veri yok**: yıl sonu raporunun (E9) sentetik adlarla dolu yılı kurulur ve
  istatistiğin BÜTÜN çıktısı (seçici ve API yanıtı) taranır.
- **Kırılımlar k eşikli, tamamlayıcı gizlemeli**: E9 ile aynı türetme denetimi
  (`test_yil_sonu_raporu._turetme_denetimi`) istatistiğin dolaşım bölümünde koşar. Aktif
  üye sayısı eşiksizdir (F10 ekleri K1); ödünç kırılımının eşiği kalır.
- **Md. 7/1**: elde bulunan KİTAP nüshası sayılır (süreli yayın, kayıttan düşülen,
  silinen eser sayılmaz); eşik 10.000'i AŞINCA kart "aşıldı" der. Madde metni
  docs/mevzuat ile birebir.
- Dönem seçimi, ek dolaşım sayıları, teslim bölümü ve uçlar.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane import selectors_istatistik
from apps.kutuphane.models import CopyStatus, Loan, ResourceType
from apps.kutuphane.services import circulation
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    uye,
)
from apps.kutuphane.tests.ortak import eser, nusha
from apps.kutuphane.tests.teslim_ortak import etkin_yil, ogretmen, sube, teslim_et
from apps.kutuphane.tests.test_yil_sonu_raporu import (
    SENTINELLER,
    YASAK_ANAHTAR_PARCALARI,
    _anahtarlar,
    _dolu_yil,
    _turetme_denetimi,
)
from apps.okul.models import SchoolYear

pytestmark = pytest.mark.django_db

UC = "/api/v1/library/statistics/"
PANO_UCU = "/api/v1/library/dashboard/statistics/"
_YONETMELIK = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi.md"


def _oku(yol: Path) -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _yakin_donem() -> tuple[date, date]:
    """Bugünü kapsayan dönem (testlerde ödünç anı gerçek saattir)."""
    bugun = timezone.localdate()
    return bugun - timedelta(days=30), bugun


# ============================================================ kişisel veri yok


class TestKisiselVeriYok:
    def test_istatistik_hicbir_kisi_izi_tasimaz(self) -> None:
        yil, izler = _dolu_yil()
        bas, son = selectors_istatistik.istatistik_donemi(school_year=yil)

        veri = selectors_istatistik.istatistik(bas, son)
        metin = json.dumps(veri, ensure_ascii=False, default=str).casefold()

        for ad, deger in SENTINELLER.items():
            assert deger.casefold() not in metin, f"{ad} istatistikte geçti"
        for iz in izler:
            assert iz.casefold() not in metin
        yasak = {a for a in _anahtarlar(veri) if any(p in a for p in YASAK_ANAHTAR_PARCALARI)}
        assert yasak == set(), yasak
        # Gezinti gerçekten veriye ulaştı (boş istatistik yanlış yeşil verirdi).
        assert veri["circulation"]["loans"] == 4
        assert veri["weeding"]["withdrawn"] == 1 and veri["weeding"]["transferred"] == 1

    def test_api_yaniti_da_kisi_izi_tasimaz(self) -> None:
        yil, izler = _dolu_yil()

        yanit = APIClient().get(UC, {"school_year": yil.pk})

        assert yanit.status_code == 200
        metin = yanit.content.decode("utf-8").casefold()
        for deger in [*SENTINELLER.values(), *izler]:
            assert deger.casefold() not in metin
        assert yanit.json()["circulation"]["loans"] == 4

    def test_dolasimda_konu_ve_sinif_ekseni_yok(self) -> None:
        """Profil yasağı: dolaşım kırılımı yalnız üye türü ve sınıf düzeyidir."""
        etkin_yil()
        odunc_ver(uye(ogrenci()))
        bas, son = _yakin_donem()

        dolasim = selectors_istatistik.istatistik(bas, son)["circulation"]

        anahtarlar = _anahtarlar(dolasim)
        for kelime in ("subject", "classification", "dewey", "section", "konu"):
            assert not {a for a in anahtarlar if kelime in a}, kelime


# ============================================================ eşik ve tamamlayıcı gizleme


class TestEsikliKirilimlar:
    def test_denetimin_senaryosu_istatistikte_de_turetilemez(self) -> None:
        """E9 türetme testi (F8 ekleri 30) istatistiğin dolaşım bölümünde de koşar."""
        etkin_yil()
        for _ in range(5):
            odunc_ver(uye(ogrenci(class_level=9)))
        for _ in range(5):
            odunc_ver(uye(ogrenci(class_level=10)))
        tek = uye(ogrenci(class_level=11))
        for _ in range(3):
            odunc_ver(tek)
        hoca = uye(ogretmen())
        for _ in range(2):
            odunc_ver(hoca)
        bas, son = _yakin_donem()

        dolasim = selectors_istatistik.istatistik(bas, son)["circulation"]

        assert dolasim["loans"] == 15 and dolasim["k_threshold"] == 5
        assert {h["class_level"]: h["loans"] for h in dolasim["by_class_level"]} == {
            9: None,
            10: 5,
            11: None,
        }
        assert all(h["loans"] is None for h in dolasim["by_member_type"].values())
        _turetme_denetimi(dolasim)

    def test_esik_politikadan_okunur(self) -> None:
        from apps.kutuphane.tests.dolasim_ortak import politika

        etkin_yil()
        politika(popular_min_members=3)
        for _ in range(3):
            odunc_ver(uye(ogrenci(class_level=9)))
        bas, son = _yakin_donem()

        dolasim = selectors_istatistik.istatistik(bas, son)["circulation"]

        assert dolasim["k_threshold"] == 3
        assert dolasim["by_member_type"]["STUDENT"] == {"loans": 3, "below_threshold": False}
        _turetme_denetimi(dolasim)

    def test_aktif_uye_sayisi_esiksiz_odunc_kirilimi_esikli_kalir(self) -> None:
        """F10 ekleri K1 (27.09.2026 kullanıcı kararı): üyelik sayısı ödünç verisi değildir.
        Tek öğretmen üye "1" görünür; aynı öğretmenin ödüncü üye türü kırılımında gizli kalır."""
        etkin_yil()
        for _ in range(6):
            odunc_ver(uye(ogrenci(class_level=9)))
        odunc_ver(uye(ogretmen()))

        yanit = APIClient().get(UC)

        assert yanit.status_code == 200
        dolasim = yanit.json()["circulation"]
        assert dolasim["active_members"] == {"STUDENT": 6, "TEACHER": 1, "STAFF": 0}
        assert dolasim["loans"] == 7
        assert dolasim["by_member_type"]["TEACHER"] == {"loans": None, "below_threshold": True}
        _turetme_denetimi(dolasim)


# ============================================================ bölümler


class TestBolumler:
    def test_gecikme_ve_su_anki_sayilar(self) -> None:
        etkin_yil()
        acik = odunc_ver(uye(ogrenci()))
        gecikmeli_yap(acik, gun=3)
        gec_donen = odunc_ver(uye(ogrenci()))
        gecikmeli_yap(gec_donen, gun=2)
        circulation.return_copy(copy=gec_donen.copy)
        zamaninda = odunc_ver(uye(ogrenci()))
        circulation.return_copy(copy=zamaninda.copy)
        bas, son = _yakin_donem()

        dolasim = selectors_istatistik.istatistik(bas, son)["circulation"]

        assert dolasim["loans"] == 3 and dolasim["returns"] == 2
        assert dolasim["returned_late"] == 1
        assert dolasim["open_now"] == 1 and dolasim["overdue_now"] == 1
        assert dolasim["lost_converted"] == 0
        assert "deliveries" not in dolasim  # teslim kendi bölümünde

    def test_teslim_bolumu_ture_gore(self) -> None:
        etkin_yil()
        teslim_et([odunc_nushasi(title=f"Şube {i}") for i in range(2)], section=sube(9, "B"))
        teslim_et([odunc_nushasi(title="Öğretmene")], personnel=ogretmen())
        bas, son = _yakin_donem()

        teslim = selectors_istatistik.istatistik(bas, son)["deliveries"]

        assert teslim["delivered"] == {"section": 2, "teacher": 1}
        assert teslim["open_now"] == {"section": 2, "teacher": 1}
        assert teslim["returned"] == 0 and teslim["lost"] == 0

    def test_koleksiyon_kaynak_turune_gore_eser_ve_nusha(self) -> None:
        kitap = eser(title="Kitap")
        nusha(kitap)
        nusha(kitap)
        eser(title="Dergi", resource_type=ResourceType.PERIODICAL)
        eser(title="E-Kitap", resource_type=ResourceType.EBOOK)
        bas, son = _yakin_donem()

        koleksiyon = selectors_istatistik.istatistik(bas, son)["collection"]

        assert koleksiyon["works_by_resource_type"]["BOOK"] == 1
        assert koleksiyon["works_by_resource_type"]["PERIODICAL"] == 1
        assert koleksiyon["works_by_resource_type"]["EBOOK"] == 1
        assert koleksiyon["resource_type_counts"]["BOOK"] == 2
        assert koleksiyon["in_stock_count"] == 2 and koleksiyon["available_count"] == 2


# ============================================================ dönem


class TestDonem:
    def test_varsayilan_etkin_ders_yilinin_donemi(self) -> None:
        yil = etkin_yil()
        assert selectors_istatistik.istatistik_donemi(bugun=date(2026, 10, 1)) == (
            yil.start_date,
            yil.end_date,
        )

    def test_etkin_yil_yoksa_takvim_yili_basindan_bugune(self) -> None:
        assert not SchoolYear.objects.exists()
        assert selectors_istatistik.istatistik_donemi(bugun=date(2026, 10, 1)) == (
            date(2026, 1, 1),
            date(2026, 10, 1),
        )

    def test_tarih_araligi_dogrulanir(self) -> None:
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            selectors_istatistik.istatistik_donemi(bas=date(2026, 9, 1))
        with pytest.raises(ValidationError):
            selectors_istatistik.istatistik_donemi(bas=date(2026, 9, 2), son=date(2026, 9, 1))

    def test_uc_tarih_araligi_ve_hatalar(self) -> None:
        istemci = APIClient()
        once = timezone.localdate() - timedelta(days=40)
        loan = odunc_ver(uye(ogrenci()))
        Loan.objects.filter(pk=loan.pk).update(loaned_at=timezone.now() - timedelta(days=40))

        dar = istemci.get(
            UC, {"start": timezone.localdate().isoformat(), "end": timezone.localdate().isoformat()}
        )
        genis = istemci.get(
            UC, {"start": once.isoformat(), "end": timezone.localdate().isoformat()}
        )
        bozuk = istemci.get(UC, {"start": "2026-13-01", "end": "2026-12-01"})
        ters = istemci.get(UC, {"start": "2026-12-02", "end": "2026-12-01"})
        yok = istemci.get(UC, {"school_year": 999_999})

        assert dar.json()["circulation"]["loans"] == 0
        assert genis.json()["circulation"]["loans"] == 1
        assert genis.json()["period"] == {
            "start": once.isoformat(),
            "end": timezone.localdate().isoformat(),
        }
        assert bozuk.status_code == 400 and "start" in bozuk.json()["fields"]
        assert ters.status_code == 400
        assert ters.json()["message"] == selectors_istatistik.TARIH_SIRASI
        assert yok.status_code == 404


# ============================================================ Md. 7/1


class TestMd7:
    def test_madde_metni_mevzuatla_birebir(self) -> None:
        metin = _oku(_YONETMELIK)
        assert f"MADDE 7- (1) {selectors_istatistik.MD7_1_METNI}" in metin
        assert selectors_istatistik.MD7_ESIGI == 10_000

    def test_elde_bulunan_kitap_nushasi_sayilir(self) -> None:
        kitap = eser(title="Kitap")
        nusha(kitap)
        nusha(kitap, is_reference=True)  # danışma kaynağı da kitaptır
        dusulen = nusha(kitap)
        dusulen.status = CopyStatus.WITHDRAWN_WEEDED
        dusulen.save(update_fields=["status"])
        silinen_eser = eser(title="Silinen")
        nusha(silinen_eser)
        silinen_eser.delete()
        dergi = eser(title="Ciltli Dergi", resource_type=ResourceType.PERIODICAL)
        nusha(dergi, is_bound_periodical=True)
        gorsel = eser(title="Belgesel", resource_type=ResourceType.AV_MATERIAL)
        nusha(gorsel)

        assert selectors_istatistik.kitap_esigi() == {
            "threshold": 10_000,
            "in_stock_books": 2,
            "lost_books": 0,
            "exceeded": False,
        }

    def test_kayip_bildirilmis_nusha_sayilir_ve_ayrica_bildirilir(self) -> None:
        """F10 düzeltme turu: kayıp bildirilmiş ama kayıttan düşülmemiş nüsha kayıttadır ve
        sayılır; kart bunu `lost_books` ile açıkça yazar (27.09.2026 kullanıcı kararı, F10
        ekleri K3: sayıda kalır)."""
        kitap = eser(title="Kitap")
        nusha(kitap)
        kayip = nusha(kitap)
        kayip.status = CopyStatus.LOST
        kayip.save(update_fields=["status"])
        assert selectors_istatistik.kitap_esigi() == {
            "threshold": 10_000,
            "in_stock_books": 2,
            "lost_books": 1,
            "exceeded": False,
        }

    def test_esik_asilinca_bilgi_verir_esitlik_asmak_degildir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(selectors_istatistik, "MD7_ESIGI", 2)
        kitap = eser(title="Kitap")
        nusha(kitap)
        nusha(kitap)
        assert selectors_istatistik.kitap_esigi()["exceeded"] is False  # "aşan": > eşik

        nusha(kitap)

        assert selectors_istatistik.kitap_esigi() == {
            "threshold": 2,
            "in_stock_books": 3,
            "lost_books": 0,
            "exceeded": True,
        }

    def test_pano_ucu_md7_ve_cok_okunanlar_ozeti(self) -> None:
        nusha(eser(title="Kitap"))

        yanit = APIClient().get(PANO_UCU)

        assert yanit.status_code == 200
        assert yanit.json() == {
            "book_threshold": {
                "threshold": 10_000,
                "in_stock_books": 1,
                "lost_books": 0,
                "exceeded": False,
            },
            "popular": {"term": None, "month": None},
        }
