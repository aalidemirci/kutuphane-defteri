"""Bağış kararı → toplu katalog (F8 — Md. 10/3, TMY 10/1-a; tasarım §14.1 F8).

F2 akışı (`test_katalog_servisleri.py::TestBagisOnKaydi`) korunur; burada F8'in
iki bütünleştirmesi sınanır: edinim tarihi kabul (komisyon kararı) tarihidir ve
katalogda zaten bulunan kitap için yeni eser açılmaz.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane.models import (
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    DonationIntake,
    Work,
)
from apps.kutuphane.services import donations
from apps.kutuphane.tests.ortak import eser, karar, nusha

pytestmark = pytest.mark.django_db


def _on_kayit(*kalemler: dict[str, object], received: date | None = None) -> DonationIntake:
    return donations.create_intake(
        donor_name="Deneme Bağışçı",
        received_date=received or timezone.localdate() - timedelta(days=10),
        items=list(kalemler) or [{"title": "Çalıkuşu", "authors": "Reşat Nuri Güntekin"}],
    )


def _karar(gun: date | None = None) -> CommissionDecision:
    return karar(
        decision_type=CommissionDecisionType.DONATION_REVIEW,
        decision_date=gun or timezone.localdate() - timedelta(days=2),
    )


def _kalemler(intake: DonationIntake) -> list[int]:
    return list(intake.items.order_by("pk").values_list("pk", flat=True))


class TestEdinimTarihi:
    def test_varsayilan_karar_tarihidir(self) -> None:
        intake = _on_kayit()
        decision = _karar()
        sonuc = donations.apply_decision(
            intake, commission_decision=decision, accepted_ids=_kalemler(intake)
        )
        assert sonuc["acquisition"].date == decision.decision_date

    def test_karar_gelisten_onceyse_gelis_tarihi(self) -> None:
        """Komisyon listeyi kitaplar gelmeden karara bağlamış olabilir: giriş gelişten önce olmaz."""
        gelis = timezone.localdate() - timedelta(days=1)
        intake = _on_kayit(received=gelis)
        sonuc = donations.apply_decision(
            intake,
            commission_decision=_karar(gelis - timedelta(days=5)),
            accepted_ids=_kalemler(intake),
        )
        assert sonuc["acquisition"].date == gelis

    def test_karardan_once_gelecekte_ya_da_gelisten_once_tarih_reddedilir(self) -> None:
        intake = _on_kayit()
        decision = _karar()
        for tarih, ileti in (
            (decision.decision_date - timedelta(days=1), "TMY 10/1-a"),
            (timezone.localdate() + timedelta(days=1), "bugünden sonra"),
        ):
            with pytest.raises(ValidationError, match=ileti):
                donations.apply_decision(
                    intake,
                    commission_decision=decision,
                    accepted_ids=_kalemler(intake),
                    acquisition_date=tarih,
                )
        assert not Copy.objects.exists()


class TestVarOlanEsereBaglama:
    def test_ayni_ad_ve_yazar_var_olan_esere_eklenir(self) -> None:
        var_olan = eser(title="ÇALIKUŞU", authors="Reşat Nuri GÜNTEKİN")
        nusha(var_olan)
        intake = _on_kayit(
            {"title": "Çalıkuşu", "authors": "Reşat Nuri Güntekin", "copies": 2},
            {"title": "Yaban", "authors": "Yakup Kadri Karaosmanoğlu"},
        )
        sonuc = donations.apply_decision(
            intake, commission_decision=_karar(), accepted_ids=_kalemler(intake)
        )

        assert [w.pk for w in sonuc["linked_works"]] == [var_olan.pk]
        assert [w.title for w in sonuc["works"]] == ["Yaban"]
        assert Work.objects.count() == 2  # yalnız "Yaban" yeni açıldı (iexact Türkçede çalışmaz)
        assert var_olan.copies.count() == 3
        assert intake.items.get(title="Çalıkuşu").work_id == var_olan.pk

    def test_isbn_ve_ad_eslesmesi(self) -> None:
        var_olan = eser(title="Sefiller", authors="Victor Hugo", isbn="9789750738609")
        intake = _on_kayit({"title": "Sefiller", "authors": "V. Hugo", "isbn": "978-975-07-3860-9"})
        eslesme = donations.item_matches(intake.items.get())
        assert eslesme.exact is not None and eslesme.exact.pk == var_olan.pk

    def test_supheli_aday_kendiliginden_baglanmaz_elle_baglanir(self) -> None:
        benzer = eser(title="Çalıkuşu", authors="Başka Yazar")
        intake = _on_kayit()
        (kalem,) = _kalemler(intake)
        eslesme = donations.item_matches(intake.items.get())
        assert eslesme.exact is None and [w.pk for w in eslesme.suspects] == [benzer.pk]

        sonuc = donations.apply_decision(
            intake,
            commission_decision=_karar(),
            accepted_ids=[kalem],
            work_links={kalem: benzer.pk},
        )
        assert sonuc["works"] == [] and [w.pk for w in sonuc["linked_works"]] == [benzer.pk]

    def test_null_bag_yeni_eser_acar(self) -> None:
        eser(title="Çalıkuşu", authors="Reşat Nuri Güntekin")
        intake = _on_kayit()
        (kalem,) = _kalemler(intake)
        sonuc = donations.apply_decision(
            intake, commission_decision=_karar(), accepted_ids=[kalem], work_links={kalem: None}
        )
        assert len(sonuc["works"]) == 1
        assert Work.objects.filter(title="Çalıkuşu").count() == 2

    def test_reddedilen_kalem_esere_baglanamaz(self) -> None:
        var_olan = eser()
        intake = _on_kayit()
        (kalem,) = _kalemler(intake)
        with pytest.raises(ValidationError) as hata:
            donations.apply_decision(
                intake,
                commission_decision=_karar(),
                rejected={kalem: "Yıpranmış."},
                work_links={kalem: var_olan.pk},
            )
        assert "work_links" in hata.value.message_dict


def test_eslesme_ucu_kayit_yazmaz() -> None:
    var_olan = eser(title="Çalıkuşu", authors="Reşat Nuri Güntekin")
    intake = _on_kayit()
    yanit = APIClient().get(f"/api/v1/library/donation-intakes/{intake.pk}/matches/")
    assert yanit.status_code == 200
    (satir,) = yanit.json()["results"]
    assert satir["exact"]["id"] == var_olan.pk and satir["suspects"] == []
    assert not Copy.objects.exists()


def test_karar_ucu_bagli_eser_sayisini_dondurur() -> None:
    var_olan = eser(title="Çalıkuşu", authors="Reşat Nuri Güntekin")
    intake = _on_kayit()
    yanit = APIClient().post(
        f"/api/v1/library/donation-intakes/{intake.pk}/decision/",
        {
            "commission_decision": _karar().pk,
            "accepted_ids": _kalemler(intake),
            "work_links": {},
        },
        format="json",
    )
    assert yanit.status_code == 200, yanit.json()
    govde = yanit.json()
    assert (govde["work_count"], govde["linked_work_count"], govde["copy_count"]) == (0, 1, 1)
    assert var_olan.copies.count() == 1


# ============================================================ F8 düzeltme turu (25.09.2026)


class TestKararTarihiSonradanDegisince:
    """Kök neden: "karardan önce olamaz" kuralı yalnız bağlı kayıt YAZILIRKEN sınanıyordu;
    kararın tarihi sonradan ileri alınınca kural geriye dönük bozuluyordu (TMY 10/1-a)."""

    def test_bagis_ediniminden_sonraya_alinamaz_geriye_alinabilir(self) -> None:
        from apps.kutuphane.services import commissions

        intake = _on_kayit()
        decision = _karar()
        sonuc = donations.apply_decision(
            intake, commission_decision=decision, accepted_ids=_kalemler(intake)
        )
        edinim_tarihi = sonuc["acquisition"].date
        with pytest.raises(ValidationError) as hata:
            commissions.update_commission_decision(
                decision, decision_date=edinim_tarihi + timedelta(days=1)
            )
        ileti = hata.value.message_dict["decision_date"][0]
        assert "bağış edinimi" in ileti and f"{edinim_tarihi:%d.%m.%Y}" in ileti
        decision.refresh_from_db()
        assert decision.decision_date == edinim_tarihi
        # Geri almak ve sayıyı düzeltmek serbesttir.
        geri = commissions.update_commission_decision(
            decision, decision_date=edinim_tarihi - timedelta(days=3), decision_no="2026/8"
        )
        assert geri.decision_no == "2026/8"

    def test_ayiklama_onayindan_ve_nadir_eser_gonderiminden_sonraya_alinamaz(self) -> None:
        from apps.kutuphane.services import commissions, rare_works, weeding
        from apps.kutuphane.tests.ayiklama_ortak import (
            ayiklama_karari,
            kalem_ekle,
            onaya_kadar,
            raftaki,
            teklif,
        )

        bugun = timezone.localdate()
        decision = ayiklama_karari(decision_date=bugun - timedelta(days=5))
        batch = teklif()
        kalem_ekle(batch, raftaki("Tarih Sondası"))
        onaya_kadar(batch, decision=decision, approved_on=bugun - timedelta(days=3))
        liste = rare_works.create_submission(commission_decision=decision)
        rare_works.add_copies(liste, copy_ids=[raftaki("Yazma", is_rare_or_manuscript=True).pk])
        rare_works.send_submission(liste, sent_on=bugun - timedelta(days=1))

        with pytest.raises(ValidationError, match="harcama yetkilisi onayı"):
            commissions.update_commission_decision(decision, decision_date=bugun)
        # Onay tarihine kadar ileri alınabilir (onay aynı gün olabilir).
        commissions.update_commission_decision(decision, decision_date=bugun - timedelta(days=3))
        weeding.apply_batch(batch)  # uygulanmış teklif de kilitli kalır
        with pytest.raises(ValidationError, match="harcama yetkilisi onayı"):
            commissions.update_commission_decision(
                decision, decision_date=bugun - timedelta(days=2)
            )

    def test_yalniz_gonderilmis_liste(self) -> None:
        from apps.kutuphane.services import commissions, rare_works
        from apps.kutuphane.tests.ayiklama_ortak import ayiklama_karari, raftaki
        from apps.kutuphane.tests.teslim_ortak import etkin_yil

        etkin_yil()
        bugun = timezone.localdate()
        decision = ayiklama_karari(decision_date=bugun - timedelta(days=5))
        liste = rare_works.create_submission(commission_decision=decision)
        rare_works.add_copies(liste, copy_ids=[raftaki("Yazma", is_rare_or_manuscript=True).pk])
        rare_works.send_submission(liste, sent_on=bugun - timedelta(days=4))
        with pytest.raises(ValidationError, match="nadir eserler listesinin gönderimi"):
            commissions.update_commission_decision(decision, decision_date=bugun)


def test_bagis_ediniminin_tarihi_sonradan_karardan_onceye_cekilemez() -> None:
    """Aynı kuralın öbür yüzü: edinimin tarihi elle geri çekilirken (F8 ekleri 9)."""
    from apps.kutuphane.services import catalog

    intake = _on_kayit()
    decision = _karar()
    edinim = donations.apply_decision(
        intake, commission_decision=decision, accepted_ids=_kalemler(intake)
    )["acquisition"]
    with pytest.raises(ValidationError) as hata:
        catalog.update_acquisition(edinim, date=decision.decision_date - timedelta(days=1))
    assert "date" in hata.value.message_dict
    assert catalog.update_acquisition(edinim, notes="Not düzeltildi.").notes == "Not düzeltildi."
