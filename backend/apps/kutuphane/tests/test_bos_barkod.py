"""Boş barkod aralığı — ayırma, iptal, bağlama, okutma türü (yöntem B, tasarım §8.1).

F4 kod kapısının maddeleri:

- ayrılmış numara ikinci kez bağlanamaz;
- iptal edilen numara HİÇBİR YOLLA yeniden verilmez (sayaç, yeni aralık,
  bağlama, dışarıdan barkodlu nüsha açma);
- `classify_scan` ayrılmış ama bağlanmamış numarayı ayrı tür olarak ayırt eder.

Uçtan uca akış `test_bos_barkod_uctan_uca.py`'de, sayaç yarışı ve yıl dönümü
`test_bos_barkod_sayac.py`'dedir. Bütün veriler uydurmadır.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.barcode import ScanKind
from apps.kutuphane.models import (
    MAX_LABELS_PER_JOB,
    BarcodeReservation,
    Copy,
    CopyCounter,
    CopyStatus,
    ReservedBarcode,
    ReservedBarcodeState,
    ResourceType,
)
from apps.kutuphane.services import barcode_reservations as rezervasyon
from apps.kutuphane.services import catalog, numbering
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db


def _bagla(kod: str, **alanlar: Any) -> Copy:
    if "work" not in alanlar:
        alanlar["work"] = ortak.eser()
    if "acquisition" not in alanlar:
        alanlar["acquisition"] = ortak.edinim()
    return rezervasyon.bind_label(label=kod, **alanlar)


def _ret_iletisi(exc: pytest.ExceptionInfo[ValidationError]) -> str:
    return " ".join(exc.value.message_dict["label_code"])


# ============================================================ Ayırma
class TestAyirma:
    def test_numaralar_tek_sayactan_ardisik_ayrilir(self) -> None:
        once = numbering.next_copy_identity()[1]
        aralik = rezervasyon.reserve(5, note="Tarih rafı")
        sonra = numbering.next_copy_identity()[1]

        numaralar = list(aralik.numbers.values_list("barcode", flat=True))
        assert len(numaralar) == 5
        assert [int(kod) for kod in numaralar] == list(range(int(once) + 1, int(once) + 6))
        # Sayaç aralığın ötesine geçti: sıradaki nüsha numarası aralıktan SONRADIR.
        assert int(sonra) == int(numaralar[-1]) + 1
        assert (aralik.first_barcode, aralik.last_barcode) == (numaralar[0], numaralar[-1])
        assert aralik.count == 5 and aralik.note == "Tarih rafı"
        assert aralik.year == timezone.localdate().year

    def test_kayit_no_barkodun_sayi_halidir(self) -> None:
        aralik = rezervasyon.reserve(3)
        for satir in aralik.numbers.all():
            assert satir.accession_no == int(satir.barcode)
            assert satir.state == ReservedBarcodeState.OPEN

    @pytest.mark.parametrize("adet", [0, -1, MAX_LABELS_PER_JOB + 1])
    def test_adet_siniri(self, adet: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rezervasyon.reserve(adet)
        assert "count" in exc.value.message_dict
        assert not ReservedBarcode.objects.exists()

    def test_sayac_dolacaksa_hicbir_numara_ayrilmaz(self) -> None:
        yil = timezone.localdate().year
        CopyCounter.objects.create(year=yil, last_no=barcode_module.MAX_SEQUENCE - 2)

        with pytest.raises(ValidationError) as exc:
            rezervasyon.reserve(3)

        assert "sayaç doldu" in " ".join(exc.value.message_dict["count"])
        assert CopyCounter.objects.get(year=yil).last_no == barcode_module.MAX_SEQUENCE - 2
        assert not ReservedBarcode.objects.exists()

    def test_sinira_tam_sigan_aralik_ayrilir(self) -> None:
        yil = timezone.localdate().year
        CopyCounter.objects.create(year=yil, last_no=barcode_module.MAX_SEQUENCE - 2)

        aralik = rezervasyon.reserve(2)

        assert aralik.last_barcode.endswith("999999")


# ============================================================ Okutma türü
class TestOkutmaTuru:
    def test_bagli_olmayan_ayrilmis_numara_ayri_turdur(self) -> None:
        kod = rezervasyon.reserve(1).first_barcode

        assert rezervasyon.classify(kod) is ScanKind.RESERVED
        assert rezervasyon.classify(barcode_module.format_barcode(kod)) is ScanKind.RESERVED
        # Saf `classify_scan` veritabanını bilmez: biçime bakar.
        assert barcode_module.classify_scan(kod) is ScanKind.COPY

    def test_baglaninca_nusha_turune_doner(self) -> None:
        kod = rezervasyon.reserve(1).first_barcode
        _bagla(kod)

        assert rezervasyon.classify(kod) is ScanKind.COPY

    def test_iptal_edilen_numara_ayri_turdur_bagli_degil_diye_sunulmaz(self) -> None:
        """F6 masası `RESERVED`'a "henüz bir kitaba bağlanmadı" der; iptal edilmiş
        numara bir daha bağlanamaz, o ileti ona yanlış olurdu (`CANCELLED`)."""
        aralik = rezervasyon.reserve(1)
        rezervasyon.cancel_numbers(aralik)

        assert rezervasyon.classify(aralik.first_barcode) is ScanKind.CANCELLED
        bilgi = rezervasyon.describe_scan(aralik.first_barcode)
        assert bilgi.kind is ScanKind.CANCELLED
        assert bilgi.is_cancelled_reservation and not bilgi.is_open_reservation
        assert bilgi.reserved is not None and bilgi.copy is None

    def test_ayrilmamis_nusha_numarasi_ve_diger_turler_degismez(self) -> None:
        nusha = ortak.nusha()
        assert rezervasyon.classify(nusha.barcode) is ScanKind.COPY
        assert rezervasyon.classify("94718263") is ScanKind.MEMBER_CARD
        assert rezervasyon.classify("9786053321245") is ScanKind.ISBN
        assert rezervasyon.classify("12345") is ScanKind.UNKNOWN


# ============================================================ Bağlama (hızlı kayıt)
class TestBaglama:
    def test_nusha_ayrilmis_numarayla_acilir(self) -> None:
        aralik = rezervasyon.reserve(3)
        kod = aralik.numbers.order_by("accession_no")[1].barcode
        sayac_once = numbering.peek_next_sequence()

        nusha = _bagla(barcode_module.format_barcode(kod))  # basılı biçim de kabul

        assert nusha.barcode == kod and nusha.accession_no == int(kod)
        assert nusha.status == CopyStatus.AVAILABLE
        satir = ReservedBarcode.objects.get(barcode=kod)
        assert satir.copy_id == nusha.pk and satir.bound_at is not None
        assert satir.state == ReservedBarcodeState.BOUND
        # Bağlama sayacı İLERLETMEZ: numara zaten ayrılmıştı.
        assert numbering.peek_next_sequence() == sayac_once

    def test_bagli_nusha_barkodu_basilmis_ve_dogrulanmis_sirt_ise_kuyrukta(self) -> None:
        aralik = rezervasyon.reserve(1)
        nusha = _bagla(aralik.first_barcode)

        assert nusha.label_printed_at is not None
        assert nusha.label_verified_at is not None
        assert nusha.spine_label_printed_at is None

    def test_basim_onayi_varsa_basim_tarihi_odur(self) -> None:
        aralik = rezervasyon.reserve(1)
        rezervasyon.confirm_print(aralik)
        aralik.refresh_from_db()

        nusha = _bagla(aralik.first_barcode)

        assert nusha.label_printed_at == aralik.printed_at

    def test_ayrilmis_numara_ikinci_kez_baglanamaz(self) -> None:
        kod = rezervasyon.reserve(1).first_barcode
        ilk = _bagla(kod)

        with pytest.raises(ValidationError) as exc:
            _bagla(kod, work=ortak.eser(title="Başka Kitap"))

        ileti = _ret_iletisi(exc)
        assert "zaten kayıtlı bir nüshanın" in ileti
        assert barcode_module.format_barcode(kod) in ileti and ilk.work.title in ileti
        # Önce "kitap zaten kayıtlı olabilir" denir; aynı kitap ikinci kez kaydedilmesin.
        assert "yeniden kaydetmeyin" in ileti
        assert Copy.objects.filter(barcode=kod).count() == 1

    def test_iptal_edilen_numara_baglanamaz(self) -> None:
        aralik = rezervasyon.reserve(2)
        kod = aralik.first_barcode
        rezervasyon.cancel_numbers(aralik, barcodes=[kod])

        with pytest.raises(ValidationError) as exc:
            _bagla(kod)

        assert "iptal edildi" in _ret_iletisi(exc)
        assert not Copy.all_objects.filter(barcode=kod).exists()

    def test_ayrilmamis_numara_baglanamaz(self) -> None:
        # Sayacın henüz vermediği, biçimce geçerli bir numara.
        kod = barcode_module.build_barcode(timezone.localdate().year, 777)
        with pytest.raises(ValidationError) as exc:
            _bagla(kod)
        assert "ayrılmış bir etiket değil" in _ret_iletisi(exc)

    def test_sayactan_verilmis_nusha_numarasi_baglanamaz(self) -> None:
        nusha = ortak.nusha()
        with pytest.raises(ValidationError) as exc:
            _bagla(nusha.barcode)
        assert "zaten kayıtlı bir nüshanın" in _ret_iletisi(exc)

    def test_silinmis_nushanin_numarasi_baglanamaz(self) -> None:
        kod = rezervasyon.reserve(1).first_barcode
        nusha = _bagla(kod)
        catalog.delete_copy(nusha)

        with pytest.raises(ValidationError) as exc:
            _bagla(kod)

        assert "silinmiş bir nüshaya aitti" in _ret_iletisi(exc)

    @pytest.mark.parametrize(
        ("kod", "beklenen"),
        [
            ("9786053321245", "ISBN barkodu"),
            ("94718263", "üye kartı"),
            ("12345", "kütüphane etiketi değil"),
            ("", "etiketini okutun"),
        ],
    )
    def test_yanlis_kod_turu_turkce_reddedilir(self, kod: str, beklenen: str) -> None:
        with pytest.raises(ValidationError) as exc:
            _bagla(kod)
        assert beklenen in _ret_iletisi(exc)

    def test_nusha_kurallari_ayni_kapidan_gecer_ve_numara_acik_kalir(self) -> None:
        """Dijital kaynağa nüsha açılamaz — ayrılmış numarayla da; numara boşa gitmez."""
        kod = rezervasyon.reserve(1).first_barcode
        e_kitap = ortak.eser(title="Dijital Deneme", resource_type=ResourceType.EBOOK)

        with pytest.raises(ValidationError) as exc:
            _bagla(kod, work=e_kitap)

        assert "work" in exc.value.message_dict
        assert ReservedBarcode.objects.get(barcode=kod).state == ReservedBarcodeState.OPEN
        # Aynı etiket doğru esere bağlanabilir.
        assert _bagla(kod).barcode == kod

    def test_kimlik_alanlari_disaridan_verilemez(self) -> None:
        kod = rezervasyon.reserve(1).first_barcode
        with pytest.raises(ValidationError) as exc:
            _bagla(kod, barcode="2026999999")
        assert "barcode" in exc.value.message_dict

    def test_on_denetim_yazmaz_ve_durumu_soyler(self) -> None:
        aralik = rezervasyon.reserve(1)
        kod = aralik.first_barcode

        acik = rezervasyon.check_label(kod)
        assert acik["bindable"] is True and acik["kind"] == "RESERVED"
        assert acik["reservation"] == aralik.pk and acik["hint"] == ""
        assert acik["barcode_display"] == barcode_module.format_barcode(kod)

        nusha = _bagla(kod)
        bagli = rezervasyon.check_label(kod)
        assert bagli["bindable"] is False and bagli["copy"] == nusha.pk
        assert bagli["work_title"] == nusha.work.title
        # Bağlı numarada "yeni numara ver" önerilmez: kitap büyük olasılıkla zaten
        # kayıtlıdır ve yeni numara aynı kitaba ikinci bir nüsha açardı.
        assert bagli["hint"] == ""
        assert "yeniden kaydetmeyin" in bagli["message"]

        isbn = rezervasyon.check_label("9786053321245")
        assert isbn["bindable"] is False and isbn["kind"] == "ISBN"
        assert "yeni numara ver" in isbn["hint"]

    def test_iptal_edilmis_ve_ayrilmamis_numarada_yeni_numara_ipucu_verilir(self) -> None:
        aralik = rezervasyon.reserve(1)
        rezervasyon.cancel_numbers(aralik)
        iptal = rezervasyon.check_label(aralik.first_barcode)
        assert iptal["kind"] == "CANCELLED" and "iptal edildi" in iptal["message"]
        assert "yeni numara ver" in iptal["hint"]

        ayrilmamis = rezervasyon.check_label(
            barcode_module.build_barcode(timezone.localdate().year, 777)
        )
        assert ayrilmamis["kind"] == "COPY" and "yeni numara ver" in ayrilmamis["hint"]


# ============================================================ İptal
class TestIptal:
    def test_bagli_olanlar_dokunulmadan_acik_numaralar_iptal_edilir(self) -> None:
        aralik = rezervasyon.reserve(4)
        kodlar = list(aralik.numbers.order_by("accession_no").values_list("barcode", flat=True))
        _bagla(kodlar[0])

        adet = rezervasyon.cancel_numbers(aralik, reason="Etiketler ıslandı")

        assert adet == 3
        durumlar = {s.barcode: s.state for s in aralik.numbers.all()}
        assert durumlar[kodlar[0]] == ReservedBarcodeState.BOUND
        assert all(durumlar[kod] == ReservedBarcodeState.CANCELLED for kod in kodlar[1:])
        assert set(
            aralik.numbers.exclude(copy__isnull=False).values_list("cancel_reason", flat=True)
        ) == {"Etiketler ıslandı"}

    def test_secili_numara_iptali_ve_tekrari_sessizdir(self) -> None:
        aralik = rezervasyon.reserve(3)
        kod = aralik.last_barcode

        assert (
            rezervasyon.cancel_numbers(aralik, barcodes=[barcode_module.format_barcode(kod)]) == 1
        )
        assert rezervasyon.cancel_numbers(aralik, barcodes=[kod]) == 0
        assert aralik.numbers.filter(cancelled_at__isnull=False).count() == 1

    def test_bagli_numara_iptal_edilemez(self) -> None:
        aralik = rezervasyon.reserve(2)
        _bagla(aralik.first_barcode)

        with pytest.raises(ValidationError) as exc:
            rezervasyon.cancel_numbers(aralik, barcodes=[aralik.first_barcode])

        assert "bağlı; iptal edilemez" in " ".join(exc.value.message_dict["barcodes"])

    def test_baska_araligin_numarasi_iptal_edilemez(self) -> None:
        birinci = rezervasyon.reserve(1)
        ikinci = rezervasyon.reserve(1)

        with pytest.raises(ValidationError) as exc:
            rezervasyon.cancel_numbers(birinci, barcodes=[ikinci.first_barcode])

        assert "bu aralıkta değil" in " ".join(exc.value.message_dict["barcodes"])
        assert ikinci.numbers.get().state == ReservedBarcodeState.OPEN

    def test_bos_liste_reddedilir(self) -> None:
        aralik = rezervasyon.reserve(1)
        with pytest.raises(ValidationError):
            rezervasyon.cancel_numbers(aralik, barcodes=["", "  "])

    def test_db_kisiti_bagli_numaranin_iptalini_engeller(self) -> None:
        aralik = rezervasyon.reserve(1)
        _bagla(aralik.first_barcode)
        with pytest.raises(IntegrityError), transaction.atomic():
            ReservedBarcode.objects.filter(barcode=aralik.first_barcode).update(
                cancelled_at=timezone.now()
            )


class TestIptalEdilenNumaraHicbirYollaYenidenVerilmez:
    """F4 kod kapısı: iptal edilen numara sayaca dönmez ve hiçbir yol onu dağıtmaz."""

    @pytest.fixture
    def iptal_edilen(self) -> str:
        aralik = rezervasyon.reserve(3)
        kod = aralik.last_barcode
        rezervasyon.cancel_numbers(aralik, barcodes=[kod])
        return kod

    def test_sayac_geri_gitmez(self, iptal_edilen: str) -> None:
        yil = int(iptal_edilen[:4])
        assert CopyCounter.objects.get(year=yil).last_no >= int(iptal_edilen[4:])
        assert int(numbering.next_copy_identity()[1]) > int(iptal_edilen)

    def test_yeni_aralik_onu_icermez(self, iptal_edilen: str) -> None:
        yeni = rezervasyon.reserve(5)
        assert iptal_edilen not in set(yeni.numbers.values_list("barcode", flat=True))
        assert int(yeni.first_barcode) > int(iptal_edilen)

    def test_sayacli_nusha_acma_onu_vermez(self, iptal_edilen: str) -> None:
        verilen = {ortak.nusha().barcode for _ in range(5)}
        assert iptal_edilen not in verilen

    def test_baglama_onu_reddeder(self, iptal_edilen: str) -> None:
        with pytest.raises(ValidationError):
            _bagla(iptal_edilen)

    def test_disaridan_barkodla_nusha_acilamaz(self, iptal_edilen: str) -> None:
        with pytest.raises(ValidationError):
            catalog.create_copy(work=ortak.eser(), acquisition=ortak.edinim(), barcode=iptal_edilen)

    def test_numara_satiri_ikinci_kez_ayrilamaz(self, iptal_edilen: str) -> None:
        satir = ReservedBarcode.objects.get(barcode=iptal_edilen)
        with pytest.raises(IntegrityError), transaction.atomic():
            ReservedBarcode.objects.create(
                reservation=satir.reservation,
                barcode=iptal_edilen,
                accession_no=int(iptal_edilen),
            )

    def test_iptal_geri_alinamaz(self, iptal_edilen: str) -> None:
        """İptali kaldıran bir servis yolu yoktur; yeniden iptal isteği de durumu değiştirmez."""
        assert not hasattr(rezervasyon, "uncancel_numbers")
        satir = ReservedBarcode.objects.get(barcode=iptal_edilen)
        assert rezervasyon.cancel_numbers(satir.reservation, barcodes=[iptal_edilen]) == 0
        satir.refresh_from_db()
        assert satir.state == ReservedBarcodeState.CANCELLED


# ============================================================ Basım işareti (D10 kuralı)
class TestAralikBasimIsareti:
    def test_onay_ve_geri_alma(self) -> None:
        aralik = rezervasyon.reserve(2)
        assert aralik.printed_at is None

        rezervasyon.confirm_print(aralik)
        assert aralik.printed_at is not None
        with pytest.raises(ValidationError):
            rezervasyon.confirm_print(aralik)

        rezervasyon.revert_print(aralik)
        assert aralik.printed_at is None
        with pytest.raises(ValidationError):
            rezervasyon.revert_print(aralik)

    def test_cift_tiklamada_ikinci_onay_bayat_nesneyle_gecmez(self) -> None:
        """Uç aralığı işlem DIŞINDA okur: iki istek de işaretsiz nesne taşır.

        Denetim bulgusu (24.09.2026): ikinci onay reddedilmiyor, damgayı üzerine
        yazıyordu. Durum kilit altında taze satırdan denetlenir.
        """
        aralik = rezervasyon.reserve(2)
        birinci = BarcodeReservation.objects.get(pk=aralik.pk)
        ikinci = BarcodeReservation.objects.get(pk=aralik.pk)

        rezervasyon.confirm_print(birinci)
        damga = BarcodeReservation.objects.get(pk=aralik.pk).printed_at
        with pytest.raises(ValidationError, match="zaten basıldı"):
            rezervasyon.confirm_print(ikinci)
        assert BarcodeReservation.objects.get(pk=aralik.pk).printed_at == damga

        # Geri almada da: iki istek "basılmış" nesne taşır, ikincisi reddedilir.
        geri_birinci = BarcodeReservation.objects.get(pk=aralik.pk)
        geri_ikinci = BarcodeReservation.objects.get(pk=aralik.pk)
        rezervasyon.revert_print(geri_birinci)
        with pytest.raises(ValidationError, match="işaretli değil"):
            rezervasyon.revert_print(geri_ikinci)
        assert BarcodeReservation.objects.get(pk=aralik.pk).printed_at is None

    def test_kitaba_baglanmis_etiket_varsa_geri_alinamaz(self) -> None:
        aralik = rezervasyon.reserve(2)
        rezervasyon.confirm_print(aralik)
        _bagla(aralik.first_barcode)

        with pytest.raises(ValidationError) as exc:
            rezervasyon.revert_print(aralik)

        assert "1 etiket kitaplara bağlandı" in " ".join(exc.value.message_dict["reservation"])

    def test_hepsi_iptal_edilmis_aralik_basildi_isaretlenemez(self) -> None:
        aralik = rezervasyon.reserve(2)
        rezervasyon.cancel_numbers(aralik)
        with pytest.raises(ValidationError):
            rezervasyon.confirm_print(aralik)

    def test_basilacak_numaralar_yalniz_aciklardir(self) -> None:
        aralik = rezervasyon.reserve(4)
        kodlar = list(aralik.numbers.order_by("accession_no").values_list("barcode", flat=True))
        _bagla(kodlar[0])
        rezervasyon.cancel_numbers(aralik, barcodes=[kodlar[1]])

        assert rezervasyon.printable_numbers(aralik) == kodlar[2:]
        assert rezervasyon.printable_numbers(aralik, barcodes=[kodlar[3]]) == [kodlar[3]]
        for yasak in (kodlar[0], kodlar[1]):
            with pytest.raises(ValidationError):
                rezervasyon.printable_numbers(aralik, barcodes=[yasak])

    def test_acik_numara_kalmadiysa_basilacak_yok(self) -> None:
        aralik = rezervasyon.reserve(1)
        rezervasyon.cancel_numbers(aralik)
        with pytest.raises(ValidationError):
            rezervasyon.printable_numbers(aralik)


# ============================================================ Kenar durumları
class TestKenarDurumlari:
    def test_sayactan_sifir_numara_istenemez(self) -> None:
        with pytest.raises(ValueError, match="en az 1"):
            numbering.reserve_identities(0)

    def test_denetimle_kilit_arasinda_baglanan_etiket_ikinci_kez_baglanmaz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """İki istek aynı etiketi okuttu: ilk denetim 'açık' görür, kilit altında 'bağlı' çıkar."""
        kod = rezervasyon.reserve(1).first_barcode
        eski_bilgi = rezervasyon.describe_scan(kod)  # henüz açık
        _bagla(kod)  # öbür istek bağladı

        gercek = rezervasyon.describe_scan
        cagri = iter([eski_bilgi])
        monkeypatch.setattr(
            rezervasyon, "describe_scan", lambda deger: next(cagri, None) or gercek(deger)
        )

        with pytest.raises(ValidationError) as exc:
            _bagla(kod, work=ortak.eser(title="İkinci İstek"))

        assert "zaten kayıtlı bir nüshanın" in _ret_iletisi(exc)
        assert Copy.objects.filter(barcode=kod).count() == 1
