"""Çok okunanlar hesabı (F10 — tasarım §5.3, §5.10-12; A12).

Kod kapısı **§5.10-12: tek üyenin tekrarlanan ödünçleri bir eseri çok okunanlara
sokmaz** (`TestEsik`). Eşik ödünç kaydı sayısı değil, pencere içinde en az k FARKLI
üyedir (`LibraryPolicy.popular_min_members`); sıra farklı üye sayısına göredir ve
tabloya sayı yazılmaz. Pencereler (ay, dönem, dönemsiz ders yılı), kapanan pencerenin
son hesabı ve dondurulması, "anonimleştirmeden sonra yeniden hesaplanmaz" kuralı ve
bakım kapısı da burada sınanır. Vitrinin bu tablodan sayısız okuması
`katalog/tests/test_vitrin_cok_okunanlar.py`'dedir.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from django.utils import timezone

from apps.kutuphane.models import (
    Copy,
    KatalogPopuler,
    Loan,
    Membership,
    PopulerPencereTuru,
    Work,
)
from apps.kutuphane.services import circulation, populer
from apps.kutuphane.tests.dolasim_ortak import ders_yili, odunc_ver, ogrenci, politika, uye
from apps.kutuphane.tests.ortak import eser, nusha
from apps.okul.models import SchoolYear
from katalog.bakim import BakimKapisi

pytestmark = pytest.mark.django_db

AY = PopulerPencereTuru.AY
DONEM = PopulerPencereTuru.DONEM


def _an(gun: date, saat: int = 10) -> datetime:
    return timezone.make_aware(datetime.combine(gun, time(saat, 0)))


def _okut(copy: Copy, uyelik: Membership, gun: date, *, iade: bool = True) -> Loan:
    """Servis yoluyla ödünç verir (ve iade alır); verilme anını `gun`e çeker."""
    loan = odunc_ver(uyelik, copy)
    if iade:
        circulation.return_copy(copy=copy)
    Loan.objects.filter(pk=loan.pk).update(loaned_at=_an(gun))
    loan.refresh_from_db()
    return loan


def _eser_ve_nusha(baslik: str) -> tuple[Work, Copy]:
    work = eser(title=baslik, authors="Deneme Yazar")
    return work, nusha(work)


def _farkli_uyeler(copy: Copy, sayi: int, gun: date) -> list[Membership]:
    uyeler = [uye(ogrenci()) for _ in range(sayi)]
    for uyelik in uyeler:
        _okut(copy, uyelik, gun)
    return uyeler


def _sira(tur: str, pencere: str) -> list[int]:
    return list(
        KatalogPopuler.objects.filter(pencere_turu=tur, pencere=pencere)
        .order_by("sira")
        .values_list("eser_id", flat=True)
    )


def _donmus(tur: str, pencere: str) -> set[bool]:
    return set(
        KatalogPopuler.objects.filter(pencere_turu=tur, pencere=pencere).values_list(
            "dondu", flat=True
        )
    )


GUN = date(2026, 9, 24)


# ============================================================ §5.10-12: eşik k farklı üye


class TestEsik:
    def test_tek_uyenin_tekrarlanan_oduncleri_eseri_listeye_sokmaz(self) -> None:
        """§5.10-12: aynı üye aynı eseri on kez alsa da eser çok okunanlara girmez."""
        tekrar, tekrar_nusha = _eser_ve_nusha("Tekrar Tekrar Alınan")
        yaygin, yaygin_nusha = _eser_ve_nusha("Beş Farklı Üyenin Eseri")
        tek = uye(ogrenci())
        for _ in range(10):
            _okut(tekrar_nusha, tek, GUN)
        _farkli_uyeler(yaygin_nusha, 5, GUN)

        populer.hesapla(GUN)

        assert Loan.objects.filter(copy=tekrar_nusha).count() == 10
        assert _sira(AY, "2026-09") == [yaygin.pk]
        assert tekrar.pk not in _sira(AY, "2026-09")

    def test_esigin_bir_eksigi_girmez_esik_ayari_uygulanir(self) -> None:
        dort, dort_nusha = _eser_ve_nusha("Dört Üye")
        _farkli_uyeler(dort_nusha, 4, GUN)

        populer.hesapla(GUN)
        assert _sira(AY, "2026-09") == []

        politika(popular_min_members=3)
        populer.hesapla(GUN)
        assert _sira(AY, "2026-09") == [dort.pk]

    def test_sira_farkli_uye_sayisina_gore_odunc_sayisi_siraya_girmez(self) -> None:
        """Altı farklı üye > beş farklı üye — beşlinin ödünç SAYISI daha çok olsa da."""
        alti, alti_nusha = _eser_ve_nusha("Zeytin Ağacı")
        bes, bes_nusha = _eser_ve_nusha("Ayçiçeği")
        _farkli_uyeler(alti_nusha, 6, GUN)
        bes_uye = _farkli_uyeler(bes_nusha, 5, GUN)
        for _ in range(8):
            _okut(bes_nusha, bes_uye[0], GUN)

        populer.hesapla(GUN)

        assert _sira(AY, "2026-09") == [alti.pk, bes.pk]

    def test_esitlikte_kaynak_adinin_turkce_sirasi(self) -> None:
        c_eser, c_nusha = _eser_ve_nusha("Çınaraltı")
        d_eser, d_nusha = _eser_ve_nusha("Dağ Başı")
        b_eser, b_nusha = _eser_ve_nusha("Bahar")
        for copy in (d_nusha, c_nusha, b_nusha):
            _farkli_uyeler(copy, 5, GUN)

        populer.hesapla(GUN)

        # BINARY sırada "Ç" "D"den sonra gelirdi (T7).
        assert _sira(AY, "2026-09") == [b_eser.pk, c_eser.pk, d_eser.pk]

    def test_kisi_bagi_koparilmis_odunc_farkli_uye_sayilmaz(self) -> None:
        work, copy = _eser_ve_nusha("Kişisi Koparılmış")
        uyeler = _farkli_uyeler(copy, 5, GUN)
        Loan.objects.filter(membership=uyeler[0]).update(membership=None)

        populer.hesapla(GUN)

        assert _sira(AY, "2026-09") == []

    def test_silinmis_eser_listelenmez_en_cok_on_eser(self) -> None:
        politika(popular_min_members=3)
        eserler = []
        for i in range(12):
            work, copy = _eser_ve_nusha(f"Eser {i:02d}")
            _farkli_uyeler(copy, 3, GUN)
            eserler.append(work)
        eserler[0].delete()

        populer.hesapla(GUN)

        sira = _sira(AY, "2026-09")
        assert len(sira) == populer.EN_COK_SIRA
        assert eserler[0].pk not in sira

    def test_tabloda_sayi_yok_ozet_kisisiz(self) -> None:
        _, copy = _eser_ve_nusha("Kişisiz Özet")
        _farkli_uyeler(copy, 5, GUN)

        ozet = populer.hesapla(GUN)

        alanlar = {f.name for f in KatalogPopuler._meta.get_fields()}
        assert alanlar == {"id", "eser", "pencere_turu", "pencere", "sira", "hesaplanma", "dondu"}
        # Kapanan ağustosun son hesabı (boş) ve açık eylül; özet yalnız pencere ve adettir.
        assert ozet["windows"] == [
            {"window_type": AY, "window": "2026-08", "ranked": 0, "final": True},
            {"window_type": AY, "window": "2026-09", "ranked": 1, "final": False},
        ]
        assert set(ozet) == {"computed_on", "k_threshold", "windows"}


# ============================================================ pencereler


class TestPencereler:
    def test_ay_penceresi_takvim_ayidir(self) -> None:
        """Sınırlar yerel saatle: 31 Ağustos 23.00 eylüle girmez, 30 Eylül 23.00 girer."""
        work, copy = _eser_ve_nusha("Eylül Kitabı")
        _farkli_uyeler(copy, 3, date(2026, 9, 1))
        for uyelik in [uye(ogrenci()) for _ in range(2)]:
            loan = _okut(copy, uyelik, date(2026, 8, 31))
            Loan.objects.filter(pk=loan.pk).update(loaned_at=_an(date(2026, 8, 31), 23))

        populer.hesapla(date(2026, 9, 30))
        assert _sira(AY, "2026-09") == []

        for uyelik in [uye(ogrenci()) for _ in range(2)]:
            loan = _okut(copy, uyelik, date(2026, 9, 30))
            Loan.objects.filter(pk=loan.pk).update(loaned_at=_an(date(2026, 9, 30), 23))
        populer.hesapla(date(2026, 9, 30))

        assert _sira(AY, "2026-09") == [work.pk]
        p = populer.ay_penceresi(date(2026, 2, 10))
        assert (p.anahtar, p.bas, p.son) == ("2026-02", date(2026, 2, 1), date(2026, 2, 28))

    def test_donem_penceresi_ders_doneminden_anahtar_yil_yillarindan(self) -> None:
        ders_yili()
        SchoolYear.objects.update(name="Uzun Adlı Ders Yılı Örneği 26")
        work, copy = _eser_ve_nusha("Dönemin Kitabı")
        _farkli_uyeler(copy, 5, date(2026, 10, 5))

        populer.hesapla(date(2026, 10, 20))

        assert _sira(DONEM, "2026-2027/1") == [work.pk]
        p = populer.donem_penceresi(date(2027, 3, 1))
        assert p is not None and (p.anahtar, p.bas) == ("2026-2027/2", date(2027, 2, 8))

    def test_donem_tarihleri_yoksa_ders_yilinin_tamami_tek_pencere(self) -> None:
        SchoolYear.objects.create(
            name="2026-2027", start_date=date(2026, 9, 7), end_date=date(2027, 6, 25)
        )
        work, copy = _eser_ve_nusha("Dönemsiz Yıl")
        _farkli_uyeler(copy, 5, date(2026, 11, 2))

        populer.hesapla(date(2027, 3, 1))

        assert _sira(DONEM, "2026-2027") == [work.pk]

    def test_ders_yili_disinda_donem_penceresi_yok(self) -> None:
        ders_yili()
        assert populer.donem_penceresi(date(2027, 7, 15)) is None
        assert populer.donem_penceresi(date(2027, 1, 30)) is None  # yarıyıl tatili


# ============================================================ kapanan pencere, dondurma


class TestKapananPencere:
    def test_kapanan_ay_son_gunun_oduncleriyle_son_kez_hesaplanir_ve_dondurulur(self) -> None:
        """Kapıdaki iş günün başında koşar: son günün ödünçleri ertesi gün yazılır."""
        work, copy = _eser_ve_nusha("Son Gün")
        populer.hesapla(date(2026, 9, 30))  # sabah: henüz ödünç yok
        assert _sira(AY, "2026-09") == []
        _farkli_uyeler(copy, 5, date(2026, 9, 30))  # öğleden sonra

        populer.hesapla(date(2026, 10, 1))

        assert _sira(AY, "2026-09") == [work.pk]
        assert _donmus(AY, "2026-09") == {True}
        # Dondurulmuş pencere bir daha yazılmaz: yeni veri gelse de sıra değişmez.
        diger, diger_nusha = _eser_ve_nusha("Geç Gelen")
        _farkli_uyeler(diger_nusha, 6, date(2026, 9, 29))
        populer.hesapla(date(2026, 10, 2))
        assert _sira(AY, "2026-09") == [work.pk]

    def test_kapanan_donem_son_kez_hesaplanir_acik_donem_dondurulmaz(self) -> None:
        ders_yili()
        birinci, birinci_nusha = _eser_ve_nusha("Birinci Dönem")
        _farkli_uyeler(birinci_nusha, 5, date(2027, 1, 20))
        ikinci, ikinci_nusha = _eser_ve_nusha("İkinci Dönem")
        _farkli_uyeler(ikinci_nusha, 5, date(2027, 2, 10))

        populer.hesapla(date(2027, 2, 15))

        assert _sira(DONEM, "2026-2027/1") == [birinci.pk]
        assert _donmus(DONEM, "2026-2027/1") == {True}
        assert _sira(DONEM, "2026-2027/2") == [ikinci.pk]
        assert _donmus(DONEM, "2026-2027/2") == {False}

    def test_anonimlestirmeden_sonra_yeniden_hesaplanmaz(self) -> None:
        """Son hesap süresini aşmış kapanmış pencere hesaplanmadan dondurulur; kişi bağı
        sonradan koparılsa da (§6.4) dondurulmuş sıra değişmez."""
        work, copy = _eser_ve_nusha("Geçen Yılın Kitabı")
        uyeler = _farkli_uyeler(copy, 5, date(2026, 5, 12))
        populer.hesapla(date(2026, 5, 20))  # mayısta açık pencere yazıldı
        assert _sira(AY, "2026-05") == [work.pk]
        # Program aylarca açılmadı; bu arada kişi bağları koparıldı (anonimleştirme).
        Loan.objects.filter(membership__in=uyeler).update(membership=None)

        populer.hesapla(date(2026, 9, 24))

        assert _sira(AY, "2026-05") == [work.pk]
        assert _donmus(AY, "2026-05") == {True}
        assert (date(2026, 9, 24) - date(2026, 5, 31)).days > populer.SON_HESAP_GUN

    def test_dondurulmus_pencere_hesaba_girmez(self) -> None:
        work, copy = _eser_ve_nusha("Dondurulmuş")
        KatalogPopuler.objects.create(
            eser=work,
            pencere_turu=AY,
            pencere="2026-08",
            sira=1,
            hesaplanma=date(2026, 9, 1),
            dondu=True,
        )
        _farkli_uyeler(nusha(eser(title="Ağustos")), 5, date(2026, 8, 20))

        sonuclar = populer._siralama_hesapla(date(2026, 9, 3))

        assert ("AY", "2026-08") not in {(s.pencere.tur, s.pencere.anahtar) for s in sonuclar}
        assert _sira(AY, "2026-08") == [work.pk]


# ============================================================ kapı ve elle yeniden hesap


class TestKapi:
    def test_gunluk_is_hesaplar_ve_tamam_doner(self) -> None:
        work, copy = _eser_ve_nusha("Kapıdan Geçen")
        _farkli_uyeler(copy, 5, GUN)

        assert populer.gunluk_is(GUN, kapi=BakimKapisi()) == "tamam"
        assert _sira(AY, "2026-09") == [work.pk]

    def test_yeniden_hesapla_bakimda_calismaz(self) -> None:
        kapi = BakimKapisi()
        kapi.bakima_al(bekleme_sn=0.01)

        with pytest.raises(populer.BakimSuruyor):
            populer.yeniden_hesapla(GUN, kapi=kapi)

    def test_kapi_isi_yerel_gunle_calisir(self, bugun: list[date]) -> None:
        work, copy = _eser_ve_nusha("Yerel Gün")
        _farkli_uyeler(copy, 5, bugun[0])

        assert populer.kapi_isi() is True
        assert _sira(AY, f"{bugun[0]:%Y-%m}") == [work.pk]
