"""Yöntem B uçtan uca: boş barkod aralığı ayır → bas → hızlı kayıtta bağla (F4 kod kapısı).

Okulun ASIL yolu (tasarım §8.1, S8): hazır liste yoktur; numaralar önce
ayrılır, boş etiketler basılıp kitaplara yapıştırılır, sonra kitap elde künye
girilirken etiket okutulur ve nüsha O numarayla açılır. Künye tamamlanınca
sırt etiketi (yer numarası) basılır.

Akışın bütünü yalnız API üzerinden yürür (ön yüzün yapacağı istekler). İlk
testte etiket motoru sahte motorla değiştirilir (`kuyruk_ortak.motoru_bagla`) ve
motora giden işler sınanır; ikinci test GERÇEK motordan geçer (kuyruk ↔ motor
bağlantısı). Motorun ölçü ve içerik ayrıntıları L kolunun testlerindedir.
Bütün veriler uydurmadır.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.models import Copy
from apps.kutuphane.services import numbering
from apps.kutuphane.tests import kuyruk_ortak, ortak

pytestmark = pytest.mark.django_db

API = "/api/v1/library/"


def _pdf_govdesi(yanit: Any) -> bytes:
    """`FileResponse` akışının baytları."""
    return b"".join(yanit.streaming_content)


def _json(yanit: Any, beklenen: int = 200) -> Any:
    assert yanit.status_code == beklenen, yanit.json()
    return yanit.json()


def test_bos_barkod_araligi_ayir_bas_bagla_sirt_bas(monkeypatch: pytest.MonkeyPatch) -> None:
    isler = kuyruk_ortak.motoru_bagla(monkeypatch)
    istemci = APIClient()
    sablon = kuyruk_ortak.sablon()
    edinim = ortak.edinim()

    # 1) Ayır — bir tabaka (65 etiket).
    aralik = _json(istemci.post(f"{API}barcode-reservations/", {"count": 65}, format="json"), 201)
    numaralar = [satir["barcode"] for satir in aralik["numbers"]]
    assert len(numaralar) == 65 and len(set(numaralar)) == 65

    # 2) Bas — PDF basıldı DEĞİLDİR; kullanıcı onaylar.
    pdf = istemci.get(f"{API}barcode-reservations/{aralik['id']}/pdf/", {"template": sablon.pk})
    assert pdf.status_code == 200
    assert list(isler[-1].barcodes) == numaralar
    assert _json(istemci.get(f"{API}barcode-reservations/{aralik['id']}/"))["printed_at"] is None
    onay = _json(istemci.post(f"{API}barcode-reservations/{aralik['id']}/confirm-print/"))
    assert onay["printed_at"] is not None

    # 3) Hızlı kayıt — kitap elde: önce etiketin ön denetimi, sonra eser, sonra bağlama.
    kitaptaki = barcode_module.format_barcode(numaralar[4])  # okuyucu basılı biçimi de verir
    denetim = _json(istemci.get(f"{API}barcode-reservations/check/", {"code": kitaptaki}))
    assert denetim["bindable"] is True and denetim["kind"] == "RESERVED"
    eser = _json(
        istemci.post(
            f"{API}works/",
            {"title": "Deneme Kitabı", "authors": "Deniz Korkmaz", "classification_code": "813"},
            format="json",
        ),
        201,
    )
    nusha = _json(
        istemci.post(
            f"{API}copies/from-label/",
            {"work": eser["id"], "acquisition": edinim.pk, "label_code": kitaptaki},
            format="json",
        ),
        201,
    )
    assert nusha["barcode"] == numaralar[4]
    assert nusha["accession_no"] == int(numaralar[4])
    assert nusha["label_printed_at"] == onay["printed_at"]
    assert nusha["label_verified_at"] is not None

    # Aynı etiket ikinci kitaba bağlanamaz.
    ikinci = istemci.post(
        f"{API}copies/from-label/",
        {"work": eser["id"], "acquisition": edinim.pk, "label_code": kitaptaki},
        format="json",
    )
    assert ikinci.status_code == 400
    assert Copy.objects.filter(barcode=numaralar[4]).count() == 1

    # Etiketsiz kitap: bugünkü yol — sayaçtan YENİ numara (aralığın ötesinde).
    etiketsiz = _json(
        istemci.post(
            f"{API}copies/", {"work": eser["id"], "acquisition": edinim.pk}, format="json"
        ),
        201,
    )
    assert int(etiketsiz["barcode"]) > int(numaralar[-1])

    # Doğrulama okutması bağlanan nüshada zaten yapılmıştır.
    okutma = _json(istemci.post(f"{API}labels/verify/", {"code": kitaptaki}, format="json"))
    assert okutma["result"] == "already_verified"
    # Henüz bağlanmamış bir etiket ayrı ileti alır (dolaşım masası F6 da aynısını der).
    bos = _json(istemci.post(f"{API}labels/verify/", {"code": numaralar[5]}, format="json"))
    assert bos["kind"] == "RESERVED" and "henüz bir kitaba bağlanmadı" in bos["message"]

    # 4) Sırt etiketi — bağlanan nüsha yalnız sırt kuyruğundadır (ikinci barkod basılmaz).
    sirt_kuyrugu = _json(
        istemci.get(f"{API}labels/queue/", {"kind": "SPINE", "reservation": aralik["id"]})
    )
    assert [s["id"] for s in sirt_kuyrugu["results"]] == [nusha["id"]]
    ikisi = _json(istemci.get(f"{API}labels/queue/", {"kind": "BOTH"}))
    assert nusha["id"] not in [s["id"] for s in ikisi["results"]]

    parti = _json(
        istemci.post(
            f"{API}labels/batches/",
            {
                "kind": "SPINE",
                "template": sablon.pk,
                "from_queue": True,
                "reservation": aralik["id"],
            },
            format="json",
        ),
        201,
    )
    assert istemci.get(f"{API}labels/batches/{parti['id']}/pdf/").status_code == 200
    assert isler[-1].kind == "SPINE" and [c.pk for c in isler[-1].copies] == [nusha["id"]]
    _json(istemci.post(f"{API}labels/batches/{parti['id']}/confirm/"))
    assert (
        _json(istemci.get(f"{API}labels/queue/", {"kind": "SPINE", "reservation": aralik["id"]}))[
            "count"
        ]
        == 0
    )

    # 5) Rapor ve iptal — kullanılmayan numaralar iptal edilir, sayaca dönmez.
    rapor = _json(istemci.get(f"{API}barcode-reservations/"))["results"][0]
    assert (rapor["open_count"], rapor["bound_count"], rapor["cancelled_count"]) == (64, 1, 0)
    iptal = _json(
        istemci.post(
            f"{API}barcode-reservations/{aralik['id']}/cancel/",
            {"reason": "Dönem sonu"},
            format="json",
        )
    )
    assert iptal["cancelled"] == 64
    ozet = _json(istemci.get(f"{API}labels/summary/"))
    assert ozet["reservations"] == {"reserved": 65, "bound": 1, "cancelled": 64, "open": 0}
    # İptal edilen numaraların hiçbiri bundan sonra verilmez.
    yeni = numbering.next_copy_identity()[1]
    assert yeni not in numaralar and int(yeni) > int(etiketsiz["barcode"])


def test_gercek_motorla_bos_etiket_ve_parti_pdfi_isaretlere_dokunmaz() -> None:
    """Kuyruk ↔ motor bağlantısı (sahte motor YOK): gerçek PDF, işaret yok (D10).

    Motorun ölçü ve içerik ayrıntıları L kolunun testlerindedir; burada yalnız
    kuyruk tarafının `LabelJob`'ının motordan geçip PDF döndüğü ve PDF üretmenin
    hiçbir işareti yazmadığı sınanır.
    """
    istemci = APIClient()
    sablon = kuyruk_ortak.sablon()
    aralik = _json(istemci.post(f"{API}barcode-reservations/", {"count": 3}, format="json"), 201)

    bos = istemci.get(
        f"{API}barcode-reservations/{aralik['id']}/pdf/",
        {"template": sablon.pk, "start_cell": 64},
    )
    assert bos.status_code == 200, bos.content[:200]
    assert _pdf_govdesi(bos).startswith(b"%PDF")
    assert _json(istemci.get(f"{API}barcode-reservations/{aralik['id']}/"))["printed_at"] is None

    nusha = _json(
        istemci.post(
            f"{API}copies/from-label/",
            {
                "work": ortak.eser(classification_code="813").pk,
                "acquisition": ortak.edinim().pk,
                "label_code": aralik["numbers"][0]["barcode"],
            },
            format="json",
        ),
        201,
    )
    parti = _json(
        istemci.post(
            f"{API}labels/batches/",
            {"kind": "SPINE", "template": sablon.pk, "copies": [nusha["id"]]},
            format="json",
        ),
        201,
    )
    pdf = istemci.get(f"{API}labels/batches/{parti['id']}/pdf/")
    assert pdf.status_code == 200
    assert _pdf_govdesi(pdf).startswith(b"%PDF")
    assert Copy.objects.get(pk=nusha["id"]).spine_label_printed_at is None
