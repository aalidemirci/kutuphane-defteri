"""Kişi dökümü (KVKK md. 11) — PDF; tasarım §8.4 ("okul no ile üyelik, ödünç, dosya ve teslim
kayıtları; yalnız yönetici kipinde çalışır").

6698 sayılı Kanun md. 11: herkes veri sorumlusuna başvurarak kendisiyle ilgili kişisel veri
işlenip işlenmediğini öğrenme ve işlenmişse buna ilişkin bilgi talep etme hakkına sahiptir;
md. 13/2: başvuru en geç otuz gün içinde ücretsiz sonuçlandırılır. Döküm bu cevabın
HAZIRLIĞIDIR: bir kişinin programdaki üyelik, ödünç, kayıp/hasar dosyası ve (personelde)
teslim kayıtlarını tek belgede toplar. Cevabı okul müdürlüğü verir.

**Kişi nasıl bulunur** (`person_candidates`): öğrencide okul no ile — kör indeksle TAM
eşleşme (T14; okul no şifrelidir, düz alanla sorgu yazılmaz). Okul no ayrılan öğrenciden
sonra başka öğrenciye verilebildiği için aynı indekste birden çok kayıt çıkabilir: aday
listesi döner, döküm SEÇİLEN kişinin kaydıyla basılır — başka bir kişinin kaydı asla aynı
belgeye girmez. Personel (okul no'su yoktur) ve adla arama: ad Python'da TR katlamalı.
Okul no aramada sorgu dizesine değil İSTEK GÖVDESİNE yazılır (uç POST'tur).

**Yalnız yönetici kipinde** (CLAUDE.md §2-4): uç görevli kipi izin listesinde DEĞİLDİR,
görünüm ve bu modülün kapısı (`require_admin_mode`) ayrıca keser. Kayıt YAZMAZ.

Saklama süresi dolup kişi bağı koparılmış kayıtlar (§6.4) kişiye bağlı değildir; dökümde
görünmez ve belge bunu söyler. "Ödünç kaydı" okuduğu kitapların listesi DEĞİLDİR (sözlük).
PDF `shared.pdf.html_to_pdf` kapısından üretilir; indirme adında kişi adı yoktur.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import dokum_ortak as ortak
from apps.kutuphane import selectors_teslim
from apps.kutuphane.models import (
    CardlessReason,
    CardRevocation,
    Delivery,
    Loan,
    LossDamageCase,
    Membership,
    OverrideReason,
)
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import selectors as okul_selectors
from apps.okul.excel_ogrenci import normalize_header
from apps.okul.models import Personnel, Student, StudentStatus
from shared.pdf import html_to_pdf

SABLON: Final = "documents/dokum.html"
BELGE_ADI: Final = "Kişi dökümü"
KIND_STUDENT: Final = "student"
KIND_PERSONNEL: Final = "personnel"
KINDS: Final[tuple[str, ...]] = (KIND_STUDENT, KIND_PERSONNEL)
#: Ad aramasında dönen en çok aday (ekran seçicisi).
MAX_CANDIDATES: Final = 20
MIN_NAME_LENGTH: Final = 2

SEARCH_REQUIRED_MESSAGE: Final = "Okul numarasını ya da adı yazın."
NAME_TOO_SHORT_MESSAGE: Final = "Ad araması en az iki harf ister."
UNKNOWN_KIND_MESSAGE: Final = "Böyle bir kişi türü yok."
NOT_FOUND_MESSAGE: Final = "Kişi bulunamadı."

#: KVKK md. 11 — docs/mevzuat/6698-kvkk.md ile BİREBİR (test sınar).
KVKK_11_A: Final = "Kişisel veri işlenip işlenmediğini öğrenme"
KVKK_11_B: Final = "Kişisel verileri işlenmişse buna ilişkin bilgi talep etme"
KVKK_13_2: Final = (
    "Veri sorumlusu başvuruda yer alan talepleri, talebin niteliğine göre en kısa sürede ve en "
    "geç otuz gün içinde ücretsiz olarak sonuçlandırır."
)
ACIKLAMA: Final = (
    "Bu döküm, 6698 sayılı Kişisel Verilerin Korunması Kanunu md. 11 uyarınca ilgili kişinin "
    f"başvurusuna (“{KVKK_11_A}”, “{KVKK_11_B}”) cevap hazırlamak için okulun kütüphane "
    "işlerini yürüttüğü yerel araçtaki kayıtlardan düzenlenmiştir. Cevabı okul müdürlüğü verir; "
    f"md. 13/2: “{KVKK_13_2}”"
)
DURUM_NOTU: Final = "Kişisel veri içerir. Yalnız başvuru sahibine verilir."
#: Dökümün kapsamı (F10 düzeltme turu): md. 11/a'yı alıntılayan belge neyi aramadığını da
#: söyler. Serbest metindeki adlar kişiye bağlı kayıt değildir; döküm onları aramaz.
KAPSAM_NOTU: Final = (
    "Bu döküm kişinin üyelik ve ödünç kayıtlarını, kişiye bağlı kayıp ve hasar dosyalarını "
    "(üyeliğiyle açılan; öğretmende üyeliksiz olup kendisine yapılan teslimden doğan) ve "
    "öğretmende teslim kayıtlarını kapsar. Serbest metinle yazılmış adlar — üyeliği olmayan "
    "dosyanın sorumlu notu, komisyon ve sayım kurulu üyeleri, onaylayan ve bağışçı adları — "
    "aranmaz; bu kayıtlar ilgili ekranlarda ayrıca denetlenmelidir."
)
SAKLAMA_NOTU: Final = (
    "Saklama süresi dolan kayıtların kişiyle bağı koparılır; o kayıtlar kişiye bağlı "
    "değildir ve bu dökümde görünmez."
)
ODUNC_NOTU: Final = (
    "Ödünç kaydı bir kitabın kimde olduğunu ve ne zaman döneceğini tutar; okunan kitapların "
    "listesi değildir."
)
DIPNOT: Final = (
    "Bu döküm okulun kütüphane işlerini yürüttüğü yerel araçtaki kayıtlardan hazırlanmıştır; "
    "Bakanlık otomasyon sistemindeki kaydın yerine geçmez."
)


# ---------------------------------------------------------------------------
# Kişi arama
# ---------------------------------------------------------------------------
def _durum(kisi: Student | Personnel) -> str:
    if isinstance(kisi, Student):
        if kisi.status == StudentStatus.LEFT:
            return f"Ayrıldı · {ortak.tarih(kisi.left_at)}" if kisi.left_at else "Ayrıldı"
        return "Aktif"
    if not kisi.is_active:
        return f"Ayrıldı · {ortak.tarih(kisi.left_at)}" if kisi.left_at else "Ayrıldı"
    return "Aktif"


def _aday(kisi: Student | Personnel) -> dict[str, Any]:
    if isinstance(kisi, Student):
        return {
            "kind": KIND_STUDENT,
            "id": kisi.pk,
            "full_name": kisi.full_name,
            "detail": kisi.class_label or "Sınıfı yazılı değil",
            "status_display": _durum(kisi),
        }
    return {
        "kind": KIND_PERSONNEL,
        "id": kisi.pk,
        "full_name": kisi.full_name,
        "detail": str(kisi.get_member_kind_display()),
        "status_display": _durum(kisi),
    }


def person_candidates(*, school_no: str = "", name: str = "") -> list[dict[str, Any]]:
    """Döküm için aday kişiler (yalnız yönetici kipi). Okul no kör indeksle TAM eşleşir."""
    require_admin_mode()
    school_no, name = (school_no or "").strip(), (name or "").strip()
    if not school_no and not name:
        raise ValidationError({"search": SEARCH_REQUIRED_MESSAGE})
    adaylar: list[Student | Personnel] = []
    if school_no:
        indeks = okul_selectors.number_search_index(school_no)
        if indeks:
            adaylar.extend(
                okul_selectors.students_sorted(Student.objects.filter(student_number_index=indeks))
            )
    if name:
        if len(normalize_header(name)) < MIN_NAME_LENGTH:
            raise ValidationError({"name": NAME_TOO_SHORT_MESSAGE})
        igne = normalize_header(name)
        adaylar.extend(
            s for s in okul_selectors.students_sorted() if igne in normalize_header(s.full_name)
        )
        adaylar.extend(
            p for p in okul_selectors.personnel_sorted() if igne in normalize_header(p.full_name)
        )
    goruldu: set[tuple[str, int]] = set()
    sonuc: list[dict[str, Any]] = []
    for kisi in adaylar:
        aday = _aday(kisi)
        anahtar = (str(aday["kind"]), int(aday["id"]))
        if anahtar in goruldu:
            continue
        goruldu.add(anahtar)
        sonuc.append(aday)
        if len(sonuc) >= MAX_CANDIDATES:
            break
    return sonuc


def get_person(kind: str, pk: int) -> Student | Personnel:
    if kind not in KINDS:
        raise ValidationError({"kind": UNKNOWN_KIND_MESSAGE})
    kisi: Student | Personnel | None = (
        okul_selectors.get_student(pk) if kind == KIND_STUDENT else okul_selectors.get_personnel(pk)
    )
    if kisi is None:
        raise ValidationError({"person": NOT_FOUND_MESSAGE})
    return kisi


# ---------------------------------------------------------------------------
# Döküm
# ---------------------------------------------------------------------------
def _uyelikler(kisi: Student | Personnel) -> list[Membership]:
    alan = "student" if isinstance(kisi, Student) else "personnel"
    return list(Membership.objects.filter(**{alan: kisi}).order_by("started_at", "pk"))


def _eser(copy: Any) -> str:
    return f"{barcode_module.format_barcode(copy.barcode)} · {copy.work.title}"


def _secim_adi(secenekler: Any, kod: str) -> str:
    return str(dict(secenekler).get(kod, kod)) if kod else ""


def _kunye(kisi: Student | Personnel) -> list[dict[str, str]]:
    if isinstance(kisi, Student):
        return [
            {"label": "Ad soyad", "value": kisi.full_name},
            {"label": "Okul no", "value": kisi.student_number or ortak.BOS},
            {"label": "Sınıf / şube", "value": kisi.class_label or ortak.BOS},
            {"label": "Durum", "value": _durum(kisi)},
        ]
    return [
        {"label": "Ad soyad", "value": kisi.full_name},
        {"label": "Üye türü", "value": str(kisi.get_member_kind_display())},
        {"label": "Durum", "value": _durum(kisi)},
    ]


def _uyelik_tablosu(uyelikler: list[Membership]) -> dict[str, Any]:
    h = ortak.hucre
    satirlar = []
    for u in uyelikler:
        iptal = CardRevocation.objects.filter(membership=u).order_by("revoked_on")
        iptaller = "; ".join(
            f"{ortak.tarih(c.revoked_on)} ({c.get_reason_display()})" for c in iptal
        )
        satirlar.append(
            [
                h(ortak.tarih(u.requested_at)),
                h(ortak.tarih(u.started_at)),
                h(str(u.get_status_display())),
                h(ortak.tarih(u.terminated_at) if u.terminated_at else ""),
                h(str(u.get_termination_reason_display()) if u.termination_reason else ""),
                h(u.card_no, "tek"),
                h(ortak.zaman(u.card_printed_at) if u.card_printed_at else ""),
                h(iptaller),
            ]
        )
    return ortak.tablo(
        "ÜYELİK VE ÜYE KARTI",
        [
            ortak.sutun("İstek tarihi", 11),
            ortak.sutun("Başlangıç", 11),
            ortak.sutun("Durum", 9),
            ortak.sutun("Sonlandığı tarih", 11),
            ortak.sutun("Sonlanma nedeni", 14),
            ortak.sutun("Kart no", 10),
            ortak.sutun("Kart basımı", 14),
            ortak.sutun("İptal edilmiş kartlar", 20),
        ],
        satirlar,
        "Üyelik kaydı yok.",
    )


def _odunc_tablosu(uyelikler: list[Membership]) -> dict[str, Any]:
    h = ortak.hucre
    oduncler = (
        Loan.objects.filter(membership__in=uyelikler)
        .select_related("copy", "copy__work")
        .order_by("loaned_at", "pk")
    )
    satirlar = []
    for o in oduncler:
        notlar = []
        if o.cardless:
            notlar.append(f"Kartsız ödünç: {_secim_adi(CardlessReason.choices, o.cardless_reason)}")
        if o.override_reason:
            notlar.append(
                f"Gerekçeli istisna: {_secim_adi(OverrideReason.choices, o.override_reason)} — "
                f"{ortak.tek_satir(o.override_note)}"
            )
        kapanis = o.returned_at or o.lost_at
        satirlar.append(
            [
                h(ortak.zaman(o.loaned_at)),
                h(_eser(o.copy)),
                h(ortak.tarih(o.due_date)),
                h(str(o.get_status_display())),
                h(ortak.zaman(kapanis) if kapanis else ""),
                h(" · ".join(notlar)),
            ]
        )
    return ortak.tablo(
        "ÖDÜNÇ KAYDI",
        [
            # Sütunlar gerçek uzunlukta sınanır (F10 düzeltme turu): %10'luk "İade tarihi"
            # gg.aa.yyyy'yi son hanesinden bölüyordu ("12.10.202" / "6").
            ortak.sutun("Verilme", 13),
            ortak.sutun("Kitap (barkod · kaynak adı)", 30),
            ortak.sutun("İade tarihi", 12),
            ortak.sutun("Durum", 11),
            ortak.sutun("İade ya da kapanış", 13),
            ortak.sutun("Not", 21),
        ],
        satirlar,
        "Ödünç kaydı yok.",
        not_=ODUNC_NOTU,
    )


def _dosya_tablosu(kisi: Student | Personnel) -> dict[str, Any]:
    """Kişiye bağlı dosyalar — TEK kural (`selectors_teslim.person_case_q`): önce üyelik,
    üyelik yoksa teslim alan öğretmen.

    F10 düzeltme turu: teslimdeki kitabı öğrenci kaybedip dosya öğrencinin üyeliğiyle
    açılınca dosyada hem üyelik hem teslim durur; o dosya ÖĞRENCİNİNDİR. Öğretmenin
    dökümüne girseydi başka bir kişinin dosyası ve sorumlu notu üçüncü kişiye verilirdi.
    """
    h = ortak.hucre
    dosyalar = (
        LossDamageCase.objects.filter(selectors_teslim.person_case_q(kisi))
        .select_related("copy", "copy__work")
        .order_by("reported_on", "pk")
        .distinct()
    )
    satirlar = [
        [
            h(str(d.get_case_type_display())),
            h(ortak.tarih(d.reported_on)),
            h(_eser(d.copy)),
            h(str(d.get_resolution_display())),
            h(ortak.zaman(d.resolved_at) if d.resolved_at else ""),
            h(f"{ortak.para(d.market_price)} TL" if d.market_price is not None else ""),
            h(ortak.tek_satir(d.responsible_note)),
        ]
        for d in dosyalar
    ]
    return ortak.tablo(
        "KAYIP VE HASAR DOSYALARI",
        [
            ortak.sutun("Tür", 7),
            ortak.sutun("Tespit tarihi", 12),
            ortak.sutun("Kitap (barkod · kaynak adı)", 24),
            ortak.sutun("Çözüm", 16),
            ortak.sutun("Çözüm tarihi", 13),
            ortak.sutun("Bedel", 12, "sayi"),
            ortak.sutun("Sorumlu notu", 16),
        ],
        satirlar,
        "Kayıp ya da hasar dosyası yok.",
    )


def _teslim_tablosu(kisi: Personnel) -> dict[str, Any]:
    h = ortak.hucre
    teslimler = (
        Delivery.objects.filter(personnel=kisi)
        .select_related("copy", "copy__work")
        .order_by("delivered_on", "pk")
    )
    satirlar = [
        [
            h(t.document_no, "tek"),
            h(ortak.tarih(t.delivered_on)),
            h(_eser(t.copy)),
            h(ortak.tarih(t.expected_return) if t.expected_return else ""),
            h(str(t.get_status_display())),
            h(ortak.zaman(t.returned_at or t.lost_at) if (t.returned_at or t.lost_at) else ""),
        ]
        for t in teslimler
    ]
    return ortak.tablo(
        "ÖĞRETMENE TESLİM",
        [
            ortak.sutun("Belge no", 12),
            ortak.sutun("Teslim tarihi", 12),
            ortak.sutun("Kitap (barkod · kaynak adı)", 36),
            ortak.sutun("Beklenen dönüş", 12),
            ortak.sutun("Durum", 12),
            ortak.sutun("Geri alma", 16),
        ],
        satirlar,
        "Teslim kaydı yok.",
    )


def person_record_context(kind: str, pk: int, *, on: date | None = None) -> dict[str, Any]:
    """Dökümün bağlamı (yalnız yönetici kipi). Yalnız SEÇİLEN kişinin kayıtları."""
    require_admin_mode()
    kisi = get_person(kind, pk)
    uyelikler = _uyelikler(kisi)
    tablolar = [
        _uyelik_tablosu(uyelikler),
        _odunc_tablosu(uyelikler),
        _dosya_tablosu(kisi),
    ]
    if isinstance(kisi, Personnel):
        tablolar.append(_teslim_tablosu(kisi))
    return {
        **ortak.antet(),
        "document_title": "KİŞİ DÖKÜMÜ",
        "subtitle": "Kütüphane kayıtları — 6698 sayılı Kanun md. 11 başvurusuna cevap hazırlığı",
        "status_note": DURUM_NOTU,
        "issued_on": ortak.tarih(ortak.bugun(on)),
        "info": _kunye(kisi),
        "paragraphs": [ACIKLAMA],
        "tables": tablolar,
        "notes": [KAPSAM_NOTU, SAKLAMA_NOTU],
        "footnote": DIPNOT,
        "landscape": False,
    }


def person_record_pdf(kind: str, pk: int, *, on: date | None = None) -> bytes:
    return html_to_pdf(render_to_string(SABLON, person_record_context(kind, pk, on=on)))


def person_record_filename(gun: date | None = None) -> str:
    """İndirme adı: belge adı + tarih — kişi adı YOK."""
    return ortak.dosya_adi(BELGE_ADI, gun, bicim=ortak.PDF)
