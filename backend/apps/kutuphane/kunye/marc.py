"""MARCXML ayrıştırması — GÜVENLİ (dış varlık ve DTD kapalı), standart kütüphaneyle.

Bakanlık kataloğunun SRU ucu MARCXML döndürür. Ayrıştırma `xml.etree` ile
yapılır (yeni bağımlılık yok, CLAUDE.md §2-10) ve **güvenilmeyen girdi**
muamelesi görür (§8.5-4, §4.3):

* **Gövde UTF-8 OLMAK ZORUNDADIR.** Ön denetim ASCII bayt deseniyle çalışır;
  UTF-16 kodlanmış bir gövdede desen eşleşmez ve varlık tanımı ayrıştırıcıya
  kadar giderdi (23.09.2026 ölçümü: UTF-16 "milyar kahkaha" gövdesi yalnız
  libexpat'ın kendi genişleme tavanına takıldı, 11 KB'lık bir gövde 250.000
  karaktere açıldı). Bakanlık ucu düz HTTP'dir (TB20) ve yol üzerindeki bir
  aktör gövdeyi değiştirebilir; kodlama bu yüzden denetlenir.
* **DTD ve varlık tanımı taşıyan gövde hiç ayrıştırılmaz.** `xml.etree` dış
  varlığı zaten çözmez ve tanımsız varlıkta hata verir; buradaki ön denetim
  "milyar kahkaha" (iç içe varlık genişlemesi) gövdesini ayrıştırıcıya hiç
  vermez — koruma ayrıştırıcının sürümüne bağlı kalmasın.
* Boyut tavanı `istemci`de uygulanır; burada kayıt ve alan sayısı da sınırlıdır.
* Her metin `temizlik`ten geçer: NFC, denetim karakteri, HTML varlığı, tavan.

Alan eşlemesi §8.5'teki ölçümden gelir: 020 ISBN · 100 yazar · 245 eser adı ve
alt başlık · 250 baskı · 260/264 yayın yeri, yayınevi, yıl · 300 sayfa · 650
konu · 041 dil · 082 Dewey · 090 yer numarası.

**700 alanı (ek giriş) BİLİNÇLİ OLARAK OKUNMAZ:** çevirmen, editör ve
hazırlayan orada durur; §8.5-5 çevirmenin dışarıdan doldurulmasını yasaklar.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree

from apps.kutuphane import isbn as isbn_module
from apps.kutuphane.kunye import temizlik
from apps.kutuphane.kunye.oneri import (
    ALAN_TAVANLARI,
    UYARI_CEVIRMEN,
    UYARI_YAZAR,
    KunyeOnerisi,
    dil_adi,
    gecerli_yil,
)

#: Ayrıştırılacak en çok kayıt (uç `maximumRecords=5` ister; yanıt yine de
#: güvenilmeyen girdidir, tavan istemciden bağımsız durur).
MAX_KAYIT = 20
#: Bir kayıttan okunacak en çok konu başlığı.
MAX_KONU = 8

_DTD_DESENI = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
#: XML bildirimindeki kodlama adı (`<?xml version="1.0" encoding="…"?>`).
_BILDIRIM_DESENI = re.compile(
    rb"<\?xml[^>]{0,200}?encoding\s*=\s*[\"']([\w.:-]+)[\"']", re.IGNORECASE
)
_UTF8_ADLARI = frozenset({"utf-8", "utf8"})
_UTF8_BOM = b"\xef\xbb\xbf"
#: "Ali, Sabahattin" → "Sabahattin Ali" çevrimi için tek virgül denetimi.
_TEK_VIRGUL = re.compile(r"^([^,]+),([^,]+)$")


class MarcHatasi(ValueError):
    """Gövde MARCXML değil ya da güvenlik denetiminden geçmedi."""


def _utf8_denetle(govde: bytes) -> None:
    """Gövde UTF-8 mi? Değilse `MarcHatasi` — DTD ön denetimi ancak öyle çalışır.

    Üç kapı: (1) NUL baytı — XML 1.0'da yasaktır ve UTF-16/UTF-32 gövdenin ilk
    baytlarında hemen görünür; (2) ilk anlamlı baytın ASCII `<` olması (BOM'lu
    UTF-16BE gövde buradan düşer); (3) XML bildirimindeki kodlama adı. Son
    kapı `decode`dur: kalan her şey gerçekten UTF-8 olmalıdır.
    """
    hata = MarcHatasi("Yanıtın kodlaması desteklenmiyor (UTF-8 bekleniyor); gövde düşürüldü.")
    if b"\x00" in govde:
        raise hata
    baslangic = govde.lstrip()
    if baslangic.startswith(_UTF8_BOM):
        baslangic = baslangic[len(_UTF8_BOM) :].lstrip()
    if not baslangic.startswith(b"<"):
        raise hata
    bildirim = _BILDIRIM_DESENI.match(baslangic)
    if bildirim is not None and bildirim.group(1).decode("ascii", "replace").lower() not in (
        _UTF8_ADLARI
    ):
        raise hata
    try:
        govde.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise hata from exc


def guvenli_ayristir(govde: bytes) -> ElementTree.Element:
    """UTF-8 olan, DTD/varlık taşımayan MARCXML gövdesini ayrıştırır; aksi hâlde `MarcHatasi`."""
    _utf8_denetle(govde)
    if _DTD_DESENI.search(govde):
        raise MarcHatasi("Yanıtta DTD ya da varlık tanımı var; gövde düşürüldü.")
    try:
        return ElementTree.fromstring(govde)  # noqa: S314 — DTD/varlık üstte elendi
    except ElementTree.ParseError as exc:
        raise MarcHatasi("Yanıt XML olarak okunamadı.") from exc


def _yerel(etiket: object) -> str:
    """Ad alanı ön ekini atar: '{…/slim}datafield' → 'datafield'."""
    return str(etiket).rpartition("}")[2]


def kayit_sayisi(kok: ElementTree.Element) -> int:
    """SRU yanıtındaki `numberOfRecords` (mükerrer kayıt kuralı — §8.5)."""
    for dugum in kok.iter():
        if _yerel(dugum.tag) == "numberOfRecords":
            sayi = temizlik.sayi_ayikla(dugum.text)
            return sayi or 0
    return 0


def marc_kayitlari(kok: ElementTree.Element) -> list[ElementTree.Element]:
    """Gövdedeki MARC kayıtları (SRU sarmalayıcısındaki `zs:record` değil)."""
    kayitlar: list[ElementTree.Element] = []
    for dugum in kok.iter():
        if _yerel(dugum.tag) != "record":
            continue
        if any(_yerel(cocuk.tag) in {"datafield", "leader", "controlfield"} for cocuk in dugum):
            kayitlar.append(dugum)
        if len(kayitlar) >= MAX_KAYIT:
            break
    return kayitlar


def _alanlar(kayit: ElementTree.Element, etiket: str) -> list[ElementTree.Element]:
    return [
        dugum for dugum in kayit if _yerel(dugum.tag) == "datafield" and dugum.get("tag") == etiket
    ]


def _alt(alan: ElementTree.Element, kod: str) -> str:
    """Alt alanın ham metni (temizlik çağırana aittir)."""
    for dugum in alan:
        if _yerel(dugum.tag) == "subfield" and dugum.get("code") == kod:
            return str(dugum.text or "")
    return ""


def _ilk(kayit: ElementTree.Element, etiketler: tuple[str, ...], kod: str) -> str:
    for etiket in etiketler:
        for alan in _alanlar(kayit, etiket):
            deger = _alt(alan, kod)
            if deger.strip():
                return deger
    return ""


def _yazar_duzelt(ham: str) -> str:
    """MARC'ın ters yazımını sözlüğün 'Ad Soyad' sırasına çevirir.

    100$a "Ali, Sabahattin" biçimindedir; katalog sözlüğü (docs/sozluk.md)
    "Ad Soyad" ister ve `keys.author_sort_name` soyadı SON sözcükten türetir.
    Ters bırakılsaydı yazar sıralaması ve yer numarası yanlış soyadı görürdü.
    Birden çok virgül varsa (tarih ya da unvan eklenmiş: "Ali, Sabahattin,
    1907-1948") dokunulmaz — tahmin etmek yanlış ad üretebilir.
    """
    eslesme = _TEK_VIRGUL.match(ham.strip())
    if not eslesme:
        return ham.strip()
    soyad, ad = (parca.strip() for parca in eslesme.groups())
    if not soyad or not ad:
        return ham.strip()
    return f"{ad} {soyad}"


def kayittan_oneri(kayit: ElementTree.Element, *, isbn13: str) -> KunyeOnerisi:
    """Tek MARC kaydını temizlenmiş künye önerisine çevirir."""
    tavan = ALAN_TAVANLARI

    ad = temizlik.marc_temizle(_ilk(kayit, ("245",), "a"), tavan=tavan["title"])
    alt_ad = temizlik.marc_temizle(_ilk(kayit, ("245",), "b"), tavan=tavan["title"])
    baslik = f"{ad} {alt_ad}".strip() if alt_ad else ad
    baslik = baslik[: tavan["title"]].strip()

    yazar = _yazar_duzelt(
        temizlik.marc_temizle(_ilk(kayit, ("100", "110"), "a"), tavan=tavan["authors"])
    )

    konular: list[str] = []
    for alan in _alanlar(kayit, "650"):
        konu = temizlik.marc_temizle(_alt(alan, "a"), tavan=120)
        if konu and konu not in konular:
            konular.append(konu)
        if len(konular) >= MAX_KONU:
            break

    yer_no_parcalari = [
        temizlik.marc_temizle(_ilk(kayit, ("090",), kod), tavan=tavan["call_number"])
        for kod in ("a", "b")
    ]
    yer_no = " ".join(parca for parca in yer_no_parcalari if parca)[: tavan["call_number"]].strip()

    sayfa = temizlik.sayi_ayikla(_ilk(kayit, ("300",), "a"))
    yil = gecerli_yil(temizlik.yil_ayikla(_ilk(kayit, ("260", "264"), "c")))

    oneri = KunyeOnerisi(
        isbn=isbn13,
        title=baslik,
        authors=yazar[: tavan["authors"]],
        publisher=temizlik.marc_temizle(_ilk(kayit, ("260", "264"), "b"), tavan=tavan["publisher"]),
        edition=temizlik.marc_temizle(_ilk(kayit, ("250",), "a"), tavan=tavan["edition"]),
        publish_year=yil,
        subjects=", ".join(konular)[: tavan["subjects"]].strip(", "),
        classification_code=temizlik.marc_temizle(
            _ilk(kayit, ("082",), "a"), tavan=tavan["classification_code"]
        ),
        call_number=yer_no,
        language=dil_adi(temizlik.marc_temizle(_ilk(kayit, ("041",), "a"), tavan=8))[
            : tavan["language"]
        ],
        pages=sayfa,
        place=temizlik.marc_temizle(_ilk(kayit, ("260", "264"), "a"), tavan=120),
        uyarilar=(UYARI_CEVIRMEN,),
    )
    if oneri.authors:
        oneri = oneri.uyarili(UYARI_YAZAR)
    return oneri


def govdeden_oneri(govde: bytes, *, isbn13: str) -> tuple[KunyeOnerisi | None, int]:
    """MARCXML gövdesinden **en zengin** öneriyi ve kaynaktaki kayıt sayısını döndürür.

    Mükerrer kayıt kuralı (§8.5): tek ISBN için yüzlerce kayıt dönebilir (ölçülen
    en yüksek değer 123). Program sessizce ilkini almaz; 082/090 taşıyan, 300 ve
    650 dolu olan kayıt seçilir. Eşitlikte kaynağın sırası korunur.
    """
    kok = guvenli_ayristir(govde)
    sayi = kayit_sayisi(kok)
    oneriler = [kayittan_oneri(kayit, isbn13=isbn13) for kayit in marc_kayitlari(kok)]
    dolu = [oneri for oneri in oneriler if not oneri.bos_mu]
    if not dolu:
        return None, sayi
    en_zengin = max(dolu, key=lambda oneri: oneri.zenginlik())
    return en_zengin, max(sayi, len(oneriler))


def isbn_uyumlu_mu(kayit: ElementTree.Element, *, isbn13: str) -> bool:
    """Kayıttaki 020$a numaralarından biri sorulan ISBN'e eşit mi?"""
    for alan in _alanlar(kayit, "020"):
        if isbn_module.to_isbn13(_alt(alan, "a")) == isbn13:
            return True
    return False
