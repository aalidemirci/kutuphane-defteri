"""İlişik ve yıl sonu belgeleri: E5 ve yıl sonu iade hatırlatma pusulası (tasarım §8.3, §10).

- **"Kütüphaneden ilişiği yoktur" belgesi** (E5): kişi başına bir sayfa, resmî
  antetli. Yalnız kütüphaneyle açık işi OLMAYAN kişiye basılır (iade edilmemiş
  ödünç, geri alınmamış teslim, "Çözüm bekliyor" ya da "Bedel belirlendi"
  durumunda kayıp/hasar dosyası). Bedeli teslim alınmış dosya kişinin işi
  değildir (25.09.2026 kullanıcı kararı): dosya okul için açık olsa da belge
  basılır; hüküm cümlesi bu yüzden "çözülmemiş kayıt" demez, kişiden "beklenen
  bir işlem" olmadığını söyler. Madde atfı
  **konum kalıbıyla** yapılır (§3 "Program nasıl konumlanır"): belge okulun yerel
  kayıtlarına dayanır ve Bakanlık otomasyon sistemindeki kaydın yerine geçmez.
  **Karne ya da diplomanın ön koşulu diye SUNULMAZ**: Yönetmelikte buna dayanak
  yoktur, Md. 18 yalnız "iadesi sağlanır" der (§8.3; sözlük "İlişik"). Belgede
  karne, diploma, borç ve "ilişik kesme" sözcükleri geçmez (test).
- **İlişik listesi** (E5): açık işi olan kişiler, son sınıflar ve ayrılanlar önce;
  şube (sınıf kitaplığı) teslimleri ayrı tabloda. Toplu liste kişisel veri içerir:
  her sayfada "Kişisel veri içerir — asılmaz, çoğaltılmaz." dipnotu (sözlük §5).
  Veri en aza indirme (OYS `LoanBrief` kalıbı): listede KAYNAK ADI YOKTUR, yalnız
  barkod, iade tarihi ve belge no — liste idareyle paylaşılabilir, okunan kitap
  oraya taşınmaz (ödünç ≠ okuduğu kitap).
- **Yıl sonu iade hatırlatma pusulası** (E4'ün yıl sonu biçimi): E4 pusulasının
  geometrisi ve şablonu (`documents/iade_pusulasi.html`) aynen; içerik kişinin
  BÜTÜN açık ödünçleridir (yalnız gecikmişler değil — yıl sonunda hepsi
  toplanır). Tek kişiliktir, katlanınca içerik görünmez; dış yüz kütüphaneyi anmaz.

PDF'ler yalnız `shared.pdf.html_to_pdf` kapısından üretilir. Bu modül veritabanına
YAZMAZ. Hata iletilerinde kişi adı yoktur.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import dolasim_belgeleri as e4
from apps.kutuphane import selectors_ilisik as ilisik
from apps.kutuphane.labels.geometry import mm_text
from apps.okul.models import SchoolConfig
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

BELGE_SABLONU: Final = "documents/ilisik_belgesi.html"
LISTE_SABLONU: Final = "documents/ilisik_listesi.html"

#: Belge adları (sözlük §2 E5; E4) — başlıklar ve indirme adları buradan.
BELGE_ADI: Final = "Kütüphaneden İlişiği Yoktur Belgesi"
LISTE_ADI: Final = "İlişik Listesi"
YIL_SONU_PUSULA_KAPSAMI: Final = "Yıl-Sonu"

#: Toplu listenin dipnotu (sözlük §5) — her sayfada.
LISTE_DIPNOTU: Final = e4.LISTE_DIPNOTU
#: Tek seferde basılabilecek en çok belge (kişi başına bir sayfa).
MAX_CERTIFICATES: Final = 150

#: Konum kalıbı (§3-1; KM-7). Tırnak içi Md. 18/1'in üçüncü cümlesinden BİREBİR
#: alıntıdır (docs/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md — test sınar).
MD18_ALINTI: Final = "alınan ödünç kitabın kütüphaneye iadesi sağlanır"
KONUM_KALIBI: Final = (
    "Bu belge, okulun kütüphane işlerini yürüttüğü yerel araçtaki kayıtlara göre "
    "düzenlenmiştir. Okul Kütüphaneleri Yönetmeliği Md. 18'deki “… "
    f"{MD18_ALINTI}.” hükmünün uygulanmasına yöneliktir; Bakanlık otomasyon "
    "sistemindeki kaydın yerine geçmez."
)
BELGE_BASLIGI: Final = "KÜTÜPHANEDEN İLİŞİĞİ YOKTUR BELGESİ"
LISTE_BASLIGI: Final = "İLİŞİK LİSTESİ"

#: Açık işi olan kişiye belge istenince (kişi adı YOK).
NOT_CLEAR_MESSAGE: Final = (
    "Seçilenlerden {sayi} kişinin iade edilmemiş kaynağı, geri alınmamış teslimi ya da "
    "çözülmemiş kayıp/hasar dosyası var; belge basılmadı. İlişik listesine bakın."
)
NO_PERSON_MESSAGE: Final = "Belge basılacak kişi seçilmedi."
TOO_MANY_MESSAGE: Final = (
    f"Tek seferde en çok {MAX_CERTIFICATES} kişinin belgesi basılabilir; şube şube basın."
)
NO_COLLECTION_MESSAGE: Final = "Bu seçimde iade edilecek ödünç yok."


def _gun(on: date | None = None) -> date:
    return on or timezone.localdate()


def _okul_adi(config: SchoolConfig) -> str:
    return " ".join((config.school_name or config.kisa_ad or "").split())


def _antet(config: SchoolConfig) -> dict[str, str]:
    return letterhead_context(
        school_name=_okul_adi(config),
        district=config.district,
        principal_name=config.principal_name,
    )


# ---------------------------------------------------------------------------
# E5 — "Kütüphaneden ilişiği yoktur" belgesi
# ---------------------------------------------------------------------------
def certificate_statement(row: ilisik.ClearanceRow, gun: date) -> str:
    """Belgenin hüküm cümlesi — öğrencide ödünç ve dosya, personelde teslim de sayılır.

    Dosya için "kişiden beklenen işlem" denir: bedeli teslim alınmış dosya okul için
    açık kalır ama kişinin işi değildir (25.09.2026 kullanıcı kararı).
    """
    isler = (
        "iade edilmemiş ödünç kaynağı ve kayıp ya da hasar nedeniyle kendisinden beklenen "
        "bir işlem"
        if row.is_student
        else (
            "iade edilmemiş ödünç kaynağı, geri alınmamış teslimi ve kayıp ya da hasar "
            "nedeniyle kendisinden beklenen bir işlem"
        )
    )
    return (
        f"Yukarıda bilgileri yazılı kişinin, okul kütüphanesinin kayıtlarına göre "
        f"{gun:%d.%m.%Y} tarihi itibarıyla {isler} bulunmamaktadır. Kütüphaneden ilişiği "
        "yoktur."
    )


def ensure_certifiable(rows: Sequence[ilisik.ClearanceRow], missing: Sequence[str]) -> None:
    """Belge basılabilir mi? Eksik kişi, açık işi olan kişi ya da boş seçimde 400."""
    if missing:
        raise ValidationError(list(dict.fromkeys(missing)))
    if not rows:
        raise ValidationError(NO_PERSON_MESSAGE)
    if len(rows) > MAX_CERTIFICATES:
        raise ValidationError(TOO_MANY_MESSAGE)
    acik = [r for r in rows if not r.is_clear]
    if acik:
        raise ValidationError(NOT_CLEAR_MESSAGE.format(sayi=len(acik)))


def certificate_context(
    rows: Sequence[ilisik.ClearanceRow], *, on: date | None = None
) -> dict[str, Any]:
    """Belgelerin bağlamı (kişi başına bir sayfa). PDF'siz; test edilebilir."""
    gun = _gun(on)
    config = SchoolConfig.load()
    belgeler = []
    for row in rows:
        satirlar = [("Adı soyadı", row.full_name)]
        if row.is_student:
            satirlar.append(("Okul no", row.student_number))
            satirlar.append(("Sınıf / şube", row.person_label or "—"))
        else:
            satirlar.append(("Görevi", row.person_label))
        if row.status_text:
            satirlar.append(("Durum", row.status_text))
        belgeler.append(
            {
                "rows": [{"label": e, "value": d} for e, d in satirlar],
                "statement": certificate_statement(row, gun),
            }
        )
    return {
        **_antet(config),
        "document_title": BELGE_BASLIGI,
        "issued_on": f"{gun:%d.%m.%Y}",
        "position_note": KONUM_KALIBI,
        "certificates": belgeler,
    }


def certificate_pdf(rows: Sequence[ilisik.ClearanceRow], *, on: date | None = None) -> bytes:
    return html_to_pdf(render_to_string(BELGE_SABLONU, certificate_context(rows, on=on)))


# ---------------------------------------------------------------------------
# E5 — İlişik listesi (toplu; dipnotlu; kaynak adı YOK)
# ---------------------------------------------------------------------------
def scope_text(filtre: ilisik.ClearanceFilter) -> str:
    """'Bütün kişiler' · 'Son sınıflar' · 'Okuldan ayrılanlar' · '12/A şubesi' …"""
    parcalar: list[str] = []
    if filtre.group == ilisik.GROUP_GRADUATING:
        parcalar.append("Son sınıflar")
    elif filtre.group == ilisik.GROUP_LEAVING:
        parcalar.append("Okuldan ayrılanlar ve ayrılış kararı bekleyenler")
    elif filtre.group == ilisik.GROUP_PRIORITY:
        parcalar.append("Son sınıflar ve okuldan ayrılanlar")
    elif filtre.group == ilisik.GROUP_OTHER:
        parcalar.append("Son sınıf olmayan ve ayrılmayan kişiler")
    sube = filtre.sube
    if filtre.class_level is not None:
        parcalar.append(
            f"{filtre.class_level}/{sube} şubesi" if sube else f"{filtre.class_level}. sınıflar"
        )
    elif sube:
        parcalar.append(f"{sube} şubeleri")
    return " · ".join(parcalar) if parcalar else "Bütün kişiler"


def scope_slug(filtre: ilisik.ClearanceFilter) -> tuple[str, ...]:
    """Dosya adının kapsam parçası ('Son-Sınıflar', '12-A' …)."""
    parca: list[str] = []
    if filtre.group == ilisik.GROUP_GRADUATING:
        parca.append("Son-Sınıflar")
    elif filtre.group == ilisik.GROUP_LEAVING:
        parca.append("Ayrılanlar")
    elif filtre.group == ilisik.GROUP_PRIORITY:
        parca.append("Son-Sınıflar-ve-Ayrılanlar")
    parca.extend(
        e4.scope_slug(filtre.class_level, filtre.sube)
        if (filtre.class_level is not None or filtre.sube)
        else ()
    )
    return tuple(parca)


def _barkod(copy: Any) -> str:
    return barcode_module.format_barcode(copy.barcode)


def obligations_text(row: ilisik.ClearanceRow, gun: date) -> str:
    """Açık işlerin kısa dökümü — barkod ve tarih; KAYNAK ADI YOK (veri en aza indirme)."""
    parcalar: list[str] = []
    if row.loans:
        oduncler = ", ".join(
            f"{_barkod(lo.copy)} (iade {lo.due_date:%d.%m.%Y}"
            + (f", {lo.overdue_days(gun)} gün gecikti" if lo.due_date < gun else "")
            + ")"
            for lo in row.loans
        )
        parcalar.append(f"Ödünç: {oduncler}")
    if row.deliveries:
        belgeler: dict[str, int] = {}
        for d in row.deliveries:
            belgeler[d.document_no] = belgeler.get(d.document_no, 0) + 1
        teslim = ", ".join(f"belge no {no} ({sayi} kitap)" for no, sayi in belgeler.items())
        parcalar.append(f"Teslim: {teslim}")
    if row.cases:
        dosya = ", ".join(
            f"{_barkod(c.copy)} ({c.get_case_type_display()}, {c.get_resolution_display()})"
            for c in row.cases
        )
        parcalar.append(f"Kayıp/hasar dosyası: {dosya}")
    return " · ".join(parcalar)


def clearance_list_context(
    rows: Sequence[ilisik.ClearanceRow],
    sections: Sequence[ilisik.SectionDeliveryRow],
    *,
    filtre: ilisik.ClearanceFilter,
    on: date | None = None,
) -> dict[str, Any]:
    gun = _gun(on)
    config = SchoolConfig.load()
    satirlar = [
        {
            "no": sira,
            "name": row.full_name,
            "label": row.person_label,
            "status": row.status_text,
            "loans": len(row.loans),
            "deliveries": len(row.deliveries),
            "cases": len(row.cases),
            "items": obligations_text(row, gun),
        }
        for sira, row in enumerate(rows, start=1)
    ]
    subeler = [
        {
            "label": s.label,
            "year": s.school_year_name,
            "status": "Son sınıf"
            if s.is_graduating
            else ("" if s.is_active_year else "Önceki yıl"),
            "count": len(s.deliveries),
            "documents": ", ".join(s.document_numbers),
            "cases": len(s.cases),
        }
        for s in sections
    ]
    return {
        **_antet(config),
        "document_title": LISTE_BASLIGI,
        "issued_on": f"{gun:%d.%m.%Y}",
        "scope": scope_text(filtre),
        "rows": satirlar,
        "person_count": len(satirlar),
        "sections": subeler,
        "section_delivery_count": sum(s["count"] for s in subeler),
        "footnote": LISTE_DIPNOTU,
    }


def clearance_list_pdf(
    rows: Sequence[ilisik.ClearanceRow],
    sections: Sequence[ilisik.SectionDeliveryRow],
    *,
    filtre: ilisik.ClearanceFilter,
    on: date | None = None,
) -> bytes:
    baglam = clearance_list_context(rows, sections, filtre=filtre, on=on)
    return html_to_pdf(render_to_string(LISTE_SABLONU, baglam))


# ---------------------------------------------------------------------------
# Yıl sonu iade hatırlatma pusulası (E4 geometrisi; kişinin BÜTÜN açık ödünçleri)
# ---------------------------------------------------------------------------
YIL_SONU_ITEMS_TITLE: Final = "İADE EDİLECEK KAYNAKLAR"
YIL_SONU_KALAN: Final = (
    "Kaynak elinizde değilse ya da iade ettiğinizi düşünüyorsanız kütüphane yöneticisiyle görüşün."
)


def year_end_paragraphs(return_by: date | None) -> tuple[str, ...]:
    """Pusulanın iç metni. Tarih verilirse "en geç … tarihine kadar" yazılır (saklanmaz)."""
    ne_zaman = (
        f"en geç {return_by:%d.%m.%Y} tarihine kadar"
        if return_by is not None
        else "ders yılı bitmeden"
    )
    return (
        "Ders yılı sona eriyor. Kütüphaneden ödünç aldığınız, sağda yazılı kaynakları "
        f"{ne_zaman} kütüphaneye getirin.",
        YIL_SONU_KALAN,
    )


@dataclass(frozen=True)
class CollectionGroup:
    """Pusulası basılacak kişi: ilişik satırı ve açık ödünçleri."""

    row: ilisik.ClearanceRow

    @property
    def full_name(self) -> str:
        return self.row.full_name

    @property
    def label(self) -> str:
        return self.row.person_label

    @property
    def is_student(self) -> bool:
        return self.row.is_student


def collection_groups(rows: Sequence[ilisik.ClearanceRow]) -> list[CollectionGroup]:
    """Açık ödüncü olan kişiler (sıra korunur: son sınıflar ve ayrılanlar önce)."""
    return [CollectionGroup(row=r) for r in rows if r.loans]


def _year_end_slip_boxes(
    group: CollectionGroup, *, gun: date, okul: str, return_by: date | None
) -> tuple[list[dict[str, str]], bool]:
    """Tek pusulanın kutuları — E4 düzeni (`dolasim_belgeleri._slip_boxes`) yıl sonu metniyle."""
    ust, alt = e4.SLIP_PAD_Y, e4.SLIP_HEIGHT - e4.SLIP_PAD_Y
    ad = group.full_name

    serit = e4._Panel(e4.SLIP_PAD_X, ust, e4.STRIP_WIDTH - 2 * e4.SLIP_PAD_X, alt)
    serit.satirlar(e4.SLIP_OUTSIDE_TITLE, (8.0, 7.5), bold=True, max_lines=1, sonra=2.0)
    serit.satirlar(ad, (10.0, 9.0, 8.0, 7.5, 7.0, 6.5), bold=True, max_lines=4, sonra=0.5)
    serit.satirlar(group.label, (9.0, 8.0), max_lines=1)
    serit.alttan(e4.SLIP_FOLD_HINT, (5.5, 5.0), max_lines=4)
    serit.alttan(
        e4.SLIP_DELIVERY_STUDENT if group.is_student else e4.SLIP_DELIVERY_STAFF,
        (6.5, 6.0),
        max_lines=4,
        bold=True,
    )

    ic = e4._Panel(
        e4.STRIP_WIDTH + e4.SLIP_PAD_X, ust, e4.FOLD_X - e4.STRIP_WIDTH - 2 * e4.SLIP_PAD_X, alt
    )
    ic.satirlar(e4.SLIP_TITLE, (10.0, 9.0), bold=True, max_lines=1)
    ic.satirlar(f"Tarih: {gun:%d.%m.%Y}", (7.5,), max_lines=1, sonra=2.0)
    ic.satirlar(f"Sayın {ad},", (8.5, 8.0), bold=True, max_lines=2, sonra=1.2)
    for paragraf in year_end_paragraphs(return_by):
        ic.satirlar(paragraf, (8.0, 7.5), max_lines=4, sonra=1.2)
    if okul:
        ic.alttan(f"{okul} Kütüphanesi", (7.0, 6.5), max_lines=2)

    sag = e4._Panel(
        e4.FOLD_X + e4.SLIP_PAD_X, ust, e4.SLIP_WIDTH - e4.FOLD_X - 2 * e4.SLIP_PAD_X, alt
    )
    sag.satirlar(YIL_SONU_ITEMS_TITLE, (8.5, 8.0), bold=True, max_lines=1, sonra=1.5)
    for loan in group.row.loans[: e4.MAX_SLIP_ITEMS]:
        sag.satirlar(loan.copy.work.title, (8.0, 7.5), bold=True, max_lines=2)
        sag.satirlar(f"Barkod: {_barkod(loan.copy)}", (7.0,), max_lines=1)
        gecikme = f" · {loan.overdue_days(gun)} gün gecikti" if loan.due_date < gun else ""
        sag.satirlar(
            f"İade tarihi: {loan.due_date:%d.%m.%Y}{gecikme}", (7.0, 6.5), max_lines=1, sonra=1.5
        )
    kalan = len(group.row.loans) - e4.MAX_SLIP_ITEMS
    if kalan > 0:
        sag.satirlar(f"ve {kalan} kaynak daha — kütüphane yöneticisine sorun.", (7.0,), max_lines=2)

    tasti = serit.tasti or ic.tasti or sag.tasti
    return [*serit.kutular, *ic.kutular, *sag.kutular], tasti


def year_end_slip_context(
    groups: Sequence[CollectionGroup],
    *,
    on: date | None = None,
    return_by: date | None = None,
    school_name: str | None = None,
) -> dict[str, Any]:
    """Yıl sonu pusulalarının bağlamı — E4 şablonunun biçimiyle (sayfa başına üç pusula)."""
    if not groups:
        raise ValidationError(NO_COLLECTION_MESSAGE)
    gun = _gun(on)
    okul = school_name if school_name is not None else _okul_adi(SchoolConfig.load())
    sayfalar: list[dict[str, Any]] = []
    tasan = 0
    for sira, grup in enumerate(groups):
        if sira % e4.SLIPS_PER_PAGE == 0:
            sayfalar.append({"slips": []})
        kutular, tasti = _year_end_slip_boxes(grup, gun=gun, okul=okul, return_by=return_by)
        tasan += int(tasti)
        sayfalar[-1]["slips"].append(
            {"top": mm_text((sira % e4.SLIPS_PER_PAGE) * e4.SLIP_HEIGHT), "texts": kutular}
        )
    return {
        "document_title": e4.PUSULA_ADI,
        "pages": sayfalar,
        "slip_height": mm_text(e4.SLIP_HEIGHT),
        "strip_width": mm_text(e4.STRIP_WIDTH),
        "fold_x": mm_text(e4.FOLD_X),
        "overflow_count": tasan,
    }


def year_end_slips_pdf(
    groups: Sequence[CollectionGroup], *, on: date | None = None, return_by: date | None = None
) -> bytes:
    baglam = year_end_slip_context(groups, on=on, return_by=return_by)
    return html_to_pdf(render_to_string(e4.PUSULA_SABLONU, baglam))
