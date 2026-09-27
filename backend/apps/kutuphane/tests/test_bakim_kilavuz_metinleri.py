"""F11 bakım kolu kılavuz metinleri ↔ mevzuat ve kod ("Görev Devri", "Güncelleme"; "Yedek ve
Güvenlik Dosyası" bölümünün F11 ekleri).

Kılavuz (`frontend/src/modules/kilavuz/KilavuzPage.tsx`) sunucunun sabitlerini birebir yazar:
dış yedek hatırlatmasının süreleri, görev devri notunun ad ve not sınırları, güncelleme
denetimi GitHub'a ulaşamadığında çıkan ileti (kullanıcı kararı 27.09.2026). Kod bir sayıyı ya
da iletiyi değiştirirse kılavuz da değişmek zorunda kalır.

Mevzuat (CLAUDE.md §2-13): alıntı atıf yapılan fıkrada BİREBİR aranır; alıntısız atıfların
dayandığı ifadeler de fıkranın metninde aranır. Sözlük §1: "imha" bu bölümlerde geçmez.

Kılavuz ve sözlük kolu (F11) buna "Saklama ve Anonimleştirme" bölümünü (tasarım §6.4: süreler
`LibraryPolicy`'nin varsayılanlarından, altı ay `saklama.AZAMI_BEKLEME_AY`'dan, ibare
`belge_izi`'nden; KVKK 4/2-d birebir, 7/1 alıntısız; Silme Yönetmeliği anılmaz), Yedek bölümünün
"USB bellekteki yedekler" ve "Geri yükleme provası" parçalarını (Yönerge 10/5, KVKK 12/5) ve
`docs/kurulum.md`'yi (çıkış kodları `desktop/errors.py` ile birebir, §6.3 ile kılavuz aynı
düzeni yazar) ekler.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.core.validators import BaseValidator
from django.db import models

from apps.kutuphane import belge_izi
from apps.kutuphane.models import LibraryPolicy
from apps.kutuphane.services import saklama
from apps.kutuphane.tests.test_rapor_dokum_kilavuz_metinleri import (
    _KVKK,
    _MEVZUAT,
    _alintilar,
    _bent,
    _bolum,
    _fikra,
    _oku,
    _tek_bosluk,
)
from apps.okul.services import backup_restore, dis_yedek, updates

_YONERGE = _MEVZUAT / "meb-bilgi-ve-sistem-guvenligi-yonergesi.md"
_KURULUM = Path("docs") / "kurulum.md"


def test_gorev_devri_kvkk_12_4_atfi_fikraya_dayanir() -> None:
    """Alıntısız atıf (kılavuz "yükümlülük" sözcüğünü kullanmaz — F7 sözlük kararı)."""
    bolum = _bolum("gorev-devri")
    assert "(KVKK md. 12/4)" in bolum
    fikra = _fikra(_KVKK, 12, 4)
    for ifade in (
        "öğrendikleri kişisel verileri bu Kanun hükümlerine aykırı olarak başkasına açıklayamaz",
        "işleme amacı dışında kullanamazlar",
        "görevden ayrılmalarından sonra da devam eder",
    ):
        assert ifade in fikra, ifade
    # Bölümde uzun tırnaklı alıntı yok (tek tırnaklı metin zarf yazısıdır).
    assert all(a.startswith("Eski anahtar") for a in _alintilar(bolum))


def test_gorev_devri_yonerge_6_4_atfi_fikraya_dayanir() -> None:
    bolum = _bolum("gorev-devri")
    assert "(Yönerge md. 6/4)" in bolum
    fikra = _fikra(_YONERGE, 6, 4)
    for ifade in (
        "çalışmalarının sonlandırılması ile birlikte",
        "bilişim sistemleri kullanımına yönelik tüm şifreleri",
        "erişim hakları kaldırılır",
    ):
        assert ifade in fikra, ifade


def test_gorev_devri_bolumu_durust_siniri_ve_akisi_yazar() -> None:
    bolum = _bolum("gorev-devri")
    for ifade in (
        "Görev devrini başlat",
        "Parolayı ve anahtarı yenile",
        "Görev devri notunu indir",
        "şifreleme anahtarını değiştirmez",
        "eski parola ve eski kurtarma anahtarıyla açılabilir",
        "14 gün içinde kendiliğinden silinir",
        "Adlar programda saklanmaz",
        "yırtarak yok edin",
        # F11 düzeltme turu: DEK değişmediği için eski parola eski bir başlıkla devirden
        # SONRAKİ yedekleri de açar (test_gorev_devri.py::test_sinir_…); masa hesabı değişir.
        "devirden sonra alınan yedekleri de",
        "Windows hesabının parolasını da değiştirin",
        "Görev devrini yeniden başlat",
    ):
        assert ifade in bolum, ifade
    assert "kilidi artık açmaz" not in bolum
    # Atıf fıkranın öznesine bağlı: 12/4 veri sorumlusu ve veri işleyenleri anlatır (okulun
    # personeli 3/1-ğ'deki "veri işleyen" değildir); 6/4 çalışması sona ereni, kıyasla.
    assert "Veri sorumlusu okuldur" in bolum
    assert "Çalışması sona eren kullanıcı" in bolum and "kıyasen uygulanır" in bolum
    assert "Görevi sona eren kullanıcı" not in bolum
    assert "Veri işleyen: Veri sorumlusunun verdiği yetkiye dayanarak" in _fikra(_KVKK, 3, 1)
    # Sözlük §1: "imha" yalnız imha tutanağı bağlamında; "devreden" kişi hep "görevi …".
    assert not re.search(r"[iİ]mha", bolum)


def test_yedek_bolumu_dis_yedek_surelerini_sunucudan_yazar() -> None:
    bolum = _bolum("yedek")
    assert f"Son indirmeden {dis_yedek.VARSAYILAN_HATIRLATMA_GUN} gün geçince" in bolum
    assert f"kurulduktan {dis_yedek.ILK_HATIRLATMA_GUN} gün sonra" in bolum
    assert (
        f"{dis_yedek.EN_AZ_HATIRLATMA_GUN} ile {dis_yedek.EN_COK_HATIRLATMA_GUN} gün arasında"
        in bolum
    )
    assert "Şifreli Yedeği USB Belleğe Alın" in bolum
    # Taşıma kontrol listesi kart defterini de taşır (TB33) ve prova anlatılır.
    assert "verilmis-kartlar.txt" in bolum
    assert "geri yükleme provası" in bolum
    assert not re.search(r"[iİ]mha", bolum)


def test_yedek_bolumu_yonerge_10_5_atfi_fikraya_dayanir() -> None:
    assert "(Yönerge md. 10/5:" in _bolum("yedek")
    fikra = _fikra(_YONERGE, 10, 5)
    assert "USB veya harici diske gizli/önemli verilerin konulması gerekiyorsa" in fikra
    assert "kriptolanarak/şifrelenerek saklanır" in fikra


def test_guncelleme_bolumu_ulasilamama_iletisini_sunucudan_birebir_yazar() -> None:
    bolum = _bolum("guncelleme")
    assert updates.ULASILAMADI_MESAJI in bolum
    assert "Şimdi denetle" in bolum
    assert "açılışta ve kendi başına internete çıkmaz" in bolum
    assert "o adrese kendisi istek atmaz" in bolum


# ---------------------------------------------------------------------------
# Saklama ve Anonimleştirme (F11 — tasarım §6.4 BAĞLAYICI)
# ---------------------------------------------------------------------------
def _varsayilan(alan: str) -> int:
    """Alanın varsayılanı (kaydedilmemiş örnek veritabanına gitmez)."""
    return int(getattr(LibraryPolicy(), alan))


def _sinirlar(alan: str) -> list[int]:
    """Alanın en az ve en çok değeri (doğrulayıcılardan)."""
    alan_tanimi = LibraryPolicy._meta.get_field(alan)
    assert isinstance(alan_tanimi, models.Field)
    return sorted(
        int(d.limit_value) for d in alan_tanimi.validators if isinstance(d, BaseValidator)
    )


def test_saklama_bolumunun_tek_alintisi_kvkk_4_2_d_birebir() -> None:
    bolum = _bolum("saklama")
    alintilar = _alintilar(bolum)
    kanun_4_2_d = _bent(_fikra(_KVKK, 4, 2), "d", "e")
    kvkk = [a for a in alintilar if a.startswith("İlgili mevzuatta")]
    assert len(kvkk) == 1
    assert kvkk[0] in kanun_4_2_d
    # Öbür uzun tırnaklı metinler ekran adları ve belge ibaresidir (alıntı değildir).
    for alinti in alintilar:
        if alinti not in kvkk:
            assert alinti in {
                belge_izi.ANONIM_KOPYA_IBARESI,
                "Kişiyle bağı koparılacak (kayıt kalır)",
                "Bu işlemin geri alınamayacağını anladım",
            }, alinti


def test_saklama_bolumunun_kvkk_7_1_atfi_fikraya_dayanir() -> None:
    bolum = _bolum("saklama")
    assert "(KVKK md. 7/1)" in bolum
    fikra = _fikra(_KVKK, 7, 1)
    for ifade in ("işlenmesini gerektiren sebeplerin ortadan kalkması", "silinir, yok edilir"):
        assert ifade in fikra, ifade
    assert "anonim hâle getirilir" in fikra
    # Silme Yönetmeliği depoda yok: atıf yapılmaz (tasarım §6.4-4, docs/mevzuat/BENIOKU.md §2).
    assert "Yönetmeliği" not in bolum
    assert not re.search(r"[iİ]mha", bolum)


def test_saklama_bolumu_sureleri_ve_sinirlari_koddan_yazar() -> None:
    bolum = _bolum("saklama")
    beklenen = {
        "retention_years_left_person": "ayrılıştan {} yıl sonra kaydı silinir",
        "retention_years_after_termination": "sona ermesinden {} yıl sonra üyelik kaydı silinir",
        "retention_years_returned_loans": "ders yılının sonundan {} yıl sonra",
        "retention_years_closed_cases": "kapanışından {} yıl sonra",
        "retention_years_closed_deliveries": "geri alınmasından {} yıl sonra",
    }
    for alan, kalip in beklenen.items():
        assert kalip.format(_varsayilan(alan)) in bolum, alan
        assert _sinirlar(alan) == [1, 10], alan
    assert "(1 ile 10 yıl arası)" in bolum
    assert saklama.AZAMI_BEKLEME_AY == 6
    assert "altı aydan uzun" in bolum
    assert belge_izi.ANONIM_KOPYA_IBARESI in bolum


def test_saklama_bolumu_yedeklerdeki_kalintiyi_rotasyonla_ayni_soyler() -> None:
    from desktop import backup

    bolum = _bolum("saklama")
    assert backup.DEFAULT_KEEP_DAYS == 14
    assert f"{backup.PRE_ANONIM_PREFIX}-…" in bolum
    assert f"{backup.PRE_MIGRATE_PREFIX}-…" in bolum
    assert "14 gün sonra kendiliğinden silinir" in bolum
    assert "yedek alınamazsa işlem yapılmaz" in bolum
    # Rotasyon yalnız kendi adlarını yönetir: elle konan dosyaya dokunmaz. Önceki veritabanı
    # dosyalarını saklama tetiği siler: tetik anından 14 günden eskileri (27.09.2026 kullanıcı
    # kararı — `saklama.onceki_veritabani_siniri`, süre günlük yedeklerinkiyle aynı sabit).
    assert "elle koyduğunuz dosyalara program dokunmaz" in bolum
    assert f"{backup_restore.OLD_DB_PREFIX}-…" in bolum
    assert f"{backup.DEFAULT_KEEP_DAYS} günden eski olanları da siler" in bolum
    assert "Daha yenileri yakın tarihli bir geri yüklemeden dönüş için kalır" in bolum
    assert "Ne kalır" in bolum
    assert "onay görevi devralana kalır" in bolum


# ---------------------------------------------------------------------------
# Yedek bölümü: USB bellekteki yedekler ve geri yükleme provası (F11)
# ---------------------------------------------------------------------------
def test_usb_bellekteki_yedekler_okulun_sorumlulugu_ve_yonerge_10_5() -> None:
    bolum = _bolum("yedek")
    # F11 düzeltme turu: 10/5'in öznesi PERSONELDİR — atıf personelin cümlesine bağlanır;
    # okulun (veri sorumlusu) sorumluluğu ve müdürlüğün düzeni ayrı söylenir.
    assert "okulun sorumluluğundadır: düzeni okul müdürlüğü belirler" in bolum
    assert "güvenliğini onu kullanan personel sağlar (Yönerge md. 10/5:" in bolum
    fikra = _fikra(_YONERGE, 10, 5)
    assert fikra.lstrip("(5) ").startswith("Personel,")
    assert "USB belleğindeki" in fikra
    assert "güvenliğini sağlamakla yükümlüdür" in fikra
    # "Yükümlülük" kılavuzun kullanmadığı sözcüktür (F7 sözlük kararı).
    assert "yükümlü" not in bolum.casefold()
    for ifade in (
        "Önerilen düzen",
        "son iki yedeği tutun",
        "Okul müdürlüğü başka bir düzen belirleyebilir",
        "Saklama işleminden sonra yeni bir şifreli yedek alın",
        "Görev devrinden sonra da yeni bir şifreli yedek alın",
        "İndirilenler klasörüne",
    ):
        assert ifade in bolum, ifade


def test_kayip_bellek_kvkk_12_5_atfi_fikraya_dayanir() -> None:
    bolum = _bolum("yedek")
    assert "(KVKK md. 12/5)" in bolum
    assert "okul müdürlüğü değerlendirir" in bolum
    fikra = _fikra(_KVKK, 12, 5)
    for ifade in (
        "kanuni olmayan yollarla başkaları tarafından elde edilmesi",
        "ilgilisine ve Kurula bildirir",
    ):
        assert ifade in fikra, ifade


def test_geri_yukleme_provasi_adimlari_ve_temizligi() -> None:
    bolum = _bolum("yedek")
    for ifade in (
        "Geri yükleme provası",
        "başka bir demirbaş bilgisayarında",
        "kurtarma anahtarını yazın",
        "Provada kayıt girmeyin",
        "kaldırmak bu klasörleri silmez",
        "kopyaladığınız dosyayı silin",
    ):
        assert ifade in bolum, ifade


def test_gorev_devri_eski_kagit_yonerge_10_3_atfi_fikraya_dayanir() -> None:
    bolum = _bolum("gorev-devri")
    assert "(Yönerge md. 10/3)" in bolum
    assert "gizli bilgi içeren atık evrakı" in _fikra(_YONERGE, 10, 3)
    # Fıkra "imha eder" der; kılavuz sözlük §1 gereği "yok edilir" diye aktarır.
    assert "gizli bilgi içeren atık evrak yok edilir" in bolum
    assert "devirden önce alınmış USB yedeklerini silin" in bolum


def test_guncelleme_bolumu_hedefi_ve_indirme_alanini_adlandirir() -> None:
    bolum = _bolum("guncelleme")
    assert "GitHub sayfasına sorulur" in bolum
    assert updates.INDIRME_ALANI in bolum
    assert "Doğrula ve indir" in bolum


# ---------------------------------------------------------------------------
# docs/kurulum.md (F11: taşıma, geri yükleme provası, USB yedekleri, çıkış kodları)
# ---------------------------------------------------------------------------
def test_kurulum_cikis_kodlari_tablosu_errors_ile_birebir() -> None:
    from desktop import errors

    kurulum = _oku(_KURULUM)
    tablo = kurulum[kurulum.index("## 11. Çıkış kodları") : kurulum.index("## 12.")]
    kodlar = {int(k) for k in re.findall(r"^\| (\d+) \|", tablo, flags=re.MULTILINE)}
    tanimli = {
        deger
        for ad, deger in vars(errors).items()
        if ad.startswith("EXIT_") and isinstance(deger, int)
    }
    assert kodlar == tanimli
    satir_4 = re.search(r"^\| 4 \| (.*)$", tablo, flags=re.MULTILINE)
    assert satir_4 is not None
    assert "geri yüklendiyse" in satir_4.group(1)
    assert errors.EXIT_SCHEMA_TOO_NEW == 4
    assert f'### 10.4 "{errors.SchemaTooNewError.title}"' in kurulum


def test_kurulum_saklama_ve_usb_duzeni_kilavuzla_ayni() -> None:
    kurulum = _tek_bosluk(_oku(_KURULUM))
    kilavuz = _bolum("yedek")
    assert "### 6.3 Saklama işlemi ve USB bellekteki yedekler" in kurulum
    assert "### 7.1 Geri yükleme provası" in kurulum
    for ifade in ("son iki yedeği", "(KVKK md. 12/5)", "Yönergesi md. 10/5"):
        assert ifade in kurulum, ifade
    assert "son iki yedeği" in kilavuz
    assert "pre-anonim-<tarih>-<saat>" in kurulum
    # Sözlük §1: "imha" okulun kendi kopyaları için kullanılmaz; düğme "Şimdi denetle"dir.
    assert not re.search(r"[iİ]mha", kurulum)
    assert '"Denetle"' not in kurulum
    assert '"Şimdi denetle"' in kurulum


@pytest.mark.parametrize(
    "ifade",
    [
        "kendiliğinden hiçbir şey silmez",
        "`backups` klasörüne kopyaladığınız yedek dosyasını silin",
        "kurtarma anahtarını",
        "okulapp.org/kutuphane-defteri",
    ],
)
def test_kurulum_belgesi_f11_adimlarini_yazar(ifade: str) -> None:
    assert ifade in _tek_bosluk(_oku(_KURULUM))
