"""Yıl sonu kütüphane raporu (F8 — Md. 12/1, Kılavuz 2.4; E9 verisi).

Kod kapısı: **E9'da kişisel veri yok** — `TestKisiselVeriYok` sentetik adlarla
(öğrenci, öğretmen, bağışçı, komisyon, harcama yetkilisi, sorumlu notu) dolu bir
yıl kurar ve raporun BÜTÜN çıktısını (servis sözlüğü ve API yanıtı) tarar. Profil
yasağı (CLAUDE.md §2-5): üye türü ve sınıf düzeyi kırılımı k farklı üyenin
altında sayı göstermez; üye bazında hiçbir alan yoktur. **Türetme testi**
(`TestTamamlayiciGizleme`): basılan toplamlardan çıkarma yapılarak k'dan az farklı
üyeye ait bir sayı bulunamaz.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane import selectors_yil_raporu
from apps.kutuphane.models import AcquisitionMethod, AnnualLibraryReview, Loan
from apps.kutuphane.services import (
    annual_review,
    circulation,
    donations,
    loss_damage,
    memberships,
    rare_works,
    weeding,
)
from apps.kutuphane.tests.ayiklama_ortak import (
    DEVRALAN_OKUL,
    ayiklama_karari,
    kalem_ekle,
    onaya_kadar,
    raftaki,
    teklif,
)
from apps.kutuphane.tests.dolasim_ortak import (
    odunc_ver,
    ogrenci,
    personel,
    personele_odunc_ac,
    uye,
)
from apps.kutuphane.tests.ortak import edinim, eser, karar, nusha
from apps.kutuphane.tests.teslim_ortak import etkin_yil, ogretmen, sube, teslim_et
from apps.okul.models import SchoolYear

pytestmark = pytest.mark.django_db


# ============================================================ kişisel veri yok (kod kapısı)


SENTINELLER = {
    "ogrenci_ad": "Yilsonuogrenciad",
    "ogrenci_soyad": "Yilsonuogrencisoyad",
    "okul_no": "731246",
    "ogretmen_ad": "Yilsonuogretmenad",
    "personel_ad": "Yilsonupersonelad",
    "bagisci": "Yilsonubagisci",
    "baskan": "Yilsonubaskan",
    "katilimci": "Yilsonukatilimci",
    "harcama_yetkilisi": "Yilsonuharcamayetkilisi",
    "tmy_komisyonu": "Yilsonutmykomisyonu",
    "sorumlu_notu": "Yilsonusorumlunotu",
    "hasar_notu": "Yilsonuhasarnotu",
}
#: Rapor çıktısında hiçbir ANAHTAR bu parçaları taşımaz (kişi ya da üye bazında alan).
YASAK_ANAHTAR_PARCALARI = (
    "name",
    "student",
    "personnel",
    "member_id",
    "membership",
    "card",
    "note",
    "donor",
    "responsible",
    "approved_by",
    "person",
)


def _anahtarlar(veri: Any) -> set[str]:
    if isinstance(veri, dict):
        return set(veri) | {a for d in veri.values() for a in _anahtarlar(d)}
    if isinstance(veri, list):
        return {a for d in veri for a in _anahtarlar(d)}
    return set()


def _dolu_yil() -> tuple[SchoolYear, list[str]]:
    """Kişi verisiyle dolu bir ders yılı; dönen liste raporda GEÇMEMESİ gereken izlerdir."""
    yil = etkin_yil()
    bugun = timezone.localdate()
    izler: list[str] = []
    # Üyeler, kartlar, ödünçler (biri kartsız, biri iade edilmiş).
    ogr = ogrenci(
        first_name=SENTINELLER["ogrenci_ad"],
        last_name=SENTINELLER["ogrenci_soyad"],
        student_number=SENTINELLER["okul_no"],
    )
    ogr_uyelik = memberships.create_membership(student=ogr)
    hoca = ogretmen(first_name=SENTINELLER["ogretmen_ad"], last_name="Deneme")
    hoca_uyelik = uye(hoca)
    memur = personel(first_name=SENTINELLER["personel_ad"], member_kind="STAFF")
    izler += [ogr_uyelik.card_no, hoca_uyelik.card_no]
    odunc_ver(ogr_uyelik)
    circulation.return_copy(copy=odunc_ver(ogr_uyelik).copy)
    circulation.checkout(
        copy=raftaki("Kartsız Verilen"), membership=hoca_uyelik, cardless_reason="CARD_LOST"
    )
    # Teslim (şube ve öğretmen), kayıp ve hasar dosyası, onarım.
    teslim_et([raftaki("Sınıfa Giden")], section=sube(10, "B"))
    teslim_et([raftaki("Öğretmene Giden")], personnel=hoca)
    kayip = odunc_ver(ogr_uyelik)
    loss_damage.report_lost(copy=kayip.copy, responsible_note=SENTINELLER["sorumlu_notu"])
    loss_damage.open_damage_case(
        copy=raftaki("Hasarlı"), responsible_note=SENTINELLER["hasar_notu"], send_to_repair=True
    )
    # Bağış (bağışçı ve komisyon adları şifreli).
    bagis_karari = karar(
        chair_name=SENTINELLER["baskan"],
        participants_text=SENTINELLER["katilimci"],
        decision_date=bugun,
    )
    on_kayit = donations.create_intake(
        donor_name=SENTINELLER["bagisci"],
        received_date=bugun,
        items=[{"title": "Bağış Eseri", "authors": "Deneme Yazar", "copies": 2}],
    )
    donations.apply_decision(
        on_kayit,
        commission_decision=bagis_karari,
        accepted_ids=list(on_kayit.items.values_list("pk", flat=True)),
    )
    # Uygulanmış ayıklama (harcama yetkilisi ve TMY komisyonu adları şifreli).
    batch = teklif()
    kalem_ekle(batch, raftaki("Yıpranmış"), "OBSOLETE")
    kalem_ekle(
        batch, raftaki("Düzeye Uygun Değil"), "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL
    )
    onaya_kadar(
        batch,
        approved_by_name=SENTINELLER["harcama_yetkilisi"],
        tmy_commission_members="\n".join(f"{SENTINELLER['tmy_komisyonu']} {i}" for i in range(3)),
    )
    weeding.apply_batch(batch)
    # Nadir eser listesi.
    liste = rare_works.create_submission(commission_decision=ayiklama_karari())
    rare_works.add_copies(liste, copy_ids=[raftaki("Yazma", is_rare_or_manuscript=True).pk])
    del memur
    return yil, izler


class TestKisiselVeriYok:
    def test_rapor_sayilari_hicbir_kisi_izi_tasimaz(self) -> None:
        yil, izler = _dolu_yil()
        veri = selectors_yil_raporu.annual_review_stats(yil)
        metin = json.dumps(veri, ensure_ascii=False, default=str).casefold()

        for ad, deger in SENTINELLER.items():
            assert deger.casefold() not in metin, f"{ad} raporda geçti"
        for iz in izler:
            assert iz.casefold() not in metin
        yasak = {a for a in _anahtarlar(veri) if any(p in a for p in YASAK_ANAHTAR_PARCALARI)}
        assert yasak == set(), yasak
        # Gezinti gerçekten veriye ulaştı (boş rapor yanlış yeşil verirdi).
        assert veri["circulation"]["loans"] == 4
        assert veri["weeding"]["withdrawn"] == 1 and veri["weeding"]["transferred"] == 1

    def test_sonlandirilmis_rapor_ve_api_yaniti_da_kisi_izi_tasimaz(self) -> None:
        yil, izler = _dolu_yil()
        rapor = annual_review.create_review(school_year=yil)
        annual_review.update_review(rapor, findings="Raflar düzenlendi.", document_no="E-9")
        annual_review.finalize_review(rapor)

        yanit = APIClient().get(f"/api/v1/library/annual-reviews/{rapor.pk}/")
        assert yanit.status_code == 200
        metin = yanit.content.decode("utf-8").casefold()
        for deger in [*SENTINELLER.values(), *izler]:
            assert deger.casefold() not in metin
        assert yanit.json()["stats"]["circulation"]["loans"] == 4

    def test_uye_bazinda_alan_yok_ve_kirilimlar_k_esikli(self) -> None:
        etkin_yil()
        # 9. sınıf: 3 farklı üye (k=5'in altı) — sayı gösterilmez.
        for _ in range(3):
            odunc_ver(uye(ogrenci(class_level=9)))
        # 10. sınıf: 5 farklı üye — tek başına eşiği geçer...
        for _ in range(5):
            odunc_ver(uye(ogrenci(class_level=10)))
        # Öğretmen: tek üye — gösterilmez.
        odunc_ver(uye(ogretmen()))

        dolasim = selectors_yil_raporu.annual_review_stats(etkin_yil())["circulation"]

        assert dolasim["k_threshold"] == 5
        # ...ama toplam (9) basıldığından "öğrenci 8" tek öğretmenin sayısını (9 − 8 = 1),
        # "10. sınıf 5" gizli 9. sınıfı (8 − 5 = 3) ele verirdi: tamamlayıcı gizleme
        # bu küçük yılda bütün kırılımı kapatır.
        assert dolasim["by_class_level"] == [
            {"class_level": 9, "loans": None, "below_threshold": True},
            {"class_level": 10, "loans": None, "below_threshold": True},
        ]
        assert dolasim["by_member_type"] == {
            "STUDENT": {"loans": None, "below_threshold": True},
            "TEACHER": {"loans": None, "below_threshold": True},
            "STAFF": {"loans": None, "below_threshold": True},
        }
        assert dolasim["loans"] == 9 and dolasim["distinct_borrowers"] == 9
        # Tek öğretmen üye: aktif üye sayısı da eşik altında gösterilmez.
        assert dolasim["active_members"] == {"STUDENT": 8, "TEACHER": None, "STAFF": 0}


# ============================================================ tamamlayıcı gizleme (türetme testi)


def _gercek_farkli(kosul: Q) -> int:
    """Testin bildiği gerçek: grubun ödünç alan farklı üye sayısı (rapor bunu basmaz)."""
    return int(Loan.objects.filter(kosul).values("membership_id").distinct().count())


def _turetme_denetimi(dolasim: dict[str, Any]) -> None:
    """Basılan sayılarla yapılabilen her çıkarma, k'dan az farklı üyeye ait bir sayı vermez.

    İki eşitlik vardır: toplam = öğrenci + öğretmen + diğer personel; öğrenci = sınıf
    düzeyleri + sınıf düzeyi kaydı olmayan öğrenciler. Okuyucunun hesaplayabildiği
    "toplam − görünenler" (ve öğrenci görünürse "öğrenci − görünen düzeyler") her
    zaman ya sıfır kişiye ya da en az k farklı üyeye aittir.
    """
    k = int(dolasim["k_threshold"])
    tur_q = {
        "STUDENT": Q(membership__student__isnull=False),
        "TEACHER": Q(membership__personnel__member_kind="TEACHER"),
        "STAFF": Q(membership__personnel__isnull=False)
        & ~Q(membership__personnel__member_kind="TEACHER"),
    }
    gizli_tur = [t for t, h in dolasim["by_member_type"].items() if h["loans"] is None]
    gizli_duzey = [h["class_level"] for h in dolasim["by_class_level"] if h["loans"] is None]
    duzeysiz = Q(membership__student__isnull=False, membership__student__class_level__isnull=True)
    duzeyler_q = Q(membership__student__class_level__in=gizli_duzey) | duzeysiz

    def birlesim(*kosullar: Q) -> Q:
        sonuc = Q(pk__in=[])
        for kosul in kosullar:
            sonuc |= kosul
        return sonuc

    if "STUDENT" in gizli_tur:
        diger = [tur_q[t] for t in gizli_tur if t != "STUDENT"]
        n = _gercek_farkli(birlesim(*diger, duzeyler_q))
        assert n == 0 or n >= k, f"toplamdan türetilen grup {n} farklı üyeye ait"
    else:
        n = _gercek_farkli(birlesim(*[tur_q[t] for t in gizli_tur]))
        assert n == 0 or n >= k, f"toplam − görünen türler {n} farklı üyeye ait"
        n = _gercek_farkli(duzeyler_q)
        assert n == 0 or n >= k, f"öğrenci − görünen düzeyler {n} farklı üyeye ait"
    for hucre in dolasim["by_class_level"]:
        if hucre["loans"] is not None:
            n = _gercek_farkli(Q(membership__student__class_level=hucre["class_level"]))
            assert n >= k
    for tur, hucre in dolasim["by_member_type"].items():
        if hucre["loans"] is not None:
            assert _gercek_farkli(tur_q[tur]) >= k


class TestTamamlayiciGizleme:
    """Bulgu (F8 denetimi, 25.09.2026): eşik altındaki grup, basılan toplamdan çıkarılarak
    geri hesaplanabiliyordu — "grubun sayısı gösterilmez" notu yanlış güvence veriyordu."""

    def test_denetimin_senaryosu_tek_ogrenci_ve_tek_ogretmen_turetilemez(self) -> None:
        """9. ve 10. sınıftan beşer öğrenci; tek 11. sınıf öğrencisi 3, tek öğretmen 2 ödünç."""
        etkin_yil()
        for _ in range(5):
            odunc_ver(uye(ogrenci(class_level=9)))
        for _ in range(5):
            odunc_ver(uye(ogrenci(class_level=10)))
        tek = uye(ogrenci(class_level=11))
        for _ in range(3):
            odunc_ver(tek)
        hoca = uye(ogretmen())
        for _ in range(2):
            odunc_ver(hoca)

        dolasim = selectors_yil_raporu.annual_review_stats(etkin_yil())["circulation"]

        assert dolasim["loans"] == 15
        turler = {t: h["loans"] for t, h in dolasim["by_member_type"].items()}
        assert turler == {"STUDENT": None, "TEACHER": None, "STAFF": None}
        duzeyler = {h["class_level"]: h["loans"] for h in dolasim["by_class_level"]}
        # Görünen düzey kalır (10. sınıf); 9. sınıf tamamlayıcı olarak gizlenir.
        assert duzeyler == {9: None, 10: 5, 11: None}
        assert dolasim["active_members"]["TEACHER"] is None
        _turetme_denetimi(dolasim)

    def test_buyuk_yilda_yalniz_gereken_hucre_gizlenir(self) -> None:
        """Öğrenci ve iki sınıf düzeyi görünür kalır; tek diğer personel için öğretmen de gizlenir."""
        etkin_yil()
        for duzey in (9, 10):
            for _ in range(6):
                odunc_ver(uye(ogrenci(class_level=duzey)))
        for _ in range(5):
            odunc_ver(uye(ogretmen()))
        personele_odunc_ac()
        odunc_ver(uye(personel(member_kind="STAFF")))

        dolasim = selectors_yil_raporu.annual_review_stats(etkin_yil())["circulation"]

        turler = {t: h["loans"] for t, h in dolasim["by_member_type"].items()}
        assert turler == {"STUDENT": 12, "TEACHER": None, "STAFF": None}
        assert {h["class_level"]: h["loans"] for h in dolasim["by_class_level"]} == {9: 6, 10: 6}
        _turetme_denetimi(dolasim)

    def test_sinif_duzeyi_olmayan_ogrenci_duzey_kirilimindan_turetilemez(self) -> None:
        """Öğrenci − düzeyler = düzeysiz öğrencinin ödüncü; o da korunur."""
        etkin_yil()
        for duzey in (9, 10):
            for _ in range(5):
                odunc_ver(uye(ogrenci(class_level=duzey)))
        duzeysiz = uye(ogrenci(class_level=None))
        for _ in range(3):  # Md. 18 sayı sınırı
            odunc_ver(duzeysiz)

        dolasim = selectors_yil_raporu.annual_review_stats(etkin_yil())["circulation"]

        assert dolasim["by_member_type"]["STUDENT"]["loans"] == 13
        duzeyler = {h["class_level"]: h["loans"] for h in dolasim["by_class_level"]}
        assert sorted(duzeyler) == [9, 10] and list(duzeyler.values()).count(None) == 1
        _turetme_denetimi(dolasim)


# ============================================================ bölümler ve dönem


class TestRaporBolumleri:
    def test_kazandirilanlar_edinim_yoluna_gore(self) -> None:
        yil = etkin_yil()
        bugun = timezone.localdate()
        alim = edinim(method=AcquisitionMethod.PURCHASE, date=bugun)
        for i in range(3):
            nusha(eser(title=f"Alınan {i}"), alim)
        nusha(eser(title="Eski Yıldan"), edinim(date=yil.start_date - timedelta(days=30)))

        kazanilan = selectors_yil_raporu.annual_review_stats(yil)["acquisitions"]
        assert kazanilan["copies_by_method"]["PURCHASE"] == 3
        assert kazanilan["total_copies"] == 3 and kazanilan["works"] == 3

    def test_programa_aktarim_kazandirilan_sayilmaz(self) -> None:
        """İlk yıl: mevcut koleksiyonun aktarımı "yıl içinde kazandırılan" diye raporlanmaz."""
        yil = etkin_yil()
        bugun = timezone.localdate()
        aktarim = edinim(method=AcquisitionMethod.EXISTING_STOCK, date=bugun)
        for i in range(6):
            nusha(eser(title=f"Aktarılan {i}"), aktarim)
        fazla = edinim(method=AcquisitionMethod.INVENTORY_FOUND, date=bugun)
        nusha(eser(title="Sayım Fazlası"), fazla)
        alim = edinim(method=AcquisitionMethod.PURCHASE, date=bugun)
        nusha(eser(title="Alınan"), alim)

        kazanilan = selectors_yil_raporu.annual_review_stats(yil)["acquisitions"]
        assert kazanilan["total_copies"] == 1 and kazanilan["works"] == 1
        assert kazanilan["register_entry_copies"] == 7
        assert kazanilan["copies_by_method"]["EXISTING_STOCK"] == 6

    def test_tespitler_onarim_hasar_kayip_sayilari(self) -> None:
        yil = etkin_yil()
        onarilan = raftaki("Onarılan")
        loss_damage.send_to_repair(onarilan)
        loss_damage.return_from_repair(onarilan)
        loss_damage.open_damage_case(copy=raftaki("Hasarlı"), send_to_repair=True)
        dosya = loss_damage.report_lost(copy=raftaki("Kaybolan"))
        loss_damage.resolve_case(dosya, resolution="WRITE_OFF_PROPOSED")

        tespit = selectors_yil_raporu.annual_review_stats(yil)["findings"]
        assert (tespit["repairs_sent"], tespit["repairs_returned"], tespit["in_repair_now"]) == (
            2,
            1,
            1,
        )
        assert (tespit["damage_cases"], tespit["loss_cases"]) == (1, 1)
        assert tespit["resolutions"]["WRITE_OFF_PROPOSED"] == 1
        assert tespit["write_off_proposals"] == 1 and tespit["lost_copies_now"] == 1

    def test_koleksiyon_ozeti_elde_bulunani_sayar(self) -> None:
        yil = etkin_yil()
        batch = teklif()
        kalem_ekle(batch, raftaki("Düşülen"))
        raftaki("Kalan", is_reference=True)
        onaya_kadar(batch)
        weeding.apply_batch(batch)

        koleksiyon = selectors_yil_raporu.annual_review_stats(yil)["collection"]
        assert koleksiyon["register_count"] == 2
        assert koleksiyon["in_stock_count"] == 1
        assert koleksiyon["status_counts"]["WITHDRAWN_WEEDED"] == 1
        assert koleksiyon["reference_count"] == 1

    def test_donem_sonraki_ders_yilinin_basina_dek(self) -> None:
        yil = etkin_yil()
        sonraki = SchoolYear.objects.create(
            name="Sonraki", start_date=date(2027, 9, 13), end_date=date(2028, 6, 23)
        )
        assert selectors_yil_raporu.report_period(yil) == (yil.start_date, date(2027, 9, 12))
        bugun = date(2028, 7, 10)
        assert selectors_yil_raporu.report_period(sonraki, today=bugun) == (
            sonraki.start_date,
            bugun,
        )


# ============================================================ rapor kaydı


class TestRaporKaydi:
    def test_ders_yili_basina_tek_rapor(self) -> None:
        yil = etkin_yil()
        annual_review.create_review(school_year=yil)
        with pytest.raises(ValidationError, match="zaten var"):
            annual_review.create_review()

    def test_sonlandirma_sayilari_dondurur_geri_alma_canlandirir(self) -> None:
        yil = etkin_yil()
        odunc_ver(uye())
        rapor = annual_review.create_review(school_year=yil)
        annual_review.finalize_review(rapor)
        odunc_ver(uye())

        dondurulmus = AnnualLibraryReview.objects.get(pk=rapor.pk)
        assert annual_review.review_stats(dondurulmus)["circulation"]["loans"] == 1
        with pytest.raises(ValidationError, match="Sonlandırılmış"):
            annual_review.update_review(dondurulmus, findings="Değişiklik")

        acik = annual_review.reopen_review(dondurulmus)
        assert acik.stats is None
        assert annual_review.review_stats(acik)["circulation"]["loans"] == 2

    def test_tarih_ileri_olamaz_bilinmeyen_alan_reddedilir(self) -> None:
        rapor = annual_review.create_review(school_year=etkin_yil())
        with pytest.raises(ValidationError, match="bugünden sonra"):
            annual_review.update_review(
                rapor, document_date=timezone.localdate() + timedelta(days=1)
            )
        with pytest.raises(ValidationError):
            annual_review.update_review(rapor, stats={"sahte": 1})

    def test_yil_sonu_ozeti_raporun_durumunu_verir_adim_rayi_degismez(self) -> None:
        from apps.kutuphane.services import yil_akislari

        yil = etkin_yil()
        assert yil_akislari.year_end_summary().annual_review is None
        rapor = annual_review.create_review(school_year=yil)
        ozet = yil_akislari.year_end_summary()
        assert ozet.annual_review == {"id": rapor.pk, "is_finalized": False}
        assert set(ozet.steps) == {"dates", "collection", "graduating", "clearance"}
        annual_review.finalize_review(rapor)
        yanit = APIClient().get("/api/v1/library/year-flows/").json()
        assert yanit["year_end"]["annual_review"] == {"id": rapor.pk, "is_finalized": True}
