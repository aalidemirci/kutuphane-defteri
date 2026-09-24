"""Doğrulama okutması ve doğrulanmamışlar raporu (tasarım §7.2, F4 kod kapısı).

Yapıştırdıktan sonra etiket okutulur → `label_verified_at`. Yanlış kod türü
(ISBN, üye kartı, henüz bağlanmamış boş etiket) ayırt edilir; okutma bir
OLAYDIR — sonuç her durumda bir gövdedir, yazma yalnız "verified"da olur.
Bütün veriler uydurmadır.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_kuyruk
from apps.kutuphane.models import Copy, CopyStatus, LabelPrintKind
from apps.kutuphane.services import barcode_reservations as rezervasyon
from apps.kutuphane.services import label_queue
from apps.kutuphane.tests import kuyruk_ortak, ortak
from apps.kutuphane.tests.kuyruk_ortak import isaretler

pytestmark = pytest.mark.django_db


def _basilmis() -> Copy:
    (nusha,) = kuyruk_ortak.nushalar(1)
    parti = label_queue.create_batch(
        kind=LabelPrintKind.BOTH, template=kuyruk_ortak.sablon(), copy_ids=[nusha.pk]
    )
    label_queue.confirm_batch(parti)
    return nusha


class TestDogrulamaOkutmasi:
    @pytest.mark.parametrize(
        "bicim", [lambda kod: kod, barcode_module.format_barcode, lambda kod: f"  {kod}\n"]
    )
    def test_basilmis_etiket_okutulunca_dogrulanir(self, bicim: Callable[[str], str]) -> None:
        nusha = _basilmis()

        sonuc = label_queue.verify_scan(bicim(nusha.barcode))

        assert sonuc["result"] == "verified" and sonuc["kind"] == "COPY"
        assert sonuc["message"] == "Etiket doğrulandı."
        assert sonuc["copy"]["id"] == nusha.pk
        assert sonuc["copy"]["barcode_display"] == barcode_module.format_barcode(nusha.barcode)
        assert isaretler(nusha)[1] is not None

    def test_ikinci_okutma_yazmaz(self) -> None:
        nusha = _basilmis()
        label_queue.verify_scan(nusha.barcode)
        ilk = isaretler(nusha)[1]

        sonuc = label_queue.verify_scan(nusha.barcode)

        assert sonuc["result"] == "already_verified"
        assert isaretler(nusha)[1] == ilk

    def test_basildi_isaretlenmemis_nusha_dogrulanmaz(self) -> None:
        """D10: onay verilmeden okutma basım işaretinin yerine geçmez."""
        (nusha,) = kuyruk_ortak.nushalar(1)
        sonuc = label_queue.verify_scan(nusha.barcode)

        assert sonuc["result"] == "rejected"
        assert "Basıldı olarak işaretle" in sonuc["message"]
        assert isaretler(nusha) == (None, None, None)

    @pytest.mark.parametrize(
        ("kod", "tur", "parca"),
        [
            ("9786053321245", "ISBN", "Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."),
            ("94718263", "MEMBER_CARD", "üye kartı"),
            ("12345", "UNKNOWN", "tanınmadı"),
            ("", "UNKNOWN", "etiketini okutun"),
        ],
    )
    def test_yanlis_kod_turu_ayirt_edilir(self, kod: str, tur: str, parca: str) -> None:
        sonuc = label_queue.verify_scan(kod)
        assert (sonuc["result"], sonuc["kind"]) == ("rejected", tur)
        assert parca in sonuc["message"] and sonuc["copy"] is None

    def test_baglanmamis_bos_etiket_ayri_ileti_alir(self) -> None:
        aralik = rezervasyon.reserve(2)
        acik = label_queue.verify_scan(aralik.first_barcode)
        assert (acik["result"], acik["kind"]) == ("rejected", "RESERVED")
        assert "henüz bir kitaba bağlanmadı" in acik["message"]

        rezervasyon.cancel_numbers(aralik, barcodes=[aralik.last_barcode])
        iptal = label_queue.verify_scan(aralik.last_barcode)
        assert iptal["kind"] == "CANCELLED" and "iptal edildi" in iptal["message"]
        # Hızlı Kayıt'la aynı yönerge: bağlanmamış numaranın basılacak nüsha
        # etiketi yoktur ("kitaba yeni etiket basın" uygulanamazdı).
        assert rezervasyon.BIND_CANCELLED.split(";")[0] in iptal["message"]
        assert "başka bir boş etiket yapıştırın" in iptal["message"]
        assert "yeni etiket basın" not in iptal["message"]

    def test_kaydi_olmayan_silinmis_ve_kayittan_dusulmus_nusha(self) -> None:
        kayitsiz = barcode_module.build_barcode(timezone.localdate().year, 4242)
        assert "kayıtlı nüsha yok" in label_queue.verify_scan(kayitsiz)["message"]

        silinen = _basilmis()
        silinen.delete()
        assert "silinmiş" in label_queue.verify_scan(silinen.barcode)["message"]

        dusen = _basilmis()
        Copy.objects.filter(pk=dusen.pk).update(status=CopyStatus.WITHDRAWN_WEEDED)
        sonuc = label_queue.verify_scan(dusen.barcode)
        assert sonuc["result"] == "rejected" and "kayıttan düşülmüş" in sonuc["message"]
        assert isaretler(dusen)[1] is None

    def test_sonuc_kisisel_veri_tasimaz(self) -> None:
        sonuc = label_queue.verify_scan(_basilmis().barcode)
        assert set(sonuc["copy"]) == {
            "id",
            "barcode",
            "barcode_display",
            "work_title",
            "call_number",
            "label_printed_at",
            "label_verified_at",
        }


class TestGorevliKipiYaniti:
    """Kullanıcı kararı (24.09.2026): doğrulama okutması görevli kipine açılır; yanıtın
    nüsha özeti orada yalnız barkod ve eser adıdır (alan listesi anlık görüntü)."""

    def test_gorevli_ozeti_yalniz_barkod_ve_eser_adi(self) -> None:
        nusha = _basilmis()

        sonuc = label_queue.verify_scan(nusha.barcode, staff=True)

        assert sonuc["result"] == "verified"
        assert label_queue.STAFF_COPY_FIELDS == ("barcode", "barcode_display", "work_title")
        assert sonuc["copy"] == {
            "barcode": nusha.barcode,
            "barcode_display": barcode_module.format_barcode(nusha.barcode),
            "work_title": nusha.work.title,
        }
        assert isaretler(nusha)[1] is not None  # kural ve yazma aynı

    def test_gorevli_reddinde_de_ozet_daralir(self) -> None:
        dusen = _basilmis()
        Copy.objects.filter(pk=dusen.pk).update(status=CopyStatus.WITHDRAWN_WEEDED)

        sonuc = label_queue.verify_scan(dusen.barcode, staff=True)

        assert sonuc["result"] == "rejected"
        assert set(sonuc["copy"]) == set(label_queue.STAFF_COPY_FIELDS)

    def test_yonetici_isine_yonelten_iletiler_gorevliyi_yoneticiye_yonlendirir(self) -> None:
        """Basım onayı ve Hızlı Kayıt görevliye kapalıdır: ileti uygulanamayan yönerge
        vermez, kitabı yöneticiye ayırtır."""
        (basilmamis,) = kuyruk_ortak.nushalar(1)
        aralik = rezervasyon.reserve(2)
        rezervasyon.cancel_numbers(aralik, barcodes=[aralik.last_barcode])

        for kod in (basilmamis.barcode, aralik.first_barcode, aralik.last_barcode):
            yonetici = label_queue.verify_scan(kod)["message"]
            gorevli = label_queue.verify_scan(kod, staff=True)["message"]
            assert gorevli.endswith(label_queue.STAFF_REFER), kod
            assert "Basıldı olarak işaretle" not in gorevli
            assert "Hızlı Kayıt" not in gorevli
            assert yonetici != gorevli
        # Yönergesi görevlinin yapabileceği iletiler aynı kalır.
        isbn = "9786053321245"
        assert (
            label_queue.verify_scan(isbn, staff=True)["message"]
            == label_queue.verify_scan(isbn)["message"]
        )


class TestDogrulanmamislarRaporu:
    def test_okutulan_rapordan_duser(self) -> None:
        a = _basilmis()
        b = _basilmis()
        rapor = set(selectors_kuyruk.unverified_labels().values_list("pk", flat=True))
        assert rapor == {a.pk, b.pk}

        label_queue.verify_scan(a.barcode)

        rapor = set(selectors_kuyruk.unverified_labels().values_list("pk", flat=True))
        assert rapor == {b.pk}

    def test_bos_etiketle_baglanan_nusha_rapora_girmez(self) -> None:
        aralik = rezervasyon.reserve(1)
        rezervasyon.bind_label(
            label=aralik.first_barcode, work=ortak.eser(), acquisition=ortak.edinim()
        )
        assert not selectors_kuyruk.unverified_labels().exists()
