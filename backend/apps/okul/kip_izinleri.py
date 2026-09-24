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
* Parametre kuralı (F6'da dolaşım uçlarıyla gelir; ör. `override_reason`
  taşıyan ödünç 403, kartla üye çözmede yalnız ad + kalan hak): isteği alıp
  geçip geçmeyeceğini söyleyen bir denetçi. Denetçi yanlış dönerse istek
  kesilir. F1'de hiçbir kuralın parametre denetçisi yoktur.

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

from collections.abc import Callable
from dataclasses import dataclass

from django.http import HttpRequest

ParametreDenetcisi = Callable[[HttpRequest], bool]


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
        "library-label-verify",
        "POST",
        gerekce=(
            "etiket doğrulama okutması (kullanıcı kararı 24.09.2026); yanıt görevli kipinde "
            "yalnız barkod ve eser adını taşır. Öbür etiket uçları kapalıdır"
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
