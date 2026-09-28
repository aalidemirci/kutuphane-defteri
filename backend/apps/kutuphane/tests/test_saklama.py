"""Saklama ve anonimleştirme (F11 — tasarım §6.4 BAĞLAYICI; D13, TB16; kod kapısı §14.1 F11).

Kod kapısı maddeleri ve sınayan sınıflar:

- **§6.4'ün her satırı testli**: ayrılmış kişi (`TestAyrilmisKisi`, kullanıcı kararı 2:
  ayrılış + 2 yıl), sonlanmış üyeliğin bağları ve üyelik satırı (`TestSonlanmisUyelik`),
  aktif üyenin iade edilmiş ödünçleri (`TestIadeEdilmisOdunc`, A3), kapanmış kayıp/hasar
  dosyası (`TestKapanmisDosya`), bedel bekleyen dosya (`TestBedelBekleyen`), kapanmış
  teslim (`TestKapanmisTeslim`).
- **Açık yükümlülük varken kişi silinmez** (`TestAcikYukumluluk`).
- **Tetik öncesi `pre-anonim` yedeği ve eski `pre-migrate` silme**, tek işlem, yanlış liste
  (`TestTetik`); geri yüklemenin kenara aldığı `db-onceki-*` dosyalarından tetik anından 14
  günden eskilerinin silinmesi (27.09.2026 kullanıcı kararı — eşleri, yeniden deneme, saat
  kayması, tetik başarısızken dokunulmaması; `TestTetik`).
- **6 ay uyarısı** (`TestAltiAy`).
- **Çok okunanlar ve dondurulmuş E9 anonimleştirmeden sonra değişmez** (`TestDondurulmus`).
- **Anonimleştirme sonrası yeniden basımda ibare** ve belge izi (`TestIbareVeBelgeIzi`).
- Gün değişimi kapısındaki tarama (`TestGunlukTarama`).

Bütün kişi verileri UYDURMADIR ("Deneme …"). Gün `plan_hesapla(bugun=…)` ve
`tetikle(bugun=…)` ile verilir; kayıtların tarihleri güncellemeyle geçmişe çekilir.
"""

from __future__ import annotations

import hashlib
import io
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader

from apps.kutuphane import belge_izi, selectors_teslim, teslim_belgeleri
from apps.kutuphane.models import (
    AnnualLibraryReview,
    BelgeIzi,
    BelgeTuru,
    CardlessReason,
    CardRevocation,
    CaseResolution,
    Delivery,
    IssuedCard,
    KatalogPopuler,
    Loan,
    LossDamageCase,
    Membership,
    OverrideReason,
    PopulerPencereTuru,
    RetentionRun,
    RetentionState,
    TerminationReason,
)
from apps.kutuphane.services import (
    annual_review,
    circulation,
    deliveries,
    loss_damage,
    memberships,
    populer,
    saklama,
)
from apps.kutuphane.tests.dolasim_ortak import (
    ders_yili,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    politika,
    uye,
)
from apps.kutuphane.tests.teslim_ortak import kademe_yaz, ogretmen, sube, teslim_et
from apps.okul import masaustu_kanca
from apps.okul.models import Personnel, SchoolLevel, Student
from apps.okul.services import app_password, backup_restore, persons
from katalog.bakim import BakimKapisi

pytestmark = pytest.mark.django_db

#: `bugun` fikstürünün günü (dolasim_ortak.ACIK_GUN) — kayıtlar bu gün açılır.
GUN = date(2026, 9, 24)
IKI_YIL_SONRA = date(2028, 9, 24)


def _an(gun: date, saat: int = 10) -> datetime:
    return timezone.make_aware(datetime.combine(gun, time(saat, 0)))


def _tetikle(gun: date) -> saklama.TetikSonucu:
    plan = saklama.plan_hesapla(gun)
    return saklama.tetikle(anahtar=plan.anahtar, bugun=gun)


def _iade_edilmis(uyelik: Membership, gun: date = GUN, **alanlar: object) -> Loan:
    """Servis yoluyla ödünç verip iade alır; iade anını `gun`e çeker."""
    loan = odunc_ver(uyelik, **alanlar)
    circulation.return_loan(loan=loan)
    Loan.objects.filter(pk=loan.pk).update(returned_at=_an(gun))
    guncel: Loan = Loan.all_objects.get(pk=loan.pk)
    return guncel


def _kayip_dosyasi_kapali(uyelik: Membership, gun: date = GUN) -> LossDamageCase:
    """Ödünçteki kitap kayıp bildirilir, sonra "Bulundu" ile kapanır (kapanış `gun`)."""
    loan = odunc_ver(uyelik)
    dosya = loss_damage.report_lost(copy=loan.copy, responsible_note="Deneme sorumlu notu")
    dosya = loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
    LossDamageCase.objects.filter(pk=dosya.pk).update(resolved_at=_an(gun))
    Loan.all_objects.filter(pk=loan.pk).update(lost_at=_an(gun))
    kapali: LossDamageCase = LossDamageCase.all_objects.get(pk=dosya.pk)
    return kapali


def _ayril(kisi: Student | Personnel) -> None:
    if isinstance(kisi, Student):
        persons.leave_student(kisi)
    else:
        persons.leave_personnel(kisi)


def _onceki(dizin: Path, an: datetime) -> Path:
    """Geri yüklemenin kenara aldığı adla (`backup_restore._swap_database_files`) önceki
    veritabanı ve `-wal`/`-shm` eşleri; adın damgası `an`ın yerel saatidir."""
    damga = timezone.localtime(an).strftime(backup_restore.OLD_DB_STAMP_FORMAT)
    yol = dizin / f"{backup_restore.OLD_DB_PREFIX}-{damga}.sqlite3"
    yol.write_bytes(b"onceki")
    for ek in ("-wal", "-shm"):
        yol.with_name(yol.name + ek).write_bytes(b"es")
    return yol


def _ailesi(yol: Path) -> list[str]:
    """Önceki veritabanı ve eşlerinin klasörde kalan adları."""
    return sorted(p.name for p in yol.parent.glob(yol.name + "*"))


# ============================================================ §6.4 satır 1 — ayrılmış kişi


class TestAyrilmisKisi:
    def test_hic_uye_olmamis_ayrilan_ogrenci_iki_yil_sonra_aday_olur_ve_silinir(
        self, bugun: list[date]
    ) -> None:
        kisi = ogrenci()
        _ayril(kisi)

        assert kisi.pk not in saklama.plan_hesapla(date(2028, 9, 23)).students
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert kisi.pk in plan.students

        _tetikle(IKI_YIL_SONRA)
        assert not Student.all_objects.filter(pk=kisi.pk).exists()

    def test_aktif_kisi_hic_aday_olmaz(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        assert kisi.pk not in saklama.plan_hesapla(date(2040, 1, 1)).students

    def test_sure_politikadan_okunur(self, bugun: list[date]) -> None:
        politika(retention_years_left_person=3)
        kisi = ogrenci()
        _ayril(kisi)
        assert kisi.pk not in saklama.plan_hesapla(IKI_YIL_SONRA).students
        assert kisi.pk in saklama.plan_hesapla(date(2029, 9, 24)).students

    def test_ayrilan_personel_silinir(self, bugun: list[date]) -> None:
        kisi = ogretmen()
        _ayril(kisi)
        _tetikle(IKI_YIL_SONRA)
        assert not Personnel.all_objects.filter(pk=kisi.pk).exists()


# ============================================================ §6.4 satır 2-3 — sonlanmış üyelik


class TestSonlanmisUyelik:
    def test_bag_ve_gerekceler_temizlenir_uyelik_ve_kisi_silinir(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        loan = _iade_edilmis(uyelik, cardless_reason=CardlessReason.CARD_NOT_WITH_MEMBER)
        # Gerekçeli istisna (şifreli çift) doğrudan yazılır: kurgusu dolaşım testlerindedir.
        Loan.objects.filter(pk=loan.pk).update(
            override_reason=OverrideReason.OTHER, override_note="Deneme açıklama"
        )
        dosya = _kayip_dosyasi_kapali(uyelik)
        kart_indeksi = uyelik.card_no_index
        _ayril(kisi)  # üyelik "Okuldan ayrıldı" ile sonlanır

        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert loan.pk in plan.loans_terminated
        assert dosya.pk in plan.cases_terminated
        assert uyelik.pk in plan.memberships
        assert kisi.pk in plan.students

        _tetikle(IKI_YIL_SONRA)

        loan = Loan.all_objects.get(pk=loan.pk)
        assert loan.membership_id is None
        assert (loan.override_reason, loan.override_note, loan.cardless_reason) == ("", "", "")
        assert loan.cardless is True  # kişisiz işaret kalır
        assert loan.anonymized_at is not None
        dosya = LossDamageCase.all_objects.get(pk=dosya.pk)
        assert dosya.membership_id is None
        assert dosya.responsible_note == ""
        assert dosya.anonymized_at is not None
        assert not Membership.all_objects.filter(pk=uyelik.pk).exists()
        assert not Student.all_objects.filter(pk=kisi.pk).exists()
        # Kart no asla yeniden verilmez; okutulursa "iptal edilmiş kart" denir.
        assert IssuedCard.objects.filter(card_no_index=kart_indeksi).exists()
        assert CardRevocation.objects.filter(card_no_index=kart_indeksi).exists()

    def test_sure_dolmadan_dokunulmaz(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        loan = _iade_edilmis(uyelik)
        memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)
        plan = saklama.plan_hesapla(date(2028, 9, 23))
        assert loan.pk not in plan.loans_terminated
        assert uyelik.pk not in plan.memberships

    def test_aktif_ogrencinin_sonlanmis_uyeligi_silinir_kisi_kalir(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        _iade_edilmis(uyelik)
        memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)

        _tetikle(IKI_YIL_SONRA)

        assert not Membership.all_objects.filter(pk=uyelik.pk).exists()
        assert Student.objects.filter(pk=kisi.pk).exists()

    def test_onizleme_adlari_kisi_ve_yalniz_uyelik_kapsamini_ayirir(
        self, bugun: list[date]
    ) -> None:
        """ "Silinecek kişileri göster": kişi kaydı silinecekler önce, sonra kişi kaydı kalıp
        yalnız sona ermiş üyelik kaydı silinecekler; ayrılan kişinin üyeliği ikinci kez
        listelenmez. Liste tetikle aynı plandan gelir."""
        ayrilan = ogrenci(first_name="Zerrin", last_name="Deneme")
        uye(ayrilan)
        _ayril(ayrilan)
        suren = ogrenci(first_name="Ahmet", last_name="Deneme")
        uyelik = uye(suren)
        memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)
        ogretmen_kisi = ogretmen()
        ogretmen_uyeligi = uye(ogretmen_kisi)
        memberships.terminate_membership(ogretmen_uyeligi, reason=TerminationReason.MEMBER_REQUEST)

        satirlar = saklama.silinecek_kisiler(IKI_YIL_SONRA)

        assert [(s.full_name, s.scope) for s in satirlar[:1]] == [
            ("Zerrin Deneme", saklama.KAPSAM_KISI)
        ]
        assert satirlar[0].left_at == GUN and satirlar[0].terminated_at is None
        uyelikler = [s for s in satirlar if s.scope == saklama.KAPSAM_UYELIK]
        assert {(s.kind, s.person_id) for s in uyelikler} == {
            ("student", suren.pk),
            ("personnel", ogretmen_kisi.pk),
        }
        assert all(s.terminated_at == GUN for s in uyelikler)
        assert sum(1 for s in satirlar if (s.kind, s.person_id) == ("student", ayrilan.pk)) == 1
        # Önizlemedeki üyelik sahibi tetikte yalnız üyeliğini yitirir.
        _tetikle(IKI_YIL_SONRA)
        assert Student.objects.filter(pk=suren.pk).exists()
        assert not Membership.all_objects.filter(pk=uyelik.pk).exists()


# ============================================================ §6.4 satır 4 — A3


class TestIadeEdilmisOdunc:
    def test_ders_yili_sonu_arti_bir_yil(self, bugun: list[date]) -> None:
        ders_yili()  # 07.09.2026 - 25.06.2027
        uyelik = uye()
        loan = _iade_edilmis(uyelik)

        assert loan.pk not in saklama.plan_hesapla(date(2028, 6, 24)).loans
        plan = saklama.plan_hesapla(date(2028, 6, 25))
        assert loan.pk in plan.loans_returned

        _tetikle(date(2028, 6, 25))
        loan = Loan.all_objects.get(pk=loan.pk)
        assert loan.membership_id is None and loan.anonymized_at is not None
        # Aktif üyelik kalır; yalnız ödüncün bağı koptu.
        assert Membership.objects.get(pk=uyelik.pk).is_active

    def test_acik_odunce_dokunulmaz(self, bugun: list[date]) -> None:
        loan = odunc_ver(uye())
        assert loan.pk not in saklama.plan_hesapla(date(2040, 1, 1)).loans

    def test_ders_yili_sonu_kurali(self) -> None:
        yillar = [(date(2026, 9, 7), date(2027, 6, 25)), (date(2027, 9, 13), date(2028, 6, 23))]
        assert saklama.ders_yili_sonu(date(2027, 3, 1), yillar) == date(2027, 6, 25)
        # Yaz arası: bir sonraki ders yılının bitişi.
        assert saklama.ders_yili_sonu(date(2027, 7, 10), yillar) == date(2028, 6, 23)
        # Ders yılı yok: izleyen 30 Haziran.
        assert saklama.ders_yili_sonu(date(2029, 3, 1), yillar) == date(2029, 6, 30)
        assert saklama.ders_yili_sonu(date(2029, 8, 1), yillar) == date(2030, 6, 30)

    def test_tarih_yardimcilari(self) -> None:
        assert saklama.yil_ekle(date(2024, 2, 29), 2) == date(2026, 2, 28)
        assert saklama.ay_ekle(date(2026, 8, 31), 6) == date(2027, 2, 28)
        assert saklama.ay_ekle(date(2026, 9, 24), 6) == date(2027, 3, 24)


# ============================================================ §6.4 satır 5 — kapanmış dosya


class TestKapanmisDosya:
    def test_aktif_uyenin_kapanmis_dosyasi_kapanis_arti_iki_yil(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        dosya = _kayip_dosyasi_kapali(uyelik)
        assert dosya.pk not in saklama.plan_hesapla(date(2028, 9, 23)).cases
        assert dosya.pk in saklama.plan_hesapla(IKI_YIL_SONRA).cases_closed

        _tetikle(IKI_YIL_SONRA)
        dosya = LossDamageCase.all_objects.get(pk=dosya.pk)
        assert dosya.membership_id is None and dosya.responsible_note == ""
        assert selectors_teslim.case_person(dosya) is None
        assert not LossDamageCase.all_objects.filter(selectors_teslim.person_case_q(kisi)).exists()

    def test_anonim_dosya_teslim_bagi_uzerinden_ogretmene_yazilmaz(self, bugun: list[date]) -> None:
        """Öğretmene teslim edilen kitabı öğrenci kaybetti (F10 düzeltme turu 15 kurgusu)."""
        politika(retention_years_closed_deliveries=5)
        hoca = ogretmen()
        uyelik = uye(ogrenci())
        (kitap,) = [odunc_nushasi()]
        teslim_et([kitap], personnel=hoca)
        dosya = loss_damage.report_lost(copy=kitap, membership=uyelik)
        dosya = loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
        LossDamageCase.objects.filter(pk=dosya.pk).update(resolved_at=_an(GUN))

        _tetikle(IKI_YIL_SONRA)

        dosya = LossDamageCase.all_objects.select_related("delivery").get(pk=dosya.pk)
        assert dosya.anonymized_at is not None
        assert dosya.delivery is not None and dosya.delivery.personnel_id == hoca.pk
        assert not LossDamageCase.all_objects.filter(selectors_teslim.person_case_q(hoca)).exists()
        assert selectors_teslim.case_person(dosya) is None

    def test_acik_dosyaya_dokunulmaz(self, bugun: list[date]) -> None:
        loan = odunc_ver(uye())
        dosya = loss_damage.report_lost(copy=loan.copy)
        assert dosya.pk not in saklama.plan_hesapla(date(2040, 1, 1)).cases


# ============================================================ §6.4 satır 6 — bedel bekleyen


class TestBedelBekleyen:
    def _bedeli_teslim_alinmis(self, uyelik: Membership) -> LossDamageCase:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        loan = odunc_ver(uyelik)
        dosya = loss_damage.report_lost(copy=loan.copy)
        dosya = loss_damage.resolve_case(
            dosya, resolution=CaseResolution.PRICE_DETERMINED, market_price=Decimal("120.00")
        )
        dosya = loss_damage.resolve_case(dosya, resolution=CaseResolution.PRICE_RECEIVED)
        LossDamageCase.objects.filter(pk=dosya.pk).update(
            price_determined_at=_an(GUN), price_received_at=_an(GUN)
        )
        bekleyen: LossDamageCase = LossDamageCase.all_objects.get(pk=dosya.pk)
        return bekleyen

    def test_yillik_listeye_duser_sessizce_silinmez(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        dosya = self._bedeli_teslim_alinmis(uyelik)
        _ayril(kisi)

        assert [s.case_id for s in saklama.bedel_hatirlatmalari(date(2027, 9, 23))] == []
        satirlar = saklama.bedel_hatirlatmalari(date(2027, 9, 24))
        assert [s.case_id for s in satirlar] == [dosya.pk]
        assert satirlar[0].years_waiting == 1
        assert saklama.pano_ozeti(date(2027, 9, 24))["price_reminders"] == 1

        uzak = date(2035, 1, 1)
        plan = saklama.plan_hesapla(uzak)
        assert dosya.pk not in plan.cases
        assert uyelik.pk not in plan.memberships
        assert kisi.pk not in plan.students
        assert plan.persons_held >= 1


# ============================================================ §6.4 satır 7 — kapanmış teslim


class TestKapanmisTeslim:
    def test_ogretmen_bagi_acik_guncellemeyle_koparilir_sube_kalir(self, bugun: list[date]) -> None:
        hoca = ogretmen()
        kitap, sinif_kitabi = odunc_nushasi(title="Bir"), odunc_nushasi(title="İki")
        teslim_et([kitap], personnel=hoca)
        teslim_et([sinif_kitabi], section=sube())
        deliveries.take_back(kitap)
        deliveries.take_back(sinif_kitabi)
        Delivery.objects.update(returned_at=_an(GUN))
        ogretmen_teslimi = Delivery.objects.get(copy=kitap)
        sube_teslimi = Delivery.objects.get(copy=sinif_kitabi)
        _ayril(hoca)

        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert plan.deliveries == frozenset({ogretmen_teslimi.pk})
        assert hoca.pk in plan.personnel

        _tetikle(IKI_YIL_SONRA)

        ogretmen_teslimi = Delivery.all_objects.get(pk=ogretmen_teslimi.pk)
        assert ogretmen_teslimi.personnel_id is None
        assert ogretmen_teslimi.anonymized_at is not None
        assert ogretmen_teslimi.recipient_kind == "TEACHER"  # tür kişisizdir, kalır
        sube_teslimi = Delivery.all_objects.get(pk=sube_teslimi.pk)
        assert sube_teslimi.section_id is not None and sube_teslimi.anonymized_at is None
        assert not Personnel.all_objects.filter(pk=hoca.pk).exists()

    def test_kisiyi_tesliminden_bulan_dosya_varken_bag_koparilmaz(self, bugun: list[date]) -> None:
        politika(retention_years_closed_cases=4)
        hoca = ogretmen()
        kitap = odunc_nushasi()
        teslim_et([kitap], personnel=hoca)
        dosya = loss_damage.report_lost(copy=kitap)  # üyeliksiz: kişi teslim alandır
        teslim = Delivery.all_objects.get(copy=kitap)
        Delivery.all_objects.filter(pk=teslim.pk).update(lost_at=_an(GUN))
        _ayril(hoca)

        # Dosya açıkken ne teslim bağı ne kişi.
        plan = saklama.plan_hesapla(date(2035, 1, 1))
        assert teslim.pk not in plan.deliveries
        assert hoca.pk not in plan.personnel

        dosya = loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
        LossDamageCase.objects.filter(pk=dosya.pk).update(resolved_at=_an(GUN))
        # Dosyanın süresi (4 yıl) dolmadan teslimin süresi (2 yıl) dolsa da bağ kalır.
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert teslim.pk not in plan.deliveries
        # Dosyanın süresi dolunca ikisi birlikte.
        plan = saklama.plan_hesapla(date(2030, 9, 24))
        assert dosya.pk in plan.cases_closed and teslim.pk in plan.deliveries
        assert hoca.pk in plan.personnel

    def test_ogretmen_teslimi_belge_no_duzeyinde_birlikte_koparilir(
        self, bugun: list[date]
    ) -> None:
        """F11 düzeltme turu: aynı belge no'nun bir satırı öğretmene bağlı kalırken öbürü
        koparılsa anonim satır belge no üzerinden öğretmene yeniden bağlanır ve ibareli
        E15 öğretmenin adını basardı (KVKK 3/1-b). Belgenin bütün satırları birlikte bekler."""
        hoca = ogretmen(last_name="Teslimalan")
        a, b = odunc_nushasi(title="Bir"), odunc_nushasi(title="İki")
        toplu = teslim_et([a, b], personnel=hoca)
        deliveries.take_back(a)
        Delivery.objects.filter(copy=a).update(returned_at=_an(GUN))
        deliveries.take_back(b)
        Delivery.objects.filter(copy=b).update(returned_at=_an(date(2027, 9, 24)))
        birinci = Delivery.all_objects.get(copy=a)
        ikinci = Delivery.all_objects.get(copy=b)

        # Birincinin süresi doldu, ikincininki dolmadı: belge bekler, hiçbir satır koparılmaz.
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert birinci.pk not in plan.deliveries and ikinci.pk not in plan.deliveries

        # Sonuncunun süresi dolunca belgenin bütün satırları birlikte koparılır.
        son_gun = date(2029, 9, 24)
        assert {birinci.pk, ikinci.pk} <= saklama.plan_hesapla(son_gun).deliveries
        _tetikle(son_gun)
        assert not Delivery.all_objects.filter(
            document_no=toplu.document_no, personnel__isnull=False
        ).exists()
        satirlar = teslim_belgeleri.delivery_list_rows(document_no=toplu.document_no)
        liste = teslim_belgeleri.delivery_list_context(satirlar)
        dokum = teslim_belgeleri.take_back_context(satirlar, document_no=toplu.document_no)
        assert liste["anonim_kopya_ibaresi"] == belge_izi.ANONIM_KOPYA_IBARESI
        assert "Teslimalan" not in str(liste) and "Teslimalan" not in str(dokum)

    def test_acik_satiri_olan_belge_hic_koparilmaz(self, bugun: list[date]) -> None:
        """Belgenin bir satırı hâlâ teslimdeyse (ya da kayba dönüşüp açık dosyaya
        bağlıysa) geri alınmış satırların da bağı kalır."""
        hoca = ogretmen()
        a, b = odunc_nushasi(title="Bir"), odunc_nushasi(title="İki")
        teslim_et([a, b], personnel=hoca)
        deliveries.take_back(a)
        Delivery.objects.filter(copy=a).update(returned_at=_an(GUN))
        geri_alinan = Delivery.all_objects.get(copy=a)

        assert geri_alinan.pk not in saklama.plan_hesapla(date(2040, 1, 1)).deliveries

        loss_damage.report_lost(copy=b)  # sınıf setinden bir kitap kayboldu: dosya açık
        assert geri_alinan.pk not in saklama.plan_hesapla(date(2040, 1, 1)).deliveries

    def test_kisisini_tesliminden_bulan_dosya_teslimle_birlikte_bekler(
        self, bugun: list[date]
    ) -> None:
        """Dosyanın süresi teslimin belgesinden önce dolsa da dosya bekler: yoksa
        anonimleştirilmiş tutanağın "Teslim — belge no" satırı öğretmene yeniden bağlanırdı."""
        politika(retention_years_closed_deliveries=5)
        hoca = ogretmen()
        kitap = odunc_nushasi()
        teslim_et([kitap], personnel=hoca)
        dosya = loss_damage.report_lost(copy=kitap)  # üyeliksiz: kişi teslim alandır
        dosya = loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
        LossDamageCase.objects.filter(pk=dosya.pk).update(resolved_at=_an(GUN))
        Delivery.all_objects.filter(copy=kitap).update(lost_at=_an(GUN))
        teslim = Delivery.all_objects.get(copy=kitap)

        plan = saklama.plan_hesapla(IKI_YIL_SONRA)  # dosyanın süresi doldu, teslimin dolmadı
        assert dosya.pk not in plan.cases and teslim.pk not in plan.deliveries

        plan = saklama.plan_hesapla(date(2031, 9, 24))
        assert dosya.pk in plan.cases_closed and teslim.pk in plan.deliveries


# ============================================================ açık yükümlülük (kod kapısı)


class TestAcikYukumluluk:
    def test_acik_oduncu_olan_ayrilmis_kisi_silinmez(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        odunc_ver(uyelik)
        _ayril(kisi)
        plan = saklama.plan_hesapla(date(2040, 1, 1))
        assert kisi.pk not in plan.students
        assert uyelik.pk not in plan.memberships

    def test_acik_teslimi_olan_ayrilmis_ogretmen_silinmez(self, bugun: list[date]) -> None:
        hoca = ogretmen()
        teslim_et([odunc_nushasi()], personnel=hoca)
        _ayril(hoca)
        assert hoca.pk not in saklama.plan_hesapla(date(2040, 1, 1)).personnel

    def test_acik_kayip_dosyasi_olan_ayrilmis_kisi_silinmez(self, bugun: list[date]) -> None:
        """Çözüm bekleyen dosya (bedel adımına gelmemiş): kişi ve üyelik kalır, dosyanın
        bağı koparılmaz; dosyaya bağlı (kayba dönüşmüş) ödüncün bağı da kalır (F11
        düzeltme turu — açık yükümlülükte bağ koparılmaz)."""
        kisi = ogrenci()
        uyelik = uye(kisi)
        loan = odunc_ver(uyelik)
        dosya = loss_damage.report_lost(copy=loan.copy)
        _ayril(kisi)

        plan = saklama.plan_hesapla(date(2040, 1, 1))

        assert dosya.pk not in plan.cases
        assert loan.pk not in plan.loans
        assert uyelik.pk not in plan.memberships
        assert kisi.pk not in plan.students
        assert plan.persons_held >= 1
        assert plan.bos  # tetiklenecek bir şey yok
        assert Student.all_objects.filter(pk=kisi.pk).exists()
        assert LossDamageCase.all_objects.get(pk=dosya.pk).membership_id == uyelik.pk

    def test_acik_dosyanin_oduncu_hicbir_tarihte_koparilmaz_dosyayla_birlikte_koparilir(
        self, bugun: list[date]
    ) -> None:
        """Aktif üyenin ödünçteki kitabı kayboldu. Ödünç "Kayba dönüştü", dosya açık: A3
        süresi dolsa da ödüncün bağı kalır (ödünç → dosya.loan → dosya.membership zinciri
        onu kişiye yeniden bağlardı). Dosya kapanıp süresi dolunca ikisi birlikte."""
        ders_yili()  # 07.09.2026 - 25.06.2027
        uyelik = uye(ogrenci())
        loan = odunc_ver(uyelik)
        dosya = loss_damage.report_lost(copy=loan.copy)
        Loan.all_objects.filter(pk=loan.pk).update(lost_at=_an(GUN))

        assert loan.pk not in saklama.plan_hesapla(date(2040, 1, 1)).loans

        dosya = loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
        LossDamageCase.objects.filter(pk=dosya.pk).update(resolved_at=_an(GUN))
        # A3 doldu (25.06.2027 + 1 yıl), dosyanın süresi (kapanış + 2 yıl) dolmadı: bekler.
        assert loan.pk not in saklama.plan_hesapla(date(2028, 6, 26)).loans
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert loan.pk in plan.loans_returned and dosya.pk in plan.cases_closed

        _tetikle(IKI_YIL_SONRA)
        assert Loan.all_objects.get(pk=loan.pk).membership_id is None
        assert LossDamageCase.all_objects.get(pk=dosya.pk).membership_id is None

    def test_tetik_kisi_basina_yeniden_sorar_ve_hepsini_geri_sarar(
        self, bugun: list[date], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Savunma derinliği + tek işlem: son anda açık iş görünürse hiçbir şey değişmez."""
        kisi = ogrenci()
        uyelik = uye(kisi)
        loan = _iade_edilmis(uyelik)
        _ayril(kisi)
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        monkeypatch.setattr(persons, "open_obligations", lambda _kisi: ["1 açık ödünç var."])

        with pytest.raises(ValidationError) as hata:
            saklama.tetikle(anahtar=plan.anahtar, bugun=IKI_YIL_SONRA)

        assert saklama.ACIK_YUKUMLULUK_MESAJI in hata.value.messages
        assert Loan.all_objects.get(pk=loan.pk).membership_id == uyelik.pk
        assert Membership.all_objects.filter(pk=uyelik.pk).exists()
        assert Student.all_objects.filter(pk=kisi.pk).exists()
        assert not RetentionRun.objects.exists()


# ============================================================ tetik: yedek, pre-migrate, liste


class TestTetik:
    def _aday(self) -> Student:
        kisi = ogrenci()
        _ayril(kisi)
        return kisi

    def test_once_pre_anonim_yedegi_alinir_eski_pre_migrate_silinir(
        self, bugun: list[date]
    ) -> None:
        self._aday()
        dizin = app_password.backup_dir()
        dizin.mkdir(parents=True, exist_ok=True)
        eski = dizin / "pre-migrate-2026.1.0-2026-09-01.kdbak"
        eski.write_bytes(b"eski")
        os.utime(eski, (_an(GUN).timestamp(), _an(GUN).timestamp()))
        yeni = dizin / "pre-migrate-2099.1.0-2099-01-01.kdbak"
        yeni.write_bytes(b"yeni")
        gelecek = _an(date(2099, 1, 1)).timestamp()
        os.utime(yeni, (gelecek, gelecek))
        gunluk = dizin / "gunluk-2026-09-01.kdbak"
        gunluk.write_bytes(b"gunluk")

        sonuc = _tetikle(IKI_YIL_SONRA)

        yedek = dizin / sonuc.run.backup_name
        assert yedek.is_file() and yedek.name.startswith("pre-anonim-")
        assert yedek.read_bytes()[:5] == b"KDBAK"
        assert not eski.exists()
        assert yeni.exists() and gunluk.exists()
        assert sonuc.run.pre_migrate_removed == 1
        assert RetentionRun.objects.get().summary["students"] == 1

    def test_gunluk_tarama_yalniz_silinemeyen_adi_yeniden_dener_saat_kaymasina_dayanikli(
        self, bugun: list[date], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F11 düzeltme turu: tetikte silinemeyen yedek ADIYLA yeniden denenir. Saat sonradan
        geri kayınca tetikten SONRA alınmış güncelleme yedeğinin dosya zamanı tetik anından
        eski görünür; tarama ona dokunmaz (geri dönülecek yedek kalır)."""
        from desktop import backup

        self._aday()
        dizin = app_password.backup_dir()
        dizin.mkdir(parents=True, exist_ok=True)
        eski = dizin / "pre-migrate-2026.1.0-2026-09-01.kdbak"
        eski.write_bytes(b"eski")
        os.utime(eski, (_an(GUN).timestamp(), _an(GUN).timestamp()))
        ozgun_sil = backup.remove_pre_migrate_named
        # Tetik anında dosya silinemedi (ör. virüs tarayıcısı açık tutuyor).
        monkeypatch.setattr(backup, "remove_pre_migrate_named", lambda _d, adlar: ([], adlar))
        sonuc = _tetikle(IKI_YIL_SONRA)
        assert sonuc.run.pre_migrate_removed == 0
        assert RetentionRun.objects.get().pre_migrate_pending == [eski.name]
        monkeypatch.setattr(backup, "remove_pre_migrate_named", ozgun_sil)

        # Program güncellendi ama saat geri kaymıştı: yeni güncelleme yedeğinin dosya
        # zamanı tetik anından ESKİ görünür.
        kaymis = dizin / "pre-migrate-2028.10.0-2028-10-01.kdbak"
        kaymis.write_bytes(b"tetikten sonra")
        os.utime(kaymis, (_an(GUN).timestamp(), _an(GUN).timestamp()))

        assert saklama.gunluk_tarama(date(2028, 10, 2)) == "tamam"

        assert not eski.exists()
        assert kaymis.exists(), "tetikten sonra alınmış yedek silindi"
        run = RetentionRun.objects.get()
        assert run.pre_migrate_removed == 1 and run.pre_migrate_pending == []

    def test_onceki_veritabani_wal_ve_shm_ile_bir_sayilir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Geri yükleme kenara aldığı veritabanının -wal/-shm dosyalarını aynı ön ekle
        taşır; Saklama ekranı tek geri yüklemeyi bir "önceki veritabanı" sayar."""
        monkeypatch.setattr(saklama, "_veritabani_yolu", lambda: tmp_path / "db.sqlite3")
        kok = tmp_path / "db-onceki-2026-09-27-101010.sqlite3"
        for yol in (kok, kok.with_name(kok.name + "-wal"), kok.with_name(kok.name + "-shm")):
            yol.write_bytes(b"x")
        assert saklama._yedek_sayilari()["old_databases"] == 1
        (tmp_path / "db-onceki-2026-10-01-080000.sqlite3").write_bytes(b"x")
        assert saklama._yedek_sayilari()["old_databases"] == 2
        # İşlem şimdi uygulansa silinecekler (14 günden eskiler) ayrıca sayılır; eşler yine
        # sayılmaz. 12.10.2026 12:00'nin sınırı 28.09.2026 12:00'dır.
        an = timezone.make_aware(datetime(2026, 10, 12, 12, 0))
        sayilar = saklama._yedek_sayilari(an)
        assert (sayilar["old_databases"], sayilar["old_databases_expired"]) == (2, 1)

    def test_onceki_veritabani_tetik_anindan_14_gunden_eskisi_silinir_yenisi_kalir(
        self, bugun: list[date], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """27.09.2026 kullanıcı kararı: tetik, geri yüklemenin kenara aldığı veritabanlarından
        tetik anından 14 günden eski olanları `-wal`/`-shm` eşleriyle siler; yenisi yakın
        tarihli geri yüklemenin dönüş yolu olarak kalır. Ölçü ADDAKİ damgadır, dosya zamanı
        değil: taşınan dosya zamanını korur (eski veritabanına son yazılan an)."""
        from desktop import backup

        monkeypatch.setattr(saklama, "_veri_dizini", lambda: tmp_path)
        self._aday()
        simdi = timezone.now()
        gun = backup.DEFAULT_KEEP_DAYS
        assert gun == 14
        eski = _onceki(tmp_path, simdi - timedelta(days=gun + 1))
        yeni = _onceki(tmp_path, simdi - timedelta(days=gun - 1))
        # Yeni dosyanın zamanı iki ay öncesi (program yaz tatilinde kapalıydı, sonra geri
        # yüklendi), eskininki bugün (klasör kopyalandı): ikisi de kararı değiştirmez.
        iki_ay_once = (simdi - timedelta(days=60)).timestamp()
        os.utime(yeni, (iki_ay_once, iki_ay_once))
        os.utime(eski, (simdi.timestamp(), simdi.timestamp()))
        elle = tmp_path / "db-onceki-elle-kopya.sqlite3"
        elle.write_bytes(b"elle")
        kaynak = tmp_path / "db.sqlite3"
        kaynak.write_bytes(b"canli")

        sonuc = _tetikle(IKI_YIL_SONRA)

        assert _ailesi(eski) == [], "14 günden eski önceki veritabanı ya da eşi kaldı"
        assert _ailesi(yeni) == [yeni.name, yeni.name + "-shm", yeni.name + "-wal"]
        assert elle.exists(), "programın ürettiği biçimde olmayan dosyaya dokunuldu"
        assert kaynak.exists()
        assert sonuc.run.old_db_removed == 1  # eşler ayrı veritabanı sayılmaz (D-4)
        assert RetentionRun.objects.get().old_db_pending == []
        kalinti = saklama.durum(IKI_YIL_SONRA)["residue"]
        assert (kalinti["old_databases"], kalinti["old_databases_expired"]) == (2, 0)
        assert saklama.durum(IKI_YIL_SONRA)["last_run"]["old_db_removed"] == 1

    def test_onceki_veritabani_silinemezse_adiyla_yeniden_denenir_saat_kaymasina_dayanikli(
        self, bugun: list[date], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silinemeyen dosya tetiği başarısız saymaz; adı `RetentionRun.old_db_pending`'e
        yazılır ve gün değişimi kapısı YALNIZ o adı yeniden dener (D-7 ilkesi): tetikten sonra
        saat kaymışken yapılan geri yüklemenin damgası "eski" görünse de o dosya silinmez."""
        monkeypatch.setattr(saklama, "_veri_dizini", lambda: tmp_path)
        kisi = self._aday()
        simdi = timezone.now()
        eski = _onceki(tmp_path, simdi - timedelta(days=30))
        ozgun_sil = backup_restore.remove_old_databases_named
        # Tetik anında dosyalar silinemedi (ör. bir veritabanı aracında açık).
        monkeypatch.setattr(
            backup_restore, "remove_old_databases_named", lambda _d, adlar: ([], list(adlar))
        )
        sonuc = _tetikle(IKI_YIL_SONRA)
        assert not Student.all_objects.filter(pk=kisi.pk).exists(), "tetik başarısız sayıldı"
        assert sonuc.run.old_db_removed == 0
        assert sorted(RetentionRun.objects.get().old_db_pending) == _ailesi(eski)
        monkeypatch.setattr(backup_restore, "remove_old_databases_named", ozgun_sil)

        # Tetikten sonra saat bir yıl geri kaymışken yapılan geri yükleme: adın damgası
        # tetik anından çok eski görünür.
        kaymis = _onceki(tmp_path, simdi - timedelta(days=400))

        assert saklama.gunluk_tarama(date(2028, 10, 2)) == "tamam"

        assert _ailesi(eski) == []
        assert len(_ailesi(kaymis)) == 3, "tetikten sonraki geri yüklemenin dosyası silindi"
        run = RetentionRun.objects.get()
        assert run.old_db_removed == 1 and run.old_db_pending == []

    @pytest.mark.parametrize("neden", ["yedek_alinamadi", "acik_yukumluluk"])
    def test_tetik_basarisizsa_onceki_veritabani_silinmez(
        self, neden: str, bugun: list[date], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silme veritabanı işlemi KALICI olduktan sonradır: yedek alınamazsa ya da işlem
        geri sarılırsa hiçbir önceki veritabanı dosyası silinmez."""
        from desktop import backup

        monkeypatch.setattr(saklama, "_veri_dizini", lambda: tmp_path)
        kisi = self._aday()
        eski = _onceki(tmp_path, timezone.now() - timedelta(days=30))
        if neden == "yedek_alinamadi":
            monkeypatch.setattr(backup, "pre_anonim_backup", lambda *a, **k: None)
        else:
            monkeypatch.setattr(persons, "open_obligations", lambda _kisi: ["1 açık ödünç var."])

        with pytest.raises(ValidationError):
            _tetikle(IKI_YIL_SONRA)

        assert Student.all_objects.filter(pk=kisi.pk).exists()
        assert len(_ailesi(eski)) == 3
        assert not RetentionRun.objects.exists()

    def test_yedek_alinamazsa_tetik_calismaz(
        self, bugun: list[date], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from desktop import backup

        kisi = self._aday()
        monkeypatch.setattr(backup, "pre_anonim_backup", lambda *a, **k: None)
        with pytest.raises(ValidationError) as hata:
            _tetikle(IKI_YIL_SONRA)
        assert saklama.YEDEK_ALINAMADI_MESAJI in hata.value.messages
        assert Student.all_objects.filter(pk=kisi.pk).exists()

    def test_onaylanan_liste_degistiyse_hicbir_sey_yazilmaz(self, bugun: list[date]) -> None:
        birinci = self._aday()
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        self._aday()  # onaydan sonra yeni aday
        with pytest.raises(saklama.SaklamaListesiDegisti):
            saklama.tetikle(anahtar=plan.anahtar, bugun=IKI_YIL_SONRA)
        assert Student.all_objects.filter(pk=birinci.pk).exists()

    def test_bos_listede_tetik_yok(self) -> None:
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        assert plan.bos
        with pytest.raises(ValidationError):
            saklama.tetikle(anahtar=plan.anahtar, bugun=IKI_YIL_SONRA)

    def test_bakimda_tetik_yok(self, bugun: list[date]) -> None:
        self._aday()
        kapi = BakimKapisi()
        kapi.bakima_al(bekleme_sn=0.1)
        plan = saklama.plan_hesapla(IKI_YIL_SONRA)
        with pytest.raises(ValidationError):
            saklama.tetikle(anahtar=plan.anahtar, bugun=IKI_YIL_SONRA, kapi=kapi)


# ============================================================ 6 ay (kod kapısı)


class TestAltiAy:
    def test_onay_bekleme_alti_ayi_asinca_uyari_tetikten_sonra_kalkar(
        self, bugun: list[date]
    ) -> None:
        kisi = ogrenci()
        _ayril(kisi)
        saklama.durum_yaz(IKI_YIL_SONRA, saklama.plan_hesapla(IKI_YIL_SONRA))
        assert RetentionState.load().pending_since == IKI_YIL_SONRA
        # Sonraki taramalar başlangıcı ötelemez.
        saklama.durum_yaz(date(2028, 12, 1), saklama.plan_hesapla(date(2028, 12, 1)))
        assert RetentionState.load().pending_since == IKI_YIL_SONRA

        assert saklama.pano_ozeti(date(2029, 3, 24))["overdue"] is False
        ozet = saklama.pano_ozeti(date(2029, 3, 25))
        assert ozet["overdue"] is True
        assert ozet["approval_deadline"] == date(2029, 3, 24)

        _tetikle(date(2029, 3, 25))
        assert RetentionState.load().pending_since is None
        assert saklama.pano_ozeti(date(2029, 3, 25))["overdue"] is False


# ============================================================ dondurulmuş sonuçlar


class TestDondurulmus:
    def test_cok_okunanlar_ve_sonlandirilmis_e9_anonimlestirmeden_sonra_degismez(
        self, bugun: list[date]
    ) -> None:
        yil = ders_yili()
        kitap = odunc_nushasi(title="Çok Okunan Deneme")
        uyeler = []
        for _ in range(5):
            kisi = ogrenci()
            uyelik = uye(kisi)
            uyeler.append((kisi, uyelik))
            loan = odunc_ver(uyelik, kitap)
            circulation.return_copy(copy=kitap)
            Loan.objects.filter(pk=loan.pk).update(
                loaned_at=_an(date(2026, 10, 5)), returned_at=_an(date(2026, 10, 6))
            )
        populer.hesapla(date(2026, 11, 1))  # Ekim kapandı: son hesap ve dondurma
        ekim = list(
            KatalogPopuler.objects.filter(pencere_turu=PopulerPencereTuru.AY, pencere="2026-10")
            .order_by("sira")
            .values_list("eser_id", "sira", "dondu")
        )
        assert ekim == [(kitap.work_id, 1, True)]
        rapor = annual_review.create_review(school_year=yil)
        rapor = annual_review.finalize_review(rapor)
        dondurulmus = annual_review.review_stats(rapor)
        for kisi, _uyelik in uyeler:
            _ayril(kisi)

        _tetikle(date(2029, 1, 1))
        assert not Loan.objects.filter(membership__isnull=False).exists()

        populer.hesapla(date(2029, 1, 2))
        sonra = list(
            KatalogPopuler.objects.filter(pencere_turu=PopulerPencereTuru.AY, pencere="2026-10")
            .order_by("sira")
            .values_list("eser_id", "sira", "dondu")
        )
        assert sonra == ekim
        rapor = AnnualLibraryReview.objects.get(pk=rapor.pk)
        assert annual_review.review_stats(rapor) == dondurulmus
        # Kişisiz istatistik (ödünç satırı) kalır.
        assert Loan.objects.filter(copy=kitap).count() == 5


# ============================================================ ibare ve belge izi


def _depo_dosyasi(yol: Path) -> str:
    """Depo kökündeki dosya: yerelde `depo/backend/...`, konteynerde `/repo`."""
    for kok in (Path(__file__).resolve().parents[4], Path("/repo")):
        if (kok / yol).is_file():
            return (kok / yol).read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı.")


def _pdf_metni(pdf: bytes) -> str:
    return " ".join(sayfa.extract_text() or "" for sayfa in PdfReader(io.BytesIO(pdf)).pages)


class TestIbareVeBelgeIzi:
    def test_ibare_tasarimdaki_metindir(self) -> None:
        assert belge_izi.ANONIM_KOPYA_IBARESI == (
            "Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir"
        )
        tasarim = _depo_dosyasi(Path("docs") / "tasarim" / "2026-09-21-genel-tasarim.md")
        assert belge_izi.ANONIM_KOPYA_IBARESI in tasarim

    def test_on_yuz_kopyalari_backendle_ayni(self) -> None:
        """Ön yüzde ELLE kopyalanmış sabitler (`test_on_yuz_sabitleri.py` kalıbı)."""
        from apps.kutuphane import dolasim_belgeleri

        api = _depo_dosyasi(Path("frontend") / "src" / "modules" / "saklama" / "api.ts")
        assert f'"{belge_izi.ANONIM_KOPYA_IBARESI}"' in api
        assert "export const YEDEK_GUN = 14;" in api
        kartlar = _depo_dosyasi(
            Path("frontend") / "src" / "modules" / "saklama" / "SaklamaKartlari.tsx"
        )
        assert f"export const AZAMI_BEKLEME_AY = {saklama.AZAMI_BEKLEME_AY};" in kartlar
        panel = _depo_dosyasi(
            Path("frontend") / "src" / "modules" / "saklama" / "SaklamaPaneli.tsx"
        )
        assert f'"{dolasim_belgeleri.KVKK_4_2_D}"' in " ".join(panel.split())
        from desktop import backup

        assert backup.DEFAULT_KEEP_DAYS == 14

    def test_kayip_hasar_tutanaginin_yeniden_basiminda_ibare(self, bugun: list[date]) -> None:
        kisi = ogrenci(first_name="Deneme", last_name="Kaybeden")
        dosya = _kayip_dosyasi_kapali(uye(kisi))
        once = teslim_belgeleri.case_report_context(selectors_teslim.get_case(dosya.pk))  # type: ignore[arg-type]
        assert once["anonim_kopya_ibaresi"] == ""
        assert "Deneme Kaybeden" in str(once["person"])

        _tetikle(IKI_YIL_SONRA)

        guncel = selectors_teslim.get_case(dosya.pk)
        assert guncel is not None
        sonra = teslim_belgeleri.case_report_context(guncel)
        assert sonra["anonim_kopya_ibaresi"] == belge_izi.ANONIM_KOPYA_IBARESI
        assert "Kaybeden" not in str(sonra) and "Deneme sorumlu" not in str(sonra)
        metin = _pdf_metni(teslim_belgeleri.case_report_pdf(guncel))
        assert "Anonimleştirilmiş kopya" in metin
        assert "Kaybeden" not in metin

    def test_teslim_listesinin_yeniden_basiminda_ibare(self, bugun: list[date]) -> None:
        hoca = ogretmen(last_name="Teslimalan")
        kitap = odunc_nushasi()
        toplu = teslim_et([kitap], personnel=hoca)
        deliveries.take_back(kitap)
        Delivery.objects.update(returned_at=_an(GUN))
        belge_no = toplu.document_no

        _tetikle(IKI_YIL_SONRA)

        satirlar = teslim_belgeleri.delivery_list_rows(document_no=belge_no)
        baglam = teslim_belgeleri.delivery_list_context(satirlar)
        assert baglam["anonim_kopya_ibaresi"] == belge_izi.ANONIM_KOPYA_IBARESI
        assert "Teslimalan" not in str(baglam)
        geri = teslim_belgeleri.take_back_context(satirlar, document_no=belge_no)
        assert geri["anonim_kopya_ibaresi"] == belge_izi.ANONIM_KOPYA_IBARESI
        assert "Anonimleştirilmiş kopya" in _pdf_metni(teslim_belgeleri.delivery_list_pdf(satirlar))

    def test_belge_izi_kisisiz_ve_anonim_kopya_isaretli(self, bugun: list[date]) -> None:
        from django.urls import reverse
        from rest_framework.test import APIClient

        kisi = ogrenci(first_name="Deneme", last_name="Izlenen")
        dosya = _kayip_dosyasi_kapali(uye(kisi))
        istemci = APIClient()
        url = reverse("library-loss-damage-case-pdf", args=[dosya.pk])

        yanit = istemci.get(url)
        assert yanit.status_code == 200
        icerik = b"".join(yanit.streaming_content)  # type: ignore[attr-defined]
        iz = BelgeIzi.objects.get()
        assert iz.tur == BelgeTuru.KAYIP_HASAR_TUTANAGI
        assert iz.sha256 == hashlib.sha256(icerik).hexdigest()
        assert iz.anonim_kopya is False
        assert "Izlenen" not in f"{iz.belge_sayisi} {iz.kapsam}"

        _tetikle(IKI_YIL_SONRA)
        istemci.get(url)
        assert BelgeIzi.objects.order_by("-pk").first().anonim_kopya is True  # type: ignore[union-attr]
        # Anonimleştirme izlere dokunmaz.
        assert BelgeIzi.objects.count() == 2


# ============================================================ gün değişimi kapısı


class TestGunlukTarama:
    def test_kapiya_kayitli(self) -> None:
        adlar = [is_.ad for is_ in masaustu_kanca.gunluk_isler()]
        assert saklama.GUNLUK_IS_ADI in adlar

    def test_tarama_kayit_degistirmez_ozeti_yazar(self, bugun: list[date]) -> None:
        kisi = ogrenci()
        _ayril(kisi)
        assert saklama.gunluk_tarama(IKI_YIL_SONRA) == "tamam"
        durum = RetentionState.load()
        assert durum.last_scan_on == IKI_YIL_SONRA
        assert durum.last_scan["students"] == 1
        assert durum.pending_since == IKI_YIL_SONRA
        assert Student.all_objects.filter(pk=kisi.pk).exists()

    def test_bakimda_ertelenir(self) -> None:
        kapi = BakimKapisi()
        kapi.bakima_al(bekleme_sn=0.1)
        assert saklama.gunluk_tarama(IKI_YIL_SONRA, kapi=kapi) == "bakimda"

    def test_bos_taramada_bekleme_baslamaz(self) -> None:
        assert saklama.gunluk_tarama(IKI_YIL_SONRA) == "tamam"
        assert RetentionState.load().pending_since is None


# ============================================================ D13: kapsam kanıtı


def test_d13_uyelik_satiri_ve_not_metinleri_kapsamda(bugun: list[date]) -> None:
    """D13 ("üyelik satırı, not metinleri"): sonlanmış üyelik satırı silinir; gerekçe ve
    sorumlu notu temizlenir — `TestSonlanmisUyelik` ayrıntılı sınar, burada tek bakış."""
    kisi = ogrenci()
    uyelik = uye(kisi)
    dosya = _kayip_dosyasi_kapali(uyelik)
    _ayril(kisi)
    _tetikle(IKI_YIL_SONRA)
    assert not Membership.all_objects.filter(pk=uyelik.pk).exists()
    assert LossDamageCase.all_objects.get(pk=dosya.pk).responsible_note == ""
    assert not LossDamageCase.all_objects.filter(anonymized_at__isnull=True).exists()


# ============================================================ TB24: tetikten sonra WAL


@pytest.mark.django_db(transaction=True)
def test_tetikten_sonra_wal_bosaltilir(bugun: list[date]) -> None:
    """`secure_delete` sayfadaki eski değeri ezer; WAL'deki eski sayfa görüntüleri de
    `checkpoint(TRUNCATE)` ile dosyaya işlenip WAL sıfıra iner (TB24 değerlendirmesi)."""
    from django.db import connection

    kisi = ogrenci()
    persons.leave_student(kisi)
    sonuc = _tetikle(IKI_YIL_SONRA)
    assert sonuc.wal_bosaldi is True
    wal = Path(f"{connection.settings_dict['NAME']}-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    with connection.cursor() as imlec:
        imlec.execute("PRAGMA secure_delete")
        assert imlec.fetchone()[0] == 1


def test_e5_ve_e15_izleri_kisisiz(bugun: list[date]) -> None:
    """E5 ve E15 üretilince iz yazılır; iz kişi adı ya da kimliği taşımaz (§6.2, KM-12)."""
    from django.urls import reverse
    from rest_framework.test import APIClient

    istemci = APIClient()
    temiz = ogrenci(first_name="Deneme", last_name="Izsoyad")
    yanit = istemci.post(
        reverse("library-clearance-certificate-pdf"), {"student_ids": [temiz.pk]}, format="json"
    )
    assert yanit.status_code == 200
    iz = BelgeIzi.objects.get(tur=BelgeTuru.ILISIK_BELGESI)
    assert (iz.kapsam, iz.adet, iz.belge_sayisi) == ("1 kişi", 1, "")

    hoca = ogretmen(last_name="Izogretmen")
    toplu = teslim_et([odunc_nushasi()], personnel=hoca)
    yanit = istemci.get(reverse("library-delivery-pdf"), {"personnel": hoca.pk})
    assert yanit.status_code == 200
    iz = BelgeIzi.objects.get(tur=BelgeTuru.TESLIM_LISTESI)
    assert iz.belge_sayisi == toplu.document_no and iz.kapsam == "Öğretmene teslim"
    yanit = istemci.post(
        reverse("library-delivery-take-back-report"),
        {"document_no": toplu.document_no},
        format="json",
    )
    assert yanit.status_code == 200
    assert BelgeIzi.objects.filter(tur=BelgeTuru.GERI_ALMA_DOKUMU).count() == 1
    for iz in BelgeIzi.objects.all():
        metin = f"{iz.belge_sayisi} {iz.kapsam}"
        assert "Izsoyad" not in metin and "Izogretmen" not in metin
