"""Görevli kipinin izin listesi (U5, tasarım §4.4) — fail-closed.

Görevli kipinde bir API isteği yalnız buradaki bir kurala uyarsa geçer; geri
kalan HER şey `kip_middleware` tarafından 403 `kip_yetkisiz` ile kesilir. Yeni
bir uç bu listeye kendiliğinden girmez (varsayılan kapalı): görevlinin o işe
gerçekten ihtiyacı varsa bilinçli olarak eklenir ve anlık görüntü testi
(`tests/test_kip_koruma.py`) aynı değişiklikte güncellenir. Testi yeşile
çekmek için listeye uç eklemek kusurdur (CLAUDE.md §2-4).

Kural düzeyi: **uç + yöntem (+ parametre)**.

* Uç, Django URL adıyla tutulur (`resolve(path).view_name`; ad alanlı
  include'larda `ad_alani:ad` biçimi). Yol değil ad tutulur: yol dönüştürücü
  içerebilir, ad değişmez.
* Yöntem büyük harfli HTTP yöntemidir. HEAD ve OPTIONS ayrıca yazılmadıkça
  kapalıdır.
* Parametre kuralı (F6): isteği alıp geçip geçmeyeceğini söyleyen bir denetçi.
  Denetçi yanlış dönerse istek kesilir. İki biçimi vardır:
  - `yalniz_sorgu(...)`: GET ucunun sorgu dizesinde YALNIZ sayılan anahtarlar
    bulunabilir (katalog okuma — görevli edinim partisine, eski kayıt no'ya
    göre süzemez; bilinmeyen anahtar da kesilir, fail-closed);
  - `govdede_yok(...)`: gövdede (ve sorgu dizesinde) sayılan anahtarların
    HİÇBİRİ bulunamaz — `override_reason`/`override_note` (gecikme istisnası),
    `cardless`/`cardless_reason` (kartsız ödünç) ve `membership_id` (kartsız
    üye açma) taşıyan ödünç ya da üye çözme isteği 403 alır (§4.4, §5.10-8).
    Gövde JSON değilse (ya da okunamıyorsa) istek kesilir: masa uçları yalnız
    JSON kabul eder (`views_masa`), denetçinin okuyamadığı bir gövde görünüme
    ulaşmamalıdır. Boş gövde geçer (görünüm doğrulamayla reddeder).
    **Karakter kümesi yalnız UTF-8'dir** (F6 düzeltme turu): denetçi baytları
    `json.loads` ile okur (UTF-8/16/32 kendiliğinden sezilir), DRF ise gövdeyi
    `Content-Type`'taki `charset` ile çözer. `charset=utf-7` gönderen bir istemci
    `override+AF8-reason` anahtarını denetçiye başka, görünüme `override_reason`
    olarak gösterebilirdi. `charset` UTF-8 dışında bir şeyse istek kesilir;
    masa görünümleri de UTF-8 dışı gövdeyi reddeder (`views_masa`).
  Anahtarın DEĞERİNE bakılmaz, VARLIĞINA bakılır: boş bir `override_reason`
  bile görevli kipinde 403'tür. Yanıtların daralması (kartla üye çözmede yalnız
  ad + kalan hak) görünümün işidir (`apps/kutuphane/serializers_masa.py`).

`setup/status/` (masaüstü sağlık denetimi), `security/status/` ve
`security/mode/` ara katmanda HİÇBİR durumda kesilmez (§4.4) — yalnız GET/HEAD;
başka yöntemler bu listeden geçer. Listede yine de açıkça yer alırlar ki izin
listesi görevlinin gördüğü yüzeyin tam tarifi olsun.

Uç URL ADIYLA eşleştiği için `/api/` altındaki adların TEKİL olması şarttır
(`apps.okul.urls` ve `apps.kutuphane.urls` aynı düz ad uzayındadır): izin
listesindeki bir adı taşıyan ikinci bir desen görevli kipinde sessizce açılırdı.
Teklik `tests/test_kip_koruma.py`'de sabitlenir.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from django.http import HttpRequest

ParametreDenetcisi = Callable[[HttpRequest], bool]

#: Masa uçlarının kabul ettiği tek gövde biçimi.
JSON_ICERIK = "application/json"
#: Gövdenin kabul edilen tek karakter kümesi (adı büyük/küçük harf ve tire farkı gözetmeden).
UTF8_ADLARI = frozenset({"utf-8", "utf8"})


def utf8_mi(charset: str | None) -> bool:
    """`Content-Type`'taki `charset` yok ya da UTF-8 mi? (Başkası → fail-closed.)"""
    if charset is None:
        return True
    return charset.strip().strip('"').lower().replace("_", "-") in UTF8_ADLARI


@dataclass(frozen=True)
class SorguSiniri:
    """GET ucunda sorgu dizesinde bulunabilecek anahtarlar (başkası → 403)."""

    izinli: frozenset[str]

    def __call__(self, request: HttpRequest) -> bool:
        return set(request.GET.keys()) <= self.izinli


@dataclass(frozen=True)
class GovdeYasagi:
    """Gövdede ve sorgu dizesinde bulunamayacak anahtarlar (varlık yeter → 403)."""

    yasak: frozenset[str]

    def __call__(self, request: HttpRequest) -> bool:
        if set(request.GET.keys()) & self.yasak:
            return False
        try:
            ham = request.body
        except Exception:  # okunamayan (ör. aşırı büyük) gövde: fail-closed
            return False
        if not ham.strip():
            return True
        if (request.content_type or "").lower() != JSON_ICERIK:
            return False
        if not utf8_mi((request.content_params or {}).get("charset")):
            return False
        try:
            govde = json.loads(ham)
        except (ValueError, UnicodeDecodeError):
            return False
        if not isinstance(govde, dict):
            return False
        return not (set(govde) & self.yasak)


def yalniz_sorgu(*anahtarlar: str) -> SorguSiniri:
    return SorguSiniri(frozenset(anahtarlar))


def govdede_yok(*anahtarlar: str) -> GovdeYasagi:
    return GovdeYasagi(frozenset(anahtarlar))


#: Görevli kipinde ödünç ve üye çözme isteğinde bulunamayacak alanlar (§4.4):
#: gecikme engeli istisnası, kartsız ödünç ve üyelik kaydıyla (kartsız) üye açma.
YONETICI_ODUNC_ALANLARI: tuple[str, ...] = (
    "override_reason",
    "override_note",
    "cardless",
    "cardless_reason",
    "membership_id",
)


@dataclass(frozen=True)
class IzinKurali:
    """Görevli kipinde açık bir uç + yöntem (+ isteğe bağlı parametre denetçisi)."""

    uc: str
    yontem: str
    parametre: ParametreDenetcisi | None = None
    # Kuralın neden açık olduğu (kod okuru için; kullanıcıya gösterilmez).
    gerekce: str = ""


IZIN_LISTESI: tuple[IzinKurali, ...] = (
    IzinKurali("setup-status", "GET", gerekce="masaüstü sağlık denetimi ve kurulum kapısı"),
    IzinKurali("security-status", "GET", gerekce="kilit ekranı durum sorgusu"),
    IzinKurali("security-lock", "POST", gerekce="Kilitle her kipte parolasızdır (§4.4)"),
    IzinKurali("security-mode", "GET", gerekce="kip göstergesi"),
    IzinKurali(
        "security-mode-admin",
        "POST",
        gerekce="yönetici kipine geçiş; gövdede yönetici parolası",
    ),
    IzinKurali(
        "app-quit",
        "POST",
        gerekce=(
            "Çık (F5, §4.2-4); parolasız istek görünümde 403 alır, gövdede yönetici "
            "parolası gerekir — kaza önleyicidir (CLAUDE.md §2-4)"
        ),
    ),
    IzinKurali(
        "library-label-verify",
        "POST",
        gerekce=(
            "etiket doğrulama okutması (kullanıcı kararı 24.09.2026); yanıt görevli kipinde "
            "yalnız barkod ve eser adını taşır. Öbür etiket uçları kapalıdır"
        ),
    ),
    # --- F6: dolaşım masası (§4.4 tablosu, §7.3). Yanıtlar görevli kipinde daralır
    # (`apps/kutuphane/serializers_masa.py`). Kapalı kalanlar: okul no ya da adla
    # üye arama, üye listesi, ödünç geçmişi, gecikme listesi, son işlemler.
    IzinKurali(
        "library-desk-member",
        "POST",
        parametre=govdede_yok("membership_id"),
        gerekce=(
            "kartla üye çözme; yanıtta YALNIZ ad + kalan hak (sınıf yok). Üyelik kaydıyla "
            "üye açma (kartsız ödünç) yönetici işidir; art arda geçersiz kart → parola (GA-7)"
        ),
    ),
    IzinKurali(
        "library-checkout",
        "POST",
        parametre=govdede_yok(*YONETICI_ODUNC_ALANLARI),
        gerekce=(
            "ödünç ver; gerekçeli istisna (override_*) ve kartsız ödünç (cardless*, "
            "membership_id) taşıyan istek 403. Sayı sınırı ve Md. 16/1 hiçbir kipte istisna almaz"
        ),
    ),
    IzinKurali(
        "library-return",
        "POST",
        gerekce="barkodla iade; yanıtta ödünç alanın kimliği ve gecikme günü YOK",
    ),
    IzinKurali(
        "library-desk-copy-status",
        "GET",
        parametre=yalniz_sorgu("barcode"),
        gerekce="nüsha durum sorgusu; ödünç kimde, ne zaman dönecek görevliye gösterilmez",
    ),
    IzinKurali(
        "library-desk-card-unlock",
        "POST",
        gerekce="GA-7 kart okutma kilidini açma; gövdede yönetici parolası (görünüm denetler)",
    ),
    # --- F7: teslimden geri alma okutması (§4.4 tablosu "Açık" sütunu, U11). Teslim
    # VERME, teslim listesi, kayıp/hasar dosyaları ve onarım kapalıdır.
    IzinKurali(
        "library-delivery-take-back",
        "POST",
        gerekce=(
            "teslimden geri alma okutması (§4.4, U11); yanıt görevli kipinde yalnız sonuç, "
            "ileti, barkod ve eser adı — teslim alanın kimliği, belge no ve tarih YOK"
        ),
    ),
    # Katalog okuma: works/copies GET, Ağ Kataloğunun alan listesine denk serializer
    # (görevli kipinde `GorevliEserSerializer`/`GorevliNushaSerializer`). Edinim,
    # komisyon kararı, bağış, fiyat ve TKYS alanları kapalı; süzgeçler sınırlı.
    IzinKurali(
        "library-work-list",
        "GET",
        parametre=yalniz_sorgu("q", "order", "resource_type", "section", "limit", "offset"),
        gerekce="katalogda arama (künye alanları; edinim ve etiket damgaları yok)",
    ),
    IzinKurali(
        "library-work-detail",
        "GET",
        parametre=yalniz_sorgu(),
        gerekce="eser künyesi (Ağ Kataloğunun eser sayfasına denk)",
    ),
    IzinKurali(
        "library-copy-list",
        "GET",
        parametre=yalniz_sorgu("work", "section", "status", "only_loanable", "limit", "offset"),
        gerekce=(
            "eserin nüshaları: durum, bölüm, ödünç verilebilirlik (kayıttan düşülenler "
            "görevliye gösterilmez); edinim partisine ve eski kayıt no'ya göre süzme yok"
        ),
    ),
)

_KURALLAR: dict[tuple[str, str], IzinKurali] = {
    (kural.uc, kural.yontem): kural for kural in IZIN_LISTESI
}


def izinli_mi(
    uc: str | None,
    yontem: str,
    request: HttpRequest,
    *,
    kurallar: tuple[IzinKurali, ...] | None = None,
) -> bool:
    """Görevli kipinde bu istek geçer mi? Adsız ya da bilinmeyen uç → hayır.

    `kurallar` yalnız testler içindir (parametre denetçisi mekanizmasını sınamak).
    """
    if not uc:
        return False
    tablo = _KURALLAR if kurallar is None else {(k.uc, k.yontem): k for k in kurallar}
    kural = tablo.get((uc, yontem.upper()))
    if kural is None:
        return False
    return kural.parametre is None or kural.parametre(request)
