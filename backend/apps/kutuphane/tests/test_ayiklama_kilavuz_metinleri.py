"""Ayıklama, nadir eser ve yıl sonu raporu metinleri ↔ kılavuz ve mevzuat (F8).

Kılavuzun (`frontend/src/modules/kilavuz/KilavuzPage.tsx`) "Ayıklama ve Nadir Eserler" ve
"Yıl Sonu Raporu" bölümleri sunucunun seçenek adlarını, belge adlarını ve iletilerini
birebir yazar. Ön yüz testi (`KilavuzPage.test.tsx`) ön yüzün sabitlerini sınar; bu test
sunucu tarafını: kod bir etiketi ya da belge adını değiştirirse kılavuz da değişmek
zorunda kalır.

Mevzuat (CLAUDE.md §2-13): kılavuzdaki alıntılar ilgili MADDENİN (Uygulama Kılavuzunda
2.4 bölümünün) içinde aranır. Kılavuz Taşınır Mal Yönetmeliği yollarını SADE DİLLE anlatır
ve fıkra numarasıyla atıf yapar; o atıfların her biri için sade anlatımın dayandığı ifade
atıf yapılan FIKRANIN metninde aranır — madde numarası uydurulmasın, fıkra kaymasın.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane import komisyon_belgeleri, yil_raporu_belgesi
from apps.kutuphane.models import (
    AnnualLibraryReview,
    CommissionDecisionType,
    CopyStatus,
    WeedingItemState,
    WeedingReason,
    WeedingTmyPath,
)

_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_YONETMELIK = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi.md"
_UYGULAMA_KILAVUZU = (
    Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md"
)
_TMY = Path("docs") / "mevzuat" / "tasinir-mal-yonetmeligi.md"


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
    """Kılavuzun kullanıcıya görünen düz metni (yaklaşık; yorumlar ve JSX etiketleri atılır)."""
    kaynak = _oku(_KILAVUZ)
    kaynak = re.sub(r"/\*.*?\*/", " ", kaynak, flags=re.DOTALL)
    kaynak = re.sub(r"^\s*//.*$", " ", kaynak, flags=re.MULTILINE)
    kaynak = kaynak.replace("&apos;", "'").replace('{" "}', " ")
    kaynak = re.sub(r"</?[A-Za-z][^<>]*>", "", kaynak)
    return _tek_bosluk(kaynak)


def _bolum(kimlik: str) -> str:
    """Kılavuzun tek bölümünün düz metni (`<Bolum id="…">` ile sonraki bölüm arası)."""
    kaynak = _oku(_KILAVUZ)
    cikis = re.search(rf'<Bolum id="{kimlik}">(.*?)</Bolum>', kaynak, flags=re.DOTALL)
    assert cikis is not None, f"kılavuzda {kimlik} bölümü yok"
    govde = cikis.group(1).replace("&apos;", "'").replace('{" "}', " ")
    govde = re.sub(r"\{/\*.*?\*/\}", " ", govde, flags=re.DOTALL)
    return _tek_bosluk(re.sub(r"</?[A-Za-z][^<>]*>", "", govde))


def _madde(yol: Path, numara: int) -> str:
    """Mevzuat dosyasından tek maddenin metni (çapadan sonraki çapaya kadar)."""
    metin = _oku(yol)
    cikis = re.search(
        rf'<a id="madde-{numara}"></a>(.*?)(?=<a id="madde-|\Z)', metin, flags=re.DOTALL
    )
    assert cikis is not None, f"{yol}: madde {numara} çapası yok"
    return _tek_bosluk(cikis.group(1))


def _fikra(yol: Path, madde: int, fikra: int) -> str:
    """Maddenin tek fıkrası: "(n) " ile "(n+1) " arası (son fıkrada madde sonuna dek)."""
    metin = _madde(yol, madde)
    cikis = re.search(rf"\({fikra}\) (.*?)(?= \({fikra + 1}\) |\Z)", metin)
    assert cikis is not None, f"{yol.name} md. {madde}/{fikra} yok"
    return cikis.group(1)


# ---------------------------------------------------------------------------
# Kılavuz ↔ kodun seçenek adları, belge adları ve iletileri
# ---------------------------------------------------------------------------
def test_kilavuz_gerekce_ve_yollari_kodun_etiketleriyle_yazar() -> None:
    """Gerekçeler (kalın), TMY yolları (tırnak içinde) ve iki terminal nüsha durumu."""
    metin = _bolum("ayiklama")
    for _kod, etiket in WeedingReason.choices:
        assert etiket in metin, etiket
    for _kod, etiket in WeedingTmyPath.choices:
        assert f"“{etiket}”" in metin, etiket
    for nusha_durumu in (CopyStatus.WITHDRAWN_WEEDED, CopyStatus.TRANSFERRED):
        assert f"“{nusha_durumu.label}”" in metin, nusha_durumu.label
    for kalem_durumu in (WeedingItemState.KEPT_BY_COMMISSION, WeedingItemState.NOT_APPROVED):
        assert f"“{kalem_durumu.label}”" in metin, kalem_durumu.label


def test_kilavuz_karar_turlerini_kodun_etiketleriyle_sayar() -> None:
    """Seçim ve Ayıklama Komisyonu alt bölümü üç karar türünü de adıyla anar (D7)."""
    metin = _bolum("ayiklama")
    for _kod, etiket in CommissionDecisionType.choices:
        assert etiket in metin, etiket


def test_kilavuz_belge_adlarini_ve_basilamama_gerekcesini_sunucudan_yazar() -> None:
    metin = _bolum("ayiklama")
    for belge in komisyon_belgeleri.AYIKLAMA_BELGELERI:
        assert belge.ad in metin, belge.ad
    assert komisyon_belgeleri.NADIR_ESER_ADI.casefold() in metin.casefold()
    assert f"“{komisyon_belgeleri.NEEDS_DECISION_MESSAGE}”" in metin
    assert yil_raporu_belgesi.BELGE_ADI in _bolum("yil-sonu-raporu")


def test_kilavuz_tespit_alaninin_uyarisini_modelle_ayni_yazar() -> None:
    """ "Tespit edilen hususlar"ın yardım metnindeki uyarı kılavuzda küçük harfle geçer."""
    yardim = str(AnnualLibraryReview._meta.get_field("findings").help_text)
    uyari = yardim.split(". ", 1)[1]
    assert uyari == "Kişi adı yazmayın."
    assert uyari[0].lower() + uyari[1:-1] in _bolum("yil-sonu-raporu")


# ---------------------------------------------------------------------------
# Kılavuz ↔ mevzuat: alıntılar birebir
# ---------------------------------------------------------------------------
_ALINTILAR: tuple[tuple[Path, int, str], ...] = (
    (
        _YONETMELIK,
        10,
        "Kütüphane kaynaklarının tespiti ve seçimi için Seçim ve Ayıklama Komisyonu, ilçe millî "
        "eğitim şube müdürü başkanlığında kurulur. Şube müdürünün katılamadığı durumlarda okul "
        "müdürü komisyona başkanlık eder.",
    ),
    (
        _YONETMELIK,
        10,
        "Okul kütüphanesine bağışlanacak kitaplar, bu Yönetmelik çerçevesinde Seçim ve Ayıklama "
        "Komisyonu tarafından değerlendirilir.",
    ),
    (
        _YONETMELIK,
        12,
        "Seçim ve Ayıklama Komisyonu tarafından aşağıda belirtilen nedenlerle ayıklanmasına "
        "karar verilen kaynaklar, bir tutanakla tespit edilerek … Taşınır Mal Yönetmeliği "
        "hükümlerine göre kayıtlardan düşümü yapılır. 10 uncu maddenin birinci fıkrasının (b) "
        "bendine uygun olmayan kaynaklar uygun okullara veya kurumlara devredilir.",
    ),
    (
        _YONETMELIK,
        12,
        "Seçim ve Ayıklama Komisyonu tarafından tespit edilen el yazmaları ve nadir eserler "
        "listesi, Genel Müdürlüğe gönderilir.",
    ),
    (
        _YONETMELIK,
        12,
        "Her ders yılı sonunda kütüphane kaynakları, kütüphaneci veya görevlendirilen öğretmen "
        "tarafından gözden geçirilir ve tespit edilen hususlar raporla okul müdürlüğüne "
        "bildirilir.",
    ),
)


@pytest.mark.parametrize(("yol", "numara", "alinti"), _ALINTILAR)
def test_kilavuz_alintisi_mevzuat_metniyle_birebir(yol: Path, numara: int, alinti: str) -> None:
    madde = _madde(yol, numara)
    for parca in alinti.split(" … "):
        assert parca in madde, f"{yol.name} md. {numara}: {parca}"
    assert f"“{alinti}”" in _kilavuz(), alinti


def test_kilavuz_uygulama_kilavuzu_2_4_alintisi_birebir() -> None:
    """Uygulama Kılavuzu 2.4 (bağlayıcı değildir; E9'un bölümlerini adlandırır)."""
    metin = _oku(_UYGULAMA_KILAVUZU)
    cikis = re.search(r"### 2\.4\.[^\n]*\n(.*?)(?=\n#)", metin, flags=re.DOTALL)
    assert cikis is not None, "Uygulama Kılavuzu 2.4 bölümü yok"
    bolum = _tek_bosluk(cikis.group(1)).strip()
    assert bolum == (
        "Her eğitim öğretim yılı sonunda kütüphanedeki kitap durumu, kazandırılan ve ayıklanan "
        "kaynaklar okul yönetimine raporlanır."
    )
    assert f"“{bolum}”" in _bolum("yil-sonu-raporu")


# ---------------------------------------------------------------------------
# Kılavuz ↔ mevzuat: alıntısız atıfların sade anlatımı atıf yapılan fıkrada
# ---------------------------------------------------------------------------
#: (kılavuzdaki atıf, mevzuat dosyası, madde, fıkra, fıkrada bulunması gereken ifadeler)
_ATIFLAR: tuple[tuple[str, Path, int, int, tuple[str, ...]], ...] = (
    # "Olağan kullanımdan doğan yıpranmada kimseden sorumluluk aranmaz"
    (
        "(TMY md. 5/8)",
        _TMY,
        5,
        8,
        ("olağan kullanımından kaynaklanan yıpranma", "sorumluluk aranmaz"),
    ),
    # "komisyon gerekmez" — durumu belgeleyen tutanak varsa komisyonsuz onay
    (
        "(TMY md. 10/1-e)",
        _TMY,
        10,
        1,
        (
            "e) Kayıttan Düşme Teklif ve Onay Tutanağı",
            "komisyon kurulması gerekmeksizin harcama yetkilisince onaylanır",
        ),
    ),
    # "kaynak taşınır kayıtlarından ancak harcama yetkilisi onaylayınca çıkar"
    (
        "(Taşınır Mal Yönetmeliği md. 10/1-e, 28/4)",
        _TMY,
        10,
        1,
        ("harcama yetkilisi tarafından onaylanır",),
    ),
    (
        "(Taşınır Mal Yönetmeliği md. 10/1-e, 28/4)",
        _TMY,
        28,
        4,
        ("harcama yetkilisinin onayı ile kayıtlardan çıkarılır",),
    ),
    # "bağışı taşınır kaydına taşınır kayıt yetkilisi alır; Varlık İşlem Fişi düzenler ve bir
    # nüshasını bağışçıya verir"
    (
        "(Taşınır Mal Yönetmeliği md. 16/1)",
        _TMY,
        16,
        1,
        (
            "taşınır kayıt yetkilisi tarafından Varlık İşlem Fişi düzenlenerek kayıtlara alınır",
            "bir nüshası bağış ve yardım edene verilir",
        ),
    ),
    # "Çıkış Varlık İşlem Fişiyle yapılır" (devir)
    ("(TMY md. 24)", _TMY, 24, 1, ("Varlık İşlem Fişi düzenlenerek yapılır",)),
    # "başka bir MEB okuluna ... aynı kamu idaresinin başka bir harcama birimine devir"
    ("(TMY 24/2)", _TMY, 24, 2, ("Aynı kamu idaresinin muhtelif harcama birimlerinin",)),
    # "yıpranarak kullanılamaz hâle gelen kaynak KDTOT ve VİF ile kayıtlardan çıkarılır"
    (
        "(TMY 27/1)",
        _TMY,
        27,
        1,
        (
            "yıpranma, kırılma veya bozulma gibi nedenlerle kullanılamaz hâle gelen",
            "Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık İşlem Fişi düzenlenerek",
        ),
    ),
    # "kusur olup olmadığını harcama yetkilisi değerlendirir"
    ("(TMY md. 27/3)", _TMY, 27, 3, ("harcama yetkilisince değerlendirilir",)),
    # "harcama yetkilisinin belirlediği ve biri işin uzmanı en az üç kişilik bir komisyon"
    (
        "(TMY md. 28/1)",
        _TMY,
        28,
        1,
        ("biri işin uzmanı olmak kaydıyla harcama yetkilisinin belirleyeceği en az üç kişiden",),
    ),
    # "komisyon ekonomik değeri olmadığına ya da imha edilmesi gerektiğine karar verirse
    # harcama yetkilisinin onayıyla ... ayrıca bir imha tutanağı düzenlenir"
    (
        "(TMY md. 28/5)",
        _TMY,
        28,
        5,
        (
            "ekonomik değerinin olmadığı",
            "harcama yetkilisinin onayı ile imha edilir",
            "imha tutanağı",
        ),
    ),
    # "Hurdaya ayrılan ve ekonomik değeri olan kitaplar hakkında 7330 sayılı Kanun" (F8 düzeltme)
    (
        "(TMY md. 28/8)",
        _TMY,
        28,
        8,
        ("Hurdaya ayrılan ve ekonomik değeri olan hurda taşınır mallar", "7330 sayılı"),
    ),
    # "kaynağa ihtiyacı olan, Bakanlık dışındaki bir kamu idaresine" bedelsiz devir
    (
        "(TMY 31)",
        _TMY,
        31,
        1,
        ("ihtiyaç duyan diğer kamu idarelerine bedelsiz olarak devredebilir",),
    ),
    # Genel Müdürlük ve komisyonun tanımı
    ("(md. 4/1-c)", _YONETMELIK, 4, 1, ("c) Genel Müdürlük: Destek Hizmetleri Genel Müdürlüğünü",)),
    (
        "Yönetmeliğin 4. maddesinin (ı) bendinde",
        _YONETMELIK,
        4,
        1,
        ("ı) Seçim ve Ayıklama Komisyonu:",),
    ),
    # Devir: 10/1-b yaş ve gelişim düzeyi; 10/4 hiçbir kütüphanede bulundurulamaz
    ("(md. 10/1-b)", _YONETMELIK, 10, 1, ("b) Öğrencilerin yaş ve gelişim düzeylerine uygun",)),
    ("Md. 10/4'e aykırı kitap", _YONETMELIK, 10, 4, ("bulundurulamaz",)),
)


@pytest.mark.parametrize(("atif", "yol", "madde", "fikra", "ifadeler"), _ATIFLAR)
def test_kilavuz_alintisiz_atfi_fikranin_metnine_dayanir(
    atif: str, yol: Path, madde: int, fikra: int, ifadeler: tuple[str, ...]
) -> None:
    assert atif in _bolum("ayiklama"), atif
    metin = _fikra(yol, madde, fikra)
    for ifade in ifadeler:
        assert ifade in metin, f"{yol.name} md. {madde}/{fikra}: {ifade}"


def test_kilavuzda_imha_yalniz_ayiklama_bolumunde_ve_28_5_baglaminda() -> None:
    """Sözlük §1: "imha" yalnız imha tutanağı ve imha kararı (TMY 28/5) bağlamında.

    Kılavuzun başka hiçbir bölümü "imha" demez; ayıklama bölümünde geçtiği her cümle
    İmha tutanağını, imha kararını ya da 28/5'i anar.
    """
    # Çıplak `.lower()` Türkçe "İ"yi "i̇" yapar (CLAUDE.md §2-9): harf sınıfıyla aranır.
    imha = re.compile(r"[iİ]mha")
    tum = _kilavuz()
    ayiklama = _bolum("ayiklama")
    assert len(imha.findall(tum)) == len(imha.findall(ayiklama)) > 0
    izinli = re.compile(r"[İi]mha tutanağı|[İi]mha kararı|imhaya karar|28/5")
    cumleler = [c for c in re.split(r"(?<=\.)\s(?=[A-ZÇĞİÖŞÜ“])", ayiklama) if imha.search(c)]
    assert cumleler
    for cumle in cumleler:
        assert izinli.search(cumle), cumle


def test_yil_sonu_raporunda_kazandirma_yollari_md_10_5_metnine_dayanir() -> None:
    """ "Kazandırılan" yalnız Md. 10/5'in yollarıdır (F8 düzeltme turu); sade anlatım fıkrada."""
    assert "(md. 10/5)" in _bolum("yil-sonu-raporu")
    fikra = _fikra(_YONETMELIK, 10, 5)
    for ifade in (
        "Bakanlıktan gönderilen kaynaklar",
        "satın alma, bağış",
        "değişim yoluyla sağlanır",
    ):
        assert ifade in fikra, ifade


# ---------------------------------------------------------------------------
# 25.09.2026 kullanıcı kararları (tasarım F8 ekleri 13, 34)
# ---------------------------------------------------------------------------
def test_kilavuz_hasar_onerisinin_engelini_sunucudan_yazar() -> None:
    """F8 ekleri 34: hasar önerisi ayıklamaya konmaz; kılavuz sunucunun iletisini birebir yazar."""
    from apps.kutuphane.services import weeding

    assert f"“{weeding.DAMAGE_PROPOSAL_MESSAGE}”" in _bolum("ayiklama")
    assert "Kayıp ve hasarlı kitap ayıklamaya konmaz" in _bolum("kayip-hasar")


@pytest.mark.parametrize(
    ("atif", "madde", "fikra", "ifadeler"),
    [
        # "bağış teslim alındığında taşınır kayıt yetkilisi VİF düzenler ve bir nüshasını
        # bağışçıya verir"
        (
            "(Taşınır Mal Yönetmeliği md. 16/1)",
            16,
            1,
            (
                "teslim alındığında, taşınır kayıt yetkilisi tarafından Varlık İşlem Fişi "
                "düzenlenerek kayıtlara alınır",
                "bir nüshası bağış ve yardım edene verilir",
            ),
        ),
        # "bağışçının belgesindeki değer ya da değer tespit komisyonunun belirlediği değer"
        (
            "(Taşınır Mal Yönetmeliği md. 13/2-c)",
            13,
            2,
            (
                "c) Bağış ve yardım yoluyla edinilen taşınırlarda",
                "ispat edici bir belge ile değeri belirtilmiş ise bu değer",
                "değer tespit komisyonunca belirlenen değer",
            ),
        ),
    ],
)
def test_kilavuz_bagis_atiflari_fikranin_metnine_dayanir(
    atif: str, madde: int, fikra: int, ifadeler: tuple[str, ...]
) -> None:
    """F8 ekleri 13: Katalog bölümünün bağış paragrafı; "bağış kabul tutanağı" TMY'de yoktur."""
    assert atif in _bolum("katalog"), atif
    metin = _fikra(_TMY, madde, fikra)
    for ifade in ifadeler:
        assert ifade in metin, f"TMY md. {madde}/{fikra}: {ifade}"
    assert "bağış kabul tutanağı" not in _oku(_TMY).casefold()
    assert "“bağış kabul tutanağı” diye bir belge yoktur" in _bolum("katalog")
