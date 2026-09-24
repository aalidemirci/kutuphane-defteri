"""Katalogun sabit kümeleri modelin ve sözlüğün TEK KAYNAĞIYLA birebir (tasarım §5.3).

Katalog `apps.*` içe aktaramadığı için kaynak türü ve nüsha durumu adlarını
kendisi taşır; bu testler kopyanın kaynaktan ayrılmasını engeller. Kaynak:
`apps.kutuphane.models` seçenekleri (onlar da `docs/sozluk.md` ile koruma
testindedir) ve Türkçe sıralama anahtarı.
"""

from __future__ import annotations

from apps.kutuphane import keys
from apps.kutuphane.katalog_gorunumleri import GORUNUR_DURUMLAR
from apps.kutuphane.models import DIGITAL_RESOURCE_TYPES, CopyStatus, ResourceType
from katalog import sabitler


def test_kaynak_turu_adlari_modelle_birebir() -> None:
    assert dict(sabitler.TUR_ADLARI) == {tur.value: str(tur.label) for tur in ResourceType}
    assert set(sabitler.TURLER.values()) == set(ResourceType.values)
    assert len(sabitler.TURLER) == len(set(sabitler.TURLER.values()))
    assert all(kisa.isascii() and kisa == kisa.lower() for kisa in sabitler.TURLER)


def test_dijital_turler_modelle_ayni() -> None:
    assert sabitler.DIJITAL_TURLER == set(DIGITAL_RESOURCE_TYPES)


def test_gorunen_durum_adlari_modelle_ve_gorunum_beyaz_listesiyle_birebir() -> None:
    assert set(sabitler.DURUM_ADLARI) == set(GORUNUR_DURUMLAR)
    for kod, ad in sabitler.DURUM_ADLARI.items():
        assert ad == CopyStatus(kod).label


def test_odunc_verilmez_metni_nushanin_gerekcesiyle_ayni() -> None:
    """Sözlük: "Ödünç verilmez — kütüphanede okunur" (Copy.not_loanable_reason)."""
    from apps.kutuphane.models import Copy, Work

    nusha = Copy(is_reference=True, work=Work(resource_type=ResourceType.BOOK))
    assert nusha.not_loanable_reason == sabitler.ODUNC_VERILMEZ + "."


def test_harfler_turk_alfabesi_sirasinda_ve_her_biri_ayri_anahtarda() -> None:
    anahtarlar = [keys.tr_collation_key(h) for h in sabitler.HARFLER]

    assert all(len(a) == 1 for a in anahtarlar)
    assert anahtarlar == sorted(anahtarlar)
    assert len(set(anahtarlar)) == len(sabitler.HARFLER)
    # Harf dışı başlangıç ("1984", "«Ağaç»") bütün harflerden önce gelir: "Diğer".
    assert keys.tr_collation_key("1")[0] < min(anahtarlar)


def test_ana_siniflar_on_hanedir_ve_adlari_hanesiyle_baslar() -> None:
    assert list(sabitler.ANA_SINIFLAR) == [str(i) for i in range(10)]
    for hane, ad in sabitler.ANA_SINIFLAR.items():
        assert ad.startswith(f"{hane}00 ")
