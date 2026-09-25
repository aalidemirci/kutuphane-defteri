"""Teslim ve kayıp/hasar belgeleri: E15 ve E6 (tasarım §9-9, §9-11, §10).

- **Teslim listesi** (E15, U11): bir toplu teslimin (aynı belge no) nüshaları; ya
  da bir şubenin (sınıf kitaplığının) veya öğretmenin ŞU AN teslimdeki nüshaları.
  Şube tesliminde liste, ortak kullanım alanına verilen taşınırların Dayanıklı
  Taşınırlar Listesi işlevini görür (TMY 23/6'ya KIYASEN — §9-11, AT-1); sayımda
  nasıl işlem göreceğini sayım kurulu seçer, liste bunu söylemez. **Teslim ödünç
  değildir** (sözlük: "zimmet", "emanet" değil).
- **Geri alma dökümü** (E15): geri alma okutmasında kapanan teslimler ya da bir
  teslim listesinin (belge no) güncel durumu — geri alınan, teslimde kalan, kayba
  dönüşen.
- **Kayıp/hasar tutanağı** (E6, Md. 19): kurumsal biçim, imza alanları. Kişinin
  adı üyelikten ya da öğretmene teslimden çözülür (ŞİFRELİ alan); sorumlu notu da
  şifrelidir. Md. 19 (bedel) YALNIZ ortaöğretimde anılır — ilkokul ve ortaokulda
  bedel ve Md. 19 alıntısı basılmaz. Program tahsilat yapmaz: piyasa bedeli
  kayıttır, tutanak "ödeme ya da tahsilat belgesi değildir" der; bedelin
  belirlendiği ve teslim alındığı tarihler (iki adım) bedel satırında yazar. Disiplin
  süreci anılmaz (OKY 164/1-g programın işi değildir — §9-9).

Belgeler yalnız yönetici kipinde basılır (uçlar görevli izin listesinde değildir).
PDF'ler yalnız `shared.pdf.html_to_pdf` kapısından üretilir. Bu modül veritabanına
YAZMAZ. Hata iletilerinde kişi adı yoktur.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_teslim
from apps.kutuphane.models import (
    CaseType,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    LossDamageCase,
)
from apps.kutuphane.selectors_ilisik import SILINMIS_KISI, member_kind_text
from apps.okul.models import ClassSection, Personnel, SchoolConfig, SchoolLevel, Student
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

TESLIM_LISTESI_SABLONU: Final = "documents/teslim_listesi.html"
GERI_ALMA_SABLONU: Final = "documents/geri_alma_dokumu.html"
TUTANAK_SABLONU: Final = "documents/kayip_hasar_tutanagi.html"

#: Belge adları (sözlük §2: E6, E15) — başlıklar ve indirme adları buradan.
TESLIM_LISTESI_ADI: Final = "Teslim Listesi"
GERI_ALMA_ADI: Final = "Geri Alma Dökümü"
TUTANAK_ADI: Final = "Kayıp-Hasar Tutanağı"

#: Tek listede en çok satır (toplu teslim sınırıyla aynı ölçek).
MAX_ROWS: Final = 500

#: Md. 19/1'in birinci cümlesi — docs/mevzuat ile BİREBİR (test sınar).
MD19_ALINTI: Final = (
    "Ortaöğretim okul kütüphanelerinde hasara uğratılan veya kaybedilen kaynak ilgili kişiden "
    "temin edilir, temin edilememesi hâlinde o günkü piyasa bedeli, hasara uğratan veya "
    "kaybeden kişiden alınır."
)
TAHSILAT_NOTU: Final = "Bu tutanak bir ödeme ya da tahsilat belgesi değildir."

SUBE_NOTU: Final = (
    "Liste, sınıf kitaplığına teslim edilen kütüphane kaynaklarını gösterir ve ortak "
    "kullanım alanına verilen taşınırlar için düzenlenen Dayanıklı Taşınırlar Listesinin "
    "işlevini görür (Taşınır Mal Yönetmeliği md. 23/6'ya kıyasen). Teslim ödünç değildir."
)
OGRETMEN_NOTU: Final = (
    "Liste, öğretmene teslim edilen kütüphane kaynaklarını gösterir. Teslim ödünç "
    "değildir; kaynaklar kütüphaneye geri verildiğinde geri alma okutmasıyla kapanır."
)

NO_ROWS_MESSAGE: Final = "Bu seçimde teslim kaydı yok."
SCOPE_REQUIRED_MESSAGE: Final = "Belge no, şube ya da öğretmen seçin."
TOO_MANY_MESSAGE: Final = f"Tek belgede en çok {MAX_ROWS} satır olabilir."


def _gun(on: date | None = None) -> date:
    return on or timezone.localdate()


def _tarih(gun: date | None) -> str:
    return f"{gun:%d.%m.%Y}" if gun is not None else "—"


def _okul_adi(config: SchoolConfig) -> str:
    return " ".join((config.school_name or config.kisa_ad or "").split())


def _antet(config: SchoolConfig) -> dict[str, str]:
    return letterhead_context(
        school_name=_okul_adi(config),
        district=config.district,
        principal_name=config.principal_name,
    )


def _barkod(copy: Any) -> str:
    return barcode_module.format_barcode(copy.barcode)


def _kisi_adi(person: Student | Personnel | None) -> str:
    if person is None:
        return ""
    if person.deleted_at is not None:
        return SILINMIS_KISI
    return " ".join(person.full_name.split())


def recipient_text(delivery: Delivery) -> str:
    """Teslim alanın belgedeki adı: '9/A sınıf kitaplığı' ya da öğretmenin adı."""
    if delivery.recipient_kind == DeliveryRecipientKind.SECTION:
        etiket = selectors_teslim.delivery_recipient_label(delivery)
        return f"{etiket} sınıf kitaplığı" if etiket else "Sınıf kitaplığı"
    return _kisi_adi(delivery.personnel) or "—"


def turkish_money(value: Decimal) -> str:
    """'1234.5' → '1.234,50 TL' (Türkçe binlik ve ondalık ayırıcı)."""
    tam, _, kurus = f"{value:,.2f}".partition(".")
    return f"{tam.replace(',', '.')},{kurus} TL"


# ---------------------------------------------------------------------------
# E15 — Teslim listesi
# ---------------------------------------------------------------------------
def delivery_list_rows(
    *,
    document_no: str = "",
    section: ClassSection | None = None,
    personnel: Personnel | None = None,
) -> list[Delivery]:
    """Teslim listesinin satırları — okutma (kayıt) sırasıyla.

    Belge no verilirse o toplu teslimin BÜTÜN satırları (sonradan geri alınmış
    olsa da: liste teslimin belgesidir). Şube ya da öğretmen verilirse o alanın
    ŞU AN teslimdeki nüshaları.
    """
    belge = document_no.strip()
    if belge:
        qs = selectors_teslim.deliveries(document_no=belge)
    elif section is not None:
        qs = selectors_teslim.deliveries(status=DeliveryStatus.OPEN, section_id=section.pk)
    elif personnel is not None:
        qs = selectors_teslim.deliveries(status=DeliveryStatus.OPEN, personnel_id=personnel.pk)
    else:
        raise ValidationError(SCOPE_REQUIRED_MESSAGE)
    satirlar = sorted(qs, key=lambda d: (d.delivered_on, d.pk))
    if not satirlar:
        raise ValidationError(NO_ROWS_MESSAGE)
    if len(satirlar) > MAX_ROWS:
        raise ValidationError(TOO_MANY_MESSAGE)
    return satirlar


def _alan_turu(rows: Sequence[Delivery]) -> str:
    turler = {d.recipient_kind for d in rows}
    return next(iter(turler)) if len(turler) == 1 else ""


def delivery_list_context(
    rows: Sequence[Delivery], *, document_no: str = "", on: date | None = None
) -> dict[str, Any]:
    gun = _gun(on)
    config = SchoolConfig.load()
    ilk = rows[0]
    tur = _alan_turu(rows)
    belgeler = list(dict.fromkeys(d.document_no for d in rows))
    teslim_tarihleri = sorted({d.delivered_on for d in rows})
    donusler = sorted({d.expected_return for d in rows if d.expected_return is not None})
    alanlar = list(dict.fromkeys(recipient_text(d) for d in rows))
    bilgi = [
        ("Belge no", ", ".join(belgeler)),
        ("Teslim alan", ", ".join(alanlar)),
        (
            "Teslim tarihi",
            _tarih(teslim_tarihleri[0])
            if len(teslim_tarihleri) == 1
            else f"{_tarih(teslim_tarihleri[0])} – {_tarih(teslim_tarihleri[-1])}",
        ),
        ("Beklenen dönüş", ", ".join(_tarih(t) for t in donusler) if donusler else "—"),
        ("Kitap sayısı", str(len(rows))),
    ]
    if ilk.recipient_kind == DeliveryRecipientKind.SECTION and ilk.section is not None:
        yil = ilk.section.school_year
        if yil is not None:
            bilgi.insert(2, ("Ders yılı", yil.name))
    tek_belge = len(belgeler) == 1
    satirlar = [
        {
            "no": sira,
            "barcode": _barkod(d.copy),
            "title": d.copy.work.title,
            "authors": d.copy.work.authors,
            "document_no": d.document_no,
        }
        for sira, d in enumerate(rows, start=1)
    ]
    return {
        **_antet(config),
        "document_title": "TESLİM LİSTESİ",
        "issued_on": _tarih(gun),
        "info": [{"label": e, "value": v} for e, v in bilgi],
        "rows": satirlar,
        "show_document_column": not tek_belge,
        "note": SUBE_NOTU if tur == DeliveryRecipientKind.SECTION else OGRETMEN_NOTU,
        "receiver_role": (
            "Sınıf kitaplığı sorumlusu"
            if tur == DeliveryRecipientKind.SECTION
            else ("Öğretmen" if tur == DeliveryRecipientKind.TEACHER else "Teslim alan")
        ),
        "receiver_name": (
            alanlar[0] if tur == DeliveryRecipientKind.TEACHER and len(alanlar) == 1 else ""
        ),
    }


def delivery_list_pdf(
    rows: Sequence[Delivery], *, document_no: str = "", on: date | None = None
) -> bytes:
    baglam = delivery_list_context(rows, document_no=document_no, on=on)
    return html_to_pdf(render_to_string(TESLIM_LISTESI_SABLONU, baglam))


# ---------------------------------------------------------------------------
# E15 — Geri alma dökümü
# ---------------------------------------------------------------------------
def take_back_rows(*, delivery_ids: Sequence[int] = (), document_no: str = "") -> list[Delivery]:
    """Dökümün satırları: verilen teslimler (okutma oturumu) ya da bir belge no'nun bütünü."""
    belge = document_no.strip()
    if belge:
        qs = selectors_teslim.deliveries(document_no=belge)
    elif delivery_ids:
        qs = selectors_teslim.deliveries(ids=[int(i) for i in delivery_ids])
    else:
        raise ValidationError("Geri alma dökümü için belge no ya da geri alınan teslimler gerekir.")
    satirlar = sorted(qs, key=lambda d: (d.delivered_on, d.document_no, d.pk))
    if not satirlar:
        raise ValidationError(NO_ROWS_MESSAGE)
    if len(satirlar) > MAX_ROWS:
        raise ValidationError(TOO_MANY_MESSAGE)
    return satirlar


def delivery_state_text(delivery: Delivery) -> str:
    """'Geri alındı · 12.06.2027' · 'Teslimde' · 'Kayba dönüştü · 03.05.2027'."""
    if delivery.status == DeliveryStatus.RETURNED and delivery.returned_at is not None:
        return f"Geri alındı · {timezone.localdate(delivery.returned_at):%d.%m.%Y}"
    if delivery.status == DeliveryStatus.LOST_CONVERTED and delivery.lost_at is not None:
        return f"Kayba dönüştü · {timezone.localdate(delivery.lost_at):%d.%m.%Y}"
    return str(delivery.get_status_display())


def take_back_context(
    rows: Sequence[Delivery], *, document_no: str = "", on: date | None = None
) -> dict[str, Any]:
    gun = _gun(on)
    config = SchoolConfig.load()
    sayilar = {s: sum(1 for d in rows if d.status == s) for s in DeliveryStatus.values}
    alanlar = list(dict.fromkeys(recipient_text(d) for d in rows))
    tur = _alan_turu(rows)
    ozet = [f"{sayilar[DeliveryStatus.RETURNED]} kitap geri alındı"]
    if sayilar[DeliveryStatus.OPEN]:
        ozet.append(f"{sayilar[DeliveryStatus.OPEN]} kitap teslimde")
    if sayilar[DeliveryStatus.LOST_CONVERTED]:
        ozet.append(f"{sayilar[DeliveryStatus.LOST_CONVERTED]} kitap kayba dönüştü")
    bilgi = [
        (
            "Kapsam",
            f"Belge no {document_no.strip()}" if document_no.strip() else "Geri alınan kitaplar",
        ),
        ("Teslim alan", ", ".join(alanlar)),
        ("Özet", " · ".join(ozet)),
    ]
    return {
        **_antet(config),
        "document_title": "GERİ ALMA DÖKÜMÜ",
        "issued_on": _tarih(gun),
        "info": [{"label": e, "value": v} for e, v in bilgi],
        "rows": [
            {
                "no": sira,
                "barcode": _barkod(d.copy),
                "title": d.copy.work.title,
                "recipient": recipient_text(d),
                "document_no": d.document_no,
                "delivered_on": _tarih(d.delivered_on),
                "state": delivery_state_text(d),
            }
            for sira, d in enumerate(rows, start=1)
        ],
        "giver_role": (
            "Sınıf kitaplığı sorumlusu"
            if tur == DeliveryRecipientKind.SECTION
            else ("Öğretmen" if tur == DeliveryRecipientKind.TEACHER else "Geri veren")
        ),
        "giver_name": alanlar[0]
        if tur == DeliveryRecipientKind.TEACHER and len(alanlar) == 1
        else "",
    }


def take_back_pdf(
    rows: Sequence[Delivery], *, document_no: str = "", on: date | None = None
) -> bytes:
    return html_to_pdf(
        render_to_string(GERI_ALMA_SABLONU, take_back_context(rows, document_no=document_no, on=on))
    )


# ---------------------------------------------------------------------------
# E6 — Kayıp/hasar tutanağı
# ---------------------------------------------------------------------------
def _kisi_etiketi(person: Student | Personnel | None) -> str:
    if isinstance(person, Student):
        return person.class_label
    if isinstance(person, Personnel):
        return member_kind_text(person)
    return ""


def _ortaogretim() -> bool:
    return SchoolConfig.load().kademe == SchoolLevel.ORTAOGRETIM


def _bedel_metni(case: LossDamageCase) -> str:
    """Piyasa bedeli satırı: tutar ve Md. 19'un iki adımının tarihleri (tek satır — sayfa bütçesi).

    Örnek: "1.234,50 TL (kayıt); 12.09.2026 tarihinde belirlendi, 20.09.2026 tarihinde
    teslim alındı". Program tahsilat yapmaz; "teslim alındı" yalnız kayıttır.
    """
    assert case.market_price is not None
    metin = f"{turkish_money(case.market_price)} (kayıt)"
    adimlar: list[str] = []
    if case.price_determined_at is not None:
        adimlar.append(
            f"{_tarih(timezone.localdate(case.price_determined_at))} tarihinde belirlendi"
        )
    if case.price_received_at is not None:
        adimlar.append(
            f"{_tarih(timezone.localdate(case.price_received_at))} tarihinde teslim alındı"
        )
    return f"{metin}; {', '.join(adimlar)}" if adimlar else metin


def case_report_context(case: LossDamageCase, *, on: date | None = None) -> dict[str, Any]:
    gun = _gun(on)
    config = SchoolConfig.load()
    kisi = selectors_teslim.case_person(case)
    ad = _kisi_adi(kisi)
    nusha = case.copy
    eser = nusha.work
    kayip = case.case_type == CaseType.LOST
    olay = "kaybolduğu" if kayip else "hasar gördüğü"

    kaynak = [
        ("Kaynak adı", eser.title),
        ("Yazar", eser.authors or "—"),
        ("Barkod", _barkod(nusha)),
        ("Kayıt no", str(nusha.accession_no)),
    ]
    if nusha.external_asset_ref:
        kaynak.append(("TKYS kodu", nusha.external_asset_ref))

    ilgili: list[tuple[str, str]] = []
    if ad:
        ilgili.append(("Adı soyadı", ad))
        etiket = _kisi_etiketi(kisi)
        if etiket:
            ilgili.append(("Sınıf / görevi", etiket))
    if case.loan is not None:
        lo = case.loan
        ilgili.append(
            (
                "Ödünç",
                f"{timezone.localdate(lo.loaned_at):%d.%m.%Y} tarihinde verildi; iade tarihi "
                f"{lo.due_date:%d.%m.%Y}",
            )
        )
    if case.delivery is not None:
        d = case.delivery
        ilgili.append(
            (
                "Teslim",
                f"{recipient_text(d)} — belge no {d.document_no}, {d.delivered_on:%d.%m.%Y}",
            )
        )
    if case.responsible_note.strip():
        # Satır sonları boşluğa iner: 500 karakterlik not satır satır yazılırsa
        # tutanağı ikinci sayfaya taşırdı (sayfa bütçesi — tek sayfa).
        ilgili.append(("Açıklama", " ".join(case.responsible_note.split())))
    if not ilgili:
        ilgili.append(("İlgili kişi", "Belirlenmedi"))

    cozum = [("Durum", str(case.get_resolution_display()))]
    if case.resolved_at is not None:
        cozum.append(("Çözüm tarihi", _tarih(timezone.localdate(case.resolved_at))))
    if case.write_off_proposed_at is not None:
        cozum.append(
            (
                "Kayıttan düşme",
                f"{_tarih(timezone.localdate(case.write_off_proposed_at))} tarihinde önerildi; "
                "kayıttan düşme taşınır işlemleriyle yapılır.",
            )
        )
    ortaogretim = _ortaogretim()
    if ortaogretim and case.market_price is not None:
        cozum.append(("Piyasa bedeli", _bedel_metni(case)))

    return {
        **_antet(config),
        "document_title": "KAYIP/HASAR TUTANAĞI",
        "issued_on": _tarih(gun),
        "case_type": str(case.get_case_type_display()),
        "statement": (
            f"Aşağıda bilgileri yazılı kütüphane kaynağının {olay} "
            f"{case.reported_on:%d.%m.%Y} tarihinde tespit edilmiştir. Bu tutanak aşağıda "
            "imzası bulunanlarca düzenlenmiştir."
        ),
        "source": [{"label": e, "value": v} for e, v in kaynak],
        "person": [{"label": e, "value": v} for e, v in ilgili],
        "resolution": [{"label": e, "value": v} for e, v in cozum],
        "md19": MD19_ALINTI if ortaogretim else "",
        "payment_note": TAHSILAT_NOTU if ortaogretim else "",
        "person_name": ad if ad and ad != SILINMIS_KISI else "",
    }


def case_report_pdf(case: LossDamageCase, *, on: date | None = None) -> bytes:
    return html_to_pdf(render_to_string(TUTANAK_SABLONU, case_report_context(case, on=on)))
