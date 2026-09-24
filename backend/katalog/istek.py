"""İstek çözümü ve bağlantı kurma — yol, sorgu dizesi, tahta kipi (tasarım §5.4, §5.5).

Bu modül `urllib`'i BİLEREK kullanmaz: Ağ Kataloğu paketinde dış bağlantı
açabilecek hiçbir modül içe aktarılmaz (§5.10-20 kaynak taraması `urllib`
kökünü toptan yasaklar — `urllib.parse` zararsızdır ama aynı kökün
`urllib.request`'i değildir ve taramanın basit kalması bu ayrımdan
değerlidir). Gereken iki iş — yüzde kodlaması ve `a=1&b=2` ayrıştırması —
burada birkaç satırdır ve sınırları sıkıdır:

- Sorgu dizesi en çok `EN_UZUN_SORGU_DIZESI` karakterdir; aşarsa istek
  reddedilir. Aynı ad birden çok kez gelirse İLKİ geçerlidir.
- Yüzde kodlaması UTF-8 olarak çözülür; bozuk kodlama `GecersizIstek`
  yükseltir (400 sayfası). Çözülen değerde denetim karakteri kalmaz.
- Yol (`PATH_INFO`) WSGI kuralı gereği latin-1 dizesi olarak gelir (baytların
  birebir karşılığı); UTF-8 olarak yeniden çözülür.

Tahta kipi (`?tahta=1`): dağıtılan yer imi bu parametreyi taşır; sunucu büyük
düzeni seçer ve parametreyi ÜRETTİĞİ BÜTÜN BAĞLANTILARDA korur (§5.4). Kip
bir çerezle değil bağlantıyla taşınır: katalog çerez okumaz ve yazmaz.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

#: Kabul edilen en uzun ham sorgu dizesi (karakter). 100 karakterlik bir arama
#: yüzde kodlamasıyla ~600 karakter tutar; kalan pay diğer parametrelerindir.
EN_UZUN_SORGU_DIZESI: Final = 2048

#: Yüzde kodlanmadan yazılan baytlar (RFC 3986 "unreserved").
_GUVENLI: Final = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_ONALTILIK: Final = frozenset(b"0123456789abcdefABCDEF")

#: Tahta kipi parametresi ve açık değeri.
TAHTA_PARAMETRESI: Final = "tahta"
TAHTA_ACIK: Final = "1"


class GecersizIstek(ValueError):
    """İstek çözülemedi (bozuk kodlama, denetim karakteri) → 400."""


class AdresCokUzun(GecersizIstek):
    """Sorgu dizesi `EN_UZUN_SORGU_DIZESI`'ni aşıyor → 414."""


def yuzde_kodla(metin: str, *, guvenli: str = "") -> str:
    """UTF-8 yüzde kodlaması; `guvenli` içindeki karakterler (ör. '/') olduğu gibi kalır."""
    ek = frozenset(guvenli.encode("ascii"))
    return "".join(
        chr(bayt) if bayt in _GUVENLI or bayt in ek else f"%{bayt:02X}"
        for bayt in metin.encode("utf-8")
    )


def yuzde_coz(ham: bytes, *, arti_bosluktur: bool) -> str:
    """`%XX` dizilerini çözer ve UTF-8 olarak okur; bozuksa `GecersizIstek`."""
    if arti_bosluktur:
        ham = ham.replace(b"+", b" ")
    cikti = bytearray()
    i = 0
    while i < len(ham):
        bayt = ham[i]
        if bayt == 0x25:  # '%'
            parca = ham[i + 1 : i + 3]
            if len(parca) != 2 or not all(b in _ONALTILIK for b in parca):
                raise GecersizIstek("bozuk yüzde kodlaması")
            cikti.append(int(parca, 16))
            i += 3
            continue
        cikti.append(bayt)
        i += 1
    try:
        metin = cikti.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GecersizIstek("UTF-8 olmayan istek") from exc
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in metin):
        raise GecersizIstek("denetim karakteri")
    return metin


def _wsgi_baytlari(deger: str) -> bytes:
    """WSGI dizesini (latin-1 ile baytlara birebir eşlenmiş) baytlara çevirir."""
    try:
        return deger.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise GecersizIstek("WSGI dizesi latin-1 değil") from exc


def yolu_coz(path_info: str) -> str:
    """`PATH_INFO`'yu UTF-8 metne çevirir (sunucu yüzde kodlamasını zaten çözmüştür)."""
    try:
        metin = _wsgi_baytlari(path_info).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GecersizIstek("UTF-8 olmayan yol") from exc
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in metin):
        raise GecersizIstek("denetim karakteri")
    return metin or "/"


def sorgu_dizesini_coz(query_string: str) -> dict[str, str]:
    """`a=1&b=2` → sözlük. Aynı ad birden çok kez gelirse ilki geçerlidir."""
    if len(query_string) > EN_UZUN_SORGU_DIZESI:
        raise AdresCokUzun("sorgu dizesi çok uzun")
    sonuc: dict[str, str] = {}
    for parca in _wsgi_baytlari(query_string).split(b"&"):
        if not parca:
            continue
        ad_ham, _esit, deger_ham = parca.partition(b"=")
        ad = yuzde_coz(ad_ham, arti_bosluktur=True)
        if ad and ad not in sonuc:
            sonuc[ad] = yuzde_coz(deger_ham, arti_bosluktur=True)
    return sonuc


@dataclass(frozen=True)
class Istek:
    """Çözülmüş istek: yol, parametreler ve tahta kipi. Çerez ve başlık taşımaz."""

    yol: str
    parametreler: Mapping[str, str] = field(default_factory=dict)

    @property
    def tahta(self) -> bool:
        return self.parametreler.get(TAHTA_PARAMETRESI) == TAHTA_ACIK

    def parametre(self, ad: str) -> str | None:
        return self.parametreler.get(ad)

    def bag(self, yol: str, **parametreler: str | int | None) -> str:
        """Katalog içi bağlantı: yol yüzde kodlanır, tahta kipi korunur.

        Değeri `None` ya da boş olan parametre yazılmaz. Adres her zaman köke
        görelidir (`/…`); başka bir sunucuya bağlantı üretilmez.
        """
        if not yol.startswith("/") or yol.startswith("//"):
            raise ValueError("Katalog bağlantısı köke göreli olmalıdır.")
        ciftler = [
            (ad, str(deger)) for ad, deger in parametreler.items() if deger not in (None, "")
        ]
        if self.tahta:
            ciftler.append((TAHTA_PARAMETRESI, TAHTA_ACIK))
        adres = yuzde_kodla(yol, guvenli="/")
        if ciftler:
            adres += "?" + "&".join(
                f"{yuzde_kodla(ad)}={yuzde_kodla(deger)}" for ad, deger in ciftler
            )
        return adres
