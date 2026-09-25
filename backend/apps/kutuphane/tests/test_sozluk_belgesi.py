"""docs/sozluk.md ↔ kod eşleşmesi (sözlük BAĞLAYICIDIR — CLAUDE.md §2).

Sözlük "tek kaynak"tır: Ağ Kataloğu metinleri (F5), tutanak metinleri (F8-F9)
ve masa ekranı (F6) hangi sözcüğün kullanılacağını oradan okur. Kod bir etiket
ekleyip sözlük eskidiğinde bu işlev sessizce kırılır — F2, `CopyStatus`'a dört
terminal hâl getirdiğinde tam olarak bu oldu.

Test satırı ÜRETMEZ, KARŞILAŞTIRIR: sözlük metni insan için yazılır (not
sütunu, vurgular), üretilmiş bir liste onu okunmaz kılardı.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.db import models

from apps.kutuphane import views_teslim
from apps.kutuphane.models import (
    CaseResolution,
    CaseType,
    CopyStatus,
    DeliveryStatus,
    LabelOrder,
    LabelPrintBatchStatus,
    LabelPrintKind,
    ReservedBarcodeState,
)
from apps.kutuphane.services import deliveries, loss_damage
from apps.kutuphane.services.barcode_reservations import NEW_NUMBER_HINT

_BELGE = Path("docs") / "sozluk.md"
#: Sözlük satırının etiketleri: kalın yazılır ve " · " ile ayrılır.
_ETIKET = re.compile(r"\*\*(.+?)\*\*")


def _belge_metni() -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        yol = kok / _BELGE
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    pytest.fail(f"{_BELGE} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _satir(baslangic: str) -> str:
    for ham in _belge_metni().splitlines():
        if ham.startswith(baslangic):
            return ham
    pytest.fail(f"Sözlükte “{baslangic}…” satırı yok.")


def test_nusha_durumlari_satiri_copystatus_ile_birebir() -> None:
    """Sözlüğün saydığı etiketler `CopyStatus.choices` etiketleridir (sıra dahil)."""
    hucreler = _satir("| Nüsha durumları").split("|")
    etiketler = _ETIKET.findall(hucreler[2])
    assert etiketler == [etiket for _kod, etiket in CopyStatus.choices]


def test_durum_olmayan_ifadeler_not_sutununda_ayrilir() -> None:
    """ "Ödünç verilmez — kütüphanede okunur" bir durum değil, `is_reference` türetimidir."""
    satir = _satir("| Nüsha durumları")
    hucreler = satir.split("|")
    assert "Ödünç verilmez" not in hucreler[2]
    assert "is_reference" in hucreler[4]


# ---------------------------------------------------------------------------
# Etiketler (F4): sözlüğün saydığı seçenek adları kodun seçenekleriyle birebir
# ---------------------------------------------------------------------------
def _kalin_dizi(etiketler: list[str]) -> str:
    """Sözlükteki yazım: kalın etiketler, sırasıyla, " · " ile ayrılır."""
    return " · ".join(f"**{etiket}**" for etiket in etiketler)


@pytest.mark.parametrize(
    ("baslangic", "secenekler"),
    [
        ("| Basım kaydı", LabelPrintBatchStatus),
        ("| Basım sırası", LabelOrder),
        ("| Boş barkod aralığı", ReservedBarcodeState),
    ],
)
def test_etiket_satirlari_kodun_secenekleriyle_birebir(
    baslangic: str, secenekler: type[models.TextChoices]
) -> None:
    """Parti durumları, basım sırası ve numara durumları sözlükte SIRASIYLA ve eksiksiz geçer.

    Kılavuz ve ekran bu adları kullanır; kod bir seçenek ekler ya da adını
    değiştirirse sözlük satırı da değişmek zorunda kalır.
    """
    hucre = _satir(baslangic).split("|")[2]
    assert _kalin_dizi([etiket for _kod, etiket in secenekler.choices]) in hucre


def test_etiket_turleri_satiri_parti_iceriklerini_sayar() -> None:
    """`LabelPrintKind` etiketleri (sırt · barkod · ikisi birden) sözlükte kalın geçer."""
    hucre = _satir("| Etiket türleri").split("|")[2]
    for _kod, etiket in LabelPrintKind.choices:
        # Sözlükte kavram adı cümle içinde küçük harfle başlar ("**sırt etiketi**").
        assert f"**{etiket[0].lower()}{etiket[1:]}**" in hucre, etiket


def test_hizli_kayit_etiket_ipucu_sozlukte_birebir() -> None:
    """Etiket reddedilince sunucunun verdiği ipucu sözlük §4.7'de aynı metinle yazılıdır."""
    metin = re.sub(r"\s+", " ", _belge_metni())
    assert NEW_NUMBER_HINT in metin


# ---------------------------------------------------------------------------
# Teslim, kayıp/hasar ve ilişik (F7): durum adları kodla birebir; yasak sözcükler
# "Kullanılmaz" sütununda durur (kılavuz ve ekranlar bu sütuna bakar)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("baslangic", "secenekler"),
    [
        ("| Teslim durumu", DeliveryStatus),
        ("| Çözüm durumları", CaseResolution),
        ("| Dosya türü", CaseType),
    ],
)
def test_teslim_ve_kayip_satirlari_kodun_secenekleriyle_birebir(
    baslangic: str, secenekler: type[models.TextChoices]
) -> None:
    """Teslim durumları, çözüm durumları ve dosya türleri sözlükte SIRASIYLA ve eksiksiz."""
    hucre = _satir(baslangic).split("|")[2]
    assert _kalin_dizi([etiket for _kod, etiket in secenekler.choices]) in hucre


def _depo_kok() -> Path:
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        if (kok / "frontend" / "src").is_dir():
            return kok
    pytest.fail("frontend/src bulunamadı (depo kökü ya da /repo).")


def _yorumsuz(yol: Path) -> str:
    """Kaynağın yorumları çıkarılmış metni (kullanıcıya görünen metin + kod)."""
    metin = re.sub(r"/\*.*?\*/", "", yol.read_text(encoding="utf-8"), flags=re.S)
    return "\n".join(s for s in metin.splitlines() if not s.lstrip().startswith("//"))


def test_acik_is_yerine_yukumluluk_kullanici_metnine_girmez() -> None:
    """Sözlük "açık iş" der; "yükümlülük" F7 ekranlarında ve kılavuzda kullanıcıya görünmez.

    "Yükümlülük" borç/tahsilat çağrışımı taşır (sözlük İlişik satırı, "Kullanılmaz"
    sütunu); kod yorumlarında (kayıt defteri adı) serbesttir.
    """
    kok = _depo_kok() / "frontend" / "src" / "modules"
    taranan = 0
    for modul in ("kayip", "teslim", "yil", "kilavuz", "dolasim", "kip"):
        for yol in sorted((kok / modul).glob("*.tsx")):
            if ".test." in yol.name:
                continue
            taranan += 1
            assert "yükümlülü" not in _yorumsuz(yol).casefold(), yol.name
    assert taranan > 10


@pytest.mark.parametrize(
    ("baslangic", "yasaklar"),
    [
        ("| `Delivery`", ("emanet", "zimmet")),
        ("| İlişik", ("borç", "ilişik kesme", "yükümlülük")),
        ("| `LossDamageCase`", ("zayi", "telef", "borç", "ceza", "tahsil edildi")),
        ("| Çözüm durumları", ("borç", "ceza", "zayi")),
    ],
)
def test_f7_yasak_sozcukler_kullanilmaz_sutununda(
    baslangic: str, yasaklar: tuple[str, ...]
) -> None:
    """Sözlük yasak sözcüğü "Kullanılmaz" sütununda tutar, "Kullanılır"da değil."""
    hucreler = _satir(baslangic).split("|")
    for yasak in yasaklar:
        assert yasak in hucreler[3], f"{baslangic}: {yasak}"
        assert yasak not in hucreler[2].casefold(), f"{baslangic}: {yasak}"


def test_ilisik_satiri_on_kosul_kuralini_soyler() -> None:
    """ "İlişiği yoktur" belgesi karne ya da diploma ön koşulu diye SUNULMAZ (tasarım §8.3)."""
    not_sutunu = _satir("| İlişik").split("|")[4]
    assert "Karne ya da diplomanın ön koşulu diye SUNULMAZ" in not_sutunu


@pytest.mark.parametrize(
    "ileti",
    [
        deliveries.DELIVERABLE_MESSAGE,
        deliveries.TAKE_BACK_DONE_MESSAGE,
        deliveries.NOT_DELIVERED_MESSAGE.split("{")[0],
        deliveries.NOT_DELIVERED_ON_LOAN_MESSAGE,
        deliveries.SECTION_OLD_YEAR_MESSAGE,
        deliveries.TEACHER_ONLY_MESSAGE,
        deliveries.SECTION_DELETE_MESSAGE.split("}")[1],
        deliveries.SECTION_DELETE_CASE_MESSAGE.split("}")[1],
        deliveries.MERGE_TARGET_NOT_TEACHER_MESSAGE.split("}")[1],
        deliveries.DELIVERY_HISTORY_DELETE_MESSAGE,
        views_teslim.REPAIR_SENT_MESSAGE,
        views_teslim.REPAIR_RETURNED_MESSAGE,
        loss_damage.REPAIR_NOT_AVAILABLE_MESSAGE.split("{")[0],
        loss_damage.LOST_IN_REPAIR_MESSAGE,
        loss_damage.DAMAGE_ON_LOAN_MESSAGE,
        loss_damage.DAMAGE_DELIVERED_MESSAGE,
    ],
)
def test_teslim_dosya_ve_onarim_iletileri_sozlukte_birebir(ileti: str) -> None:
    """Sunucunun teslim, dosya ve onarım iletileri sözlük §4.12'deki satırda aynı metinle
    (yer tutucular "(…)" ve "N" diye yazılır; sabit parçası aranır)."""
    hucre = _satir("| Teslim, dosya ve onarım iletileri").split("|")[2]
    assert ileti.strip() in hucre, ileti
