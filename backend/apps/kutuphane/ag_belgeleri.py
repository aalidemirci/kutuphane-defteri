"""Ağ Kataloğu belgeleri: afiş, Ağ Hizmeti Bilgi Notu, yer imi dosyaları, PYS talep metni.

Tasarım §5.6, §5.9, §10 E3. PDF'ler TEK KAPIDAN (`shared.pdf.html_to_pdf`)
basılır. Belgeler yerel üretilir ve okulda kalır; bu yüzden bilgisayarın gerçek
IP adresini ve tahta ağı bloklarını taşıyabilir (§5.9). Hiçbiri yönetim portunu
taşımaz (§4.1) ve hiçbirinde kişisel veri yoktur.

- **Katalog afişi**: adres büyük ve birincil, QR küçük ve ikincil (SU-14);
  dayanak yazılmaz. Afiş basılınca adres `son_afis_ip` olarak kaydedilir: gün
  değişimi kapısı IP değişince "afişi yeniden basın, yer imlerini güncelleyin"
  uyarısını bu değerle karşılaştırır.
- **Ağ Hizmeti Bilgi Notu**: §5.9'daki bütün maddeler — demirbaş no, port ve
  gerekçesi, kuraldaki GERÇEK uzak adres ve profil (güvenlik duvarı denetiminin
  okuduğu değerler), ne sunulup ne sunulmadığı, kişisel veri olmadığı,
  programın giden bağlantıları (künye sorgusu açık/kapalı durumuna göre),
  BTR'nin sınama komutları, Yönerge atıfları, BTR ve müdür imza alanları.
- **Yer imi dosyaları** (ZIP): ETAP/Pardus Chromium `ManagedBookmarks` politika
  dosyası ve `.desktop` başlatıcı (tahta kipi, `?tahta=1`), Windows `.url`
  kısayolları ve nereye konacaklarını anlatan BENIOKU.
- **PYS talep metni**: "yerel ağ VLAN düzenlemesi — tek yön, TCP/<port>"
  (R8 §1-14: "internet/site açma" diye yazılırsa filtre birimine gider).

Modül `services/` altında DEĞİLDİR: bilgi notu künye sorgusunun hedef adreslerini
künye paketinin kendi sabitlerinden okur, `services/*.py` ise künye paketini hiç
içe aktarmaz (§5.10-19a, `test_kunye_servisi.py` kaynak taraması — toplu içe
aktarma yolundan künye modülüne ulaşılamasın). Bu modül yalnız belge uçlarından
çağrılır; ağa çıkmaz.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from typing import Any, Final
from urllib.parse import urlparse

from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane.kunye.istemci import BAKANLIK_HOST, OPENLIBRARY_HOST
from apps.kutuphane.labels.metrics import largest_fitting_size
from apps.kutuphane.models import KATALOG_VARSAYILAN_PORT, LibraryPolicy
from apps.kutuphane.services import ag_doktoru
from apps.kutuphane.services import katalog_ayari as katalog_ayari_service
from apps.okul.models import SchoolConfig
from apps.okul.services import updates
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

AFIS_SABLONU: Final = "documents/katalog_afisi.html"
BILGI_NOTU_SABLONU: Final = "documents/ag_hizmeti_bilgi_notu.html"

#: Belge adları (sözlük §2, E3) — dosya adları ve başlıklar buradan.
AFIS_ADI: Final = "Katalog Afişi"
BILGI_NOTU_ADI: Final = "Ağ Hizmeti Bilgi Notu"
YER_IMI_ADI: Final = "Yer İmi Dosyaları"

#: Adres kutusunun iç genişlik bütçesi (A4, 16 mm kenar payları, kutu çerçevesi ve iç
#: boşluğu düşülmüş; güvenlik payı bırakılmış).
ADRES_GENISLIGI_MM: Final = 160.0
ADRES_PUNTOLARI: Final = (44.0, 40.0, 36.0, 32.0, 30.0, 28.0, 26.0, 24.0, 22.0, 20.0, 18.0)
QR_KENARI_MM: Final = 26.0
QR_SESSIZ_BOLGE: Final = 4

#: Yer imi dosyalarında görünen ad (Türkçe; dosya ADLARI ASCII'dir — ETAP ve Windows
#: arşiv açıcıları arasında ad kodlaması tutarsızdır).
YER_IMI_BASLIGI: Final = "Kütüphane Kataloğu"

_PROFIL_ADLARI: Final = {
    "Domain": "Etki alanı",
    "DomainAuthenticated": "Etki alanı",
    "Private": "Özel",
    "Public": "Genel",
}
_MADDE_DURUMLARI: Final = {
    "gecti": "Geçti",
    "kaldi": "Geçmedi",
    "uyari": "Uyarı",
    "bilinmiyor": "Denetlenemedi",
}


def _gun() -> date:
    return timezone.localdate()


def belge_dosya_adi(ad: str, uzanti: str, gun: date | None = None) -> str:
    """ "Katalog-Afişi_24.09.2026.pdf" — belge adı + yerel tarih (sözlük §3)."""
    return f"{ad.replace(' ', '-')}_{(gun or _gun()):%d.%m.%Y}.{uzanti}"


# ------------------------------------------------------------------ QR


def qr_svg(metin: str, kenar_mm: float = QR_KENARI_MM) -> str:
    """mm ölçülü bağımsız SVG QR; 4 modül sessiz bölge (etiket motorundaki çizimle aynı yol)."""
    satirlar = ag_doktoru.qr_satirlari(metin)
    boyut = len(satirlar)
    toplam = boyut + 2 * QR_SESSIZ_BOLGE
    parcalar: list[str] = []
    for satir_no, satir in enumerate(satirlar):
        sutun = 0
        while sutun < boyut:
            if satir[sutun] == "1":
                bas = sutun
                while sutun < boyut and satir[sutun] == "1":
                    sutun += 1
                parcalar.append(
                    f'<rect x="{bas + QR_SESSIZ_BOLGE}" y="{satir_no + QR_SESSIZ_BOLGE}" '
                    f'width="{sutun - bas}" height="1"/>'
                )
            else:
                sutun += 1
    kenar = f"{kenar_mm:.3f}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{kenar}mm" height="{kenar}mm" '
        f'viewBox="0 0 {toplam} {toplam}" shape-rendering="crispEdges">'
        f'<rect width="{toplam}" height="{toplam}" fill="#fff"/>'
        f'<g fill="#000">{"".join(parcalar)}</g></svg>'
    )


# ------------------------------------------------------------------ afiş


def adres_puntosu(adres: str) -> float:
    """Adresin tek satıra sığdığı en büyük punto (DejaVu Sans Bold ölçüleriyle)."""
    boy = largest_fitting_size([adres], ADRES_GENISLIGI_MM, ADRES_PUNTOLARI, bold=True)
    return boy if boy is not None else ADRES_PUNTOLARI[-1]


def afis_baglami(ip: str) -> dict[str, Any]:
    ayar = katalog_ayari_service.katalog_ayari()
    config = SchoolConfig.load()
    adres = ag_doktoru.katalog_adresi(ip, int(ayar.port))
    return {
        "school_name": " ".join((config.school_name or "").split()),
        "adres": adres,
        "adres_punto": f"{adres_puntosu(adres):g}",
        "qr_svg": qr_svg(adres),
        "kutuphane_saatleri": (config.kutuphane_saatleri or "").strip(),
    }


def afis_pdf(ip: str) -> bytes:
    """Afişin PDF'i. Afişteki IP `son_afis_ip` olarak kaydedilir (IP değişimi uyarısı)."""
    pdf = html_to_pdf(render_to_string(AFIS_SABLONU, afis_baglami(ip)))
    katalog_ayari_service.update_katalog_ayari(son_afis_ip=ip)
    return pdf


# ------------------------------------------------------------ Ağ Hizmeti Bilgi Notu


def port_gerekcesi(port: int, platform: str | None = None) -> str:
    """Portun gerekçesi (A5): notta ve PYS talep metninde aynı cümle.

    Son cümle platforma bağlıdır: Windows'ta port değişikliği güvenlik duvarı
    kuralını da günceller (UAC yardımcısı); Pardus'ta program kural açmaz ve
    değiştirmez, komut yeni portla yeniden çalıştırılır. Cümle "BTR" geçirmez:
    PYS talep metninde kısaltmanın ilk geçişi açılımlıdır (sözlük §2).
    """
    varsayilan = (
        f"{port} programın varsayılan portudur. "
        if port == KATALOG_VARSAYILAN_PORT
        else f"{port} okulun seçtiği porttur (programın varsayılanı {KATALOG_VARSAYILAN_PORT}). "
    )
    degisiklik = (
        "port değişince güvenlik duvarı komutu yeni portla yeniden çalıştırılır (Pardus'ta "
        "program güvenlik duvarı kuralını açmaz ve değiştirmez)."
        if (platform or ag_doktoru.platform_adi()) == ag_doktoru.LINUX
        else "değişiklik güvenlik duvarı kuralını da günceller."
    )
    return (
        varsayilan + "80 ve 443 bu bilgisayardaki başka web bileşenleriyle çakışabilir; 1024'ün "
        "altındaki portlar Pardus'ta yönetici yetkisi ister; 8080, 8000 ve 5000 gibi yaygın "
        "portlar başka programlarca kullanılabilir. Katalog kişisel veri taşımadığı için "
        "sertifika gerektirmeyen düz HTTP ile çalışır. Port programın ayarlarından "
        "değiştirilebilir; " + degisiklik
    )


def _profil_metni(profil: object) -> str:
    metin = str(profil or "").strip()
    if not metin:
        return ""
    if metin.lower() == "any":
        return "Hepsi (Etki alanı, Özel, Genel)"
    parcalar = [p.strip() for p in metin.replace(";", ",").split(",") if p.strip()]
    return ", ".join(_PROFIL_ADLARI.get(p, p) for p in parcalar)


def _uzak_adres_metni(adresler: object) -> str:
    liste = (
        [str(a) for a in (adresler or []) if str(a).strip()] if isinstance(adresler, list) else []
    )
    if not liste:
        return "Okunamadı"
    return ", ".join(
        "LocalSubnet (yalnız yerel alt ağ)" if a.lower() == "localsubnet" else a for a in liste
    )


def _kural_satirlari(kural: dict[str, Any] | None) -> dict[str, Any] | None:
    if not kural:
        return None
    portlar = kural.get("yerel_port") or []
    return {
        "ad": str(kural.get("ad") or ""),
        "program": str(kural.get("program") or ""),
        "yerel_port": ", ".join(str(p) for p in portlar) if isinstance(portlar, list) else "",
        "uzak_adres": _uzak_adres_metni(kural.get("uzak_adres")),
        "profil": _profil_metni(kural.get("profil")) or "Okunamadı",
        "etkin": bool(kural.get("etkin")),
    }


def _kural_listesi(denetim: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Denetimin okuduğu BÜTÜN izin kuralları (Windows herhangi birine uyanı kabul eder).

    Eski biçimde (yalnız `kural`) gelen okuma tek satırlı listeye çevrilir.
    """
    denetim = denetim or {}
    ham = denetim.get("kurallar")
    kurallar = ham if isinstance(ham, list) and ham else [denetim.get("kural")]
    return [
        satir
        for satir in (_kural_satirlari(k) if isinstance(k, dict) else None for k in kurallar)
        if satir is not None
    ]


def _madde_satirlari(maddeler: object) -> list[dict[str, str]]:
    if not isinstance(maddeler, list):
        return []
    return [
        {
            "durum": _MADDE_DURUMLARI.get(str(m.get("durum")), str(m.get("durum") or "")),
            "baslik": str(m.get("baslik") or ""),
            "aciklama": str(m.get("aciklama") or ""),
        }
        for m in maddeler
        if isinstance(m, dict)
    ]


def _guvenlik_duvari_okumasi() -> dict[str, Any] | None:
    """Denetimin GÜNCEL okuması (notta kuraldaki gerçek değerler); masaüstü yoksa None."""
    from apps.okul import masaustu_kanca

    denetci = masaustu_kanca.katalog_kontrolu()
    if denetci is None:
        return None
    try:
        return denetci.guvenlik_duvari()
    except Exception:  # noqa: BLE001 — okunamazsa not elle doldurulacak alanlarla basılır
        durum = denetci.durum().get("guvenlik_duvari")
        return durum if isinstance(durum, dict) else None


#: Kurulum dosyasının indirildiği alan. `updates._safe_release_url` indirme adresini
#: bu alanla sınırlar; GitHub sürüm eki indirmesini kendi içerik alanına yönlendirir
#: ve `urlopen` yönlendirmeyi izler (hedef adı GitHub'ın elindedir, joker yazılır).
INDIRME_HOST: Final = "github.com"
INDIRME_YONLENDIRME: Final = "*.githubusercontent.com"


def guncelleme_hedefleri() -> list[str]:
    """Güncelleme denetiminin gerçek hedefleri (kaynak koddaki adreslerden türetilir)."""
    denetim = urlparse(updates.LATEST_RELEASE_URL)
    return [
        f"{denetim.hostname} (HTTPS, 443) — yayımlanan son sürüm sorulur",
        f"{INDIRME_HOST} ve indirmenin yönlendirildiği {INDIRME_YONLENDIRME} (HTTPS, 443) — "
        "yalnız kurulum dosyası indirilirse",
    ]


def kunye_hedefleri(politika: LibraryPolicy) -> list[str]:
    hedefler: list[str] = []
    if politika.metadata_lookup_ministry:
        hedefler.append(f"{BAKANLIK_HOST} (HTTP, 210) — Kültür ve Turizm Bakanlığı kataloğu")
    if politika.metadata_lookup_openlibrary:
        hedefler.append(f"{OPENLIBRARY_HOST} (HTTPS, 443) — Open Library")
    return hedefler


def kunye_disari_cikar(politika: LibraryPolicy) -> bool:
    """Künye sorgusu gerçekten dışarı çıkabilir mi? Ana bayrak + en az bir kaynak.

    Bayrak açık ama iki kaynak da kapalıysa program künye isteği atmaz: not bu
    durumu "kapalı" gibi yazar (boş hedef listesi ve 11/12-11/19 atıfları basılmaz).
    """
    return bool(politika.metadata_lookup_enabled) and bool(kunye_hedefleri(politika))


def dis_komutlar(politika: LibraryPolicy) -> list[str]:
    """BTR'nin bu bilgisayardan sınayacağı dış adresler (S15)."""
    denetim = urlparse(updates.LATEST_RELEASE_URL).hostname
    komutlar = [
        f"Test-NetConnection {denetim} -Port 443",
        f"Test-NetConnection {INDIRME_HOST} -Port 443",
    ]
    if kunye_disari_cikar(politika):
        if politika.metadata_lookup_ministry:
            komutlar.append(f"Test-NetConnection {BAKANLIK_HOST} -Port 210")
        if politika.metadata_lookup_openlibrary:
            komutlar.append(f"Test-NetConnection {OPENLIBRARY_HOST} -Port 443")
    return komutlar


def bilgi_notu_baglami(ip: str | None) -> dict[str, Any]:
    ayar = katalog_ayari_service.katalog_ayari()
    config = SchoolConfig.load()
    politika = LibraryPolicy.load()
    port = int(ayar.port)
    denetim = _guvenlik_duvari_okumasi()
    platform = ag_doktoru.platform_adi()
    if denetim is not None:
        platform = "windows" if denetim.get("platform") == "windows" else "linux"
    linux = dict((denetim or {}).get("linux") or {})
    etkin = linux.get("etkin")
    linux["etkin_metni"] = (
        "etkin" if etkin is True else "kapalı" if etkin is False else "durumu okunamadı"
    )
    ag_profilleri = [
        _PROFIL_ADLARI.get(str(p), str(p)) for p in (denetim or {}).get("ag_profilleri") or []
    ]
    hedef_ip = ip or "<IP>"
    kurallar = _kural_listesi(denetim)
    return {
        **letterhead_context(
            school_name=config.school_name,
            district=config.district,
            principal_name=config.principal_name,
        ),
        "document_title": "AĞ HİZMETİ BİLGİ NOTU",
        "issued_on": f"{_gun():%d.%m.%Y}",
        "asset_no": (config.demirbas_no or "").strip(),
        "program": f"Kütüphane Defteri {updates.get_app_version()}",
        "ip": ip or "",
        "adres": ag_doktoru.katalog_adresi(ip, port) if ip else "",
        "port": port,
        "dinleme": ag_doktoru.dinleme_ozeti(ayar),
        "ag_profilleri": ", ".join(dict.fromkeys(ag_profilleri)),
        "port_gerekcesi": port_gerekcesi(port, platform),
        "platform": platform,
        # İlk kural (programın kendi adlı kuralı) tam tabloyla; öbürleri kısa satırla
        # (sayfa bütçesi: en çok iki sayfa). Hepsi basılır: BTR gerçek kapsamı görür.
        "kurallar": kurallar,
        "kural": kurallar[0] if kurallar else None,
        "ek_kurallar": [
            {**k, "program_farkli": k["program"] != kurallar[0]["program"]} for k in kurallar[1:]
        ],
        "maddeler": _madde_satirlari((denetim or {}).get("maddeler")),
        "linux": linux,
        "tahta_bloklari": [str(b) for b in (ayar.tahta_cidrleri or [])],
        "kunye_acik": kunye_disari_cikar(politika),
        "kunye_hedefleri": kunye_hedefleri(politika),
        "guncelleme_hedefleri": guncelleme_hedefleri(),
        "katalog_komutu": f"Test-NetConnection {hedef_ip} -Port {port}",
        "dis_komutlar": dis_komutlar(politika),
    }


def bilgi_notu_pdf(ip: str | None) -> bytes:
    return html_to_pdf(render_to_string(BILGI_NOTU_SABLONU, bilgi_notu_baglami(ip)))


# ------------------------------------------------------------------ yer imleri


def chromium_politikasi(adres: str) -> str:
    """ETAP/Pardus Chromium yönetilen yer imi politikası (`/etc/chromium/policies/managed/`)."""
    politika = {
        "ManagedBookmarks": [
            {"toplevel_name": "Okul"},
            {"name": YER_IMI_BASLIGI, "url": adres},
        ]
    }
    return json.dumps(politika, ensure_ascii=False, indent=2) + "\n"


def desktop_baslatici(adres: str) -> str:
    """`/usr/share/applications/` için başlatıcı: varsayılan tarayıcıda açar.

    Desktop Entry belirtimine göre `?` ayrılmış karakterdir; adres çift tırnak
    içinde verilir (adreste tırnak, ters bölü, `$` ya da ters tırnak geçmez).
    """
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={YER_IMI_BASLIGI}\n"
        "Comment=Okul kütüphanesinin katalogunda kitap arayın\n"
        f'Exec=xdg-open "{adres}"\n'
        "Icon=accessories-dictionary\n"
        "Terminal=false\n"
        "Categories=Education;\n"
    )


def url_kisayolu(adres: str) -> str:
    """Windows İnternet kısayolu (.url; ASCII, CRLF)."""
    return f"[InternetShortcut]\r\nURL={adres}\r\n"


def _benioku(adres: str, tahta_adresi: str) -> str:
    return (
        f"{YER_IMI_BASLIGI} — yer imi dosyaları\n"
        f"Düzenlenme tarihi: {_gun():%d.%m.%Y}\n\n"
        f"Katalog adresi: {adres}\n"
        f"Tahtalar için (büyük düzen): {tahta_adresi}\n\n"
        "Bu dosyaların tahtalara ve bilgisayarlara dağıtımı okulun bilişim teknolojileri\n"
        "rehber öğretmeninin (BTR) işidir. Liderahenk ile toplu dağıtım yetkisini BTR'ye\n"
        "sorun. Kullanıcı başına yer imi yetmez: tahtalarda her öğretmenin ayrı hesabı olabilir.\n\n"
        "pardus-etap/kutuphane-katalogu-chromium.json\n"
        '  Chromium\'un yönetilen yer imleri. Bütün hesaplarda yer imleri menüsünde, "Okul"\n'
        "  klasöründe görünür; yer imi çubuğu açıksa çubukta da durur (Chromium çubuğu\n"
        "  varsayılan olarak yalnız yeni sekme sayfasında gösterir):\n"
        "  sudo install -D -m 644 kutuphane-katalogu-chromium.json \\\n"
        "      /etc/chromium/policies/managed/kutuphane-katalogu.json\n"
        "  Çubuğun her sayfada görünmesi istenirse okulun kararıyla aynı dosyaya\n"
        '  "BookmarkBarEnabled": true satırı eklenir. Tahtada ManagedBookmarks içeren\n'
        "  başka bir politika dosyası varsa ikisi TEK dosyada birleştirilir: aynı politika\n"
        "  iki dosyada tanımlanırsa yalnız biri geçerli olur.\n\n"
        "pardus-etap/kutuphane-katalogu.desktop\n"
        "  Uygulama menüsüne kısayol ekler; varsayılan tarayıcıda açar:\n"
        "  sudo install -m 644 kutuphane-katalogu.desktop /usr/share/applications/\n\n"
        "windows/Kutuphane-Katalogu.url\n"
        "  Öğretmen ve laboratuvar bilgisayarları için masaüstü kısayolu.\n"
        "windows/Kutuphane-Katalogu-Tahta.url\n"
        "  Windows tahtalar için (büyük düzen).\n\n"
        "Bilgisayarın IP adresi değişirse bu dosyaları Ağ Doktoru'ndan yeniden üretin ve\n"
        "eskilerinin yerine koyun; katalog afişini de yeniden basın.\n"
    )


def yer_imi_zip(ip: str) -> bytes:
    """Yer imi dosyalarının ZIP'i (modül belgesi). Tahtaya giden adres `?tahta=1` taşır."""
    port = int(katalog_ayari_service.katalog_ayari().port)
    adres = ag_doktoru.katalog_adresi(ip, port)
    tahta = ag_doktoru.katalog_adresi(ip, port, tahta=True)
    dosyalar = {
        "BENIOKU.txt": _benioku(adres, tahta),
        "pardus-etap/kutuphane-katalogu-chromium.json": chromium_politikasi(tahta),
        "pardus-etap/kutuphane-katalogu.desktop": desktop_baslatici(tahta),
        "windows/Kutuphane-Katalogu.url": url_kisayolu(adres),
        "windows/Kutuphane-Katalogu-Tahta.url": url_kisayolu(tahta),
    }
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as arsiv:
        for ad, icerik in dosyalar.items():
            arsiv.writestr(ad, icerik.encode("utf-8"))
    return tampon.getvalue()


# ------------------------------------------------------------------ PYS talep metni


def pys_talep_metni(ip: str | None) -> str:
    """FATİH PYS'ye yapıştırılacak talep metni ("yerel ağ VLAN düzenlemesi")."""
    ayar = katalog_ayari_service.katalog_ayari()
    config = SchoolConfig.load()
    port = int(ayar.port)
    okul = " ".join((config.school_name or "").split()) or "……………………"
    hedef = ip or "……………………"
    # Sözlük §2: BTR ilk geçişte açılır. Bloklar boşken ilk geçiş yer tutucudadır.
    bloklar = ", ".join(str(b) for b in (ayar.tahta_cidrleri or []))
    btr = "BTR'sinin"
    if not bloklar:
        bloklar = "…………………… (tahta ağı bloğu; bilişim teknolojileri rehber öğretmeni (BTR) yazar)"
    else:
        btr = "bilişim teknolojileri rehber öğretmeninin (BTR)"
    return (
        f"Konu: Yerel ağ VLAN düzenlemesi — tek yön, TCP/{port}\n\n"
        f"{okul} kütüphanesindeki demirbaş bilgisayarda çalışan salt okur kütüphane "
        "kataloğuna okulun etkileşimli tahta ağından erişilebilmesi için yerel ağ VLAN "
        "düzenlemesi talep edilmektedir. Talep internet ya da site erişimi talebi değildir; "
        "trafik okul ağının içinde kalır.\n\n"
        "Talep ayrıntısı:\n"
        f"- Kaynak: {bloklar}\n"
        f"- Hedef: {hedef} (kütüphane bilgisayarı), TCP {port}\n"
        "- Yön: tek yön — tahtalardan kütüphane bilgisayarına. Kütüphane bilgisayarı "
        "tahtalara bağlantı başlatmaz.\n"
        "- Protokol: HTTP, yalnız sayfa okuma.\n\n"
        "Hizmetin niteliği:\n"
        "- Kütüphane kataloğu: eser künyesi, raf yeri ve nüshanın rafta ya da ödünçte "
        "olduğu bilgisi.\n"
        "- Kişisel veri içermez (üye, ödünç alan, iade tarihi ve ödünç geçmişi yoktur).\n"
        "- Uzaktan erişim, dosya ya da yazıcı paylaşımı değildir; yönetim işlevi bu "
        "porttan sunulmaz.\n"
        f"- Port gerekçesi: {port_gerekcesi(port)}\n\n"
        f"Okulun {btr} ve okul müdürünün "
        "imzaladığı Ağ Hizmeti Bilgi Notu okulda saklanmaktadır; istenirse gönderilir.\n"
    )
