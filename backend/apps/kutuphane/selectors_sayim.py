"""Sayım — salt okuma sorguları, kilit durumları ve TMY 34/1 büyüklükleri (F9; TMY 32, 34/1).

Bu modül YALNIZ modelleri import eder: TMY 32/3 kapısı (`services.tmy_kapisi`),
ödünç kapısı (`services.circulation`) ve katalog yazma yolları (`services.catalog`)
kilit durumunu buradan sorar; döngüsel import doğmaz.

**İki ayrı kilit** (tasarım §9-10; sözlük: "sayım kilidi" ve "dondurma" denmez):
`tmy_stop_active` (TMY 32/3 durdurması — edinim ve yeni nüsha, programa aktarım,
kayıttan düşme, devir, kayıp bildirimi, kayıp dosyası çözümü) ve `service_pause_active`
(sayım için hizmet arası — yeni ödünç ve yeni teslim). İkisi de sayım "Sürüyor" ya da
"Tamamlandı" iken sürer (D17). İade ve teslimden geri alma hiçbir durumda kilitlenmez;
burada onları soran bir işlev YOKTUR.

**Kişisel veri.** Sayım kalemi kişisizdir; bu modülün hiçbir sorgusu ödünç alanın,
teslim alan öğretmenin ya da dosya sorumlusunun kimliğini okumaz (E10: fazla/noksan
sayfaları VİF'e bağlanıp muhasebe birimine gider — TMY 10/1-g, 32/8). Şube etiketi
kişisel veri değildir (sınıf kitaplığı ilerlemesi).

**TMY 34/1** (`tmy_34_1`, A8 kararı — tasarım F8 ekleri 13): taşınır mal yönetim
hesabında "önceki yıldan devredilen, yılı içinde giren, çıkan ve ertesi yıla
devredilen taşınırlar ile yıl sonu sayımında bulunan fazla ve noksanlar gösterilir".
Program Taşınır Sayım ve Döküm Cetveli'ni ÜRETMEZ (TKYS'nindir); bu sayılar
kütüphane materyali için NÜSHA sayısıdır ve taşınır kayıt yetkilisinin cetvele
aktaracağı büyüklüklerdir. "Gelecek yıla devir" sayımda bulunan miktardır (10/1-ğ);
sayımda bulunup onayda hasar nedeniyle (27/1) düşülenler ondan çıkarılır ve ayrı satırda
gösterilir — sayımın kendi çıkışından sonraki kayıt (F9 ekleri madde 25, seçenek a).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any, Final

from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import keys
from apps.kutuphane.models import (
    LOCKING_STOCKTAKE_STATUSES,
    OPEN_STOCKTAKE_STATUSES,
    REPAIR_BASIS_LABELS,
    SHELF_RETURN_RESOLUTIONS,
    TERMINAL_COPY_STATUSES,
    AcquisitionMethod,
    CaseType,
    Copy,
    CopyRepair,
    CopyStatus,
    CountBasis,
    Delivery,
    DeliveryRecipientKind,
    Loan,
    LossDamageCase,
    StockTake,
    StockTakeItem,
    StockTakeOutcome,
    StockTakeResult,
    StockTakeStatus,
    StockTakeWriteOffPath,
    WeedingBatchStatus,
    WeedingItem,
    WeedingItemState,
)

# ---------------------------------------------------------------------------
# Tutanak satırları — iki seçenek AYRI satırda, kurul seçimi dayanağıyla (E10)
# ---------------------------------------------------------------------------
#: TMY 32/3 durdurmasının kapsadığı işlemler (ekran ve tutanak aynı sözcükleri kullanır —
#: ön yüzde `sayim/api.ts::TMY_DURDURMA_KAPSAMI`, test eşitler). Kapının GERÇEK kapsamıyla
#: yazılır (F9 düzeltme turu; F7 ekleri 17): kayıp dosyasında bulunma (F9 ekleri K1) ve
#: bedel adımları, hasar dosyasında öneri yazmayan çözümler kapsam dışıdır. Programa
#: aktarım da durur ama TMY'ye dayandırılmaz (K4) — bu listede yoktur, ayrı cümledir.
TMY_STOP_SCOPE_TEXT: Final = (
    "edinim ve yeni nüsha kaydı, kayıttan düşme, devir, kayıp bildirimi, kayıp dosyasının "
    "bulunma ve bedel adımları dışındaki çözümü ve hasar dosyasında kayıttan düşme önerisi"
)
#: Durdurmanın KAPSAMADIKLARI — durumu değil kapsamı söyler (hizmet arası da seçildiyse
#: yeni ödünç o yüzden kapalıdır; "ödünç açıktır" demek çelişirdi).
TMY_STOP_NOT_COVERED_TEXT: Final = "Durdurma ödüncü ve iadeyi kapsamaz."
RETURN_ALWAYS_OPEN_TEXT: Final = "İade hiçbir durumda durdurulmaz (Yönetmelik Md. 23/1-c)."

#: Hizmet arasının tutanaktaki kapsam cümlesi (madde 27, 25.09.2026 kullanıcı kararı).
SERVICE_PAUSE_SCOPE_TEXT: Final = (
    "sayım süresince yeni ödünç ve teslim durdurulur; iade ve teslimden geri alma açıktır."
)

#: Sınıf kitaplığı kayda göre ALINMAZ (F9 ekleri K3, 25.09.2026 ana oturum kararı): 32/5'e
#: 23/6 üzerinden kıyas sınıf kitaplığını ortak kullanım alanı yapar ve 32/5'in birinci
#: cümlesi ortak kullanım alanındaki taşınırın SAYILMASINI öngörür; "sayım yapılmaksızın"
#: yalnız ikinci cümlededir (kamu görevlilerine teslim belgesiyle verilen taşınır). Seçenek
#: kalktı; toplanamayan şube nüshası yerinde aranır, bulunmazsa noksandır.
SECTION_IN_PLACE_NOTE: Final = (
    "TMY 32/5 birinci cümleye kıyasen (teslim listesi Dayanıklı Taşınırlar Listesi işlevini "
    "görür — 23/6'ya kıyasen)"
)
#: Onarımdaki nüshanın sayımına ilişkin TMY'de doğrudan hüküm YOKTUR (F9 ekleri K2):
#: `docs/mevzuat/tasinir-mal-yonetmeligi.md`'de onarım bakım yükümlülüğü (5/3), değer artışı
#: ve yedek parça (10/1-a, 14/1), iş talep belgesi (10/1-c) ve binayla teslim alınan taşınır
#: (15/5) bağlamında geçer; md. 32'nin hiçbir fıkrası onarımı anmaz (test sınar — BENIOKU §4).
#: Dayanak metni bunu dürüstçe yazar; 32/5 atfedilmez.
REPAIR_NOTE: Final = (
    "sayım kurulunun kararıdır; Taşınır Mal Yönetmeliğinde onarıma gönderilmiş taşınırın "
    "sayımına ilişkin doğrudan hüküm yoktur."
)

#: Kurul seçiminin dayanak metni — (kategori, seçim) → metin. Kıyas "kıyasen" diye yazılır.
BASIS_DAYANAK: Final[dict[tuple[str, str], str]] = {
    ("loan", CountBasis.COLLECT): (
        "Sayımdan önce toplanır; toplanamayan nüsha kayda göre alınır (TMY 32/5'e kıyasen; 23/4)."
    ),
    ("loan", CountBasis.BY_RECORD): (
        "Kayda göre alınır: TMY 32/5'e kıyasen; 23/4 (ödünç takip sistemiyle izlenir)."
    ),
    ("section_delivery", CountBasis.IN_PLACE): (
        f"Sınıf kitaplığında yerinde sayılır: {SECTION_IN_PLACE_NOTE}."
    ),
    ("section_delivery", CountBasis.COLLECT): (
        "Sayımdan önce geri alınır ve kütüphanede sayılır; geri alınamayan nüsha sınıf "
        f"kitaplığında yerinde aranır, bulunmazsa noksandır ({SECTION_IN_PLACE_NOTE})."
    ),
    ("teacher_delivery", CountBasis.COLLECT): (
        "Sayımdan önce geri alınır; geri alınamayan nüsha kayda göre alınır (TMY 32/5'e kıyasen; "
        "23/4)."
    ),
    ("teacher_delivery", CountBasis.BY_RECORD): (
        "Kayda göre alınır: Taşınır Teslim Belgesi düzenlendiyse TMY 32/5 ikinci cümle, "
        "düzenlenmediyse 32/5'e kıyasen (23/4)."
    ),
    ("repair", CountBasis.COLLECT): (
        "Sayımdan önce onarımdan geri alınır ve kütüphanede sayılır. Geri alınamayan nüshanın "
        f"kayda göre alınması {REPAIR_NOTE}"
    ),
    ("repair", CountBasis.BY_RECORD): (
        f"Kayda göre alınır — onarımda (onarım kaydıyla izlenir): {REPAIR_NOTE}"
    ),
}
BASIS_CATEGORY_LABELS: Final[dict[str, str]] = {
    "loan": "Ödünçteki nüsha",
    "section_delivery": "Sınıf kitaplığına teslim edilen nüsha",
    "teacher_delivery": "Öğretmene teslim edilen nüsha",
    "repair": "Onarımdaki nüsha",
}
#: Kategorinin taslaktaki alanı (seçici) — tek kaynak (serializer ve tutanak).
BASIS_CATEGORY_FIELDS: Final[dict[str, str]] = {
    "loan": "loan_basis",
    "section_delivery": "section_delivery_basis",
    "teacher_delivery": "teacher_delivery_basis",
    "repair": "repair_basis",
}
#: Kategoride "geri alınamadı" işaretinin (`basis_fallback`) tutanaktaki cümlesi. Sınıf
#: kitaplığında işaret doğmaz (K3: geri alınamayan yerinde aranır).
BASIS_FALLBACK_TEXT: Final[dict[str, str]] = {
    "loan": "Toplanamayan {sayi} nüsha kayda göre alındı.",
    "section_delivery": "Geri alınamayan {sayi} nüsha kayda göre alındı.",
    "teacher_delivery": "Geri alınamayan {sayi} nüsha kayda göre alındı.",
    "repair": "Onarımdan geri alınamayan {sayi} nüsha kayda göre alındı.",
}


def basis_label(category: str, basis: str) -> str:
    """Seçimin ekrandaki ve tutanaktaki adı: onarımda kararın sözcükleri (K2 —
    `REPAIR_BASIS_LABELS`), öbürlerinde `CountBasis` adı."""
    if category == "repair" and basis in REPAIR_BASIS_LABELS:
        return REPAIR_BASIS_LABELS[basis]
    return str(CountBasis(basis).label)


def item_basis_label(item: StockTakeItem) -> str:
    """Kalemin "Nasıl sayılır"ı: onarımdaki nüshada onarım seçeneğinin adı (K2)."""
    if not item.basis:
        return ""
    kategori = "repair" if item.expected_status == CopyStatus.IN_REPAIR else ""
    return basis_label(kategori, item.basis)


def options_lines(stocktake: StockTake) -> list[dict[str, Any]]:
    """İki seçenek ve iade — tutanakta AYRI satırlar (§9-10; kod kapısı "ayrı satırda").

    Kişi adı taşımaz: durduran harcama yetkilisinin adı ayrıntı yanıtındadır, belge
    onu gerekirse ayrıca basar.
    """
    if stocktake.tmy_stop:
        talep = stocktake.tmy_stop_requested_on
        tarih = stocktake.tmy_stop_on
        durdurma = (
            "Sayım kurulunun"
            + (f" {talep:%d.%m.%Y} tarihli" if talep else "")
            + " talebi üzerine harcama yetkilisince"
            + (f" {tarih:%d.%m.%Y} tarihinde" if tarih else "")
            + f" durduruldu: {TMY_STOP_SCOPE_TEXT}. {TMY_STOP_NOT_COVERED_TEXT}"
        )
    else:
        durdurma = "Seçilmedi: taşınır giriş ve çıkışları durdurulmadı."
    if stocktake.service_pause:
        karar = stocktake.service_pause_decision.strip()
        hizmet = (
            "Seçildi (okul kararı"
            + (f" — {karar}" if karar else "")
            + f"): {SERVICE_PAUSE_SCOPE_TEXT}"
        )
    else:
        hizmet = "Seçilmedi: ödünç ve teslim durdurulmadı."
    return [
        {
            "key": "tmy_32_3",
            "label": "TMY 32/3 durdurması",
            "selected": stocktake.tmy_stop,
            "text": durdurma,
            "basis": "TMY 32/3",
        },
        {
            "key": "service_pause",
            "label": "Sayım için hizmet arası",
            "selected": stocktake.service_pause,
            "text": hizmet,
            # TMY'ye dayandırılmaz; en fazla kurulun önlem alma görevi anılabilir.
            "basis": "Okul kararı (TMY 32/3 ikinci cümle: sayımda önlem almak kurulun görevidir)",
        },
        {
            "key": "return",
            "label": "İade",
            "selected": False,
            "text": RETURN_ALWAYS_OPEN_TEXT,
            "basis": "Yönetmelik Md. 23/1-c",
        },
    ]


def basis_lines(stocktake: StockTake) -> list[dict[str, Any]]:
    """Kurulun ödünçteki, teslimdeki ve onarımdaki nüsha için seçimi ve dayanağı (§9-11)."""
    satirlar: list[dict[str, Any]] = []
    for kategori, alan in BASIS_CATEGORY_FIELDS.items():
        secim = str(getattr(stocktake, alan))
        satirlar.append(
            {
                "category": kategori,
                "label": BASIS_CATEGORY_LABELS[kategori],
                "basis": secim,
                "basis_display": basis_label(kategori, secim),
                "dayanak": BASIS_DAYANAK[(kategori, secim)],
            }
        )
    return satirlar


# ---------------------------------------------------------------------------
# Kilit durumları (kapılar buradan sorar)
# ---------------------------------------------------------------------------
def _kilitleyen() -> QuerySet[StockTake]:
    return StockTake.objects.filter(status__in=LOCKING_STOCKTAKE_STATUSES)


def locking_stocktake() -> StockTake | None:
    """Kilitleri süren sayım ("Sürüyor" ya da "Tamamlandı"); yoksa None."""
    return _kilitleyen().order_by("-pk").first()


def live_stocktake() -> StockTake | None:
    """Canlı sayım (taslak, sürüyor ya da tamamlandı — en çok bir tane)."""
    return StockTake.objects.filter(status__in=OPEN_STOCKTAKE_STATUSES).order_by("-pk").first()


def tmy_stop_active() -> bool:
    """TMY 32/3 durdurması şu an sürüyor mu? (D4, D17)"""
    return _kilitleyen().filter(tmy_stop=True).exists()


def service_pause_active() -> bool:
    """Sayım için hizmet arası şu an sürüyor mu? Yeni ödüncü ve yeni teslimi durdurur."""
    return _kilitleyen().filter(service_pause=True).exists()


def copy_in_live_stocktake(copy_id: int) -> bool:
    """Nüsha süren bir sayımın anlık görüntüsünde mi? (silme kapısı)"""
    return StockTakeItem.objects.filter(
        copy_id=copy_id,
        stocktake__status__in=LOCKING_STOCKTAKE_STATUSES,
        stocktake__deleted_at__isnull=True,
    ).exists()


def copy_created_by_stocktake(copy_id: int) -> bool:
    """Nüsha bir sayımın onayında sayım fazlası olarak mı açıldı? (silme kapısı)"""
    return StockTakeItem.objects.filter(
        created_copy_id=copy_id, stocktake__deleted_at__isnull=True
    ).exists()


# ---------------------------------------------------------------------------
# Sayımlar ve kalemler
# ---------------------------------------------------------------------------
def stocktakes(*, status: str = "", fiscal_year: int | None = None) -> QuerySet[StockTake]:
    qs = StockTake.objects.all()
    if status:
        qs = qs.filter(status=status)
    if fiscal_year is not None:
        qs = qs.filter(fiscal_year=fiscal_year)
    return qs.order_by("-created_at", "-pk")


def get_stocktake(stocktake_id: int) -> StockTake | None:
    return StockTake.objects.filter(pk=stocktake_id).first()


def return_event_q(since: datetime) -> Q:
    """Nüsha `since`'ten beri kütüphaneye döndü mü? (`copy_id` üzerinden Exists koşulu)

    Dönüş: iade (Md. 23/1-c — iade hiçbir durumda kilitlenmez ve sayım sırasında iade
    edilen nüsha o turda "bulundu" sayılır), teslimden geri alma, kayıp dosyasında
    nüshayı rafa döndüren çözüm (bulunma ve aynısının temini — `SHELF_RETURN_RESOLUTIONS`)
    ve onarımdan dönüş.

    F9 düzeltme turu: (1) onarım dönüşü GÜN değil AN düzeyinde karşılaştırılır — sayım
    başlamadan önce aynı gün onarımdan dönmüş ve okutulmamış nüsha "bulundu" sayılmaz.
    `returned_on` tarih alanıdır: ertesi gün ve sonrası kesin dönüştür; aynı gün ise
    kaydın kapandığı an (`updated_at` — onarım kaydı yalnız açılışta ve kapanışta yazılır)
    sayımın başlangıcıyla karşılaştırılır. (2) Kayıp dosyasında "Aynısı temin edildi" ve
    "Bedelle aynısı alındı" da nüshayı rafa döndürür; dönüş sayılmazsa kitap kütüphanede
    dururken 32/7 ile düşülürdü.
    """
    kopya = OuterRef("copy_id")
    gun = timezone.localdate(since)
    return (
        Q(Exists(Loan.objects.filter(copy_id=kopya, returned_at__gte=since)))
        | Q(Exists(Delivery.objects.filter(copy_id=kopya, returned_at__gte=since)))
        | Q(
            Exists(
                LossDamageCase.objects.filter(
                    copy_id=kopya,
                    case_type=CaseType.LOST,
                    resolution__in=SHELF_RETURN_RESOLUTIONS,
                    resolved_at__gte=since,
                )
            )
        )
        | Q(
            Exists(
                CopyRepair.objects.filter(copy_id=kopya).filter(
                    Q(returned_on__gt=gun) | Q(returned_on=gun, updated_at__gte=since)
                )
            )
        )
    )


def items(
    stocktake: StockTake,
    *,
    result: str = "",
    basis: str = "",
    outcome: str = "",
    section_id: int | None = None,
    class_section_id: int | None = None,
    surplus: bool | None = None,
    damage: bool | None = None,
    undecided: bool | None = None,
    q: str = "",
) -> QuerySet[StockTakeItem]:
    """Sayımın canlı kalemleri — eser adının Türkçe sırasıyla, fazlalar sonda.

    `q`: eser adı ya da barkod (rakamlar). `undecided`: kararı bekleyen sayım fazlası
    (eseri seçilmemiş, "Kayda alınmayacak" denmemiş — onayı durduran kalemler).
    Kişisel veri süzgeci YOKTUR.
    """
    qs = StockTakeItem.objects.filter(stocktake=stocktake).select_related(
        "copy",
        "copy__work",
        "section",
        "class_section",
        "case",
        "surplus_copy",
        "surplus_work",
        "created_copy",
    )
    if result:
        qs = qs.filter(result=result)
    if basis:
        qs = qs.filter(basis=basis)
    if outcome:
        qs = qs.filter(outcome=outcome)
    if section_id is not None:
        qs = qs.filter(section_id=section_id)
    if class_section_id is not None:
        qs = qs.filter(class_section_id=class_section_id)
    if surplus is not None:
        qs = qs.filter(copy__isnull=surplus)
    if damage is not None:
        qs = qs.filter(damage_write_off=damage)
    if undecided is not None:
        karar_bekliyor = Q(
            copy__isnull=True, surplus_work__isnull=True, surplus_excluded=False, outcome=""
        ) & ~surplus_bound_q(stocktake)
        qs = qs.filter(karar_bekliyor) if undecided else qs.exclude(karar_bekliyor)
    sade = str(q or "").strip().replace("-", "").replace(" ", "")
    if len(sade) >= 4 and sade.isascii() and sade.isdigit():
        rakamlar = barcode_module.normalize_scan(sade)
        qs = qs.filter(Q(copy__barcode__contains=rakamlar) | Q(surplus_barcode__contains=rakamlar))
    else:
        for terim in keys.search_terms(q):
            qs = qs.filter(
                Q(copy__work__search_key__contains=terim)
                | Q(surplus_work__search_key__contains=terim)
            )
    return qs.order_by(F("copy__work__sort_key").asc(nulls_last=True), "copy__accession_no", "pk")


def surplus_bound_q(stocktake: StockTake) -> Q:
    """Sayım fazlasının okutulan etiketi sayım SIRASINDA bir nüshaya bağlandı mı? (F9 düzeltme)

    Hiçbir kitaba bağlanmamış boş etiket sayım fazlası olarak okutulur; sayım sürerken aynı
    kitap Hızlı Kayıt'ta o etiketle bağlanırsa kitap KAYDA GİRMİŞTİR (kendi edinimiyle).
    Onay onu ikinci kez kayda almaz (D17'nin "onayda yeniden doğrulama" ilkesi fazlaya da
    uygulanır). Nüsha etiketin numarasını taşır ve sayım başladıktan sonra açılmıştır.
    """
    if stocktake.started_at is None:
        return Q(pk__in=[])
    bagli = (
        Copy.objects.filter(
            barcode=OuterRef("surplus_barcode"),
            created_at__gte=stocktake.started_at,
            work__deleted_at__isnull=True,
        )
        .exclude(status__in=TERMINAL_COPY_STATUSES)
        .values("pk")
    )
    return Q(copy__isnull=True) & ~Q(surplus_barcode="") & Q(Exists(bagli))


def bound_surplus_copy(item: StockTakeItem) -> Copy | None:
    """`surplus_bound_q`'nun kalem düzeyindeki eşi: etiketin sayım sırasında bağlandığı nüsha."""
    if item.copy_id is not None or not item.surplus_barcode:
        return None
    baslangic = item.stocktake.started_at
    if baslangic is None:
        return None
    nusha: Copy | None = (
        Copy.objects.select_related("work")
        .filter(
            barcode=item.surplus_barcode,
            created_at__gte=baslangic,
            work__deleted_at__isnull=True,
        )
        .exclude(status__in=TERMINAL_COPY_STATUSES)
        .first()
    )
    return nusha


def summary(stocktake: StockTake) -> dict[str, Any]:
    """Kişisiz sayılar: sonuçlar, onay sonuçları, fazla ve hasar listesi (TEK birkaç sorgu).

    `missing_recorded_lost` ve `missing_in_repair` (F9 düzeltme turu): tamamlanırken kayıtta
    "Kayıp" ya da "Onarımda" görünen noksanlar. Onay penceresi bunlar için uyarır. Kayıp
    kitap sayım tamamlandıktan sonra getirildiyse kayıp dosyası onaydan önce "Bulundu" ile
    kapatılır (K1: bulunma TMY 32/3 durdurmasının kapsamında değildir) ve onay kalemi
    düşmez. Onarımdaki nüsha kurulun seçimiyle kayda göre alınır (K2); noksanda "Onarımda"
    görünen, sayım sırasında onarıma gönderilmiş nüshadır — kitap onarımcıda olabilir.
    """
    qs = StockTakeItem.objects.filter(stocktake=stocktake)
    sonuclar = {
        satir["result"]: satir["adet"] for satir in qs.values("result").annotate(adet=Count("pk"))
    }
    onaylar = {
        satir["outcome"]: satir["adet"]
        for satir in qs.exclude(outcome="").values("outcome").annotate(adet=Count("pk"))
    }
    fazla = qs.filter(copy__isnull=True)
    bagli = surplus_bound_q(stocktake)
    fiziki = qs.filter(copy__isnull=False).exclude(basis=CountBasis.BY_RECORD)
    noksan = qs.filter(result=StockTakeResult.MISSING)
    return {
        "snapshot": qs.filter(copy__isnull=False).count(),
        "results": {r: sonuclar.get(r, 0) for r in StockTakeResult.values},
        "outcomes": {o: onaylar.get(o, 0) for o in StockTakeOutcome.values},
        "physical_expected": fiziki.count(),
        "physical_found": fiziki.filter(result=StockTakeResult.FOUND).count(),
        "by_record_basis": qs.filter(basis=CountBasis.BY_RECORD).count(),
        "surplus": fazla.count(),
        "surplus_unresolved": fazla.filter(
            surplus_work__isnull=True, surplus_excluded=False, outcome=""
        )
        .exclude(bagli)
        .count(),
        "surplus_excluded": fazla.filter(surplus_excluded=True).count(),
        "surplus_bound": fazla.filter(bagli).count(),
        "damage_write_off": qs.filter(damage_write_off=True).count(),
        "found_in_round2": qs.filter(found_in_round=2).count(),
        "missing_recorded_lost": noksan.filter(status_at_completion=CopyStatus.LOST).count(),
        "missing_in_repair": noksan.filter(status_at_completion=CopyStatus.IN_REPAIR).count(),
    }


def progress(stocktake: StockTake) -> dict[str, Any]:
    """Bölüm bölüm ve sınıf kitaplığı sınıf kitaplığı ilerleme (kişisiz).

    Sayım sürerken kütüphaneye dönen (iade, geri alma, bulunma, onarımdan dönüş) ve
    henüz okutulmamış nüsha da "bulundu" sayılır — tamamlanınca öyle yazılır.
    Kayda göre alınan nüsha fiziki ilerlemeye girmez, ayrı sayıdır.
    """
    kalemler = StockTakeItem.objects.filter(stocktake=stocktake, copy__isnull=False)
    bulundu = Q(result=StockTakeResult.FOUND)
    if stocktake.started_at is not None:
        bulundu |= Q(
            result__in=(StockTakeResult.PENDING, StockTakeResult.MISSING)
        ) & return_event_q(stocktake.started_at)
    fiziki = kalemler.exclude(basis=CountBasis.BY_RECORD)
    kutuphane = fiziki.exclude(basis=CountBasis.IN_PLACE)
    bolumler = [
        {
            "section": satir["section_id"],
            "name": satir["section__name"] or "",
            "expected": satir["beklenen"],
            "found": satir["bulunan"],
            "_sira": (
                satir["section_id"] is None,
                satir["section__sort_order"] or 0,
                satir["section__name_sort_key"] or "",
            ),
        }
        for satir in kutuphane.values(
            "section_id", "section__name", "section__sort_order", "section__name_sort_key"
        ).annotate(beklenen=Count("pk"), bulunan=Count("pk", filter=bulundu))
    ]
    bolumler.sort(key=lambda s: s.pop("_sira"))
    siniflar = [
        {
            "class_section": satir["class_section_id"],
            "label": _sinif_etiketi(
                satir["class_section__class_level"], satir["class_section__class_section"]
            ),
            "expected": satir["beklenen"],
            "found": satir["bulunan"],
            "_sira": (
                satir["class_section__class_level"] or 0,
                keys.tr_collation_key(satir["class_section__class_section"] or ""),
            ),
        }
        for satir in fiziki.filter(basis=CountBasis.IN_PLACE)
        .values("class_section_id", "class_section__class_level", "class_section__class_section")
        .annotate(beklenen=Count("pk"), bulunan=Count("pk", filter=bulundu))
    ]
    siniflar.sort(key=lambda s: s.pop("_sira"))
    return {
        "round": stocktake.round,
        "sections": bolumler,
        "class_libraries": siniflar,
        "physical_expected": fiziki.count(),
        "physical_found": fiziki.filter(bulundu).count(),
        "by_record_basis": kalemler.filter(basis=CountBasis.BY_RECORD).count(),
        "surplus": StockTakeItem.objects.filter(stocktake=stocktake, copy__isnull=True).count(),
    }


def _sinif_etiketi(seviye: int | None, sube: str | None) -> str:
    if seviye is None:
        return ""
    return f"{seviye}/{sube or ''}"


def category_lines(stocktake: StockTake) -> list[dict[str, Any]]:
    """Ödünçteki, teslimdeki ve onarımdaki nüshanın nasıl sayıldığı — AYRI satırlar (F8
    ekleri 13; onarım — F9 ekleri K2).

    Her satır: kategori, kurulun seçimi ve dayanağı, anlık görüntüdeki nüsha sayısı ve
    sonuç kırılımı. Kimlik yok: yalnız sayı.
    """
    kategoriler = {
        "loan": Q(expected_status=CopyStatus.ON_LOAN),
        "section_delivery": Q(
            expected_status=CopyStatus.DELIVERED, delivery_kind=DeliveryRecipientKind.SECTION
        ),
        "teacher_delivery": Q(
            expected_status=CopyStatus.DELIVERED, delivery_kind=DeliveryRecipientKind.TEACHER
        ),
        "repair": Q(expected_status=CopyStatus.IN_REPAIR),
    }
    satirlar = {s["category"]: s for s in basis_lines(stocktake)}
    sonuc: list[dict[str, Any]] = []
    for kategori, kosul in kategoriler.items():
        qs = StockTakeItem.objects.filter(stocktake=stocktake).filter(kosul)
        sayilar = {s["result"]: s["adet"] for s in qs.values("result").annotate(adet=Count("pk"))}
        sonuc.append(
            {
                **satirlar[kategori],
                "count": sum(sayilar.values()),
                "results": {r: sayilar.get(r, 0) for r in StockTakeResult.values},
                "fallback": qs.filter(basis_fallback=True).count(),
            }
        )
    return sonuc


# ---------------------------------------------------------------------------
# TMY 34/1 büyüklükleri (A8 kararı; E10 eki)
# ---------------------------------------------------------------------------
#: TMY 34/1'in "yılı içinde giren"i: Md. 10/5 yolları ve sayım fazlası (TMY 17).
#: Mevcut koleksiyonun programa aktarımı AYRI satırdır (taşınır girişi değil, kayıt işlemi).
GIREN_YOLLAR: Final[tuple[str, ...]] = (
    AcquisitionMethod.MINISTRY,
    AcquisitionMethod.PURCHASE,
    AcquisitionMethod.DONATION,
    AcquisitionMethod.EXCHANGE,
    AcquisitionMethod.INVENTORY_FOUND,
)
TMY_34_1_NOTE: Final = (
    "Bu döküm Taşınır Sayım ve Döküm Cetveli değildir; resmî cetvel TKYS'de düzenlenir."
)


def exit_dates() -> dict[int, date]:
    """Kayıttan çıkmış nüshaların çıkış tarihi — harcama yetkilisinin onay tarihi.

    Ayıklama (TMY 27/1, 28) ve devir (24/2, 31): uygulanmış teklifin onay tarihi; sayım
    (noksan — 32/7; hasar — 27/1): sayımın onay tarihi. VİF dayanağından önceki tarihi
    taşıyamaz (10/1-a); onay tarihi o dayanaktır.
    """
    tarihler: dict[int, date] = {}
    for copy_id, onay in WeedingItem.objects.filter(
        state=WeedingItemState.APPLIED,
        batch__status=WeedingBatchStatus.APPLIED,
        batch__deleted_at__isnull=True,
    ).values_list("copy_id", "batch__approved_on"):
        if onay is not None:
            tarihler[int(copy_id)] = onay
    for copy_id, onay in StockTakeItem.objects.filter(
        outcome=StockTakeOutcome.WRITTEN_OFF,
        stocktake__status=StockTakeStatus.APPROVED,
        stocktake__deleted_at__isnull=True,
    ).values_list("copy_id", "stocktake__approved_on"):
        if copy_id is not None and onay is not None:
            tarihler[int(copy_id)] = onay
    return tarihler


def found_quantity(stocktake: StockTake) -> dict[str, Any]:
    """Sayımda bulunan miktar (TMY 10/1-ğ: "Gelecek Yıla Devir"e eşit olmalıdır).

    Bulunan = bulundu + kayda göre alındı (32/5'e kıyasen) + sayım fazlası (kütüphaneye
    ait olmadığı işaretlenenler hariç). Noksan ve sayım sırasında kayıttan çıkan
    girmez. Sayım tamamlanmadan sayı KESİN değildir; tamamlanmış sayımda da kararı bekleyen
    sayım fazlası varken kesin değildir (F9 düzeltme turu): kurul onu "Kayda alınmayacak"
    derse sayımda bulunan miktardan düşer — imzaya basılan tutanak bunu söyler
    (`surplus_unresolved`).
    """
    qs = StockTakeItem.objects.filter(stocktake=stocktake)
    bulundu = qs.filter(result__in=(StockTakeResult.FOUND, StockTakeResult.BY_RECORD)).count()
    fazla = qs.filter(copy__isnull=True, surplus_excluded=False).count()
    noksan = qs.filter(result=StockTakeResult.MISSING).count()
    kararsiz = (
        qs.filter(copy__isnull=True, surplus_work__isnull=True, surplus_excluded=False, outcome="")
        .exclude(surplus_bound_q(stocktake))
        .count()
    )
    tamam = stocktake.status in (StockTakeStatus.COMPLETED, StockTakeStatus.APPROVED)
    return {
        "final": tamam and kararsiz == 0,
        "surplus_unresolved": kararsiz,
        "found": bulundu + fazla,
        "surplus": fazla,
        "missing": noksan,
        "missing_written_off": qs.filter(
            result=StockTakeResult.MISSING, outcome=StockTakeOutcome.WRITTEN_OFF
        ).count(),
        # Madde 25 (a): sayımda bulunup onayda hasar nedeniyle (27/1) düşülenler ve henüz
        # onaylanmamış hasar önerileri (onaydan önce gelecek yıla devir kesin değildir).
        "damage_written_off": qs.filter(
            outcome=StockTakeOutcome.WRITTEN_OFF, write_off_path=StockTakeWriteOffPath.DAMAGE_27_1
        ).count(),
        "damage_pending": qs.filter(damage_write_off=True, outcome="").count(),
    }


def tmy_34_1(stocktake: StockTake, *, fiscal_year: int | None = None) -> dict[str, Any]:
    """TMY 34/1'in dört büyüklüğü (+ fazla ve noksan) — nüsha sayısıyla (A8 kararı).

    Yıl mali yıldır (1 Ocak - 31 Aralık; VİF sıra numarası her mali yılın başında 1'den
    başlar — 10/1-a). Giriş tarihi edinim tarihidir; çıkış tarihi harcama yetkilisinin
    onay tarihidir (`exit_dates`). Silinmiş (yanlış açılmış) nüsha hiç sayılmaz.

    - **önceki yıldan devir**: yıl başında kayıtta olan;
    - **programa aktarım** (AYRI satır): yıl içinde programa aktarılan mevcut
      koleksiyon — taşınır girişi değildir, önceki yıllardan gelir;
    - **yıl içinde giren**: Md. 10/5 yolları ve sayım fazlası (TMY 17), yola göre;
    - **yıl içinde çıkan**: kayıttan düşme ve devir, nüsha durumuna göre;
    - **kayda göre yıl sonu** = devir + aktarım + giren − çıkan;
    - **gelecek yıla devir** = sayımda bulunan (10/1-ğ) − onayda hasar nedeniyle (27/1)
      düşülen (F9 ekleri madde 25, seçenek a: cetvele aktarılacak devir sayımın kendi
      çıkışından sonraki kaydı yansıtır; sayımda bulunan miktar DEĞİŞMEZ, düşülen ayrı
      satırdadır). Onaylanmamış hasar önerisi varken devir onaydan sonra yazılır
      (`carryover_final`). Kayda göre yıl sonuyla farkı varsa (onaylanmayan noksan, sayım
      sürerken yapılan giriş ya da çıkış) ayrıca gösterilir.
    """
    yil = fiscal_year or stocktake.fiscal_year or timezone.localdate().year
    bas, son = date(yil, 1, 1), date(yil, 12, 31)
    cikislar = exit_dates()
    devir = aktarim = kayda_gore = 0
    giren: Counter[str] = Counter()
    cikan: Counter[str] = Counter()
    satirlar = Copy.objects.filter(work__deleted_at__isnull=True).values_list(
        "pk", "status", "acquisition__date", "acquisition__method", "updated_at"
    )
    for pk, durum, giris, yol, guncel in satirlar:
        cikis: date | None = None
        if durum in TERMINAL_COPY_STATUSES:
            cikis = cikislar.get(int(pk)) or timezone.localdate(guncel)
        if giris > son:
            continue
        if giris < bas:
            if cikis is None or cikis >= bas:
                devir += 1
        elif yol == AcquisitionMethod.EXISTING_STOCK:
            aktarim += 1
        else:
            giren[yol] += 1
        if cikis is not None and bas <= cikis <= son:
            cikan[durum] += 1
        if cikis is None or cikis > son:
            kayda_gore += 1
    bulunan = found_quantity(stocktake)
    devir_kesin = bool(bulunan["final"]) and (
        stocktake.status == StockTakeStatus.APPROVED or bulunan["damage_pending"] == 0
    )
    gelecek = bulunan["found"] - bulunan["damage_written_off"] if devir_kesin else None
    fark = kayda_gore - gelecek if gelecek is not None else None
    return {
        "fiscal_year": yil,
        "period_start": bas.isoformat(),
        "period_end": son.isoformat(),
        "previous_year_carryover": devir,
        "program_transfer": aktarim,
        "entered": sum(giren.values()),
        "entered_by_method": {y: giren.get(y, 0) for y in GIREN_YOLLAR},
        "exited": sum(cikan.values()),
        "exited_by_status": {d: cikan.get(d, 0) for d in TERMINAL_COPY_STATUSES},
        "year_end_by_record": kayda_gore,
        "found_quantity": bulunan["found"] if bulunan["final"] else None,
        "damage_written_off": bulunan["damage_written_off"],
        "damage_pending": bulunan["damage_pending"],
        "next_year_carryover": gelecek,
        "count_final": bulunan["final"],
        "carryover_final": devir_kesin,
        "surplus_unresolved": bulunan["surplus_unresolved"],
        "surplus": bulunan["surplus"],
        "missing": bulunan["missing"],
        "missing_written_off": bulunan["missing_written_off"],
        "difference": fark,
        "categories": category_lines(stocktake),
        "note": TMY_34_1_NOTE,
    }
