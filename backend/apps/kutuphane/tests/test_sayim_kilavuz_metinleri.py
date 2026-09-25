"""Sayım metinleri ↔ kılavuz, ön yüz ve mevzuat (F9).

Kılavuzun (`frontend/src/modules/kilavuz/KilavuzPage.tsx`) "Sayım" bölümü sunucunun
seçenek adlarını, iletilerini ve belge adlarını birebir yazar. Ön yüz testi
(`KilavuzPage.test.tsx`) ön yüzün sabitlerini sınar; bu test sunucu tarafını: kod bir
etiketi ya da iletiyi değiştirirse kılavuz da değişmek zorunda kalır.

Mevzuat (CLAUDE.md §2-13): kılavuzdaki alıntılar atıf yapılan FIKRANIN içinde aranır;
alıntısız atıfların sade anlatımının dayandığı ifadeler de fıkranın metninde aranır — madde
numarası uydurulmasın, fıkra kaymasın.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane import sayim_belgeleri, selectors_sayim
from apps.kutuphane.models import (
    LOAN_BASIS_CHOICES,
    REPAIR_BASIS_CHOICES,
    SECTION_DELIVERY_BASIS_CHOICES,
    TEACHER_DELIVERY_BASIS_CHOICES,
    CaseResolution,
    CaseType,
    CopyStatus,
    CountBasis,
    StockTakeOutcome,
)
from apps.kutuphane.services import circulation, stocktake, tmy_kapisi

_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_TMY = Path("docs") / "mevzuat" / "tasinir-mal-yonetmeligi.md"
_YONETMELIK = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi.md"


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


def _bolum(kimlik: str) -> str:
    kaynak = _oku(_KILAVUZ)
    cikis = re.search(rf'<Bolum id="{kimlik}">(.*?)</Bolum>', kaynak, flags=re.DOTALL)
    assert cikis is not None, f"kılavuzda {kimlik} bölümü yok"
    govde = cikis.group(1).replace("&apos;", "'").replace('{" "}', " ")
    govde = re.sub(r"\{/\*.*?\*/\}", " ", govde, flags=re.DOTALL)
    return _tek_bosluk(re.sub(r"</?[A-Za-z][^<>]*>", "", govde))


def _fikra(yol: Path, madde: int, fikra: int) -> str:
    metin = _oku(yol)
    cikis = re.search(
        rf'<a id="madde-{madde}"></a>(.*?)(?=<a id="madde-|\Z)', metin, flags=re.DOTALL
    )
    assert cikis is not None, f"{yol.name}: madde {madde} çapası yok"
    govde = _tek_bosluk(cikis.group(1))
    bolum = re.search(rf"\({fikra}\) (.*?)(?= \({fikra + 1}\) |\Z)", govde)
    assert bolum is not None, f"{yol.name} md. {madde}/{fikra} yok"
    return bolum.group(1)


# ---------------------------------------------------------------------------
# Kılavuz ↔ kodun adları ve iletileri
# ---------------------------------------------------------------------------
def test_kilavuz_kurul_seciminin_adlarini_koddan_yazar() -> None:
    metin = _bolum("sayim")
    secilebilir = {
        *LOAN_BASIS_CHOICES,
        *SECTION_DELIVERY_BASIS_CHOICES,
        *TEACHER_DELIVERY_BASIS_CHOICES,
    }
    for kod in secilebilir:
        assert f"“{CountBasis(kod).label}”" in metin, kod
    # K2 (25.09.2026): onarımdaki nüshanın seçenekleri kararın sözcükleriyle.
    for kod in REPAIR_BASIS_CHOICES:
        assert f"“{selectors_sayim.basis_label('repair', kod)}”" in metin, kod


def test_kilavuz_terminal_durumlari_ve_onay_sonucunu_koddan_yazar() -> None:
    metin = _bolum("sayim")
    for durum in (
        CopyStatus.WITHDRAWN_MISSING,
        CopyStatus.WITHDRAWN_LOST,
        CopyStatus.WITHDRAWN_DAMAGED,
    ):
        assert f"“{durum.label}”" in metin, durum.label
    assert f"“{StockTakeOutcome.STATE_CHANGED.label}”" in metin


def test_kilavuz_hizmet_arasi_iletisini_sunucudan_birebir_yazar() -> None:
    assert f"“{circulation.SERVICE_PAUSE_MESSAGE}”" in _bolum("sayim")


def test_kilavuz_belge_ve_ek_adini_sunucudan_yazar() -> None:
    metin = _bolum("sayim")
    assert sayim_belgeleri.TUTANAK_ADI in metin
    assert f"“{sayim_belgeleri.EK_ADI}”" in metin
    # Ekin ibaresi (A8 kararı, F8 ekleri 13) ve belgenin basılamadığı durum sunucudan birebir.
    assert f"“{selectors_sayim.TMY_34_1_NOTE}”" in metin
    assert sayim_belgeleri.CANCELLED_MESSAGE in metin


def test_kilavuzda_yasak_sozcuk_yok() -> None:
    """Sözlük §1: "sayım kilidi" ve "dondurma" denmez; iki seçenek kendi adlarıyla anılır."""
    metin = _bolum("sayim").casefold()
    assert "sayım kilidi" not in metin and "dondurma" not in metin


def test_kilavuz_durdurmanin_kapsadigi_islemleri_kapidan_yazar() -> None:
    """Kılavuzun "yapılamaz" listesi `tmy_kapisi.ISLEM_ADLARI`'dır (ret iletisiyle aynı adlar)."""
    metin = _bolum("sayim")
    for ad in tmy_kapisi.ISLEM_ADLARI.values():
        assert ad in metin, ad


@pytest.mark.parametrize(
    ("dosya_turu", "cozum"),
    [
        # K1 (25.09.2026): kayıp dosyasında bulunma kapsam dışıdır.
        (CaseType.LOST, CaseResolution.FOUND_RETURNED),
        (CaseType.LOST, CaseResolution.FOUND_AFTER_PRICE),
        (CaseType.LOST, CaseResolution.PRICE_DETERMINED),
        (CaseType.LOST, CaseResolution.PRICE_RECEIVED),
        (CaseType.DAMAGED, CaseResolution.REPAIRED),
        (CaseType.DAMAGED, CaseResolution.REPLACED_SAME),
        (CaseType.DAMAGED, CaseResolution.CLOSED_SAME_REPURCHASED),
    ],
)
def test_kilavuzun_durmayan_cozumleri_kapinin_kapsami_disinda(dosya_turu: str, cozum: str) -> None:
    """Kılavuz "Durmayanlar" diye saydığı çözümü ekrandaki adıyla yazar ve kapı onu gerçekten
    geçirir (F7 ekleri 17: bedel adımları ve öneri yazmayan hasar çözümleri; F9 ekleri K1:
    kayıp dosyasında bulunma kapsam dışı)."""
    assert not tmy_kapisi.dosya_cozumu_kapsamda_mi(dosya_turu, cozum)
    assert f"“{CaseResolution(cozum).label}”" in _bolum("sayim")


def test_kilavuz_durdurmada_bulunmanin_acik_oldugunu_soyler() -> None:
    """K1 (25.09.2026): kayıp dosyasının "Bulundu"su kapıdan geçmez; kılavuz bunu gerekçesiyle
    söyler, okutmayı ve onaydaki kapanışı da anlatır."""
    assert not tmy_kapisi.dosya_cozumu_kapsamda_mi(CaseType.LOST, CaseResolution.FOUND_RETURNED)
    metin = _bolum("sayim")
    assert (
        f"kayıp dosyası durdurma sürerken de “{CaseResolution.FOUND_RETURNED.label}” ile "
        "kapatılır" in metin
    )
    assert "Kayıptaki kitabın rafa dönüşü taşınır giriş ve çıkışı değildir" in metin
    assert "ile kapatılamaz" not in metin
    for cozum in (CaseResolution.FOUND_RETURNED, CaseResolution.FOUND_AFTER_PRICE):
        assert f"“{CaseResolution(cozum).label}”" in metin
    assert f"“{StockTakeOutcome.RECONCILED.label}”" in metin


def test_kilavuz_programa_aktarimin_tmysiz_iletisini_yazar() -> None:
    """K4 (b): programa aktarım durdurma süresince kapalı; ileti TMY'ye dayanmaz."""
    assert f"“{tmy_kapisi.PROGRAMA_AKTARIM_MESSAGE}”" in _bolum("sayim")
    assert f"“{tmy_kapisi.PROGRAMA_AKTARIM_MESSAGE}”" in _bolum("ice-aktarma")


def test_kilavuz_okutma_iletisini_sunucudan_birebir_yazar() -> None:
    assert f"“{stocktake.SCAN_ALREADY}”" in _bolum("sayim")


def test_kilavuzun_obur_bolumleri_hizmet_arasi_ve_durdurma_adlarini_yazar() -> None:
    """Dolaşım Masası hizmet arası iletisini sunucudan birebir yazar; durdurmanın bandı
    edinim, kayıp/hasar ve ayıklama bölümlerinde aynı adla geçer."""
    assert f"“{circulation.SERVICE_PAUSE_MESSAGE}”" in _bolum("dolasim")
    for kimlik in ("katalog", "kayip-hasar", "ayiklama"):
        assert "“TMY 32/3 durdurması sürüyor” bandı" in _bolum(kimlik), kimlik


def test_kilavuz_32_1_ifadesini_kisaltmadan_yazar() -> None:
    ifade = "yıl sonlarında ve harcama yetkilisinin gerekli gördüğü durum ve zamanlarda"
    assert ifade in _fikra(_TMY, 32, 1)
    assert ifade in _bolum("sayim")


def test_hizmet_arasi_icin_13_1_odunc_saymaz() -> None:
    """ "Ödünç, yönetmeliğin saydığı giriş ve çıkış hâllerinden değildir (md. 13/1)": fıkra
    giriş ve çıkış hâllerini sayar, ödünç aralarında yoktur."""
    fikra = _fikra(_TMY, 13, 1)
    assert "ödünç" not in fikra.casefold()
    assert "ödünç, yönetmeliğin saydığı giriş ve çıkış hâllerinden değildir (md. 13/1)" in (
        _bolum("sayim")
    )


def test_kilavuz_10_1_e_takdir_diliyle_yazilir() -> None:
    """Tasarım F8 ekleri 27: 10/1-e "onaylanır" der ama belgenin o tutanak sayılıp
    sayılmayacağını harcama yetkilisi değerlendirir — kılavuz kesin hüküm gibi yazmaz."""
    metin = _bolum("sayim")
    assert "komisyon kurulmadan harcama yetkilisince onaylanabilir" in metin
    assert "o belge sayılıp sayılmayacağını harcama yetkilisi değerlendirir" in metin
    assert "harcama yetkilisince onaylanır" not in metin


# ---------------------------------------------------------------------------
# Kılavuz ↔ mevzuat: alıntılar birebir
# ---------------------------------------------------------------------------
_ALINTILAR: tuple[tuple[int, int, str], ...] = (
    (
        32,
        3,
        "Sayım süresince, hizmetin aksamaması ve bozulabilecek nitelikteki taşınırlar için "
        "gerekli tedbirlerin alınması kaydıyla, taşınır giriş ve çıkışları sayım kurulunun "
        "talebi üzerine harcama yetkilisince durdurulabilir.",
    ),
    (17, 1, sayim_belgeleri.TMY17_1),
    (34, 1, sayim_belgeleri.TMY34_1),
)


@pytest.mark.parametrize(("madde", "fikra", "alinti"), _ALINTILAR)
def test_kilavuz_alintisi_fikranin_metniyle_birebir(madde: int, fikra: int, alinti: str) -> None:
    assert alinti in _fikra(_TMY, madde, fikra), f"TMY md. {madde}/{fikra}"
    assert f"“{alinti}”" in _bolum("sayim"), alinti


# ---------------------------------------------------------------------------
# Kılavuz ↔ mevzuat: alıntısız atıfların sade anlatımı atıf yapılan fıkrada
# ---------------------------------------------------------------------------
_ATIFLAR: tuple[tuple[str, Path, int, int, tuple[str, ...]], ...] = (
    # "yıl sonlarında ve harcama yetkilisinin gerekli gördüğü durum ve zamanlarda sayılır"
    (
        "(Taşınır Mal Yönetmeliği md. 32/1)",
        _TMY,
        32,
        1,
        ("yıl sonlarında ve harcama yetkilisinin gerekli gördüğü durum ve zamanlarda",),
    ),
    # "başkan + taşınır kayıt yetkilisi + en az üç kişilik sayım kurulu"
    (
        "(md. 32/2)",
        _TMY,
        32,
        2,
        (
            "kendisinin veya görevlendireceği bir kişinin başkanlığında",
            "taşınır kayıt yetkilisinin de katılımıyla",
            "en az üç kişiden oluşturulan sayım kurulu",
        ),
    ),
    # "okuyucuya verilen kütüphane materyali Taşınır Teslim Belgesi düzenlenmeden ödünç takip
    # sistemiyle izlenir"
    (
        "(md. 23/4)",
        _TMY,
        23,
        4,
        (
            "okuyucu ve araştırmacılara verilen kütüphane materyalleri",
            "Taşınır Teslim Belgesi düzenlenmeden",
            "ödünç takip sistemleri ile takip edilir",
        ),
    ),
    # sınıf kitaplığı ortak kullanım alanı gibi yerinde; öğretmende kişilere verilen miktar
    (
        "md. 32/5'in birinci cümlesine kıyasen",
        _TMY,
        32,
        5,
        (
            "ortak kullanım alanlarında bulunan taşınırlar",
            "Kayıtlara Göre Kişilere Verilen Miktar",
        ),
    ),
    # "bulunamayan kitaplar bir kez daha aranır"
    ("(md. 32/6)", _TMY, 32, 6, ("bir kez daha tekrarlanır",)),
    # "noksan için KDTOT ve VİF, fazla için VİF düzenlettirilerek … uygunluğu sağlanır"
    (
        "(md. 32/7)",
        _TMY,
        32,
        7,
        (
            "Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık İşlem Fişi",
            "düzenlettirilerek, defter kayıtlarının sayım sonuçlarıyla uygunluğu sağlanır",
        ),
    ),
    # "kullanılamaz hâle gelen taşınır olarak kayıtlardan çıkarılır"
    ("(TMY 27/1)", _TMY, 27, 1, ("kullanılamaz hâle gelen taşınırlar", "kayıtlardan çıkarılır")),
    # "durumu belgeleyen tutanak varsa komisyon kurulmadan harcama yetkilisince onaylanabilir"
    (
        "(TMY md. 10/1-e)",
        _TMY,
        10,
        1,
        (
            "durumu belgeleyen tutanak, rapor ve benzeri belgelerin bulunması",
            "komisyon kurulması gerekmeksizin harcama yetkilisince onaylanır",
        ),
    ),
    # "fazla/noksan sayfaları VİF'e eklenir ve muhasebe birimine gönderilir"
    (
        "(TMY md. 10/1-g, 32/8)",
        _TMY,
        10,
        1,
        (
            "Sayım Tutanağının sayım fazlası veya noksanına ilişkin sayfalarının",
            "muhasebe birimine gönderilecek nüshasına bağlanır",
        ),
    ),
    ("(TMY md. 10/1-g, 32/8)", _TMY, 32, 8, ("muhasebe birimine gönderilir",)),
    # "taşınır kodu düzeyindeki resmî Sayım Tutanağı"
    ("(md. 10/1-g)", _TMY, 10, 1, ("Sayım Tutanağına Taşınır Kodu düzeyinde kaydedilir",)),
    # "cetveli … sayım kurulu düzenler; sayım kurulu ile taşınır kayıt yetkilisi imzalar"
    (
        "(md. 32/9)",
        _TMY,
        32,
        9,
        (
            "sayım kurulu tarafından Taşınır Sayım ve Döküm Cetveli düzenlenir",
            "Cetvel, sayım kurulu ile taşınır kayıt yetkilisi tarafından imzalanır",
        ),
    ),
    # "“Gelecek Yıla Devir” = “Sayımda Bulunan Miktar”"
    (
        "(md. 10/1-ğ)",
        _TMY,
        10,
        1,
        (
            "“Gelecek Yıla Devir” sütununda gösterilen miktarın",
            "“Sayımda Bulunan Miktar” sütununda gösterilen miktara eşit olması gerekir",
        ),
    ),
    # hizmet arası: "ödünç giriş ve çıkış hâllerinden değildir" (olumsuzu ayrı testte)
    ("(md. 13/1)", _TMY, 13, 1, ("teslim alındığında giriş", "çıkış kaydedilir")),
    # hizmet arasının tutanaktaki dayanağı: "önlem almak sayım kurulunun görevidir"
    (
        "(md. 32/3, ikinci cümle)",
        _TMY,
        32,
        3,
        ("Sayım yapılırken gerekli önlemlerin alınması, sayım kurulunun görev ve sorumluluğu",),
    ),
    # "kasıt, kusur, ihmal ya da tedbirsizliği harcama yetkilisi değerlendirir"
    (
        "(md. 27/3)",
        _TMY,
        27,
        3,
        ("kasıt, kusur, ihmal veya tedbirsizlik olup olmadığı harcama yetkilisince",),
    ),
    # fazlanın kayda esas değeri
    (
        "(md. 17/1, ikinci cümle)",
        _TMY,
        17,
        1,
        (
            "son bir yıl içinde girişi yapılan taşınır varsa bu değer",
            "değer tespit komisyonu tarafından belirlenecek değer",
        ),
    ),
    # "iade hiçbir durumda durmaz" — iade otomasyon üzerinden alınır (alıntısız: fıkra
    # kılavuzun yasak sözcüğünü taşır)
    ("(Yönetmelik Md. 23/1-c)", _YONETMELIK, 23, 1, ("c) Kaynak teslim edildiğinde",)),
)


@pytest.mark.parametrize(("atif", "yol", "madde", "fikra", "ifadeler"), _ATIFLAR)
def test_kilavuz_alintisiz_atfi_fikranin_metnine_dayanir(
    atif: str, yol: Path, madde: int, fikra: int, ifadeler: tuple[str, ...]
) -> None:
    assert atif in _bolum("sayim"), atif
    metin = _fikra(yol, madde, fikra)
    for ifade in ifadeler:
        assert ifade in metin, f"{yol.name} md. {madde}/{fikra}: {ifade}"


# ---------------------------------------------------------------------------
# F9 düzeltme turu (25.09.2026): kılavuz düzeltilen davranışları yazar
# ---------------------------------------------------------------------------
def test_kilavuz_tamamlandidan_sonra_getirilen_kayip_kitabin_yolunu_yazar() -> None:
    """Okutma yalnız süren sayımdadır. K1'den (25.09.2026) sonra kayıp dosyası durdurma
    sürerken de "Bulundu" ile kapatılır: kılavuz onaydan ÖNCE bulunmayı yazar ("Onaylanmadı"
    ara önlemi sadeleşti); onay kalemi yeniden denetler (D17)."""
    metin = _bolum("sayim")
    assert stocktake.STATE_MESSAGES["scan"] == "Okutma yalnız süren sayımda yapılır."
    assert "Sayım tamamlandıktan sonra okutma kapanır" in metin
    assert (
        "o arada getirilen kayıp kitap için onaydan önce kayıp dosyasında "
        f"“{CaseResolution.FOUND_RETURNED.label}”yu seçin" in metin
    )
    assert f"“{CopyStatus.WITHDRAWN_LOST.label}”" in metin
    assert f"“{StockTakeOutcome.NOT_APPROVED.label}”" in metin
    kayip = _bolum("kayip-hasar")
    assert "Sayım tamamlandıktan sonra getirilen kayıp kitap okutulamaz" in kayip
    assert "onaydan önce dosyada “Bulundu”yu seçin" in kayip


def test_kilavuz_durdurmanin_kapsamadigini_sunucunun_cumlesiyle_yazar() -> None:
    assert selectors_sayim.TMY_STOP_NOT_COVERED_TEXT in _bolum("sayim")


def test_kilavuz_sinif_kitapliginda_kayda_gore_alma_olmadigini_yazar() -> None:
    """K3 (25.09.2026): seçenek kalktı; "sayım yapılmaksızın" 32/5'in yalnız ikinci
    cümlesindedir — kılavuz bunu fıkranın metnine dayanarak söyler."""
    metin = _bolum("sayim")
    assert CountBasis.BY_RECORD not in SECTION_DELIVERY_BASIS_CHOICES
    assert "Sınıf kitaplığındaki kitap kayda göre alınmaz" in metin
    assert "geri alınamayan kitap sınıf kitaplığında yerinde aranır" in metin
    fikra = _fikra(_TMY, 32, 5)
    birinci, ikinci = fikra.split(". ", 1)
    assert "sayım yapılmaksızın" not in birinci and "sayım yapılmaksızın" in ikinci
    assert "kamu görevlilerine taşınır teslim belgesiyle verilmiş" in ikinci
    assert "yalnız ikinci cümlededir ve kamu görevlilerine teslim belgesiyle verilen" in metin


def test_kilavuz_onarimdaki_nushanin_dayanagini_uydurmaz() -> None:
    """K2 (25.09.2026): TMY'de onarıma gönderilmiş taşınırın sayımına ilişkin hüküm yok —
    kılavuz ve dayanak metni 32/5'i atfetmez, bunu açıkça söyler. Sayımın maddesinde (md. 32)
    hiçbir fıkrada "onarım" sözcüğü yoktur (BENIOKU §4)."""
    metin = _bolum("sayim")
    assert selectors_sayim.REPAIR_NOTE.split("; ", 1)[1].rstrip(".") in metin
    for fikra_no in range(1, 10):
        assert "onarım" not in _fikra(_TMY, 32, fikra_no).casefold(), fikra_no


def test_kilavuz_harfli_kodu_ve_sayimda_baglanan_etiketi_yazar() -> None:
    metin = _bolum("sayim")
    assert "Harf içeren kod" in metin and "“Etiketsiz kitap ekle”" in metin
    assert "“Sayım sırasında kayda girdi”" in metin
