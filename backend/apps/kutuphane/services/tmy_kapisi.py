"""TMY 32/3 durdurmasının kapı noktası (tasarım §9-10, D4, D17, D18) — F9'da doldu.

TMY 32/3: "Sayım süresince, hizmetin aksamaması ve bozulabilecek nitelikteki
taşınırlar için gerekli tedbirlerin alınması kaydıyla, taşınır giriş ve çıkışları
sayım kurulunun talebi üzerine harcama yetkilisince durdurulabilir." Durdurma
İSTEĞE BAĞLIDIR (D18): sayım başlatılırken seçilir (kurulun talep tarihi +
harcama yetkilisinin adı ve tarihi — `StockTake.tmy_stop`) ve seçildiyse sayım
"Sürüyor" ya da "Tamamlandı" iken, yani onaya ya da iptale DEK sürer (D17).

Yalnız TMY anlamında giriş ve çıkış olan işlemleri kapsar: **edinim ve yeni
nüsha** (`EDINIM` — `services.catalog`: edinim partisi açma ve her yeni nüsha;
bağış kataloglaması, içe aktarım ve boş etiket bağlama da bu yoldan geçer),
**kayıttan düşme** ve **devir** (`services.weeding.apply_batch`), **kayıp
bildirimi** ve **kayıp dosyası çözümü** (D4: OYS'nin sayım kilidi `report_lost` ile
`resolve_case`'i kapsamıyordu). Sayımın kendi onayı (noksanın düşümü — 32/7,
fazlanın girişi — TMY 17) kilidi önce kaldırır, sonra işler.

**Programa aktarım** (`PROGRAMA_AKTARIM`; "Mevcut koleksiyon (programa aktarım)"
edinim yolu — içe aktarım, Hızlı Kayıt ve bu yoldaki edinim partisi) taşınır girişi
DEĞİLDİR (raftaki eski koleksiyonun programa girişidir), ama durdurma süresince yine
kapalıdır: ret iletisi TMY'ye DAYANDIRILMAZ ("Sayım sürerken programa aktarım
yapılamaz; sayım bitince aktarın."), kodu da ayrıdır (`RED_KODU_AKTARIM`). F9 ekleri
K4 (25.09.2026 ana oturum kararı, seçenek b). Hangi yolun hangi işleme düştüğünü
`edinim_islemi` söyler.

Dosya çözümlerinden hangisinin kapıdan geçeceğini `dosya_cozumu_kapsamda_mi`
söyler (F7 ekleri 17, F9 ekleri K1): nüshanın envanterdeki yerini değiştiren ya da
kayıttan düşme önerisi yazan çözümler kapsamdadır. Kapsam dışı: kayıp dosyasında
kitabın BULUNMASI ("Bulundu", "Bulundu (bedel teslim alınmıştı)" — kayıptaki kitabın
rafa dönüşü taşınır giriş-çıkışı değildir; nüsha kayıttan düşülmediyse kayıtta zaten
vardır; K1) ve Md. 19'un iki bedel adımı ("Bedel belirlendi", "Bedel teslim
alındı"); hasar dosyasının onarımla ya da aynısının teminiyle kapanması (nüshanın
kaydı değişmez; onarım da bedelin belirlenmesi ve teslim alınması da TMY'de
giriş-çıkış değildir — F7 ekleri 17 ve 26).

Kapsamadıkları (bilinçli): ödünç ve iade (TMY'de giriş-çıkış değildir — 13/1,
23/4), teslim ve geri alma (ödünç değildir ama çıkış da değildir; 23/6'ya
kıyasen kullanıma veriliştir), onarım. "Sayım için hizmet arası" ayrı bir okul
kararıdır ve yeni ödüncü ve yeni teslimi durdurur; bu kapıyla ilgisi yoktur. **İade
ve geri alma hiçbir durumda kilitlenmez.**
"""

from __future__ import annotations

from typing import Final

from django.core.exceptions import ValidationError

from apps.kutuphane import selectors_sayim
from apps.kutuphane.models import (
    FOUND_RESOLUTIONS,
    WRITE_OFF_RESOLUTIONS,
    AcquisitionMethod,
    CaseResolution,
    CaseType,
)

#: Kapıdan geçen işlemlerin adları (F9 tutanağı ve iletisi bunlara göre yazılır).
KAYIP_BILDIRIMI: Final = "kayip_bildirimi"
DOSYA_COZUMU: Final = "kayip_hasar_dosyasi_cozumu"
#: F8 — ayıklama teklifinin uygulanması: kayıttan düşme (TMY 27/1, 28) ve devir
#: (24/2, 31) TMY anlamında çıkıştır; ikisi de kapıdan geçer (`services.weeding`).
KAYITTAN_DUSME: Final = "kayittan_dusme"
DEVIR: Final = "devir"
#: F9 — edinim partisi açma ve yeni nüsha (taşınır girişi; `services.catalog`).
EDINIM: Final = "edinim"
#: F9 ekleri K4 — mevcut koleksiyonun programa aktarımı (taşınır girişi DEĞİL).
PROGRAMA_AKTARIM: Final = "programa_aktarim"

#: TMY 32/3'e dayanan işlemlerin iletideki adları (kullanıcı metni — sözlük; iç kod
#: yazılmaz). Programa aktarım burada YOKTUR: onun iletisi TMY'ye dayanmaz.
ISLEM_ADLARI: Final[dict[str, str]] = {
    EDINIM: "edinim ve yeni nüsha kaydı",
    KAYITTAN_DUSME: "kayıttan düşme",
    DEVIR: "devir",
    KAYIP_BILDIRIMI: "kayıp bildirimi",
    DOSYA_COZUMU: "kayıp/hasar dosyası çözümü",
}
#: Kapının ret kodu (`ValidationError.code`; test ve belge için kararlıdır).
RED_KODU: Final = "tmy_32_3_durdurmasi"
#: Programa aktarımın ret kodu — TMY'ye dayanmaz (K4).
RED_KODU_AKTARIM: Final = "sayim_programa_aktarim"
#: Son cümle durumu değil KAPSAMI söyler (F9 düzeltme turu): sayım için hizmet arası da
#: seçildiyse yeni ödünç o yüzden kapalıdır; "ödünç açıktır" demek yanlış olurdu.
STOP_MESSAGE: Final = (
    "TMY 32/3 durdurması süresince {islem} yapılamaz. Durdurma, sayım onaylanınca ya da "
    "iptal edilince kalkar. Durdurma ödüncü ve iadeyi kapsamaz."
)
#: K4 (b): programa aktarım durdurma süresince kapalıdır ama ileti TMY'ye dayandırılmaz.
PROGRAMA_AKTARIM_MESSAGE: Final = (
    "Sayım sürerken programa aktarım yapılamaz; sayım bitince aktarın."
)

#: Md. 19 bedel ADIMLARI — dosyayı kapatmaz, nüshanın kaydına dokunmaz (kapsam dışı).
BEDEL_ADIMLARI: Final[tuple[str, ...]] = (
    CaseResolution.PRICE_DETERMINED,
    CaseResolution.PRICE_RECEIVED,
)


def edinim_islemi(method: object) -> str:
    """Edinim yolunun kapıdaki işlemi: "Mevcut koleksiyon (programa aktarım)" →
    `PROGRAMA_AKTARIM`, Md. 10/5 yolları ve sayım fazlası → `EDINIM` (K4)."""
    return PROGRAMA_AKTARIM if method == AcquisitionMethod.EXISTING_STOCK else EDINIM


def dosya_cozumu_kapsamda_mi(case_type: str, resolution: str) -> bool:
    """Bu dosya çözümü TMY 32/3 durdurmasının kapsamında mı? (§9-10 "kayıp dosyası çözümü")

    - Kayıp dosyası: bulunma ("Bulundu", "Bulundu (bedel teslim alınmıştı)" — K1) ve iki
      bedel adımı ("Bedel belirlendi", "Bedel teslim alındı") DIŞINDAKİ çözümler: aynısının
      teminiyle nüsha "Kayıp"tan rafa döner ("Aynısı temin edildi", "Bedelle aynısı
      alındı") ya da kayıttan düşme önerilir ("Kayıttan düşme önerildi", "Bedelle başka
      eser alındı").
    - Hasar dosyası: yalnız kayıttan düşme önerisi yazan çözümler. "Onarıldı",
      "Aynısı temin edildi", "Bedelle aynısı alındı" ve bedel adımları nüshanın
      kaydını değiştirmez (onarım kapsam dışıdır).
    """
    if resolution in WRITE_OFF_RESOLUTIONS:
        return True
    return (
        case_type == CaseType.LOST
        and resolution not in BEDEL_ADIMLARI
        and resolution not in FOUND_RESOLUTIONS
    )


def durdurma_iletisi(islem: str) -> str:
    """Durdurma sürüyorsa işlemin ret iletisi, sürmüyorsa boş metin (YAZMAYAN ön denetimler).

    Hızlı kayıt etiketi ÖNCE denetler (`barcode_reservations.check_label`): durdurma
    sürerken eser açılıp nüshasız kalmasın diye ret burada da verilir (F9 düzeltme turu).
    Programa aktarımın iletisi TMY'ye dayanmaz (K4).
    """
    if not selectors_sayim.tmy_stop_active():
        return ""
    if islem == PROGRAMA_AKTARIM:
        return PROGRAMA_AKTARIM_MESSAGE
    return STOP_MESSAGE.format(islem=ISLEM_ADLARI.get(islem, "bu işlem"))


def ensure_open(islem: str) -> None:
    """İşlem TMY 32/3 durdurmasına takılıyor mu? Takılıyorsa Django `ValidationError`.

    Süren (kilitleri açık — "Sürüyor" ya da "Tamamlandı") bir sayımda durdurma
    seçilmişse 400 + Türkçe ileti (`STOP_MESSAGE`; kod `RED_KODU` — programa aktarımda
    `PROGRAMA_AKTARIM_MESSAGE`, kod `RED_KODU_AKTARIM`). Durdurma yoksa ya da sayım
    onaylanmış/iptal edilmişse sessizce geçer. İmza F7'den beri değişmedi; dosya
    çözümünde kapı yalnız `dosya_cozumu_kapsamda_mi` doğru olduğunda sorulur. Ödünç ve
    iade bu kapıdan HİÇ geçmez.
    """
    ileti = durdurma_iletisi(islem)
    if ileti:
        kod = RED_KODU_AKTARIM if islem == PROGRAMA_AKTARIM else RED_KODU
        raise ValidationError(ileti, code=kod)
