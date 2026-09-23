"""`kutuphane` modelleri — kısıtlar, ödünç verilebilirlik türetimi, yumuşak silme.

F2 kod kapısının model tarafı: nüsha kuralları, barkodun yeniden kullanılmaması
ve "silinen eser/nüsha sayaçlarda ve aramada görünmez" tuzağı (CLAUDE.md §3).
"""

from __future__ import annotations

import itertools

import pytest
from django.db import IntegrityError, transaction

from apps.kutuphane import selectors
from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    CommissionDecisionType,
    Copy,
    CopyStatus,
    LabelCalibration,
    LabelSheetTemplate,
    LibraryPolicy,
    ResourceType,
    Section,
    Work,
)
from apps.kutuphane.tests.ortak import (
    VARSAYILAN_TARIH,
    bolum,
    edinim,
    eser,
    karar,
    nusha,
    nusha_sayaclari,
)


@pytest.mark.django_db
class TestPolitikaSingleton:
    def test_kayit_yokken_kaydedilmemis_varsayilan_doner(self) -> None:
        policy = LibraryPolicy.load()
        assert policy.max_loans_student == 3
        assert policy.max_loans_teacher == 5
        assert LibraryPolicy.objects.count() == 0  # okuma yazmaz

    def test_odunc_suresi_alani_yoktur(self) -> None:
        """Md. 18 süreyi sabitler (D19): ayar alanı OLMAMALIDIR."""
        alanlar = {f.name for f in LibraryPolicy._meta.get_fields()}
        assert "loan_period_days" not in alanlar


@pytest.mark.django_db
class TestBolum:
    def test_ayni_ad_iki_kez_acilamaz(self) -> None:
        bolum(name="Tarih")
        with pytest.raises(IntegrityError), transaction.atomic():
            Section.objects.create(name="Tarih")

    def test_silinen_bolumun_adi_yeniden_kullanilabilir(self) -> None:
        eski = bolum(name="Tarih")
        eski.delete()
        yeni = bolum(name="Tarih")
        assert yeni.pk != eski.pk


@pytest.mark.django_db
class TestNushaKimligi:
    def test_barkod_ve_kayit_no_ayni_sayidir(self) -> None:
        copy = nusha()
        assert copy.accession_no == int(copy.barcode)

    def test_barkod_yeniden_kullanilmaz(self) -> None:
        """Silinen nüshanın numarası başka nüshaya verilmez (düz unique)."""
        work = eser()
        acquisition = edinim()
        birinci = nusha(work, acquisition)
        birinci.delete()  # yumuşak silme
        ikinci = nusha(work, acquisition)
        assert ikinci.barcode != birinci.barcode
        with pytest.raises(IntegrityError), transaction.atomic():
            Copy.objects.create(
                work=work,
                acquisition=acquisition,
                accession_no=999_999_999,
                barcode=birinci.barcode,
            )

    def test_kayit_no_da_tekildir(self) -> None:
        work = eser()
        acquisition = edinim()
        copy = nusha(work, acquisition)
        with pytest.raises(IntegrityError), transaction.atomic():
            Copy.objects.create(
                work=work,
                acquisition=acquisition,
                accession_no=copy.accession_no,
                barcode="2099999999",
            )


@pytest.mark.django_db
class TestOduncVerilebilirlik:
    def test_rafta_duran_kitap_odunc_verilir(self) -> None:
        assert nusha().is_loanable is True

    def test_danisma_kaynagi_odunc_verilmez(self) -> None:
        copy = nusha(is_reference=True)
        assert copy.is_loanable is False
        assert copy.not_loanable_reason == "Ödünç verilmez — kütüphanede okunur."

    def test_piyasada_mevcudu_olmayan_odunc_verilmez(self) -> None:
        copy = nusha(is_out_of_print=True)
        assert copy.is_loanable is False

    def test_sureli_yayin_odunc_verilmez(self) -> None:
        dergi = eser(title="Bilim ve Teknik", resource_type=ResourceType.PERIODICAL)
        copy = nusha(dergi, is_bound_periodical=True)
        assert copy.is_loanable is False
        assert "Süreli yayın" in copy.not_loanable_reason

    def test_raftan_cikan_kitap_odunc_verilmez(self) -> None:
        copy = nusha()
        copy.status = CopyStatus.ON_LOAN
        copy.save(update_fields=["status"])
        assert copy.is_loanable is False

    def test_dijital_kaynagin_nushasi_odunc_verilmez(self) -> None:
        """Dijital kaynak rafta durmaz, elden ele geçmez (Md. 14/1-a mantığı).

        Nüsha ancak iki servis kapısı da delinirse doğar (`ensure_copy_allowed`,
        `ensure_work_type_change`); o hâlde bile ödünç verilebilir GÖRÜNMEMELİ
        ve kullanıcıya gerekçe gösterilmelidir. Hâl burada ham `update` ile
        kurulur — servisten geçirilemez, çünkü servis onu reddeder.
        """
        work = eser(title="E-kitap Deneme")
        yaratilan = nusha(work)
        Work.objects.filter(pk=work.pk).update(resource_type=ResourceType.EBOOK)

        copy = Copy.objects.select_related("work").get(pk=yaratilan.pk)
        assert copy.is_loanable is False
        assert copy.not_loanable_reason == "Dijital kaynak — ödünç verilmez."
        assert not Copy.objects.filter(selectors.LOANABLE_Q, pk=copy.pk).exists()

    def test_oduncluk_suzgeci_ozellikle_ayni_sonucu_verir(self) -> None:
        """`Copy.is_loanable` ile `selectors.LOANABLE_Q` TEK türetimdir (F2 kapısı).

        Bütün kombinasyonlar kurulur; iki yol ayrışırsa masada ödünç verilen bir
        kitap listede "ödünç verilebilir" görünmezdi (ya da tersi). Ürün DİJİTAL
        ekseni de kapsar: iki türetim aynı yönde eksikse kapı yeşil kalır ama
        e-kitabın nüshası ödünç verilebilir görünür.
        """
        acquisition = edinim()
        durumlar = (CopyStatus.AVAILABLE, CopyStatus.ON_LOAN, CopyStatus.IN_REPAIR)
        turler = (
            ResourceType.BOOK,
            ResourceType.PERIODICAL,
            ResourceType.EBOOK,
            ResourceType.EDATABASE,
        )
        for tur in turler:
            # Nüshalar KİTAP türünde açılır, sonra eserin türü ham `update` ile
            # değiştirilir: servisler dijital eserde ve ciltsiz süreli yayında
            # nüsha açtırmaz. Koruma testi yine de bu hâlleri kurar — iki türetim
            # kural delinse bile aynı cevabı vermek zorundadır.
            work = eser(title=f"Eser {tur}")
            for danisma, piyasada_yok, durum in itertools.product(
                (False, True), (False, True), durumlar
            ):
                copy = nusha(
                    work,
                    acquisition,
                    is_reference=danisma,
                    is_out_of_print=piyasada_yok,
                )
                if durum != CopyStatus.AVAILABLE:
                    Copy.objects.filter(pk=copy.pk).update(status=durum)
            Work.objects.filter(pk=work.pk).update(resource_type=tur)

        ozellikle = {c.pk for c in Copy.objects.select_related("work") if c.is_loanable}
        suzgecle = set(Copy.objects.filter(selectors.LOANABLE_Q).values_list("pk", flat=True))
        assert ozellikle == suzgecle
        assert ozellikle, "Kurgu bozuk: hiç ödünç verilebilir nüsha üretilmemiş"


@pytest.mark.django_db
class TestYumusakSilme:
    def test_silinen_nusha_sayaclarda_gorunmez(self) -> None:
        work = eser()
        acquisition = edinim()
        nusha(work, acquisition)
        silinen = nusha(work, acquisition)
        silinen.delete()
        satir = nusha_sayaclari(work.pk)
        assert satir["copy_count"] == 1
        assert satir["available_copy_count"] == 1

    def test_silinen_eser_aramada_gorunmez(self) -> None:
        work = eser(title="Silinecek Eser")
        work.delete()
        assert list(selectors.works(q="silinecek")) == []

    def test_silinen_nusha_listede_gorunmez(self) -> None:
        copy = nusha()
        copy.delete()
        assert list(selectors.copies()) == []
        assert selectors.find_copy_by_barcode(copy.barcode) is None


@pytest.mark.django_db
class TestEdinimKisitlari:
    def test_bagista_komisyon_karari_zorunludur(self) -> None:
        """Md. 10/3 — DB kısıtı son savunmadır (servis zaten reddeder)."""
        with pytest.raises(IntegrityError), transaction.atomic():
            Acquisition.objects.create(method=AcquisitionMethod.DONATION, date=VARSAYILAN_TARIH)

    def test_bagis_karariyla_edinim_acilir(self) -> None:
        acquisition = edinim(
            method=AcquisitionMethod.DONATION,
            commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
        )
        assert acquisition.pk is not None


@pytest.mark.django_db
class TestPolitikaKisiti:
    def test_kararsiz_personel_odunc_secenegi_db_de_reddedilir(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            LibraryPolicy.objects.create(pk=LibraryPolicy.SINGLETON_PK, staff_loans_enabled=True)


@pytest.mark.django_db
class TestEserAlanlari:
    def test_yer_numarasi_turkce_buyuk_harfle_uretilir(self) -> None:
        """D11: çıplak `.upper()` 'İnce' soyadını 'INC' basardı."""
        work = eser(title="Roman", authors="Deniz İncedal", classification_code="813.54")
        assert work.call_number == "813.54 İNC"

    def test_yer_numarasi_elle_degistirilebilir(self) -> None:
        work = eser(call_number="ÖZEL 001")
        assert work.call_number == "ÖZEL 001"

    def test_dijital_kaynak_isaretlenir(self) -> None:
        assert eser(resource_type=ResourceType.EBOOK).is_digital is True
        assert eser(resource_type=ResourceType.BOOK).is_digital is False

    def test_bozuk_isbn_kaydi_engellemez_uyari_verir(self) -> None:
        work = eser(isbn="978-0-306-40615-9")
        assert work.pk is not None
        assert work.isbn_warning != ""

    def test_ayni_isbn_birden_cok_eserde_olabilir(self) -> None:
        eser(title="Birinci Cilt", isbn="978-0-306-40615-7")
        ikinci = eser(title="İkinci Cilt", isbn="978-0-306-40615-7")
        assert ikinci.pk is not None
        assert Work.objects.filter(isbn13="9780306406157").count() == 2


@pytest.mark.django_db
class TestEtiketSiralamasi:
    """Etiket şablonu ve kalibrasyon listeleri TR sıralanır (CLAUDE.md §3, T7).

    Listeler F4'te açılacak ama alanlar F2'de kuruluyor: ham `order_by`
    bırakılsaydı "Çıkartma" ile "Şerit" Z'den sonraya düşer ve kullanıcı aradığı
    şablonu listenin sonunda bulurdu. Anahtar alanı sonradan eklemek ayrı bir
    göç isterdi; `0001_initial` henüz yayımlanmadığı için maliyeti sıfırdır.
    """

    @staticmethod
    def _sablon(name: str) -> LabelSheetTemplate:
        sablon: LabelSheetTemplate = LabelSheetTemplate.objects.create(
            name=name,
            page_margin_top=10,
            page_margin_left=10,
            label_width=70,
            label_height=37,
            rows=8,
            cols=3,
        )
        return sablon

    def test_sablonlar_turk_alfabesi_sirasinda_gelir(self) -> None:
        for ad in ("Zarf", "Çıkartma", "Şerit", "Ada"):
            self._sablon(ad)
        assert [s.name for s in LabelSheetTemplate.objects.all()] == [
            "Ada",
            "Çıkartma",
            "Şerit",
            "Zarf",
        ]

    def test_kalibrasyonlar_yazici_adina_gore_turkce_siralanir(self) -> None:
        sablon = self._sablon("Ada")
        for yazici in ("Zebra", "Çok İşlevli", "Salon Yazıcısı"):
            LabelCalibration.objects.create(template=sablon, printer_name=yazici)
        assert [k.printer_name for k in LabelCalibration.objects.all()] == [
            "Çok İşlevli",
            "Salon Yazıcısı",
            "Zebra",
        ]
