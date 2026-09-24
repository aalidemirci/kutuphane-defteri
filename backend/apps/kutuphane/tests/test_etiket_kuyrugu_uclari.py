"""Etiket kuyruğu ve boş barkod aralığı UÇLARI (F4-Q) — biçim, kapılar, PDF.

Servis kuralları kendi test dosyalarındadır (`test_etiket_kuyrugu*.py`,
`test_bos_barkod*.py`); burada uçların gövde biçimi, sayfalaması, hata
gövdeleri ve kapıları sınanır:

- görevli kipi izin listesinde etiket yüzeyinden YALNIZ doğrulama okutması
  (`library-label-verify` POST; kullanıcı kararı 24.09.2026) vardır: görevli
  kipinde o uç 200 ve daraltılmış yanıt döner, geri kalan her etiket ucu her
  yöntemde 403 `kip_yetkisiz` (genel dolaşma `test_uc_kapilari.py`'de; burada
  etiket yüzeyi AÇIKÇA sabitlenir);
- PDF uçları işarete DOKUNMAZ ve motor bağlı değilken 503 `etiket_motoru_yok`
  döner.

Bütün veriler uydurmadır.
"""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import unquote

import pytest
from django.urls import URLPattern, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.models import Copy, LabelPrintBatch, LabelPrintKind, ReservedBarcode
from apps.kutuphane.services import barcode_reservations as rezervasyon
from apps.kutuphane.services import label_queue
from apps.kutuphane.tests import kuyruk_ortak, ortak
from apps.kutuphane.tests.kuyruk_ortak import isaretler
from apps.okul.kip import KIP
from apps.okul.kip_izinleri import IZIN_LISTESI

pytestmark = pytest.mark.django_db

KUYRUK = "/api/v1/library/labels/queue/"
DOGRULANMAMIS = "/api/v1/library/labels/unverified/"
OZET = "/api/v1/library/labels/summary/"
DOGRULA = "/api/v1/library/labels/verify/"
PARTILER = "/api/v1/library/labels/batches/"
ARALIKLAR = "/api/v1/library/barcode-reservations/"
ON_DENETIM = "/api/v1/library/barcode-reservations/check/"
ETIKETTEN_NUSHA = "/api/v1/library/copies/from-label/"

#: F4-Q'nun bütün uçları (adlar tekil; görevli kipinde yalnız `GOREVLI_ACIK` açık).
Q_UCLARI = {
    "library-label-queue": {},
    "library-label-unverified": {},
    "library-label-summary": {},
    "library-label-verify": {},
    "library-label-batch-list": {},
    "library-label-batch-detail": {"pk": 1},
    "library-label-batch-pdf": {"pk": 1},
    "library-label-batch-confirm": {"pk": 1},
    "library-label-batch-revert": {"pk": 1},
    "library-label-batch-discard": {"pk": 1},
    "library-label-batch-reprint": {"pk": 1},
    "library-barcode-reservation-list": {},
    "library-barcode-reservation-check": {},
    "library-barcode-reservation-detail": {"pk": 1},
    "library-barcode-reservation-pdf": {"pk": 1},
    "library-barcode-reservation-confirm-print": {"pk": 1},
    "library-barcode-reservation-revert-print": {"pk": 1},
    "library-barcode-reservation-cancel": {"pk": 1},
    "library-copy-from-label": {},
}
#: Etiket motorunun uçları (`labels/urls.py`) — görevli kipinde hepsi kapalı.
MOTOR_UCLARI = {
    "library-label-template-list": {},
    "library-label-template-detail": {"pk": 1},
    "library-label-calibration-list": {},
    "library-label-calibration-detail": {"pk": 1},
    "library-label-calibration": {},
    "library-label-preview": {},
}
#: Görevli kipinde açık TEK etiket ucu ve yöntemi (kullanıcı kararı 24.09.2026).
GOREVLI_ACIK = ("library-label-verify", "POST")
YONTEMLER = ("get", "post", "put", "patch", "delete")


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


def _json(yanit: Any) -> dict[str, Any]:
    govde: dict[str, Any] = yanit.json()
    return govde


# ============================================================ Kapılar
class TestKapilar:
    def test_izin_listesinde_yalniz_dogrulama_okutmasi_var(self) -> None:
        izinli = {(kural.uc, kural.yontem) for kural in IZIN_LISTESI}
        etiket_uclari = set(Q_UCLARI) | set(MOTOR_UCLARI)
        assert {cift for cift in izinli if cift[0] in etiket_uclari} == {GOREVLI_ACIK}

    def test_dolasma_butun_etiket_yuzeyini_goruyor(self) -> None:
        """Elle tutulan listeler eksik kalmasın: etiket adlı her desen burada sayılır."""
        from apps.kutuphane.urls import urlpatterns

        adlar = {
            desen.name
            for desen in urlpatterns
            if isinstance(desen, URLPattern)
            and desen.name
            and (
                desen.name.startswith(("library-label", "library-barcode-reservation"))
                or desen.name == "library-copy-from-label"
            )
        }
        assert adlar == set(Q_UCLARI) | set(MOTOR_UCLARI)

    def test_gorevli_kipinde_dogrulama_disindaki_her_etiket_ucu_403(
        self, istemci: APIClient
    ) -> None:
        KIP.gorevliye_gec()
        kesilmeyen = []
        for ad, kwargs in {**Q_UCLARI, **MOTOR_UCLARI}.items():
            yol = reverse(ad, kwargs=kwargs)
            for yontem in YONTEMLER:
                if (ad, yontem.upper()) == GOREVLI_ACIK:
                    continue
                yanit = getattr(istemci, yontem)(yol, {}, format="json")
                if yanit.status_code != 403 or yanit.json()["code"] != "kip_yetkisiz":
                    kesilmeyen.append((ad, yontem, yanit.status_code))
        assert kesilmeyen == []
        assert KIP.durum() == "gorevli", "dolaşma sırasında kip değişti"

    def test_gorevli_kipinde_dogrulama_okutmasi_200_ve_yaniti_daralir(
        self, istemci: APIClient
    ) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        parti = label_queue.create_batch(
            kind=LabelPrintKind.BOTH, template=kuyruk_ortak.sablon(), copy_ids=[nusha.pk]
        )
        label_queue.confirm_batch(parti)
        KIP.gorevliye_gec()

        yanit = istemci.post(DOGRULA, {"code": nusha.barcode}, format="json")

        assert yanit.status_code == 200, yanit.content
        govde = _json(yanit)
        assert govde["result"] == "verified" and govde["message"] == "Etiket doğrulandı."
        # Kişisel veri zaten yoktur; görevliye yalnız barkod ve eser adı gider.
        assert set(govde["copy"]) == {"barcode", "barcode_display", "work_title"}
        assert govde["copy"]["work_title"] == nusha.work.title
        assert isaretler(nusha)[1] is not None
        # Ret de 200 gövdedir; aynı uç GET'te kapalıdır.
        isbn = istemci.post(DOGRULA, {"code": "9786053321245"}, format="json")
        assert isbn.status_code == 200 and isbn.json()["kind"] == "ISBN"
        assert istemci.get(DOGRULA).status_code == 403
        assert KIP.durum() == "gorevli"

    def test_yonetici_kipinde_dogrulama_yaniti_tam_ozettir(self, istemci: APIClient) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        label_queue.confirm_batch(
            label_queue.create_batch(
                kind=LabelPrintKind.BARCODE, template=kuyruk_ortak.sablon(), copy_ids=[nusha.pk]
            )
        )

        govde = _json(istemci.post(DOGRULA, {"code": nusha.barcode}, format="json"))

        assert govde["copy"]["id"] == nusha.pk and "call_number" in govde["copy"]

    def test_kilitliyken_423(self, istemci: APIClient, kilitli: Any) -> None:
        for ad, kwargs in Q_UCLARI.items():
            yanit = istemci.post(reverse(ad, kwargs=kwargs), {}, format="json")
            assert yanit.status_code == 423, ad

    def test_parolasiz_ortamda_da_calisir_kisi_verisi_yok(
        self, istemci: APIClient, parolasiz: Any
    ) -> None:
        """Etiket ve numara kişisel veri değildir: kurulum bitmeden de basılabilir."""
        yanit = istemci.post(ARALIKLAR, {"count": 2}, format="json")
        assert yanit.status_code == 201, yanit.json()


# ============================================================ Kuyruk
class TestKuyrukUclari:
    def test_kuyruk_sayfali_sirali_ve_bekleyen_partiyi_gosterir(self, istemci: APIClient) -> None:
        z = ortak.nusha(ortak.eser(title="Z", classification_code="900"))
        a = ortak.nusha(ortak.eser(title="A", classification_code="100"))
        m = ortak.nusha(ortak.eser(title="M", classification_code="500"))
        sablon = kuyruk_ortak.sablon()
        parti = istemci.post(
            PARTILER,
            {"kind": "BOTH", "template": sablon.pk, "copies": [m.pk]},
            format="json",
        )
        assert parti.status_code == 201

        yanit = istemci.get(KUYRUK, {"limit": 2})
        govde = _json(yanit)

        assert yanit.status_code == 200
        assert govde["count"] == 3 and govde["next"] is not None
        assert [satir["id"] for satir in govde["results"]] == [a.pk, m.pk]
        assert govde["results"][1]["pending_batch"] == parti.json()["id"]
        assert govde["results"][0]["pending_batch"] is None
        assert govde["results"][0]["barcode_display"].count("-") == 1
        ikinci = _json(istemci.get(KUYRUK, {"limit": 2, "offset": 2}))
        assert [satir["id"] for satir in ikinci["results"]] == [z.pk]

    def test_kuyruk_sira_ve_tur_parametreleri(self, istemci: APIClient) -> None:
        birinci, ikinci = kuyruk_ortak.nushalar(2)
        barkod = _json(istemci.get(KUYRUK, {"order": "BARCODE", "kind": "SPINE"}))
        assert [s["id"] for s in barkod["results"]] == [birinci.pk, ikinci.pk]

        hatali = istemci.get(KUYRUK, {"order": "TITLE"})
        assert hatali.status_code == 400 and "order" in hatali.json()["fields"]
        assert istemci.get(KUYRUK, {"kind": "CARD"}).status_code == 400
        assert istemci.get(KUYRUK, {"section": "abc"}).status_code == 400
        tarih = istemci.get(KUYRUK, {"created_from": "31.12.2026"})
        assert tarih.status_code == 400 and "created_from" in tarih.json()["fields"]

    def test_kuyruk_suzgecleri(self, istemci: APIClient) -> None:
        parti = ortak.edinim()
        icerde = ortak.nusha(acquisition=parti)
        ortak.nusha()
        yanit = _json(istemci.get(KUYRUK, {"acquisition": parti.pk}))
        assert [s["id"] for s in yanit["results"]] == [icerde.pk]

    def test_dogrulanmamislar_ve_ozet(self, istemci: APIClient) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        Copy.objects.filter(pk=nusha.pk).update(label_printed_at="2026-09-01T10:00:00+03:00")

        rapor = _json(istemci.get(DOGRULANMAMIS))
        assert [s["id"] for s in rapor["results"]] == [nusha.pk]

        ozet = _json(istemci.get(OZET))
        assert ozet["unverified"] == 1 and ozet["queue"]["SPINE"] == 1


# ============================================================ Basım partileri
class TestPartiUclari:
    def test_parti_ac_pdf_onayla_geri_al(
        self, istemci: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isler = kuyruk_ortak.motoru_bagla(monkeypatch)
        nushalar = kuyruk_ortak.nushalar(2)
        sablon = kuyruk_ortak.sablon()

        acilan = istemci.post(
            PARTILER,
            {
                "kind": "BARCODE",
                "template": sablon.pk,
                "order": "BARCODE",
                "start_cell": 3,
                "copies": [nushalar[1].pk, nushalar[0].pk],
            },
            format="json",
        )
        assert acilan.status_code == 201, acilan.json()
        govde = _json(acilan)
        assert govde["status"] == "PENDING" and govde["status_display"] == "Basım onayı bekliyor"
        assert [kalem["id"] for kalem in govde["items"]] == [nushalar[0].pk, nushalar[1].pk]
        assert [kalem["position"] for kalem in govde["items"]] == [1, 2]
        pk = govde["id"]

        pdf = istemci.get(f"{PARTILER}{pk}/pdf/")
        assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
        assert b"".join(cast("Any", pdf).streaming_content) == kuyruk_ortak.SAHTE_PDF
        # Belge adı + yerel tarih; parti numarası (iç kimlik) dosya adına girmez.
        assert (
            f'filename="Barkod-Etiketi_{timezone.localdate():%d.%m.%Y}.pdf"'
            in pdf["Content-Disposition"]
        )
        assert isler[0].start_cell == 3
        assert all(isaretler(n) == (None, None, None) for n in nushalar)

        onay = istemci.post(f"{PARTILER}{pk}/confirm/")
        assert onay.status_code == 200 and onay.json()["status"] == "CONFIRMED"
        assert all(isaretler(n)[0] is not None for n in nushalar)
        assert istemci.post(f"{PARTILER}{pk}/confirm/").status_code == 400

        geri = istemci.post(f"{PARTILER}{pk}/revert/")
        assert geri.status_code == 200
        assert geri.json()["restored"] == 2 and geri.json()["kept_verified"] == 0
        assert geri.json()["requeued"] == 2
        assert geri.json()["batch"]["status"] == "REVERTED"
        assert all(isaretler(n) == (None, None, None) for n in nushalar)

        liste = _json(istemci.get(PARTILER, {"status": "REVERTED"}))
        assert [satir["id"] for satir in liste["results"]] == [pk]
        assert istemci.get(PARTILER, {"status": "BILINMEYEN"}).status_code == 400

    def test_motor_bagli_degilse_pdf_503_ve_isaret_yok(
        self, istemci: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kuyruk_ortak.motoru_ayir(monkeypatch)
        (nusha,) = kuyruk_ortak.nushalar(1)
        pk = istemci.post(
            PARTILER,
            {"kind": "BOTH", "template": kuyruk_ortak.sablon().pk, "copies": [nusha.pk]},
            format="json",
        ).json()["id"]

        yanit = istemci.get(f"{PARTILER}{pk}/pdf/")

        assert yanit.status_code == 503 and yanit.json()["code"] == "etiket_motoru_yok"
        assert isaretler(nusha) == (None, None, None)

    def test_kuyruktan_parti_ilk_n_nusha(self, istemci: APIClient) -> None:
        nushalar = [
            ortak.nusha(ortak.eser(title=f"E{sira}", classification_code=kod))
            for sira, kod in enumerate(["900", "100", "500"])
        ]
        yanit = istemci.post(
            PARTILER,
            {
                "kind": "BOTH",
                "template": kuyruk_ortak.sablon().pk,
                "from_queue": True,
                "limit": 2,
            },
            format="json",
        )
        assert yanit.status_code == 201, yanit.json()
        assert [k["id"] for k in yanit.json()["items"]] == [nushalar[1].pk, nushalar[2].pk]

    def test_parti_govdesi_denetimi(self, istemci: APIClient) -> None:
        sablon = kuyruk_ortak.sablon()
        (nusha,) = kuyruk_ortak.nushalar(1)

        secimsiz = istemci.post(PARTILER, {"kind": "BOTH", "template": sablon.pk}, format="json")
        assert secimsiz.status_code == 400 and "copies" in secimsiz.json()["fields"]

        ikisi = istemci.post(
            PARTILER,
            {"kind": "BOTH", "template": sablon.pk, "copies": [nusha.pk], "from_queue": True},
            format="json",
        )
        assert ikisi.status_code == 400

        hucre = istemci.post(
            PARTILER,
            {"kind": "BOTH", "template": sablon.pk, "copies": [nusha.pk], "start_cell": 99},
            format="json",
        )
        assert hucre.status_code == 400
        assert "1 ile 65 arasında" in hucre.json()["message"]

        sablonsuz = istemci.post(PARTILER, {"kind": "BOTH", "copies": [nusha.pk]}, format="json")
        assert sablonsuz.status_code == 400 and "template" in sablonsuz.json()["fields"]
        assert not LabelPrintBatch.objects.exists()

    def test_vazgec_ve_yeniden_bas(self, istemci: APIClient) -> None:
        (nusha,) = kuyruk_ortak.nushalar(1)
        pk = istemci.post(
            PARTILER,
            {"kind": "BOTH", "template": kuyruk_ortak.sablon().pk, "copies": [nusha.pk]},
            format="json",
        ).json()["id"]

        vazgec = istemci.post(f"{PARTILER}{pk}/discard/")
        assert vazgec.status_code == 200 and vazgec.json()["status"] == "DISCARDED"

        yeni = istemci.post(f"{PARTILER}{pk}/reprint/", {"start_cell": 5}, format="json")
        assert yeni.status_code == 201
        assert yeni.json()["reprint_of"] == pk and yeni.json()["start_cell"] == 5
        assert istemci.get(f"{PARTILER}{pk}/").json()["status"] == "DISCARDED"
        assert istemci.get(f"{PARTILER}999999/").status_code == 404

    def test_yeniden_basimda_null_kalibrasyon_kaldirir_gonderilmeyen_tasinir(
        self, istemci: APIClient
    ) -> None:
        """Ön yüzün "Yazıcı: yok" seçimi `calibration: null` gönderir; yutulmamalı."""
        (nusha,) = kuyruk_ortak.nushalar(1)
        sablon = kuyruk_ortak.sablon()
        yazici = kuyruk_ortak.kalibrasyon(sablon)
        pk = istemci.post(
            PARTILER,
            {
                "kind": "BARCODE",
                "template": sablon.pk,
                "calibration": yazici.pk,
                "copies": [nusha.pk],
            },
            format="json",
        ).json()["id"]
        istemci.post(f"{PARTILER}{pk}/discard/")

        kaldirilan = istemci.post(f"{PARTILER}{pk}/reprint/", {"calibration": None}, format="json")
        assert kaldirilan.status_code == 201, kaldirilan.json()
        assert kaldirilan.json()["calibration"] is None

        tasinan = istemci.post(f"{PARTILER}{pk}/reprint/", {"start_cell": 2}, format="json")
        assert tasinan.status_code == 201 and tasinan.json()["calibration"] == yazici.pk


def test_indirme_adlari_motorun_ve_on_yuzun_belge_adlariyla_ayni() -> None:
    """Kuyruk, motoru (WeasyPrint) yüklememek için adları kopyalar; kopya kaymasın."""
    from apps.kutuphane.labels.content import LabelSelection
    from apps.kutuphane.labels.render import DOCUMENT_NAMES

    assert set(label_queue.DOCUMENT_NAMES) == set(LabelPrintKind.values)
    for tur, ad in label_queue.DOCUMENT_NAMES.items():
        assert DOCUMENT_NAMES[LabelSelection(tur)] == ad
    assert DOCUMENT_NAMES[LabelSelection.BLANK_BARCODE] == rezervasyon.BLANK_DOCUMENT_NAME


# ============================================================ Doğrulama okutması
def test_dogrulama_ucu_her_zaman_govde_doner(istemci: APIClient) -> None:
    isbn = istemci.post(DOGRULA, {"code": "9786053321245"}, format="json")
    assert isbn.status_code == 200
    assert isbn.json()["result"] == "rejected" and isbn.json()["kind"] == "ISBN"

    bos = istemci.post(DOGRULA, {"code": ""}, format="json")
    assert bos.status_code == 200 and bos.json()["result"] == "rejected"


# ============================================================ Boş barkod aralığı
class TestAralikUclari:
    def test_ayir_listele_ayrinti(self, istemci: APIClient) -> None:
        yanit = istemci.post(ARALIKLAR, {"count": 3, "note": "Tarih rafı"}, format="json")
        assert yanit.status_code == 201, yanit.json()
        govde = _json(yanit)
        assert govde["count"] == 3 and govde["open_count"] == 3
        assert [n["state"] for n in govde["numbers"]] == ["OPEN"] * 3
        assert govde["numbers"][0]["state_display"] == "Bağlanmadı"
        assert govde["first_barcode_display"].count("-") == 1

        liste = _json(istemci.get(ARALIKLAR))
        assert liste["count"] == 1 and liste["results"][0]["open_count"] == 3
        ayrinti = _json(istemci.get(f"{ARALIKLAR}{govde['id']}/"))
        assert len(ayrinti["numbers"]) == 3

    @pytest.mark.parametrize("adet", [0, 1301, "çok"])
    def test_adet_denetimi(self, istemci: APIClient, adet: object) -> None:
        yanit = istemci.post(ARALIKLAR, {"count": adet}, format="json")
        assert yanit.status_code == 400 and "count" in yanit.json()["fields"]
        assert not ReservedBarcode.objects.exists()

    def test_pdf_basim_isareti_ve_iptal(
        self, istemci: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isler = kuyruk_ortak.motoru_bagla(monkeypatch)
        aralik = rezervasyon.reserve(3)
        kodlar = list(aralik.numbers.order_by("accession_no").values_list("barcode", flat=True))
        sablon = kuyruk_ortak.sablon()

        pdf = istemci.get(f"{ARALIKLAR}{aralik.pk}/pdf/", {"template": sablon.pk, "start_cell": 60})
        assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
        ilk, son = (barcode_module.format_barcode(kod) for kod in (kodlar[0], kodlar[-1]))
        assert f"Boş-Barkod-Etiketi_{ilk}_{son}_{timezone.localdate():%d.%m.%Y}.pdf" in unquote(
            pdf["Content-Disposition"]
        )
        assert list(isler[0].barcodes) == kodlar and isler[0].kind == "BLANK"
        assert isler[0].start_cell == 60 and list(isler[0].copies) == []
        aralik.refresh_from_db()
        assert aralik.printed_at is None  # D10: PDF basıldı değildir

        tekli = istemci.get(
            f"{ARALIKLAR}{aralik.pk}/pdf/", {"template": str(sablon.pk), "barcodes": kodlar[1]}
        )
        assert tekli.status_code == 200 and list(isler[1].barcodes) == [kodlar[1]]
        assert istemci.get(f"{ARALIKLAR}{aralik.pk}/pdf/").status_code == 400  # şablon yok

        onay = istemci.post(f"{ARALIKLAR}{aralik.pk}/confirm-print/")
        assert onay.status_code == 200 and onay.json()["printed_at"] is not None
        geri = istemci.post(f"{ARALIKLAR}{aralik.pk}/revert-print/")
        assert geri.status_code == 200 and geri.json()["printed_at"] is None

        iptal = istemci.post(
            f"{ARALIKLAR}{aralik.pk}/cancel/",
            {"barcodes": [kodlar[0]], "reason": "Etiket yırtıldı"},
            format="json",
        )
        assert iptal.status_code == 200 and iptal.json()["cancelled"] == 1
        assert iptal.json()["reservation"]["cancelled_count"] == 1
        hepsi = istemci.post(f"{ARALIKLAR}{aralik.pk}/cancel/", {}, format="json")
        assert hepsi.json()["cancelled"] == 2
        assert hepsi.json()["reservation"]["open_count"] == 0

    def test_on_denetim_ve_etiketten_nusha(self, istemci: APIClient) -> None:
        aralik = rezervasyon.reserve(1)
        kod = aralik.first_barcode
        eser = ortak.eser()
        edinim = ortak.edinim()

        denetim = _json(istemci.get(ON_DENETIM, {"code": kod}))
        assert denetim["bindable"] is True

        yanit = istemci.post(
            ETIKETTEN_NUSHA,
            {"work": eser.pk, "acquisition": edinim.pk, "label_code": kod},
            format="json",
        )
        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["barcode"] == kod
        assert yanit.json()["spine_label_printed_at"] is None

        ikinci = istemci.post(
            ETIKETTEN_NUSHA,
            {"work": eser.pk, "acquisition": edinim.pk, "label_code": kod},
            format="json",
        )
        assert ikinci.status_code == 400
        assert "label_code" in ikinci.json()["fields"]
        assert "zaten kayıtlı bir nüshanın" in ikinci.json()["message"]

        etiketsiz = istemci.post(
            ETIKETTEN_NUSHA, {"work": eser.pk, "acquisition": edinim.pk}, format="json"
        )
        assert etiketsiz.status_code == 400 and "label_code" in etiketsiz.json()["fields"]
