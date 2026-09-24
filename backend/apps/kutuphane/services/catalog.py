"""Katalog yazma yolları: bölüm, eser, nüsha, edinim (tasarım §6.2, F2).

Kurallar tek yerdedir; görünüm katmanı ORM'e doğrudan yazmaz:

- **Dijital kaynakta nüsha açılmaz** (e-kitap, e-veri tabanı): TMY'nin fiziksel
  taşınır düzeni dışındadır, rafta durmaz, sayımda görülmez.
- **Süreli yayın yalnız ciltletildiğinde kayda girer** (TMY Md. 15/4); "ciltli
  süreli yayın" işareti de yalnız süreli yayında kullanılır (ters yön).
- **Nüsha kuralları eser güncellenirken de korunur** (`ensure_work_type_change`):
  kaynak türü değişimi, nüsha açılırken uygulanan kuralları delemez.
- **Bağışta komisyon kararı zorunludur** (Md. 10/3) ve kararın TÜRÜ denetlenir
  (D7 — `services.commissions.require_decision_type`).
- **Barkod ve kayıt no yalnız sayaçtan gelir** (`services.numbering`); dışarıdan
  verilemez, elle değiştirilemez.
- **Yer numarası** boş bırakılırsa üretilir (D11: `tr_upper` + soyad sezgisi) ve
  elle değiştirilebilir.
- **Yumuşak silinmiş eser ya da edinim kullanılamaz.** CLAUDE.md §3: `obj.fk`
  erişimi ve `select_related` silinmiş kaydı geri getirir, `PROTECT` yumuşak
  silmede hiç tetiklenmez — canlılık elle denetlenir.

Durum (`Copy.status`) geçişleri BU MODÜLDE DEĞİLDİR: ödünç/iade F6'da,
teslim ve onarım F7'de, kayıttan düşme F8-F9'da kendi servislerinden yürür.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kutuphane import keys
from apps.kutuphane.models import (
    DIGITAL_RESOURCE_TYPES,
    TERMINAL_COPY_STATUSES,
    Acquisition,
    AcquisitionMethod,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    CopyStatus,
    ResourceType,
    Section,
    Work,
)
from apps.kutuphane.services import commissions, numbering

#: Nüshada servis dışından yazılamayacak alanlar (kimlik ve durum makinesi).
PROTECTED_COPY_FIELDS: tuple[str, ...] = ("barcode", "accession_no", "status")


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------
def _require_alive(obj: Any, *, field: str, label: str) -> None:
    """Yumuşak silinmiş kayıt kullanılmak isteniyorsa `ValidationError`."""
    if getattr(obj, "deleted_at", None) is not None:
        raise ValidationError({field: f"{label} silinmiş; önce geri alın ya da başkasını seçin."})


# ---------------------------------------------------------------------------
# Bölüm
# ---------------------------------------------------------------------------
def ensure_section_name_free(name: object, *, exclude_pk: int | None = None) -> None:
    """Bölüm adı canlı listede zaten var mı? (Türkçe katlamalı — TEK kapı)

    İki sebepten model kısıtına bırakılmaz:

    1. **İleti.** Koşullu `UniqueConstraint` ihlalinde `full_clean` kısıtın ADINI
       kullanıcıya basar ("“uq_section_name_alive” kısıtlaması ihlal edildi");
       sözlük iç kimliklerin kullanıcı metnine girmesini yasaklar (§2).
    2. **Katlama.** DB kısıtı harfi harfine eşitliğe bakar; "Edebiyat",
       "edebiyat " ve "EDEBİYAT" AYNI bölümdür — kontrollü listenin var olma
       sebebi budur (§6.2) — ama SQLite `=` Türkçe harflerde bunu göremez (T7).

    Karşılaştırma Python'dadır: liste kontrollü ve kısadır, tam tarama ucuzdur.

    `fold_search` harf ve rakam dışını atar, yani yalnız noktalamadan oluşan bir
    ad ("!!!", "—", "…") boş dizeye iner. O durumda denetimi ATLAMAK kapıyı
    delerdi: ikinci kayıt DB kısıtına düşer ve `full_clean` kısıtın ADINI
    kullanıcıya basardı — engellenmek istenen şeyin ta kendisi. Bu yüzden
    katlama boş dönerse kırpılmış HAM ad üzerinden karşılaştırılır.
    """
    aranan = keys.fold_search(name) or str(name or "").strip()
    if not aranan:
        return
    if any(
        (keys.fold_search(mevcut) or str(mevcut or "").strip()) == aranan
        for pk, mevcut in Section.objects.values_list("pk", "name")
        if pk != exclude_pk
    ):
        raise ValidationError({"name": "Bu adda bir bölüm zaten var. Var olan bölümü kullanın."})


@transaction.atomic
def create_section(**fields: Any) -> Section:
    """Bölüm açar (kontrollü liste)."""
    section = Section(**fields)
    ensure_section_name_free(section.name)
    section.full_clean(exclude=["name_sort_key"])
    section.save()
    return section


@transaction.atomic
def update_section(section: Section, **fields: Any) -> Section:
    """Bölümü günceller; ad sıralama anahtarı `save()`'de yeniden türetilir."""
    for name, value in fields.items():
        setattr(section, name, value)
    ensure_section_name_free(section.name, exclude_pk=section.pk)
    section.full_clean(exclude=["name_sort_key"])
    section.save()
    return section


@transaction.atomic
def delete_section(section: Section) -> None:
    """Bölümü yumuşak siler.

    Bölüme bağlı canlı eser ya da nüsha varsa reddedilir: `PROTECT` yumuşak
    silmede tetiklenmez (CLAUDE.md §3), denetim burada elle yapılır — aksi hâlde
    bölüm listeden düşer, nüshalar görünmez bir bölüme bağlı kalırdı.
    """
    if section.works.exists() or section.copies.exists():
        raise ValidationError(
            {"section": ("Bu bölümde eser ya da nüsha var. Önce onları başka bir bölüme taşıyın.")}
        )
    section.delete()


# ---------------------------------------------------------------------------
# Eser
# ---------------------------------------------------------------------------
def _fill_call_number(work: Work) -> None:
    """Yer numarası boşsa üretir (sınıflama kodu + yazar soyadının ilk üç harfi)."""
    if not work.call_number.strip():
        work.call_number = keys.build_call_number(work.classification_code, work.authors)


@transaction.atomic
def create_work(**fields: Any) -> Work:
    """Eser açar. ISBN ve Türkçe anahtarlar `Work.save()`'de türetilir."""
    work = Work(**fields)
    if work.section_id is not None:
        _require_alive(work.section, field="section", label="Seçilen bölüm")
    _fill_call_number(work)
    work.full_clean(exclude=list(Work.DERIVED_FIELDS))
    work.save()
    return work


def ensure_work_type_change(work: Work, new_resource_type: str) -> None:
    """Kaynak türü var olan nüshalarla bağdaşıyor mu? (nüsha kurallarının EŞİ)

    `ensure_copy_allowed` nüsha açılırken bakar; bu kapı aynı kuralları ESER
    DEĞİŞİRKEN korur. İkisi olmadan kural güncelleme yolundan delinirdi: nüshası
    olan bir kitap e-kitaba çevrilebiliyor, e-kitabın kayıt defterinde nüshası
    oluyor, o nüsha ödünç verilebilir görünüyor ve bir daha DÜZENLENEMİYORDU
    (her `update_copy` kendi kapısına takılırdı).

    Üç değişmez, canlı nüshalar üzerinden:

    1. Dijital kaynağın (e-kitap, e-veri tabanı) nüshası olamaz.
    2. Süreli yayının nüshası yalnız ciltliyse kayda girer (TMY Md. 15/4).
    3. "Ciltli süreli yayın" işareti yalnız süreli yayında kullanılır, yani
       süreli yayından çıkarken ciltli nüsha kalamaz.
    """
    nushalar = work.copies.all()
    if new_resource_type in DIGITAL_RESOURCE_TYPES:
        if nushalar.exists():
            raise ValidationError(
                {
                    "resource_type": (
                        "Bu eserin nüshaları var; kaynak türü e-kitap ya da e-veri tabanına "
                        "çevrilemez. Önce nüshaları silin ya da kayıttan düşürün."
                    )
                }
            )
        return
    if new_resource_type == ResourceType.PERIODICAL:
        if nushalar.filter(is_bound_periodical=False).exists():
            raise ValidationError(
                {
                    "resource_type": (
                        "Bu eserin ciltsiz nüshaları var; kaynak türü süreli yayına çevrilemez "
                        "(TMY Md. 15/4). Nüshalar ciltletildiyse önce nüsha kayıtlarında "
                        "“ciltli süreli yayın” seçeneğini işaretleyin."
                    )
                }
            )
        return
    if nushalar.filter(is_bound_periodical=True).exists():
        raise ValidationError(
            {
                "resource_type": (
                    "Bu eserin “ciltli süreli yayın” işaretli nüshaları var; kaynak türü "
                    "süreli yayından çıkarılamaz. Önce nüshalardaki işareti kaldırın."
                )
            }
        )


@transaction.atomic
def update_work(work: Work, **fields: Any) -> Work:
    """Eseri günceller; yer numarası boş bırakılmışsa yeniden üretilir."""
    for name, value in fields.items():
        setattr(work, name, value)
    if work.section_id is not None:
        _require_alive(work.section, field="section", label="Seçilen bölüm")
    ensure_work_type_change(work, work.resource_type)
    _fill_call_number(work)
    work.full_clean(exclude=list(Work.DERIVED_FIELDS))
    work.save()
    return work


@transaction.atomic
def delete_work(work: Work) -> None:
    """Eseri yumuşak siler; canlı nüshası varsa reddeder."""
    if work.copies.exists():
        raise ValidationError(
            {"work": "Bu eserin nüshaları var. Önce nüshaları kayıttan düşürün ya da silin."}
        )
    work.delete()


# ---------------------------------------------------------------------------
# Nüsha
# ---------------------------------------------------------------------------
def ensure_copy_allowed(work: Work, *, is_bound_periodical: bool) -> None:
    """Bu eser için nüsha açılabilir mi? (tasarım §6.2; F2 kod kapısı)

    Dijital kaynak rafta durmaz; süreli yayın yalnız ciltletildiğinde TMY
    defterine girer (Md. 15/4). Üç kural da nüshanın VARLIĞIYLA ilgilidir;
    ödünç verilebilirlik ayrı bir sorudur (`Copy.is_loanable`).

    Süreli yayın denetimi İKİ YÖNLÜDÜR. Ters yön (kitap türünde bir esere
    "ciltli süreli yayın" nüshası açmak) denetlenmezse alan sessizce anlamsız
    dolar: F3'ün Excel şemasında "Kaynak Türü" ile "Ciltli Süreli Yayın" AYRI
    sütunlardır, yani bir satır "Kitap" + "Evet" diyebilir. Md. 16/1-c süreli
    yayının ödünç verilmemesini ister; ciltletilmiş süreli yayın da süreli
    yayındır ve kitap künyesine saklanmış hâlde ödünç verilebilir kalırdı.
    """
    if work.is_digital:
        raise ValidationError(
            {
                "work": (
                    "E-kitap ve e-veri tabanı için nüsha açılamaz: bunlar rafta durmaz, "
                    "kayıt defterine girmez."
                )
            }
        )
    if work.resource_type == ResourceType.PERIODICAL and not is_bound_periodical:
        raise ValidationError(
            {
                "is_bound_periodical": (
                    "Süreli yayın yalnız ciltletildiğinde kayda girer (TMY Md. 15/4). "
                    "Ciltletildiyse “ciltli süreli yayın” seçeneğini işaretleyin."
                )
            }
        )
    if is_bound_periodical and work.resource_type != ResourceType.PERIODICAL:
        raise ValidationError(
            {
                "is_bound_periodical": (
                    "“Ciltli süreli yayın” işareti yalnız kaynak türü “Süreli yayın” olan "
                    "eserlerde kullanılır. Eserin kaynak türünü düzeltin ya da işareti "
                    "kaldırın."
                )
            }
        )


def validate_new_copy(*, work: Work, acquisition: Acquisition, **fields: Any) -> dict[str, Any]:
    """Yeni nüshanın kurallarını uygular; numarasız, yazılmaya hazır alanları döndürür.

    `create_copy` ile F4'ün boş barkod bağlaması (`services.barcode_reservations`)
    AYNI kapıdan geçer: numaranın sayaçtan mı yoksa önceden ayrılmış bir boş
    etiketten mi geldiği, nüsha kurallarını (dijital kaynak, ciltsiz süreli
    yayın, silinmiş eser/edinim/bölüm) değiştirmez. Kimlik alanları dışarıdan
    verilemez — ayrılmış numarayı da çağıran bu işlevden SONRA ekler.
    """
    for alan in PROTECTED_COPY_FIELDS:
        if alan in fields:
            raise ValidationError(
                {alan: "Bu alan program tarafından üretilir, dışarıdan verilemez."}
            )
    _require_alive(work, field="work", label="Seçilen eser")
    _require_alive(acquisition, field="acquisition", label="Seçilen edinim")
    is_bound_periodical = bool(fields.pop("is_bound_periodical", False))
    ensure_copy_allowed(work, is_bound_periodical=is_bound_periodical)
    section = fields.get("section")
    if section is not None:
        _require_alive(section, field="section", label="Seçilen bölüm")
    return {
        "work": work,
        "acquisition": acquisition,
        "is_bound_periodical": is_bound_periodical,
        **fields,
    }


@transaction.atomic
def create_copy(*, work: Work, acquisition: Acquisition, **fields: Any) -> Copy:
    """Tek nüsha açar: numara sayaçtan gelir, kurallar uygulanır, durum "Rafta"dır."""
    alanlar = validate_new_copy(work=work, acquisition=acquisition, **fields)
    accession_no, barcode = numbering.next_copy_identity()
    copy: Copy = Copy.objects.create(accession_no=accession_no, barcode=barcode, **alanlar)
    return copy


@transaction.atomic
def create_copies(
    *, work: Work, acquisition: Acquisition, count: int = 1, **fields: Any
) -> list[Copy]:
    """Aynı künyeden `count` nüsha açar (Excel'in "Nüsha Sayısı" sütununun karşılığı).

    Eski kayıt no TEK nüshaya aittir (§8.1): dolu olduğu çağrıda nüsha sayısı
    birden büyük olamaz — aksi hâlde aynı eski damga birkaç nüshaya yazılırdı.
    """
    if count < 1:
        raise ValidationError({"count": "Nüsha sayısı en az 1 olmalıdır."})
    if str(fields.get("old_register_no", "")).strip() and count > 1:
        raise ValidationError(
            {
                "old_register_no": (
                    "Bir eski kayıt no tek nüshaya aittir. Aynı eserin öbür nüshaları için "
                    "nüshaları ayrı ayrı ekleyin."
                )
            }
        )
    return [create_copy(work=work, acquisition=acquisition, **fields) for _ in range(count)]


@transaction.atomic
def update_copy(copy: Copy, **fields: Any) -> Copy:
    """Nüshanın katalog alanlarını günceller.

    Kimlik alanları (barkod, kayıt no) ve durum BURADAN yazılmaz: numara asla
    değişmez, durum kendi servislerinden (ödünç, teslim, onarım, kayıttan
    düşme) geçer.
    """
    for alan in PROTECTED_COPY_FIELDS:
        if alan in fields:
            raise ValidationError(
                {alan: "Bu alan program tarafından yönetilir, elle değiştirilemez."}
            )
    for name, value in fields.items():
        setattr(copy, name, value)
    if copy.section_id is not None:
        _require_alive(copy.section, field="section", label="Seçilen bölüm")
    _require_alive(copy.work, field="work", label="Seçilen eser")
    ensure_copy_allowed(copy.work, is_bound_periodical=copy.is_bound_periodical)
    copy.full_clean(exclude=["barcode", "accession_no"])
    copy.save()
    return copy


@transaction.atomic
def delete_copy(copy: Copy) -> None:
    """Yanlış açılmış nüshayı yumuşak siler. Numarası SERBEST KALMAZ.

    Silme yalnız veri giriş hatası içindir (aynı kitap iki kez açıldı, yanlış
    eserin altına girildi); bu yüzden kural "YALNIZ RAFTA olan nüsha silinir"
    biçiminde yazılmıştır — durum listesi saymak yerine. Böylece F7 (kayıp ve
    hasar) ile F8-F9 (kayıttan düşme, devir) yeni bir hâl eklediğinde kapı
    kendiliğinden kapsar; sayılan listeye eklemeyi unutmak sessiz bir açık
    bırakırdı.

    Reddedilen hâllerin gerekçeleri:

    - Nüsha dışarıdaysa (ödünçte ya da sınıf kitaplığında) silmek kitabın kimde
      olduğunu unutmak demektir; önce iade ya da geri alma yapılır.
    - Kayıp ya da onarımdaki nüsha bir İŞLETME HÂLİDİR, veri giriş hatası
      değildir: kaydı silmek kayıp/hasar dosyasını ve Md. 19'un (kaynağın temini
      ya da bedelinin alınması) izini yok eder.
    - Kayıttan düşülmüş ya da devredilmiş nüsha silinemez: kayıttan düşme bir
      taşınır işlemidir, nüsha defterde ve tutanakta görünmeye devam eder
      (yumuşak silme onun karşılığı DEĞİLDİR).

    Barkod ve kayıt no teklik kısıtı DÜZ `unique`'tir: silinen nüshanın numarası
    başka nüshaya asla verilmez — bu yüzden defterde izahı olmayan boşluk
    kalmaması önemlidir.
    """
    if copy.status in (CopyStatus.ON_LOAN, CopyStatus.DELIVERED):
        raise ValidationError(
            {
                "status": (
                    f"{copy.get_status_display()} durumundaki nüsha silinemez. "
                    "Önce kitabı geri alın."
                )
            }
        )
    if copy.status in TERMINAL_COPY_STATUSES:
        raise ValidationError(
            {
                "status": (
                    "Kayıttan düşülmüş ya da devredilmiş nüsha silinemez; kayıt defterinde "
                    "ve tutanakta kalır."
                )
            }
        )
    if copy.status != CopyStatus.AVAILABLE:
        raise ValidationError(
            {
                "status": (
                    f"{copy.get_status_display()} durumundaki nüsha silinemez. Silme yalnız "
                    "yanlış açılmış kayıt içindir; nüshayı önce rafa döndürün, kayıttan "
                    "düşülecekse kayıttan düşme yolunu kullanın."
                )
            }
        )
    copy.delete()


# ---------------------------------------------------------------------------
# Edinim
# ---------------------------------------------------------------------------
def ensure_acquisition_decision(method: str, decision: CommissionDecision | None) -> None:
    """Edinimin komisyon kararı kuralı (Md. 10/3 + D7 tür denetimi).

    Bağışta karar ZORUNLUDUR ve türü "bağış değerlendirme" olmalıdır. Hangi
    edinim yolu olursa olsun ayıklama kararı edinime bağlanamaz: ayıklama
    kaynağın kayıttan düşülmesidir, edinilmesi değil.
    """
    if method == AcquisitionMethod.DONATION:
        if decision is None:
            raise ValidationError(
                {
                    "commission_decision": (
                        "Bağış, Seçim ve Ayıklama Komisyonu değerlendirmesinden geçer "
                        "(Md. 10/3): komisyon kararını seçin."
                    )
                }
            )
        commissions.require_decision_type(decision, CommissionDecisionType.DONATION_REVIEW)
        return
    if decision is not None and decision.decision_type == CommissionDecisionType.WEEDING:
        raise ValidationError({"commission_decision": "Ayıklama kararı bir edinime bağlanamaz."})


@transaction.atomic
def create_acquisition(**fields: Any) -> Acquisition:
    """Edinim partisi açar."""
    acquisition = Acquisition(**fields)
    ensure_acquisition_decision(acquisition.method, acquisition.commission_decision)
    acquisition.full_clean()
    acquisition.save()
    return acquisition


@transaction.atomic
def update_acquisition(acquisition: Acquisition, **fields: Any) -> Acquisition:
    """Edinimi günceller (komisyon kararı kuralı yeniden denetlenir)."""
    for name, value in fields.items():
        setattr(acquisition, name, value)
    ensure_acquisition_decision(acquisition.method, acquisition.commission_decision)
    acquisition.full_clean()
    acquisition.save()
    return acquisition


@transaction.atomic
def delete_acquisition(acquisition: Acquisition) -> None:
    """Yanlış açılmış edinim partisini yumuşak siler; kullanılmışsa reddeder.

    Her nüsha bir edinimden gelir; partiyi silmek nüshaları görünmez bir partiye
    bağlar (`PROTECT` yumuşak silmede tetiklenmez — CLAUDE.md §3). Bağış ön
    kaydının kataloglama sırasında açtığı parti de silinemez: kaydın hangi
    kararla kütüphaneye girdiği bilgisi kopar.
    """
    if acquisition.copies.exists():
        raise ValidationError(
            {
                "acquisition": (
                    "Bu edinime bağlı nüshalar var; edinim silinemez. Önce nüshaları silin "
                    "ya da bilgileri düzeltin."
                )
            }
        )
    if acquisition.donation_intakes.exists():
        raise ValidationError(
            {"acquisition": "Bu edinim bir bağış ön kaydının kararından doğdu; silinemez."}
        )
    acquisition.delete()
