"""Dolaşım seçicileri — kalan hak, gecikmişler, ödünç kaydı, son işlemler, üyelik araması.

Profil yasağı (tasarım §3, CLAUDE.md §2-5): üye bazında konu ya da sınıf
dağılımı ÜRETİLMEZ; üyenin ödünç kaydı yalnız satırlardan oluşur ve konu,
sınıflama, bölüm taşımaz. Beklenmedik kapanış (T15): son oturumdaki ödünç ve
iadeler yöneticiye listelenir. Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.kutuphane import selectors_dolasim, serializers_uyelik
from apps.kutuphane.models import Loan, MemberType, TerminationReason
from apps.kutuphane.selectors_dolasim import TransactionKind
from apps.kutuphane.services import circulation, memberships
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    personel,
    personele_odunc_ac,
    politika,
    uye,
)
from apps.okul.models import MemberKind

pytestmark = pytest.mark.django_db


class TestKalanHak:
    def test_kalan_hak_sinirdan_acik_oduncler_dusulerek(self) -> None:
        uyelik = uye()
        assert selectors_dolasim.remaining_quota(uyelik) == 3
        odunc_ver(uyelik)
        odunc_ver(uyelik)
        assert selectors_dolasim.remaining_quota(uyelik) == 1
        assert selectors_dolasim.loan_limit(uyelik) == 3

    def test_ogretmen_bes_diger_personel_karar_yoksa_sifir(self) -> None:
        assert selectors_dolasim.loan_limit(uye(personel())) == 5
        personele_odunc_ac(max_loans_staff=2)
        staff = uye(personel(member_kind=MemberKind.STAFF))
        assert selectors_dolasim.loan_limit(staff) == 2
        politika(staff_loans_enabled=False)
        assert selectors_dolasim.remaining_quota(staff) == 0

    def test_sonlanmis_uyelikte_kalan_hak_sifir(self) -> None:
        uyelik = memberships.terminate_membership(uye(), reason=TerminationReason.MEMBER_REQUEST)
        assert selectors_dolasim.remaining_quota(uyelik) == 0

    def test_kisi_bazinda_toplu_sayilar_tekil_sayilarla_ayni(self) -> None:
        a, b, c = uye(), uye(), uye(personel())
        odunc_ver(a)
        gecikmeli_yap(odunc_ver(a))
        odunc_ver(c)

        sayilar = selectors_dolasim.loan_counts_by_person([a, b, c])

        for uyelik in (a, b, c):
            beklenen = (
                selectors_dolasim.open_loan_count(uyelik),
                selectors_dolasim.overdue_loan_count(uyelik),
            )
            assert sayilar.get(selectors_dolasim.person_key(uyelik), (0, 0)) == beklenen
        assert sayilar[selectors_dolasim.person_key(a)] == (2, 1)


class TestGecikmisler:
    def test_gecikmis_liste_iade_tarihine_gore_ve_sayi_kisisiz(self) -> None:
        yeni = gecikmeli_yap(odunc_ver(uye()), gun=2)
        eski = gecikmeli_yap(odunc_ver(uye()), gun=9)
        odunc_ver(uye())  # gecikmemiş
        iade = gecikmeli_yap(odunc_ver(uye()), gun=20)
        circulation.return_copy(copy=iade.copy)

        assert [lo.pk for lo in selectors_dolasim.overdue_loans()] == [eski.pk, yeni.pk]
        assert selectors_dolasim.overdue_count() == 2

    def test_bugun_iade_tarihi_olan_gecikmis_sayilmaz(self) -> None:
        loan = odunc_ver(uye())
        Loan.objects.filter(pk=loan.pk).update(due_date=timezone.localdate())
        loan.refresh_from_db()
        assert selectors_dolasim.overdue_count() == 0
        assert loan.overdue_days() == 0
        assert loan.overdue_days(timezone.localdate() + timedelta(days=3)) == 3


class TestOduncKaydi:
    def test_yalniz_bu_uyeligin_satirlari_en_yeni_once(self) -> None:
        uyelik = uye()
        ilk = odunc_ver(uyelik)
        circulation.return_copy(copy=ilk.copy)
        ikinci = odunc_ver(uyelik)
        odunc_ver(uye())

        kayit = list(selectors_dolasim.member_loan_history(uyelik))

        assert [lo.pk for lo in kayit] == [ikinci.pk, ilk.pk]

    def test_profil_yasagi_konu_ve_siniflama_dagilimi_uretilmez(self) -> None:
        """Seçici ve serializer kaynağında konu/sınıflama/bölüm alanına dokunulmaz."""
        yasak = (
            "subject",
            "classification",
            "dewey",
            "work__section",
            "copy__section",
            "Section",
            "okuduğu",
        )
        for modul in (selectors_dolasim, serializers_uyelik):
            kod = inspect.getsource(modul)
            for kelime in yasak:
                assert kelime not in kod, f"{modul.__name__}: {kelime}"
        alanlar = set(serializers_uyelik.MemberLoanSerializer.Meta.fields)
        assert not {a for a in alanlar if "subject" in a or "class" in a or "section" in a}


class TestSonIslemler:
    def test_oturumdan_onceki_odunc_ve_iadeler_en_yeni_once(self) -> None:
        sinir = timezone.now() + timedelta(seconds=30)
        verilen = odunc_ver(uye())
        iade_edilen = odunc_ver(uye())
        circulation.return_copy(copy=iade_edilen.copy)
        sonradan = odunc_ver(uye())
        Loan.objects.filter(pk=sonradan.pk).update(loaned_at=sinir + timedelta(minutes=1))

        islemler = selectors_dolasim.recent_transactions(before=sinir)

        turler = [(i.kind, i.loan.pk) for i in islemler]
        assert turler[0] == (TransactionKind.RETURN, iade_edilen.pk)
        assert set(turler) == {
            (TransactionKind.LOAN, verilen.pk),
            (TransactionKind.LOAN, iade_edilen.pk),
            (TransactionKind.RETURN, iade_edilen.pk),
        }
        assert islemler[0].label == "İade alındı"

    def test_liste_sinirlidir(self) -> None:
        for _ in range(5):
            odunc_ver(uye())
        islemler = selectors_dolasim.recent_transactions(
            before=timezone.now() + timedelta(seconds=5), limit=3
        )
        assert len(islemler) == 3

    def test_surec_baslangici_isaretlidir(self) -> None:
        assert selectors_dolasim.process_started_at() <= timezone.now()

    @pytest.mark.parametrize(
        ("deger", "beklenen"),
        [("beklenmedik", True), ("temiz", False), ("ilk", False), ("", False)],
    )
    def test_onceki_oturum_beklenmedik_mi(
        self, monkeypatch: pytest.MonkeyPatch, deger: str, beklenen: bool
    ) -> None:
        monkeypatch.setenv("KD_ONCEKI_OTURUM", deger)
        assert selectors_dolasim.previous_session_unexpected() is beklenen

    def test_degisken_yoksa_kart_gosterilmez(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("KD_ONCEKI_OTURUM", raising=False)
        assert selectors_dolasim.previous_session_unexpected() is False


class TestUyelikListesi:
    def test_ogrenciler_once_sinif_sube_okul_no_sonra_personel_adi(self) -> None:
        b = uye(ogrenci(class_level=10, class_section="Ç", student_number="3"))
        a = uye(ogrenci(class_level=10, class_section="C", student_number="7"))
        c = uye(ogrenci(class_level=9, class_section="B", student_number="100"))
        ozge = uye(personel(first_name="Özge"))
        oya = uye(personel(first_name="Oya"))

        sira = [m.pk for m in selectors_dolasim.memberships()]

        assert sira == [c.pk, a.pk, b.pk, oya.pk, ozge.pk]

    def test_turkce_ad_aramasi_okul_no_ve_kart_no_tam_eslesme(self) -> None:
        sahin = uye(ogrenci(first_name="ŞAHİN", last_name="Deneme", student_number="4321"))
        uye(ogrenci(first_name="Sahra", student_number="43210"))

        assert [m.pk for m in selectors_dolasim.memberships(search="şahin")] == [sahin.pk]
        assert [m.pk for m in selectors_dolasim.memberships(search="04321")] == [sahin.pk]
        kart = sahin.card_no
        assert [m.pk for m in selectors_dolasim.memberships(search=kart)] == [sahin.pk]
        assert selectors_dolasim.memberships(search="432") == []  # ön ek araması yok

    def test_suzgecler(self) -> None:
        ogr = uye(ogrenci(class_level=11, class_section="D"))
        ogrt = uye(personel())
        biten = memberships.terminate_membership(
            uye(ogrenci()), reason=TerminationReason.RECORD_ERROR
        )

        assert [m.pk for m in selectors_dolasim.memberships(member_type=MemberType.TEACHER)] == [
            ogrt.pk
        ]
        assert [m.pk for m in selectors_dolasim.memberships(status="TERMINATED")] == [biten.pk]
        assert [m.pk for m in selectors_dolasim.memberships(class_level=11, class_section="d")] == [
            ogr.pk
        ]


def test_bugun_fiksturu_gunu_sabitler(bugun: list[date]) -> None:
    assert timezone.localdate() == bugun[0]
    bugun[0] = date(2027, 1, 4)
    assert timezone.localdate() == date(2027, 1, 4)
    assert odunc_ver(uye(), odunc_nushasi()).due_date == date(2027, 1, 19)
