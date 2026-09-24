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
// F4 bölümü: Etiketler (Hızlı Kayıt'ın ardında). Sekme, düğme ve seçenek adları
// ekran sabitlerinden (ETIKETLER_SEKMELERI, ETIKET_YOLLARI, ETIKET_ICERIGI_TR,
// BASIM_SIRASI_TR, PARTI_DURUMU_TR) doğrulanır; sabiti olmayan düğme ve alan
// adları ekranın kaynağından (EtiketKuyrugu, etiketOrtak, BasimGecmisi,
// BosBarkodPaneli, DogrulamaOkutmasi, SablonlarPaneli) birebir kopyalandı.
// Kilitlenenler: satın alma notu (QR kararı tabakayı belirler), kalibrasyon
// adımları ve işaret kuralı, basım sırası, "PDF'i almak basıldı saymaz" ve geri
// alma, doğrulama okutması, önce etiket yolunun SIRALI adımları, bozulan ve
// kaybolan etiketin iki ayrı yolu, sırtı dar kitap ve koruyucu bant önerisi.
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

import { DOSYA_KAYIP_BASLIGI } from "../guvenlik/metinler";
import {
  GOREVLI_DOGRULAMA_BITIR,
  GOREVLI_DOGRULAMA_DUGMESI,
  GOREVLI_EKRANI_BASLIGI,
} from "../kip/GorevliEkrani";
import { GOREVLI_KISAYOLU } from "../kip/KipGostergesi";
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
  KATALOG_SABLONU_BELGE_ADI,
  KUNYE_LISTESI_BELGE_ADI,
  RESOURCE_TYPE_TR,
  WORK_ORDER_TR,
} from "../kutuphane/api";
import { HOLIDAY_KIND_TR, MEMBER_KIND_TR, SCHOOL_LEVEL_TR } from "../okul/api";
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
  "Katalog Excel Şablonu",
  "İçe Aktarma",
  "Yedek ve Güvenlik Dosyası",
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
    // İleti GELECEK ZAMANDADIR: dolaşım sonraki fazda gelir, bu sürümde hiçbir
    // ekran bu iletiyi üretmez (şimdiki zaman kullanıcıyı okuyucusu bozuk sanır).
    expect(metin).toContain("“Bu ISBN barkodu. Kitabın kütüphane etiketini okutun.” diyecek");
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
    // Yedek AÇILIŞTA alınır; tepside açık kalan programda gün değişimi kapısı
    // henüz yoktur (desktop/main.py: daily_backup yalnız açılış zincirinde).
    expect(metin).toContain("Yedek açılışa bağlıdır");
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

  it("Ağ Kataloğu: kişisel veri göstermez, varsayılan kapalı, BTR'nin bilgisi alınır", () => {
    renderPage();
    const metin = bolumMetni("ag-katalogu");

    expect(metin).toContain("Kişisel veri göstermez");
    expect(metin).toContain("Varsayılan olarak kapalıdır");
    // "İzin" değil "bilgi" (sözlük: BTR notu bir bilgi notudur).
    expect(metin).toContain("bilgisi alınır");
    expect(metin).not.toMatch(/izni(ni)? alınır/);
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
      /\bceza\b/i,
      /uzatma/i,
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
    ]) {
      expect(metin).not.toMatch(yasak);
    }
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
