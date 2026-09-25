"""Kayıp, hasar ve onarım — Md. 19 dosyaları ve D3 akışları (F7; tasarım §9-9, §13 D3).

Kod kapısı maddeleri: **Md. 19 kademe kapısı** (bedel seçenekleri yalnız
ortaöğretimde; ilkokul ve ortaokulda o çözüm yolları reddedilir) ve **D3 kapanır**
(onarıma gönder / onarımdan dön, hasar dosyası açılışı). Ayrıca: kayıp
bildiriminde ödünç kapanır ve nüsha "Kayıp" olur, bulununca rafa döner; kayıttan
düşme yalnız öneridir; sorumlu notu şifrelidir; çözülmemiş dosya açık
yükümlülüktür; tahsilat ve borç dili yoktur.

F7 düzeltme turu: öneriyle kapanan kayıp dosyasında bulunan kitap rafa döner;
açık hasar dosyalı nüsha kaybolunca hasar dosyası "Kayba dönüştü" ile kapanır;
TMY 32/3 kapısı onarımı ve bedel adımlarını kapsamaz; kişi bağı kayıt defterinde,
ilişik listesinde ve E5'te aynı kuraldır.

25.09.2026 kullanıcı kararı (`TestBedelIkiAdim`): bedel iki adımdır — "Bedel
belirlendi" kişinin açık işini sürdürür, "Bedel teslim alındı" bitirir (ilişik ve E5);
dosya okul için açık kalır ve yalnız bedelle alımla kapanır.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.models import (
    CaseResolution,
    CaseType,
    CopyRepair,
    CopyStatus,
    DeliveryStatus,
    LoanStatus,
    LossDamageCase,
)
from apps.kutuphane.services import deliveries, loss_damage, memberships, tmy_kapisi
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.teslim_ortak import (
    kademe_yaz,
    ogretmen,
    sube,
    tazele_dosya,
    tazele_nusha,
    tazele_teslim,
    teslim_et,
)
from apps.okul.kip import KIP
from apps.okul.models import Personnel, SchoolLevel, Student
from apps.okul.services import persons

pytestmark = pytest.mark.django_db

R = CaseResolution
BEDEL_YOLLARI = (
    R.PRICE_DETERMINED,
    R.PRICE_RECEIVED,
    R.CLOSED_SAME_REPURCHASED,
    R.CLOSED_OTHER_REPURCHASED,
)
KAPANIS_YOLLARI = (R.CLOSED_SAME_REPURCHASED, R.CLOSED_OTHER_REPURCHASED)


def _kayip_dosyasi() -> LossDamageCase:
    return loss_damage.report_lost(copy=odunc_nushasi())


def _bedel_teslim_alinmis(dosya: LossDamageCase, bedel: str = "80") -> LossDamageCase:
    """İki bedel adımı: "Bedel belirlendi" → "Bedel teslim alındı" (yalnız ortaöğretim)."""
    loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal(bedel))
    loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)
    return tazele_dosya(dosya)


# ============================================================ Md. 19 kademe kapısı


class TestKademeKapisi:
    @pytest.mark.parametrize("kademe", [SchoolLevel.ILKOKUL, SchoolLevel.ORTAOKUL, ""])
    def test_ortaogretim_disinda_bedel_yollari_sunulmaz_ve_reddedilir(self, kademe: str) -> None:
        kademe_yaz(kademe)
        dosya = _kayip_dosyasi()

        assert loss_damage.price_options_available() is False
        assert loss_damage.allowed_resolutions(dosya) == (
            R.FOUND_RETURNED,
            R.REPLACED_SAME,
            R.WRITE_OFF_PROPOSED,
        )
        for cozum in BEDEL_YOLLARI:
            with pytest.raises(ValidationError, match="yalnız ortaöğretim"):
                loss_damage.resolve_case(dosya, resolution=cozum, market_price=Decimal("120"))
        # Piyasa bedeli de kaydedilmez (bedel seçeneğidir).
        with pytest.raises(ValidationError, match="yalnız ortaöğretim"):
            loss_damage.resolve_case(dosya, resolution=R.REPLACED_SAME, market_price=Decimal("120"))
        guncel = tazele_dosya(dosya)
        assert guncel.is_open and guncel.market_price is None
        assert guncel.price_determined_at is None and guncel.price_received_at is None

    def test_ortaogretimde_bedel_iki_adimdir_sonra_aynisi_alinir(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _kayip_dosyasi()
        secenekler = loss_damage.allowed_resolutions(dosya)
        assert R.PRICE_DETERMINED in secenekler
        assert R.PRICE_RECEIVED not in secenekler  # önce bedel belirlenir
        assert R.CLOSED_SAME_REPURCHASED not in secenekler

        loss_damage.resolve_case(
            dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("245.50")
        )
        dosya = tazele_dosya(dosya)
        assert dosya.resolution == R.PRICE_DETERMINED
        assert dosya.is_open and dosya.resolved_at is None
        assert dosya.market_price == Decimal("245.50")
        assert dosya.price_determined_at is not None and dosya.price_received_at is None
        assert tazele_nusha(dosya.copy).status == CopyStatus.LOST
        secenekler = loss_damage.allowed_resolutions(dosya)
        assert R.PRICE_RECEIVED in secenekler
        # Bedelle alım yalnız bedel teslim alındıktan sonra.
        assert R.CLOSED_SAME_REPURCHASED not in secenekler
        with pytest.raises(ValidationError, match="seçilemez"):
            loss_damage.resolve_case(dosya, resolution=R.CLOSED_SAME_REPURCHASED)

        loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)
        dosya = tazele_dosya(dosya)
        assert dosya.resolution == R.PRICE_RECEIVED
        assert dosya.is_open and dosya.resolved_at is None
        assert dosya.price_received_at is not None
        assert tazele_nusha(dosya.copy).status == CopyStatus.LOST
        assert loss_damage.allowed_resolutions(dosya) == KAPANIS_YOLLARI

        loss_damage.resolve_case(dosya, resolution=R.CLOSED_SAME_REPURCHASED)
        dosya = tazele_dosya(dosya)
        assert not dosya.is_open and dosya.resolved_at is not None
        assert dosya.price_received_at is not None  # adımın tarihi kayıtta kalır (E6)
        assert tazele_nusha(dosya.copy).status == CopyStatus.AVAILABLE

    def test_bedel_kaydi_piyasa_bedeli_ister(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _kayip_dosyasi()
        with pytest.raises(ValidationError, match="piyasa bedelini"):
            loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED)
        with pytest.raises(ValidationError, match="Bedel belirlendi"):
            loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED, market_price=Decimal("10"))
        with pytest.raises(ValidationError, match="seçilemez"):
            loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)

    def test_teslim_alinan_bedel_sonradan_degistirilmez(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("80"))
        # "Bedel belirlendi"de bedel düzeltilebilir.
        loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("95"))
        assert tazele_dosya(dosya).market_price == Decimal("95")
        with pytest.raises(ValidationError, match="Bedel belirlendi"):
            loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED, market_price=Decimal("1"))
        dosya = _bedel_teslim_alinmis(tazele_dosya(dosya), "95")
        with pytest.raises(ValidationError, match="seçilemez"):
            loss_damage.resolve_case(
                dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("5")
            )
        with pytest.raises(ValidationError, match="Bedel belirlendi"):
            loss_damage.resolve_case(
                dosya, resolution=R.CLOSED_SAME_REPURCHASED, market_price=Decimal("5")
            )
        assert tazele_dosya(dosya).market_price == Decimal("95")

    def test_bedelle_baska_eser_alininca_eski_nusha_icin_kayittan_dusme_onerilir(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _bedel_teslim_alinmis(_kayip_dosyasi())
        loss_damage.resolve_case(dosya, resolution=R.CLOSED_OTHER_REPURCHASED)

        dosya = tazele_dosya(dosya)
        assert dosya.write_off_proposed_at is not None and not dosya.is_open
        # Asıl kayıttan düşme F8/F9'un işidir: nüsha "Kayıp" kalır.
        assert tazele_nusha(dosya.copy).status == CopyStatus.LOST

    def test_kademe_sonradan_degisirse_bedel_yolu_kapanir(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("80"))
        kademe_yaz(SchoolLevel.ORTAOKUL)
        dosya = tazele_dosya(dosya)
        assert R.PRICE_RECEIVED not in loss_damage.allowed_resolutions(dosya)
        with pytest.raises(ValidationError, match="yalnız ortaöğretim"):
            loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)
        loss_damage.resolve_case(dosya, resolution=R.REPLACED_SAME)
        assert not tazele_dosya(dosya).is_open

    def test_kademe_degisse_de_bedeli_teslim_alinmis_dosya_kapanabilir(self) -> None:
        """Alınmış bedelin kullanımı kaydedilmeli: okulun açık işi kilitli kalmaz."""
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _bedel_teslim_alinmis(_kayip_dosyasi())
        kademe_yaz(SchoolLevel.ILKOKUL)
        dosya = tazele_dosya(dosya)
        assert loss_damage.allowed_resolutions(dosya) == KAPANIS_YOLLARI
        with pytest.raises(ValidationError, match="seçilemez"):
            loss_damage.resolve_case(dosya, resolution=R.REPLACED_SAME)
        loss_damage.resolve_case(dosya, resolution=R.CLOSED_OTHER_REPURCHASED)
        assert not tazele_dosya(dosya).is_open


# ============================================================ kayıp bildirimi


class TestKayipBildirimi:
    def test_oduncteki_nushanin_odunc_kapanir_nusha_kayip_olur(self) -> None:
        uyelik = uye()
        loan = odunc_ver(uyelik)

        dosya = loss_damage.report_lost(
            copy=loan.copy, responsible_note="Kitabı kaybettiğini söyledi."
        )

        loan.refresh_from_db()
        assert loan.status == LoanStatus.LOST_CONVERTED
        assert loan.lost_at is not None and loan.returned_at is None
        assert tazele_nusha(loan.copy).status == CopyStatus.LOST
        assert (dosya.case_type, dosya.membership_id, dosya.loan_id) == (
            CaseType.LOST,
            uyelik.pk,
            loan.pk,
        )
        # Kapanan ödünç sayı sınırına ve gecikmeye sayılmaz; yükümlülük dosyadır.
        assert selectors_dolasim.open_loan_count(uyelik) == 0
        assert persons.open_obligations(uyelik.person) == ["1 çözülmemiş kayıp/hasar dosyası var."]

    def test_teslimdeki_nushanin_teslimi_kayba_donusur(self) -> None:
        hoca = ogretmen()
        teslim = teslim_et([odunc_nushasi()], personnel=hoca).deliveries[0]

        dosya = loss_damage.report_lost(copy=teslim.copy)

        teslim = tazele_teslim(teslim)
        assert teslim.status == DeliveryStatus.LOST_CONVERTED and teslim.lost_at is not None
        assert dosya.delivery_id == teslim.pk
        assert tazele_nusha(teslim.copy).status == CopyStatus.LOST
        # Açık teslim bitti; öğretmenin yükümlülüğü artık dosyadır.
        assert persons.open_obligations(hoca) == ["1 çözülmemiş kayıp/hasar dosyası var."]

    def test_bulununca_nusha_rafa_doner_odunc_yeniden_acilmaz(self) -> None:
        loan = odunc_ver(uye())
        dosya = loss_damage.report_lost(copy=loan.copy)

        loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)

        assert tazele_nusha(loan.copy).status == CopyStatus.AVAILABLE
        loan.refresh_from_db()
        assert loan.status == LoanStatus.LOST_CONVERTED
        assert loan.membership is not None
        assert persons.open_obligations(loan.membership.person) == []

    def test_kayittan_dusme_yalniz_onerilir_nusha_kayip_kalir(self) -> None:
        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(dosya, resolution=R.WRITE_OFF_PROPOSED)
        dosya = tazele_dosya(dosya)
        assert dosya.write_off_proposed_at is not None and dosya.resolved_at is not None
        assert tazele_nusha(dosya.copy).status == CopyStatus.LOST

    def test_ayni_nushaya_ikinci_kayip_ve_kayip_nushaya_hasar_dosyasi_acilmaz(self) -> None:
        dosya = _kayip_dosyasi()
        with pytest.raises(ValidationError, match="zaten kayıp"):
            loss_damage.report_lost(copy=dosya.copy)
        with pytest.raises(ValidationError, match="Kayıp nüshaya"):
            loss_damage.open_damage_case(copy=dosya.copy)

    def test_uyelik_oduncle_celisirse_reddedilir(self) -> None:
        loan = odunc_ver(uye())
        with pytest.raises(ValidationError, match="ödüncü alan üyelikle"):
            loss_damage.report_lost(copy=loan.copy, membership=uye())

    def test_kapali_dosya_yeniden_cozulmez(self) -> None:
        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)
        with pytest.raises(ValidationError, match="zaten kapanmış"):
            loss_damage.resolve_case(dosya, resolution=R.WRITE_OFF_PROPOSED)

    def test_tmy_kapisi_kayip_bildirimi_ve_cozumde_sorulur(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """D4: TMY 32/3 durdurması (F9) kayıp bildirimini ve dosya çözümünü kapsar."""
        sorulan: list[str] = []
        monkeypatch.setattr(tmy_kapisi, "ensure_open", sorulan.append)
        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)
        assert sorulan == [tmy_kapisi.KAYIP_BILDIRIMI, tmy_kapisi.DOSYA_COZUMU]

    def test_tmy_kapisi_onarim_ve_bedel_kaydini_kapsamaz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F7 düzeltme turu: kapı yalnız TMY anlamında giriş-çıkışa yol açan çözümde sorulur.

        Hasar dosyasının "Onarıldı"sı ve iki bedel adımı ("Bedel belirlendi", "Bedel
        teslim alındı") nüshanın kaydını değiştirmez (onarım 32/3 kapsamı dışındadır —
        `tmy_kapisi` belge metni; bedel teslimi giriş-çıkış değildir — F7 ekleri 26);
        hasar dosyasında kayıttan düşme önerisi ve kayıp dosyasının kapanan çözümleri
        kapsamdadır.
        """
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        sorulan: list[str] = []
        monkeypatch.setattr(tmy_kapisi, "ensure_open", sorulan.append)

        hasar = loss_damage.open_damage_case(copy=odunc_nushasi())
        loss_damage.resolve_case(hasar, resolution=R.PRICE_DETERMINED, market_price=Decimal("50"))
        loss_damage.resolve_case(hasar, resolution=R.REPAIRED)
        assert sorulan == []

        oneri = loss_damage.open_damage_case(copy=odunc_nushasi())
        loss_damage.resolve_case(oneri, resolution=R.WRITE_OFF_PROPOSED)
        assert sorulan == [tmy_kapisi.DOSYA_COZUMU]

        kayip = _kayip_dosyasi()
        sorulan.clear()
        _bedel_teslim_alinmis(kayip, "50")
        assert sorulan == []
        loss_damage.resolve_case(kayip, resolution=R.CLOSED_SAME_REPURCHASED)
        assert sorulan == [tmy_kapisi.DOSYA_COZUMU]

    @pytest.mark.parametrize(
        ("tur", "cozum", "kapsamda"),
        [
            (CaseType.LOST, R.FOUND_RETURNED, True),
            (CaseType.LOST, R.REPLACED_SAME, True),
            (CaseType.LOST, R.CLOSED_SAME_REPURCHASED, True),
            (CaseType.LOST, R.CLOSED_OTHER_REPURCHASED, True),
            (CaseType.LOST, R.WRITE_OFF_PROPOSED, True),
            (CaseType.LOST, R.PRICE_DETERMINED, False),
            (CaseType.LOST, R.PRICE_RECEIVED, False),
            (CaseType.DAMAGED, R.WRITE_OFF_PROPOSED, True),
            (CaseType.DAMAGED, R.CLOSED_OTHER_REPURCHASED, True),
            (CaseType.DAMAGED, R.REPAIRED, False),
            (CaseType.DAMAGED, R.REPLACED_SAME, False),
            (CaseType.DAMAGED, R.CLOSED_SAME_REPURCHASED, False),
            (CaseType.DAMAGED, R.PRICE_DETERMINED, False),
            (CaseType.DAMAGED, R.PRICE_RECEIVED, False),
        ],
    )
    def test_tmy_kapisinin_cozum_kapsami(self, tur: str, cozum: str, kapsamda: bool) -> None:
        assert tmy_kapisi.dosya_cozumu_kapsamda_mi(tur, cozum) is kapsamda

    def test_oneriyle_kapanan_kayip_dosyasinda_kitap_bulununca_rafa_doner(self) -> None:
        """F7 düzeltme turu: öneri kayıttan düşme değildir; bulunan kitap dolaşıma döner."""
        loan = odunc_ver(uye())
        dosya = loss_damage.report_lost(copy=loan.copy)
        loss_damage.resolve_case(dosya, resolution=R.WRITE_OFF_PROPOSED)
        dosya = tazele_dosya(dosya)
        assert not dosya.is_open
        assert loss_damage.allowed_resolutions(dosya) == (R.FOUND_RETURNED,)
        with pytest.raises(ValidationError, match="zaten kapanmış"):
            loss_damage.resolve_case(dosya, resolution=R.REPLACED_SAME)

        loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)

        dosya = tazele_dosya(dosya)
        assert dosya.resolution == R.FOUND_RETURNED and not dosya.is_open
        assert dosya.write_off_proposed_at is None and dosya.resolved_at is not None
        assert tazele_nusha(loan.copy).status == CopyStatus.AVAILABLE
        assert loss_damage.allowed_resolutions(dosya) == ()
        loan.refresh_from_db()
        assert loan.status == LoanStatus.LOST_CONVERTED  # ödünç yeniden açılmaz
        odunc_ver(uye(), tazele_nusha(loan.copy))  # kitap yeniden dolaşımda

    def test_bedelle_baska_eser_alinan_dosyada_bulundu_yolu_yoktur(self) -> None:
        """Md. 19: "kaybedilenin kaydı silinerek başka eser satın alınır" — öneri geri alınmaz."""
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = _bedel_teslim_alinmis(_kayip_dosyasi())
        loss_damage.resolve_case(dosya, resolution=R.CLOSED_OTHER_REPURCHASED)
        dosya = tazele_dosya(dosya)
        assert loss_damage.allowed_resolutions(dosya) == ()
        with pytest.raises(ValidationError, match="zaten kapanmış"):
            loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)

    def test_hasar_dosyasinda_oneri_bulundu_yolunu_acmaz(self) -> None:
        dosya = loss_damage.open_damage_case(copy=odunc_nushasi())
        loss_damage.resolve_case(dosya, resolution=R.WRITE_OFF_PROPOSED)
        assert loss_damage.allowed_resolutions(tazele_dosya(dosya)) == ()

    def test_nusha_kayip_degilse_oneri_geri_alinamaz(self) -> None:
        """Nüsha asıl kayıttan düşülmüşse (F8/F9) öneri yolu kapanır."""
        from apps.kutuphane.models import Copy

        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(dosya, resolution=R.WRITE_OFF_PROPOSED)
        Copy.all_objects.filter(pk=dosya.copy_id).update(status=CopyStatus.WITHDRAWN_LOST)
        dosya = tazele_dosya(dosya)
        assert loss_damage.allowed_resolutions(dosya) == ()
        with pytest.raises(ValidationError, match="zaten kapanmış"):
            loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)


# ============================================================ hasar dosyası açık nüsha kaybolursa


class TestHasarKaybaDonusur:
    """F7 düzeltme turu: hasar dosyası nüshayı dolaşımdan çıkarmaz; nüsha sonra kaybolursa
    kayıp bildirilebilmelidir. Hasar dosyası "Kayba dönüştü" ile kapanır, kayıp dosyası
    açılır; gerçeğe aykırı bir çözümle kapatmak gerekmez."""

    def test_oduncte_kaybolan_hasarli_nusha(self) -> None:
        kitap = odunc_nushasi()
        onceki = uye()
        hasar = loss_damage.open_damage_case(
            copy=kitap, membership=onceki, responsible_note="Kapak yırtık."
        )
        uyelik = uye()
        loan = odunc_ver(uyelik, tazele_nusha(kitap))

        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap))

        loan.refresh_from_db()
        assert loan.status == LoanStatus.LOST_CONVERTED
        assert selectors_dolasim.open_loan_count(uyelik) == 0
        eski = tazele_dosya(hasar)
        assert eski.resolution == R.CONVERTED_TO_LOSS and not eski.is_open
        assert eski.resolved_at is not None and eski.write_off_proposed_at is None
        # Hasar dosyasının sorumlusu ve notu kendi kaydında kalır.
        assert eski.membership_id == onceki.pk and eski.responsible_note == "Kapak yırtık."
        assert (dosya.case_type, dosya.membership_id, dosya.loan_id) == (
            CaseType.LOST,
            uyelik.pk,
            loan.pk,
        )
        assert dosya.is_open and tazele_nusha(kitap).status == CopyStatus.LOST
        assert persons.open_obligations(onceki.person) == []
        assert persons.open_obligations(uyelik.person) == ["1 çözülmemiş kayıp/hasar dosyası var."]
        assert loss_damage.allowed_resolutions(eski) == ()

    def test_teslimde_kaybolan_hasarli_nusha(self) -> None:
        kitap = odunc_nushasi()
        hasar = loss_damage.open_damage_case(copy=kitap)
        hoca = ogretmen()
        teslim = teslim_et([tazele_nusha(kitap)], personnel=hoca).deliveries[0]

        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap))

        assert tazele_teslim(teslim).status == DeliveryStatus.LOST_CONVERTED
        assert tazele_dosya(hasar).resolution == R.CONVERTED_TO_LOSS
        assert dosya.delivery_id == teslim.pk and dosya.is_open
        assert persons.open_obligations(hoca) == ["1 çözülmemiş kayıp/hasar dosyası var."]

    def test_rafta_kaybolan_hasarli_nusha_ve_kayitli_bedel_korunur(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        kitap = odunc_nushasi()
        hasar = loss_damage.open_damage_case(copy=kitap)
        loss_damage.resolve_case(hasar, resolution=R.PRICE_DETERMINED, market_price=Decimal("75"))

        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap))

        eski = tazele_dosya(hasar)
        assert eski.resolution == R.CONVERTED_TO_LOSS and eski.market_price == Decimal("75")
        assert dosya.membership_id is None and dosya.market_price is None

    def test_bedeli_teslim_alinmis_hasar_dosyasi_kayba_donusunce_adimlar_kayitta_kalir(
        self,
    ) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        kitap = odunc_nushasi()
        hasar = _bedel_teslim_alinmis(loss_damage.open_damage_case(copy=kitap), "60")

        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap))

        eski = tazele_dosya(hasar)
        assert eski.resolution == R.CONVERTED_TO_LOSS and not eski.is_open
        assert eski.market_price == Decimal("60")
        assert eski.price_determined_at is not None and eski.price_received_at is not None
        assert dosya.is_open and dosya.is_person_open_work

    def test_kayba_donustu_elle_secilemez_ve_yalniz_hasarda_durur(self) -> None:
        hasar = loss_damage.open_damage_case(copy=odunc_nushasi())
        kayip = _kayip_dosyasi()
        for dosya in (hasar, kayip):
            assert R.CONVERTED_TO_LOSS not in loss_damage.allowed_resolutions(dosya)
            with pytest.raises(ValidationError, match="seçilemez"):
                loss_damage.resolve_case(dosya, resolution=R.CONVERTED_TO_LOSS)
        with pytest.raises(IntegrityError):
            LossDamageCase.objects.filter(pk=kayip.pk).update(
                resolution=R.CONVERTED_TO_LOSS, resolved_at=kayip.created_at
            )


# ============================================================ kişi bağı — tek kural


def _her_yerde(kisi: object) -> tuple[bool, bool, bool]:
    """Kişinin açık işi: (kayıt defteri, ilişik listesi, toplu soru) — E5 bunların tersidir."""
    from apps.kutuphane import ilisik_belgeleri, selectors_ilisik, selectors_teslim

    assert isinstance(kisi, Student | Personnel)
    yukumlu = bool(persons.open_obligations(kisi))
    ilisikte = not selectors_ilisik.person_clearance(kisi).is_clear
    anahtar = ("S" if isinstance(kisi, Student) else "P", kisi.pk)
    toplu = anahtar in selectors_teslim.persons_with_open_cases()
    if isinstance(kisi, Student):
        satirlar, eksik = selectors_ilisik.persons_for_certificate(student_ids=[kisi.pk])
    else:
        satirlar, eksik = selectors_ilisik.persons_for_certificate(personnel_ids=[kisi.pk])
    try:
        ilisik_belgeleri.ensure_certifiable(satirlar, eksik)
        belgesi_basilir = True
    except ValidationError:
        belgesi_basilir = False
    assert yukumlu == ilisikte == toplu == (not belgesi_basilir), kisi
    return yukumlu, ilisikte, toplu


class TestKisiBagiTutarliligi:
    """F7 düzeltme turu: kayıt defteri, ilişik listesi, E5 ve E6 dosyayı AYNI kişiye yazar.

    Kural: önce üyelik; üyelik yoksa teslim alan öğretmen (`selectors_teslim.case_person`).
    """

    def _hepsi(self, kisi: object) -> tuple[bool, bool, bool]:
        return _her_yerde(kisi)

    def test_ogretmene_teslimde_uye_secilirse_dosya_uyenindir(self) -> None:
        from apps.kutuphane import selectors_teslim

        hoca = ogretmen()
        kitap = odunc_nushasi()
        teslim_et([kitap], personnel=hoca)
        ogr = ogrenci()
        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap), membership=uye(ogr))

        assert self._hepsi(hoca) == (False, False, False)
        assert self._hepsi(ogr) == (True, True, True)
        assert selectors_teslim.case_person(tazele_dosya(dosya)) == ogr

    def test_ogretmene_teslimde_uye_secilmezse_dosya_ogretmenindir(self) -> None:
        from apps.kutuphane import selectors_teslim

        hoca = ogretmen()
        kitap = odunc_nushasi()
        teslim_et([kitap], personnel=hoca)
        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap))

        assert self._hepsi(hoca) == (True, True, True)
        assert selectors_teslim.case_person(tazele_dosya(dosya)) == hoca

    def test_ogretmenin_kendi_uyeligiyle_dosyasi(self) -> None:
        hoca = ogretmen()
        loss_damage.report_lost(copy=odunc_ver(uye(hoca)).copy)
        assert self._hepsi(hoca) == (True, True, True)


# ============================================================ Md. 19 bedel iki adımdır (25.09.2026)


class TestBedelIkiAdim:
    """Kullanıcı kararı (25.09.2026): "Bedel belirlendi" kişinin açık işini SÜRDÜRÜR;
    "Bedel teslim alındı" BİTİRİR (ilişik listesinden çıkar, E5 basılabilir) ama dosya
    okul için açık kalır — "Bedelle aynısı / başka eser alındı" ile kapanana dek. Program
    tahsilat yapmaz, iki adımı yalnız kaydeder."""

    def test_bedel_belirlendi_kisinin_acik_isi_surer(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        ogr = ogrenci()
        dosya = loss_damage.report_lost(copy=odunc_ver(uye(ogr)).copy)
        loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("80"))

        assert tazele_dosya(dosya).is_person_open_work
        assert _her_yerde(ogr) == (True, True, True)  # E5 basılmaz
        assert persons.open_obligations(ogr) == ["1 çözülmemiş kayıp/hasar dosyası var."]

    def test_bedel_teslim_alindi_kisinin_isi_biter_dosya_okul_icin_acik_kalir(self) -> None:
        from apps.kutuphane import selectors_ilisik, selectors_teslim

        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        ogr = ogrenci()
        dosya = _bedel_teslim_alinmis(loss_damage.report_lost(copy=odunc_ver(uye(ogr)).copy))

        # Kişi: açık işi yok — kayıt defteri, ilişik listesi, toplu soru ve E5 aynı sonucu verir.
        assert not dosya.is_person_open_work
        assert _her_yerde(ogr) == (False, False, False)  # E5 basılabilir
        assert persons.open_obligations(ogr) == []
        assert selectors_ilisik.clearance_counts().open_cases == 0
        # Okul: dosya AÇIK — tek açık dosya, "Çözülmemiş dosyalar" süzgeci, nüsha "Kayıp".
        assert dosya.is_open and dosya.resolved_at is None
        assert selectors_teslim.open_case_for_copy(dosya.copy_id) == dosya
        assert list(selectors_teslim.loss_damage_cases(open_only=True)) == [dosya]
        assert tazele_nusha(dosya.copy).status == CopyStatus.LOST
        with pytest.raises(ValidationError, match="zaten kayıp"):
            loss_damage.report_lost(copy=dosya.copy)
        # Yalnız iki kapanış yolu; sorumlu notu açık dosyada düzeltilebilir.
        with pytest.raises(ValidationError, match="seçilemez"):
            loss_damage.resolve_case(dosya, resolution=R.FOUND_RETURNED)
        loss_damage.update_case_note(dosya, responsible_note="Düzeltilmiş not.")

        loss_damage.resolve_case(dosya, resolution=R.CLOSED_SAME_REPURCHASED)

        dosya = tazele_dosya(dosya)
        assert not dosya.is_open
        assert list(selectors_teslim.loss_damage_cases(open_only=True)) == []
        assert _her_yerde(ogr) == (False, False, False)

    def test_ogretmene_teslimden_dogan_dosyada_da_ayni_kural(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        hoca = ogretmen()
        kitap = odunc_nushasi()
        teslim_et([kitap], personnel=hoca)
        dosya = loss_damage.report_lost(copy=tazele_nusha(kitap))
        loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("40"))
        assert _her_yerde(hoca) == (True, True, True)

        loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)

        assert _her_yerde(hoca) == (False, False, False)
        assert tazele_dosya(dosya).is_open

    def test_sube_teslimi_dosyasi_bedel_teslim_alininca_subenin_acik_isi_degildir(self) -> None:
        from apps.kutuphane import selectors_ilisik, selectors_teslim

        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        sinif = sube()
        teslim = teslim_et([odunc_nushasi()], section=sinif).deliveries[0]
        dosya = loss_damage.report_lost(copy=teslim.copy)
        loss_damage.resolve_case(dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("40"))
        assert selectors_teslim.open_cases_for_section(sinif).count() == 1
        assert deliveries.section_delete_obstacles(sinif) != []

        loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)

        assert selectors_teslim.open_cases_for_section(sinif).count() == 0
        assert deliveries.section_delete_obstacles(sinif) == []
        assert all(s.section.pk != sinif.pk for s in selectors_ilisik.section_delivery_rows())
        assert tazele_dosya(dosya).is_open

    @pytest.mark.parametrize("kademe", [SchoolLevel.ILKOKUL, SchoolLevel.ORTAOKUL])
    def test_ilkokul_ve_ortaokulda_iki_adim_da_yoktur(self, kademe: str) -> None:
        kademe_yaz(kademe)
        for dosya in (_kayip_dosyasi(), loss_damage.open_damage_case(copy=odunc_nushasi())):
            secenekler = loss_damage.allowed_resolutions(dosya)
            assert R.PRICE_DETERMINED not in secenekler and R.PRICE_RECEIVED not in secenekler
            with pytest.raises(ValidationError, match="yalnız ortaöğretim"):
                loss_damage.resolve_case(
                    dosya, resolution=R.PRICE_DETERMINED, market_price=Decimal("40")
                )
            with pytest.raises(ValidationError, match="yalnız ortaöğretim"):
                loss_damage.resolve_case(dosya, resolution=R.PRICE_RECEIVED)
            assert tazele_dosya(dosya).resolution == R.PENDING

    def test_db_kisitlari_adim_zamanlarini_durumla_tutarli_tutar(self) -> None:
        dosya = _kayip_dosyasi()
        simdi = dosya.created_at
        dosyalar = LossDamageCase.objects.filter(pk=dosya.pk)
        # Teslim zamanı yalnız bedeli teslim alınmış yolda.
        with pytest.raises(IntegrityError), transaction.atomic():
            dosyalar.update(price_received_at=simdi)
        # Bedel ve belirlendiği zaman birlikte.
        with pytest.raises(IntegrityError), transaction.atomic():
            dosyalar.update(market_price=Decimal("5"))
        # "Bedel teslim alındı"nın zamanı zorunludur.
        with pytest.raises(IntegrityError), transaction.atomic():
            dosyalar.update(
                resolution=R.PRICE_RECEIVED, market_price=Decimal("5"), price_determined_at=simdi
            )


# ============================================================ hasar ve onarım (D3)


class TestHasarVeOnarim:
    def test_iadesi_alinmis_odunc_icin_hasar_dosyasi_ve_onarima_gonderme(self) -> None:
        uyelik = uye()
        loan = odunc_ver(uyelik)
        from apps.kutuphane.services import circulation

        circulation.return_copy(copy=loan.copy)
        loan.refresh_from_db()

        dosya = loss_damage.open_damage_case(copy=loan.copy, loan=loan, send_to_repair=True)

        assert dosya.case_type == CaseType.DAMAGED and dosya.membership_id == uyelik.pk
        assert tazele_nusha(loan.copy).status == CopyStatus.IN_REPAIR
        onarim = CopyRepair.objects.get(copy=loan.copy)
        assert onarim.case_id == dosya.pk and onarim.is_open

        loss_damage.resolve_case(dosya, resolution=R.REPAIRED)

        onarim.refresh_from_db()
        assert onarim.returned_on is not None
        assert tazele_nusha(loan.copy).status == CopyStatus.AVAILABLE
        assert not tazele_dosya(dosya).is_open

    def test_oduncteki_ve_teslimdeki_nushaya_hasar_dosyasi_acilmaz(self) -> None:
        loan = odunc_ver(uye())
        with pytest.raises(ValidationError, match="önce iade alın"):
            loss_damage.open_damage_case(copy=loan.copy)
        teslim = teslim_et([odunc_nushasi()]).deliveries[0]
        with pytest.raises(ValidationError, match="önce geri alın"):
            loss_damage.open_damage_case(copy=teslim.copy)

    def test_geri_alinan_teslim_icin_hasar_dosyasi(self) -> None:
        hoca = ogretmen()
        teslim = teslim_et([odunc_nushasi()], personnel=hoca).deliveries[0]
        deliveries.take_back(teslim.copy)
        with pytest.raises(ValidationError, match="bu nüshaya ait değil"):
            loss_damage.open_damage_case(copy=odunc_nushasi(), delivery=tazele_teslim(teslim))
        dosya = loss_damage.open_damage_case(copy=teslim.copy, delivery=tazele_teslim(teslim))
        assert persons.open_obligations(hoca) == ["1 çözülmemiş kayıp/hasar dosyası var."]
        assert dosya.delivery_id == teslim.pk

    def test_hasar_dosyasi_nushayi_dolasimdan_cikarmaz(self) -> None:
        kitap = odunc_nushasi()
        loss_damage.open_damage_case(copy=kitap, responsible_note="Kapak yırtık.")
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE
        odunc_ver(uye(), tazele_nusha(kitap))

    def test_onarima_gonder_ve_onarimdan_don(self) -> None:
        kitap = odunc_nushasi()
        kayit = loss_damage.send_to_repair(kitap)
        assert tazele_nusha(kitap).status == CopyStatus.IN_REPAIR and kayit.case_id is None
        with pytest.raises(ValidationError, match="raftaki nüsha"):
            loss_damage.send_to_repair(kitap)
        with pytest.raises(ValidationError, match="Onarımdaki nüsha için kayıp"):
            loss_damage.report_lost(copy=kitap)

        donen = loss_damage.return_from_repair(kitap)

        assert donen is not None and donen.returned_on is not None
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE
        with pytest.raises(ValidationError, match="onarımda değil"):
            loss_damage.return_from_repair(kitap)

    def test_onarimdan_donus_hasar_dosyasini_kendiliginden_kapatmaz(self) -> None:
        kitap = odunc_nushasi()
        dosya = loss_damage.open_damage_case(copy=kitap)
        kayit = loss_damage.send_to_repair(kitap)
        assert kayit.case_id == dosya.pk  # açık hasar dosyasına bağlandı

        loss_damage.return_from_repair(kitap)

        assert tazele_dosya(dosya).is_open
        loss_damage.resolve_case(dosya, resolution=R.REPAIRED)
        assert not tazele_dosya(dosya).is_open

    def test_onarimdaki_nusha_teslim_ve_odunc_verilmez(self) -> None:
        kitap = odunc_nushasi()
        loss_damage.send_to_repair(kitap)
        with pytest.raises(ValidationError):
            teslim_et([kitap])
        assert tazele_nusha(kitap).is_loanable is False

    def test_bulundu_yalniz_kayipta_onarildi_yalniz_hasarda(self) -> None:
        hasar = loss_damage.open_damage_case(copy=odunc_nushasi())
        kayip = _kayip_dosyasi()
        assert R.FOUND_RETURNED not in loss_damage.allowed_resolutions(hasar)
        assert R.REPAIRED not in loss_damage.allowed_resolutions(kayip)
        with pytest.raises(ValidationError, match="seçilemez"):
            loss_damage.resolve_case(hasar, resolution=R.FOUND_RETURNED)
        with pytest.raises(IntegrityError):
            LossDamageCase.objects.filter(pk=kayip.pk).update(
                resolution=R.REPAIRED, resolved_at=kayip.created_at
            )


# ============================================================ kip, şifreleme, yükümlülük


class TestKipVeSifreleme:
    def test_dosya_islemleri_gorevli_kipinde_yapilamaz(self) -> None:
        kitap = odunc_nushasi()
        dosya = loss_damage.open_damage_case(copy=odunc_nushasi())
        KIP.gorevliye_gec()
        with pytest.raises(KipYetkisiz):
            loss_damage.report_lost(copy=kitap)
        with pytest.raises(KipYetkisiz):
            loss_damage.resolve_case(dosya, resolution=R.REPAIRED)
        with pytest.raises(KipYetkisiz):
            loss_damage.send_to_repair(kitap)

    def test_sorumlu_notu_veritabaninda_sifreli_durur(self) -> None:
        dosya = loss_damage.open_damage_case(
            copy=odunc_nushasi(), responsible_note="Denemesorumluadı veli toplantısında"
        )
        with connection.cursor() as imlec:
            imlec.execute(
                "SELECT responsible_note FROM kutuphane_lossdamagecase WHERE id = %s", [dosya.pk]
            )
            ham = imlec.fetchone()[0]
        assert "Denemesorumluadı" not in ham
        assert tazele_dosya(dosya).responsible_note == "Denemesorumluadı veli toplantısında"

    def test_sorumlu_notu_ust_siniri(self) -> None:
        with pytest.raises(ValidationError, match="en çok 500"):
            loss_damage.open_damage_case(copy=odunc_nushasi(), responsible_note="x" * 501)

    def test_cozulmus_dosya_yukumluluk_degildir_uyelik_silinemez(self) -> None:
        uyelik = uye(ogrenci())
        dosya = loss_damage.report_lost(copy=odunc_nushasi(), membership=uyelik)
        assert persons.open_obligations(uyelik.person) != []
        loss_damage.resolve_case(dosya, resolution=R.REPLACED_SAME)

        assert persons.open_obligations(uyelik.person) == []
        with pytest.raises(ValidationError, match="Kayıp/hasar dosyası olan üyelik"):
            memberships.delete_membership(uyelik)

    def test_not_duzeltme_yalniz_acik_dosyada(self) -> None:
        dosya = loss_damage.open_damage_case(copy=odunc_nushasi())
        loss_damage.update_case_note(dosya, responsible_note="Düzeltilmiş not.")
        assert tazele_dosya(dosya).responsible_note == "Düzeltilmiş not."
        loss_damage.resolve_case(dosya, resolution=R.REPAIRED)
        with pytest.raises(ValidationError, match="zaten kapanmış"):
            loss_damage.update_case_note(dosya, responsible_note="x")


def test_ilisik_icin_toplu_sorular_acik_teslim_ve_dosyasi_olanlari_verir() -> None:
    """İlişik listesinin (sonraki kol) kişi anahtarları: açık teslim ve çözülmemiş dosya."""
    from apps.kutuphane import selectors_teslim

    hoca = ogretmen()
    teslim_et([odunc_nushasi()], personnel=hoca)
    teslim_et([odunc_nushasi()])  # şube teslimi: kişisiz
    ogr = ogrenci()
    acik = loss_damage.report_lost(copy=odunc_ver(uye(ogr)).copy)
    kapali = loss_damage.report_lost(copy=odunc_ver(uye(ogrenci())).copy)
    loss_damage.resolve_case(kapali, resolution=R.FOUND_RETURNED)

    assert selectors_teslim.persons_with_open_deliveries() == {("P", hoca.pk)}
    assert selectors_teslim.persons_with_open_cases() == {("S", ogr.pk)}
    assert acik.is_open


def test_kayip_hasar_iletilerinde_borc_ceza_tahsilat_dili_yok() -> None:
    """Sözlük: "bedel belirlendi", "bedel teslim alındı" — asla borç, ceza, zayi, zimmet (Md. 19)."""
    kaynak = inspect.getsource(loss_damage) + inspect.getsource(deliveries)
    etiketler = " ".join(str(etiket) for _, etiket in CaseResolution.choices)
    for yasak in ("borç", "ceza", "zayi", "zimmet", "tahsil"):
        assert yasak not in etiketler.casefold()
    # Kaynakta yasak sözcük yalnız "yapmaz" bağlamında (belge metni) geçebilir; iletilerde yok.
    iletiler = [
        deger
        for ad, deger in {**vars(loss_damage), **vars(deliveries)}.items()
        if ad.endswith("_MESSAGE") and isinstance(deger, str)
    ]
    assert iletiler, "ileti sabitleri bulunamadı"
    for ileti in iletiler:
        for yasak in ("borç", "ceza", "zayi", "zimmet"):
            assert yasak not in ileti.casefold(), ileti
    assert "tahsilat" in kaynak  # belge metni kuralı söyler ("program tahsilat yapmaz")
