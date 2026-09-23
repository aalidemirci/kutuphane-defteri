"""İki kaynağın ayrıştırması: MARCXML (Bakanlık) ve JSON (Open Library).

Gerçek ağa ÇIKILMAZ; yanıtlar taklit edilir. Gövdeler §8.5'teki ölçümün
biçimini taşır (alan numaraları, ölçülen Türkçe kusurlar). Kitap künyeleri
kamu malı ya da uydurmadır.
"""

from __future__ import annotations

import json
import unicodedata

import pytest

from apps.kutuphane.kunye import bakanlik, istemci, marc, openlibrary
from apps.kutuphane.kunye.istemci import KunyeAgHatasi
from apps.kutuphane.kunye.oneri import UYARI_CEVIRMEN, UYARI_YAZAR
from apps.kutuphane.tests.test_kunye_istemci import SahteAcici, SahteYanit

ISBN = "9789753638029"


@pytest.fixture(autouse=True)
def hizli_saat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hız sınırlayıcı testlerde gerçek `sleep` çağırmasın (§8.5-2 ayrı dosyada sınanır)."""
    monkeypatch.setattr(istemci, "_uyu", lambda _sure: None)
    istemci._sifirla_testler_icin()


def marcxml(kayitlar: str, *, toplam: int = 1) -> bytes:
    """SRU yanıtı: ad alanlı sarmalayıcı + MARCXML kayıtları."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">
  <zs:version>1.1</zs:version>
  <zs:numberOfRecords>{toplam}</zs:numberOfRecords>
  <zs:records>{kayitlar}</zs:records>
</zs:searchRetrieveResponse>""".encode()


def kayit(
    *,
    ad: str = "Kürk mantolu Madonna /",
    alt_ad: str = "",
    yazar: str = "Ali, Sabahattin",
    yayinevi: str = "Yapı Kredi Yayınları,",
    yil: str = "2015.",
    sayfa: str = "160 s. ;",
    konular: tuple[str, ...] = ("Türk edebiyatı", "Roman"),
    dewey: str = "894.353",
    yer_no: str = "",
    dil: str = "tur",
) -> str:
    konu_alanlari = "".join(
        f'<datafield tag="650" ind1=" " ind2="0"><subfield code="a">{konu}</subfield></datafield>'
        for konu in konular
    )
    alt_ad_alani = f'<subfield code="b">{alt_ad}</subfield>' if alt_ad else ""
    dewey_alani = (
        f'<datafield tag="082" ind1="0" ind2="4"><subfield code="a">{dewey}</subfield></datafield>'
        if dewey
        else ""
    )
    yer_no_alani = (
        f'<datafield tag="090" ind1=" " ind2=" "><subfield code="a">{yer_no}</subfield></datafield>'
        if yer_no
        else ""
    )
    return f"""<zs:record xmlns:zs="http://www.loc.gov/zing/srw/"><zs:recordData>
  <record xmlns="http://www.loc.gov/MARC21/slim">
    <leader>00000nam a2200000 i 4500</leader>
    <datafield tag="020" ind1=" " ind2=" "><subfield code="a">{ISBN}</subfield></datafield>
    <datafield tag="041" ind1=" " ind2=" "><subfield code="a">{dil}</subfield></datafield>
    <datafield tag="100" ind1="1" ind2=" "><subfield code="a">{yazar}</subfield></datafield>
    <datafield tag="245" ind1="1" ind2="0"><subfield code="a">{ad}</subfield>{alt_ad_alani}
      <subfield code="c">Sabahattin Ali ; çeviren Uydurma Çevirmen.</subfield></datafield>
    <datafield tag="250" ind1=" " ind2=" "><subfield code="a">5. bs.</subfield></datafield>
    <datafield tag="260" ind1=" " ind2=" "><subfield code="a">İstanbul :</subfield>
      <subfield code="b">{yayinevi}</subfield><subfield code="c">{yil}</subfield></datafield>
    <datafield tag="300" ind1=" " ind2=" "><subfield code="a">{sayfa}</subfield></datafield>
    {konu_alanlari}{dewey_alani}{yer_no_alani}
    <datafield tag="700" ind1="1" ind2=" "><subfield code="a">Çevirmen, Uydurma</subfield></datafield>
  </record>
</zs:recordData></zs:record>"""


# ===================================================== MARCXML güvenliği
class TestMarcGuvenligi:
    def test_dis_varlik_tasiyan_govde_reddedilir(self) -> None:
        govde = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE kayit [<!ENTITY dosya SYSTEM "file:///etc/passwd">]>'
            b"<kayit>&dosya;</kayit>"
        )

        with pytest.raises(marc.MarcHatasi):
            marc.guvenli_ayristir(govde)

    def test_milyar_kahkaha_govdesi_reddedilir(self) -> None:
        govde = (
            b'<?xml version="1.0"?><!DOCTYPE lol ['
            b'<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">'
            b"]><lol>&lol2;</lol>"
        )

        with pytest.raises(marc.MarcHatasi):
            marc.guvenli_ayristir(govde)

    def test_bozuk_xml_hataya_cevrilir(self) -> None:
        with pytest.raises(marc.MarcHatasi):
            marc.guvenli_ayristir(b"<kayit><acik>")

    @pytest.mark.parametrize("kodlama", ["utf-16", "utf-16-be", "utf-32"])
    def test_utf8_olmayan_govde_reddedilir(self, kodlama: str) -> None:
        """Ön denetim ASCII bayt deseniyle çalışır: UTF-16'da desen eşleşmezdi.

        Ölçüldü (23.09.2026): aynı DTD gövdesi UTF-16 verildiğinde denetimden
        geçiyor, varlık çözülüyor ve koruma yalnız libexpat'ın genişleme
        tavanına kalıyordu — modül başlığının verdiği sözün tersi.
        """
        metin = '<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY a "aaaa">]><lol>&a;</lol>'

        with pytest.raises(marc.MarcHatasi, match="kodlama"):
            marc.guvenli_ayristir(metin.encode(kodlama))

    def test_utf8_bom_lu_govde_kabul_edilir(self) -> None:
        """BOM'lu UTF-8 gerçek bir uçtan gelebilir; denetim onu düşürmemeli."""
        kok = marc.guvenli_ayristir(b"\xef\xbb\xbf" + marcxml(kayit()))

        assert marc.kayit_sayisi(kok) == 1

    def test_temiz_marcxml_ayristirilir(self) -> None:
        kok = marc.guvenli_ayristir(marcxml(kayit()))

        assert marc.kayit_sayisi(kok) == 1
        assert len(marc.marc_kayitlari(kok)) == 1


# ===================================================== Alan eşlemesi
class TestMarcAlanlari:
    def test_kunye_alanlari_okunur(self) -> None:
        oneri, sayi = marc.govdeden_oneri(marcxml(kayit(yer_no="894.353 ALI")), isbn13=ISBN)

        assert oneri is not None
        assert oneri.title == "Kürk mantolu Madonna"
        assert oneri.authors == "Sabahattin Ali"  # MARC'ın ters yazımı düzeltilir
        assert oneri.publisher == "Yapı Kredi Yayınları"
        assert oneri.publish_year == 2015
        assert oneri.pages == 160
        assert oneri.subjects == "Türk edebiyatı, Roman"
        assert oneri.classification_code == "894.353"
        assert oneri.call_number == "894.353 ALI"
        assert oneri.language == "Türkçe"
        assert oneri.place == "İstanbul"
        assert oneri.isbn == ISBN
        assert sayi == 1

    def test_alt_baslik_ada_eklenir(self) -> None:
        oneri, _ = marc.govdeden_oneri(
            marcxml(kayit(ad="Sinekli Bakkal :", alt_ad="roman /")), isbn13=ISBN
        )

        assert oneri is not None
        assert oneri.title == "Sinekli Bakkal roman"

    def test_cevirmen_alani_doldurulmaz(self) -> None:
        """§8.5-5: 245$c ve 700 çevirmeni taşır; öneride çevirmen alanı YOKTUR."""
        oneri, _ = marc.govdeden_oneri(marcxml(kayit()), isbn13=ISBN)

        assert oneri is not None
        assert "translator" not in oneri.alan_sozlugu()
        assert "Uydurma Çevirmen" not in " ".join(str(d) for d in oneri.alan_sozlugu().values())
        assert UYARI_CEVIRMEN in oneri.uyarilar
        assert UYARI_YAZAR in oneri.uyarilar

    def test_cok_virgullu_yazar_adina_dokunulmaz(self) -> None:
        oneri, _ = marc.govdeden_oneri(
            marcxml(kayit(yazar="Ali, Sabahattin, 1907-1948")), isbn13=ISBN
        )

        assert oneri is not None
        assert oneri.authors == "Ali, Sabahattin, 1907-1948"

    def test_yanitin_metni_temizlenir_ve_nfc_olur(self) -> None:
        ayrisik = unicodedata.normalize("NFD", "İletişim")
        oneri, _ = marc.govdeden_oneri(marcxml(kayit(yayinevi=f"{ayrisik},")), isbn13=ISBN)

        assert oneri is not None
        assert oneri.publisher == "İletişim"
        assert unicodedata.is_normalized("NFC", oneri.publisher)


# ===================================================== Mükerrer kayıt kuralı
class TestMukerrerKayit:
    def test_en_zengin_kayit_secilir_ve_sayi_bildirilir(self) -> None:
        """Tek ISBN için 123 kayıt döndüğü ölçüldü; program ilkini sessizce almaz."""
        govde = marcxml(
            kayit(ad="Yoksul kayıt /", dewey="", konular=(), sayfa="")
            + kayit(ad="Zengin kayıt /", dewey="894.353", yer_no="894.353 ALI"),
            toplam=123,
        )

        oneri, sayi = marc.govdeden_oneri(govde, isbn13=ISBN)

        assert oneri is not None
        assert oneri.title == "Zengin kayıt"
        assert sayi == 123

    def test_kayit_yoksa_none_doner(self) -> None:
        oneri, sayi = marc.govdeden_oneri(marcxml("", toplam=0), isbn13=ISBN)

        assert oneri is None
        assert sayi == 0


# ===================================================== Bakanlık adaptörü
class TestBakanlikAdaptoru:
    def test_yanit_onerilere_cevrilir(self) -> None:
        acici = SahteAcici(SahteYanit(marcxml(kayit())))

        oneri, sayi = bakanlik.sorgula(ISBN, acici=acici)

        assert oneri is not None
        assert oneri.title == "Kürk mantolu Madonna"
        assert sayi == 1

    def test_bos_govde_ag_hatasidir(self) -> None:
        acici = SahteAcici(SahteYanit(b""))

        with pytest.raises(KunyeAgHatasi):
            bakanlik.sorgula(ISBN, acici=acici)


# ===================================================== Open Library adaptörü
class TestOpenLibraryAdaptoru:
    def _govde(self, **alanlar: object) -> bytes:
        kayit_verisi = {
            "title": "Kürk Mantolu Madonna",
            "author_name": ["Sabahattin Ali"],
            "publisher": ["Do&#x11F;an Kitap"],
            "publish_year": [2015, 2018],
            "number_of_pages_median": 160,
            "language": ["tur"],
            "subject": ["Türk edebiyatı", "Roman"],
        }
        kayit_verisi.update(alanlar)
        return json.dumps({"numFound": 3, "docs": [kayit_verisi]}).encode("utf-8")

    def test_kunye_alanlari_okunur(self) -> None:
        oneri, sayi = openlibrary.govdeden_oneri(self._govde(), isbn13=ISBN)

        assert oneri is not None
        assert oneri.title == "Kürk Mantolu Madonna"
        assert oneri.authors == "Sabahattin Ali"
        assert oneri.publisher == "Doğan Kitap"  # ölçülen ham HTML varlığı çözüldü
        assert oneri.publish_year == 2015
        assert oneri.pages == 160
        assert oneri.language == "Türkçe"
        assert oneri.subjects == "Türk edebiyatı, Roman"
        assert sayi == 3

    def test_ayrisik_kod_noktalari_nfcye_cevrilir(self) -> None:
        ayrisik = unicodedata.normalize("NFD", "İletişim")
        oneri, _ = openlibrary.govdeden_oneri(self._govde(publisher=[ayrisik]), isbn13=ISBN)

        assert oneri is not None
        assert oneri.publisher == "İletişim"

    def test_uydurma_tarih_yil_uretmez(self) -> None:
        oneri, _ = openlibrary.govdeden_oneri(
            self._govde(publish_year=["13 Nisan"], first_publish_year=[]), isbn13=ISBN
        )

        assert oneri is not None
        assert oneri.publish_year is None

    def test_cevirmen_uyarisi_ve_yazar_uyarisi_gelir(self) -> None:
        oneri, _ = openlibrary.govdeden_oneri(self._govde(), isbn13=ISBN)

        assert oneri is not None
        assert UYARI_CEVIRMEN in oneri.uyarilar
        assert UYARI_YAZAR in oneri.uyarilar

    def test_kayit_yoksa_none_doner(self) -> None:
        govde = json.dumps({"numFound": 0, "docs": []}).encode("utf-8")

        assert openlibrary.govdeden_oneri(govde, isbn13=ISBN) == (None, 0)

    def test_eser_adi_yoksa_oneri_uretilmez(self) -> None:
        oneri, _ = openlibrary.govdeden_oneri(self._govde(title=""), isbn13=ISBN)

        assert oneri is None

    @pytest.mark.parametrize("govde", [b"{bozuk", b"[]", b"\xff\xfe"])
    def test_bozuk_govde_ag_hatasina_cevrilir(self, govde: bytes) -> None:
        with pytest.raises(KunyeAgHatasi):
            openlibrary.govdeden_oneri(govde, isbn13=ISBN)
