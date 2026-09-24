"""Etiket ekranlarının gönderdiği gövdeler GERÇEK etiket motorundan geçer (F4 bütünleştirme).

Ön yüz (`frontend/src/modules/kutuphane/etiketApi.ts`) isteklerini sabit
biçimde kurar: seçilmeyen kalibrasyon ve ayrı sırt tabakası `null` gider,
kuyruktan basımda boş süzgeçler `null` gider, ölçüler JSON'da SAYIDIR. Bu
dosya o gövdeleri olduğu gibi uçlara verir ve kuyruk kolunun (Q) ucunun etiket
motoruna (L) bağlandığını sahte motor OLMADAN sınar:

    kuyruk → parti aç → PDF (gerçek motor) → "Basıldı olarak işaretle"
    → yeniden basım → kalibrasyon sayfası → şablon ve kalibrasyon yazma
    → boş barkod aralığı → hızlı kayıtta bağlama.

Motorun ölçü ayrıntıları L kolunun testlerinde, kuyruk kuralları Q kolunun
testlerindedir; burada yalnız iki kolun ön yüz gövdeleriyle birlikte çalıştığı
kanıtlanır. Bütün veriler uydurmadır.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane.models import Copy, LabelKind, LabelSheetTemplate
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

API = "/api/v1/library/"


def _json(yanit: Any, beklenen: int = 200) -> Any:
    assert yanit.status_code == beklenen, getattr(yanit, "data", yanit.content[:300])
    return yanit.json()


def _pdf(yanit: Any) -> bytes:
    assert yanit.status_code == 200, getattr(yanit, "data", None)
    govde = b"".join(yanit.streaming_content)
    assert govde.startswith(b"%PDF")
    return govde


def _varsayilan(sablonlar: list[dict[str, Any]], tur: str) -> dict[str, Any]:
    return next(s for s in sablonlar if s["kind"] == tur and s["is_default"])


def test_kuyruktan_parti_gercek_motorla_basilir_onaylanir_ve_yeniden_basilir() -> None:
    istemci = APIClient()
    edinim = ortak.edinim()
    eser = ortak.eser(classification_code="813", call_number="813 KOR")
    nushalar = [ortak.nusha(work=eser, acquisition=edinim) for _ in range(3)]

    # Şablon listesi hazır şablonları yazar; ölçüler SAYIDIR (ızgara bu sayılarla çizilir).
    sablonlar = _json(istemci.get(f"{API}label-templates/", {"limit": 200}))["results"]
    barkod = _varsayilan(sablonlar, LabelKind.BARCODE)
    assert isinstance(barkod["label_width"], float) and barkod["labels_per_sheet"] == 65

    # Ön yüzün kuyruk isteği.
    kuyruk = _json(
        istemci.get(
            f"{API}labels/queue/",
            {"limit": "25", "kind": "BOTH", "order": "CALL_NUMBER", "acquisition": str(edinim.pk)},
        )
    )
    assert kuyruk["count"] == 3

    # "Basım partisini hazırla" — seçim yok: kuyruktan, boş süzgeçler null.
    parti = _json(
        istemci.post(
            f"{API}labels/batches/",
            {
                "kind": "BOTH",
                "order": "CALL_NUMBER",
                "template": barkod["id"],
                "calibration": None,
                "spine_template": None,
                "spine_calibration": None,
                "include_qr": False,
                "start_cell": 64,
                "from_queue": True,
                "limit": 3,
                "section": None,
                "acquisition": edinim.pk,
                "reservation": None,
                "created_from": None,
                "created_to": None,
            },
            format="json",
        ),
        201,
    )
    assert parti["status"] == "PENDING" and parti["copy_count"] == 3
    assert [kalem["id"] for kalem in parti["items"]] == sorted(n.pk for n in nushalar)

    # PDF gerçek motordan gelir ve işarete dokunmaz (D10).
    _pdf(istemci.get(f"{API}labels/batches/{parti['id']}/pdf/"))
    assert not Copy.objects.filter(label_printed_at__isnull=False).exists()
    kuyruk = _json(istemci.get(f"{API}labels/queue/", {"kind": "BOTH"}))
    assert kuyruk["results"][0]["pending_batch"] == parti["id"]

    # "Basıldı olarak işaretle".
    onay = _json(istemci.post(f"{API}labels/batches/{parti['id']}/confirm/", {}, format="json"))
    assert onay["status"] == "CONFIRMED"
    assert _json(istemci.get(f"{API}labels/queue/", {"kind": "BOTH"}))["count"] == 0
    assert _json(istemci.get(f"{API}labels/summary/"))["unverified"] == 3

    # "Yeniden bas" — ön yüz içeriği, şablonu, kalibrasyonu (null) ve başlangıç hücresini yollar.
    yeni = _json(
        istemci.post(
            f"{API}labels/batches/{parti['id']}/reprint/",
            {"kind": "BARCODE", "template": barkod["id"], "calibration": None, "start_cell": 3},
            format="json",
        ),
        201,
    )
    assert yeni["reprint_of"] == parti["id"] and yeni["kind"] == "BARCODE"
    _pdf(istemci.get(f"{API}labels/batches/{yeni['id']}/pdf/"))

    # Doğrulama okutması ön yüzün gövdesiyle.
    sonuc = _json(
        istemci.post(f"{API}labels/verify/", {"code": nushalar[0].barcode}, format="json")
    )
    assert sonuc["result"] == "verified"


def test_secilen_nushalar_ayri_sirt_tabakasiyla_ve_kalibrasyonla_basilir() -> None:
    istemci = APIClient()
    sablonlar = _json(istemci.get(f"{API}label-templates/", {"limit": 200}))["results"]
    barkod = _varsayilan(sablonlar, LabelKind.BARCODE)
    sirt = _varsayilan(sablonlar, LabelKind.SPINE)

    # "Yeni yazıcı kalibrasyonu" — kaymalar SAYI; düzenleme aynı şablonu yeniden yollar.
    kalibrasyon = _json(
        istemci.post(
            f"{API}label-calibrations/",
            {
                "template": barkod["id"],
                "printer_name": "Masa yazıcısı",
                "offset_x": 1.5,
                "offset_y": -0.5,
            },
            format="json",
        ),
        201,
    )
    kalibrasyon = _json(
        istemci.patch(
            f"{API}label-calibrations/{kalibrasyon['id']}/",
            {
                "template": barkod["id"],
                "printer_name": "Masa yazıcısı",
                "offset_x": 1.75,
                "offset_y": -0.5,
            },
            format="json",
        )
    )
    assert kalibrasyon["offset_x"] == 1.75

    # Kalibrasyon sayfası: kaymasız ve o yazıcının kaymasıyla.
    _pdf(
        istemci.post(
            f"{API}labels/calibration/",
            {"template": barkod["id"], "calibration": None},
            format="json",
        )
    )
    _pdf(
        istemci.post(
            f"{API}labels/calibration/",
            {"template": barkod["id"], "calibration": kalibrasyon["id"]},
            format="json",
        )
    )

    nushalar = [ortak.nusha() for _ in range(2)]
    parti = _json(
        istemci.post(
            f"{API}labels/batches/",
            {
                "kind": "BOTH",
                "order": "IMPORT_ROW",
                "template": barkod["id"],
                "calibration": kalibrasyon["id"],
                "spine_template": sirt["id"],
                "spine_calibration": None,
                "include_qr": False,
                "start_cell": 1,
                "copies": [n.pk for n in nushalar],
            },
            format="json",
        ),
        201,
    )
    assert parti["printer_name"] == "Masa yazıcısı"
    _pdf(istemci.get(f"{API}labels/batches/{parti['id']}/pdf/"))


def test_sablon_formu_govdesi_ve_bos_barkod_akisi() -> None:
    istemci = APIClient()
    _json(istemci.get(f"{API}label-templates/", {"limit": 200}))

    # "Yeni şablon" — köşe yarıçapı gönderilmez, ölçüler SAYI.
    sablon = _json(
        istemci.post(
            f"{API}label-templates/",
            {
                "name": "Deneme sırt — 25 × 38 mm, 40'lı",
                "kind": "SPINE",
                "label_width": 38.1,
                "label_height": 25,
                "page_margin_top": 8.5,
                "page_margin_left": 4.75,
                "gutter_x": 2.5,
                "gutter_y": 0,
                "rows": 8,
                "cols": 5,
                "is_default": False,
            },
            format="json",
        ),
        201,
    )
    assert sablon["labels_per_sheet"] == 40
    assert LabelSheetTemplate.objects.filter(pk=sablon["id"]).exists()

    # Boş barkod aralığı: ayır → PDF (yalnız seçilen numara) → basıldı → ön denetim → bağla.
    aralik = _json(
        istemci.post(
            f"{API}barcode-reservations/", {"count": 3, "note": "Hikâye rafı"}, format="json"
        ),
        201,
    )
    ilk = aralik["numbers"][0]["barcode"]
    varsayilan = LabelSheetTemplate.objects.get(kind=LabelKind.BARCODE, is_default=True)
    _pdf(
        istemci.get(
            f"{API}barcode-reservations/{aralik['id']}/pdf/",
            {
                "template": varsayilan.pk,
                "start_cell": 7,
                "include_qr": "false",
                "barcodes": ",".join(n["barcode"] for n in aralik["numbers"][1:]),
            },
        )
    )
    _json(
        istemci.post(f"{API}barcode-reservations/{aralik['id']}/confirm-print/", {}, format="json")
    )
    denetim = _json(istemci.get(f"{API}barcode-reservations/check/", {"code": ilk}))
    assert denetim["bindable"] is True

    nusha = _json(
        istemci.post(
            f"{API}copies/from-label/",
            {
                "work": ortak.eser().pk,
                "acquisition": ortak.edinim().pk,
                "section": None,
                "old_register_no": "",
                "is_reference": False,
                "label_code": ilk,
            },
            format="json",
        ),
        201,
    )
    assert nusha["barcode"] == ilk and nusha["spine_label_printed_at"] is None

    # Kullanılmayan numaraların iptali (seçilenler + gerekçe).
    iptal = _json(
        istemci.post(
            f"{API}barcode-reservations/{aralik['id']}/cancel/",
            {"barcodes": [aralik["numbers"][1]["barcode"]], "reason": "Etiket yırtıldı"},
            format="json",
        )
    )
    assert iptal["cancelled"] == 1 and iptal["reservation"]["open_count"] == 1
