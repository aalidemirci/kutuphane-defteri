"""Dolaşım kuralları — tasarım §9 maddeleri, HER MADDE AYRI SINIF (§14.1 F6 kod kapısı).

§9-1 kim ödünç alabilir · §9-2 üyelik isteğe bağlı (ayrıca `test_uyelik.py`) ·
§9-3 ödünç verilmeyenler · §9-4 süre ve sayı (hiçbir kipte istisna yok) ·
§9-5 iade tarihi kaydırması ve dönem sonu uyarısı · §9-6 uzatma/ceza yok,
gecikme engeli ve yönetici istisnası · §9-7 tek açık ödünç · §9-8 ayrılış ·
§9-12 kartsız ödünç · yıl sonu son ödünç tarihi (§8.3) · iade hiçbir durumda
kilitlenmez · D9 (26. ödünç de barkodla iade edilir) · D19 (süre sabit).
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.models import (
    Copy,
    CopyStatus,
    LibraryPolicy,
    Loan,
    LoanStatus,
    ResourceType,
    TerminationReason,
)
from apps.kutuphane.services import circulation, memberships
from apps.kutuphane.services.circulation import (
    OVERDUE_STAFF_MESSAGE,
    RED_ACIK_ODUNC_YOK,
    RED_BASKA_UYEDE,
    RED_BU_UYEDE,
    RED_GECIKME,
    RED_ODUNC_VERILMEZ,
    RED_PERSONEL,
    RED_SINIR,
    RED_SON_TARIH,
    RED_UYELIK,
    DolasimReddi,
)
from apps.kutuphane.services.policy import LOAN_PERIOD_DAYS
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.dolasim_ortak import (
    ACIK_GUN,
    ders_yili,
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    personel,
    personele_odunc_ac,
    politika,
    uye,
)
from apps.kutuphane.tests.ortak import eser, nusha
from apps.okul.kip import KIP
from apps.okul.models import (
    Holiday,
    HolidayKind,
    MemberKind,
    SchoolConfig,
    SchoolLevel,
    Student,
)
from apps.okul.services import calendar, persons

pytestmark = pytest.mark.django_db

#: Gerekçeli istisnanın geçerli gövdesi (yönetici kipi).
ISTISNA = {"override_reason": "COURSE_NEED", "override_note": "Proje ödevi için gerekli."}
KARTSIZ = {"cardless_reason": "CARD_NOT_WITH_MEMBER"}


def _red(hata: pytest.ExceptionInfo[DolasimReddi], kod: str) -> None:
    assert hata.value.code == kod, (hata.value.code, hata.value.message)


def _ham(tablo: str, sutun: str, pk: int) -> str:
    with connection.cursor() as imlec:
        imlec.execute(f'SELECT "{sutun}" FROM "{tablo}" WHERE id = %s', [pk])  # noqa: S608
        satir = imlec.fetchone()
    return str(satir[0])


# ============================================================ §9-1 kim ödünç alabilir


class Test91KimOduncAlabilir:
    def test_uye_ogrenci_ve_ogretmen_odunc_alir(self) -> None:
        for kisi in (ogrenci(), personel(member_kind=MemberKind.TEACHER)):
            loan = odunc_ver(uye(kisi))
            assert loan.status == LoanStatus.OPEN
            assert Copy.objects.get(pk=loan.copy_id).status == CopyStatus.ON_LOAN

    def test_diger_personel_yalniz_mudurluk_karariyla(self) -> None:
        personele_odunc_ac()
        uyelik = uye(personel(member_kind=MemberKind.STAFF))
        politika(staff_loans_enabled=False)  # karar kaldırıldı
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_PERSONEL)
        personele_odunc_ac()
        assert odunc_ver(uyelik).status == LoanStatus.OPEN

    def test_sonlanmis_uyelige_odunc_verilmez(self) -> None:
        uyelik = memberships.terminate_membership(uye(), reason=TerminationReason.MEMBER_REQUEST)
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_UYELIK)

    def test_ayrilmis_kisinin_aktif_kalmis_uyeligine_odunc_verilmez(self) -> None:
        """Savunma: kanca dışı bir yolla ayrılmış kişi (üyelik aktif kalmış) yine alamaz."""
        kisi = ogrenci()
        uyelik = uye(kisi)
        Student.objects.filter(pk=kisi.pk).update(status="LEFT")
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_UYELIK)


# ============================================================ §9-2 üyelik isteğe bağlı


class Test92UyelikIstegeBagli:
    def test_uyeligi_olmayan_ogrencinin_odunc_yolu_yoktur(self) -> None:
        kisi = ogrenci()
        assert selectors_dolasim.active_membership_of(kisi) is None
        assert (
            selectors_dolasim.find_active_membership_by_student_number(kisi.student_number) is None
        )
        assert "membership" in inspect.signature(circulation.checkout).parameters


# ============================================================ §9-3 ödünç verilmeyenler


def _verilmez_nusha(tur: str) -> Copy:
    if tur == "danisma":
        return odunc_nushasi(is_reference=True)
    if tur == "piyasada_yok":
        return odunc_nushasi(is_out_of_print=True)
    if tur == "sureli_yayin":
        return nusha(eser(resource_type=ResourceType.PERIODICAL), is_bound_periodical=True)
    if tur == "dijital":
        # Dijital eserin nüshası servisle AÇILAMAZ; iki kapı da aşılmış olsa bile
        # ödünç verilmemelidir (savunma derinliği).
        copy = odunc_nushasi()
        eser_ = copy.work
        eser_.resource_type = ResourceType.EBOOK
        eser_.save(update_fields=["resource_type"])
        return copy
    copy = odunc_nushasi()
    Copy.objects.filter(pk=copy.pk).update(status=tur)
    copy.refresh_from_db()
    return copy


VERILMEYENLER = [
    "danisma",
    "piyasada_yok",
    "sureli_yayin",
    "dijital",
    CopyStatus.IN_REPAIR,
    CopyStatus.LOST,
    CopyStatus.DELIVERED,
    CopyStatus.WITHDRAWN_WEEDED,
]


class Test93OduncVerilmeyenler:
    @pytest.mark.parametrize("tur", VERILMEYENLER)
    @pytest.mark.parametrize("kip", ["gorevli", "yonetici", "yonetici_istisna", "kartsiz"])
    def test_hicbir_kipte_verilmez(self, tur: str, kip: str) -> None:
        uyelik = uye()
        copy = _verilmez_nusha(tur)
        ek: dict[str, str] = {}
        if kip == "gorevli":
            KIP.gorevliye_gec()
        elif kip == "yonetici_istisna":
            gecikmeli_yap(odunc_ver(uyelik))  # istisna gerekçesi anlamlı olsun
            ek = ISTISNA
        elif kip == "kartsiz":
            ek = KARTSIZ

        with pytest.raises(DolasimReddi) as hata:
            circulation.checkout(copy=copy, membership=uyelik, **ek)

        _red(hata, RED_ODUNC_VERILMEZ)
        assert not Loan.objects.filter(copy=copy).exists()

    def test_red_iletisi_kisisel_olmayan_sebeptir(self) -> None:
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uye(), odunc_nushasi(is_reference=True))
        assert hata.value.message == "Ödünç verilmez — kütüphanede okunur."

    def test_servisin_sinir_ve_kaynak_icin_istisna_parametresi_yoktur(self) -> None:
        """Md. 18 sayı sınırı ve Md. 16/1 kaynakları için gerekçe alanı bulunmaz."""
        parametreler = set(inspect.signature(circulation.checkout).parameters)
        assert parametreler == {
            "copy",
            "membership",
            "override_reason",
            "override_note",
            "cardless_reason",
        }


# ============================================================ §9-4 süre ve sayı


class Test94SureVeSayi:
    def test_sure_on_bes_gun_ve_ayar_degildir(self, bugun: list[date]) -> None:
        """D19: OYS'nin 1-15 arası ayarı alınmadı; süre sabittir."""
        loan = odunc_ver(uye())
        assert LOAN_PERIOD_DAYS == 15
        assert loan.due_date == ACIK_GUN + timedelta(days=15)
        alanlar = {alan.name for alan in LibraryPolicy._meta.get_fields()}
        assert not {a for a in alanlar if "period" in a or "sure" in a or "days" in a}

    @pytest.mark.parametrize(("tur", "sinir"), [("ogrenci", 3), ("ogretmen", 5), ("diger", 3)])
    def test_uye_turune_gore_sayi_siniri(self, tur: str, sinir: int) -> None:
        if tur == "diger":
            personele_odunc_ac(max_loans_staff=3)
            kisi: Any = personel(member_kind=MemberKind.STAFF)
        elif tur == "ogretmen":
            kisi = personel(member_kind=MemberKind.TEACHER)
        else:
            kisi = ogrenci()
        uyelik = uye(kisi)
        for _ in range(sinir):
            odunc_ver(uyelik)
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_SINIR)
        assert hata.value.message == f"Ödünç sınırı dolu (en çok {sinir} kitap)."

    @pytest.mark.parametrize("kip", ["gorevli", "yonetici", "yonetici_istisna", "kartsiz"])
    def test_sayi_siniri_hicbir_kipte_istisna_almaz(self, kip: str) -> None:
        uyelik = uye()
        acik = [odunc_ver(uyelik) for _ in range(3)]
        ek: dict[str, str] = {}
        if kip == "gorevli":
            KIP.gorevliye_gec()
        elif kip == "yonetici_istisna":
            gecikmeli_yap(acik[0])
            ek = ISTISNA
        elif kip == "kartsiz":
            ek = KARTSIZ

        with pytest.raises(DolasimReddi) as hata:
            circulation.checkout(copy=odunc_nushasi(), membership=uyelik, **ek)

        _red(hata, RED_SINIR)
        assert selectors_dolasim.open_loan_count(uyelik) == 3

    def test_politikada_daha_dusuk_sinir_uygulanir(self) -> None:
        politika(max_loans_student=1)
        uyelik = uye()
        odunc_ver(uyelik)
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_SINIR)

    def test_iade_edilen_hak_geri_gelir(self) -> None:
        uyelik = uye()
        loans = [odunc_ver(uyelik) for _ in range(3)]
        circulation.return_copy(copy=loans[0].copy)
        assert selectors_dolasim.remaining_quota(uyelik) == 1
        assert odunc_ver(uyelik).status == LoanStatus.OPEN


# ============================================================ §9-5 iade tarihi


def _pazartesi_sonrasi(gun: date) -> date:
    """`gun + 15` cumartesiye denk gelecek ödünç günü (hafta sonu kaydırması kurgusu)."""
    while (gun + timedelta(days=15)).weekday() != 5:
        gun += timedelta(days=1)
    return gun


class Test95IadeTarihi:
    def test_acik_gunde_kaydirma_yok(self) -> None:
        assert circulation.due_date_for(ACIK_GUN) == ACIK_GUN + timedelta(days=15)

    def test_hafta_sonu_izleyen_ilk_is_gunune_kayar(self, bugun: list[date]) -> None:
        bugun[0] = _pazartesi_sonrasi(ACIK_GUN)
        sonuc = circulation.checkout(copy=odunc_nushasi(), membership=uye())
        ham = bugun[0] + timedelta(days=15)
        assert ham.weekday() == 5
        assert sonuc.loan.due_date == ham + timedelta(days=2)  # pazartesi
        assert sonuc.due_date_shifted is True

    @pytest.mark.parametrize(
        "tur", [HolidayKind.OFFICIAL, HolidayKind.RELIGIOUS, HolidayKind.OTHER]
    )
    def test_resmi_dini_tatil_ve_idari_izin_daima_kaydirir(self, tur: str) -> None:
        politika(shift_due_date_on_school_break=False)  # bu ayar bunlara dokunmaz
        ham = ACIK_GUN + timedelta(days=15)  # cuma
        Holiday.objects.create(name="Deneme kapalı gün", start_date=ham, end_date=ham, kind=tur)
        assert circulation.due_date_for(ACIK_GUN) == ham + timedelta(days=3)  # pazartesi

    @pytest.mark.parametrize(("ayar", "kayar"), [(True, True), (False, False)])
    def test_ogrenciye_kapali_gun_ayarla_kaydirir(self, ayar: bool, kayar: bool) -> None:
        politika(shift_due_date_on_school_break=ayar)
        ham = ACIK_GUN + timedelta(days=15)
        Holiday.objects.create(
            name="Deneme ara tatil",
            start_date=ham - timedelta(days=4),
            end_date=ham + timedelta(days=5),
            kind=HolidayKind.SCHOOL_BREAK,
        )
        beklenen = ham + timedelta(days=6) if kayar else ham
        while beklenen.weekday() >= 5:
            beklenen += timedelta(days=1)
        assert circulation.due_date_for(ACIK_GUN) == beklenen

    def test_donem_sonunu_asarsa_uyari_sure_kisaltilmaz(self, bugun: list[date]) -> None:
        ders_yili()
        calendar.seed_holidays(2027)
        bugun[0] = date(2027, 1, 14)  # 1. dönem 22.01.2027'de biter
        sonuc = circulation.checkout(copy=odunc_nushasi(), membership=uye())
        assert sonuc.loan.due_date >= date(2027, 1, 29)  # 15 gün tam
        assert len(sonuc.warnings) == 1
        assert "22.01.2027" in sonuc.warnings[0]
        assert "Süre kısaltılmaz" in sonuc.warnings[0]

    def test_donem_icinde_uyari_yok(self, bugun: list[date]) -> None:
        ders_yili()
        calendar.seed_holidays(2026)
        sonuc = circulation.checkout(copy=odunc_nushasi(), membership=uye())
        assert sonuc.warnings == ()

    def test_tatilleri_girilmemis_yila_dusen_iade_tarihi_uyarir(self, bugun: list[date]) -> None:
        """Yıl dönümü: 2027'nin tatilleri yokken 01.01.2027'ye düşen iade KAYMAZ; uyarı çıkar."""
        calendar.seed_holidays(2026)
        bugun[0] = date(2026, 12, 17)  # + 15 = 01.01.2027 cuma (Yılbaşı)
        sonuc = circulation.checkout(copy=odunc_nushasi(), membership=uye())

        assert sonuc.loan.due_date == date(2027, 1, 1)
        assert sonuc.warnings == (circulation.HOLIDAYS_MISSING_WARNING.format(yil="2027"),)

        calendar.seed_holidays(2027)
        sonuc = circulation.checkout(copy=odunc_nushasi(), membership=uye())
        assert sonuc.loan.due_date == date(2027, 1, 4)  # Yılbaşı ve hafta sonu atlandı
        assert sonuc.warnings == ()

    def test_dini_bayramlari_eksik_yil_da_uyarir(self, bugun: list[date]) -> None:
        """Resmî tatiller var ama dini bayram kaydı yoksa (ör. tablo dışı yıl) yine uyarı."""
        calendar.seed_holidays(2026)
        Holiday.objects.filter(kind=HolidayKind.RELIGIOUS).delete()
        sonuc = circulation.checkout(copy=odunc_nushasi(), membership=uye())
        assert sonuc.warnings == (circulation.HOLIDAYS_MISSING_WARNING.format(yil="2026"),)

    def test_ders_yili_tanimsizken_uyari_yok(self) -> None:
        assert circulation.term_end_warning(ACIK_GUN, ACIK_GUN + timedelta(days=200)) == ""

    def test_kaydirma_md18_geregi_diye_sunulmaz(self) -> None:
        kaynak = inspect.getsource(circulation)
        iletiler = [
            deger
            for ad, deger in vars(circulation).items()
            if ad.isupper() and isinstance(deger, str)
        ]
        assert iletiler
        for metin in [*iletiler, circulation.term_end_warning(date(2027, 1, 14), date(2027, 2, 1))]:
            assert "Md. 18 gereği" not in metin
        assert "gereği" not in "".join(iletiler)
        assert kaynak.count("Md. 18 gereği") == 1  # yalnız bu yasağı anlatan modül yorumunda


# ============================================================ §9-6 uzatma/ceza yok, gecikme engeli


class Test96GecikmeEngeli:
    def test_uzatma_ceza_ve_harc_yoktur(self) -> None:
        alanlar = {alan.name for alan in Loan._meta.get_fields()}
        yasak = ("renew", "extend", "fine", "fee", "penalty", "ceza", "harc", "uzat")
        assert not [a for a in alanlar if any(k in a for k in yasak)]
        assert not [ad for ad in vars(circulation) if any(k in ad.lower() for k in yasak)]

    def test_gecikmesi_olan_uyeye_odunc_verilmez(self) -> None:
        uyelik = uye()
        gecikmeli_yap(odunc_ver(uyelik))
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_GECIKME)
        assert hata.value.message == circulation.OVERDUE_ADMIN_MESSAGE

    def test_gorevli_kipinde_eser_adi_ve_gecikme_gunu_gosterilmez(self) -> None:
        uyelik = uye()
        loan = gecikmeli_yap(odunc_ver(uyelik, odunc_nushasi(title="Gizlieseradi")), gun=7)
        KIP.gorevliye_gec()
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik)
        _red(hata, RED_GECIKME)
        assert hata.value.message == OVERDUE_STAFF_MESSAGE
        assert "Gizlieseradi" not in hata.value.message
        assert str(loan.overdue_days()) not in hata.value.message

    def test_gorevli_kipinde_ret_sirasi_gecikmeli_uyenin_kitaplarini_ele_vermez(self) -> None:
        """§4.4: görevli, gecikmeli üyenin kartıyla barkod deneyerek elindekileri öğrenemez.

        Görevli kipinde gecikme engeli nüshanın kimde olduğundan ÖNCE koşar: üyenin
        kendi (gecikmiş) kitabı, başka üyedeki ve raftaki kitap AYNI reddi alır.
        """
        uyelik = uye()
        kendi = gecikmeli_yap(odunc_ver(uyelik, odunc_nushasi(title="Gizlieseradi")), gun=7)
        baskasinda = odunc_ver(uye())
        rafta = odunc_nushasi()
        KIP.gorevliye_gec()
        iletiler = set()
        for copy in (kendi.copy, baskasinda.copy, rafta):
            with pytest.raises(DolasimReddi) as hata:
                odunc_ver(uyelik, copy)
            _red(hata, RED_GECIKME)
            iletiler.add(hata.value.message)
        assert iletiler == {OVERDUE_STAFF_MESSAGE}

    def test_gorevli_kipinde_siniri_dolu_uyenin_odunc_listesi_cikarilamaz(self) -> None:
        uyelik = uye()
        kendileri = [odunc_ver(uyelik) for _ in range(3)]
        baskasinda = odunc_ver(uye())
        KIP.gorevliye_gec()
        for copy in [lo.copy for lo in kendileri] + [baskasinda.copy, odunc_nushasi()]:
            with pytest.raises(DolasimReddi) as hata:
                odunc_ver(uyelik, copy)
            _red(hata, RED_SINIR)

    def test_yonetici_kipinde_uyenin_kendi_kitabi_once_sorulur(self) -> None:
        """Yönetici kipinde sıra korunur: kendi gecikmiş kitabı istisna penceresine düşmez."""
        uyelik = uye()
        kendi = gecikmeli_yap(odunc_ver(uyelik))
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik, kendi.copy)
        _red(hata, RED_BU_UYEDE)

    def test_gorevli_kipinde_istisna_istenemez(self) -> None:
        uyelik = uye()
        gecikmeli_yap(odunc_ver(uyelik))
        KIP.gorevliye_gec()
        with pytest.raises(KipYetkisiz):
            odunc_ver(uyelik, **ISTISNA)
        assert selectors_dolasim.open_loan_count(uyelik) == 1

    def test_yonetici_kipinde_gerekceli_istisna_kayda_sifreli_gecer(self) -> None:
        uyelik = uye()
        gecikmeli_yap(odunc_ver(uyelik))

        loan = odunc_ver(uyelik, **ISTISNA)

        assert loan.has_override
        loan.refresh_from_db()
        assert loan.override_reason == "COURSE_NEED"
        assert loan.override_note == ISTISNA["override_note"]
        assert _ham("kutuphane_loan", "override_note", loan.pk) != ISTISNA["override_note"]
        assert _ham("kutuphane_loan", "override_reason", loan.pk) != "COURSE_NEED"

    @pytest.mark.parametrize(
        ("govde", "alan"),
        [
            ({"override_reason": "COURSE_NEED"}, "override_note"),
            ({"override_reason": "COURSE_NEED", "override_note": "   "}, "override_note"),
            ({"override_reason": "BASKA", "override_note": "açıklama"}, "override_reason"),
            ({"override_note": "yalnız açıklama"}, "override_reason"),
            ({"override_reason": "OTHER", "override_note": "x" * 501}, "override_note"),
        ],
    )
    def test_gerekce_kapali_liste_ve_aciklama_zorunlu(
        self, govde: dict[str, str], alan: str
    ) -> None:
        """D12: istisna gerekçesi boş kalamaz."""
        uyelik = uye()
        gecikmeli_yap(odunc_ver(uyelik))
        with pytest.raises(ValidationError) as hata:
            odunc_ver(uyelik, **govde)
        assert alan in hata.value.message_dict

    def test_db_kisiti_bos_gerekceli_istisnayi_reddeder(self) -> None:
        loan = odunc_ver(uye())
        loan.override_reason = "OTHER"
        with pytest.raises(IntegrityError), transaction.atomic():
            loan.save(update_fields=["override_reason"])  # açıklamasız gerekçe

    def test_engel_kapaliysa_gecikmeli_uyeye_verilir_istisna_kaydedilmez(self) -> None:
        politika(block_loan_if_overdue=False)
        uyelik = uye()
        gecikmeli_yap(odunc_ver(uyelik))
        loan = odunc_ver(uyelik, **ISTISNA)
        assert not loan.has_override

    def test_gecikme_yoksa_istisna_kaydedilmez(self) -> None:
        loan = odunc_ver(uye(), **ISTISNA)
        assert not loan.has_override and loan.override_note == ""


# ============================================================ §9-7 tek açık ödünç


class Test97TekAcikOdunc:
    def test_baska_uyedeki_nusha_verilmez(self) -> None:
        copy = odunc_nushasi()
        odunc_ver(uye(), copy)
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uye(), copy)
        _red(hata, RED_BASKA_UYEDE)
        assert hata.value.message == "Bu kitap başka bir üyede."

    def test_ayni_uyedeki_nusha_ayri_iletiyle_reddedilir(self) -> None:
        uyelik = uye()
        copy = odunc_nushasi()
        odunc_ver(uyelik, copy)
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(uyelik, copy)
        _red(hata, RED_BU_UYEDE)

    def test_db_kisiti_ikinci_acik_oduncu_keser(self) -> None:
        loan = odunc_ver(uye())
        with pytest.raises(IntegrityError), transaction.atomic():
            Loan.objects.create(
                copy=loan.copy, membership=uye(), due_date=loan.due_date, status=LoanStatus.OPEN
            )

    def test_iadeden_sonra_yeniden_verilir(self) -> None:
        copy = odunc_nushasi()
        odunc_ver(uye(), copy)
        circulation.return_copy(copy=copy)
        assert odunc_ver(uye(), copy).status == LoanStatus.OPEN
        assert Loan.objects.filter(copy=copy).count() == 2


# ============================================================ §9-8 ayrılış


class Test98Ayrilis:
    def test_ayrilista_uyelik_sonlanir_sonlanmis_uye_iade_yapar(self) -> None:
        kisi = ogrenci()
        uyelik = uye(kisi)
        loan = odunc_ver(uyelik)

        persons.leave_student(kisi)
        uyelik.refresh_from_db()
        assert not uyelik.is_active
        assert persons.open_obligations(kisi) == ["1 açık ödünç var."]
        with pytest.raises(DolasimReddi):
            odunc_ver(uyelik)

        sonuc = circulation.return_copy(copy=loan.copy)

        assert sonuc.loan.status == LoanStatus.RETURNED
        assert persons.open_obligations(kisi) == []


# ============================================================ §9-12 kartsız ödünç


class Test912KartsizOdunc:
    def test_yalniz_yonetici_kipinde_ve_gerekceyle_kayit_isaretli(self) -> None:
        kisi = ogrenci()
        uye(kisi)
        uyelik = selectors_dolasim.find_active_membership_by_student_number(
            f"0{kisi.student_number}"
        )
        assert uyelik is not None

        loan = odunc_ver(uyelik, **KARTSIZ)

        loan.refresh_from_db()
        assert loan.cardless is True
        assert loan.cardless_reason == "CARD_NOT_WITH_MEMBER"
        assert _ham("kutuphane_loan", "cardless_reason", loan.pk) != "CARD_NOT_WITH_MEMBER"

    def test_gorevli_kipinde_kartsiz_odunc_403(self) -> None:
        uyelik = uye()
        KIP.gorevliye_gec()
        with pytest.raises(KipYetkisiz):
            odunc_ver(uyelik, **KARTSIZ)
        assert not Loan.objects.exists()

    def test_gerekce_kapali_listeden(self) -> None:
        with pytest.raises(ValidationError) as hata:
            odunc_ver(uye(), cardless_reason="Unuttu")
        assert "cardless_reason" in hata.value.message_dict

    def test_kartli_odunc_isaretsizdir(self) -> None:
        loan = odunc_ver(uye())
        assert loan.cardless is False and loan.cardless_reason == ""

    def test_db_kisiti_gerekcesiz_kartsiz_oduncu_reddeder(self) -> None:
        loan = odunc_ver(uye())
        with pytest.raises(IntegrityError), transaction.atomic():
            Loan.objects.filter(pk=loan.pk).update(cardless=True)


# ============================================================ yıl sonu son ödünç tarihi (§8.3)


class TestSonOduncTarihi:
    @pytest.mark.parametrize("kip", ["gorevli", "yonetici", "yonetici_istisna", "kartsiz"])
    def test_son_tarihten_sonra_hicbir_kipte_odunc_yok(self, bugun: list[date], kip: str) -> None:
        ders_yili()
        uyelik = uye()
        loan = odunc_ver(uyelik)
        politika(last_loan_date=date(2026, 9, 30))
        bugun[0] = date(2026, 10, 20)
        ek: dict[str, str] = {}
        if kip == "gorevli":
            KIP.gorevliye_gec()
        elif kip == "yonetici_istisna":
            gecikmeli_yap(loan)
            ek = ISTISNA
        elif kip == "kartsiz":
            ek = KARTSIZ

        with pytest.raises(DolasimReddi) as hata:
            circulation.checkout(copy=odunc_nushasi(), membership=uyelik, **ek)

        _red(hata, RED_SON_TARIH)
        if kip == "gorevli":
            # Görevli iletisi tarihsizdir (son sınıf tarihi sınıf düzeyini gösterirdi).
            assert hata.value.message == circulation.LAST_LOAN_DATE_STAFF_MESSAGE
            assert "30.09.2026" not in hata.value.message
        else:
            assert "30.09.2026" in hata.value.message
        # İade kilitlenmez.
        assert circulation.return_copy(copy=loan.copy).loan.status == LoanStatus.RETURNED

    def test_son_tarihe_kadar_verilir(self, bugun: list[date]) -> None:
        ders_yili()
        politika(last_loan_date=ACIK_GUN)
        assert odunc_ver(uye()).status == LoanStatus.OPEN

    def test_son_siniflar_icin_erken_tarih_yalniz_son_sinifa(self, bugun: list[date]) -> None:
        ders_yili()
        config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
        config.kademe = SchoolLevel.ORTAOGRETIM
        config.save()
        politika(last_loan_date=date(2027, 6, 1), last_loan_date_graduating=date(2026, 9, 20))
        son_sinif = uye(ogrenci(class_level=12))
        alt_sinif = uye(ogrenci(class_level=11))
        with pytest.raises(DolasimReddi) as hata:
            odunc_ver(son_sinif)
        _red(hata, RED_SON_TARIH)
        assert odunc_ver(alt_sinif).status == LoanStatus.OPEN

    def test_gorevli_kipinde_son_sinif_reddi_sinif_duzeyini_ele_vermez(
        self, bugun: list[date]
    ) -> None:
        """Son sınıf tarihi görevliye gösterilmez: iki ret aynı, tarihsiz iletidir (TB32)."""
        ders_yili()
        config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
        config.kademe = SchoolLevel.ORTAOGRETIM
        config.save()
        son_sinif = uye(ogrenci(class_level=12))
        alt_sinif = uye(ogrenci(class_level=11))
        politika(last_loan_date=date(2026, 9, 20), last_loan_date_graduating=date(2026, 9, 10))
        KIP.gorevliye_gec()
        iletiler = []
        for uyelik in (son_sinif, alt_sinif):
            with pytest.raises(DolasimReddi) as hata:
                odunc_ver(uyelik)
            _red(hata, RED_SON_TARIH)
            iletiler.append(hata.value.message)
        assert iletiler == [circulation.LAST_LOAN_DATE_STAFF_MESSAGE] * 2

    def test_gecen_yilin_tarihi_yeni_yilda_uygulanmaz(self, bugun: list[date]) -> None:
        ders_yili(baslangic=date(2026, 9, 7))
        politika(last_loan_date=date(2026, 6, 12))  # geçen yıl sonu, güncellenmemiş
        assert odunc_ver(uye()).status == LoanStatus.OPEN


# ============================================================ iade hiçbir durumda kilitlenmez


class TestIade:
    def test_iade_gorevli_kipinde_yapilir_nusha_rafa_doner(self) -> None:
        loan = odunc_ver(uye())
        KIP.gorevliye_gec()
        sonuc = circulation.return_copy(copy=loan.copy)
        assert sonuc.loan.returned_at is not None
        assert Copy.objects.get(pk=loan.copy_id).status == CopyStatus.AVAILABLE

    def test_gecikmeli_iade_gecikme_gununu_verir_ceza_yok(self) -> None:
        loan = gecikmeli_yap(odunc_ver(uye()), gun=4)
        sonuc = circulation.return_copy(copy=loan.copy)
        assert sonuc.overdue_days == 4
        assert sonuc.loan.status == LoanStatus.RETURNED

    @pytest.mark.parametrize(
        ("durum", "ileti"),
        [
            (CopyStatus.AVAILABLE, "Rafta — ödünç değil."),
            (CopyStatus.LOST, "Kayıp kaydında."),
            (CopyStatus.IN_REPAIR, "Onarımda."),
            (CopyStatus.DELIVERED, "Sınıf kitaplığında."),
            (CopyStatus.WITHDRAWN_LOST, "Kayıttan düşülmüş nüsha."),
        ],
    )
    def test_acik_oduncu_olmayan_nushada_durum_iletisi(self, durum: str, ileti: str) -> None:
        copy = odunc_nushasi()
        Copy.objects.filter(pk=copy.pk).update(status=durum)
        with pytest.raises(DolasimReddi) as hata:
            circulation.return_copy(copy=copy)
        _red(hata, RED_ACIK_ODUNC_YOK)
        assert hata.value.message == ileti

    def test_yirmi_altinci_odunc_de_barkodla_iade_edilir(self) -> None:
        """D9: OYS listede ilk 25 ödüncü gösterdiği için 26. iade edilemiyordu."""
        loans = [odunc_ver(uye()) for _ in range(30)]
        hedef = loans[25]
        sonuc = circulation.return_copy(copy=hedef.copy)
        assert sonuc.loan.pk == hedef.pk
        assert Loan.objects.filter(status=LoanStatus.OPEN).count() == 29

    def test_odunc_kaydindan_iade(self) -> None:
        loan = odunc_ver(uye())
        assert circulation.return_loan(loan=loan).loan.status == LoanStatus.RETURNED
        with pytest.raises(DolasimReddi):
            circulation.return_loan(loan=loan)

    def test_iade_zamani_ve_kayit_birlikte_yazilir(self) -> None:
        loan = odunc_ver(uye())
        once = timezone.now()
        circulation.return_copy(copy=loan.copy)
        loan.refresh_from_db()
        assert loan.returned_at is not None and loan.returned_at >= once
        with pytest.raises(IntegrityError), transaction.atomic():
            Loan.objects.filter(pk=loan.pk).update(returned_at=None)
