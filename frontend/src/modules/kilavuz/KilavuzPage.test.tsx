// Kullanım Kılavuzu testleri. Bölümler özelliklerle birlikte eklendikçe her
// bölümün çekirdek metni burada kilitlenir — özellik kılavuzda ANLATILMADAN
// sürüme girmesin (tasarım §14.1 "kılavuz bölümü" iş kalemi).
//
// F1 bölümleri (iş sırasıyla): ilk kurulum, başlangıç yol haritası, görevli ve
// yönetici kipi, kişiler ve e-Okul listeleri, kapalı günler, katalog Excel
// şablonu, yedek ve güvenlik dosyası, Ağ Kataloğu.
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
import { GOREVLI_EKRANI_BASLIGI } from "../kip/GorevliEkrani";
import { GOREVLI_KISAYOLU } from "../kip/KipGostergesi";
import { KATALOG_SABLONU_BELGE_ADI } from "../kutuphane/api";
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
  "Katalog Excel Şablonu",
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
    expect(hedef("Ayarlar → Okul Bilgileri")).toEqual(["/ayarlar?tab=okul"]);
    expect(hedef("Ayarlar → Şubeler")).toEqual(["/ayarlar?tab=subeler"]);
    expect(hedef("Kişiler")).toEqual(["/kisiler"]);
    expect(new Set(hedef("Genel Bakış"))).toEqual(new Set(["/"]));
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
    ]) {
      expect(metin).not.toMatch(yasak);
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
