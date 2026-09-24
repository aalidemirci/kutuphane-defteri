"""Basım kaydı: PDF üretmek "basıldı" DEĞİLDİR, işaret onaylıdır ve geri alınır (D10).

F4 kod kapısı "basım durumu geri alınabilir" maddesinin kanıtı. Etiket motoru
sahte motorla değiştirilir (`kuyruk_ortak.motoru_bagla`); motora giden işin
SIRASI ve ayarları da burada sınanır (sırt ve barkod aynı sıra — §7.2).
Bütün veriler uydurmadır.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import selectors_kuyruk
from apps.kutuphane.models import (
    MAX_LABELS_PER_JOB,
    Copy,
    CopyStatus,
    LabelKind,
    LabelOrder,
    LabelPrintBatch,
    LabelPrintBatchStatus,
    LabelPrintKind,
)
from apps.kutuphane.services import label_queue, label_render
from apps.kutuphane.tests import kuyruk_ortak, ortak
from apps.kutuphane.tests.kuyruk_ortak import isaretler

pytestmark = pytest.mark.django_db


def _parti(
    nushalar: list[Copy], kind: str = LabelPrintKind.BOTH, **alanlar: Any
) -> LabelPrintBatch:
    if "template" not in alanlar:
        alanlar["template"] = kuyruk_ortak.sablon()
    return label_queue.create_batch(kind=kind, copy_ids=[n.pk for n in nushalar], **alanlar)


# ============================================================ D10: PDF ≠ basıldı
class TestPdfBasildiDegildir:
    def test_parti_acmak_ve_pdf_uretmek_isaretlere_dokunmaz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isler = kuyruk_ortak.motoru_bagla(monkeypatch)
        nushalar = kuyruk_ortak.nushalar(3)
        parti = _parti(nushalar)

        for _ in range(2):  # aynı partinin PDF'i istenildiği kadar yeniden alınır
            assert label_queue.render_batch_pdf(parti) == kuyruk_ortak.SAHTE_PDF

        assert len(isler) == 2
        assert parti.status == LabelPrintBatchStatus.PENDING
        for nusha in nushalar:
            assert isaretler(nusha) == (None, None, None)

    def test_motor_bagli_degilse_acik_hata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kuyruk_ortak.motoru_ayir(monkeypatch)
        parti = _parti(kuyruk_ortak.nushalar(1))
        with pytest.raises(label_render.LabelRendererUnavailable):
            label_queue.render_batch_pdf(parti)

    def test_motora_giden_is_basim_sirasini_ve_ayarlari_tasir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isler = kuyruk_ortak.motoru_bagla(monkeypatch)
        z = ortak.nusha(ortak.eser(title="Z", classification_code="900"))
        a = ortak.nusha(ortak.eser(title="A", classification_code="100"))
        sablon = kuyruk_ortak.sablon()
        kalibrasyon = kuyruk_ortak.kalibrasyon(sablon)
        parti = label_queue.create_batch(
            kind=LabelPrintKind.BOTH,
            template=sablon,
            calibration=kalibrasyon,
            start_cell=7,
            include_qr=True,
            copy_ids=[z.pk, a.pk],
        )

        label_queue.render_batch_pdf(parti)

        is_ = isler[0]
        assert [nusha.pk for nusha in is_.copies] == [a.pk, z.pk]  # yer numarası sırası
        assert (is_.kind, is_.start_cell, is_.include_qr) == ("BOTH", 7, True)
        assert is_.template == sablon and is_.calibration == kalibrasyon
        assert list(is_.barcodes) == []


# ============================================================ Onay
class TestOnay:
    def test_ikisi_birden_onayi_iki_isareti_yazar(self) -> None:
        nushalar = kuyruk_ortak.nushalar(2)
        parti = label_queue.confirm_batch(_parti(nushalar))

        assert parti.status == LabelPrintBatchStatus.CONFIRMED
        for nusha in nushalar:
            basim, dogrulama, sirt = isaretler(nusha)
            assert basim == parti.confirmed_at and sirt == parti.confirmed_at
            assert dogrulama is None

    def test_sirt_partisi_yalniz_sirt_isaretini_yazar(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        parti = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.SPINE))
        assert isaretler(nusha) == (None, None, parti.confirmed_at)

    def test_barkodun_yeniden_basimi_dogrulamayi_sifirlar(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        eski = timezone.now()
        Copy.objects.filter(pk=nusha.pk).update(label_printed_at=eski, label_verified_at=eski)

        parti = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.BARCODE))

        assert isaretler(nusha) == (parti.confirmed_at, None, None)
        kalem = parti.items.get()
        assert (kalem.previous_printed_at, kalem.previous_verified_at) == (eski, eski)

    def test_yalniz_bekleyen_parti_onaylanir(self) -> None:
        parti = label_queue.confirm_batch(_parti(kuyruk_ortak.nushalar(1)))
        with pytest.raises(ValidationError, match="zaten basıldı"):
            label_queue.confirm_batch(parti)

        vazgecilen = label_queue.discard_batch(_parti(kuyruk_ortak.nushalar(1)))
        with pytest.raises(ValidationError, match="vazgeçildi"):
            label_queue.confirm_batch(vazgecilen)


# ============================================================ Geri alma
class TestGeriAlma:
    def test_geri_alma_isaretleri_onay_oncesine_dondurur_parti_iz_kalir(self) -> None:
        nushalar = kuyruk_ortak.nushalar(2)
        parti = label_queue.confirm_batch(_parti(nushalar))

        sonuc = label_queue.revert_batch(parti)

        assert sonuc == {
            "batch": sonuc["batch"],
            "restored": 2,
            "requeued": 2,
            "kept_verified": 0,
        }
        assert sonuc["batch"].status == LabelPrintBatchStatus.REVERTED
        for nusha in nushalar:
            assert isaretler(nusha) == (None, None, None)
        assert LabelPrintBatch.objects.filter(pk=parti.pk).exists()
        assert parti.items.count() == 2

    def test_hasarli_etiketin_yeniden_basimi_geri_alininca_ilk_basima_doner(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        ilk = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.BARCODE))
        Copy.objects.filter(pk=nusha.pk).update(label_verified_at=timezone.now())
        _, ilk_dogrulama, _ = isaretler(nusha)

        ikinci = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.BARCODE))
        sonuc = label_queue.revert_batch(ikinci)

        # Kuyruğa DÜŞMEZ: ilk basımın tarihi ve doğrulaması geri gelir; yanıt da
        # "kuyruğa döndü" demez (ön yüz iletisi `requeued`'dan kurulur).
        assert isaretler(nusha) == (ilk.confirmed_at, ilk_dogrulama, None)
        assert (sonuc["restored"], sonuc["requeued"]) == (1, 0)

    def test_dogrulanmis_nushayi_koruyan_yeniden_basim_geri_alininca_ilk_parti_geri_alinabilir(
        self,
    ) -> None:
        """Denetim bulgusu (24.09.2026): önceden bu durumda B1 kalıcı olarak geri alınamıyordu.

        B1 (C1, C2) onaylanır, C1 okutulur; B2 = yeniden basım onaylanır, C1 yeniden
        okutulur; B2 geri alınır (C1'in işareti doğrulandığı için B2'nin damgasında
        KALIR, C2 B1'e döner). B2 artık onaylı değildir: B1'in geri alınmasını
        engellememeli, C2 kuyruğa dönmeli, C1'e dokunulmamalıdır.
        """
        c1, c2 = kuyruk_ortak.nushalar(2)
        b1 = label_queue.confirm_batch(_parti([c1, c2], LabelPrintKind.BARCODE))
        assert label_queue.verify_scan(c1.barcode)["result"] == "verified"
        b2 = label_queue.confirm_batch(label_queue.reprint_batch(b1))
        assert label_queue.verify_scan(c1.barcode)["result"] == "verified"

        geri_b2 = label_queue.revert_batch(b2)
        assert geri_b2["kept_verified"] == 1
        assert isaretler(c1)[0] == b2.confirmed_at
        assert isaretler(c2)[0] == b1.confirmed_at

        geri_b1 = label_queue.revert_batch(b1)

        assert geri_b1["batch"].status == LabelPrintBatchStatus.REVERTED
        assert (geri_b1["restored"], geri_b1["requeued"], geri_b1["kept_verified"]) == (1, 1, 1)
        basim, dogrulama, _ = isaretler(c1)
        assert basim == b2.confirmed_at and dogrulama is not None  # etiket kitapta, okundu
        assert isaretler(c2) == (None, None, None)  # kuyruğa döndü

    def test_onayli_sonraki_parti_hala_engeldir(self) -> None:
        """Geri alınmamış sonraki basım varken önceki parti yine geri alınamaz."""
        c1, c2 = kuyruk_ortak.nushalar(2)
        b1 = label_queue.confirm_batch(_parti([c1, c2], LabelPrintKind.BARCODE))
        label_queue.verify_scan(c1.barcode)
        label_queue.confirm_batch(label_queue.reprint_batch(b1))

        with pytest.raises(ValidationError, match="Önce o partinin basım işaretini geri alın"):
            label_queue.revert_batch(b1)

    def test_onaydan_sonra_okutulan_nushanin_iki_isareti_de_korunur(self) -> None:
        """Kullanıcı kararı (24.09.2026): sırt ve barkod partisi geri alınınca barkodu
        okutularak doğrulanmış nüshanın barkod VE sırt işareti korunur; nüsha ne barkod
        ne sırt kuyruğuna döner. Sayaçlar ayrık: korunan nüsha `restored`'a ve
        `requeued`'a girmez."""
        okutulan, okutulmayan = kuyruk_ortak.nushalar(2)
        parti = label_queue.confirm_batch(_parti([okutulan, okutulmayan]))
        sonuc_okutma = label_queue.verify_scan(okutulan.barcode)
        assert sonuc_okutma["result"] == "verified"
        _, dogrulama_once, _ = isaretler(okutulan)

        sonuc = label_queue.revert_batch(parti)

        assert (sonuc["restored"], sonuc["requeued"], sonuc["kept_verified"]) == (1, 1, 1)
        assert isaretler(okutulan) == (parti.confirmed_at, dogrulama_once, parti.confirmed_at)
        assert isaretler(okutulmayan) == (None, None, None)
        for tur in (LabelPrintKind.SPINE, LabelPrintKind.BARCODE, LabelPrintKind.BOTH):
            kuyruk = set(selectors_kuyruk.label_queue(tur).values_list("pk", flat=True))
            assert okutulan.pk not in kuyruk, tur
            assert okutulmayan.pk in kuyruk, tur

    def test_yalniz_sirt_partisinde_dogrulama_sirt_isaretini_korumaz(self) -> None:
        """Sırt etiketi barkod taşımaz, doğrulanamaz: sırt partisi geri alınınca barkodu
        başka partiden okutulmuş nüshanın da sırt işareti geri alınır."""
        (nusha,) = kuyruk_ortak.nushalar(1)
        barkod = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.BARCODE))
        assert label_queue.verify_scan(nusha.barcode)["result"] == "verified"
        sirt = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.SPINE))

        sonuc = label_queue.revert_batch(sirt)

        assert (sonuc["restored"], sonuc["requeued"], sonuc["kept_verified"]) == (1, 1, 0)
        basim, dogrulama, sirt_isareti = isaretler(nusha)
        assert basim == barkod.confirmed_at and dogrulama is not None
        assert sirt_isareti is None

    def test_dogrulanmis_nusha_sonraki_sirt_partisine_ragmen_geri_almayi_engellemez(
        self,
    ) -> None:
        """İşaretleri korunacak nüshaya dokunulmaz; bu yüzden onun sonraki bir partideki
        işareti "önce o partiyi geri alın" reddini tetiklemez. Doğrulanmamış nüshanın
        sonraki işareti ise yine engeldir."""
        okutulan, okutulmayan = kuyruk_ortak.nushalar(2)
        parti = label_queue.confirm_batch(_parti([okutulan, okutulmayan]))
        label_queue.verify_scan(okutulan.barcode)
        sirt = label_queue.confirm_batch(_parti([okutulan], LabelPrintKind.SPINE))

        sonuc = label_queue.revert_batch(parti)

        assert (sonuc["restored"], sonuc["requeued"], sonuc["kept_verified"]) == (1, 1, 1)
        basim, dogrulama, sirt_isareti = isaretler(okutulan)
        assert basim == parti.confirmed_at and dogrulama is not None
        assert sirt_isareti == sirt.confirmed_at  # sonraki partinin işareti silinmedi
        assert isaretler(okutulmayan) == (None, None, None)

        ikinci = label_queue.confirm_batch(_parti([okutulmayan]))
        label_queue.confirm_batch(_parti([okutulmayan], LabelPrintKind.SPINE))
        with pytest.raises(ValidationError, match="Önce o partinin basım işaretini geri alın"):
            label_queue.revert_batch(ikinci)

    def test_sonraki_basim_varken_onceki_parti_geri_alinamaz(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        birinci = label_queue.confirm_batch(_parti([nusha]))
        ikinci = label_queue.confirm_batch(_parti([nusha]))

        with pytest.raises(ValidationError, match="Önce o partinin basım işaretini geri alın"):
            label_queue.revert_batch(birinci)

        label_queue.revert_batch(ikinci)
        assert isaretler(nusha)[0] == birinci.confirmed_at
        label_queue.revert_batch(birinci)
        assert isaretler(nusha) == (None, None, None)

    def test_sirt_partisi_barkod_partisinin_geri_almasini_engellemez(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        barkod = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.BARCODE))
        label_queue.confirm_batch(_parti([nusha], LabelPrintKind.SPINE))

        label_queue.revert_batch(barkod)

        basim, _, sirt = isaretler(nusha)
        assert basim is None and sirt is not None

    def test_yalniz_onayli_parti_geri_alinir_ve_bir_kez(self) -> None:
        bekleyen = _parti(kuyruk_ortak.nushalar(1))
        with pytest.raises(ValidationError, match="henüz basıldı olarak işaretlenmedi"):
            label_queue.revert_batch(bekleyen)

        onayli = label_queue.confirm_batch(bekleyen)
        label_queue.revert_batch(onayli)
        with pytest.raises(ValidationError, match="geri alındı"):
            label_queue.revert_batch(onayli)
        with pytest.raises(ValidationError, match="Yeniden bas"):
            label_queue.confirm_batch(onayli)

    def test_db_kisiti_onaysiz_geri_almayi_ve_onayli_vazgecmeyi_engeller(self) -> None:
        parti = _parti(kuyruk_ortak.nushalar(1))
        with pytest.raises(IntegrityError), transaction.atomic():
            LabelPrintBatch.objects.filter(pk=parti.pk).update(reverted_at=timezone.now())
        with pytest.raises(IntegrityError), transaction.atomic():
            LabelPrintBatch.objects.filter(pk=parti.pk).update(
                confirmed_at=timezone.now(), discarded_at=timezone.now()
            )


# ============================================================ Vazgeçme ve yeniden basım
class TestVazgecmeVeYenidenBasim:
    def test_vazgecilen_parti_iz_kalir_isaretlere_dokunulmaz(self) -> None:
        nushalar = kuyruk_ortak.nushalar(2)
        parti = label_queue.discard_batch(_parti(nushalar))

        assert parti.status == LabelPrintBatchStatus.DISCARDED
        assert all(isaretler(n) == (None, None, None) for n in nushalar)
        with pytest.raises(ValidationError):
            label_queue.discard_batch(parti)

    def test_yeniden_basim_ayni_nushalari_ayni_sirayla_yeni_partide_basar(self) -> None:
        nushalar = [
            ortak.nusha(ortak.eser(title=f"E{sira}", classification_code=kod))
            for sira, kod in enumerate(["500", "100", "900"])
        ]
        eski = label_queue.confirm_batch(_parti(nushalar, start_cell=10))
        eski_sira = list(eski.items.order_by("position").values_list("copy_id", flat=True))
        # Eser yer numarası değişse bile yeniden basım ESKİ diziliş korunur.
        nushalar[2].work.call_number = "001 AAA"
        nushalar[2].work.save()

        yeni = label_queue.reprint_batch(eski, start_cell=1)

        assert yeni.pk != eski.pk and yeni.reprint_of_id == eski.pk
        assert yeni.status == LabelPrintBatchStatus.PENDING
        assert list(yeni.items.order_by("position").values_list("copy_id", flat=True)) == eski_sira
        assert (yeni.start_cell, yeni.kind, yeni.template_id) == (1, eski.kind, eski.template_id)

    def test_sablon_degisince_eski_kalibrasyon_tasinmaz(self) -> None:
        sablon = kuyruk_ortak.sablon()
        eski = _parti(
            kuyruk_ortak.nushalar(1), template=sablon, calibration=kuyruk_ortak.kalibrasyon(sablon)
        )
        yeni_sablon = kuyruk_ortak.sablon(name="Deneme 44'lü", rows=11, cols=4)

        yeni = label_queue.reprint_batch(eski, template=yeni_sablon)

        assert yeni.template_id == yeni_sablon.pk and yeni.calibration_id is None
        assert label_queue.reprint_batch(eski).calibration_id == eski.calibration_id


# ============================================================ Parti ayarının denetimi
class TestPartiDenetimi:
    def test_nusha_secimi_bos_olamaz_sinir_asilamaz(self) -> None:
        with pytest.raises(ValidationError, match="nüshaları seçin"):
            _parti([])
        with pytest.raises(ValidationError, match="en çok 1.300"):
            label_queue.create_batch(
                kind=LabelPrintKind.BOTH,
                template=kuyruk_ortak.sablon(),
                copy_ids=list(range(1, MAX_LABELS_PER_JOB + 2)),
            )

    def test_yinelenen_nusha_tek_sayilir(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        parti = label_queue.create_batch(
            kind=LabelPrintKind.BOTH, template=kuyruk_ortak.sablon(), copy_ids=[nusha.pk] * 3
        )
        assert parti.copy_count == 1 and parti.items.count() == 1

    def test_silinmis_ve_kayittan_dusulmus_nusha_reddedilir(self) -> None:
        silinen, dusen = kuyruk_ortak.nushalar(2)
        silinen.delete()
        Copy.objects.filter(pk=dusen.pk).update(status=CopyStatus.WITHDRAWN_LOST)

        with pytest.raises(ValidationError, match="bulunamadı ya da silinmiş"):
            _parti([silinen])
        with pytest.raises(ValidationError, match="kayıttan düşülmüş"):
            _parti([dusen])

    def test_uye_karti_ve_silinmis_sablon_kullanilmaz(self) -> None:
        nushalar = kuyruk_ortak.nushalar(1)
        kart = kuyruk_ortak.sablon(name="Kart", kind=LabelKind.CARD, rows=5, cols=2)
        with pytest.raises(ValidationError, match="Üye kartı"):
            _parti(nushalar, template=kart)
        silinen = kuyruk_ortak.sablon(name="Eski")
        silinen.delete()
        with pytest.raises(ValidationError, match="silinmiş"):
            _parti(nushalar, template=silinen)

    def test_kalibrasyon_sablona_ait_olmali(self) -> None:
        birinci = kuyruk_ortak.sablon(name="Birinci")
        ikinci = kuyruk_ortak.sablon(name="İkinci")
        with pytest.raises(ValidationError, match="bu etiket şablonuna ait değil"):
            _parti(
                kuyruk_ortak.nushalar(1),
                template=birinci,
                calibration=kuyruk_ortak.kalibrasyon(ikinci),
            )

    @pytest.mark.parametrize("hucre", [0, 66])
    def test_baslangic_hucresi_tabakanin_icinde(self, hucre: int) -> None:
        with pytest.raises(ValidationError, match="1 ile 65 arasında"):
            _parti(kuyruk_ortak.nushalar(1), start_cell=hucre)

    def test_son_hucre_gecerlidir(self) -> None:
        assert _parti(kuyruk_ortak.nushalar(1), start_cell=65).start_cell == 65

    def test_ayri_sirt_tabakasi_yalniz_ikisi_birden_ve_ayni_izgara(self) -> None:
        nushalar = kuyruk_ortak.nushalar(1)
        sirt = kuyruk_ortak.sablon(name="Sırt 65'li", kind=LabelKind.SPINE)
        with pytest.raises(ValidationError, match="yalnız “sırt ve barkod etiketi”"):
            _parti(nushalar, LabelPrintKind.BARCODE, spine_template=sirt)

        farkli = kuyruk_ortak.sablon(name="Sırt 40'lı", kind=LabelKind.SPINE, rows=10, cols=4)
        with pytest.raises(ValidationError, match="satır ve sütun sayısı aynı"):
            _parti(nushalar, spine_template=farkli)

        parti = _parti(nushalar, spine_template=sirt)
        assert parti.spine_template_id == sirt.pk

    def test_tanimsiz_icerik_ve_sira_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            _parti(kuyruk_ortak.nushalar(1), "CARD")
        with pytest.raises(ValidationError):
            _parti(kuyruk_ortak.nushalar(1), order="TITLE")

    def test_kuyruktan_bas_bos_kuyrukta_reddedilir(self) -> None:
        with pytest.raises(ValidationError, match="Kuyrukta bu süzgece uyan nüsha yok"):
            label_queue.queue_copy_ids(kind=LabelPrintKind.BOTH, order=LabelOrder.BARCODE)
        with pytest.raises(ValidationError):
            label_queue.queue_copy_ids(kind=LabelPrintKind.BOTH, order=LabelOrder.BARCODE, limit=0)


# ============================================================ Kenar durumları
class TestKenarDurumlari:
    def test_sirt_partisinin_geri_alinmasi_barkod_isaretine_dokunmaz(self) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        barkod = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.BARCODE))
        sirt = label_queue.confirm_batch(_parti([nusha], LabelPrintKind.SPINE))

        label_queue.revert_batch(sirt)

        assert isaretler(nusha) == (barkod.confirmed_at, None, None)

    def test_yeniden_basimda_acik_kalibrasyon_secilebilir(self) -> None:
        sablon = kuyruk_ortak.sablon()
        eski = _parti(kuyruk_ortak.nushalar(1), template=sablon)
        yazici = kuyruk_ortak.kalibrasyon(sablon, printer_name="Laboratuvar yazıcısı")

        yeni = label_queue.reprint_batch(eski, calibration=yazici, kind=LabelPrintKind.SPINE)

        assert (yeni.calibration_id, yeni.kind) == (yazici.pk, LabelPrintKind.SPINE)

    def test_silinmis_kalibrasyon_ve_sablonsuz_sirt_kalibrasyonu_reddedilir(self) -> None:
        sablon = kuyruk_ortak.sablon()
        eski_yazici = kuyruk_ortak.kalibrasyon(sablon)
        eski_yazici.delete()
        nushalar = kuyruk_ortak.nushalar(1)

        with pytest.raises(ValidationError, match="kalibrasyon silinmiş"):
            _parti(nushalar, template=sablon, calibration=eski_yazici)
        with pytest.raises(ValidationError, match="yalnız ayrı bir sırt şablonuyla"):
            _parti(nushalar, template=sablon, spine_calibration=kuyruk_ortak.kalibrasyon(sablon))


# ============================================================ Sonradan silinen / elden çıkan nüsha
class TestSonradanElCikanNusha:
    """Denetim bulgusu (24.09.2026): partideki bir nüsha sonradan silinir ya da elden
    çıkarsa partinin PDF'i hiç üretilemiyor, onay ise silinmiş nüshayı da "basıldı"
    işaretliyordu. Artık hücresi BOŞ kalır (sonrakiler kaymaz), onay ona dokunmaz,
    yeniden basım onu almaz. PDF testleri GERÇEK motorla koşar.
    """

    def _parti_ve_elden_cikanlar(self) -> tuple[LabelPrintBatch, list[Copy]]:
        nushalar = kuyruk_ortak.nushalar(4)
        parti = _parti(nushalar, LabelPrintKind.BARCODE, order=LabelOrder.IMPORT_ROW, start_cell=3)
        nushalar[1].delete()  # yumuşak silme
        Copy.objects.filter(pk=nushalar[2].pk).update(status=CopyStatus.TRANSFERRED)
        return parti, nushalar

    def test_partinin_pdfi_uretilir_elden_cikanin_hucresi_bos_kalir(self) -> None:
        from apps.kutuphane.labels.geometry import SheetGeometry
        from apps.kutuphane.tests import etiket_olcum as olcum

        parti, nushalar = self._parti_ve_elden_cikanlar()

        pdf = label_queue.render_batch_pdf(parti)

        sayfa = olcum.sayfalar(pdf)[0]
        tabaka = SheetGeometry.from_template(parti.template)
        for sira, nusha in enumerate(nushalar):
            hucre = tabaka.cell(parti.start_cell - 1 + sira)  # 3., 4., 5., 6. hücre
            metinler = [
                y.metin
                for y in olcum.yazilar_hucrede(
                    sayfa, hucre.left, hucre.top, hucre.right, hucre.bottom
                )
            ]
            barlar = olcum.barlar_hucrede(sayfa, hucre.left, hucre.top, hucre.right, hucre.bottom)
            numara = f"{nusha.barcode[:4]}-{nusha.barcode[4:]}"
            if sira in (1, 2):
                assert metinler == [] and barlar == [], sira  # yeri tutuldu, basılmadı
            else:
                assert numara in metinler and barlar, sira  # sonraki etiket KAYMADI

    def test_onay_elden_cikan_nushayi_isaretlemez_geri_alma_ona_dokunmaz(self) -> None:
        parti, nushalar = self._parti_ve_elden_cikanlar()

        onayli = label_queue.confirm_batch(parti)

        assert isaretler(nushalar[0])[0] == onayli.confirmed_at
        assert isaretler(nushalar[3])[0] == onayli.confirmed_at
        assert isaretler(nushalar[1]) == (None, None, None)
        assert isaretler(nushalar[2]) == (None, None, None)

        sonuc = label_queue.revert_batch(onayli)
        assert (sonuc["restored"], sonuc["requeued"]) == (2, 2)
        assert all(isaretler(n) == (None, None, None) for n in nushalar)

    def test_yeniden_basim_elden_cikanlari_almaz_sirayi_korur(self) -> None:
        parti, nushalar = self._parti_ve_elden_cikanlar()

        yeni = label_queue.reprint_batch(label_queue.confirm_batch(parti))

        assert list(yeni.items.order_by("position").values_list("copy_id", flat=True)) == [
            nushalar[0].pk,
            nushalar[3].pk,
        ]
        assert yeni.copy_count == 2

    def test_hepsi_elden_ciktiysa_acik_ret(self) -> None:
        nushalar = kuyruk_ortak.nushalar(2)
        parti = _parti(nushalar, LabelPrintKind.BARCODE)
        for nusha in nushalar:
            nusha.delete()

        with pytest.raises(ValidationError, match="hiçbirine artık etiket basılamaz"):
            label_queue.render_batch_pdf(parti)
        with pytest.raises(ValidationError, match="hiçbirine artık etiket basılamaz"):
            label_queue.reprint_batch(parti)
