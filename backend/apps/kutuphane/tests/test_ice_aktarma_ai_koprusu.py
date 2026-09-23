"""Yapay zekâ köprüsü — JSON şeması v1, komut metni ve arayüz uyarıları (§8.2).

Köprü bir METİN köprüsüdür: program hiçbir servise bağlanmaz (o kural
`test_ice_aktarma_dis_istek.py`'de kilitlenir), burada komutun ve şemanın
sözleşmesi sabitlenir.

Komutun en kırılgan yeri **ne İSTEMEDİĞİDİR**: demirbaş no, edinim ve bağışçı
bilgisi komuta girmez (§8.2). Bir gün alan listesine sessizce eklenirse okulun
kitap listesiyle birlikte kayıt numaraları da dış hizmete çıkar.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.kutuphane import ai_bridge
from apps.kutuphane.import_schema import COLUMNS_BY_KEY, MAX_COPIES_PER_ROW
from apps.kutuphane.models import CatalogImportSource, ClassificationSource, Copy, Work
from apps.kutuphane.services import import_service as ia


def _payload(**alanlar: Any) -> dict[str, Any]:
    oge = {"title": "Huzur", "authors": "Ahmet Hamdi Tanpınar", **alanlar}
    return {"schema_version": ai_bridge.SCHEMA_VERSION, "items": [oge]}


def _oge(**alanlar: Any) -> dict[str, Any]:
    return ai_bridge.validate_payload(_payload(**alanlar))[0]


# ---------------------------------------------------------------------------
# Komut metni
# ---------------------------------------------------------------------------
class TestKomutMetni:
    def test_sema_surumu_ve_alanlar_komutta_gecer(self) -> None:
        komut = ai_bridge.AI_PROMPT

        assert f'"{ai_bridge.SCHEMA_VERSION}"' in komut
        for anahtar in ai_bridge.ITEM_KEYS:
            assert anahtar in komut, anahtar

    def test_kunye_disi_alanlar_komutta_ISTENMEZ(self) -> None:
        """Demirbaş no, edinim ve bağışçı komuta girmez (§8.2)."""
        for anahtar in ai_bridge.IGNORED_KEYS:
            assert anahtar not in ai_bridge.AI_PROMPT, anahtar

    def test_siniflama_kodu_genellestirilmistir(self) -> None:
        """OYS komutu "Dewey kodunu araştır" diyordu; ifade genelleştirildi (§8.2)."""
        komut = ai_bridge.AI_PROMPT

        assert "sınıflama kodu" in komut.lower()
        assert "ESTIMATED" in komut
        # OYS komutu aracı bu adreslere yönlendiriyordu; TO-KAT kazımayı tümden
        # yasaklar (§8.5) ve programın komutu oraya yönlendiremez.
        assert "TO-KAT" not in komut
        assert "Milli Kütüphane" not in komut

    def test_sutun_basliklari_sozlukten_gelir(self) -> None:
        """Komut sözlüğü tekrarlamaz: başlık değişirse komut da değişir (tek kaynak)."""
        assert COLUMNS_BY_KEY["shelf_location"].header in ai_bridge.AI_PROMPT
        assert str(MAX_COPIES_PER_ROW) in ai_bridge.AI_PROMPT

    def test_kisisel_veri_uyarisi_komutta_da_vardir(self) -> None:
        assert "kişisel veri" in ai_bridge.AI_PROMPT

    def test_dort_arayuz_uyarisi_sirayla(self) -> None:
        """§8.2'nin dört maddesi: kişisel veri · taşıyan kullanıcıdır · bağlanmaz · Yönerge."""
        notlar = ai_bridge.UI_NOTES

        assert len(notlar) == 4
        assert "kişisel veri" in notlar[0]
        assert "kullanıcı" in notlar[1]
        assert "bağlanmaz" in notlar[2]
        assert "11/23" in notlar[3] and "Excel" in notlar[3]

    def test_uyarilarda_ic_kod_gecmez(self) -> None:
        """Kullanıcı metninde iç kodlar (U13, §8.2, T-…) geçmez (docs/sozluk.md §2)."""
        metin = " ".join(ai_bridge.UI_NOTES)

        for kod in ("U13", "§8.2", "F3", "SU-24"):
            assert kod not in metin


# ---------------------------------------------------------------------------
# Şema doğrulaması
# ---------------------------------------------------------------------------
class TestSemaDogrulamasi:
    def test_gecerli_govde_temiz_oge_dondurur(self) -> None:
        oge = _oge(copies=3, isbn="978-605-999-900-1", shelf_location="Edebiyat")

        assert oge["title"] == "Huzur"
        assert oge["copies"] == 3
        assert oge["resource_type"] == "BOOK"
        assert oge["classification_source"] == "MANUAL"
        assert oge["issues"] == []

    def test_sema_surumu_tutmazsa_hata(self) -> None:
        with pytest.raises(ai_bridge.AiBridgeError) as hata:
            ai_bridge.validate_payload({"schema_version": "v2", "items": [{"title": "Huzur"}]})

        assert "Şema sürümü" in hata.value.errors[0]

    def test_bos_liste_hata(self) -> None:
        with pytest.raises(ai_bridge.AiBridgeError):
            ai_bridge.validate_payload({"schema_version": "v1", "items": []})

    def test_nesne_olmayan_govde_hata(self) -> None:
        with pytest.raises(ai_bridge.AiBridgeError):
            ai_bridge.validate_payload([{"title": "Huzur"}])

    def test_taninmayan_kaynak_turu_kitap_sayilir_ve_soylenir(self) -> None:
        oge = _oge(resource_type="KASET")

        assert oge["resource_type"] == "BOOK"
        assert any("tanınmadı" in ileti for ileti in oge["issues"])

    def test_taninmayan_siniflama_kaynagi_elle_girildi_sayilir(self) -> None:
        assert _oge(classification_source="WIKIPEDIA")["classification_source"] == "MANUAL"

    def test_nusha_sinirini_asan_oge_gecersiz_sayilir(self) -> None:
        oge = _oge(copies=MAX_COPIES_PER_ROW + 1)

        assert oge["copies"] == 0
        assert any(str(MAX_COPIES_PER_ROW) in ileti for ileti in oge["issues"])

    def test_kunye_disi_alanlar_yok_sayilir_ve_soylenir(self) -> None:
        oge = _oge(old_register_no="1452", donor_name="Selma Yücel")

        assert "old_register_no" not in oge
        assert len(oge["issues"]) == 2
        assert all("yok sayıldı" in ileti for ileti in oge["issues"])

    def test_duzeltmeler_ve_sorunlar_korunur(self) -> None:
        oge = _oge(
            corrections=[{"field": "title", "original": "Huzurr", "corrected": "Huzur"}],
            issues=["Yayınevi belirsiz."],
        )

        assert oge["corrections"][0]["corrected"] == "Huzur"
        assert oge["issues"] == ["Yayınevi belirsiz."]

    def test_oge_nesne_degilse_hata(self) -> None:
        with pytest.raises(ai_bridge.AiBridgeError):
            ai_bridge.validate_payload({"schema_version": "v1", "items": ["Huzur"]})


# ---------------------------------------------------------------------------
# Köprü satırları içe aktarma hattına aynı biçimde girer
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestKopruIceAktarma:
    def test_kopru_satirlari_uygulanir(self) -> None:
        parsed = ia.rows_from_payload(_payload(copies=2, shelf_location=""))

        rapor = ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        assert rapor.stats["copies_created"] == 2
        assert Work.objects.get().title == "Huzur"

    def test_tahmini_kod_katalogda_isaretli_kalir(self) -> None:
        parsed = ia.rows_from_payload(
            _payload(classification_code="894.353", classification_source="ESTIMATED")
        )

        ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        eser = Work.objects.get()
        assert eser.classification_source == ClassificationSource.ESTIMATED
        assert eser.classification_code == "894.353"

    def test_ders_kitabi_konusu_danisma_varsayilanini_acar(self) -> None:
        parsed = ia.rows_from_payload(_payload(subjects="Ders kitabı"))

        ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        assert Copy.objects.get().is_reference is True

    def test_gecersiz_nusha_sayisi_satiri_dusurur(self) -> None:
        parsed = ia.rows_from_payload(_payload(copies=MAX_COPIES_PER_ROW + 1))

        rapor = ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        assert rapor.stats["skipped_rows"] == 1
        assert Work.objects.count() == 0

    def test_dort_haneli_olmayan_yil_bos_kalir(self) -> None:
        parsed = ia.rows_from_payload(_payload(publish_year=99))

        ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        assert Work.objects.get().publish_year is None

    def test_gecerli_yil_kunyeye_gecer(self) -> None:
        parsed = ia.rows_from_payload(_payload(publish_year=2020))

        ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        assert Work.objects.get().publish_year == 2020

    def test_kunye_disi_alan_nushaya_yazilmaz(self) -> None:
        parsed = ia.rows_from_payload(_payload(old_register_no="1452"))

        ia.apply_import(parsed, payload_sha256="abc", source=CatalogImportSource.AI_JSON)

        assert Copy.objects.get().old_register_no == ""

    def test_ayni_govdenin_ozeti_anahtar_sirasindan_etkilenmez(self) -> None:
        birinci = ia.content_hash(
            ia.rows_from_payload({"schema_version": "v1", "items": [{"title": "Huzur"}]}).rows
        )
        ikinci = ia.content_hash(
            ia.rows_from_payload({"items": [{"title": "Huzur"}], "schema_version": "v1"}).rows
        )

        assert birinci == ikinci
