"""Üyelik — açma, istek listesi, kartı yenile, sonlandırma, silme ve kişi kancaları.

Tasarım §6.2, §9-1/2/8, §4.4; D12 (sonlandırma nedeni kapalı liste ve zorunlu).
Kişi kayıt defterleri (`apps.okul.services.persons`): açık ödünç = açık
yükümlülük; "hiç üye olmuş mu"; ayrılışta üyelik sonlanır; personel
birleştirmede üyelik ve ödünçler taşınır. Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.models import (
    CardRevocation,
    CardRevocationReason,
    Loan,
    LoanStatus,
    Membership,
    MembershipStatus,
    MemberType,
    TerminationReason,
)
from apps.kutuphane.selectors_dolasim import membership_request_list
from apps.kutuphane.services import circulation, memberships
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.dolasim_ortak import (
    odunc_ver,
    ogrenci,
    personel,
    personele_odunc_ac,
    uye,
)
from apps.okul.kip import KIP
from apps.okul.models import MemberKind, Personnel, Student, StudentStatus
from apps.okul.services import persons

pytestmark = pytest.mark.django_db


# ============================================================ açma (§9-1, §9-2)


class TestUyelikAcma:
    def test_ogrenci_ve_ogretmen_uye_olur_tur_kisiden_turer(self) -> None:
        ogr = uye(ogrenci())
        ogrt = uye(personel(member_kind=MemberKind.TEACHER))
        assert ogr.member_type == MemberType.STUDENT
        assert ogr.get_member_type_display() == "öğrenci"
        assert ogrt.member_type == MemberType.TEACHER
        assert ogr.status == MembershipStatus.ACTIVE
        assert ogr.started_at == timezone.localdate()
        assert ogr.card_printed_at is None  # kart basımı kuyruğunda

    def test_uye_turu_saklanmaz_personelin_turu_degisince_degisir(self) -> None:
        kisi = personel(member_kind=MemberKind.TEACHER)
        personele_odunc_ac()
        uyelik = uye(kisi)
        Personnel.objects.filter(pk=kisi.pk).update(member_kind=MemberKind.STAFF)
        uyelik.refresh_from_db()
        assert uyelik.member_type == MemberType.STAFF
        assert "member_type" not in {alan.name for alan in Membership._meta.get_fields()}

    def test_diger_personele_uyelik_yalniz_mudurluk_karariyla(self) -> None:
        kisi = personel(member_kind=MemberKind.STAFF)
        with pytest.raises(ValidationError) as hata:
            uye(kisi)
        assert memberships.STAFF_MEMBERSHIP_OFF_MESSAGE in hata.value.messages
        personele_odunc_ac()
        assert uye(kisi).member_type == MemberType.STAFF

    def test_kisi_basina_tek_aktif_uyelik(self) -> None:
        kisi = ogrenci()
        uye(kisi)
        with pytest.raises(ValidationError) as hata:
            uye(kisi)
        assert memberships.ALREADY_MEMBER_MESSAGE in hata.value.messages

    def test_tek_aktif_uyelik_db_kisitiyla_da_korunur(self) -> None:
        kisi = ogrenci()
        ilk = uye(kisi)
        ikinci = Membership(student=kisi, card_no="91234567")
        with pytest.raises(IntegrityError), transaction.atomic():
            ikinci.save()
        memberships.terminate_membership(ilk, reason=TerminationReason.MEMBER_REQUEST)
        yeni = uye(kisi)  # sonlanan üyelikten sonra YENİ satır ve yeni kart
        assert yeni.pk != ilk.pk and yeni.card_no != ilk.card_no

    def test_xor_kisiti_ogrenci_ya_da_personel(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            Membership(student=ogrenci(), personnel=personel(), card_no="91111112").save()
        with pytest.raises(IntegrityError), transaction.atomic():
            Membership(card_no="92222224").save()
        with pytest.raises(ValidationError):
            memberships.create_membership()
        with pytest.raises(ValidationError):
            memberships.create_membership(student=ogrenci(), personnel=personel())

    def test_veli_uyeligi_yoktur(self) -> None:
        """§9-1: veli alamaz — üyelik yalnız öğrenci ya da personele bağlanır."""
        baglar = {
            alan.name
            for alan in Membership._meta.get_fields()
            if alan.is_relation and alan.many_to_one
        }
        assert baglar == {"student", "personnel"}

    def test_ayrilmis_kisiye_uyelik_acilmaz(self) -> None:
        kisi = ogrenci()
        persons.leave_student(kisi)
        with pytest.raises(ValidationError) as hata:
            uye(kisi)
        assert memberships.PERSON_LEFT_MESSAGE in hata.value.messages

    def test_istek_tarihi_gelecekte_olamaz(self) -> None:
        with pytest.raises(ValidationError):
            uye(requested_at=timezone.localdate() + timedelta(days=1))
        gecmis = timezone.localdate() - timedelta(days=3)
        assert uye(requested_at=gecmis).requested_at == gecmis


class TestIstekListesi:
    def test_ogrenci_kaydi_kimseyi_uye_yapmaz(self) -> None:
        """§9-2: üyelik isteğe bağlıdır (Md. 17/1)."""
        ogrenci()
        ogrenci()
        assert not Membership.objects.exists()

    def test_istek_listesi_subenin_aktif_ogrencilerini_siralar(self) -> None:
        b = ogrenci(first_name="Bora", student_number="12", class_section="Ş")
        a = ogrenci(first_name="Ayşe", student_number="9", class_section="Ş")
        persons.leave_student(ogrenci(student_number="15", class_section="Ş"))
        ogrenci(class_section="A")
        uye(b)

        satirlar = membership_request_list(class_level=9, class_section="ş")

        assert [s.student.pk for s in satirlar] == [a.pk, b.pk]  # okul no doğal sırası
        assert [s.membership is not None for s in satirlar] == [False, True]

    def test_secilenlere_toplu_uyelik_acilir(self) -> None:
        secilen = [ogrenci(), ogrenci()]
        secilmeyen = ogrenci()

        acilan = memberships.create_memberships_for_students([o.pk for o in secilen])

        assert [m.student_id for m in acilan] == [o.pk for o in secilen]
        assert not Membership.objects.filter(student=secilmeyen).exists()
        assert len({m.card_no for m in acilan}) == 2

    @pytest.mark.parametrize("durum", ["uye", "ayrilmis", "yok"])
    def test_bayat_secimde_hicbir_uyelik_acilmaz(self, durum: str) -> None:
        temiz = ogrenci()
        sorunlu = ogrenci()
        if durum == "uye":
            uye(sorunlu)
        elif durum == "ayrilmis":
            persons.leave_student(sorunlu)
        kimlikler = [temiz.pk, sorunlu.pk if durum != "yok" else 999_999]
        onceki = Membership.objects.count()

        with pytest.raises(ValidationError) as hata:
            memberships.create_memberships_for_students(kimlikler)

        assert memberships.REQUEST_STALE_MESSAGE in hata.value.messages
        assert Membership.objects.count() == onceki

    def test_bos_secim_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            memberships.create_memberships_for_students([])


# ============================================================ sonlandırma (D12)


class TestSonlandirma:
    @pytest.mark.parametrize(
        "neden", [TerminationReason.MEMBER_REQUEST, TerminationReason.RECORD_ERROR]
    )
    def test_elle_sonlandirma_nedeni_ve_tarihi_yazar(self, neden: str) -> None:
        uyelik = memberships.terminate_membership(uye(), reason=neden)
        uyelik.refresh_from_db()
        assert uyelik.status == MembershipStatus.TERMINATED
        assert uyelik.terminated_at == timezone.localdate()
        assert uyelik.termination_reason == neden

    @pytest.mark.parametrize("neden", ["", "BASKA", "LEFT_SCHOOL", "MERGED"])
    def test_elle_secilemeyen_ya_da_bos_neden_reddedilir(self, neden: str) -> None:
        uyelik = uye()
        with pytest.raises(ValidationError) as hata:
            memberships.terminate_membership(uyelik, reason=neden)
        assert "reason" in hata.value.message_dict
        uyelik.refresh_from_db()
        assert uyelik.is_active

    def test_db_kisiti_bos_ya_da_liste_disi_nedeni_reddeder(self) -> None:
        uyelik = uye()
        for alanlar in (
            {"status": "TERMINATED", "terminated_at": date(2026, 9, 1), "termination_reason": ""},
            {"status": "TERMINATED", "terminated_at": None, "termination_reason": "RECORD_ERROR"},
            {"status": "TERMINATED", "terminated_at": date(2026, 9, 1), "termination_reason": "X"},
            {"status": "ACTIVE", "terminated_at": None, "termination_reason": "RECORD_ERROR"},
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                Membership.objects.filter(pk=uyelik.pk).update(**alanlar)

    def test_acik_oduncu_olan_uyelik_elle_sonlandirilamaz(self) -> None:
        uyelik = uye()
        odunc_ver(uyelik)
        with pytest.raises(ValidationError) as hata:
            memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)
        assert memberships.TERMINATE_OPEN_LOANS_MESSAGE in hata.value.messages

    def test_sonlanmis_uyelik_yeniden_sonlandirilamaz(self) -> None:
        uyelik = memberships.terminate_membership(uye(), reason=TerminationReason.RECORD_ERROR)
        with pytest.raises(ValidationError):
            memberships.terminate_membership(uyelik, reason=TerminationReason.RECORD_ERROR)


# ============================================================ kartı yenile (§4.4)


class TestKartiYenile:
    def test_yeni_no_eski_iptal_acik_odunc_uyelikte_kalir(self) -> None:
        uyelik = uye()
        loan = odunc_ver(uyelik)
        Membership.objects.filter(pk=uyelik.pk).update(card_printed_at=timezone.now())
        uyelik.refresh_from_db()
        eski_no, eski_indeks = uyelik.card_no, uyelik.card_no_index

        memberships.renew_card(uyelik)

        uyelik.refresh_from_db()
        assert uyelik.card_no != eski_no
        assert uyelik.card_printed_at is None  # yeni kart basım kuyruğunda
        iptal = CardRevocation.objects.get(card_no_index=eski_indeks)
        assert iptal.reason == CardRevocationReason.RENEWED
        assert iptal.membership_id == uyelik.pk
        loan.refresh_from_db()
        assert loan.membership_id == uyelik.pk and loan.status == LoanStatus.OPEN

    def test_gorevli_kipinde_kart_yenilenemez(self) -> None:
        uyelik = uye()
        eski = uyelik.card_no
        KIP.gorevliye_gec()
        with pytest.raises(KipYetkisiz):
            memberships.renew_card(uyelik)
        uyelik.refresh_from_db()
        assert uyelik.card_no == eski
        assert not CardRevocation.objects.exists()

    def test_sonlanmis_uyeligin_karti_yenilenemez(self) -> None:
        uyelik = memberships.terminate_membership(uye(), reason=TerminationReason.RECORD_ERROR)
        with pytest.raises(ValidationError):
            memberships.renew_card(uyelik)


# ============================================================ silme


class TestSilme:
    def test_odunc_kaydi_olmayan_uyelik_silinir_karti_iptal_edilir(self) -> None:
        uyelik = uye()
        memberships.delete_membership(uyelik)
        assert not Membership.all_objects.exists()
        assert CardRevocation.objects.filter(reason=CardRevocationReason.DELETED).count() == 1

    def test_odunc_kaydi_olan_uyelik_silinmez(self) -> None:
        uyelik = uye()
        loan = odunc_ver(uyelik)
        circulation.return_copy(copy=loan.copy)
        with pytest.raises(ValidationError) as hata:
            memberships.delete_membership(uyelik)
        assert memberships.DELETE_HAS_LOANS_MESSAGE in hata.value.messages

    def test_yenilenmis_kartin_iptal_kaydi_uyelik_silinince_kalir(self) -> None:
        uyelik = uye()
        memberships.renew_card(uyelik)
        memberships.delete_membership(uyelik)
        assert CardRevocation.objects.count() == 2
        assert set(CardRevocation.objects.values_list("membership", flat=True)) == {None}


# ============================================================ kişi kayıt defterleri


class TestKisiKancalari:
    def test_kancalar_kayitlidir(self) -> None:
        assert memberships.open_loan_obligations in persons._obligation_checks
        assert memberships.was_ever_member in persons._membership_checks
        assert memberships.terminate_on_leave in persons._leave_hooks
        assert memberships.move_on_merge in persons._merge_hooks

    def test_acik_odunc_acik_yukumluluktur_ve_ad_icermez(self) -> None:
        kisi = ogrenci(first_name="Zeynepkanca", last_name="Deneme")
        odunc_ver(uye(kisi))
        gerekceler = persons.open_obligations(kisi)
        assert gerekceler == ["1 açık ödünç var."]
        assert "Zeynepkanca" not in " ".join(gerekceler)
        with pytest.raises(ValidationError):
            persons.delete_student(kisi)

    def test_uye_olmus_kisi_silinmez_yanlis_uyelik_silinince_silinir(self) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        assert persons.was_ever_member(kisi)
        with pytest.raises(ValidationError) as hata:
            persons.delete_student(kisi)
        assert persons.MEMBER_DELETE_MESSAGE in hata.value.messages

        memberships.delete_membership(uyelik)
        persons.delete_student(kisi)
        assert not Student.all_objects.filter(pk=kisi.pk).exists()

    def test_ayrilista_uyelik_sonlanir_acik_odunc_yukumluluk_olarak_kalir(self) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        loan = odunc_ver(uyelik)

        persons.leave_student(kisi)

        uyelik.refresh_from_db()
        assert uyelik.status == MembershipStatus.TERMINATED
        assert uyelik.termination_reason == TerminationReason.LEFT_SCHOOL
        assert uyelik.terminated_at == timezone.localdate()
        assert persons.open_obligations(kisi) == ["1 açık ödünç var."]
        assert Student.objects.get(pk=kisi.pk).status == StudentStatus.LEFT  # kayıt kalır
        loan.refresh_from_db()
        assert loan.status == LoanStatus.OPEN and loan.membership_id == uyelik.pk

    def test_havuz_karariyla_ayrilanin_uyeligi_sonlanir(self) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        persons.add_to_leave_pool(kisi, run=None)
        persons.resolve_leave_pool(students=persons.PoolDecision(leave=(kisi.pk,)))
        uyelik.refresh_from_db()
        assert uyelik.termination_reason == TerminationReason.LEFT_SCHOOL

    def test_personel_ayrilisinda_uyelik_sonlanir(self) -> None:
        kisi = personel()
        uyelik = uye(kisi)
        persons.leave_personnel(kisi)
        uyelik.refresh_from_db()
        assert uyelik.status == MembershipStatus.TERMINATED

    def test_birlestirmede_uyelik_ve_odunc_hedefe_tasinir(self) -> None:
        kaynak = personel(last_name="Eskisoyad")
        hedef = personel(last_name="Yenisoyad")
        uyelik = uye(kaynak)
        loan = odunc_ver(uyelik)

        persons.merge_personnel(kaynak, hedef)

        uyelik.refresh_from_db()
        assert uyelik.personnel_id == hedef.pk and uyelik.is_active
        loan.refresh_from_db()
        assert loan.membership_id == uyelik.pk
        assert not Personnel.all_objects.filter(pk=kaynak.pk).exists()

    def test_birlestirmede_hedefin_aktif_uyeligi_varsa_odunc_ona_gecer(self) -> None:
        kaynak = personel(last_name="Eskisoyad")
        hedef = personel(last_name="Yenisoyad")
        kaynak_uyelik = uye(kaynak)
        hedef_uyelik = uye(hedef)
        loan = odunc_ver(kaynak_uyelik)
        eski_indeks = kaynak_uyelik.card_no_index

        persons.merge_personnel(kaynak, hedef)

        kaynak_uyelik.refresh_from_db()
        assert kaynak_uyelik.personnel_id == hedef.pk
        assert kaynak_uyelik.termination_reason == TerminationReason.MERGED
        loan.refresh_from_db()
        assert loan.membership_id == hedef_uyelik.pk
        assert (
            CardRevocation.objects.get(card_no_index=eski_indeks).reason
            == CardRevocationReason.MERGED
        )
        assert Membership.objects.filter(personnel=hedef, status="ACTIVE").count() == 1

    def test_birlestirmede_hedef_ayrilmissa_tasinan_uyelik_sonlanir(self) -> None:
        kaynak = personel()
        hedef = personel()
        uyelik = uye(kaynak)
        persons.leave_personnel(hedef)

        persons.merge_personnel(kaynak, hedef)

        uyelik.refresh_from_db()
        assert uyelik.personnel_id == hedef.pk
        assert uyelik.termination_reason == TerminationReason.LEFT_SCHOOL

    def test_ayrilip_donen_ogrencinin_eski_acik_oduncu_sayilir(self) -> None:
        """Sayılar KİŞİ bazındadır: yeni üyelik eski üyelikteki açık ödüncü sıfırlamaz."""
        kisi = ogrenci()
        eski = uye(kisi)
        odunc_ver(eski)
        persons.leave_student(kisi)
        persons.reactivate_student(kisi)
        kisi.save(update_fields=["status", "left_at"])

        yeni = uye(kisi)

        assert Loan.objects.filter(membership=eski, status="OPEN").count() == 1

        assert selectors_dolasim.open_loan_count(yeni) == 1
        assert selectors_dolasim.remaining_quota(yeni) == 2
