"""El yazması ve nadir eserler listesi (F8 — Md. 12/2, D14; E8 verisi).

Kod kapısı: **nadir eser ayıklanamaz** (`test_ayiklama.py::TestAyiklamaEngelleri`)
ve D14 — nadir eser denetimi ve komisyon kararı bağı (burada).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.kutuphane import selectors_ayiklama
from apps.kutuphane.models import (
    CommissionDecision,
    CommissionDecisionType,
    RareWorksSubmission,
    RareWorksSubmissionStatus,
)
from apps.kutuphane.services import catalog, commissions, rare_works
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.ayiklama_ortak import ayiklama_karari, raftaki, tazele
from apps.kutuphane.tests.ortak import karar
from apps.kutuphane.tests.teslim_ortak import etkin_yil
from apps.okul.kip import KIP

pytestmark = pytest.mark.django_db


def _liste(commission_decision: CommissionDecision | None = None) -> RareWorksSubmission:
    etkin_yil()
    return rare_works.create_submission(commission_decision=commission_decision)


def test_liste_yalniz_nadir_eser_isaretli_nushalari_alir() -> None:
    liste = _liste()
    nadir = raftaki("Eski Yazma", is_rare_or_manuscript=True)
    sade = raftaki("Sade Kitap")

    with pytest.raises(ValidationError) as hata:
        rare_works.add_copies(liste, copy_ids=[nadir.pk, sade.pk])
    assert rare_works.NOT_RARE_MESSAGE in hata.value.message_dict["barcodes"][0]
    assert not liste.items.exists()  # tek işlem

    (satir,) = rare_works.add_copies(liste, barcodes=[nadir.barcode])
    assert satir.copy_id == nadir.pk
    with pytest.raises(ValidationError, match="zaten var"):
        rare_works.add_copies(liste, copy_ids=[nadir.pk])


def test_gonderim_komisyon_kararina_baglidir_ve_karar_ayiklama_turundedir() -> None:
    liste = _liste()
    rare_works.add_copies(liste, copy_ids=[raftaki(is_rare_or_manuscript=True).pk])
    bugun = timezone.localdate()

    with pytest.raises(ValidationError) as hata:
        rare_works.send_submission(liste, sent_on=bugun)
    assert "commission_decision" in hata.value.message_dict

    with pytest.raises(ValidationError) as hata:
        rare_works.update_submission(
            liste,
            commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
        )
    assert "commission_decision" in hata.value.message_dict

    rare_works.update_submission(liste, commission_decision=ayiklama_karari())
    with pytest.raises(ValidationError, match="bugünden sonra"):
        rare_works.send_submission(liste, sent_on=bugun + timedelta(days=1))
    with pytest.raises(ValidationError, match="karar"):
        rare_works.send_submission(liste, sent_on=bugun - timedelta(days=1))

    gonderilen = rare_works.send_submission(liste, sent_on=bugun, sent_document_no="E-12345")
    assert gonderilen.status == RareWorksSubmissionStatus.SENT
    assert (gonderilen.sent_on, gonderilen.sent_document_no) == (bugun, "E-12345")


def test_bos_liste_gonderilemez() -> None:
    liste = _liste(commission_decision=ayiklama_karari())
    with pytest.raises(ValidationError, match="en az bir"):
        rare_works.send_submission(liste, sent_on=timezone.localdate())


def test_gonderilmis_liste_degismez_ve_nadir_isareti_kaldirilamaz() -> None:
    nadir = raftaki(is_rare_or_manuscript=True)
    liste = _liste(commission_decision=ayiklama_karari())
    (satir,) = rare_works.add_copies(liste, copy_ids=[nadir.pk])

    # Hiçbir listede olmayan işaret veri giriş hatası olarak düzeltilebilir.
    ikinci = raftaki("Yanlış İşaretli", is_rare_or_manuscript=True)
    catalog.update_copy(ikinci, is_rare_or_manuscript=False)
    assert not tazele(ikinci).is_rare_or_manuscript

    rare_works.send_submission(liste, sent_on=timezone.localdate())
    with pytest.raises(ValidationError, match="Genel Müdürlüğe gönderilmiş"):
        rare_works.add_copies(liste, copy_ids=[raftaki(is_rare_or_manuscript=True).pk])
    with pytest.raises(ValidationError, match="Genel Müdürlüğe gönderilmiş"):
        rare_works.remove_item(satir)
    with pytest.raises(ValidationError, match="Genel Müdürlüğe gönderilmiş"):
        rare_works.delete_submission(liste)
    with pytest.raises(ValidationError) as hata:
        catalog.update_copy(tazele(nadir), is_rare_or_manuscript=False)
    assert "is_rare_or_manuscript" in hata.value.message_dict
    # Öbür alanlar düzenlenebilir kalır.
    assert catalog.update_copy(tazele(nadir), old_register_no="E-7").old_register_no == "E-7"


def test_nadir_eser_secicisi_gonderilmemisleri_ayirir() -> None:
    gonderilen = raftaki("Gönderilen", is_rare_or_manuscript=True)
    bekleyen = raftaki("Bekleyen", is_rare_or_manuscript=True)
    raftaki("Sade")
    liste = _liste(commission_decision=ayiklama_karari())
    rare_works.add_copies(liste, copy_ids=[gonderilen.pk])
    rare_works.send_submission(liste, sent_on=timezone.localdate())

    hepsi = {c.pk: cast("Any", c).sent for c in selectors_ayiklama.rare_copies()}
    assert hepsi == {gonderilen.pk: True, bekleyen.pk: False}
    assert [c.pk for c in selectors_ayiklama.rare_copies(unsent_only=True)] == [bekleyen.pk]


def test_karar_listeye_baglaninca_kullanimdadir() -> None:
    decision = ayiklama_karari()
    _liste(commission_decision=decision)
    assert commissions.decision_in_use(decision)
    assert selectors_ayiklama.decision_usage(decision)["rare_works_submissions"] == 1


def test_gorevli_kipinde_liste_islenemez() -> None:
    liste = _liste()
    KIP.gorevliye_gec()
    with pytest.raises(KipYetkisiz):
        rare_works.add_copies(liste, copy_ids=[raftaki(is_rare_or_manuscript=True).pk])


# ============================================================ F8 düzeltme turu (25.09.2026)


def test_komisyonca_tespit_edilen_nadir_eserin_isareti_kaldirilamaz() -> None:
    """Md. 12/2 listeyi "komisyon tarafından tespit edilen" diye tanımlar: karar bağlanmış
    (henüz gönderilmemiş) listedeki nüshanın işareti artık veri girişi değildir."""
    nadir = raftaki("Komisyonca Tespit Edilmiş", is_rare_or_manuscript=True)
    liste = _liste(commission_decision=ayiklama_karari())
    (satir,) = rare_works.add_copies(liste, copy_ids=[nadir.pk])

    with pytest.raises(ValidationError) as hata:
        catalog.update_copy(tazele(nadir), is_rare_or_manuscript=False)
    assert catalog.RARE_FLAG_DECIDED_MESSAGE in hata.value.message_dict["is_rare_or_manuscript"]
    assert tazele(nadir).is_rare_or_manuscript

    # Bilinçli yol: listeden çıkarmak (listede görünen bir adım), sonra işareti düzeltmek.
    rare_works.remove_item(satir)
    catalog.update_copy(tazele(nadir), is_rare_or_manuscript=False)
    assert not tazele(nadir).is_rare_or_manuscript


def test_karar_baglanmamis_listedeki_isaret_duzeltilebilir() -> None:
    nadir = raftaki("Hazırlanan Listede", is_rare_or_manuscript=True)
    liste = _liste()
    rare_works.add_copies(liste, copy_ids=[nadir.pk])
    catalog.update_copy(tazele(nadir), is_rare_or_manuscript=False)
    assert not tazele(nadir).is_rare_or_manuscript


@pytest.mark.parametrize("gonderilmis", [True, False], ids=["gonderilmis", "hazirlanan"])
def test_listedeki_nadir_eser_silinemez(gonderilmis: bool) -> None:
    """Kök neden: `catalog.delete_copy` nadir eser satırını saymıyordu; Genel Müdürlüğe
    bildirilmiş eser "yanlış açılmış kayıt" yoluyla defterden düşüyordu."""
    nadir = raftaki("Bildirilen Yazma", is_rare_or_manuscript=True)
    liste = _liste(commission_decision=ayiklama_karari())
    (satir,) = rare_works.add_copies(liste, copy_ids=[nadir.pk])
    if gonderilmis:
        rare_works.send_submission(liste, sent_on=timezone.localdate())

    with pytest.raises(ValidationError) as hata:
        catalog.delete_copy(tazele(nadir))
    assert catalog.DELETE_RARE_LISTED_MESSAGE in hata.value.message_dict["status"]
    assert tazele(nadir).deleted_at is None
    assert [c.pk for c in selectors_ayiklama.rare_copies()] == [nadir.pk]

    if not gonderilmis:
        rare_works.remove_item(satir)
        catalog.delete_copy(tazele(nadir))
        assert tazele(nadir).deleted_at is not None


def test_listedeki_nadir_eser_ayiklanamaz_isareti_de_kaldirilamaz() -> None:
    """Sonda: kararı bağlı taslak listedeki nadir eser işaret kaldırılarak ayıklanıyordu."""
    from apps.kutuphane.models import WeedingItem
    from apps.kutuphane.tests.ayiklama_ortak import kalem_ekle, teklif

    nadir = raftaki("Tespit Edilmiş Yazma", is_rare_or_manuscript=True)
    liste = _liste(commission_decision=ayiklama_karari())
    rare_works.add_copies(liste, copy_ids=[nadir.pk])
    with pytest.raises(ValidationError):
        catalog.update_copy(tazele(nadir), is_rare_or_manuscript=False)
    with pytest.raises(ValidationError, match="nadir eser ayıklanamaz"):
        kalem_ekle(teklif(), tazele(nadir), "OBSOLETE")
    assert not WeedingItem.objects.filter(copy_id=nadir.pk).exists()
