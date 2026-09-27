"""F10 kılavuz bölümleri ↔ mevzuat ve kod ("Raporlar ve Çok Okunanlar", "Dökümler ve Dışa
Aktarım"; Sayım ve Yedek bölümlerinin F10 ekleri).

Kılavuz (`frontend/src/modules/kilavuz/KilavuzPage.tsx`) sunucunun belge, sayfa ve eksen adlarını,
çok okunanların sınırlarını ve "Bakanlık sistemi kullanımda" ayarının adını birebir yazar. Ön yüz
testi (`KilavuzPage.test.tsx`) ön yüzün sabitlerini sınar; bu test sunucu tarafını: kod bir adı ya
da sınırı değiştirirse kılavuz da değişmek zorunda kalır.

Mevzuat (CLAUDE.md §2-13): bölümdeki HER uzun alıntı atıf yapılan fıkranın (ya da kılavuz
bölümünün) metninde aranır; alıntısız atıfların sade anlatımının dayandığı ifadeler de fıkranın
metninde aranır — madde numarası uydurulmasın, fıkra ya da bent kaymasın. Kılavuz Uygulama
Kılavuzu 6.2'yi alıntılamaz (metni programın kılavuzunun kullanmadığı bir ad taşır); yalnız
bölüm numarasıyla gönderir.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane import (
    ayin_kitaplari_belgesi,
    export_schema,
    katalog_dokumu,
    kisi_dokumu,
    okuma_odulu_belgesi,
    tmy_dokumleri,
)
from apps.kutuphane.models import (
    POPULAR_MIN_MEMBERS_MAX,
    POPULAR_MIN_MEMBERS_MIN,
    LibraryPolicy,
)
from apps.kutuphane.services import populer

_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_MEVZUAT = Path("docs") / "mevzuat"
_YONETMELIK = _MEVZUAT / "meb-okul-kutuphaneleri-yonetmeligi.md"
_UYGULAMA = _MEVZUAT / "meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md"
_TMY = _MEVZUAT / "tasinir-mal-yonetmeligi.md"
_KVKK = _MEVZUAT / "6698-kvkk.md"
_AYDINLATMA = Path("backend") / "templates" / "documents" / "aydinlatma_metni.html"

#: Bu uzunluktan kısa tırnaklı metinler ekran, seçici ve belge adıdır; alıntı sayılmaz.
_ALINTI_EN_AZ = 40


def _oku(yol: Path) -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _tek_bosluk(metin: str) -> str:
    return re.sub(r"\s+", " ", metin).strip()


def _bolum(kimlik: str) -> str:
    """Kılavuz bölümünün düz metni (etiketler ve JSX yorumları atılır)."""
    kaynak = _oku(_KILAVUZ)
    cikis = re.search(rf'<Bolum id="{kimlik}">(.*?)</Bolum>', kaynak, flags=re.DOTALL)
    assert cikis is not None, f"kılavuzda {kimlik} bölümü yok"
    govde = cikis.group(1).replace("&apos;", "'").replace('{" "}', " ")
    govde = re.sub(r"\{/\*.*?\*/\}", " ", govde, flags=re.DOTALL)
    return _tek_bosluk(re.sub(r"</?[A-Za-z][^<>]*>", "", govde))


def _madde(yol: Path, madde: int) -> str:
    metin = _oku(yol)
    cikis = re.search(
        rf'<a id="madde-{madde}"></a>(.*?)(?=<a id="madde-|\Z)', metin, flags=re.DOTALL
    )
    assert cikis is not None, f"{yol.name}: madde {madde} çapası yok"
    return _tek_bosluk(cikis.group(1))


def _fikra(yol: Path, madde: int, fikra: int) -> str:
    govde = _madde(yol, madde)
    bolum = re.search(rf"\({fikra}\) (.*?)(?= \({fikra + 1}\) |\Z)", govde)
    assert bolum is not None, f"{yol.name} md. {madde}/{fikra} yok"
    return bolum.group(1)


def _bent(fikra_metni: str, harf: str, sonraki: str) -> str:
    """Fıkranın `harf)` bendi (`sonraki)` bendine ya da fıkra sonuna dek)."""
    cikis = re.search(rf"(?:^| ){harf}\) (.*?)(?= {sonraki}\) |\Z)", fikra_metni)
    assert cikis is not None, f"{harf}) bendi yok"
    return cikis.group(1)


def _uygulama_bolumu(bas: str, son: str) -> str:
    metin = _tek_bosluk(_oku(_UYGULAMA))
    assert bas in metin and son in metin
    return metin[metin.index(bas) : metin.index(son)]


def _alintilar(metin: str) -> list[str]:
    """Bölümdeki uzun tırnaklı metinler; baştaki ve sondaki "…" atılır."""
    return [
        a.strip("… ").strip() for a in re.findall(r"“([^”]+)”", metin) if len(a) >= _ALINTI_EN_AZ
    ]


# ---------------------------------------------------------------------------
# Raporlar ve Çok Okunanlar
# ---------------------------------------------------------------------------
def test_raporlar_bolumundeki_her_alinti_atif_yapilan_metinde_birebir() -> None:
    metin = _bolum("raporlar")
    md_15_1 = _fikra(_YONETMELIK, 15, 1)
    kaynaklar = {
        "Yönetmelik Md. 7/1": _fikra(_YONETMELIK, 7, 1),
        "Yönetmelik Md. 15/1-ğ": _bent(md_15_1, "ğ", "h"),
        "Uygulama Kılavuzu 7": _uygulama_bolumu(
            "## 7. Kitap Okumanın", "## 8. Çeşitli ve Son Hükümler"
        ),
    }
    alintilar = _alintilar(metin)
    assert len(alintilar) == len(kaynaklar), alintilar
    for alinti in alintilar:
        assert any(alinti in kaynak for kaynak in kaynaklar.values()), alinti
    # Md. 7/1 fıkranın İLK cümlesidir; Kılavuz 7'nin alıntısı son maddenin ilk cümlesidir.
    md_7 = next(a for a in alintilar if a.startswith("Kitap sayısı"))
    assert kaynaklar["Yönetmelik Md. 7/1"].startswith(md_7)
    kilavuz_7 = next(a for a in alintilar if a.startswith("En çok kitap okuyan"))
    assert kaynaklar["Uygulama Kılavuzu 7"].rsplit(" - ", 1)[-1].startswith(kilavuz_7)


def test_raporlar_alintisiz_atiflari_metne_dayanir() -> None:
    metin = _bolum("raporlar")
    # Uygulama Kılavuzu 6.2 — "Ayın Kitapları" panosu (alıntısız; bölüm numarasıyla).
    assert "Uygulama Kılavuzu (6.2)" in metin
    assert "o ay en çok okunan kitapların tanıtıldığı bir “Ayın Kitapları” panosu" in metin
    bolum_6_2 = _uygulama_bolumu("### 6.2. Okul İçi", "## 7. Kitap Okumanın")
    assert 'o ay en çok okunan kitapların tanıtıldığı "Ayın Kitapları" panosu' in bolum_6_2
    # Kılavuz 7 ders başarısıyla ilişkilendirmeyi de önerir; program bunu yapmaz.
    assert "kütüphane kullanımını ders başarısıyla ilişkilendirmeyi de önerir" in metin
    bolum_7 = _uygulama_bolumu("## 7. Kitap Okumanın", "## 8. Çeşitli ve Son Hükümler")
    assert "kütüphane kullanımı" in bolum_7 and "ders başarıları" in bolum_7
    # KVKK md. 6 — özel nitelikli veri; işlenmesi yasak, istisnalar sayılı.
    assert "(6698 sayılı Kanun md. 6)" in metin
    assert "düşüncesi, inancı ya da sağlığı" in metin
    md_6_1 = _fikra(_KVKK, 6, 1)
    for ifade in (
        "siyasi düşüncesi",
        "felsefi inancı",
        "sağlığı",
        "özel nitelikli kişisel veridir",
    ):
        assert ifade in md_6_1, ifade
    assert "Özel nitelikli kişisel verilerin işlenmesi yasaktır" in _fikra(_KVKK, 6, 3)


def test_raporlar_belge_adlari_ve_cok_okunanlarin_sinirlari_koddan() -> None:
    metin = _bolum("raporlar")
    assert ayin_kitaplari_belgesi.BELGE_ADI in metin
    assert okuma_odulu_belgesi.BELGE_ADI in metin
    varsayilan = LibraryPolicy._meta.get_field("popular_min_members").default
    sinir = (
        f"{POPULAR_MIN_MEMBERS_MIN} ile {POPULAR_MIN_MEMBERS_MAX} arasında ayarlanır "
        f"(varsayılan {varsayilan})"
    )
    assert sinir in metin
    assert sinir in _bolum("katalog")
    # Pencere başına yazılan sıra sınırı (vitrin ve afiş).
    assert populer.EN_COK_SIRA == 10
    assert "Her listede en çok on eser yer alır." in metin


# ---------------------------------------------------------------------------
# Dökümler ve Dışa Aktarım
# ---------------------------------------------------------------------------
def test_dokumler_bolumundeki_her_alinti_atif_yapilan_fikrada_birebir() -> None:
    metin = _bolum("dokumler")
    md_9_1 = _fikra(_TMY, 9, 1)
    md_34_3 = _fikra(_TMY, 34, 3)
    kaynaklar = {
        "Yönetmelik Md. 11/1": _fikra(_YONETMELIK, 11, 1),
        # ç) Kütüphane Defteri, fıkranın son bendidir.
        "TMY md. 9/1-ç": _bent(md_9_1, "ç", "d"),
        "TMY md. 34/3-a": _bent(md_34_3, "a", "b"),
        "KVKK md. 11/1": _fikra(_KVKK, 11, 1),
    }
    alintilar = _alintilar(metin)
    assert len(alintilar) == len(kaynaklar), alintilar
    for alinti in alintilar:
        assert any(alinti in kaynak for kaynak in kaynaklar.values()), alinti
    # Bent kaymasın: 9/1-ç "Kütüphane Defteri" bendidir; 34/3-a alıntısı bendin ilk cümlesidir.
    assert "ç) Kütüphane Defteri: Bu defter" in md_9_1
    assert kaynaklar["TMY md. 34/3-a"].startswith(
        "Sayım kurulu tarafından onaylanan Taşınır Sayım ve Döküm Cetveline dayanılarak"
    )
    # KVKK 11/1: giriş + a ve b bentleri, sonu "…".
    assert (
        "a) Kişisel veri işlenip işlenmediğini öğrenme, b) Kişisel verileri işlenmişse"
        in (kaynaklar["KVKK md. 11/1"])
    )


def test_dokumler_alintisiz_atiflari_fikranin_metnine_dayanir() -> None:
    metin = _bolum("dokumler")
    # TMY 10/1-a-4: süreli yayın için Varlık İşlem Fişi düzenlenmez (ciltletilmiş olan hariç).
    assert (
        "dergi ve gazete gibi süreli yayınlar için Varlık İşlem Fişi düzenlenmez (md. 10/1-a-4)"
        in (metin)
    )
    md_10_1 = _fikra(_TMY, 10, 1)
    assert "süreli yayınlardan ciltletilmiş olanlar hariç" in md_10_1
    assert "4) Dergi ve gazete gibi süreli yayınlar" in _bent(md_10_1, "a", "b")
    # TMY 15/4: cilt birliği sağlananlar ciltletildikten sonra kayda alınır.
    assert "cilt birliği sağlananlar ciltletildikten sonra kayda alınır (md. 15/4)" in metin
    assert "cilt birliği sağlananlar, ciltletildikten sonra" in _fikra(_TMY, 15, 4)
    # TMY 34/1: yönetim hesabının büyüklükleri.
    assert "Taşınır mal yönetim hesabının büyüklükleri (md. 34/1)" in metin
    assert "önceki yıldan devredilen, yılı içinde giren, çıkan ve ertesi yıla devredilen" in (
        _fikra(_TMY, 34, 1)
    )
    # TMY 34/2-c ve 34/3-a ikinci cümle: Kütüphane Yönetim Hesabı Cetveli kimin hesabındadır.
    assert "kütüphane olarak faaliyet gösteren harcama birimlerinin hesabındadır (md. 34/2-c)" in (
        metin
    )
    assert "kütüphane olarak faaliyet gösteren harcama birimlerinde Müze/Kütüphane Yönetim" in (
        _bent(_fikra(_TMY, 34, 2), "c", "ç")
    )
    assert "gerekli görürse bu cetveli ayrıca düzenleyebilir (md. 34/3-a)" in metin
    assert "kütüphane materyalleri bulunan kamu idareleri, gerekli görülmesi hâlinde" in (
        _bent(_fikra(_TMY, 34, 3), "a", "b")
    )
    # KVKK 13/2: otuz gün.
    assert "en geç otuz gün içinde sonuçlandırılır (md. 13/2)" in metin
    assert "en geç otuz gün içinde" in _fikra(_KVKK, 13, 2)


def test_dokumler_adlari_koddan() -> None:
    metin = _bolum("dokumler")
    for ad in (
        katalog_dokumu.BELGE_ADI,
        tmy_dokumleri.DEFTER_ADI,
        tmy_dokumleri.HESAP_ADI,
        kisi_dokumu.BELGE_ADI,
    ):
        assert ad in metin, ad
    for eksen in katalog_dokumu.AXES.values():
        assert f"“{eksen}”" in metin, eksen
    assert f"“{katalog_dokumu.KONUSUZ}”" in metin
    assert f"“{katalog_dokumu.YAZARSIZ}”" in metin
    for sayfa in (
        export_schema.INFO_SHEET,
        export_schema.COUNTERS_SHEET,
        export_schema.MEMBER_SUMMARY_SHEET,
    ):
        assert f"“{sayfa}”" in metin, sayfa
    # "İlk on altı sütun katalog Excel şablonunun sütunlarıdır" (docs/disa-aktarim.md).
    assert len(export_schema.BASE_COLUMNS) == 16
    assert "İlk on altı sütun katalog Excel şablonunun sütunlarıdır" in metin
    # Kişi dökümü: saklama süresi dolan kayıtlar görünmez (belgenin notuyla aynı kural).
    assert "bu dökümde görünmez" in kisi_dokumu.SAKLAMA_NOTU
    assert "kişiyle bağı koparılmış kayıtlar dökümde görünmez" in metin


def test_bakanlik_sistemi_ayari_adi_varsayilani_ve_aydinlatma_metni() -> None:
    metin = _bolum("dokumler")
    alan = LibraryPolicy._meta.get_field("ministry_system_in_use")
    assert alan.default is False
    assert f"“{alan.verbose_name}”" in metin
    assert "Ayar varsayılan olarak kapalıdır ve yalnız hatırlatma açar" in metin
    # Hatırlatmanın çıktığı ekranların ve ayarın bölümleri ayarı adıyla anar.
    for kimlik in ("kisiler", "ilisik", "katalog"):
        assert f"“{alan.verbose_name}”" in _bolum(kimlik), kimlik
    # Kılavuzun aydınlatma metnine dair cümlesi belgenin kendisine dayanır.
    assert (
        "Kütüphane aydınlatma metni, Bakanlık sistemi okulda kullanıma girdiğinde kayıtların "
        "okul müdürlüğünce o sisteme aktarılabileceğini söyler"
    ) in metin
    aydinlatma = _tek_bosluk(_oku(_AYDINLATMA))
    assert "Bakanlık otomasyon sistemi okulda kullanıma girdiğinde kayıtlar" in aydinlatma
    assert "okul müdürlüğünce aktarılabilir" in aydinlatma
    # Konum dili (CLAUDE.md §2-13): program o sistemin yerine geçmez.
    assert "yerine geçer" not in metin.replace("yerine geçmez", "")


# ---------------------------------------------------------------------------
# Sayım ve Yedek bölümlerinin F10 ekleri
# ---------------------------------------------------------------------------
def test_sayim_bolumunun_yil_sonu_isareti_atiflari_metne_dayanir() -> None:
    metin = _bolum("sayim")
    assert "Cetvel yıl sonu hesabı için düzenlenir (md. 10/1-ğ, 32/9)" in metin
    assert "yıl sonu hesaplarına" in _bent(_fikra(_TMY, 10, 1), "ğ", "h")
    assert "yıl sonu hesabını oluşturur" in _fikra(_TMY, 32, 9)
    assert "harcama yetkilisinin gerekli gördüğü ara sayımdır (md. 32/1)" in metin
    assert "harcama yetkilisinin gerekli gördüğü durum ve zamanlarda" in _fikra(_TMY, 32, 1)


def test_yeni_bilgisayara_tasima_kurulum_belgesiyle_ayni_yolu_anlatir() -> None:
    metin = _bolum("yedek")
    kurulum = _tek_bosluk(_oku(Path("docs") / "kurulum.md"))
    assert "## 7. Yeni bilgisayara taşıma" in kurulum
    for yol in (
        r"%LOCALAPPDATA%\KutuphaneDefteri\backups",
        "~/.local/share/kutuphane-defteri/backups",
    ):
        assert yol in metin and yol in kurulum, yol
    assert "“Kütüphane Defteri — Yedekten Geri Yükle”" in metin
    assert "Kütüphane Defteri — Yedekten Geri Yükle" in kurulum
    assert "kutuphane-defteri --geri-yukle" in metin
