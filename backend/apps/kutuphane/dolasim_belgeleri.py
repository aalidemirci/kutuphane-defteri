"""Dolaşım ve üyelik belgeleri: E4, E13, E19 (tasarım §3 KVKK, §9-13, §10).

- **İade hatırlatma pusulası** (E4, §9-13): TEK KİŞİLİKTİR. A4'te üç pusula,
  aralarında kesme çizgisi. Her pusula bir kişiye aittir ve katlanınca içerik
  görünmez: soldaki dar **ad bölümü** (kime verileceği) açık kalır, sağdaki
  bölüm katlama çizgisinden sola, yazılı yüz içe gelecek biçimde katlanınca
  hatırlatma metnini ve gecikmiş kaynakları örter. Tek yüze basılan kâğıtta
  içeriği gizlemenin yolu budur. Pusulayı kütüphane yöneticisi ya da sınıf
  rehber öğretmeni dağıtır; sınıfta okunmaz, öğrenci görevliye dağıttırılmaz
  (kılavuz). Uzatma, ceza ve harç YOKTUR; kaydırılmış iade tarihi "Md. 18
  gereği" diye sunulmaz (§9-5). Md. 18'e yalnız süre cümlesinde atıf vardır.
- **Gecikmiş ödünç listesi** (E4): toplu liste, YALNIZ yönetici kipinde açılır
  (uç görevli izin listesinde değildir). Her sayfanın dibinde "Kişisel veri
  içerir — asılmaz, çoğaltılmaz." dipnotu (KM-10, sözlük §5). Veri en aza
  indirme: okul no basılmaz (ad + sınıf yeter).
- **Kütüphane aydınlatma metni** (E13, KVKK md. 10/1 + Aydınlatma Tebliği md. 4
  ve 5): veri sorumlusu, amaçlar, hukuki sebep ve yöntem, kimlerin gördüğü
  (masadaki öğrenci görevliler DAHİL), aktarım, saklama (bugünkü gerçek — teknik
  borç TB16: saklama taraması F11'de gelir), md. 11 hakları ve md. 13 başvuru
  yolu. Okul alanları `SchoolConfig`'ten (Okul Bilgileri ekranında düzenlenir);
  başvuru adresi ve e-posta basım isteğiyle gelir, saklanmaz. Kanun
  alıntıları `docs/mevzuat/6698-kvkk.md` metniyle BİREBİRDİR (test).
- **Masa kartı** (E19, KVKK md. 12/1): görevli öğrenci için tek sayfa kullanım ve
  gizlilik uyarısı. Kişisel veri taşımaz.

PDF'ler yalnız `shared.pdf.html_to_pdf` kapısından üretilir. Bu modül
veritabanına YAZMAZ. Metinlere ve günlüğe kişi adı yalnız belgenin kendisinde
girer; hata iletilerinde ad yoktur.

**Profil yasağı** (§3, CLAUDE.md §2-5): belgeler üye bazında konu, sınıflama ya
da bölüm dağılımı ÜRETMEZ; pusula ve liste yalnız gecikmiş ödünç satırlarını
(kaynak adı, barkod, iade tarihi, gecikme) taşır.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_dolasim
from apps.kutuphane.labels.card import line_height, member_type_text, wrap_text
from apps.kutuphane.labels.geometry import mm_text
from apps.kutuphane.labels.layout import FIT_SAFETY_MM
from apps.kutuphane.labels.metrics import clean_text
from apps.kutuphane.models import Loan, Membership
from apps.okul import normalize
from apps.okul.models import SchoolConfig
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

PUSULA_SABLONU: Final = "documents/iade_pusulasi.html"
LISTE_SABLONU: Final = "documents/gecikmis_odunc_listesi.html"
AYDINLATMA_SABLONU: Final = "documents/aydinlatma_metni.html"
MASA_KARTI_SABLONU: Final = "documents/masa_karti.html"

#: Belge adları (sözlük §2: E4, E13, E19) — başlıklar ve indirme adları buradan.
PUSULA_ADI: Final = "İade Hatırlatma Pusulası"
LISTE_ADI: Final = "Gecikmiş Ödünç Listesi"
AYDINLATMA_ADI: Final = "Kütüphane Aydınlatma Metni"
MASA_KARTI_ADI: Final = "Masa Kartı"

#: Toplu gecikme listesinin dipnotu (§9-13, sözlük §5) — her sayfada.
LISTE_DIPNOTU: Final = "Kişisel veri içerir — asılmaz, çoğaltılmaz."
#: Silinmiş kişi kaydının adı yerine basılan metin (CLAUDE.md §3: evraka ad basan
#: her yol `deleted_at`'i elle denetler).
SILINMIS_KISI: Final = "Kaydı silinmiş kişi"
#: Tek belgede en çok pusula (50 sayfa). Daha büyük iş şube şube basılır.
MAX_SLIPS_PER_DOCUMENT: Final = 150


def _gun(on: date | None = None) -> date:
    return on or timezone.localdate()


def tarih(gun: date) -> str:
    return f"{gun:%d.%m.%Y}"


def belge_dosya_adi(ad: str, gun: date | None = None, *, kapsam: Sequence[str] = ()) -> str:
    """'Gecikmiş-Ödünç-Listesi_9-A_24.09.2026.pdf' — belge adı + kapsam + yerel tarih (sözlük §3)."""
    parcalar = [ad.replace(" ", "-")]
    parcalar += [p.replace("/", "-").replace(" ", "-") for p in kapsam if p]
    parcalar.append(tarih(_gun(gun)))
    return "_".join(parcalar) + ".pdf"


def _okul_adi(config: SchoolConfig) -> str:
    return " ".join((config.school_name or config.kisa_ad or "").split())


# ---------------------------------------------------------------------------
# Gecikmiş ödünçler: kişi bazında gruplar (pusula ve liste ortak)
# ---------------------------------------------------------------------------
def person_name(membership: Membership) -> str:
    """Belgeye basılacak ad; kişi kaydı silinmişse ad BASILMAZ."""
    kisi = membership.person
    if kisi.deleted_at is not None:
        return SILINMIS_KISI
    return clean_text(kisi.full_name)


def person_label(membership: Membership) -> str:
    """Öğrencide sınıf/şube ('9/A'), personelde üye türü ('Öğretmen')."""
    if membership.student is not None:
        return membership.student.class_label
    return member_type_text(membership.get_member_type_display())


@dataclass(frozen=True)
class OverdueGroup:
    """Bir kişinin gecikmiş açık ödünçleri (kişinin BÜTÜN üyelikleri — sayılar kişi bazında)."""

    membership: Membership
    loans: tuple[Loan, ...]

    @property
    def full_name(self) -> str:
        return person_name(self.membership)

    @property
    def label(self) -> str:
        return person_label(self.membership)

    @property
    def is_student(self) -> bool:
        return self.membership.student_id is not None


def _sinif_uyar(membership: Membership, class_level: int | None, class_section: str) -> bool:
    if class_level is None and not class_section.strip():
        return True
    ogrenci = membership.student
    if ogrenci is None:
        return False
    if class_level is not None and ogrenci.class_level != class_level:
        return False
    sube = normalize.tr_upper(class_section.strip())
    return not sube or ogrenci.class_section == sube


def overdue_rows(
    *,
    on: date | None = None,
    class_level: int | None = None,
    class_section: str = "",
    membership_ids: Iterable[int] | None = None,
) -> list[Loan]:
    """Gecikmiş açık ödünçler: kişi sırası (sınıf → şube → okul no → ad; sonra personel), kişi
    içinde iade tarihi sırası. Kişiye bağı kopmuş (anonimleştirilmiş) ödünç listeye girmez.

    `membership_ids`: yalnız bu üyeliklerin KİŞİLERİ (kişinin öbür üyeliklerindeki
    gecikmiş ödünç de gelir — sayılar kişi bazındadır).
    """
    satirlar = [
        lo
        for lo in selectors_dolasim.overdue_loans(on=on)
        if lo.membership is not None and _sinif_uyar(lo.membership, class_level, class_section)
    ]
    if membership_ids is not None:
        kimlikler = {int(i) for i in membership_ids}
        kisiler = {
            selectors_dolasim.person_key(m) for m in Membership.all_objects.filter(pk__in=kimlikler)
        }
        satirlar = [
            lo
            for lo in satirlar
            if lo.membership is not None and selectors_dolasim.person_key(lo.membership) in kisiler
        ]
    temsil: dict[selectors_dolasim.PersonKey, Membership] = {}
    for lo in satirlar:
        assert lo.membership is not None
        temsil.setdefault(selectors_dolasim.person_key(lo.membership), lo.membership)
    sira = {
        selectors_dolasim.person_key(m): no
        for no, m in enumerate(selectors_dolasim.memberships_sorted(temsil.values()))
    }

    def _anahtar(lo: Loan) -> tuple[int, date, int]:
        assert lo.membership is not None
        return (sira[selectors_dolasim.person_key(lo.membership)], lo.due_date, lo.pk)

    return sorted(satirlar, key=_anahtar)


def overdue_groups(
    *,
    on: date | None = None,
    class_level: int | None = None,
    class_section: str = "",
    membership_ids: Iterable[int] | None = None,
) -> list[OverdueGroup]:
    """`overdue_rows`'un kişi bazında grupları (sıra korunur)."""
    gruplar: dict[selectors_dolasim.PersonKey, list[Loan]] = {}
    temsil: dict[selectors_dolasim.PersonKey, Membership] = {}
    for lo in overdue_rows(
        on=on, class_level=class_level, class_section=class_section, membership_ids=membership_ids
    ):
        assert lo.membership is not None
        anahtar = selectors_dolasim.person_key(lo.membership)
        gruplar.setdefault(anahtar, []).append(lo)
        temsil.setdefault(anahtar, lo.membership)
    return [OverdueGroup(membership=temsil[a], loans=tuple(lo)) for a, lo in gruplar.items()]


def scope_text(class_level: int | None, class_section: str) -> str:
    """Belgenin kapsamı: 'Bütün okul', '9. sınıflar', '9/A şubesi'."""
    sube = normalize.tr_upper(class_section.strip())
    if class_level is None:
        return f"{sube} şubeleri" if sube else "Bütün okul"
    if sube:
        return f"{class_level}/{sube} şubesi"
    return f"{class_level}. sınıflar"


def scope_slug(class_level: int | None, class_section: str) -> tuple[str, ...]:
    """Dosya adının kapsam parçası: () · ('9-A',) · ('9-sınıflar',) · ('A-şubeleri',)."""
    sube = normalize.tr_upper(class_section.strip())
    if class_level is None:
        return (f"{sube}-şubeleri",) if sube else ()
    return (f"{class_level}-{sube}",) if sube else (f"{class_level}-sınıflar",)


def _gecikme(loan: Loan, gun: date) -> int:
    return loan.overdue_days(gun)


# ---------------------------------------------------------------------------
# E4 — İade hatırlatma pusulası (tek kişilik, kesme çizgili, katlanınca gizli)
# ---------------------------------------------------------------------------
#: Pusula ölçüleri (mm): A4'te üç pusula; soldaki ad bölümü katlanınca açık kalır.
SLIP_WIDTH: Final = 210.0
SLIP_HEIGHT: Final = 99.0
SLIPS_PER_PAGE: Final = 3
STRIP_WIDTH: Final = 45.0
#: Katlama çizgisi: sağ bölüm (82,5 mm) sola katlanınca tam olarak ad bölümünün
#: sağındaki alanı örter (45 + 82,5 = 127,5).
FOLD_X: Final = STRIP_WIDTH + (SLIP_WIDTH - STRIP_WIDTH) / 2
SLIP_PAD_X: Final = 5.5
SLIP_PAD_Y: Final = 6.0
#: Sağ bölümde listelenen en çok kaynak; fazlası "ve N kaynak daha" satırıdır.
MAX_SLIP_ITEMS: Final = 5

SLIP_OUTSIDE_TITLE: Final = "KİŞİYE ÖZELDİR"
SLIP_TITLE: Final = "İADE HATIRLATMASI"
SLIP_ITEMS_TITLE: Final = "GECİKMİŞ KAYNAKLAR"
#: Katlanınca DIŞTA kalan teslim notu. Kaynağı (kütüphaneyi) söylemez: sınıfta elden
#: ele geçen kâğıdın kütüphaneden geldiği, yani öğrencinin iade etmediği bir kitap
#: olduğu dıştan anlaşılmamalıdır (§9-13). Kimin dağıttığı kılavuzdadır.
SLIP_DELIVERY_STUDENT: Final = "Kişinin kendisine elden verilir; sınıfta okunmaz."
SLIP_DELIVERY_STAFF: Final = "Kişinin kendisine elden verilir."
SLIP_FOLD_HINT: Final = (
    "Sağ bölümü katlama çizgisinden sola, yazılı yüz içe gelecek biçimde katlayın."
)
SLIP_PARAGRAPHS: Final = (
    "Kütüphaneden ödünç aldığınız, sağda yazılı kaynakların iade tarihi geçti. Lütfen bu "
    "kaynakları ilk fırsatta kütüphaneye getirin.",
    "Kaynak elinizde değilse ya da iade ettiğinizi düşünüyorsanız kütüphane yöneticisiyle "
    "görüşün.",
    "Bir kitabı ödünç alma süresi on beş gündür (Okul Kütüphaneleri Yönetmeliği Md. 18).",
)


@dataclass
class _Panel:
    """Pusulanın bir bölümü: tek satırlık metin kutuları yukarıdan aşağı dizilir."""

    left: float
    top: float
    width: float
    bottom: float
    y: float = 0.0
    kutular: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.y = self.top

    def satirlar(
        self,
        metin: str,
        boylar: tuple[float, ...],
        *,
        bold: bool = False,
        max_lines: int = 2,
        align: str = "l",
        sonra: float = 0.0,
    ) -> None:
        satirlar, boy = wrap_text(
            metin, self.width - FIT_SAFETY_MM, boylar, bold=bold, max_lines=max_lines
        )
        yuk = line_height(boy)
        for satir in satirlar:
            self._kutu(satir, self.y, yuk, boy, bold=bold, align=align)
            self.y += yuk
        self.y += sonra

    def alttan(
        self, metin: str, boylar: tuple[float, ...], *, max_lines: int, bold: bool = False
    ) -> None:
        """Metni bölümün DİBİNE yaslar; alt sınır yukarı çekilir."""
        satirlar, boy = wrap_text(
            metin, self.width - FIT_SAFETY_MM, boylar, bold=bold, max_lines=max_lines
        )
        yuk = line_height(boy)
        ust = self.bottom - yuk * len(satirlar)
        for sira, satir in enumerate(satirlar):
            self._kutu(satir, ust + sira * yuk, yuk, boy, bold=bold, align="l")
        self.bottom = ust - 1.0

    def _kutu(
        self, metin: str, top: float, yuk: float, boy: float, *, bold: bool, align: str
    ) -> None:
        css = f"{align} b" if bold else align
        self.kutular.append(
            {
                "css": css,
                "text": metin,
                "left": mm_text(self.left),
                "top": mm_text(top),
                "width": mm_text(self.width),
                "height": mm_text(yuk),
                "size": f"{boy:.2f}",
            }
        )

    @property
    def tasti(self) -> bool:
        """Yukarıdan dizilen metin alttan yaslanan metne ya da alt sınıra çarptı mı?"""
        return self.y > self.bottom + 0.01


def _slip_boxes(group: OverdueGroup, *, gun: date, okul: str) -> tuple[list[dict[str, str]], bool]:
    """Tek pusulanın metin kutuları (pusulaya göre mm) + taşma işareti (test içindir)."""
    ust, alt = SLIP_PAD_Y, SLIP_HEIGHT - SLIP_PAD_Y
    ad = group.full_name

    serit = _Panel(SLIP_PAD_X, ust, STRIP_WIDTH - 2 * SLIP_PAD_X, alt)
    serit.satirlar(SLIP_OUTSIDE_TITLE, (8.0, 7.5), bold=True, max_lines=1, sonra=2.0)
    # Ad pusulayı dağıtanın tek dayanağıdır: kısalmasın diye boy 6,5 pt'ye dek iner.
    serit.satirlar(ad, (10.0, 9.0, 8.0, 7.5, 7.0, 6.5), bold=True, max_lines=4, sonra=0.5)
    serit.satirlar(group.label, (9.0, 8.0), max_lines=1)
    serit.alttan(SLIP_FOLD_HINT, (5.5, 5.0), max_lines=4)
    serit.alttan(
        SLIP_DELIVERY_STUDENT if group.is_student else SLIP_DELIVERY_STAFF,
        (6.5, 6.0),
        max_lines=4,
        bold=True,
    )

    ic = _Panel(STRIP_WIDTH + SLIP_PAD_X, ust, FOLD_X - STRIP_WIDTH - 2 * SLIP_PAD_X, alt)
    ic.satirlar(SLIP_TITLE, (10.0, 9.0), bold=True, max_lines=1)
    ic.satirlar(f"Tarih: {tarih(gun)}", (7.5,), max_lines=1, sonra=2.0)
    ic.satirlar(f"Sayın {ad},", (8.5, 8.0), bold=True, max_lines=2, sonra=1.2)
    for paragraf in SLIP_PARAGRAPHS:
        ic.satirlar(paragraf, (8.0, 7.5), max_lines=4, sonra=1.2)
    if okul:
        ic.alttan(f"{okul} Kütüphanesi", (7.0, 6.5), max_lines=2)

    sag = _Panel(FOLD_X + SLIP_PAD_X, ust, SLIP_WIDTH - FOLD_X - 2 * SLIP_PAD_X, alt)
    sag.satirlar(SLIP_ITEMS_TITLE, (8.5, 8.0), bold=True, max_lines=1, sonra=1.5)
    for loan in group.loans[:MAX_SLIP_ITEMS]:
        sag.satirlar(loan.copy.work.title, (8.0, 7.5), bold=True, max_lines=2)
        sag.satirlar(
            f"Barkod: {barcode_module.format_barcode(loan.copy.barcode)}", (7.0,), max_lines=1
        )
        sag.satirlar(
            f"İade tarihi: {tarih(loan.due_date)} · {_gecikme(loan, gun)} gün gecikti",
            (7.0, 6.5),
            max_lines=1,
            sonra=1.5,
        )
    kalan = len(group.loans) - MAX_SLIP_ITEMS
    if kalan > 0:
        sag.satirlar(f"ve {kalan} kaynak daha — kütüphane yöneticisine sorun.", (7.0,), max_lines=2)

    tasti = serit.tasti or ic.tasti or sag.tasti
    return [*serit.kutular, *ic.kutular, *sag.kutular], tasti


def slip_context(
    groups: Sequence[OverdueGroup], *, on: date | None = None, school_name: str | None = None
) -> dict[str, Any]:
    """Pusula belgesinin bağlamı: sayfalar × (en çok üç) pusula. PDF'siz; test edilebilir."""
    if not groups:
        raise ValueError("Pusula basılacak gecikmiş ödünç yok.")
    gun = _gun(on)
    okul = school_name if school_name is not None else _okul_adi(SchoolConfig.load())
    sayfalar: list[dict[str, Any]] = []
    tasan = 0
    for sira, grup in enumerate(groups):
        if sira % SLIPS_PER_PAGE == 0:
            sayfalar.append({"slips": []})
        kutular, tasti = _slip_boxes(grup, gun=gun, okul=okul)
        tasan += int(tasti)
        sayfalar[-1]["slips"].append(
            {"top": mm_text((sira % SLIPS_PER_PAGE) * SLIP_HEIGHT), "texts": kutular}
        )
    return {
        "document_title": PUSULA_ADI,
        "pages": sayfalar,
        "slip_height": mm_text(SLIP_HEIGHT),
        "strip_width": mm_text(STRIP_WIDTH),
        "fold_x": mm_text(FOLD_X),
        "overflow_count": tasan,
    }


def slips_pdf(groups: Sequence[OverdueGroup], *, on: date | None = None) -> bytes:
    return html_to_pdf(render_to_string(PUSULA_SABLONU, slip_context(groups, on=on)))


# ---------------------------------------------------------------------------
# E4 — Gecikmiş ödünç listesi (toplu, yalnız yönetici, dipnotlu)
# ---------------------------------------------------------------------------
def overdue_list_context(
    rows: Sequence[Loan],
    *,
    on: date | None = None,
    class_level: int | None = None,
    class_section: str = "",
) -> dict[str, Any]:
    gun = _gun(on)
    config = SchoolConfig.load()
    satirlar: list[dict[str, Any]] = []
    kisiler: set[selectors_dolasim.PersonKey] = set()
    for sira, lo in enumerate(rows, start=1):
        assert lo.membership is not None
        kisiler.add(selectors_dolasim.person_key(lo.membership))
        satirlar.append(
            {
                "no": sira,
                "name": person_name(lo.membership),
                "label": person_label(lo.membership),
                "title": clean_text(lo.copy.work.title),
                "barcode": barcode_module.format_barcode(lo.copy.barcode),
                "due": tarih(lo.due_date),
                "days": _gecikme(lo, gun),
            }
        )
    return {
        **letterhead_context(
            school_name=_okul_adi(config),
            district=config.district,
            principal_name=config.principal_name,
        ),
        "document_title": "GECİKMİŞ ÖDÜNÇ LİSTESİ",
        "issued_on": tarih(gun),
        "scope": scope_text(class_level, class_section),
        "rows": satirlar,
        "loan_count": len(satirlar),
        "person_count": len(kisiler),
        "footnote": LISTE_DIPNOTU,
    }


def overdue_list_pdf(
    rows: Sequence[Loan],
    *,
    on: date | None = None,
    class_level: int | None = None,
    class_section: str = "",
) -> bytes:
    baglam = overdue_list_context(rows, on=on, class_level=class_level, class_section=class_section)
    return html_to_pdf(render_to_string(LISTE_SABLONU, baglam))


# ---------------------------------------------------------------------------
# E13 — Kütüphane aydınlatma metni (KVKK md. 10/1)
# ---------------------------------------------------------------------------
#: KVKK md. 11/1'in bentleri — docs/mevzuat/6698-kvkk.md ile BİREBİR (test sınar).
KVKK_11_HAKLAR: Final = (
    ("a", "Kişisel veri işlenip işlenmediğini öğrenme,"),
    ("b", "Kişisel verileri işlenmişse buna ilişkin bilgi talep etme,"),
    (
        "c",
        "Kişisel verilerin işlenme amacını ve bunların amacına uygun kullanılıp "
        "kullanılmadığını öğrenme,",
    ),
    ("ç", "Yurt içinde veya yurt dışında kişisel verilerin aktarıldığı üçüncü kişileri bilme,"),
    (
        "d",
        "Kişisel verilerin eksik veya yanlış işlenmiş olması hâlinde bunların düzeltilmesini "
        "isteme,",
    ),
    (
        "e",
        "7 nci maddede öngörülen şartlar çerçevesinde kişisel verilerin silinmesini veya yok "
        "edilmesini isteme,",
    ),
    (
        "f",
        "(d) ve (e) bentleri uyarınca yapılan işlemlerin, kişisel verilerin aktarıldığı üçüncü "
        "kişilere bildirilmesini isteme,",
    ),
    (
        "g",
        "İşlenen verilerin münhasıran otomatik sistemler vasıtasıyla analiz edilmesi suretiyle "
        "kişinin kendisi aleyhine bir sonucun ortaya çıkmasına itiraz etme,",
    ),
    (
        "ğ",
        "Kişisel verilerin kanuna aykırı olarak işlenmesi sebebiyle zarara uğraması hâlinde "
        "zararın giderilmesini talep etme,",
    ),
)
#: KVKK md. 5/2-ç ve md. 13/1-2 alıntıları — depodaki metinle BİREBİR (test sınar).
KVKK_5_2_C: Final = (
    "Veri sorumlusunun hukuki yükümlülüğünü yerine getirebilmesi için zorunlu olması."
)
KVKK_13_1: Final = (
    "İlgili kişi, bu Kanunun uygulanmasıyla ilgili taleplerini yazılı olarak veya Kurulun "
    "belirleyeceği diğer yöntemlerle veri sorumlusuna iletir."
)
KVKK_13_2: Final = (
    "Veri sorumlusu başvuruda yer alan talepleri, talebin niteliğine göre en kısa sürede ve "
    "en geç otuz gün içinde ücretsiz olarak sonuçlandırır."
)
#: Otomatik yedeklerin saklanması (desktop/backup.py: DEFAULT_KEEP_DAYS,
#: DEFAULT_KEEP_PRE_MIGRATE) — metin bu değerlerle testte eşitlenir.
YEDEK_GUN: Final = 14
YEDEK_GUNCELLEME: Final = 5
#: Başvuru alanlarının üst sınırları (istek gövdesi; saklanmaz).
MAX_ADRES: Final = 300
MAX_ILETISIM: Final = 120


def privacy_notice_context(
    *, basvuru_adresi: str = "", iletisim: str = "", on: date | None = None
) -> dict[str, Any]:
    config = SchoolConfig.load()
    okul = _okul_adi(config)
    yer = " / ".join(p for p in (config.district.strip(), config.province.strip()) if p)
    return {
        **letterhead_context(
            school_name=okul, district=config.district, principal_name=config.principal_name
        ),
        "document_title": "KÜTÜPHANE AYDINLATMA METNİ",
        "okul": okul,
        "okul_yeri": yer,
        "issued_on": tarih(_gun(on)),
        "basvuru_adresi": " ".join(basvuru_adresi.split())[:MAX_ADRES],
        "iletisim": " ".join(iletisim.split())[:MAX_ILETISIM],
        "haklar": [{"bent": b, "metin": m} for b, m in KVKK_11_HAKLAR],
        "kvkk_5_2_c": KVKK_5_2_C,
        "kvkk_13_1": KVKK_13_1,
        "kvkk_13_2": KVKK_13_2,
        "yedek_gun": YEDEK_GUN,
        "yedek_guncelleme": YEDEK_GUNCELLEME,
    }


def privacy_notice_pdf(*, basvuru_adresi: str = "", iletisim: str = "") -> bytes:
    baglam = privacy_notice_context(basvuru_adresi=basvuru_adresi, iletisim=iletisim)
    return html_to_pdf(render_to_string(AYDINLATMA_SABLONU, baglam))


# ---------------------------------------------------------------------------
# E19 — Masa kartı (KVKK md. 12/1)
# ---------------------------------------------------------------------------
def desk_card_context() -> dict[str, Any]:
    config = SchoolConfig.load()
    return {
        "document_title": "MASA KARTI",
        "okul": _okul_adi(config),
    }


def desk_card_pdf() -> bytes:
    return html_to_pdf(render_to_string(MASA_KARTI_SABLONU, desk_card_context()))
