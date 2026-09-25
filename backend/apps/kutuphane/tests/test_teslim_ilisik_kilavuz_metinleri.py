"""Teslim, kayıp/hasar, ilişik ve yıl akışı metinleri ↔ kılavuz ve mevzuat (F7).

Kılavuzun (`frontend/src/modules/kilavuz/KilavuzPage.tsx`) F7 bölümleri masada, teslim
ve kayıp ekranlarında, ilişik belgelerinde görülen SUNUCU iletilerini birebir yazar.
Ön yüz testi (`KilavuzPage.test.tsx`) bu iletileri okuyamadığı için kopya tutar; bu test
kopyaların sunucudaki sabitlerle aynı kaldığını denetler. Sunucu bir iletiyi, sınırı ya
da tarih penceresini değiştirirse kılavuz da değişmek zorunda kalır.

Mevzuat alıntıları (Md. 18/1 ve 19/1) ilgili MADDENİN içinde aranır (CLAUDE.md §2-13).
Md. 18/1'in üçüncü cümlesinin ortası Bakanlığın sistemini andığı için kılavuzda "…" ile
atlanır; her parça ayrı ayrı aranır.

Kılavuzun konum kuralları da burada kaynak metinde sınanır: "İlişiği yoktur" belgesi
karne ya da diploma ön koşulu diye sunulmaz (tasarım §8.3; docs/mevzuat/BENIOKU.md §4),
kayıp ve hasarda borç/tahsilat dili yoktur (sözlük §1).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane import ilisik_belgeleri, models, teslim_belgeleri
from apps.kutuphane.models import (
    CaseResolution,
    Copy,
    CopyStatus,
    DeliveryStatus,
    Work,
)
from apps.kutuphane.services import circulation, deliveries, yil_akislari
from apps.okul import kip
from apps.okul.models import SchoolLevel

_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_YONETMELIK = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi.md"
_TMY = Path("docs") / "mevzuat" / "tasinir-mal-yonetmeligi.md"
_OKY = Path("docs") / "mevzuat" / "ortaogretim-kurumlari-yonetmeligi-ilgili-maddeler.md"

_AYLAR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}


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
    """Kılavuzun kullanıcıya görünen düz metni (yaklaşık).

    Yorumlar atılır (kuralı ANLATIRLAR, ör. "yıl devri" sözcüğü kullanılmaz); JSX
    etiketleri (`<strong>`, `<Ekran …>`) sökülür, boşluk parçaları ve varlıklar çözülür.
    Satır başı `//` yorumları ve `/* … */` blokları atılır.
    """
    kaynak = _oku(_KILAVUZ)
    kaynak = re.sub(r"/\*.*?\*/", " ", kaynak, flags=re.DOTALL)
    kaynak = re.sub(r"^\s*//.*$", " ", kaynak, flags=re.MULTILINE)
    kaynak = kaynak.replace("&apos;", "'").replace('{" "}', " ")
    kaynak = re.sub(r"</?[A-Za-z][^<>]*>", "", kaynak)
    return _tek_bosluk(kaynak)


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
def _oduncteki_nushanin_teslim_gerekcesi() -> str:
    """`deliveries.delivery_obstacle`'ın ödünçteki nüshaya verdiği gerekçe (DB'siz)."""
    nusha = Copy(work=Work(title="Örnek Eser"), status=CopyStatus.ON_LOAN)
    return deliveries.delivery_obstacle(nusha)


_KILAVUZ_ILETILERI: tuple[str, ...] = (
    deliveries.TAKE_BACK_DONE_MESSAGE,
    deliveries.NOT_DELIVERED_ON_LOAN_MESSAGE,
    deliveries.NOT_DELIVERED_MESSAGE.format(durum="…"),
    deliveries.SECTION_DELETE_MESSAGE.format(sayi="…"),
    deliveries.SECTION_DELETE_CASE_MESSAGE.format(sayi="…"),
    ilisik_belgeleri.NOT_CLEAR_MESSAGE.format(sayi="N"),
    ilisik_belgeleri.LISTE_DIPNOTU,
    teslim_belgeleri.TAHSILAT_NOTU,
    circulation.COPY_STATE_MESSAGES[CopyStatus.DELIVERED],
)


@pytest.mark.parametrize("ileti", _KILAVUZ_ILETILERI)
def test_kilavuz_sunucu_iletisini_tirnak_icinde_birebir_yazar(ileti: str) -> None:
    assert f"“{ileti}”" in _kilavuz(), ileti


def test_kilavuz_teslim_retlerinin_gerekcesini_sunucudaki_bicimle_yazar() -> None:
    gerekce = _oduncteki_nushanin_teslim_gerekcesi()
    assert gerekce == f"{CopyStatus.ON_LOAN.label} — teslim edilemez."
    assert f"“{gerekce}”" in _kilavuz()


def test_kilavuz_cozum_ve_teslim_durumlarini_etiketleriyle_yazar() -> None:
    """Çözüm düğmeleri `CaseResolution` etiketleriyle; "Çözüm bekliyor" düğme değildir."""
    metin = _kilavuz()
    for kod, etiket in CaseResolution.choices:
        if kod == CaseResolution.PENDING:
            continue
        assert f"“{etiket}”" in metin, etiket
    assert f"“{DeliveryStatus.LOST_CONVERTED.label}” olarak kapanır" in metin
    assert f"“{CopyStatus.LOST.label}” olur" in metin
    assert f"“{CopyStatus.DELIVERED.label}” görünür" in metin


def test_kilavuz_sorumlu_notu_uyarisini_yazar() -> None:
    """Sorumlu notunun yardımı (`RESPONSIBLE_NOTE_HELP`) cümle içinde küçük harfle."""
    ikinci = models.RESPONSIBLE_NOTE_HELP.split(". ", 1)[1]
    assert ikinci == "Sağlık ya da aile bilgisi yazmayın."
    assert ikinci[0].lower() + ikinci[1:-1] in _kilavuz()


def test_kilavuz_sinirlari_sunucu_sabitleriyle_ayni_yazar() -> None:
    metin = _kilavuz()
    assert f"Tek teslimde en çok {deliveries.MAX_DELIVERY_BATCH} kitap" in metin
    assert f"Tek seferde en çok {ilisik_belgeleri.MAX_CERTIFICATES} belge" in metin
    # Son sınıf: kademenin son sınıfı (circulation.GRADUATING_LEVEL).
    seviye = circulation.GRADUATING_LEVEL
    assert (
        f"ilkokulda {seviye[SchoolLevel.ILKOKUL]}, ortaokulda {seviye[SchoolLevel.ORTAOKUL]}, "
        f"ortaöğretimde {seviye[SchoolLevel.ORTAOGRETIM]}. sınıf"
    ) in metin


def test_kilavuz_kip_surelerini_model_sinirlariyla_yazar() -> None:
    """Varsayılanlar `kip.VARSAYILAN_*`, ayar sınırları `LibraryPolicy` doğrulayıcıları."""
    metin = _kilavuz()
    assert f"{kip.VARSAYILAN_BOSTA_DK} dakika işlem yapılmazsa" in metin
    assert f"en geç {kip.VARSAYILAN_MUTLAK_DK} dakika sonra" in metin
    assert (
        f"“İşlem yapılmazsa kapanma süresi (dakika)” {models.IDLE_MINUTES_MIN} ile "
        f"{models.IDLE_MINUTES_MAX}"
    ) in metin
    assert (
        f"“En uzun açık kalma süresi (dakika)” {models.ADMIN_MAX_MINUTES_MIN} ile "
        f"{models.ADMIN_MAX_MINUTES_MAX} dakika"
    ) in metin


def _gun_ay(gun_ay: tuple[int, int], ek: str) -> str:
    ay, gun = gun_ay
    return f"{gun} {_AYLAR[ay]}'{ek}"


def test_kilavuz_genel_bakis_kartlarinin_penceresini_servisle_ayni_yazar() -> None:
    """Yıl sonu ve yıl başı kartlarının tarih pencereleri (`services/yil_akislari.py`)."""
    metin = _kilavuz()
    assert yil_akislari.YEAR_END_GRACE_DAYS == 14  # kılavuz "iki hafta" der
    assert (
        f"“Yıl Sonu” kartı {_gun_ay(yil_akislari.YEAR_END_START, 'tan')} "
        f"{_gun_ay(yil_akislari.YEAR_END_END, 'a')} kadar (ders yılı daha geç biterse "
        "bitişten iki hafta sonrasına dek)"
    ) in metin
    assert (
        f"“Yıl Başı” kartı {_gun_ay(yil_akislari.YEAR_START_START, 'tan')} "
        f"{_gun_ay(yil_akislari.YEAR_START_END, 'e')} kadar"
    ) in metin


# ---------------------------------------------------------------------------
# Kılavuz ↔ mevzuat
# ---------------------------------------------------------------------------
_ALINTILAR: tuple[tuple[Path, int, str], ...] = (
    (
        _YONETMELIK,
        19,
        "Ortaöğretim okul kütüphanelerinde hasara uğratılan veya kaybedilen kaynak ilgili "
        "kişiden temin edilir, temin edilememesi hâlinde o günkü piyasa bedeli, hasara "
        "uğratan veya kaybeden kişiden alınır. Kaynak bedeli ile mevcudu varsa aynısı yoksa "
        "kaybedilenin kaydı silinerek başka eser satın alınır.",
    ),
    (
        _YONETMELIK,
        18,
        "Kütüphaneye iadesi yapılmayan kitapların takibi kütüphaneci veya kütüphaneden "
        "sorumlu öğretmen tarafından yapılır. Öğrencilerin ve öğretmenlerin okuldan "
        "ayrılması sebebiyle … alınan ödünç kitabın kütüphaneye iadesi sağlanır.",
    ),
)


@pytest.mark.parametrize(("yol", "numara", "alinti"), _ALINTILAR)
def test_kilavuz_alintisi_mevzuat_metniyle_birebir(yol: Path, numara: int, alinti: str) -> None:
    madde = _madde(yol, numara)
    for parca in alinti.split(" … "):
        assert parca in madde, f"{yol.name} md. {numara}: {parca}"
    assert f"“{alinti}”" in _kilavuz(), alinti


def test_evrak_alintilari_kilavuzdakiyle_ayni_kaynaktan() -> None:
    """Tutanağın Md. 19 ve belgenin Md. 18 parçası kılavuzdaki alıntının içindedir."""
    metin = _kilavuz()
    assert teslim_belgeleri.MD19_ALINTI in metin
    assert ilisik_belgeleri.MD18_ALINTI in metin


@pytest.mark.parametrize(
    ("yol", "numara", "parca", "atif"),
    [
        (_TMY, 23, "Dayanıklı Taşınırlar Listesi", "Taşınır Mal Yönetmeliği md. 23/6'ya kıyasen"),
        (
            _TMY,
            32,
            "Dayanıklı Taşınırlar Listeleri esas alınarak sayılır",
            "Taşınır Mal Yönetmeliği md. 32/5'e kıyasen",
        ),
        (
            _OKY,
            164,
            "aldığı kitap, araç- gereç ve malzemeyi, eksik vermek veya kötü kullanmak",
            "Ortaöğretim Kurumları Yönetmeliği'nde (md. 164/1-g)",
        ),
    ],
)
def test_kilavuzun_alintisiz_atiflari_depodaki_maddede(
    yol: Path, numara: int, parca: str, atif: str
) -> None:
    """Alıntısız atıflar da doğru maddeye gider (metin depodaki maddede geçer)."""
    assert parca in _madde(yol, numara), f"{yol.name} md. {numara}"
    assert atif in _kilavuz()


# ---------------------------------------------------------------------------
# Konum ve sözlük kuralları (kaynak metin)
# ---------------------------------------------------------------------------
def test_ilisik_belgesi_karne_ya_da_diploma_on_kosulu_diye_sunulmaz() -> None:
    metin = _kilavuz()
    assert len(re.findall(r"karne", metin, flags=re.IGNORECASE)) == 1
    assert len(re.findall(r"diploma", metin, flags=re.IGNORECASE)) == 1
    assert "Bu belge karne ya da diploma almanın ön koşulu değildir" in metin


@pytest.mark.parametrize(
    "yasak",
    [
        r"zayi",
        r"(?<!\w)telef(?!on)",
        r"borç(?!lar Kanunu)",
        r"ilişi\w* kes",
        r"tahsil edil",
        r"zimmet",
        r"emanet",
        r"yıl devri",
        r"otomasyon sistemi",
    ],
)
def test_kilavuz_sozlugun_kullanilmaz_sozcuklerini_tasimaz(yasak: str) -> None:
    assert not re.search(yasak, _kilavuz(), flags=re.IGNORECASE), yasak
