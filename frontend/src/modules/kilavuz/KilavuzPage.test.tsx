// Kullanım Kılavuzu testleri. Bölümler özelliklerle birlikte eklendikçe her
// bölümün çekirdek metni burada kilitlenir — özellik kılavuzda ANLATILMADAN
// sürüme girmesin (tasarım §14.1 "kılavuz bölümü" iş kalemi).
//
// F1 bölümleri (iş sırasıyla): ilk kurulum, başlangıç yol haritası, görevli ve
// yönetici kipi, kişiler ve e-Okul listeleri, kapalı günler, katalog Excel
// şablonu, yedek ve güvenlik dosyası, Ağ Kataloğu.
// F2 bölümü: Katalog (kapalı günler ile Excel şablonunun arasında).
// F3 bölümleri: Hızlı Kayıt (katalogdan hemen sonra — okulda hazır liste yoktur,
// katalog kitap kitap kurulur) ve İçe Aktarma (Excel şablonundan sonra). Hızlı
// Kayıt bölümü iki geçiş yolunu ("önce liste" / "önce etiket") karşılaştırarak
// açar; testi hangisinin asıl yol olduğunu da kilitler.
// F5 bölümleri: Tepsi, Çıkış ve Gün Değişimi (yedekten sonra) ve Ağ Kataloğu.
// Ekran adları sabitlerden (AG_DOKTORU_BASLIGI, DINLEME_KIPI_TR,
// KATALOG_DURUMU_TR, MADDE_DURUMU_TR, AG_PROFILI_TR, COPY_STATUS_TR, bilgi notu
// belge adı) doğrulanır. Python ve Inno kaynağındaki adlar buradan okunamaz;
// birebir kopyalandı ve kaynakları testin yanında yazılı: tepsi menüsü
// (desktop/tray.py), tepsi durum satırı ve adres uyarısı
// (desktop/katalog_kontrol.py), kurucu görevleri (kutuphane-defteri.iss),
// kataloğun kendi üst menüsü (backend/katalog/sablonlar/taban.html). Kilitlenenler:
// Ağ Kataloğunun neyi gösterip neyi ASLA göstermediği (kişisel veri yok),
// BTR'yle yapılacak beş iş, Yönerge 11/6, 11/12, 11/22 alıntıları, açma
// kartının adımları, Ağ Doktoru'nun beş kartı, ETAP'ın öğretmen başına hesabı
// (politika dosyası), tahta kipi, adres değişince yapılacaklar, görevli
// kipinde Çık, gün değişimi ve uyku.
// F4 bölümü: Etiketler (Hızlı Kayıt'ın ardında). Sekme, düğme ve seçenek adları
// ekran sabitlerinden (ETIKETLER_SEKMELERI, ETIKET_YOLLARI, ETIKET_ICERIGI_TR,
// BASIM_SIRASI_TR, PARTI_DURUMU_TR) doğrulanır; sabiti olmayan düğme ve alan
// adları ekranın kaynağından (EtiketKuyrugu, etiketOrtak, BasimGecmisi,
// BosBarkodPaneli, DogrulamaOkutmasi, SablonlarPaneli) birebir kopyalandı.
// Kilitlenenler: satın alma notu (QR kararı tabakayı belirler), kalibrasyon
// adımları ve işaret kuralı, basım sırası, "PDF'i almak basıldı saymaz" ve geri
// alma, doğrulama okutması, önce etiket yolunun SIRALI adımları, bozulan ve
// kaybolan etiketin iki ayrı yolu, sırtı dar kitap ve koruyucu bant önerisi.
// F6 bölümleri: Üyelik, Kart ve Belgeler ile Dolaşım Masası (Etiketler'in ardında).
// Adlar `modules/dolasim`, `modules/uyelik` ve görevli ekranının sabitlerinden;
// sunucu iletileri birebir kopyalandı (kaynakları testin yanında; sunucu tarafı
// `test_dolasim_metinleri.py` aynı iletileri sabitlerden sınar). Kilitlenenler:
// aydınlatma metni e-Okul aktarımından ÖNCE (bölümün ilk alt başlığı, Kişiler'de
// ipucu), Md. 18/1 alıntısı ve kaymanın iki ayrı kural olup Yönetmeliğe
// bağlanmaması, sayı sınırının hiçbir kipte istisna almaması, gecikme engeli ve
// gerekçeli istisna, iadenin hiçbir durumda kilitlenmemesi, görevlinin gördüğü ve
// görmediği, kartsız ödünç (Md. 23/1-a alıntısı), pusulanın dağıtım kuralı, masa
// kartı (KVKK 12/1 alıntısı) ve "sonraki sürümde" sözlerinin kalkması.
// F7 bölümleri: Sınıf Kitaplığına ve Öğretmene Teslim, Kayıp, Hasar ve Onarım, İlişik
// Listesi, Yıl Sonu ve Yıl Başı (dördü de Dolaşım Masası'nın ardında). Adlar
// `modules/teslim`, `modules/kayip`, `modules/yil`, masanın ve görevli ekranının
// sabitlerinden; sunucu iletileri birebir kopyalandı (sunucu tarafı
// `test_teslim_ilisik_kilavuz_metinleri.py` aynı iletileri ve Md. 18/1, 19/1
// alıntılarını sabitlerden ve docs/mevzuat'tan sınar). Kilitlenenler: teslim ödünç
// değildir (sayı sınırı, süre ve "kalan hak" dili yok), teslim tek işlemdir, beklenen
// dönüşün geçmesi gecikme değildir, geri alma görevli kipinde de açıktır, şube
// listesinde TMY 23/6'ya kıyasen notu ve sayımdaki yer; kayıp bildirimi ödüncü/teslimi
// "Kayba dönüştü" ile kapatır ve "Bulundu" yeniden açmaz, bedel yolları YALNIZ
// ortaöğretimde, program tahsilat yapmaz ve disiplin sürecini başlatmaz; ilişik
// belgesi karne ya da diploma ön koşulu DEĞİLDİR (iki sözcük yalnız o olumsuz cümlede
// geçer); yıl sonu ve yıl başının dörder adımı; kip sürelerinin ayarı (Kipler).
//
// Üç tür kilit var:
// 1. Ekran adları DEPODAN gelir: kısayol, kip ekranı başlığı, kapalı gün türleri,
//    üye türleri, kademeler, şablon adı ve güvenlik dosyası ekranının başlığı
//    ekran sabitlerinden okunur; ekrandaki ad değişirse kılavuz da değişmek
//    zorunda kalır.
// 2. Sözlük (docs/sozluk.md, bağlayıcı): iç kodlar (F1, U5, E14, GA-…) ve yasak
//    sözcükler ("uygulama parolası", "şifre", "OPAC", "okuduğu kitaplar"…) geçmez;
//    BTR ilk geçişte açılır; kaydırılmış iade tarihi "Md. 18 gereği" diye sunulmaz.
// 3. Mevzuat alıntıları docs/mevzuat'taki metinle BİREBİR yazılır (buradaki
//    beklenen metinler o dosyalardan kopyalandı).
//
// Metin denetimleri `textContent` üzerinden yapılır: `getByText` yalnız tek
// elemanın metnine baktığından <strong>/<kbd> sınırını aşan ifade eşleşmezdi.

import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  AG_DOKTORU_ADRESI,
  AG_DOKTORU_BASLIGI,
  AG_KATALOGU_SEKMESI,
  AG_PROFILI_TR,
  BILGI_NOTU_BELGE_ADI,
  DINLEME_KIPI_TR,
  KATALOG_DURUMU_TR,
  MADDE_DURUMU_TR,
} from "../agkatalogu/api";
import {
  BAGLAM_SURESI_MS,
  BASKA_UYEDE_SORUSU,
  BASKA_UYEDEN_IADE_UYARISI,
  BITTI_DUGMESI,
  BU_UYEDE_SORUSU,
  DURUM_SORGUSU,
  DURUM_SORGUSU_KAPANDI,
  IADE_ONERISI,
  ISTEM_BAGLAM_DEGISTI,
  KARTSIZ_DUGMESI,
  KAYIP_BILDIRILDI,
  OKUTMA_KUTUSU,
  SINIF_KITAPLIGINDA,
  TESLIM_GERI_ALMA_ONERISI,
  TESLIMDEN_GERI_AL,
} from "../dolasim/DolasimMasasi";
import { DOLASIM_MASASI_BASLIGI } from "../dolasim/DolasimMasasiPage";
import { ISTISNA_GEREKCELERI, KARTSIZ_GEREKCELER } from "../dolasim/api";
import {
  ISTISNA_BASLIGI,
  ISTISNA_YARDIMI,
  KART_KILIDI_BASLIGI,
  KARTSIZ_BASLIGI,
} from "../dolasim/MasaDiyaloglari";
import { DOSYA_KAYIP_BASLIGI } from "../guvenlik/metinler";
import { COZUM_TR, DOSYA_TURU_TR, SORUMLU_NOTU_YARDIMI, TUTANAK_ADI } from "../kayip/api";
import {
  HASAR_BASLIGI,
  HASAR_DUGMESI,
  KAYIP_BASLIGI,
  KAYIP_DUGMESI,
} from "../kayip/DosyaAcDiyalogu";
import { BEDEL_IADESI_NOTU, BEDEL_YOK_NOTU } from "../kayip/DosyaAyrintisi";
import {
  KAYIP_HASAR_ADRESI,
  KAYIP_HASAR_BASLIGI,
  OKULUN_ACIK_ISI_ETIKETI,
} from "../kayip/KayipHasarPage";
import { NUSHA_ISLEMLERI_BASLIGI } from "../kayip/NushaIslemleri";
import {
  GOREVLI_DOGRULAMA_BITIR,
  GOREVLI_DOGRULAMA_DUGMESI,
  GOREVLI_EKRANI_BASLIGI,
  GOREVLI_GERI_ALMA_BASLIGI,
  GOREVLI_GERI_ALMA_DUGMESI,
  GOREVLI_KATALOG_DUGMESI,
  GOREVLI_MASAYA_DON,
} from "../kip/GorevliEkrani";
import { GOREVLI_KISAYOLU } from "../kip/KipGostergesi";
import { BAGIS_BIRIM_FIYAT_YARDIMI } from "../kutuphane/BagisPaneli";
import { EDINIMLER_BASLIGI } from "../kutuphane/EdinimlerPage";
import { ESER_DETAY_BASLIGI } from "../kutuphane/EserDetayPage";
import { BASIM_SIRASI_TR, ETIKET_ICERIGI_TR, PARTI_DURUMU_TR } from "../kutuphane/etiketApi";
import {
  ETIKETLER_ADRESI,
  ETIKETLER_BASLIGI,
  ETIKETLER_SEKMELERI,
} from "../kutuphane/EtiketlerPage";
import { ETIKET_YOLLARI, HIZLI_KAYIT_BASLIGI } from "../kutuphane/HizliKayitPage";
import { ICE_AKTARMA_ADRESI, ICE_AKTARMA_BASLIGI } from "../kutuphane/IceAktarmaPage";
import { EDINIMLER_ADRESI } from "../kutuphane/KatalogPage";
import {
  ACQUISITION_METHOD_TR,
  AKTARIM_KOVASI_TR,
  CLASSIFICATION_SOURCE_TR,
  COMMISSION_DECISION_TYPE_TR,
  COPY_STATUS_TR,
  KATALOG_SABLONU_BELGE_ADI,
  KUNYE_LISTESI_BELGE_ADI,
  RESOURCE_TYPE_TR,
  WORK_ORDER_TR,
} from "../kutuphane/api";
import { HOLIDAY_KIND_TR, MEMBER_KIND_TR, SCHOOL_LEVEL_TR } from "../okul/api";
import { GERI_ALMA_BASLIGI, GERI_ALMA_KUTUSU } from "../teslim/GeriAlmaOkutmasi";
import { BEKLENEN_DONUS_GECTI } from "../teslim/TeslimKayitlari";
import { TESLIMLER_ADRESI, TESLIMLER_BASLIGI } from "../teslim/TeslimlerPage";
import {
  DIGER_PERSONEL_GEREKCESI,
  LISTEYE_GIRMEYENLER,
  TESLIM_ET_DUGMESI,
  TESLIM_KUTUSU,
  ZATEN_LISTEDE,
} from "../teslim/YeniTeslim";
import {
  GERI_ALMA_DOKUMU_ADI,
  TESLIM_ALAN_TURU_TR,
  TESLIM_DURUMU_TR,
  TESLIM_LISTESI_ADI,
} from "../teslim/api";
import { KAPANIS_KARTI_BASLIGI } from "../uyelik/DolasimKartlari";
import { GECIKMIS_ODUNCLER_BASLIGI } from "../uyelik/GecikmisOdunclerPage";
import { LISTE_DIPNOTU } from "../uyelik/api";
import {
  ILISIK_BELGESI_ADI,
  ILISIK_LISTESI_ADI,
  ILISIK_LISTESI_ADRESI,
  ILISIK_LISTESI_BASLIGI,
  KAPSAM_SECENEKLERI,
  LISTE_DIPNOTU as ILISIK_DIPNOTU,
  PUSULA_ADI,
  YIL_BASI_ADRESI,
  YIL_BASI_BASLIGI,
  YIL_SONU_ADRESI,
  YIL_SONU_BASLIGI,
} from "../yil/api";
import {
  AYIKLAMA_ADRESI,
  AYIKLAMA_BASLIGI,
  BAGIS_SONUCU_BELGESI,
  GEREKCE_TR,
  KALEM_DURUMU_TR,
  NADIR_ESERLER_ADRESI,
  NADIR_ESERLER_BASLIGI,
  TMY_YOLU_TR,
  YIL_SONU_RAPORU_ADRESI,
  YIL_SONU_RAPORU_BASLIGI,
} from "../ayiklama/api";
import { HASAR_ONERILERI_BASLIGI, KAYIP_ONERILERI_BASLIGI } from "../ayiklama/TeklifDiyaloglari";
import { TESPIT_YARDIMI, YAZ_DONEMI_UYARISI } from "../ayiklama/YilSonuRaporuPage";
import KilavuzPage, { KILAVUZ_BOLUMLERI } from "./KilavuzPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <KilavuzPage />
    </MemoryRouter>,
  );
}

/** Sayfanın düz metni (boşluklar tekleştirilir). */
function sayfaMetni(container: HTMLElement): string {
  return (container.textContent ?? "").replace(/\s+/g, " ");
}

/** Bir bölümün (section) düz metni. */
function bolumMetni(id: string): string {
  const bolum = document.getElementById(id);
  expect(bolum).not.toBeNull();
  return (bolum?.textContent ?? "").replace(/\s+/g, " ");
}

const BEKLENEN_BASLIKLAR = [
  "İlk Kurulum",
  "Başlangıç Yol Haritası",
  "Görevli Kipi ve Yönetici Kipi",
  "Kişiler ve e-Okul Listeleri",
  "Kapalı Günler",
  "Katalog",
  "Hızlı Kayıt",
  "Etiketler",
  "Üyelik, Kart ve Belgeler",
  "Dolaşım Masası",
  "Sınıf Kitaplığına ve Öğretmene Teslim",
  "Kayıp, Hasar ve Onarım",
  "İlişik Listesi",
  "Yıl Sonu ve Yıl Başı",
  "Ayıklama ve Nadir Eserler",
  "Yıl Sonu Raporu",
  "Katalog Excel Şablonu",
  "İçe Aktarma",
  "Yedek ve Güvenlik Dosyası",
  "Tepsi, Çıkış ve Gün Değişimi",
  "Ağ Kataloğu",
];

describe("KilavuzPage — kabuk ve bölümler", () => {
  it("kabuğu gösterir (üstbaşlık, h1, konum dili)", () => {
    const { container } = renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: "Kullanım Kılavuzu" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Kütüphane Defteri")).toBeInTheDocument();
    expect(sayfaMetni(container)).toContain("okulun kütüphane işlerini yürüttüğü yerel araçtır");
  });

  it("bölümler kullanıcının iş sırasıyla gelir", () => {
    renderPage();

    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(
      BEKLENEN_BASLIKLAR,
    );
    expect(KILAVUZ_BOLUMLERI.map((b) => b.baslik)).toEqual(BEKLENEN_BASLIKLAR);
  });

  it("'Bu kılavuzda' listesi her bölüme çapayla bağlanır", () => {
    renderPage();

    const liste = screen.getByRole("navigation", { name: "Kılavuz bölümleri" });
    const baglantilar = within(liste).getAllByRole("link");
    expect(baglantilar.map((a) => a.textContent)).toEqual(BEKLENEN_BASLIKLAR);
    baglantilar.forEach((a, i) => {
      const id = KILAVUZ_BOLUMLERI[i].id;
      expect(a).toHaveAttribute("href", `#${id}`);
      const bolum = document.getElementById(id);
      expect(bolum?.tagName).toBe("SECTION");
      // Bölüm kendi başlığıyla adlandırılır (ekran okuyucu bölge adı).
      expect(bolum).toHaveAccessibleName(BEKLENEN_BASLIKLAR[i]);
    });
  });

  // Yol haritasındaki BTR maddesi `/kilavuz#ag-katalogu` adresine gider;
  // tarayıcı SPA rota değişiminde çapayı kendisi uygulamaz (KilavuzPage uygular).
  it("çapalı adresle açılınca o bölüme kaydırır", () => {
    const kaydir = vi.fn();
    const onceki = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = kaydir;
    try {
      render(
        <MemoryRouter initialEntries={["/kilavuz#ag-katalogu"]}>
          <KilavuzPage />
        </MemoryRouter>,
      );
      expect(kaydir).toHaveBeenCalledTimes(1);
      expect(kaydir.mock.instances[0]).toBe(document.getElementById("ag-katalogu"));
    } finally {
      Element.prototype.scrollIntoView = onceki;
    }
  });

  it("çapasız açılışta kaydırma yapılmaz", () => {
    const kaydir = vi.fn();
    const onceki = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = kaydir;
    try {
      renderPage();
      expect(kaydir).not.toHaveBeenCalled();
    } finally {
      Element.prototype.scrollIntoView = onceki;
    }
  });

  it("ekran bağlantıları ilgili sayfaya ve sekmeye gider", () => {
    renderPage();

    const hedef = (ad: string) =>
      screen.getAllByRole("link", { name: ad }).map((a) => a.getAttribute("href"));

    expect(new Set(hedef("Ayarlar → Güvenlik"))).toEqual(new Set(["/ayarlar?tab=guvenlik"]));
    expect(hedef("Ayarlar → Kapalı Günler")).toEqual(["/ayarlar?tab=kapali-gunler"]);
    // Okul Bilgileri'ne iki bölümden bağlanılır (ilk kurulum + etiketlerin kısa okul adı).
    expect(new Set(hedef("Ayarlar → Okul Bilgileri"))).toEqual(new Set(["/ayarlar?tab=okul"]));
    expect(hedef("Ayarlar → Şubeler")).toEqual(["/ayarlar?tab=subeler"]);
    expect(hedef("Ayarlar → Bölümler")).toEqual(["/ayarlar?tab=bolumler"]);
    // F5: Ağ Kataloğu sekmesine birden çok yerden (katalog sayfaları, açma adımları,
    // uyku) bağlanılır; Ağ Doktoru ekranı.
    expect(new Set(hedef("Ayarlar → Ağ Kataloğu"))).toEqual(
      new Set([`/ayarlar?tab=${AG_KATALOGU_SEKMESI}`]),
    );
    expect(hedef(AG_DOKTORU_BASLIGI)).toEqual([AG_DOKTORU_ADRESI]);
    // Kütüphane Politikası'na iki bölümden bağlanılır (katalog + hızlı kayıt).
    expect(new Set(hedef("Ayarlar → Kütüphane Politikası"))).toEqual(
      new Set(["/ayarlar?tab=politika"]),
    );
    expect(hedef("Kişiler")).toEqual(["/kisiler"]);
    expect(new Set(hedef("Genel Bakış"))).toEqual(new Set(["/"]));
    // "Katalog" iki bağlantıdır: "Bu kılavuzda" çapası ve ekran bağlantısı.
    expect(new Set(hedef("Katalog"))).toEqual(new Set(["#katalog", "/katalog"]));
    // Edinimler ekranının adresi katalog sayfasının sabitinden doğrulanır; ona katalog
    // ve etiketler (önce etiket yolunda edinim partisi) bölümlerinden bağlanılır.
    expect(new Set(hedef(EDINIMLER_BASLIGI))).toEqual(new Set([EDINIMLER_ADRESI]));
    // F3 ekranlarına birden çok bölümden bağlanılır (katalog + hızlı kayıt +
    // içe aktarma); adresler sayfa sabitlerinden doğrulanır.
    expect(new Set(hedef(`Katalog → ${HIZLI_KAYIT_BASLIGI}`))).toEqual(
      new Set(["/katalog/hizli-kayit"]),
    );
    expect(new Set(hedef(`Katalog → ${ICE_AKTARMA_BASLIGI}`))).toEqual(
      new Set([ICE_AKTARMA_ADRESI]),
    );
    expect(new Set(hedef("Katalog → Nüshalar"))).toEqual(new Set(["/katalog?tab=nushalar"]));
    // Etiketler ekranına Hızlı Kayıt ve Etiketler bölümlerinden bağlanılır (F4).
    expect(new Set(hedef(`Katalog → ${ETIKETLER_BASLIGI}`))).toEqual(new Set([ETIKETLER_ADRESI]));
    // Etiketler sekmelerine doğrudan bağlanılır; `?tab=` değeri sekme tanımının
    // anahtarından doğrulanır (sekme adı ya da anahtarı değişirse test kırılır).
    const sekmeAnahtari = (ad: string) =>
      Object.entries(ETIKETLER_SEKMELERI).find(([, sekme]) => sekme === ad)?.[0];
    for (const sekme of [
      "Şablonlar ve Kalibrasyon",
      "Basım Geçmişi",
      "Doğrulama Okutması",
      "Boş Barkod Aralığı",
    ]) {
      const anahtar = sekmeAnahtari(sekme);
      expect(anahtar).toBeDefined();
      expect(hedef(`${ETIKETLER_BASLIGI} → ${sekme}`)).toEqual([
        `${ETIKETLER_ADRESI}?tab=${anahtar}`,
      ]);
    }
    // Çevrimdışı künye yoluna doğrudan sekmesiyle bağlanılır.
    expect(hedef(`Katalog → ${ICE_AKTARMA_BASLIGI} → Çevrimdışı Künye`)).toEqual([
      `${ICE_AKTARMA_ADRESI}?tab=cevrimdisi`,
    ]);
  });
});

describe("KilavuzPage — bölüm içerikleri", () => {
  it("ilk kurulum: parola zorunlu, kurtarma anahtarı saklanır ve doğrulanır, demirbaş onayı", () => {
    renderPage();
    const metin = bolumMetni("ilk-kurulum");

    // Sihirbazın gerçek düğme adları (KurulumPage, KurtarmaAnahtariPaneli).
    for (const dugme of [
      "“Yönetici parolasını kur”",
      "“Yazdır”",
      "“PDF olarak kaydet”",
      "“Sakladım, doğrula”",
      "“Anahtarı yeniden göster”",
      "“Devam”",
      "“Kaydet ve devam et”",
      "“Ders yılını kaydet ve aktifleştir”",
      "“Kurulumu tamamla”",
    ]) {
      expect(metin).toContain(dugme);
    }
    expect(metin).toContain("Yönetici parolası zorunludur ve bu adım atlanamaz");
    // F1 eki, karar 2: kurulum anahtar doğrulanmadan tamamlanmaz; iki çıkış yolu.
    expect(metin).toContain("kurulum bu doğrulama yapılmadan tamamlanmaz");
    // TB19: gözetimsiz ekranda kurtarma anahtarı gizlenir (kip askısı korunur).
    expect(metin).toContain("Beş dakika hiçbir işlem yapılmazsa anahtar ekranda gizlenir");
    expect(metin).toContain("Kurtarma Anahtarını Doğrula:");
    expect(metin).toContain("Kurtarma Anahtarını Yenile:");
    expect(metin).toContain("müdürlükte kilitli dolapta saklayın");
    expect(metin).toContain("en az iki görevlendirilmiş kişide bulunsun");
    expect(metin).toContain("0, 1, 8 ve 9 rakamları yoktur");
    expect(metin).toContain("“Bu bilgisayar okul demirbaşıdır.” onayı zorunludur");
    expect(metin).toContain("Bilgisayarın demirbaş no'su isteğe bağlıdır");
    for (const kademe of Object.values(SCHOOL_LEVEL_TR)) expect(metin).toContain(kademe);
    // Yönerge alıntıları docs/mevzuat/meb-bilgi-ve-sistem-guvenligi-yonergesi.md'den birebir.
    expect(metin).toContain(
      "“Kullanıcılar, kişisel bilişim kaynaklarını kurum ağında sistem yöneticisinden izin almadan kullanamaz.”",
    );
    expect(metin).toContain("Bilgi ve Sistem Güvenliği Yönergesi, md. 11/8");
    expect(metin).toContain(
      "“Bakanlığa ait gizli ya da açık her türlü veri Bakanlık sistemleri üzerinde barındırılır.",
    );
    expect(metin).toContain("Bilgi ve Sistem Güvenliği Yönergesi, md. 11/23");
  });

  it("yol haritası: yedi madde, kendiliğinden ve elle işaretlenenler", () => {
    renderPage();
    const metin = bolumMetni("yol-haritasi");

    const maddeler = document.querySelectorAll("#yol-haritasi ol > li");
    expect(maddeler).toHaveLength(7);
    expect(metin).toContain("“Yapıldı”");
    expect(metin).toContain("“Kartı gizle”");
    expect(metin).toContain("İşaretler programda saklanır");
  });

  it("kipler: kısayol, süreler, Kilitle ve parolayı unutunca kurtarma anahtarı", () => {
    renderPage();
    const metin = bolumMetni("kipler");

    // Kısayol ve kip ekranının başlığı ekran sabitlerinden (KipGostergesi, GorevliEkrani).
    expect(metin).toContain(GOREVLI_KISAYOLU);
    expect(metin).toContain(`“${GOREVLI_EKRANI_BASLIGI}” sayfası`);
    for (const dugme of [
      "“Görevli kipine geç”",
      "“Yönetici kipine geç”",
      "“Kilitle”",
      "“Parolamı unuttum”",
      "“Kurtar ve aç”",
      "“Parolayı değiştir”",
      "“Uygula”",
      "“Kayıtlar kilitli”",
    ]) {
      expect(metin).toContain(dugme);
    }
    expect(metin).toContain("3 dakika işlem yapılmazsa");
    expect(metin).toContain("en geç 30 dakika sonra");
    // F7: iki süre Kütüphane Politikası'ndan ayarlanır; alan adları ve sınırlar panelin
    // metniyle aynı (sınırlar backend `test_on_yuz_sabitleri.py` ile modele kilitli).
    expect(metin).toContain("“Yönetici Kipi Süreleri” bölümünden değiştirilir");
    expect(metin).toContain("“İşlem yapılmazsa kapanma süresi (dakika)” 1 ile 15");
    expect(metin).toContain("“En uzun açık kalma süresi (dakika)” 5 ile 120 dakika");
    expect(metin).toContain("ilki ikincisini aşamaz");
    expect(metin).toContain("Değişiklik bir sonraki işlemden itibaren geçerlidir");
    // Görevliye açık teslim işi yalnız geri almadır (§4.4).
    expect(metin).toContain(`“${GOREVLI_GERI_ALMA_DUGMESI}” düğmesiyle`);
    expect(metin).toContain("“Kilitle” her kipte parolasızdır");
    // Kurtarmayla parola yenileme anahtarı değiştirmez; anahtar yalnız istenirse yenilenir.
    expect(metin).toContain("kurtarma anahtarını DEĞİŞTİRMEZ");
    expect(metin).toContain("“Kurtarma Anahtarını Yenile”");
    expect(metin).toContain("Pencerenin çarpı düğmesi programı ne kapatır ne kilitler");
    // Görevliye açık tek etiket işi: doğrulama okutması (kullanıcı kararı 24.09.2026).
    expect(metin).toContain(`“${GOREVLI_DOGRULAMA_DUGMESI}” düğmesiyle`);
    expect(metin).toContain("“Doğrulanmamış Etiketler” listesi yönetici kipindedir");
  });

  it("kişiler: e-Okul raporları, şube kapsamı, tam liste onayı, ayrılış havuzu ve birleştirme", () => {
    renderPage();
    const metin = bolumMetni("kisiler");

    // Desteklenen e-Okul raporları (backend apps/okul/eokul.py).
    expect(metin).toContain("OOG01001R020 — Sınıf/Şube Öğrenci Listesi");
    expect(metin).toContain("OOK01001R1 — Personel Listesi");
    // Kişiler sayfasının ve aktarım panelinin gerçek adları.
    for (const ad of [
      "“Öğrenciler”",
      "“Öğretmenler ve Diğer Personel”",
      "“Şablon indir”",
      "“Ya da tabloyu yapıştırın”",
      "“Önizle”",
      "“Aktar”",
      "“Bu dosya okulun tam listesidir”",
      "“Ayrılış Havuzu”",
      "“Aktif kalsın”",
      "“Birleştir”",
      "“Öğrenci ekle”",
      "“Kişi ekle”",
      "“Ayrıldı olarak işaretle”",
      "“Ayrıldı · gg.aa.yyyy”",
    ]) {
      expect(metin).toContain(ad);
    }
    for (const tur of Object.values(MEMBER_KIND_TR)) expect(metin).toContain(tur);
    expect(metin).toContain("yalnız dosyada bulunan şubelerle");
    expect(metin).toContain("Tek bir şubenin listesini yüklemek diğer şubelere dokunmaz");
    expect(metin).toContain("Dosyada yeni şubesiyle görünen öğrenci ayrılmaz");
    // Aktarım kimseyi ayırmaz ve silmez (F1 eki 7): karar havuzda verilir.
    expect(metin).toContain("Aktarım kimseyi okuldan ayırmaz ve kimsenin kaydını silmez.");
    expect(metin).toContain("durumu aktif kalır");
    expect(metin).toContain("iade etmediği kitap varsa izlenebilir");
    expect(metin).toContain("Sınıf” süzgeci yıl sonunda mezun şubeleri bir kerede işaretlemeye");
    // Şube şube yüklemenin bilinen sınırı açıkça söylenir; yıl başında tam liste önerilir.
    expect(metin).toContain(
      "Başka bir şubeye geçtiği için bu dosyada bulunmayan öğrenci de havuza eklenir",
    );
    expect(metin).toContain("okulun bütün şubelerini içeren listeyi tek dosyada yükleyin");
    // Import silmez ilkesi ve okul no yeniden kullanımı.
    expect(metin).toContain("o satırdaki okul numarasına sahip öğrenci havuza eklenmez");
    expect(metin).toContain("aynı numara ve aynı adla");
    expect(metin).toContain("Olası aynı kişi");
    // TB18: aday satırı gerekçeyi yazar, birleştirme ikinci doğrulama ister.
    expect(metin).toContain("neden aday olduğunu");
    expect(metin).toContain("onay kutusunu işaretlemeden düğme açılmaz");
    expect(metin).toContain("görev sütunu yalnız üye türünü");
    // Kişisel veri notu (tasarım §4.5): liste dosyası aktarımdan sonra silinir.
    expect(metin).toContain("aktarım biter bitmez silin");
    // KVKK: program bu alanları tutmaz.
    expect(metin).toContain("T.C. kimlik numarası, veli bilgisi, cinsiyet, unvan ve branş tutmaz");
  });

  it("kapalı günler: türler, tahmini rozeti ve iade tarihindeki iki ayrı kural", () => {
    renderPage();
    const metin = bolumMetni("kapali-gunler");

    for (const tur of Object.values(HOLIDAY_KIND_TR)) expect(metin).toContain(tur);
    expect(metin).toContain("“tahmini” rozetli");
    expect(metin).toContain("“Resmî ve dini tatilleri ekle”");
    expect(metin).toContain("“Kapalı Gün Ekle”");
    // İki ayrı kural: tatil kaydırması TBK 93'e kıyasen, ara tatil/yarıyıl okulun tercihi.
    expect(metin).toContain("Türk Borçlar Kanunu'ndaki genel kuralı kıyasen uygular");
    expect(metin).toContain("bir mevzuat hükmü değil, okulun tercihidir");
    // İdari izin TBK 93 kıyası altında anılmaz: dayanaksız program kuralıdır.
    expect(metin).toContain("Bu bir mevzuat hükmü değil, programın kuralıdır");
    expect(metin).not.toContain("İdari izin günü de kütüphane kapalı olduğu için aynı biçimde");
    // Alıntılar docs/mevzuat'tan birebir.
    expect(metin).toContain("“Bir kitabı ödünç alma süresi on beş gündür.”");
    expect(metin).toContain(
      "“İfa zamanı veya sürenin son günü, kanunlarda tatil olarak kabul edilen bir güne rastlarsa, kendiliğinden bu günü izleyen ve tatil olmayan ilk güne geçer.”",
    );
  });

  it("katalog: eser ve nüsha ayrımı, sıralama eksenleri, bölümler ve yer numarası", () => {
    renderPage();
    const metin = bolumMetni("katalog");

    // Katalog sayfasının sekmeleri ve düğmeleri (KatalogPage, EserDetayPage).
    for (const ad of [
      "“Eserler”",
      "“Nüshalar”",
      "“Eser ekle”",
      "“Nüsha ekle”",
      "“Künyeyi düzenle”",
      "“Nüsha sayısı”",
      "“Yalnız ödünç verilebilenler”",
      "“Yalnız etiketlenmemişler”",
      "“Kayıttan düşülenleri gizle”",
      "“Bölüm ekle”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain(ESER_DETAY_BASLIGI);
    // TR arama kapıları kılavuzda da söylenir (kullanıcı "ŞİİR" yazıp bulamadı sanmasın).
    expect(metin).toContain("“şiir” ile “ŞİİR”");
    expect(metin).toContain("“ılık” ile “ILIK”");
    expect(metin).toContain("“İnce” ile “ince”");
    // 'ı' ile 'i' BİLİNÇLİ olarak ayrıdır; kılavuz "Türkçe harfler ayırt edilmez"
    // diye genelleme YAPMAMALI (kullanıcı "ilik" yazıp kaydı yok sanmasın).
    expect(metin).not.toContain("Türkçe harfler ayırt edilmez");
    expect(metin).toContain("“ı” ile “i” ayrı harflerdir");
    expect(metin).toContain("“rüzgar”");
    // Üç katalog ekseni + "en yeni": seçicinin gerçek etiketleri.
    for (const eksen of Object.values(WORK_ORDER_TR)) expect(metin).toContain(eksen);
    expect(metin).toContain(
      "“Kataloglar; yazar adı, kaynak adı ve konularına göre alfabetik olarak düzenlenir.”",
    );
    // Bölüm kontrollü listedir; DOS ilk geçişte açılır (docs/sozluk.md §1, §2).
    expect(metin).toContain("Dewey Onlu Sınıflama (DOS)");
    expect(metin).toContain("kontrollü bir listedir");
    expect(metin).toContain("Aralık yalnız bilgilendirmedir");
    // Yer numarası üretimi ve elle düzeltilebilirliği (soyad sezgisi yanılabilir).
    expect(metin).toContain("“813.54 STE”");
    expect(metin).toContain("elle değiştirilebilir");
    expect(metin).toContain("“Ad Soyad” sırasıyla");
    for (const kaynak of Object.values(CLASSIFICATION_SOURCE_TR)) expect(metin).toContain(kaynak);
  });

  it("katalog: ISBN uyarısı engellemez, barkod ve kayıt no yeniden kullanılmaz", () => {
    renderPage();
    const metin = bolumMetni("katalog");

    // ISBN: sağlama hatası kaydı ENGELLEMEZ (F2 sözleşmesi §3).
    expect(metin).toContain("kayıt engellenmez");
    expect(metin).toContain("“ISBN uyarısı”");
    expect(metin).toContain("978 ya da 979 ile başlar");
    // F6'dan beri ileti ŞİMDİKİ ZAMANDADIR: Dolaşım Masası ISBN barkodunda bu iletiyi
    // verir (barcode.ISBN_SCAN_MESSAGE); F2-F5'teki "diyecek" kalmaz.
    expect(metin).toContain(
      "Dolaşım Masası'nda ISBN barkodu okutulursa program “Bu ISBN barkodu. Kitabın kütüphane etiketini okutun.” der",
    );
    expect(metin).not.toContain("diyecek");
    expect(metin).toContain("yalnız kütüphane etiketini arar");
    // Barkod / kayıt no: on hane, yıl + sıra, basılı biçim, salt okunur.
    expect(metin).toContain("Barkod on hanedir");
    expect(metin).toContain("“2026-000123”");
    expect(metin).toContain("2026000123");
    expect(metin).toContain("Bir numara asla yeniden kullanılmaz.");
    expect(metin).toContain("yalnız bilgi satırıdır");
    expect(metin).toContain("“Eski kayıt no”");
    // TKYS ilk geçişte açılır (docs/sozluk.md §2).
    expect(metin).toContain("Taşınır Kayıt ve Yönetim Sistemi (TKYS)");
  });

  it("katalog: ödünç verilmeyen kaynaklar mevzuat metniyle anlatılır", () => {
    renderPage();
    const metin = bolumMetni("katalog");

    expect(metin).toContain("“Danışma kaynağı (ödünç verilmez)”");
    expect(metin).toContain("“Piyasada mevcudu yok (ödünç verilmez)”");
    expect(metin).toContain("“Ödünç verilmez — kütüphanede okunur.”");
    expect(metin).toContain("“Süreli yayın — ödünç verilmez.”");
    // Alıntılar docs/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md'den birebir.
    expect(metin).toContain(
      "“Ancak; a) Danışma kaynakları, b) Piyasada mevcudu bulunmayan kitaplar, c) Süreli yayınlar, ödünç verilmez.”",
    );
    expect(metin).toContain(
      "“Danışma dermesi oluşturulur. Burada ders kitapları, ansiklopediler, sözlükler, atlaslar,",
    );
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 16/1");
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 14/1-a");
    // Ders kitabı danışma dermesindedir; kutuyu kullanıcı işaretler.
    expect(metin).toContain("Ders kitapları da danışma dermesindedir");
    // Kaynak türleri ve dijital kaynakta nüsha açılmaması.
    for (const tur of Object.values(RESOURCE_TYPE_TR)) expect(metin).toContain(tur);
    expect(metin).toContain("E-kitap ve e-veri tabanında nüsha açılmaz.");
  });

  it("katalog: edinim yolları ve bağış ön kaydı akışı", () => {
    renderPage();
    const metin = bolumMetni("katalog");

    expect(metin).toContain(EDINIMLER_BASLIGI);
    for (const ad of [
      "“Edinim Partileri”",
      "“Bağış Ön Kayıtları”",
      "“Komisyon Kararları”",
      "“Edinim ekle”",
      "“Edinim yolu”",
      "“Bağış ön kaydı ekle”",
      "“Kalem ekle”",
      "“Çıkar”",
      "“Karar ekle”",
      "“Komisyon kararını uygula”",
      "“Kararı uygula”",
      "“Ret gerekçesi”",
      "“İptal et”",
      "“Kullanımda”",
    ]) {
      expect(metin).toContain(ad);
    }
    for (const yol of Object.values(ACQUISITION_METHOD_TR)) expect(metin).toContain(yol);
    for (const tur of Object.values(COMMISSION_DECISION_TYPE_TR)) expect(metin).toContain(tur);
    // Bağışta nüsha komisyon kararına kadar AÇILMAZ ve karar geri alınamaz.
    expect(metin).toContain("Bağış kataloğa doğrudan girmez.");
    expect(metin).toContain("Bu aşamada nüsha açılmaz, numara verilmez");
    expect(metin).toContain("geri alınamaz");
    expect(metin).toContain(
      "“Okul kütüphanesine bağışlanacak kitaplar, bu Yönetmelik çerçevesinde Seçim ve Ayıklama Komisyonu tarafından değerlendirilir.”",
    );
    expect(metin).toContain(
      "“Kütüphane kaynakları; Bakanlıktan gönderilen kaynaklar ile satın alma, bağış ve imkânlara göre değişim yoluyla sağlanır.”",
    );
    // Bağışçı ve komisyon adları kişi adıdır.
    expect(metin).toContain("şifreli saklanır");
  });

  it("katalog: ödünç süresi ayar değildir, politika alanları anlatılır", () => {
    renderPage();
    const metin = bolumMetni("katalog");

    expect(metin).toContain("Ödünç süresi burada bir ayar değildir ve değiştirilemez.");
    expect(metin).toContain("“Bir kitabı ödünç alma süresi on beş gündür.”");
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 18/1");
    expect(metin).toContain("en fazla üç, öğretmene en fazla beş kitap");
    for (const ad of [
      "“Ödünç Sınırları”",
      "“Diğer personele ödünç verilir”",
      "“Müdürlük kararı tarihi”",
      "“Müdürlük kararı sayısı”",
      "“Gecikmiş kitabı olana yeni ödünç verilmez”",
      "“İade tarihi öğrenciye kapalı günlerde kaydırılır”",
      "“Yıl sonu son ödünç tarihi”",
      "“Son sınıflar için son ödünç tarihi”",
      "“Çok okunanlar için en az üye sayısı”",
    ]) {
      expect(metin).toContain(ad);
    }
    // Ara tatil kaydırması okulun tercihi; resmî/dini tatil bu ayardan bağımsız.
    expect(metin).toContain("okulun tercihidir");
    expect(metin).toContain("bu ayardan bağımsızdır");
    // Profil yasağı (tasarım §3): ödünç sayısı dışarı verilmez, vitrinde sayı yok.
    expect(metin).toContain("öğrenci bazlı ödünç sayısı öğretmene");
    expect(metin).toContain("sayı hiçbir yerde gösterilmez");
  });

  it("katalog şablonu: nereden indirilir, üç sayfa, tek zorunlu sütun, kişisel veri yok", () => {
    renderPage();
    const metin = bolumMetni("katalog-sablonu");

    expect(metin).toContain(`“${KATALOG_SABLONU_BELGE_ADI}” kartında`);
    expect(metin).toContain("“Şablonu indir”");
    expect(metin).toContain("Tek zorunlu sütun Eser Adı");
    for (const sayfa of ["Katalog", "Sütunlar", "Örnek"]) expect(metin).toContain(sayfa);
    expect(metin).toContain("en çok 50");
    expect(metin).toContain("Listeye kişisel veri yazılmaz");
  });

  it("hızlı kayıt: iki geçiş yolu anlatılır ve asıl yol 'önce etiket'tir", () => {
    renderPage();
    const metin = bolumMetni("hizli-kayit");

    // §8.1'in geçiş tablosu kullanıcı diliyle: iki yol da adıyla anlatılır ve
    // hangisinin asıl yol olduğu (S8 cevabı) açıkça yazılır.
    expect(metin).toContain("Önce liste");
    expect(metin).toContain("Önce etiket");
    expect(metin).toContain("Okulun asıl yolu budur");
    expect(metin).toContain("hazır bir kitap listesi yoktur");
    // Etiket basımı artık vardır (F4): kılavuz ekranı gösterir, "sonraki sürüm" sözü kalmaz.
    expect(metin).toContain("Katalog → Etiketler");
    expect(sayfaMetni(document.body)).not.toContain("Etiket basımı sonraki sürümde");
    // Geçiş dönemi kuralı (§8.1): etiketsiz kitap masaya gelirse hemen kaydedilir.
    expect(metin).toContain("kâğıt defter");
  });

  it("hızlı kayıt: okutma, künye önerisi, ayarın varsayılanı ve ikinci nüsha", () => {
    renderPage();
    const metin = bolumMetni("hizli-kayit");

    // Ekran ve düğme adları ekrandaki metinle birebir (docs/sozluk.md §4).
    expect(metin).toContain("Katalog → Hızlı Kayıt");
    expect(metin).toContain("“ISBN barkodu”");
    expect(metin).toContain("“Künyeyi getir”");
    expect(metin).toContain("“Formu temizle”");
    expect(metin).toContain("“Seçilenleri forma yaz”");
    expect(metin).toContain("“ISBN ile künye getirme açık”");
    expect(metin).toContain("“Nüshayı aç”");
    expect(metin).toContain("“Bu esere nüsha ekle”");
    // Bağlı etiket: kitap büyük olasılıkla zaten kayıtlıdır (barcode_reservations._bound_message).
    expect(metin).toContain("kitabı yeniden kaydetmeyin");
    expect(metin).toContain("“Yalnız etiketlenmemişler”");
    // Yanlış kod okutulduğunda gösterilen ileti kılavuzda da yazılıdır (§7.1).
    expect(metin).toContain("Bu bir kütüphane etiketi.");
    // §8.5'in kullanıcıya görünen üç kuralı: varsayılan kapalı, yalnız numara
    // gider, çevirmen dışarıdan doldurulmaz; fail-open iletisi de yazılıdır.
    expect(metin).toContain("varsayılan olarak kapalıdır");
    expect(metin).toContain("dışarıya yalnız numaranın kendisi gider");
    expect(metin).toContain("Çevirmen alanı dışarıdan doldurulmaz");
    expect(metin).toContain("Dış kaynaktan alındı, doğrulayın");
    expect(metin).toContain("İnternetten getirilemedi, elle girebilirsiniz.");
    // Künye NEREDEN geliyor ve neden doğrulanmalı: iki kaynak da adıyla anılır,
    // konum dili korunur (okulun kaydı değil, başka kurumların kataloğu).
    expect(metin).toContain("Kültür ve Turizm Bakanlığı");
    expect(metin).toContain("Open Library");
    expect(metin).toContain("Gelen künyeyi kitabın künye sayfasından doğrulayın.");
    expect(metin).toContain("okulun kendi kaydı değildir");
    // İnternetsiz masanın yolu: dosyayla gidip gelen künye + Yönerge'nin kuralı.
    expect(metin).toContain("Çevrimdışı Künye");
    expect(metin).toContain("telefon ya da mobil modem bağlayarak internet alınmaz");
    // Barkod programın verdiği numaradır ve yeniden kullanılmaz.
    expect(metin).toContain("numara asla yeniden kullanılmaz");
    // Kitaptaki etiket (F4): iki yolun adı ekrandaki seçeneklerle birebir.
    expect(metin).toContain(`“${ETIKET_YOLLARI.etiket}”`);
    expect(metin).toContain(`“${ETIKET_YOLLARI.yeni}”`);
    expect(metin).toContain("“Kütüphane etiketi”");
    expect(metin).toContain("“Etiketini bas”");
    expect(metin).toContain("“Sırt etiketini bas”");
    expect(metin).toContain("eser açılmaz");
    // Etiket yolunda her etiket tek nüshadır ve etiketi okutmak kaydı bitirir
    // (HizliKayitPage: "Nüsha sayısı" yalnız yeni numara yolunda; Enter → kaydet).
    expect(metin).toContain("“Nüsha sayısı” sorulmaz");
    expect(metin).toContain("okuyucunun gönderdiği Enter kaydı bitirir");
    // Etiket yolunda ISBN kutusuna etiket okutulursa ileti etiket kutusunu gösterir
    // (HizliKayitPage ETIKET_ISBN_KUTUSUNDA).
    expect(metin).toContain("etiketi de “Kütüphane etiketi” kutusuna okutmanızı söyler");
  });

  it("etiketler: sekmeler, etiket türleri ve nereye yapıştırılacağı", () => {
    renderPage();
    const metin = bolumMetni("etiketler");

    expect(metin).toContain(`Katalog → ${ETIKETLER_BASLIGI}`);
    for (const sekme of Object.values(ETIKETLER_SEKMELERI)) expect(metin).toContain(sekme);
    // Sayfanın sayaç şeridi (EtiketlerPage OzetSeridi) ekrandaki adlarıyla.
    for (const sayac of [
      "“Sırt etiketi bekleyen”",
      "“Barkod etiketi bekleyen”",
      "“Doğrulanmamış etiket”",
      "“Bağlanmamış boş etiket”",
    ]) {
      expect(metin).toContain(sayac);
    }
    // Sırt etiketi yer numarasını boşluktan bölerek alt alta basar (labels/content.py).
    expect(metin).toContain("boşlukla ayrılmış parçaları alt alta basılır");
    expect(metin).toContain("“894.3533 ALİ 2. cilt”");
    // Üç etiket türü; boş barkod etiketinde künye yoktur.
    expect(metin).toContain("Boş barkod etiketi önce etiket yolunda");
    expect(metin).toContain("kitaba ait bilgi yoktur");
    // Sırtı dar kitapta ön kapak (§7.2); köşe dayatılmaz, AYNI köşe önerilir.
    expect(metin).toContain("Sırtı dar kitaplarda");
    expect(metin).toContain("ön kapağa, sırta yakın köşeye");
    expect(metin).toContain("Bütün ince kitaplarda aynı köşeyi kullanın");
    expect(metin).not.toContain("sol üst");
    // Önce etiket yolunda ISBN de okutulur: etiket ISBN barkodunu örtmez.
    expect(metin).toContain("ISBN barkodunun ve kapak yazısının üstüne gelmesin");
    expect(metin).toContain("şeffaf koruyucu bant");
  });

  it("etiketler: tabaka seçimi ve satın alma notu — QR kararı tabakayı belirler", () => {
    renderPage();
    const metin = bolumMetni("etiketler");

    // Hazır şablonlar (labels/seed.py) milimetreyle; kâğıt boyunun kısa adı yazılmaz.
    expect(metin).toContain("38,1 × 21,2 mm");
    expect(metin).toContain("48,5 × 25,4 mm");
    expect(metin).toContain("52,5 × 29,7 mm");
    // Satın alma QR kararından SONRA yapılır (tasarım §7.2, S4).
    expect(metin).toContain("Tabaka almadan önce QR kararını verin.");
    expect(metin).toContain("varsayılan olarak kapalıdır");
    expect(metin).toContain("QR 65'li tabakanın etiketine sığmaz");
    expect(metin).toContain("QR yalnız barkod numarasını taşır, adres taşımaz");
    expect(metin).toContain("iki boyutlu (2D) okuyucu");
    expect(metin).toContain("1.000 kitap için 16 barkod ve 16 sırt tabakası");
    // Ayrı sırt tabakası aynı satır × sütun düzeninde olmalıdır (etiketOrtak BasimAyarlari).
    expect(metin).toContain("“Sırt etiketi tabakası”");
    expect(metin).toContain("satır ve sütun sayısı barkod tabakasınınkiyle aynı olmalıdır");
    for (const ad of ["“Yeni şablon”", "“QR'a uygun”", "“Barkod bu etikete sığmaz”"]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("“yaklaşık ölçü”");
    expect(metin).toContain("40'lı tabaka kâğıdın kenarına kadar uzanır");
    // Güvenli basım payı (labels/geometry.py PRINT_SAFE_MARGIN_MM = 5 mm).
    expect(metin).toContain("sayfa kenarından en az 5 mm içeride");
    // Program yalnız 210 × 297 mm sayfaya dizer (labels/geometry.py); kısa adı yazılmaz.
    expect(metin).toContain("210 × 297 mm'lik sayfaya dizer");
    // Düzeni tutmayan sırt tabakasında iki etiket ayrı basılır (validate_print_setup).
    expect(metin).toContain("iki etiketi ayrı basın");
    // Kısa okul adı Okul Bilgileri'nden gelir (SchoolConfig.kisa_ad, en çok 24).
    expect(metin).toContain("Ayarlar → Okul Bilgileri");
    expect(metin).toContain("en çok 24 karakterdir");
  });

  it("etiketler: kalibrasyon adım adım, kalibrasyon sayfasının diliyle", () => {
    renderPage();
    const metin = bolumMetni("etiketler");

    // Şablonlar ve Kalibrasyon sekmesinin gerçek adları (SablonlarPaneli).
    for (const ad of [
      "“Kalibrasyon”",
      "“Sayfaya uygulanacak kayma”",
      "“— yok —”",
      "“PDF'i indir”",
      "“Yeni yazıcı kalibrasyonu”",
      "“Yazıcı adı”",
      "“Okunan yatay değer”",
      "“Okunan dikey değer”",
      "“Kaymaya ekle”",
      "“Yatay kayma (mm)”",
      "“Dikey kayma (mm)”",
      "“Kaydet”",
      "“Kayıtlı yazıcılar”",
      "“Düzenle”",
      "“Yazıcı (kalibrasyon)”",
    ]) {
      expect(metin).toContain(ad);
    }
    // Kalibrasyon sayfasının kendi talimatıyla aynı dil (etiket_kalibrasyon.html).
    expect(metin).toContain("gerçek boyutta (%100)");
    expect(metin).toContain("100 mm olmalıdır");
    expect(metin).toContain("cetvelin sağ ve alt tarafı artı");
    // Kâğıt kenarına yakın cetvel iç kenara konur (labels/calibration.py measured_edges).
    expect(metin).toContain("yan etiketle arasındaki kesime");
    expect(metin).toContain("cetvelin 0 çizgisindeki çerçeveye ait kesimi okuyun");
    expect(metin).toContain("Artı değer sağa ve aşağı");
    expect(metin).toContain("sorun kayma değil ölçektir");
    // Kayma şablon + yazıcı çiftine yazılır; başka yazıcı ayrıca kalibre edilir.
    expect(metin).toContain("her şablon ve yazıcı çifti için bir kez");
    expect(metin).toContain("bir yazıcının kayması başka yazıcıya uymaz");
    expect(metin).toContain("Kayma en çok 10 mm olabilir");
    // Adımlar sırasıyla: sayfa bas → oku → kaymaya ekle → doğrula.
    const adimlar = [
      "“Sayfaya uygulanacak kayma” seçicisi “— yok —” kalsın",
      "Çıktıyı etiket tabakasının üstüne koyup ışığa tutun",
      "“Yeni yazıcı kalibrasyonu” deyin",
      "Kayıttan sonra “Sayfaya uygulanacak kayma” seçicisinde bu yazıcı seçili gelir",
    ];
    const konumlar = adimlar.map((adim) => metin.indexOf(adim));
    for (const konum of konumlar) expect(konum).toBeGreaterThan(-1);
    expect(konumlar).toEqual([...konumlar].sort((a, b) => a - b));
  });

  it("etiketler: basım sırası, PDF almak basıldı saymaz, geri alma ve doğrulama", () => {
    renderPage();
    const metin = bolumMetni("etiketler");

    for (const ad of Object.values(ETIKET_ICERIGI_TR)) expect(metin).toContain(`“${ad}”`);
    for (const sira of Object.values(BASIM_SIRASI_TR)) expect(metin).toContain(sira);
    // Kuyruk süzgeçleri ve basım ayarları (EtiketKuyrugu, etiketOrtak).
    for (const ad of [
      "“Bölüm”",
      "“Edinim partisi”",
      "“Boş barkod aralığı”",
      "“Basım Ayarları”",
      "“Etiket şablonu”",
      "“Başlangıç hücresi”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("hücreler satır satır, soldan sağa sayılır");
    expect(metin).toContain("aynı sıra ve hücre düzeninde");
    expect(metin).toContain("önce sırt tabakaları, sonra barkod tabakaları");
    expect(metin).toContain("Yer numarası olmayan nüshalar sona düşer");
    expect(metin).toContain("kitapların masadan geçtiği sıradır");
    expect(metin).toContain("1.300");
    // D10: işaret onaylıdır ve geri alınabilir; PDF hiçbir işarete dokunmaz.
    expect(metin).toContain("PDF'i almak “basıldı” saymaz.");
    expect(metin).toContain("hiçbir işarete dokunmaz");
    expect(metin).toContain(`“${PARTI_DURUMU_TR.PENDING}”`);
    expect(metin).toContain("“Onay bekleyen partide”");
    for (const dugme of [
      "“Basım partisini hazırla”",
      "“Önizle”",
      "“PDF'i indir”",
      "“Basıldı olarak işaretle”",
      "“Partiden vazgeç”",
      "“Basım işaretini geri al”",
      "“Yeniden bas”",
      "“Nüshaları göster”",
      "“Kutuya dön”",
    ]) {
      expect(metin).toContain(dugme);
    }
    // Geri alma işareti SİLMEZ, bu basımdan önceki hâline döndürür; doğrulanmış etiket
    // korunur; sonradan yeniden basılmış nüshası olan parti önce o parti geri alınmadan
    // geri alınamaz (services/label_queue.py::revert_batch).
    expect(metin).toContain("bu basımdan önceki hâline döner");
    expect(metin).toContain("Okutularak doğrulanmış etiketlerin işareti korunur");
    // Kullanıcı kararı (24.09.2026): sırt ve barkod partisinde doğrulanmış nüshanın sırt
    // işareti de korunur.
    expect(metin).toContain("sırt işareti de korunur ve nüsha hiçbir kuyruğa dönmez");
    expect(metin).toContain("önce o partinin işaretini geri almanızı ister");
    // Barkod etiketi içeren partinin onayı doğrulamayı sıfırlar (confirm_batch); numara
    // değişmediği için eski etiketi okutmak yeniden doğrular.
    expect(metin).toContain("o nüshaların doğrulaması sıfırlanır");
    expect(metin).toContain("kitaplardaki eski etiketleri okutmak onları yeniden doğrular");
    // Doğrulama okutması: yalnız barkod etiketi; ret türleri ayrı iletilerle.
    expect(metin).toContain("Doğrulama barkod etiketi içindir");
    expect(metin).toContain("numarası iptal edilmiş boş etiket");
    expect(metin).toContain("“Doğrulanmamış Etiketler”");
    expect(metin).toContain("Basım Geçmişi'nden yeniden basın");
    // Görevli kipinde okutma görevli ekranından açılır ve kapanır (GorevliEkrani sabitleri).
    expect(metin).toContain("Okutmayı masadaki görevli de yapabilir");
    expect(metin).toContain(`“${GOREVLI_DOGRULAMA_DUGMESI}” düğmesiyle açılır`);
    expect(metin).toContain(`“${GOREVLI_DOGRULAMA_BITIR}” ile kapanır`);
  });

  it("etiketler: önce etiket yolu adım adım; numara yeniden verilmez", () => {
    renderPage();
    const metin = bolumMetni("etiketler");

    expect(metin).toContain("Önce etiket yolu adım adım");
    expect(metin).toContain("Okulun asıl yolu budur");
    // Sıra: ayır → bas → yapıştır → Hızlı Kayıt'ta künye + etiket → sırt → iptal.
    const adimlar = [
      "Numara ayırın.",
      "Basın.",
      "Yapıştırın.",
      "Kaydedin.",
      "Sırt etiketlerini basın.",
      "Kullanılmayanları iptal edin.",
    ];
    const konumlar = adimlar.map((adim) => metin.indexOf(adim));
    for (const konum of konumlar) expect(konum).toBeGreaterThan(-1);
    expect(konumlar).toEqual([...konumlar].sort((a, b) => a - b));
    // Boş Barkod Aralığı sekmesinin gerçek adları (BosBarkodPaneli).
    for (const ad of [
      "“Numara Ayır”",
      "“Adet”",
      "“Açıklama”",
      "“Numara ayır”",
      "“Seçilen Aralık”",
      "“Numaralar”",
      "“Seçilenleri iptal et”",
      "“Bağlanmamış bütün numaraları iptal et”",
      "“Sırt etiketlerini bas”",
      "“Bu numaraların etiketlerinin kitaplara yapıştırılmadığını denetledim.”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain(`“${ETIKET_YOLLARI.etiket}”`);
    expect(metin).toContain(`“${ETIKET_YOLLARI.yeni}”`);
    expect(metin).toContain("“Kütüphane etiketi”");
    expect(metin).toContain("ayrılan numara başka hiçbir kitaba verilmez");
    // Hızlı Kayıt edinimsiz nüsha açmaz: eski koleksiyonun edinim yolu önceden açılır.
    expect(metin).toContain("“Mevcut koleksiyon (programa aktarım)”");
    expect(metin).toContain("İptal geri alınmaz ve numara sayaca dönmez");
    // Bozulan etiket eldeyse aynı numara yeniden basılır; kaybolan etiketin
    // numarası iptal edilir; toplu iptal ancak bütün kitaplar kaydedilince.
    expect(metin).toContain("Bozulan etiket elinizdeyse");
    expect(metin).toContain("Kaybolan ya da artan etiketlerin numaralarını");
    expect(metin).toContain("Toplu iptali yalnız o aralığın bütün kitapları");
    // Etiketsiz kitabın tek etiket kısayolu (TekEtiketBasimi) kartın adıyla.
    expect(metin).toContain("“Etiket Basımı”");
  });

  it("içe aktarma: önizleme yazmaz, kararlar sorulur, aynı dosya ikinci kez uygulanmaz", () => {
    renderPage();
    const metin = bolumMetni("ice-aktarma");

    expect(metin).toContain("Katalog → İçe Aktarma");
    for (const sekme of [
      "Excel Aktarımı",
      "Yapay Zekâ Köprüsü",
      "Çevrimdışı Künye",
      "Aktarım Geçmişi",
    ]) {
      expect(metin).toContain(sekme);
    }
    // Önizleme = uygulama; fikirdeşlik ENGELDİR (uyarı değil).
    expect(metin).toContain("hiçbir kayıt yazmaz");
    expect(metin).toContain("uygulamanın gerçekten yazacağı sayılardır");
    expect(metin).toContain("Aynı dosya ikinci kez uygulanamaz.");
    // Eşleşme kovaları EKRANDAKİ rozet adlarıyla anlatılır (kilit: api.ts sabiti).
    for (const kova of Object.values(AKTARIM_KOVASI_TR)) {
      expect(metin).toContain(kova);
    }
    // Şüpheli satır tek tek karar ister; karar verilmeden "Uygula" açılmaz.
    expect(metin).toContain("“Karar bekleyen satırlar”");
    expect(metin).toContain("“Yeni eser aç”");
    expect(metin).toContain("“Yeniden önizle”");
    expect(metin).toContain("“Uygula” düğmesi açılmaz");
    // D5: bölüm değeri kaybolmaz; ders kitabı → danışma varsayılanı.
    expect(metin).toContain("“Bölüm listesinde bulunmayan değerler”");
    expect(metin).toContain("“Yeni bölüm aç”");
    expect(metin).toContain("danışma kaynağı sayılan");
    // Toplu aktarımda dış istek YOKTUR (§8.5-2) ve kılavuz bunu söyler.
    expect(metin).toContain("internetten künye getirmez");
    // Uygulamadan sonraki etiket kısayolu (§8.1; AktarimPaneli) kuyruğu partiye süzer.
    expect(metin).toContain("“Bu partinin etiketlerini bas”");
    expect(metin).toContain("bu edinim partisine süzülmüş açar");
    // Çevrimdışı yol AYRI CİHAZ demektir (Yönerge 11/18, birebir alıntı).
    expect(metin).toContain("başka bir cihazda");
    expect(metin).toContain(
      "“Bakanlık merkez ve taşra teşkilatında tanımı Başkanlık tarafından yapılan MEBNET ağı " +
        "dışında bir ağ kullanılamaz. Kullanıcı Bakanlık merkez ve taşra teşkilatında bulunan " +
        "bilgisayarlardan MEBNET ağı dışında cep telefonu, ADSL, VDSL, fiber, mobil modem, " +
        "kişisel erişim noktası, kablosuz bağlantı alanı cihazı vb. cihazlarını kullanamaz.”",
    );
    // Çevrimdışı künye dosyasının adı ve onay adımı (dolu alan sessizce yazılmaz).
    expect(metin).toContain(KUNYE_LISTESI_BELGE_ADI);
    expect(metin).toContain("“ISBN listesini indir”");
    expect(metin).toContain("“Seçilenleri kaydet”");
    expect(metin).toContain("dolu alanlar işaretsiz gelir");
    // Köprü: isteğe bağlı, program bağlanmaz, listeye kişisel veri yazılmaz,
    // asıl yol Excel, ISBN yolu daha güvenli (§8.2 U13 eki).
    expect(metin).toContain("isteğe bağlıdır");
    expect(metin).toContain("“Komutu kopyala”");
    expect(metin).toContain("Program hiçbir yapay zekâ servisine bağlanmaz");
    expect(metin).toContain("Listeye kişisel veri yazılmaz");
    expect(metin).toContain("Asıl yol Excel ile içe aktarmadır");
  });

  it("yedek ve güvenlik dosyası: şifreli yedek, geri yükleme ve üç çıkış yolu", () => {
    renderPage();
    const metin = bolumMetni("yedek");

    expect(metin).toContain(`“${DOSYA_KAYIP_BASLIGI}” ekranını`);
    // F5: gün değişimi kapısı (desktop/gunluk.py) tepside açık kalan programda da
    // her gün yedek alır; "yedek açılışa bağlıdır" uyarısı kalktı.
    expect(metin).toContain(
      "Program tepside günlerce açık kalsa da gün değişince o günün yedeğini",
    );
    expect(metin).not.toContain("açılışa bağlıdır");
    expect(metin).toContain("“Programdan çık” düğmesiyle");
    expect(metin).toContain("Ağ Kataloğu açıksa geri yükleme sırasında kapanır");
    for (const ad of [
      "“Şifreli Veritabanı Yedeği”",
      "“Şifreli yedeği indir”",
      "“Yedekten Geri Yükleme”",
      "“Geri yükle”",
      "“Yeniden denetle”",
      "“Güvenlik dosyasını sıfırla ve kuruluma dön”",
      "“Kütüphane Defteri — Yedekten Geri Yükle”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("kutuphane-defteri --geri-yukle");
    expect(metin).toContain("son 14 günün yedeklerini saklar");
    expect(metin).toContain("Mevcut veritabanı silinmez");
    expect(metin).toContain("Yedeği bulut depolama hizmetine yüklemeyin");
    expect(metin).toContain("tam disk şifrelemesi değildir");
    // Anahtar yenileme ve eski yedekler (F1 eki, karar 2-3; backend testiyle kanıtlı).
    expect(metin).toContain("“Kurtarma Anahtarını Yenile” kartından");
    expect(metin).toContain("Eski kâğıdı hemen atmayın.");
    expect(metin).toContain("güvenlik dosyası da yedeğin dönemine döner");
    expect(metin).toContain("eline geçmiş bir anahtara karşı koruma değildir");
  });

  it("Ağ Kataloğu: ne olduğu, salt okur, varsayılan kapalı, BTR'nin bilgisi alınır", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain("tahtaya ya da öğretmen bilgisayarına bir şey kurulmaz");
    expect(metin).toContain("Katalog yalnız okunur: oradan ödünç alınamaz");
    expect(metin).toContain("Varsayılan olarak kapalıdır ve yalnız yönetici kipinde açılır");
    // "İzin" değil "bilgi" (sözlük: BTR notu bir bilgi notudur).
    expect(metin).toContain("bilgisi alınır");
    expect(metin).not.toMatch(/izni(ni)? alınır/);
    expect(metin).toContain("Bu bir izin belgesi değil, bilgi notudur.");
  });

  // Tasarım §5.1 "Görünür / Asla görünmez" tablosu; nüsha durumları katalog
  // ekranının sabitinden (sözlük §1 "Nüsha durumları" satırıyla birebir).
  it("Ağ Kataloğu: neyi gösterir, neyi asla göstermez — kişisel veri yok", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(
      screen.getByRole("heading", { level: 3, name: "Neyi gösterir, neyi asla göstermez" }),
    ).toBeInTheDocument();
    for (const durum of ["AVAILABLE", "ON_LOAN", "DELIVERED", "IN_REPAIR"] as const) {
      expect(metin).toContain(`“${COPY_STATUS_TR[durum]}”`);
    }
    expect(metin).toContain("“Ödünç verilmez — kütüphanede okunur”");
    expect(metin).toContain("Kişisel veri göstermez.");
    expect(metin).toContain("hiçbir kişinin adı, sınıfı, okul numarası ya da kart no'su");
    expect(metin).toContain(
      "bir nüshanın “Ödünçte” olduğu görünür, kimde olduğu ve ne zaman döneceği görünmez",
    );
    expect(metin).toContain("bağışçı, fiyat, TKYS kodu, eski kayıt no");
    expect(metin).toContain("Aramalar ve bağlanan bilgisayarların adresleri kaydedilmez");
    expect(metin).toContain("kayıtlar kilitliyken de çalışır; internete hiç bağlanmaz");
    // Çok okunanlar: sayı yok; bu sürümde liste boştur (ödünç verisi yok) ve kılavuz bunu söyler.
    expect(metin).toContain("Çok okunanlarda yalnız sıra görünür, sayı gösterilmez");
    expect(metin).toContain("sonraki sürümlerde dolmaya başlar");
    // Kataloğun kendi üst menüsü (backend/katalog/sablonlar/taban.html).
    expect(metin).toContain("“Ara”, “Kaynak Adları”, “Yazarlar”, “Konular” ve “Hakkında”");
    expect(metin).toContain("“Katalog Sayfaları”");
  });

  it("Ağ Kataloğu: BTR'yle yapılacaklar — ağ keşfi, sabit adres, PYS talebi, not, erişim sınaması", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    for (const baslik of [
      "Ağ keşfi.",
      "Sabit adres.",
      "Tahta ağından erişim kapalıysa PYS talebi.",
      `${BILGI_NOTU_BELGE_ADI}.`,
      "Okul ağından erişim sınaması.",
    ]) {
      expect(metin).toContain(baslik);
    }
    expect(metin).toContain("tahta tarayıcısının vekil sunucu ayarı");
    expect(metin).toContain("“yerel ağ VLAN düzenlemesi — tek yön”");
    expect(metin).toContain("FATİH PYS");
    expect(metin).toContain("“internet ya da site açma” diye yazmayın");
    expect(metin).toContain("tahtanın tarayıcısında kataloğun adresini açın");
    expect(metin).toContain("erişim talebi Yardım Masası'ndan açılır");
  });

  it("Ağ Kataloğu: Yönerge alıntıları depodaki metinle birebir", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    // docs/mevzuat/meb-bilgi-ve-sistem-guvenligi-yonergesi.md, md. 11/6, 11/12, 11/22 (ilk cümle).
    expect(metin).toContain(
      "“Bilgisayarlara tahsis edilen IP numarası ve ortam erişim kontrolü adresi (MAC adresi) ile BIOS ayarları Bakanlık tarafından yetkilendirilmiş kişiler dışında değiştirilemez.”",
    );
    expect(metin).toContain("Bilgi ve Sistem Güvenliği Yönergesi, md. 11/6");
    expect(metin).toContain(
      "“Başkanlık MEBNET ağında erişime açılacak ve kapanacak portları belirleme ve düzenleme yetkisine sahiptir.”",
    );
    expect(metin).toContain("Bilgi ve Sistem Güvenliği Yönergesi, md. 11/22");
    expect(metin).toContain(
      "“MEBNET ağında kategorisi olmayan ip adresi, içerik veya sitelere erişim izni verilmez. Erişim talepleri Yardım Masası Modülü (yardimmasasi.meb.gov.tr) üzerinden yapılır.”",
    );
    expect(metin).toContain("Bilgi ve Sistem Güvenliği Yönergesi, md. 11/12");
  });

  it("Ağ Kataloğu: açma adımları ekrandaki kartın adlarıyla, beş madde ve dinleme seçenekleri", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    // modules/agkatalogu/AgKataloguPaneli.tsx: kart ve adım başlıkları (sabitleri yok,
    // kaynaktan birebir).
    expect(metin).toContain("“Ağ Kataloğunu Açmadan Önce” kartı");
    for (const adim of [
      "BTR'yle görüşün:",
      "Güvenlik duvarını hazırlayın:",
      "Adresi seçin:",
      "Ağ Kataloğunu açın:",
      "Afişi basın, yer imlerini dağıtın:",
    ]) {
      expect(metin).toContain(adim);
    }
    // Kurucu görevinin adı packaging/windows/kutuphane-defteri.iss [Tasks] ile birebir.
    expect(metin).toContain("“Yerel ağdan katalog taramasına izin ver (güvenlik duvarı kuralı)”");
    expect(metin).toContain("“Ağ Doktoru'nu aç”");
    expect(metin).toContain("“Kuralı ekle/güncelle”");
    expect(metin).toContain("“Katalog hangi ağ bağlantısında açılsın?”");
    expect(metin).toContain(`“${DINLEME_KIPI_TR.ALL}”`);
    expect(metin).toContain(`“${DINLEME_KIPI_TR.SELECTED}”`);
    expect(metin).toContain("“Ağ Kataloğunu aç”");
    expect(metin).toContain("beş maddesinden biri tutmazsa katalog okul ağına hiç açılmaz");
    expect(metin).toContain(`“${KATALOG_DURUMU_TR.engellendi}”`);
  });

  it("Ağ Kataloğu: Ağ Doktoru'nun kartları, durum rozeti, dinleyici sınamasının sınırı", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain(`${AG_DOKTORU_BASLIGI} menüde yoktur`);
    expect(metin).toContain(`${AG_DOKTORU_BASLIGI} yalnız yönetici kipinde açılır`);
    // modules/agkatalogu/AgDoktoruPage.tsx kart başlıkları, düğmeler ve seçici.
    for (const kart of [
      "Katalog Durumu:",
      "Güvenlik Duvarı:",
      "Ağ Bağlantıları:",
      "Dinleyici Sınaması:",
      "Belgeler:",
    ]) {
      expect(metin).toContain(kart);
    }
    for (const dugme of [
      "“Yeniden başlat”",
      "“Yenile”",
      "“Yeniden denetle”",
      "“Dinleyiciyi sına”",
      "“Afişi bas”",
      "“Yer imi dosyalarını üret”",
      "“PYS talep metnini kopyala”",
      "“Ağ Hizmeti Bilgi Notu'nu bas”",
      "“Belgelerde kullanılacak adres”",
    ]) {
      expect(metin).toContain(dugme);
    }
    // Rozet ve madde adları ekran sabitlerinden.
    for (const durum of Object.values(KATALOG_DURUMU_TR)) {
      expect(metin).toContain(`${durum}:`);
    }
    for (const madde of Object.values(MADDE_DURUMU_TR)) {
      expect(metin).toContain(`“${madde}”`);
    }
    for (const profil of ["Genel", "Özel", "Etki alanı"]) {
      expect(Object.values(AG_PROFILI_TR)).toContain(profil);
      expect(metin).toContain(`“${profil}”`);
    }
    expect(metin).toContain("güvenlik duvarını ya da ağ bölümlerini kanıtlamaz");
    expect(metin).toContain("Test-NetConnection");
    expect(metin).toContain("TcpTestSucceeded : True");
    expect(metin).toContain("Kimin neyi aradığı tutulmaz");
  });

  it("Ağ Kataloğu: afiş ve yer imleri — ETAP her öğretmene ayrı hesap açar, politika dosyası", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain("QR kodu küçük ve ikincildir");
    expect(metin).toContain("Afiş basılınca program o adresi hatırlar");
    expect(metin).toContain("ETAP her öğretmene tahtada ayrı bir hesap açar");
    expect(metin).toContain("kullanıcı başına yer imi yetmez");
    expect(metin).toContain("tahtanın bütün hesaplarında görünen bir yer imi politika dosyası");
    expect(metin).toContain("/etc/chromium/policies/managed/");
    expect(metin).toContain("BENIOKU.txt");
    expect(metin).toContain("Dosyaları tahtalara ve bilgisayarlara BTR dağıtır");
  });

  it("Ağ Kataloğu: tahta kipi klavyesiz gezinme, adres değişirse, port ve Pardus", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain("kataloğu tahta kipinde açar");
    expect(metin).toContain("Ekran klavyesine gerek kalmadan");
    expect(metin).toContain("?tahta=1");
    // Adres uyarısı desktop/katalog_kontrol.py::ip_denetle metniyle birebir (adresler yerine …).
    expect(screen.getByRole("heading", { level: 3, name: "Adres değişirse" })).toBeInTheDocument();
    expect(metin).toContain(
      "“Bu bilgisayarın IP adresi değişti (… → …). Afişi yeniden basın, yer imlerini güncelleyin.”",
    );
    expect(metin).toContain("uyarı yeni afişle kalkar");
    expect(metin).toContain("birden çok adresi varsa katalog açılmaz");
    expect(metin).toContain("“Portu değiştir”");
    expect(metin).toContain("onay verilmezse port değişmez");
    expect(metin).toContain("Pardus'ta program güvenlik duvarı kuralı açmaz");
  });

  it("tepsi ve çıkış: çarpı gizler, görevli kipinde Çık parola ister, kaza önleyicidir", () => {
    renderPage();
    const metin = bolumMetni("tepsi-ve-cikis");

    expect(metin).toContain("Pencerenin çarpı düğmesi programı kapatmaz");
    expect(metin).toContain("Üst çubuktaki “Çık” düğmesi");
    // modules/cikis/CikisDugmesi.tsx: diyalog başlıkları, alan ve düğme adları.
    expect(metin).toContain("“Programdan çıkılsın mı?” diye onay ister");
    expect(metin).toContain("tepsiden seçilen “Çık” bu durumlarda onay sormadan kapatır");
    expect(metin).toContain("Görevli kipinde “Çık” yönetici parolası ister");
    expect(metin).toContain("“Programdan çık” penceresinde “Yönetici parolası” alanını");
    expect(metin).toContain("bir güvenlik sınırı değildir");
    expect(metin).toContain("“Programı kapatıp yeniden açın” ekranındaki “Programdan çık”");
    expect(metin).toContain("Masaüstünde tepsi yoksa");
    expect(metin).toContain("kurucu programı kendisi düzenli kapatır");
  });

  it("tepsi menüsü: adlar tepsideki metinle birebir, kipe göre değişir", () => {
    renderPage();
    const metin = bolumMetni("tepsi-ve-cikis");

    // desktop/tray.py: MENU_SHOW, MENU_KATALOG_AC/KAPAT, MENU_GOREVLI, MENU_KILITLE, MENU_QUIT.
    for (const ad of [
      "“Pencereyi aç”",
      "“Ağ Kataloğunu aç”",
      "“Ağ Kataloğunu kapat”",
      "“Görevli kipine geç”",
      "“Kilitle”",
      "“Çık”",
    ]) {
      expect(metin).toContain(ad);
    }
    // desktop/katalog_kontrol.py::tepsi_satiri.
    expect(metin).toContain("“Ağ Kataloğu: açık — http://…”");
    expect(metin).toContain("“Ağ Kataloğu: kapalı”");
    expect(metin).toContain("ayar değiştiren komutlar görevli kipinde çalışmaz");
  });

  it("oturum açılınca başlatma: kurucu görevlerinin adları birebir", () => {
    renderPage();
    const metin = bolumMetni("tepsi-ve-cikis");

    // packaging/windows/kutuphane-defteri.iss [Tasks]: otobaslat ve otobaslat\tepside.
    expect(metin).toContain("“Oturum açılınca Kütüphane Defteri'ni başlat”");
    expect(metin).toContain("“Pencereyi açmadan tepside başlat”");
    expect(metin).toContain("kilit ekranıyla açılır");
    expect(metin).toContain("Windows oturumu açılmadan ne program ne Ağ Kataloğu çalışır");
  });

  it("gün değişimi ve uyku: saatte bir denetim, yedek, adres uyarısı, yalnız boşta uyku", () => {
    renderPage();
    const metin = bolumMetni("tepsi-ve-cikis");

    expect(metin).toContain("Program günlerce kapanmadan açık kalabilir");
    expect(metin).toContain("saatte bir tarihi denetler");
    expect(metin).toContain("o günün şifreli yedeğini alır, 14 günden eski yedekleri siler");
    expect(metin).toContain("“Afişi yeniden basın, yer imlerini güncelleyin.”");
    expect(metin).toContain("bir saat sonra yeniden denenir");
    expect(metin).toContain("boşta kalınca uykuya geçmesi engellenir");
    expect(metin).toContain("Kapağı kapatmak ya da bilgisayarı elle uyutmak engellenmez");
    // AgKataloguPaneli.tsx "Uyku" kartının onay kutusu.
    expect(metin).toContain("“Ağ Kataloğu açıkken bilgisayar boşta uykuya geçmesin”");
    expect(metin).toContain("Katalog kapalıyken uyku hiç engellenmez");
  });
});

describe("KilavuzPage — sözlük ve kalıntı denetimi", () => {
  it("iç kodlar geçmez", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    // Karar, faz ve evrak kodları (docs/sozluk.md §2).
    expect(metin).not.toMatch(/\b[UTAFSDE]\d{1,2}\b/);
    expect(metin).not.toMatch(/\b(GA|KM|UY|SU|EK|AT|V2)-\d/);
    expect(metin).not.toMatch(/\bKD\b/);
  });

  it("yasak sözcükler ve iddialar geçmez", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    // "şifre" tek başına yasak ("şifreli", "şifreleme" serbest); \b Türkçe harfte
    // çalışmadığı için harf sınıfıyla bakılır.
    expect(metin).not.toMatch(/(^|[^\p{L}])şifre(?!\p{L})/iu);
    for (const yasak of [
      /uygulama parolası/i,
      /\bOPAC\b/,
      /okuduğu kitap/i,
      /otomasyon sistemi/i,
      /yerine geçer/i,
      /Md\.? ?18 gereği/i,
      /madde 18 gereği/i,
      /\.kdbak/i,
      /\bTCKN\b/,
      /mükerrer/i,
      /pasifleştir/i,
      /emanet/i,
      // Dolaşım sözlüğünün "kullanılmaz" sütunu (docs/sozluk.md §1, F6): programda
      // uzatma, ceza ve harç yoktur; ödünç kaydı okuma bilgisi değildir.
      /ceza/i,
      /uzatma/i,
      /harç(?!\p{L})/iu,
      /son teslim tarihi/i,
      /okuma geçmişi/i,
      /okuma karnesi/i,
      /okuma puanı/i,
      /okuyucu kartı/i,
      /kütüphane kartı/i,
      /\babone/i,
      /check-?out/i,
      /kitap çıkışı/i,
      /kara liste/i,
      /ihtar/i,
      /borç listesi/i,
      // Katalog sözlüğünün "kullanılmaz" sütunu (docs/sozluk.md §1).
      /envanter/i,
      /raf kodu/i,
      /lokasyon/i,
      /\bDDC\b/,
      /Dewey numarası/i,
      /call number/i,
      /zimmet/i,
      /popüler/i,
      /en çok ödünç alınan/i,
      // Künye getirmenin konum dili (docs/sozluk.md §1, tasarım §8.5-10):
      // program "resmî künye" ya da "Bakanlık sisteminden geliyor" demez ve
      // teknik dile kaymaz.
      /otomatik künye/i,
      /resmî künye/i,
      /Bakanlık sistemi/i,
      /sorgula/i,
      /\bAPI\b/,
      // "yapay zekâ" düzeltme işaretiyle yazılır; "AI" kısaltması kullanılmaz.
      /yapay zeka/i,
      /\bAI\b/,
      // Etiket sözlüğünün "kullanılmaz" sütunu (docs/sozluk.md §1, F4).
      /rezervasyon/i,
      /sticker/i,
      /\bof+set\b/i,
      /hizalama ayarı/i,
      /yazıcı profili/i,
      /baskı kuyruğu/i,
      /yazdırma kuyruğu/i,
      /barkod stoğu/i,
      /yöntem [AB]\b/,
      // Teslim, kayıp/hasar ve ilişik sözlüğünün "kullanılmaz" sütunu (docs/sozluk.md §1,
      // §4.12, §4.13; F7). "Borç" yalnız Türk Borçlar Kanunu'nun adında geçer; "telef"
      // sözcüğü "telefon"dan ayrılır.
      /zayi/i,
      /(^|[^\p{L}])telef(?!on)/iu,
      /borç(?!lar Kanunu)/iu,
      /ilişi\p{L}* kes/iu,
      /tahsil edil/i,
      /tazminat/i,
      // Teslimin geri alınması "teslim alındı" değildir. TEK istisna Md. 19'un bedel adımı
      // (25.09.2026 kullanıcı kararı): "Bedel teslim alındı", "bedelin teslim alındığı".
      /(?<!bedel\p{L}* )teslim alındı/iu,
      /kayıp ödünç/i,
      /son uyarı/i,
      /yıl devri/i,
      /yıl kapanışı/i,
      /mezun listesi/i,
      // Ayıklama, nadir eser ve yıl sonu raporu sözlüğünün "kullanılmaz" sütunu (docs/sozluk.md
      // §1, §4.14; F8). "Hurda" yalnız "hurdaya ayırma"da geçer; "bağış kabul tutanağı" TMY'de
      // bir belge değildir — ad yalnız bunu söyleyen tek olumsuz cümlede geçer (25.09.2026
      // kullanıcı kararı, F8 ekleri 13); resmî tutanak ve fiş kısaltmasız, tam adıyla yazılır.
      /hurdaya çıkar/iu,
      /hurda listesi/iu,
      /işe yaramaz/iu,
      /bağış kabul tutanağı(?!” diye bir belge yoktur)/iu,
      /kayıttan düşme tutanağı/iu,
      /(^|[^\p{L}])VİF(?!\p{L})/u,
      /okuma raporu/iu,
      /faaliyet raporu/iu,
      /(?<!Seçim ve )Ayıklama Komisyon/iu,
    ]) {
      expect(metin).not.toMatch(yasak);
    }
  });

  it("'Kütüphaneden ilişiği yoktur' belgesi karne ya da diploma ön koşulu diye sunulmaz", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    // İki sözcük kılavuzda YALNIZ olumsuz cümlede ve birer kez geçer (tasarım §8.3,
    // docs/mevzuat/BENIOKU.md §4: dayanağı yok, Md. 18 yalnız "iadesi sağlanır" der).
    expect(metin.match(/karne/giu) ?? []).toHaveLength(1);
    expect(metin.match(/diploma/giu) ?? []).toHaveLength(1);
    expect(metin).toContain("Bu belge karne ya da diploma almanın ön koşulu değildir");
    expect(metin).not.toMatch(/ön koşul(u|udur)(?! değildir)/u);
  });

  it("DOS ve TKYS ilk geçişte açılır", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    const acilimlar: Array<[kisaltma: string, acilim: RegExp]> = [
      ["DOS", /Dewey Onlu Sınıflama \($/u],
      ["TKYS", /Taşınır Kayıt ve Yönetim Sistemi \($/u],
    ];
    for (const [kisaltma, acilim] of acilimlar) {
      const ilk = metin.indexOf(kisaltma);
      expect(ilk).toBeGreaterThan(-1);
      expect(metin.slice(0, ilk)).toMatch(acilim);
    }
  });

  it("BTR ilk geçişte açılır", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    const ilkKisaltma = metin.indexOf("BTR");
    expect(ilkKisaltma).toBeGreaterThan(-1);
    expect(metin.slice(0, ilkKisaltma)).toMatch(/bilişim teknolojileri rehber öğretmen\w*\s*\($/u);
  });

  it("başka programın kılavuz içeriği taşınmadı", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    // Kardeş programın ADI burada aranmaz: kimlik kalıntı taraması
    // (packaging/tests/test_kimlik_kalintisi.py) kılavuz kaynağını zaten tarar
    // ve adın bu test dosyasında geçmesi o kapıyı düşürür.
    for (const kalinti of [/sınav/i, /salon/i, /ders havuzu/i, /zümre/i]) {
      expect(metin).not.toMatch(kalinti);
    }
  });
});

describe("KilavuzPage — F5 düzeltmeleri", () => {
  it("geri yüklemeden sonra katalogun kalkması yedekteki ayara bağlanır (koşulsuz değil)", () => {
    renderPage();
    const yedek = bolumMetni("yedek");
    const ag = bolumMetni("ag-katalogu");

    expect(yedek).not.toContain("yeniden açılınca kendiliğinden kalkar.");
    expect(yedek).toContain("yedekte katalog açıksa kendiliğinden kalkar");
    expect(ag).toContain("geri yüklenen yedekte Ağ Kataloğu açıksa");
  });

  it("taşınabilir sürüm cümlesi yalnız Windows içindir; Pardus komutu kaynak sınırlıdır", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain("Windows'ta kurulum yapılmadan çalıştırılan (taşınabilir) sürümde");
    expect(metin).toContain("Pardus'un taşınabilir arşivinde katalog açılır");
    expect(metin).toContain("yalnız bu bilgisayarın yerel ağına ve Ayarlar'daki tahta ağı");
  });

  it("birden çok izin kuralı, öğrenci erişimli ağ ve kapatma yolu anlatılır", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain("birden çok izin kuralı varsa hepsi listelenir");
    expect(metin).toContain("Bu bilgisayar öğrenci erişimli ağda");
    expect(metin).toContain("saatte bir kendiliğinden yeniden dener");
    expect(metin).toContain("ayar açık kaldıkça program her açılışta yeniden dener");
  });
});

// ---------------------------------------------------------------------------
// F6 — Üyelik, Kart ve Belgeler + Dolaşım Masası
//
// Ekran adları ön yüz sabitlerinden okunur (`modules/dolasim`, `modules/uyelik`,
// `kip/GorevliEkrani`). SUNUCU iletileri (ör. “Üyenin gecikmiş ödüncü var…”, kart
// iletileri) buradan okunamaz; birebir kopyalandı ve kaynakları yanında yazılı —
// sunucu tarafında `apps/kutuphane/tests/test_dolasim_metinleri.py` aynı iletilerin
// kılavuz kaynağında ve sözlükte geçtiğini sabitlerden denetler, mevzuat
// alıntılarını da docs/mevzuat metniyle karşılaştırır.
// ---------------------------------------------------------------------------

describe("KilavuzPage — Dolaşım Masası (F6)", () => {
  it("ekran, kutu, düğme ve pencere adları masa ekranının sabitleriyle aynıdır", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    expect(metin).toContain(`${DOLASIM_MASASI_BASLIGI}'ndan yapılır`);
    expect(metin).toContain(`“${OKUTMA_KUTUSU}”`);
    expect(metin).toContain(`“${BITTI_DUGMESI}” düğmesine basın`);
    expect(metin).toContain(`${BAGLAM_SURESI_MS / 1000} saniye işlem yapmadığınızda`);
    expect(metin).toContain(`“${DURUM_SORGUSU}” işaretliyken`);
    expect(metin).toContain(`“${KARTSIZ_DUGMESI}” düğmesine basın`);
    expect(KARTSIZ_BASLIGI).toBe(KARTSIZ_DUGMESI);
    expect(metin).toContain(`“${ISTISNA_BASLIGI}” penceresi açılır`);
    expect(metin).toContain(`“${KART_KILIDI_BASLIGI}” şeridi`);
    expect(metin).toContain(`“${GOREVLI_KATALOG_DUGMESI}” ile`);
    expect(metin).toContain(`“${GOREVLI_MASAYA_DON}” masaya getirir`);
    expect(metin).toContain(BASKA_UYEDE_SORUSU);
    expect(metin).toContain(BU_UYEDE_SORUSU);
    expect(metin).toContain(`“${BASKA_UYEDEN_IADE_UYARISI}”`);
    for (const dugme of [
      "“İade al ve ödünç ver”",
      "“İade al”",
      "“Vazgeç”",
      "“Kart okutmayı aç”",
      "“Okul no ya da ad”",
      "“Ara”",
      "“Üyeyi aç”",
      "“Gerekçe”",
      "“Açıklama”",
      "“Gerekçeyle ödünç ver”",
      "“Okuma sesi açık”",
      "“Kutuya dön”",
    ]) {
      expect(metin).toContain(dugme);
    }
    for (const { label } of KARTSIZ_GEREKCELER) expect(metin).toContain(`“${label}”`);
    for (const { label } of ISTISNA_GEREKCELERI) expect(metin).toContain(`“${label}”`);
    // Bağlamdaki şerit (DolasimMasasi.UyeKarti).
    expect(metin).toContain("“Kartsız ödünç — gerekçe: …”");
    // Yardım metni sözlükteki yazımla: "Sağlık ya da aile bilgisi yazmayın."
    expect(ISTISNA_YARDIMI).toBe("Sağlık ya da aile bilgisi yazmayın.");
    expect(metin).toContain("Açıklamaya sağlık ya da aile bilgisi yazmayın.");
    const bolum = document.getElementById("dolasim") as HTMLElement;
    const baglanti = within(bolum).getByRole("link", { name: DOLASIM_MASASI_BASLIGI });
    expect(baglanti).toHaveAttribute("href", "/dolasim");
  });

  it("sunucu iletileri birebir yazılır (kaynakları yanında)", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    for (const ileti of [
      // services/masa.py
      "“Ödünç verildi.”",
      "“İade alındı.”",
      "“Bu kart tanınmadı — kütüphane yöneticisine yönlendirin.”",
      "“Kart numarası hatalı. Kartı yeniden okutun.”",
      // selectors_dolasim.REVOKED_CARD_MESSAGE
      "“İptal edilmiş kart — kütüphane yöneticisine yönlendirin.”",
      // barcode.ISBN_SCAN_MESSAGE
      "“Bu ISBN barkodu. Kitabın kütüphane etiketini okutun.”",
      // label_queue.STAFF_REFER (görevli kipinde bağlanmamış ya da iptal edilmiş etiket)
      "“Kitabı ayırın ve kütüphane yöneticisine gösterin.”",
      // services/circulation.py — COPY_STATE_MESSAGES
      "“Rafta — ödünç değil.”",
      "“Kayıp kaydında.”",
      "“Onarımda.”",
      "“Sınıf kitaplığında.”",
      // circulation: üyelik ve gecikme
      "“Üyelik sonlanmış — ödünç verilemez.”",
      "“Üye okuldan ayrılmış — ödünç verilemez.”",
      "“Ödünç verilemiyor — kütüphane yöneticisine yönlendirin.”",
      "“Üyenin gecikmiş ödüncü var. Önce iade alın ya da gerekçeli istisnayla ödünç verin.”",
      // circulation: sayı sınırı (f-string, öğrenci sınırıyla) ve dönem sonu uyarısının sonu
      "“Ödünç sınırı dolu (en çok 3 kitap).”",
      "“… Süre kısaltılmaz.”",
      // circulation: ödünç verilmeyen kaynak (Copy.not_loanable_reason)
      "“Ödünç verilmez — kütüphanede okunur.”",
    ]) {
      expect(metin).toContain(ileti);
    }
  });

  it("süre sabittir; ödünç sınırı Md. 18/1'den; kayma iki ayrı kuraldır ve Yönetmeliğe bağlanmaz", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    // docs/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md md. 18/1 — ilk ve son cümle
    // birebir; aradaki cümleler Bakanlığın sistemini andığı için "…" ile atlanır.
    expect(metin).toContain(
      "“Bir kitabı ödünç alma süresi on beş gündür. … Öğrencilere bir defasında en fazla üç, öğretmenlere en fazla beş kitap ödünç verilebilir.”",
    );
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 18/1");
    expect(metin).toContain("Ödünç süresi on beş gündür ve değiştirilemez");
    // Kayma: iki kural, dayanakları ayrı; hiçbiri Yönetmelik hükmü gibi sunulmaz.
    expect(metin).toContain("Bu kayma Yönetmelikten gelmez; iki ayrı kuraldır");
    expect(metin).toContain("Türk Borçlar Kanunu'ndaki genel kuralı kıyasen uygular");
    expect(metin).toContain(
      "İdari izin ve diğer kapalı günler de her zaman atlanır; bu programın kuralıdır",
    );
    expect(metin).toContain("“İade tarihi öğrenciye kapalı günlerde kaydırılır”");
    expect(metin).toContain("Bu okulun tercihidir, mevzuatta dayanağı yoktur");
    // Dönem sonu yalnız uyarıdır; ödünç sınırı ve Md. 16/1 kaynakları istisna almaz.
    expect(metin).toContain("süre yine on beş gündür");
    expect(metin).toContain("okul daha düşük tutabilir");
    expect(metin).toContain(
      "Ödünç sınırı ve ödünç verilmeyen kaynaklar hiçbir kipte istisna almaz",
    );
    expect(metin).toContain("“Yıl sonu son ödünç tarihi” geçtiyse yeni ödünç verilmez");
    expect(metin).toContain("“Diğer personele ödünç verilir”");
    expect(metin).not.toMatch(/Md\.? ?18 gereği/i);
    expect(metin).not.toMatch(/madde 18 gereği/i);
  });

  it("gecikme engeli okulun tercihidir; istisna yalnız yönetici kipinde ve gerekçeyle", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    expect(metin).toContain(
      "“Gecikmiş kitabı olana yeni ödünç verilmez” açıksa (okulun tercihidir)",
    );
    expect(metin).toContain(
      "Gerekçeli istisna yalnız gecikme engeli içindir ve yalnız yönetici kipinde yapılır",
    );
    expect(metin).toContain("İstisna, gerekçesi ve açıklamasıyla ödünç kaydına geçer.");
    // Gecikmenin karşılığı: para yok, süre değişmez, pusula (uzatma/ceza sözcükleri yok).
    expect(metin).toContain("Gecikme için para alınmaz, ödünç süresi değişmez");
    expect(metin).toContain("kişiye özel pusulayla hatırlatılır");
  });

  it("iade hiçbir durumda kilitlenmez; başka üyedeki kitap iade + uyarıyla verilir", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    expect(metin).toContain("İade hiçbir durumda kilitlenmez");
    expect(metin).toContain("kart okutma durdurulmuşken gelen kitap da iade edilir");
    expect(metin).toContain("Üye bağlamı açıkken iade almak için önce “Bitti” deyin");
    expect(metin).toContain("önce iadeyi alır, sonra kitabı karttaki üyeye verir");
    expect(metin).toContain("Görevli kipinde önceki üyenin kim olduğu gösterilmez");
    expect(metin).toContain("okuttuğunuz sırayla işlenir, hiçbiri kaybolmaz");
  });

  it("F6 düzeltme turu: iade önerisi, istem yarışı, durum sorgusu, pencere sırası, kilit şeridi", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    expect(metin).toContain(`“${IADE_ONERISI}”`);
    expect(metin).toContain(`“${ISTEM_BAGLAM_DEGISTI}”`);
    expect(metin).toContain(`(${DURUM_SORGUSU_KAPANDI})`);
    expect(metin).toContain("“Yalnız durum sor” ile bakılan kitapta iki kısa ses");
    expect(metin).toContain("Pencere açıkken okuttuğunuz kitaplar kaybolmaz");
    expect(metin).toContain("Pencere açıkken üye bağlamının 60 saniyelik süresi işlemez");
    expect(metin).toContain("on dakika içinde beş tanınmayan veya iptal edilmiş kart");
    expect(metin).toContain("şerit dururken okutulan kitabın iadesi alınır");
    expect(metin).toContain("görevli barkod deneyerek üyenin elindeki kitapları öğrenemez");
    expect(metin).toContain(
      "“Yıl sonu son ödünç tarihi geçti — yeni ödünç verilmez. İade alınabilir.”",
    );
    expect(metin).toContain("iki takvim yılına resmî tatiller ve dini bayramlar");
  });

  it("görevli kipinde masa: görevlinin gördüğü ve görmediği, gizlilik", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    expect(
      screen.getByRole("heading", { level: 3, name: "Görevli kipinde masa" }),
    ).toBeInTheDocument();
    expect(metin).toContain("Görevli üyenin yalnız adını ve kalan ödünç hakkını görür");
    expect(metin).toContain("sınıfı ve açık ödünçleri görünmez");
    expect(metin).toContain("hangi kitabın kaç gün geciktiği görevliye gösterilmez");
    expect(metin).toContain("kimden geldiği ve gecikip gecikmediği görevli ekranında görünmez");
    expect(metin).toContain("“Yalnız durum sor” ile bakılan kitabın kimde olduğu da görünmez");
    expect(metin).toContain("son işlemler listesinde üye adı yazmaz");
    expect(metin).toContain(
      "Üye listesi, ödünç geçmişi, gecikmiş ödünçler, gerekçeli istisna ve kartsız ödünç yönetici kipindedir",
    );
    expect(metin).toContain("Kişisel olmayan nedenler (ödünç sınırının dolması");
    expect(metin).toContain("Art arda beş geçersiz kart");
    expect(metin).toContain("görevli kipinden çıkılmaz");
    expect(metin).toContain("görevliye göreve başlamadan masa kartını verin");
    expect(metin).toContain("ekranın fotoğrafını çekmez");
  });

  it("kartsız ödünç yalnız yönetici kipinde; Md. 23/1-a'dan sapma olarak işaretlenir", () => {
    renderPage();
    const metin = bolumMetni("dolasim");

    // docs/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md md. 23/1-a birebir.
    expect(metin).toContain("“a) Öğrenci, öğretmen kartını kütüphane görevlisine verir.”");
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 23/1-a");
    expect(metin).toContain("Kartı yanında olmayan üyeye yalnız yönetici kipinde ödünç verilir");
    expect(metin).toContain("ödünç kaydında kartsız ödünç işareti ve gerekçesi durur");
    expect(metin).toContain("Kartı yanında olmayan üyeyi görevli kütüphane yöneticisine");
  });
});

describe("KilavuzPage — Üyelik, Kart ve Belgeler (F6)", () => {
  it("üyelik isteğe bağlıdır; ekran ve düğme adları ekrandakiyle birebir", () => {
    renderPage();
    const metin = bolumMetni("uyelik");

    expect(metin).toContain("üyelik isteğe bağlıdır");
    expect(metin).toContain("e-Okul listesini aktarmak da üyelik açmaz");
    // Yönetmelik parçaları birebir (md. 16/1 ve 17/1; geri kalanı Bakanlığın sistemini anar).
    expect(metin).toContain("“üye olmak koşuluyla”");
    expect(metin).toContain("“üye olmak isteyen”");
    for (const ad of [
      "Kişiler → Üyeler",
      "Kişiler → Üyelik İstek Listesi",
      "Kişiler → Kart Basımı",
      "“Üyelik isteği tarihi”",
      "“Seçilenleri üye yap”",
      "“Üyelik aç”",
      "“Personele üyelik aç”",
      "“Kart Basımı Bekleyen”",
      "“Kartı Basılmış”",
      "“Yazıcı (kalibrasyon)”",
      "“Önizle”",
      "“PDF'i indir”",
      "“Basıldı olarak işaretle”",
      "“Basım işaretini geri al”",
      "“Kesim çizgisi bas”",
      "“Yazıcı kalibrasyonunu göster”",
      "“Kartı yenile”",
      "“Kart yenilensin mi?”",
      "“Üyeliği sonlandır”",
      "“Üyenin isteği”",
      "“Yanlış kayıt”",
      "“Üyeliği sil”",
      "“Ayrıldı olarak işaretle”",
      `“${GECIKMIS_ODUNCLER_BASLIGI}”`,
      "“Şube”",
      "“Üyelik Belgeleri”",
      "“Başvuru adresi”",
      "“E-posta ya da telefon”",
      `“${KAPANIS_KARTI_BASLIGI}”`,
      "“Kontrol ettim”",
      "“Kilitle”",
    ]) {
      expect(metin).toContain(ad);
    }
  });

  it("aydınlatma metni e-Okul aktarımından önce duyurulur (KVKK md. 10/1)", () => {
    renderPage();
    const metin = bolumMetni("uyelik");

    expect(
      screen.getByRole("heading", { level: 3, name: "Önce aydınlatma metni" }),
    ).toBeInTheDocument();
    expect(metin).toContain("e-Okul listelerini programa aktarmadan önce öğrencilere ve personele");
    // docs/mevzuat/6698-kvkk.md md. 10/1'in birebir parçası.
    expect(metin).toContain("“elde edilmesi sırasında”");
    expect(metin).toContain("(md. 10/1)");
    expect(metin).toContain("Listeleri daha önce aktardıysanız metni şimdi duyurun");
    expect(metin).toContain("programda saklanmaz");
    expect(metin).toContain("programın kayıtları bugün kendiliğinden silmediğini");
    // Aydınlatma bölümün İLK alt başlığıdır (işin sırası: önce duyuru, sonra üyelik).
    const bolum = document.getElementById("uyelik") as HTMLElement;
    const altBasliklar = within(bolum)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(altBasliklar[0]).toBe("Önce aydınlatma metni");
  });

  it("kart sınıf taşımaz; PDF basıldı saymaz; pusula dağıtım kuralı ve dipnot yazılıdır", () => {
    renderPage();
    const metin = bolumMetni("uyelik");

    expect(metin).toContain("sınıf yazmaz");
    // Kartın konum notu (labels/card.POSITION_NOTE; sözlük "Kart" satırı) — Bakanlığın
    // sistemini adıyla anan ikinci yarısı kılavuza girmez.
    expect(metin).toContain(
      "Yönetmeliğin 20. maddesinde öngörülen kullanıcı kartının okulca düzenlenen yerel karşılığı",
    );
    expect(metin).toContain("PDF'i almak kartı basılmış saymaz");
    expect(metin).toContain("hiçbir zaman başka birine yeniden verilmez");
    expect(metin).toContain(
      "Pusulayı kütüphane yöneticisi ya da sınıf rehber öğretmeni dağıtır. Sınıfta okunmaz, öğrenci görevliye dağıttırılmaz.",
    );
    expect(metin).toContain("İade hatırlatma pusulası tek kişiliktir");
    expect(metin).toContain("“KİŞİYE ÖZELDİR”");
    expect(metin).toContain(`“${LISTE_DIPNOTU}”`);
    expect(metin).toContain("“İptal edilmiş kart — kütüphane yöneticisine yönlendirin.”");
    expect(metin).toContain("Açık ödüncü olan üyelik sonlandırılamaz");
    expect(metin).toContain("Program gecikme için para almaz ve ödünç süresini değiştirmez");
  });

  it("masa kartı görevliye göreve başlamadan verilir; KVKK md. 12/1 birebir", () => {
    renderPage();
    const metin = bolumMetni("uyelik");

    expect(metin).toContain("Görevliye göreve başlamadan verin");
    // docs/mevzuat/6698-kvkk.md md. 12/1 birebir.
    expect(metin).toContain(
      "“Veri sorumlusu; a) Kişisel verilerin hukuka aykırı olarak işlenmesini önlemek, b) Kişisel verilere hukuka aykırı olarak erişilmesini önlemek, c) Kişisel verilerin muhafazasını sağlamak, amacıyla uygun güvenlik düzeyini temin etmeye yönelik gerekli her türlü teknik ve idari tedbirleri almak zorundadır.”",
    );
    expect(metin).toContain("6698 sayılı Kişisel Verilerin Korunması Kanunu, md. 12/1");
  });

  it("ekran bağlantıları sekmelere gider", () => {
    renderPage();
    const bolum = document.getElementById("uyelik");
    expect(bolum).not.toBeNull();
    const adresler = Array.from(bolum?.querySelectorAll("a") ?? []).map((a) =>
      a.getAttribute("href"),
    );
    expect(adresler).toEqual(
      expect.arrayContaining([
        "/kisiler?tab=uyeler",
        "/kisiler?tab=uyelik-istekleri",
        "/kisiler?tab=kart-basimi",
        "/ayarlar?tab=okul",
      ]),
    );
  });
});

describe("KilavuzPage — F6 ile değişen eski bölümler", () => {
  it("Kişiler: altı sekme anılır, aydınlatma metni aktarımdan önce hatırlatılır", () => {
    renderPage();
    const metin = bolumMetni("kisiler");

    expect(metin).toContain("sayfasının ilk üç sekmesi kişi kayıtlarını tutar");
    expect(metin).toContain("(“Üyeler”, “Üyelik İstek Listesi”, “Kart Basımı”)");
    expect(metin).not.toContain("sayfasının üç sekmesi vardır");
    expect(metin).toContain(
      "e-Okul listelerini aktarmadan önce kütüphane aydınlatma metnini duyurun.",
    );
    expect(metin).toContain("hiç kütüphane üyesi olmamış kişinin kaydında yapılabilir");
    expect(
      new Set(
        screen
          .getAllByRole("link", { name: "Kişiler → Üyeler" })
          .map((a) => a.getAttribute("href")),
      ),
    ).toEqual(new Set(["/kisiler?tab=uyeler"]));
  });

  it("ödünç artık vardır: 'sonraki sürümde' sözleri kalkar, saklama taraması yok denir", () => {
    const { container } = renderPage();
    const metin = sayfaMetni(container);

    // Üye kartı okulun TAM adını basar (labels/card.py); kısa ad kitap etiketlerindedir.
    expect(bolumMetni("ilk-kurulum")).toContain(
      "Kısa ad kitap etiketlerinde basılır, en çok 24 karakterdir; üye kartında okulun tam adı yazar.",
    );
    expect(metin).not.toContain("Ödünç ve iade ekranları sonraki sürümde");
    expect(metin).not.toContain("Barkod okuyucuyla ödünç verme sonraki sürümde");
    expect(metin).not.toContain("ödünç işlemleriyle birlikte sonraki");
    expect(bolumMetni("katalog")).toContain(
      "kurallar ödünç verilirken Dolaşım Masası'nda uygulanır",
    );
    expect(bolumMetni("katalog")).toContain("o zamana kadar üyelik ve ödünç kayıtları silinmez");
  });
});

// ---------------------------------------------------------------------------
// F7 — Teslim, Kayıp/Hasar/Onarım, İlişik ve Yıl Akışları
//
// Ekran adları `modules/teslim`, `modules/kayip`, `modules/yil`, masanın
// (`dolasim/DolasimMasasi`) ve görevli ekranının sabitlerinden okunur. Sabiti olmayan
// sekme ve adım adları ekranın kaynağından (TeslimlerPage TABS, YilSonuPage /
// YilBasiPage ADIMLAR) birebir kopyalandı. SUNUCU iletileri ve mevzuat alıntıları
// `apps/kutuphane/tests/test_teslim_ilisik_kilavuz_metinleri.py` ile sunucu
// sabitlerine ve docs/mevzuat metnine kilitlidir.
// ---------------------------------------------------------------------------

describe("KilavuzPage — Sınıf Kitaplığına ve Öğretmene Teslim (F7)", () => {
  it("teslim ödünç değildir: sayı sınırı, süre ve üyelik yok; 'kalan hak' dili kullanılmaz", () => {
    renderPage();
    const metin = bolumMetni("teslim");

    expect(metin).toContain("teslimdir, ödünç değildir");
    expect(metin).toContain("ödünç sınırı ve on beş günlük süre uygulanmaz, üyelik gerekmez");
    expect(metin).toContain("teslim alanın ödünç hakkından düşmez");
    expect(metin).not.toMatch(/kalan (ödünç )?hak/iu);
    expect(metin).toContain(`(“${DIGER_PERSONEL_GEREKCESI}”)`);
    expect(metin).toContain("Teslim yalnız etkin ders yılının bir şubesine ya da bir öğretmene");
    // Ödünç verilmeyen kaynaklar teslim edilebilir (services/deliveries.delivery_obstacle).
    expect(metin).toContain("Ödünç verilmeyen kaynaklar da teslim edilebilir");
  });

  it("ekran, sekme, kutu ve düğme adları teslim ekranlarının sabitleriyle aynıdır", () => {
    renderPage();
    const metin = bolumMetni("teslim");

    expect(metin).toContain(`Dolaşım Masası → ${TESLIMLER_BASLIGI}`);
    // TeslimlerPage TABS (sabit dışa açılmaz; kaynaktan birebir).
    expect(metin).toContain("“Teslim Kayıtları”, “Yeni Teslim” ve “Geri Alma”");
    for (const alan of Object.values(TESLIM_ALAN_TURU_TR)) expect(metin).toContain(`“${alan}”`);
    expect(metin).toContain("“Teslim Alan” kartında");
    expect(metin).toContain("“Teslim Edilecek Kitaplar” kartında");
    expect(metin).toContain(`“${TESLIM_KUTUSU}” kutusuna okutun`);
    expect(metin).toContain(`“${ZATEN_LISTEDE}”`);
    expect(metin).toContain(`“${TESLIM_ET_DUGMESI}”e basın`);
    expect(metin).toContain(`“${GERI_ALMA_BASLIGI}” kartındaki “${GERI_ALMA_KUTUSU}” kutusuna`);
    expect(metin).toContain(`“${BEKLENEN_DONUS_GECTI}” rozeti`);
    expect(metin).toContain(`“${GERI_ALMA_DOKUMU_ADI}” kartından`);
    // Belge adı (sözlük §2) cümle içinde küçük harfle.
    expect(metin).toContain(TESLIM_LISTESI_ADI.toLocaleLowerCase("tr"));
    expect(metin).toContain(`“${TESLIM_DURUMU_TR.LOST_CONVERTED}” olarak kapanır`);
    for (const ad of [
      "“Teslim tarihi”",
      "“Beklenen dönüş (isteğe bağlı)”",
      "“Belge no (isteğe bağlı)”",
      "“Şube”",
      "“Çıkar”",
      "“Listeyi boşalt”",
      "“Önizle”",
      "“PDF'i indir”",
      "“Yeni teslim”",
      "“Durum”",
      "“Teslim alan”",
      "“Belge no”",
      "“Kayıp bildir”",
      "“12 kitap 9/A sınıf kitaplığına teslim edilsin mi?”",
      "“Teslim eden — Kütüphane yöneticisi”",
      "“Teslim alan — Sınıf kitaplığı sorumlusu”",
      "“Teslim alan — Öğretmen”",
      "“Sınıf Kitaplıkları”",
    ]) {
      expect(metin).toContain(ad);
    }
  });

  it("sunucu iletileri birebir yazılır; teslim tek işlemdir", () => {
    renderPage();
    const metin = bolumMetni("teslim");

    for (const ileti of [
      // services/deliveries.py — delivery_obstacle (CopyStatus.ON_LOAN etiketiyle)
      "“Ödünçte — teslim edilemez.”",
      // YeniTeslim (toplu ret)
      "“Listedeki bazı kitaplar teslim edilemiyor; hiçbir teslim yapılmadı.”",
      // services/deliveries.py — TAKE_BACK_DONE_MESSAGE, NOT_DELIVERED_*, SECTION_DELETE
      "“Geri alındı.”",
      "“Bu kitap teslimde değil (…).”",
      "“Bu kitap teslimde değil (Ödünçte). İade için dolaşım masasını kullanın.”",
      "“Bu şubede … açık teslim var; önce geri alın.”",
    ]) {
      expect(metin).toContain(ileti);
    }
    expect(metin).toContain("Teslim tek işlemdir");
    expect(metin).toContain("hiçbir teslim yapılmaz");
    expect(metin).toContain("Tek teslimde en çok 500 kitap olur");
  });

  it("teslimdeki kitap 'Sınıf kitaplığında' görünür; beklenen dönüşün geçmesi gecikme değildir", () => {
    renderPage();
    const metin = bolumMetni("teslim");

    expect(metin).toContain(`“${COPY_STATUS_TR.DELIVERED}” görünür`);
    expect(metin).toContain("Kime teslim edildiği Ağ Kataloğunda ve görevli ekranında görünmez");
    expect(metin).toContain("bir kitap aynı anda ya bir üyede ödünçtedir ya da teslimdedir");
    expect(metin).toContain("Bu bir gecikme değildir");
    expect(metin).toContain("teslimde hatırlatma pusulası da engel de yoktur");
    expect(metin).toContain("Geri alma, iade gibi, hiçbir durumda kilitlenmez");
    // Ağ Kataloğu bölümü de teslimin kimde olduğunu göstermediğini söyler.
    expect(bolumMetni("ag-katalogu")).toContain(
      "hangi şubede ya da hangi öğretmende olduğu da görünmez",
    );
  });

  it("geri alma: masadaki öneri ve görevli kipi; teslim vermek yönetici kipindedir", () => {
    renderPage();
    const metin = bolumMetni("teslim");

    // Masa (DolasimMasasi): ileti + öneri + düğme; öneri kime teslim edildiğini söylemez.
    expect(SINIF_KITAPLIGINDA).toBe(`${COPY_STATUS_TR.DELIVERED}.`);
    expect(metin).toContain(
      `“${SINIF_KITAPLIGINDA}” iletisinin altında “${TESLIM_GERI_ALMA_ONERISI}”`,
    );
    expect(metin).toContain(`“${TESLIMDEN_GERI_AL}” düğmesi kitabı geri alır`);
    expect(metin).toContain("Öneri kitabın kime teslim edildiğini söylemez");
    // Görevli ekranı (GorevliEkrani): düğme, bölüm başlığı ve çıkış düğmesi.
    expect(GOREVLI_GERI_ALMA_DUGMESI).toBe(TESLIMDEN_GERI_AL);
    expect(metin).toContain(
      `“${GOREVLI_GERI_ALMA_DUGMESI}” düğmesiyle açılan “${GOREVLI_GERI_ALMA_BASLIGI}” bölümünde`,
    );
    expect(metin).toContain(`“${GOREVLI_DOGRULAMA_BITIR}” masaya döndürür`);
    expect(metin).toContain("teslim alanın kim olduğu ve belgeler görünmez");
    expect(metin).toContain(
      "Teslim vermek, teslim kayıtları ve teslim listeleri yönetici kipindedir",
    );
    // Dolaşım bölümü de öneriyi anar.
    expect(bolumMetni("dolasim")).toContain(`“${TESLIMDEN_GERI_AL}” düğmesi çıkar`);
  });

  it("teslim listesi TMY 23/6'ya kıyasen; sayımdaki yeri 32/5'e kıyasen ve sayım kurulunun kararı", () => {
    renderPage();
    const metin = bolumMetni("teslim");

    expect(metin).toContain("Dayanıklı Taşınırlar Listesinin işlevini gördüğü notu basılır");
    expect(metin).toContain("(Taşınır Mal Yönetmeliği md. 23/6'ya kıyasen)");
    expect(screen.getByRole("heading", { level: 3, name: "Sayımdaki yeri" })).toBeInTheDocument();
    expect(metin).toContain("Sayım ekranı sonraki bir sürümde gelecek");
    expect(metin).toContain("sayım kurulu karar verir");
    expect(metin).toContain("(Taşınır Mal Yönetmeliği md. 32/5'e kıyasen)");
    expect(metin).toContain("TKYS'de Taşınır Teslim Belgesi düzenlendiyse");
  });
});

describe("KilavuzPage — Kayıp, Hasar ve Onarım (F7)", () => {
  it("ekran, pencere ve düğme adları kayıp ekranlarının sabitleriyle aynıdır", () => {
    renderPage();
    const metin = bolumMetni("kayip-hasar");

    expect(metin).toContain(`Dolaşım Masası → ${KAYIP_HASAR_BASLIGI}`);
    expect(metin).toContain(`“${KAYIP_BASLIGI}” diye sorar`);
    expect(metin).toContain(`“${HASAR_BASLIGI}” diye sorar`);
    expect(metin).toContain(`“${KAYIP_DUGMESI}”e basın`);
    expect(metin).toContain(`“${HASAR_DUGMESI}” deyin`);
    for (const tur of Object.values(DOSYA_TURU_TR)) {
      expect(metin).toContain(`“${tur} dosyası”`);
    }
    // Sorumlu notunun yardımı cümle içinde (SORUMLU_NOTU_YARDIMI'nın ikinci cümlesi).
    expect(SORUMLU_NOTU_YARDIMI).toContain("Sağlık ya da aile bilgisi yazmayın.");
    expect(metin).toContain("sağlık ya da aile bilgisi yazmayın");
    expect(metin).toContain(`“${TUTANAK_ADI}” bölümünden tutanak basılır`);
    expect(metin).toContain(`“${NUSHA_ISLEMLERI_BASLIGI}” bölümünde “Onarıma gönder” deyin`);
    expect(metin).toContain(`“${KAYIP_BILDIRILDI}”`);
    for (const ad of [
      "“Görünüm”",
      "“Tür”",
      "“Tespit tarihi”",
      "“Sorumlu üye (isteğe bağlı)”",
      "“Sorumlu notu (isteğe bağlı)”",
      "“Nüshayı onarıma da gönder”",
      "“Notu kaydet”",
      "“Çözüm”",
      "““…” işlensin mi?”",
      "“İşle”",
      "“Vazgeç”",
      "“O günkü piyasa bedeli (TL)”",
      "“Onarımdan dön”",
      "“Nüsha onarıma gönderilsin mi?”",
      "“Nüsha onarımdan dönsün mü?”",
      "“Nüshayı düzenle”",
      "“Dosyayı göster”",
      "“Bu tutanak bir ödeme ya da tahsilat belgesi değildir.”",
    ]) {
      expect(metin).toContain(ad);
    }
  });

  it("çözümlerin adları CaseResolution etiketleriyle birebir; bekleyen durum düğme değildir", () => {
    renderPage();
    const metin = bolumMetni("kayip-hasar");

    for (const [kod, etiket] of Object.entries(COZUM_TR)) {
      if (kod === "PENDING") continue;
      expect(metin).toContain(`“${etiket}”`);
    }
  });

  it("kayıp bildirimi ödüncü ya da teslimi kapatır; 'Bulundu' yeniden açmaz", () => {
    renderPage();
    const metin = bolumMetni("kayip-hasar");

    expect(metin).toContain(`Nüsha “${COPY_STATUS_TR.LOST}” olur ve kayıp dosyası açılır`);
    expect(metin).toContain("teslimdeyse teslim “Kayba dönüştü” olarak kapanır");
    expect(metin).toContain("Kayba dönüşen ödünç artık ödünç sınırına ve gecikmeye sayılmaz");
    expect(metin).toContain("kapanan ödünç ya da teslim yeniden açılmaz");
    expect(metin).toContain("Kayıp bildirimi geri alınmaz");
    expect(metin).toContain(
      "ödünçteki kitabın önce iadesini alın, teslimdeki kitabı önce geri alın",
    );
    expect(metin).toContain("Hasar dosyası kitabı dolaşımdan çıkarmaz");
    expect(metin).toContain("Onarımdan dönüş hasar dosyasını kendiliğinden kapatmaz");
    expect(metin).toContain("Kapanan dosya yeniden açılmaz");
  });

  it("bedel yalnız ortaöğretimde (Md. 19/1 birebir); program tahsilat yapmaz, disiplin başlatmaz", () => {
    renderPage();
    const metin = bolumMetni("kayip-hasar");

    // docs/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md md. 19/1 birebir.
    expect(metin).toContain(
      "“Ortaöğretim okul kütüphanelerinde hasara uğratılan veya kaybedilen kaynak ilgili kişiden temin edilir, temin edilememesi hâlinde o günkü piyasa bedeli, hasara uğratan veya kaybeden kişiden alınır. Kaynak bedeli ile mevcudu varsa aynısı yoksa kaybedilenin kaydı silinerek başka eser satın alınır.”",
    );
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 19/1");
    expect(metin).toContain(`“${SCHOOL_LEVEL_TR.ORTAOGRETIM}” seçiliyse görünür`);
    // Dosya penceresindeki not (DosyaAyrintisi.BEDEL_YOK_NOTU) — ilk cümlesi birebir
    // ("Md. 19)." içindeki nokta cümle sonu değildir; cümle ")." ile biter).
    const notunIlkCumlesi = BEDEL_YOK_NOTU.slice(0, BEDEL_YOK_NOTU.indexOf("). ") + 2);
    expect(notunIlkCumlesi).toMatch(/\(Yönetmelik Md\. 19\)\.$/u);
    expect(metin).toContain(`“${notunIlkCumlesi} …”`);
    expect(metin).toContain("dosya açık kalır");
    expect(metin).toContain("son üçü bedel teslim alındıktan sonra");
    expect(metin).toContain("Program tahsilat yapmaz.");
    expect(metin).toContain("Program disiplin sürecini de başlatmaz");
    expect(metin).toContain("Ortaöğretim Kurumları Yönetmeliği'nde (md. 164/1-g)");
  });

  it("bedel iki adımdır: belirlenince açık iş sürer, teslim alınınca kişinin işi biter (25.09.2026)", () => {
    renderPage();
    const kayip = bolumMetni("kayip-hasar");
    const ilisik = bolumMetni("ilisik");

    expect(kayip).toContain("Ortaöğretimde beş çözüm daha vardır; ilk ikisi bedelin iki adımıdır");
    expect(kayip).toContain(`“${COZUM_TR.PRICE_DETERMINED}”: pencere “O günkü piyasa bedeli (TL)”`);
    expect(kayip).toContain("kişinin kütüphaneyle açık işi sürer");
    expect(kayip).toContain(`“${COZUM_TR.PRICE_RECEIVED}”: kişiden bedelin teslim alındığı`);
    expect(kayip).toContain("Kişinin kütüphaneyle açık işi biter");
    expect(kayip).toContain("“Kütüphaneden ilişiği yoktur” belgesi basılabilir");
    expect(kayip).toContain(`satırın altında “${OKULUN_ACIK_ISI_ETIKETI}” yazar`);
    expect(kayip).toContain("Bu adım geri alınmaz");
    expect(kayip).toContain(`“${COZUM_TR.PRICE_RECEIVED}” da yalnız bir kayıttır`);
    expect(kayip).toContain(
      `piyasa bedeli iki adımın tarihleriyle (“${COZUM_TR.PRICE_DETERMINED}”, “${COZUM_TR.PRICE_RECEIVED}”)`,
    );
    expect(ilisik).toContain(
      `“${COZUM_TR.PRICE_RECEIVED}” durumundaki dosya ise kişinin açık işi değildir`,
    );
    expect(ilisik).toContain("kayıp ya da hasar nedeniyle kendisinden beklenen bir işlem");
    for (const yasak of [/borç/i, /ceza/i, /tahsil edil/i]) {
      expect(kayip).not.toMatch(yasak);
    }
  });

  it("F7 düzeltme turu: öneri sonrası bulunma, hasarın kayba dönüşmesi, teslim ve döküm", () => {
    renderPage();
    const kayip = bolumMetni("kayip-hasar");
    const teslim = bolumMetni("teslim");

    // Öneri kayıttan düşme değildir: kayıp dosyasında "Bulundu" kalır.
    expect(kayip).toContain("Öneri kayıttan düşme değildir");
    expect(kayip).toContain(`“${COZUM_TR.FOUND_RETURNED}” düğmesi durur`);
    // 25.09.2026 kullanıcı kararı (F8 ekleri 14): bedelle başka eser alınmış dosyada da kitap
    // kayıttan düşülmemişse rafa döner; "seçilemez" kuralı kalktı.
    expect(kayip).not.toContain(`“${COZUM_TR.FOUND_RETURNED}” seçilemez`);
    expect(kayip).toContain(`“${COZUM_TR.FOUND_AFTER_PRICE}” düğmesi durur`);
    // Açık hasar dosyalı kitap kaybolunca hasar dosyası "Kayba dönüştü" ile kapanır.
    expect(kayip).toContain(`hasar dosyası “${COZUM_TR.CONVERTED_TO_LOSS}” olarak kapanır`);
    expect(kayip).toContain("bu bir düğme değildir");
    // Kişi bağı tek kuraldır.
    expect(kayip).toContain("Teslimdeki kitapta üye seçerseniz dosya o üyeye bağlanır");
    // "Bedel belirlendi"nin kişi açısından sonucu açıkça yazar.
    expect(kayip).toContain("“Kütüphaneden ilişiği yoktur” belgesi basılmaz");

    expect(teslim).toContain(`“${LISTEYE_GIRMEYENLER}”`);
    expect(teslim).toContain("“Kutuya dön”");
    expect(teslim).toContain(
      "“Bu şubenin tesliminden doğan … çözülmemiş kayıp/hasar dosyası var; önce dosyayı çözün.”",
    );
    expect(teslim).toContain("yalnız üye türü “Öğretmen” olan kayda birleştirilir");
    expect(teslim).toContain(
      `belge no'ya tıklayınca çıkan kartın “${GERI_ALMA_DOKUMU_ADI}” bölümü`,
    );
    expect(document.body).not.toHaveTextContent(/yükümlülü/i);
  });

  it("masadaki kısayol ve Eser Ayrıntısı bölümü anlatılır", () => {
    renderPage();

    expect(bolumMetni("dolasim")).toContain(
      "Açık ödünçlerin her satırında “Kayıp bildir” kısayolu durur",
    );
    expect(bolumMetni("kayip-hasar")).toContain("(yalnız yönetici kipinde)");
    expect(bolumMetni("katalog")).toContain("kaybolan kitap için kayıp bildirilir");
  });
});

describe("KilavuzPage — İlişik Listesi (F7)", () => {
  it("açık iş tanımı, sıra ve süzgeçler ekrandaki adlarla", () => {
    renderPage();
    const metin = bolumMetni("ilisik");

    expect(metin).toContain(
      "iade edilmemiş ödüncü, geri alınmamış teslimi ya da çözülmemiş kayıp/hasar dosyası",
    );
    expect(metin).toContain("Okuldan ayrılmış kişiler de listededir");
    expect(metin).toContain(
      "önce son sınıflar, sonra okuldan ayrılanlar (ayrılmış ya da Ayrılış Havuzu'nda karar bekleyen), sonra diğerleri",
    );
    // circulation.GRADUATING_LEVEL (4 · 8 · 12).
    expect(metin).toContain("ilkokulda 4, ortaokulda 8, ortaöğretimde 12. sınıf");
    expect(metin).toContain(
      `“Kapsam” (${KAPSAM_SECENEKLERI.map((s) => `“${s.label}”`).join(", ")})`,
    );
    for (const rozet of ["“Son sınıf”", "“Ayrıldı · gg.aa.yyyy”", "“Ayrılış kararı bekliyor”"]) {
      expect(metin).toContain(rozet);
    }
    expect(metin).toContain(`“${COZUM_TR.PRICE_DETERMINED}” durumundaki dosya da açık iştir`);
    expect(metin).toContain("“Sınıf Kitaplıkları” kartında");
    expect(metin).toContain("“önceki ders yılı”");
  });

  it("basılı liste kaynak adı taşımaz ve dipnotludur; belge kartı ekrandaki adla", () => {
    renderPage();
    const metin = bolumMetni("ilisik");

    expect(metin).toContain(`“${ILISIK_LISTESI_ADI}” kartı`);
    expect(metin).toContain("Basılı listede kaynak adı ve okul numarası yoktur");
    expect(ILISIK_DIPNOTU).toBe(LISTE_DIPNOTU);
    expect(metin).toContain(`“${ILISIK_DIPNOTU}” dipnotu`);
    expect(metin).toContain("liste panoya asılmaz");
    expect(metin).toContain(`“${ILISIK_BELGESI_ADI}” kartında “Kişi” alanına`);
    expect(metin).toContain("yalnız açık işi olmayan kişiler seçilebilir");
    expect(metin).toContain("her kişiye bir sayfa basılır");
    // ilisik_belgeleri.NOT_CLEAR_MESSAGE ({sayi} → N); ileti kişi adı yazmaz.
    expect(metin).toContain(
      "“Seçilenlerden N kişinin iade edilmemiş kaynağı, geri alınmamış teslimi ya da çözülmemiş kayıp/hasar dosyası var; belge basılmadı. İlişik listesine bakın.”",
    );
    expect(metin).toContain("ileti kimsenin adını yazmaz");
  });

  it("belge ön koşul değildir; Md. 18/1 alıntısı depodaki metinle birebir", () => {
    renderPage();
    const metin = bolumMetni("ilisik");

    expect(metin).toContain("Bu belge karne ya da diploma almanın ön koşulu değildir");
    expect(metin).toContain("buna dayanak yoktur");
    // docs/mevzuat md. 18/1'in ikinci cümlesi ve üçüncü cümlenin baş ve son parçası;
    // ortası Bakanlığın sistemini andığı için "…" ile atlanır.
    expect(metin).toContain(
      "“Kütüphaneye iadesi yapılmayan kitapların takibi kütüphaneci veya kütüphaneden sorumlu öğretmen tarafından yapılır. Öğrencilerin ve öğretmenlerin okuldan ayrılması sebebiyle … alınan ödünç kitabın kütüphaneye iadesi sağlanır.”",
    );
    expect(metin).toContain("Okul Kütüphaneleri Yönetmeliği, md. 18/1");
    // Belgenin konumu: yerel araç.
    expect(metin).toContain("okulun kütüphane işlerini yürüttüğü yerel araçtaki kayıtlara göre");
  });
});

describe("KilavuzPage — Yıl Sonu ve Yıl Başı (F7)", () => {
  /** Bölümdeki n. numaralı listenin adım adları (kalın başlıklar). */
  function adimAdlari(n: number): Array<string | null> {
    const listeler = document.querySelectorAll("#yil-akislari ol");
    return Array.from(listeler[n]?.querySelectorAll(":scope > li > strong") ?? []).map(
      (s) => s.textContent,
    );
  }

  it("Genel Bakış kartlarının pencereleri ve ekranların adları", () => {
    renderPage();
    const metin = bolumMetni("yil-akislari");

    expect(metin).toContain(`${YIL_SONU_BASLIGI} (Mayıs-Haziran)`);
    expect(metin).toContain(`${YIL_BASI_BASLIGI} (Ağustos-Ekim)`);
    // services/yil_akislari.py: YEAR_END_* ve YEAR_START_* pencereleri.
    expect(metin).toContain(
      "“Yıl Sonu” kartı 1 Mayıs'tan 30 Haziran'a kadar (ders yılı daha geç biterse bitişten iki hafta sonrasına dek)",
    );
    expect(metin).toContain("“Yıl Başı” kartı 15 Ağustos'tan 31 Ekim'e kadar");
    expect(metin).toContain("“Geri” ve “Devam”");
  });

  it("yıl sonunun beş adımı adım rayındaki adlarla; pusula ve belgeler", () => {
    renderPage();
    const metin = bolumMetni("yil-akislari");

    // YilSonuPage ADIMLAR (kaynaktan birebir).
    expect(adimAdlari(0)).toEqual([
      "Son Ödünç Tarihleri.",
      "Kitap Toplama.",
      "Son Sınıflar ve Ayrılanlar.",
      "İlişik ve Belgeler.",
      // F8: yıl sonu raporu adımı rapor ekranına götürür.
      "Yıl Sonu Raporu.",
    ]);
    for (const ad of [
      "“Yıl sonu son ödünç tarihi”",
      "“Son sınıflar için son ödünç tarihi”",
      "“Kaydet”",
      "“… önceki ders yılına ait; bu yıl uygulanmaz.”",
      "“Toplanacak kitaplar”",
      `“${PUSULA_ADI}” kartından`,
      "“Son getirme günü”",
      "“en geç … tarihine kadar”",
      "“Son sınıf şubesi”",
      "“Bütün son sınıflar”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("yeni ödünç verilmez, iade alınmaya devam eder");
    expect(metin).toContain("Yıl sonu pusulası kişinin bütün açık ödünçlerini yazar");
    expect(metin).toContain("tarih kaydedilmez");
    expect(metin).toContain("Tek seferde en çok 150 belge basılır");
  });

  it("yıl başının dört adımı; ekran kayıt yazmaz, ayrı bir yıl geçişi işlemi yoktur", () => {
    renderPage();
    const metin = bolumMetni("yil-akislari");

    // YilBasiPage ADIMLAR (kaynaktan birebir).
    expect(adimAdlari(1)).toEqual([
      "Ders Yılı.",
      "e-Okul Listeleri.",
      "Ayrılış Havuzu.",
      "Kapalı Günler.",
    ]);
    for (const ad of [
      "“Ders Yılları'nı aç”",
      "“Öğrencileri aç”",
      "“Öğretmenler ve Diğer Personel'i aç”",
      "“Ayrılış Havuzu'nu aç”",
      "“Kapalı Günler'i aç”",
      "“Ayrıldı olarak işaretle”",
      "“Aktif kalsın”",
      `“${HOLIDAY_KIND_TR.SCHOOL_BREAK}”`,
      "“Resmî ve dini tatilleri ekle”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("Yıl Başı ekranı kayıt yazmaz");
    expect(metin).toContain("Programda yeni yıla geçiş için ayrı bir işlem yoktur");
    expect(metin).toContain("Aktarım kimseyi ayırmaz ve kimsenin kaydını silmez");
    // Yeni yılda sınıf kitaplıkları: teslim yalnız etkin yılın şubesine.
    expect(metin).toContain("“önceki ders yılı” notuyla görünür");
    expect(metin).toContain("yeni şubeye yeniden teslim edin");
  });
});

describe("KilavuzPage — F7 ekran bağlantıları", () => {
  it("teslim, kayıp, ilişik ve yıl akışı ekranlarına sabit adreslerle bağlanılır", () => {
    renderPage();

    const hedef = (ad: string) =>
      screen.getAllByRole("link", { name: ad }).map((a) => a.getAttribute("href"));

    expect(hedef(`Dolaşım Masası → ${TESLIMLER_BASLIGI}`)).toEqual([TESLIMLER_ADRESI]);
    // TeslimlerPage TAB_KEYS ("yeni", "geri-alma").
    expect(hedef("Teslimler → Yeni Teslim")).toEqual([`${TESLIMLER_ADRESI}?tab=yeni`]);
    expect(hedef("Teslimler → Geri Alma")).toEqual([`${TESLIMLER_ADRESI}?tab=geri-alma`]);
    expect(hedef(`Dolaşım Masası → ${KAYIP_HASAR_BASLIGI}`)).toEqual([KAYIP_HASAR_ADRESI]);
    // "İlişik Listesi" iki bağlantıdır: "Bu kılavuzda" çapası ve ekran bağlantısı.
    expect(new Set(hedef(ILISIK_LISTESI_BASLIGI))).toEqual(
      new Set(["#ilisik", ILISIK_LISTESI_ADRESI]),
    );
    expect(hedef(YIL_SONU_BASLIGI)).toEqual([YIL_SONU_ADRESI]);
    expect(hedef(YIL_BASI_BASLIGI)).toEqual([YIL_BASI_ADRESI]);
  });
});

// ---------------------------------------------------------------------------
// F8: Ayıklama ve Nadir Eserler, Yıl Sonu Raporu. Adlar `modules/ayiklama`
// sabitlerinden; Md. 12/1 ve 12/2 alıntıları docs/mevzuat/meb-okul-kutuphaneleri-
// yonetmeligi.md'den birebir (sunucu tarafı `test_komisyon_belgeleri.py` ve
// `test_yil_raporu_belgesi.py` aynı alıntıları depodaki metinle sınar).
// ---------------------------------------------------------------------------
describe("KilavuzPage — Ayıklama ve Nadir Eserler (F8)", () => {
  it("ayıklama ≠ kayıttan düşme; gerekçeden TMY yoluna, ekrandaki adlarla", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    expect(metin).toContain("Ayıklama Seçim ve Ayıklama Komisyonunun kararıdır");
    expect(metin).toContain("kayıttan düşme ve devir ise harcama yetkilisinin onayıyla");
    for (const gerekce of Object.values(GEREKCE_TR)) expect(metin).toContain(gerekce);
    for (const yol of Object.values(TMY_YOLU_TR)) expect(metin).toContain(yol);
    for (const durum of ["Komisyon ayıklanmasına karar vermedi", "Onaylanmadı"]) {
      expect(Object.values(KALEM_DURUMU_TR)).toContain(durum);
      expect(metin).toContain(`“${durum}”`);
    }
    // 10/1-b gerekçeli kalem hurdaya ayrılamaz; devir yalnız düzeye uygunsuzlukla.
    expect(metin).toContain("Devir yalnız bu gerekçeyle yapılır");
    expect(metin).toContain("hurdaya ayrılamaz: ölçüt listesinde bu seçenek yoktur");
    expect(metin).toContain("Md. 10/4'e aykırı kitap okul kütüphanelerinde");
    expect(metin).not.toContain("hiçbir kütüphanede");
    expect(metin).toContain("program bu gerekçedeki kaynağı devir yoluna bağlamaz");
  });

  it("teklifin adımları ve düğmeleri ekrandakiyle aynıdır; uygulama geri alınamaz", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");
    const adimlar = Array.from(document.querySelectorAll("#ayiklama ol > li > strong")).map(
      (s) => s.textContent,
    );
    expect(adimlar).toEqual([
      "Taslak.",
      "Komisyona sunuldu.",
      "Komisyon kararı.",
      "Harcama yetkilisi onayı.",
      "Uygulandı.",
    ]);
    for (const ad of [
      "“Yeni teklif”",
      "“Kalem ekle”",
      "“Aday Nüshalar”",
      "“Kütüphane etiketleri”",
      "“Düzenle”",
      "“Çıkar”",
      "“Komisyona sun”",
      "“Komisyon kararını bağla”",
      "“Harcama yetkilisinin onayını işle”",
      "“Komisyon üyeleri”",
      "“İmha kararı verildi”",
      "“Uygula”",
      "“Teklifi geri çek”",
      "“İptal et”",
      `“${KAYIP_ONERILERI_BASLIGI}”`,
      `“${HASAR_ONERILERI_BASLIGI}”`,
      "“Ayıklama Belgeleri”",
      "“Excel'i indir”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("İşlem geri alınamaz.");
    expect(metin).toContain("en az üç kişidir (TMY md. 28/1)");
    // 10/1-e yorumu kesin hüküm değil, harcama yetkilisinin takdiridir.
    expect(metin).toContain("komisyon kurulmadan onaylayabilir (TMY md. 10/1-e)");
    expect(metin).not.toContain("komisyon gerekmez");
    expect(metin).toContain("biri işin uzmanıdır, onu ilk satıra yazın");
    expect(metin).toContain("(TMY md. 28/8)");
    expect(metin).toContain("İmha kararı kalem kalem verilir");
    expect(metin).toContain("için yeni komisyon kararı gerekir");
    expect(metin).toContain(
      "Kayıp ve Hasar'da kayıttan düşme önerisiyle kapanan dosyaların kitapları da ayıklamaya konmaz",
    );
  });

  it("belgeler TMY yoluna göre; imha yalnız imha tutanağı bağlamında; TKYS hazırlığı", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    for (const belge of [
      "Ayıklama teklif listesi",
      "Ayıklama tutanağı",
      "Kayıttan düşme teklif listesi",
      "İmha tutanağı",
      "Devir listesi",
    ]) {
      expect(metin).toContain(belge);
    }
    expect(metin).toContain("TKYS'de düzenlenir");
    // "imha" geçen her cümle imha kararı ya da imha tutanağıyla (TMY 28/5) ilgilidir.
    const cumleler = metin.split(/(?<=\.)\s(?=\p{Lu})/u).filter((c) => /imha/iu.test(c));
    expect(cumleler.length).toBeGreaterThan(0);
    for (const cumle of cumleler) {
      expect(cumle).toMatch(/İmha tutanağı|imha kararı|İmha kararı|imhaya karar|28\/5/u);
    }
    expect(bolumMetni("yil-sonu-raporu")).not.toMatch(/imha/iu);
  });

  it("nadir eserler: Md. 12/2 birebir, liste ve gönderim ekrandaki adlarla", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    expect(metin).toContain(
      "“Seçim ve Ayıklama Komisyonu tarafından tespit edilen el yazmaları ve nadir eserler listesi, Genel Müdürlüğe gönderilir.”",
    );
    expect(metin).toContain("Destek Hizmetleri Genel Müdürlüğüdür (md. 4/1-c)");
    for (const ad of [
      "“El yazması / nadir eser”",
      "“Yeni liste”",
      "“Bildirilmemiş Nadir Eserler”",
      "“Seçilenleri listeye ekle”",
      "“Kararı kaydet”",
      "“Gönderildi olarak işaretle”",
      "“Nadir Eser İşaretli Nüshalar”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("gönderilmiş liste değişmez");
    // Md. 12/1 alıntısı (ortası "…" ile).
    expect(metin).toContain(
      "10 uncu maddenin birinci fıkrasının (b) bendine uygun olmayan kaynaklar uygun okullara veya kurumlara devredilir.”",
    );
  });

  it("katalog bölümünde 'sonraki sürüm' sözü kalmaz; bağış kararının F8 kuralları", () => {
    renderPage();
    const metin = bolumMetni("katalog");

    // Nadir eser, ayıklama kararı ve kayıttan düşme artık işler (saklama taraması hâlâ
    // sonraki sürümdedir; o cümle kalır).
    for (const eskiCumle of [
      "(sonraki sürüm)",
      "ayıklama kararı sonraki sürümde",
      "kayıttan düşme yolu sonraki sürümlerde",
    ]) {
      expect(metin).not.toContain(eskiCumle);
    }
    expect(bolumMetni("kayip-hasar")).not.toContain("ayrı bir işlemdir ve sonraki sürümlerde");
    expect(metin).toContain("“Katalogdaki karşılığı”");
    expect(metin).toContain("“Yeni eser aç”");
    expect(metin).toContain("“… eserine nüsha ekle”");
    expect(metin).toContain("komisyon kararının tarihi ile bağışın geliş tarihinden geç olanı");
    expect(metin).toContain("“Kabul / Ret” sütunu");
  });

  it("25.09.2026 kullanıcı kararları: bağış sonucu, bedelden sonra bulunma, öneriler sayımda", () => {
    const { container } = renderPage();
    const katalog = bolumMetni("katalog");
    const kayip = bolumMetni("kayip-hasar");
    const ayiklama = bolumMetni("ayiklama");

    // F8 ekleri 13: karardan sonraki döküm; TMY'de "bağış kabul tutanağı" yoktur (tek olumsuz
    // cümle), VİF'i taşınır kayıt yetkilisi düzenler (TMY 16/1), değer 13/2-c'dedir.
    expect(katalog).toContain(`${BAGIS_SONUCU_BELGESI} basılır`);
    expect(katalog).toContain(
      "Taşınır Mal Yönetmeliği'nde “bağış kabul tutanağı” diye bir belge yoktur",
    );
    expect(sayfaMetni(container).match(/bağış kabul tutanağı/giu) ?? []).toHaveLength(1);
    expect(katalog).toContain("(Taşınır Mal Yönetmeliği md. 16/1)");
    expect(katalog).toContain("(Taşınır Mal Yönetmeliği md. 13/2-c)");
    expect(BAGIS_BIRIM_FIYAT_YARDIMI).toContain("(Taşınır Mal Yönetmeliği md. 13/2-c)");

    // F8 ekleri 14: bedel teslim alındıktan sonra bulunma; kayıttan düşülmüşse sayım fazlası.
    expect(kayip).toContain(`“${COZUM_TR.FOUND_AFTER_PRICE}” (yalnız kayıp dosyasında)`);
    expect(kayip).toContain(`“${BEDEL_IADESI_NOTU}”`);
    expect(kayip).toContain("“Sayım fazlası (kayda giriş)” yoluyla açılan bir edinimle");

    // F8 ekleri 34: kayıp ve hasar önerisi ayıklamaya konmaz, sayımda düşülür.
    expect(kayip).not.toContain("hasarlı kitap Ayıklama ekranında teklife konur");
    expect(kayip).toContain("Kayıp ve hasarlı kitap ayıklamaya konmaz");
    expect(ayiklama).not.toContain("Yalnız kayıttan düşme önerileri");
    expect(ayiklama).toContain("Seçim ve Ayıklama Komisyonu kararı gerekmez");
  });
});

describe("KilavuzPage — Yıl Sonu Raporu (F8)", () => {
  it("Md. 12/1 birebir; adımlar ekrandaki adlarla; rapor kişisizdir", () => {
    renderPage();
    const metin = bolumMetni("yil-sonu-raporu");

    expect(metin).toContain(
      "“Her ders yılı sonunda kütüphane kaynakları, kütüphaneci veya görevlendirilen öğretmen tarafından gözden geçirilir ve tespit edilen hususlar raporla okul müdürlüğüne bildirilir.”",
    );
    for (const ad of [
      "“Raporu hazırla”",
      "“Sayı”",
      "“Tarih”",
      "“Tespit edilen hususlar”",
      "“Kaydet”",
      "“Önizle”",
      "“OKUL MÜDÜRLÜĞÜNE”",
      "“Raporu sonlandır”",
      "“Sonlandırmayı geri al”",
      "“TASLAK”",
      "“Çok okunanlar için en az üye sayısı”",
    ]) {
      expect(metin).toContain(ad);
    }
    // Ekranın yardım metniyle aynı uyarı.
    expect(TESPIT_YARDIMI).toContain("Kişi adı yazmayın.");
    expect(metin).toContain("kişi adı yazmayın");
    expect(metin).toContain("Rapor kişisizdir");
    expect(metin).toContain("imza satırında ad basılmaz");
    // Dönem: yaz ayıklaması rapora ancak yeni ders yılı tanımlandıktan sonra sonlandırılırsa girer.
    expect(metin).not.toContain("yaz aylarında yapılan ayıklama da rapora girer");
    expect(metin).toContain("raporu yeni ders yılı tanımlandıktan sonra sonlandırın");
    // 25.09.2026 kullanıcı kararı (F8 ekleri 35 — a): ekranın uyarısı kılavuzda birebir (ilk
    // iki cümlesi; son cümle "…" ile atlanır).
    const ilkIki = YAZ_DONEMI_UYARISI.slice(0, YAZ_DONEMI_UYARISI.indexOf(" Gerekirse"));
    expect(ilkIki).toMatch(/bu rapora girmez\.$/u);
    expect(metin).toContain(`“${ilkIki} …”`);
    expect(metin).toContain("“kayıt içi giriş”");
    expect(metin).toContain("bir grup daha gizlenir");
  });

  it("F8 ekranlarına sabit adreslerle bağlanılır", () => {
    renderPage();
    const hedef = (ad: string) =>
      screen.getAllByRole("link", { name: ad }).map((a) => a.getAttribute("href"));

    expect(hedef(AYIKLAMA_BASLIGI)).toEqual([AYIKLAMA_ADRESI]);
    expect(hedef(NADIR_ESERLER_BASLIGI)).toEqual([NADIR_ESERLER_ADRESI]);
    expect(new Set(hedef(YIL_SONU_RAPORU_BASLIGI))).toEqual(
      new Set(["#yil-sonu-raporu", YIL_SONU_RAPORU_ADRESI]),
    );
  });
});

// ---------------------------------------------------------------------------
// F8 kılavuz ve sözlük kolu: ayıklama ≠ kayıttan düşme, Seçim ve Ayıklama Komisyonu ve
// kararları, TMY yollarının sade anlatımı, imha yalnız 28/5 bağlamında, nadir eserlerin
// adımları, yıl sonu raporunun kişisizliği. Mevzuat alıntıları ve alıntısız atıfların
// fıkra metni sunucu tarafında `test_ayiklama_kilavuz_metinleri.py` ile depodaki metinden
// sınanır; burada ekranın adları ve kılavuzun kurgusu kilitlenir.
// ---------------------------------------------------------------------------
describe("KilavuzPage — Seçim ve Ayıklama Komisyonu ve TMY yolları (F8)", () => {
  it("bölümün kurgusu: ayıklama ≠ kayıttan düşme önce, komisyon sonra, yollar ondan sonra", () => {
    renderPage();
    const altBasliklar = Array.from(document.querySelectorAll("#ayiklama h3")).map(
      (h) => h.textContent,
    );
    expect(altBasliklar).toEqual([
      "Ayıklama kayıttan düşme değildir",
      "Seçim ve Ayıklama Komisyonu ve kararları",
      "Gerekçe ve Taşınır Mal Yönetmeliği yolu",
      "Teklif adım adım",
      "Ayıklamaya konamayan kitaplar",
      "Ayıklama belgeleri",
      "El yazması ve nadir eserler",
    ]);
  });

  it("ayıklama kayıttan düşme değildir: iki ayrı adım, nüsha yalnız uygulamada değişir", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    expect(metin).toContain(
      "Programda bu yüzden iki ayrı adım vardır: “Komisyon kararı” ve “Harcama yetkilisi onayı”.",
    );
    expect(metin).toContain("(Taşınır Mal Yönetmeliği md. 10/1-e, 28/4)");
    expect(metin).toContain("Nüshanın durumu yalnız teklif uygulanınca değişir");
    expect(metin).toContain("Ayıklanan ya da devredilen nüsha silinmez");
  });

  it("komisyon: Md. 10/1 birebir, bileşim yalnız bende gönderilir, üç karar türü ekrandaki adla", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    expect(metin).toContain(
      "“Kütüphane kaynaklarının tespiti ve seçimi için Seçim ve Ayıklama Komisyonu, ilçe millî eğitim şube müdürü başkanlığında kurulur. Şube müdürünün katılamadığı durumlarda okul müdürü komisyona başkanlık eder.”",
    );
    expect(metin).toContain("Yönetmeliğin 4. maddesinin (ı) bendinde sayılır");
    for (const ad of ["“Karar ekle”", "“Başkan adı”", "“Katılımcılar”", "“Karar türü”"]) {
      expect(metin).toContain(ad);
    }
    for (const tur of Object.values(COMMISSION_DECISION_TYPE_TR)) {
      expect(metin).toContain(`${tur}:`);
    }
    // Bağış kararı ve toplu kataloglama: özet burada, adımlar Katalog bölümünde.
    expect(metin).toContain("“Komisyon kararını uygula”");
    expect(metin).toContain("“Kararı uygula”");
    expect(metin).toContain("kabul edilen kitaplar tek işlemde kataloglanır");
    expect(metin).toContain("katalogda zaten bulunan kitabın nüshaları var olan esere eklenir");
    expect(metin).toContain("Adımlar Katalog bölümünün “Edinimler ve bağışlar” kısmındadır.");
    expect(bolumMetni("katalog")).toContain(
      "Komisyonun başkanlığı ve karar türlerinin neye bağlandığı Ayıklama ve Nadir Eserler bölümündedir.",
    );
    // Kataloglama taşınır kaydı değildir; hurdaya ayırma komisyonu ayrı komisyondur.
    expect(metin).toContain("Kataloglama taşınır kaydı değildir");
    expect(metin).toContain("(Taşınır Mal Yönetmeliği md. 16/1)");
    expect(metin).toContain(
      "Hurdaya ayırmada kaynağı değerlendiren komisyon da Seçim ve Ayıklama Komisyonu değildir",
    );
  });

  it("TMY yolları sade dille ve fıkra atfıyla; devir yalnız düzeye uygunsuzlukta", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    for (const atif of [
      "(TMY md. 5/8)",
      "(TMY md. 27/3)",
      "(TMY md. 28/1, 28/4)",
      "(TMY md. 24)",
      "(TMY md. 28/5)",
      "(md. 10/1-b)",
    ]) {
      expect(metin).toContain(atif);
    }
    expect(metin).toContain("Olağan kullanımdan doğan yıpranmada kimseden sorumluluk aranmaz");
    expect(metin).toContain("biri işin uzmanı en az üç kişilik bir komisyon");
    expect(metin).toContain("aynı kamu idaresinin başka bir harcama birimine devirdir");
    expect(metin).toContain("kayıttan düşülmez, devredilir");
    expect(metin).toContain(
      "program bu kaynağı kurumun düzeyine uygun olmayan kaynakla aynı gerekçede toplar",
    );
  });

  it("imha: ayıklanan kitap kendiliğinden imha edilmez; kılavuzun başka bölümü imha demez", () => {
    const { container } = renderPage();
    const metin = bolumMetni("ayiklama");

    expect(metin).toContain("Ayıklanan kitap kendiliğinden imha edilmez");
    const imha = /[iİ]mha/gu;
    const tumu = sayfaMetni(container).match(imha) ?? [];
    const bolumde = metin.match(imha) ?? [];
    expect(bolumde.length).toBeGreaterThan(0);
    expect(tumu).toHaveLength(bolumde.length);
  });

  it("onay ve uygulama ekrandaki alan ve kutu adlarıyla", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    for (const ad of [
      "“Harcama yetkilisinin adı”",
      "“Onay tarihi”",
      "“Harcama yetkilisinin onayını ve belgelerin imzalandığını denetledim.”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("kutu yalnız hurdaya ayırma kalemi olan teklifte çıkar");
    // Sayım ekranı henüz yok: kayıp nüshanın kaydını sayım kapatır, iki bölüm de bunu söyler.
    expect(metin).toContain("sayım ekranı sonraki bir sürümde gelecek");
    expect(bolumMetni("kayip-hasar")).toContain("sayım ekranı sonraki bir sürümde gelecek");
  });

  it("nadir eserler: dört adım ekrandaki adlarla; nadir eser ayıklanmaz", () => {
    renderPage();
    const metin = bolumMetni("ayiklama");

    expect(metin).toContain("El yazması ve nadir eser ayıklanmaz");
    for (const ad of [
      "“Listeler”",
      "“Çıkar”",
      "“Komisyon kararı”",
      "“Önizle”",
      "“PDF'i indir”",
      "“Genel Müdürlüğe Gönderim”",
      "“Gönderim tarihi”",
      "“Bildirildi” / “Bildirilmedi”",
      "“Yalnız bildirilmemişler”",
    ]) {
      expect(metin).toContain(ad);
    }
    expect(metin).toContain("Bu işaret geri alınmaz.");
    expect(metin).toContain("Genel Müdürlüğe bildirilmemiş nüshanın işareti");
    expect(metin).toContain("kararı bağlanmış listedeyse önce nüshayı listeden çıkarın");
    expect(metin).toContain("Bir listedeki nüsha silinemez.");
  });
});

describe("KilavuzPage — Yıl Sonu Raporu kişisizdir (F8)", () => {
  it("Uygulama Kılavuzu 2.4 birebir; kişisel veri ve adlı kırılım yok", () => {
    renderPage();
    const metin = bolumMetni("yil-sonu-raporu");

    expect(metin).toContain(
      "“Her eğitim öğretim yılı sonunda kütüphanedeki kitap durumu, kazandırılan ve ayıklanan kaynaklar okul yönetimine raporlanır.”",
    );
    expect(metin).toContain("Uygulama Kılavuzu, 2.4");
    expect(metin).toContain("kişisel veri içermez");
    expect(metin).toContain("şube ile konu kırılımı yapmaz");
    expect(metin).toContain("öğrenci, öğretmen ya da personel adı yazmayın");
  });
});
