"""Dolaşım metinleri ↔ kılavuz, sözlük ve mevzuat (F6; sözlük BAĞLAYICIDIR — CLAUDE.md §2).

Kılavuz (`frontend/src/modules/kilavuz/KilavuzPage.tsx`) ve sözlük (`docs/sozluk.md`)
masada görülen iletileri BİREBİR yazar. Ön yüz testi (`KilavuzPage.test.tsx`) sunucu
iletilerini okuyamadığı için onları kopya olarak tutar; bu test kopyaların sunucudaki
sabitlerle aynı kaldığını denetler. Sunucu bir iletiyi değiştirirse kılavuz ve sözlük
de değişmek zorunda kalır.

Kılavuzdaki mevzuat alıntıları da burada `docs/mevzuat/` metniyle karşılaştırılır
(CLAUDE.md §2-13: atıf depodaki metinden doğrulanır). Alıntı ilgili MADDENİN içinde
aranır (`<a id="madde-N">` çapasından sonrakine kadar): yanlış madde numarası da
yakalanır. Md. 18/1'in orta cümleleri Bakanlığın sistemini andığı için kılavuzda
"…" ile atlanır; her parça ayrı ayrı aranır.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.db import models

from apps.kutuphane import barcode, dolasim_belgeleri
from apps.kutuphane.labels import card
from apps.kutuphane.models import (
    MANUAL_TERMINATION_REASONS,
    OVERRIDE_NOTE_HELP,
    CardlessReason,
    Copy,
    CopyStatus,
    MembershipStatus,
    OverrideReason,
    TerminationReason,
)
from apps.kutuphane.selectors_dolasim import REVOKED_CARD_MESSAGE
from apps.kutuphane.services import circulation, label_queue, masa

_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_SOZLUK = Path("docs") / "sozluk.md"
_YONETMELIK = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi.md"
_KVKK = Path("docs") / "mevzuat" / "6698-kvkk.md"


def _oku(yol: Path) -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _tek_bosluk(metin: str) -> str:
    return re.sub(r"\s+", " ", metin)


def _kilavuz() -> str:
    """Kılavuz kaynağının düz metni: yorumlar atılır, JSX boşluk parçaları ve varlıklar çözülür.

    Yorumlar kuralı ANLATIR (ör. `"Md. 18 gereği" denmez`); denetim yalnız kullanıcıya
    görünen metne bakar. Satır başı `//` yorumları ve `/* … */` blokları (JSX'teki
    `{/* … */}` dahil) atılır; metin içindeki "http://" satır başında olmadığı için kalır.
    """
    kaynak = _oku(_KILAVUZ)
    kaynak = re.sub(r"/\*.*?\*/", " ", kaynak, flags=re.DOTALL)
    kaynak = re.sub(r"^\s*//.*$", " ", kaynak, flags=re.MULTILINE)
    return _tek_bosluk(kaynak.replace("&apos;", "'").replace('{" "}', " "))


def _sozluk() -> str:
    return _tek_bosluk(_oku(_SOZLUK))


def _madde(yol: Path, numara: int) -> str:
    """Mevzuat dosyasından tek maddenin metni (çapadan sonraki çapaya kadar)."""
    metin = _oku(yol)
    cikis = re.search(
        rf'<a id="madde-{numara}"></a>(.*?)(?=<a id="madde-|\Z)', metin, flags=re.DOTALL
    )
    assert cikis is not None, f"{yol}: madde {numara} çapası yok"
    return _tek_bosluk(cikis.group(1))


# ---------------------------------------------------------------------------
# Kılavuz ↔ sunucu iletileri
# ---------------------------------------------------------------------------
_KILAVUZ_ILETILERI: tuple[str, ...] = (
    masa.CHECKOUT_DONE_MESSAGE,
    masa.RETURN_DONE_MESSAGE,
    masa.CARD_UNKNOWN_MESSAGE,
    masa.CARD_INVALID_MESSAGE,
    REVOKED_CARD_MESSAGE,
    barcode.ISBN_SCAN_MESSAGE,
    label_queue.STAFF_REFER,
    circulation.COPY_STATE_MESSAGES[CopyStatus.AVAILABLE],
    circulation.COPY_STATE_MESSAGES[CopyStatus.LOST],
    circulation.COPY_STATE_MESSAGES[CopyStatus.IN_REPAIR],
    circulation.COPY_STATE_MESSAGES[CopyStatus.DELIVERED],
    circulation.MEMBERSHIP_ENDED_MESSAGE,
    circulation.MEMBER_LEFT_MESSAGE,
    circulation.OVERDUE_STAFF_MESSAGE,
    circulation.OVERDUE_ADMIN_MESSAGE,
    circulation.COPY_WITH_OTHER_MEMBER_MESSAGE,
    circulation.COPY_WITH_THIS_MEMBER_MESSAGE,
    dolasim_belgeleri.LISTE_DIPNOTU,
    dolasim_belgeleri.SLIP_OUTSIDE_TITLE,
    dolasim_belgeleri.SLIP_DELIVERY_STUDENT,
    circulation.LAST_LOAN_DATE_STAFF_MESSAGE,
    card.STAFF_POSITION_NOTE,
)


@pytest.mark.parametrize("ileti", _KILAVUZ_ILETILERI)
def test_kilavuz_sunucu_iletisini_tirnak_icinde_birebir_yazar(ileti: str) -> None:
    assert f"“{ileti}" in _kilavuz(), ileti


def test_kilavuz_odunc_verilmez_gerekcesini_nushanin_ozelliginden_yazar() -> None:
    """Danışma kaynağının gerekçesi `Copy.not_loanable_reason`'dan (kaydedilmemiş nüsha)."""
    gerekce = Copy(is_reference=True).not_loanable_reason
    assert f"“{gerekce}”" in _kilavuz()


def test_kilavuz_istisna_ve_kartsiz_gerekcelerini_sayar() -> None:
    metin = _kilavuz()
    for _kod, etiket in (*OverrideReason.choices, *CardlessReason.choices):
        assert f"“{etiket}”" in metin, etiket
    # Yardım metni kılavuzda cümle içinde küçük harfle başlar.
    yardim = OVERRIDE_NOTE_HELP[0].lower() + OVERRIDE_NOTE_HELP[1:]
    assert yardim in metin


def test_kilavuz_elle_sonlandirma_nedenlerini_sayar() -> None:
    metin = _kilavuz()
    for kod in MANUAL_TERMINATION_REASONS:
        assert f"“{TerminationReason(kod).label}”" in metin, kod


def test_kilavuz_kartin_konum_notunu_kartla_ayni_anlatir() -> None:
    """Kartın altındaki not (labels/card.POSITION_NOTE) kılavuzda aynı sözlerle anlatılır.

    Kılavuz notun ikinci yarısını (Bakanlığın sistemini adıyla anan kısmı) yazmaz;
    ortak parça birebirdir.
    """
    ortak = "öngörülen kullanıcı kartının okulca düzenlenen yerel karşılığı"
    assert ortak in card.POSITION_NOTE
    assert f"20. maddesinde {ortak}" in _kilavuz()


def test_kilavuz_kart_kilidinin_esigini_dogru_yazar() -> None:
    """Görevli kipinde art arda geçersiz kart sınırı (GA-7) kılavuzda sözle yazılır."""
    sayilar = {3: "üç", 4: "dört", 5: "beş", 6: "altı"}
    assert f"Art arda {sayilar[masa.GECERSIZ_KART_SINIRI]} geçersiz kart" in _kilavuz()
    # Kural 2 (F6 düzeltme turu): pencere içinde tanınmayan/iptal edilmiş kart.
    dakika = {10: "on", 15: "on beş", 30: "otuz"}[masa.TANINMAYAN_KART_PENCERESI_SN // 60]
    sayi = sayilar[masa.TANINMAYAN_KART_SINIRI]
    assert f"{dakika} dakika içinde {sayi} tanınmayan veya iptal edilmiş kart" in _kilavuz()


# ---------------------------------------------------------------------------
# Kılavuz ↔ mevzuat
# ---------------------------------------------------------------------------
_ALINTILAR: tuple[tuple[Path, int, str], ...] = (
    (
        _YONETMELIK,
        18,
        "Bir kitabı ödünç alma süresi on beş gündür. … Öğrencilere bir defasında en fazla "
        "üç, öğretmenlere en fazla beş kitap ödünç verilebilir.",
    ),
    (_YONETMELIK, 23, "a) Öğrenci, öğretmen kartını kütüphane görevlisine verir."),
    (_YONETMELIK, 16, "üye olmak koşuluyla"),
    (_YONETMELIK, 17, "üye olmak isteyen"),
    (_KVKK, 10, "elde edilmesi sırasında"),
    (
        _KVKK,
        12,
        "Veri sorumlusu; a) Kişisel verilerin hukuka aykırı olarak işlenmesini önlemek, "
        "b) Kişisel verilere hukuka aykırı olarak erişilmesini önlemek, c) Kişisel "
        "verilerin muhafazasını sağlamak, amacıyla uygun güvenlik düzeyini temin etmeye "
        "yönelik gerekli her türlü teknik ve idari tedbirleri almak zorundadır.",
    ),
)


@pytest.mark.parametrize(("yol", "numara", "alinti"), _ALINTILAR)
def test_kilavuz_alintisi_mevzuat_metniyle_birebir(yol: Path, numara: int, alinti: str) -> None:
    madde = _madde(yol, numara)
    for parca in alinti.split(" … "):
        assert parca in madde, f"{yol.name} md. {numara}: {parca}"
    assert f"“{alinti}”" in _kilavuz(), alinti


def test_kilavuz_otomasyon_sistemini_ve_md18_geregini_anmaz() -> None:
    """Konum dili (CLAUDE.md §2-13) ve iade tarihi kuralı (§2-6) kaynak metinde de tutar."""
    metin = _kilavuz()
    assert not re.search(r"Md\.? ?18 gereği", metin, flags=re.IGNORECASE)
    # Yönetmelik alıntıları "otomasyon sistemi"ni anan cümleleri almaz (Md. 18/1'de "…").
    assert "otomasyon sistemi" not in metin.lower()


# ---------------------------------------------------------------------------
# Sözlük ↔ sunucu iletileri ve kapalı listeler
# ---------------------------------------------------------------------------
_SOZLUK_ILETILERI: tuple[str, ...] = (
    masa.CHECKOUT_DONE_MESSAGE,
    masa.RETURN_DONE_MESSAGE,
    masa.ON_LOAN_STATUS_MESSAGE,
    masa.AVAILABLE_STATUS_MESSAGE,
    masa.MEMBER_READY_MESSAGE,
    masa.CARD_UNKNOWN_MESSAGE,
    masa.CARD_INVALID_MESSAGE,
    masa.SCAN_MEMBER_CARD_MESSAGE,
    masa.SCAN_UNKNOWN_MESSAGE,
    masa.SCAN_NO_COPY_MESSAGE,
    masa.KART_KILIDI_ACILDI_MESSAGE,
    REVOKED_CARD_MESSAGE,
    barcode.ISBN_SCAN_MESSAGE,
    label_queue.STAFF_REFER,
    circulation.COPY_STATE_MESSAGES[CopyStatus.AVAILABLE],
    circulation.COPY_STATE_MESSAGES[CopyStatus.LOST],
    circulation.COPY_STATE_MESSAGES[CopyStatus.IN_REPAIR],
    circulation.COPY_STATE_MESSAGES[CopyStatus.DELIVERED],
    circulation.MEMBERSHIP_ENDED_MESSAGE,
    circulation.MEMBER_LEFT_MESSAGE,
    circulation.STAFF_LOANS_OFF_MESSAGE,
    circulation.OVERDUE_STAFF_MESSAGE,
    circulation.OVERDUE_ADMIN_MESSAGE,
    OVERRIDE_NOTE_HELP,
    circulation.LAST_LOAN_DATE_STAFF_MESSAGE,
    card.STAFF_POSITION_NOTE,
    dolasim_belgeleri.SLIP_DELIVERY_STUDENT,
    dolasim_belgeleri.SLIP_DELIVERY_STAFF,
)


@pytest.mark.parametrize("ileti", _SOZLUK_ILETILERI)
def test_sozluk_masa_iletisini_birebir_yazar(ileti: str) -> None:
    assert f'"{ileti}' in _sozluk(), ileti


def test_sozluk_kart_kilidi_iletisinin_ilk_cumlesini_yazar() -> None:
    ilk = masa.KART_KILIDI_MESSAGE.split(". ")[0] + "."
    assert f'"{ilk} …"' in _sozluk()
    pencere = masa.KART_KILIDI_PENCERE_MESSAGE.split(". ")[0] + "."
    assert f'"{pencere} …"' in _sozluk()


def _kalin_tirnakli(etiketler: list[str]) -> str:
    """Sözlük §4.10'daki yazım: kalın, tırnaklı, " · " ile ayrılmış, sırasıyla."""
    return " · ".join(f'**"{etiket}"**' for etiket in etiketler)


@pytest.mark.parametrize("secenekler", [OverrideReason, CardlessReason])
def test_sozluk_gerekce_listeleri_kodun_secenekleriyle_birebir(
    secenekler: type[models.TextChoices],
) -> None:
    etiketler = [etiket for _kod, etiket in secenekler.choices]
    assert _kalin_tirnakli(etiketler) in _sozluk()


def test_sozluk_sonlandirma_nedenleri_ve_durumlari_kodla_birebir() -> None:
    metin = _sozluk()
    elle = [TerminationReason(kod).label for kod in MANUAL_TERMINATION_REASONS]
    assert "elle " + " · ".join(f"**{e}**" for e in elle) in metin
    for _kod, etiket in TerminationReason.choices:
        assert f"**{etiket}**" in metin, etiket
    assert f"**{MembershipStatus.ACTIVE.label}**" in metin
    assert f"**{MembershipStatus.TERMINATED.label} · gg.aa.yyyy**" in metin


def test_sozluk_pusula_ve_masa_karti_basliklarini_yazar() -> None:
    metin = _sozluk()
    for baslik in (
        dolasim_belgeleri.SLIP_OUTSIDE_TITLE,
        dolasim_belgeleri.SLIP_TITLE,
        dolasim_belgeleri.SLIP_ITEMS_TITLE,
    ):
        assert f'**"{baslik}"**' in metin, baslik
    assert f'"{dolasim_belgeleri.LISTE_DIPNOTU}"' in metin
