"""TMY 32/3 durdurmasının kapı noktası — F7'de BOŞTUR, F9 doldurur (tasarım §9-10, D4).

Sayım başlatılırken isteğe bağlı olarak seçilen **TMY 32/3 durdurması** (kurul
talebi + harcama yetkilisinin adı ve tarihi) yalnız TMY anlamında giriş ve çıkış
olan işlemleri kapsar: edinim ve yeni nüsha, kayıttan düşme, devir ve **kayıp
dosyası çözümü** (§9-10). OYS'nin sayım kilidi `report_lost` ile `resolve_case`'i
kapsamıyordu (D4); bu projede o iki yol F7'den başlayarak bu kapıdan geçer ki F9
kilidi tek yerden bağlasın.

Dosya çözümlerinden hangisinin kapıdan geçeceğini `dosya_cozumu_kapsamda_mi`
söyler (F7 düzeltme turu): nüshanın envanterdeki yerini değiştiren ya da
kayıttan düşme önerisi yazan çözümler kapsamdadır; hasar dosyasının onarımla ya
da aynısının teminiyle kapanması ve Md. 19'un iki bedel adımı ("Bedel
belirlendi", "Bedel teslim alındı") kapsam dışıdır (nüshanın kaydı değişmez;
onarım da bedelin belirlenmesi ve teslim alınması da TMY'de giriş-çıkış
değildir — F7 ekleri 17 ve 26).

Kapsamadıkları (bilinçli): ödünç ve iade (TMY'de giriş-çıkış değildir — 13/1,
23/4), teslim ve geri alma (ödünç değildir ama çıkış da değildir; 23/6'ya
kıyasen kullanıma veriliştir), onarım. "Sayım için hizmet arası" ayrı bir okul
kararıdır ve yalnız yeni ödüncü durdurur; bu kapıyla ilgisi yoktur. **İade ve
geri alma hiçbir durumda kilitlenmez.**
"""

from __future__ import annotations

from typing import Final

from apps.kutuphane.models import WRITE_OFF_RESOLUTIONS, CaseResolution, CaseType

#: Kapıdan geçen işlemlerin adları (F9 tutanağı ve iletisi bunlara göre yazılır).
KAYIP_BILDIRIMI: Final = "kayip_bildirimi"
DOSYA_COZUMU: Final = "kayip_hasar_dosyasi_cozumu"

#: Md. 19 bedel ADIMLARI — dosyayı kapatmaz, nüshanın kaydına dokunmaz (kapsam dışı).
BEDEL_ADIMLARI: Final[tuple[str, ...]] = (
    CaseResolution.PRICE_DETERMINED,
    CaseResolution.PRICE_RECEIVED,
)


def dosya_cozumu_kapsamda_mi(case_type: str, resolution: str) -> bool:
    """Bu dosya çözümü TMY 32/3 durdurmasının kapsamında mı? (§9-10 "kayıp dosyası çözümü")

    - Kayıp dosyası: iki bedel adımı ("Bedel belirlendi", "Bedel teslim alındı")
      DIŞINDAKİ bütün çözümler — nüsha "Kayıp"tan rafa döner ("Bulundu", "Aynısı
      temin edildi", "Bedelle aynısı alındı") ya da kayıttan düşme önerilir.
    - Hasar dosyası: yalnız kayıttan düşme önerisi yazan çözümler. "Onarıldı",
      "Aynısı temin edildi", "Bedelle aynısı alındı" ve bedel adımları nüshanın
      kaydını değiştirmez (onarım kapsam dışıdır).
    """
    if resolution in WRITE_OFF_RESOLUTIONS:
        return True
    return case_type == CaseType.LOST and resolution not in BEDEL_ADIMLARI


def ensure_open(islem: str) -> None:
    """İşlem TMY 32/3 durdurmasına takılıyor mu? F7'de her zaman geçer (F9 doldurur).

    F9'da: etkin sayımda durdurma seçilmişse Django `ValidationError` yükseltir
    (400, Türkçe ileti: sayım ve durdurma kararı). İmza değişmez; dosya çözümünde
    kapı yalnız `dosya_cozumu_kapsamda_mi` doğru olduğunda sorulur.
    """
    del islem  # F9'a kadar kullanılmaz
