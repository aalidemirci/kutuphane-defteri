// Kullanım Kılavuzu — statik içerik, çevrimdışı. Kabuk ve bileşen deseni KS'nin
// kılavuzundan (Adim/Ipucu/Mevzuat/Ekran); içerik yeniden yazıldı (tasarım §12):
// her fazın "kılavuz bölümü" iş kalemiyle (§14.1) bölümler özelliklerle birlikte
// eklenir. Kalıp HakkindaPage'den: max-w-4xl kap, üstbaşlık üçlüsü, bölüm başına
// Card + 44px ikon rozeti. Ekranlara `Link` ile atlanır; sayfa içi bağlantılar
// yalnız "Bu kılavuzda" listesindeki bölüm çapalarıdır.
//
// F1 bölümleri, kullanıcının iş sırasıyla: ilk kurulum (parola + kurtarma anahtarı,
// okul bilgileri, ders yılı ve kapalı günler) → başlangıç yol haritası → görevli ve
// yönetici kipi → kişiler ve e-Okul mutabakatı → kapalı günler ve iade tarihi →
// katalog Excel şablonu → yedek ve güvenlik dosyası → Ağ Kataloğu (BTR görüşmesi).
//
// F2 bölümü "Katalog", kapalı günlerle Excel şablonunun arasına girer: eser/nüsha
// ayrımı, bölümler, sınıflama kodu ve yer numarası, ISBN, barkod ve kayıt no,
// ödünç verilmeyen kaynaklar, edinim yolları ve bağış ön kaydı, Kütüphane
// Politikası.
//
// F3 iki bölüm ekler ve sıra SAHADAKİ iş sırasıdır (tasarım §8.1, S8 cevabı):
// "Hızlı Kayıt" kataloğun HEMEN ardından gelir, çünkü okulda hazır liste yoktur
// ve katalog kitap kitap kurulur; "Katalog Excel Şablonu" ile "İçe Aktarma" ondan
// sonra, liste yolu olarak anlatılır. Yapay zekâ köprüsü İçe Aktarma bölümünün
// SONUNDA ve uyarılarıyla durur: okulun kitap listesi dışarı çıkar, asıl yol
// Excel'dir, künye eksiği için ISBN yolu daha güvenlidir (§8.2 U13 eki).
//
// İki geçiş yolu ("önce liste" / "önce etiket", §8.1 tablosu) Hızlı Kayıt
// bölümünün BAŞINDA karşılaştırılır: kullanıcı hangi yolu izleyeceğine, ekranlar
// anlatılmadan önce karar verir. Yolların adı kullanıcı dilindedir; "yöntem A/B"
// iç adlandırması kılavuza girmez.
//
// F4 bölümü "Etiketler" Hızlı Kayıt'ın hemen ardından gelir: önce etiket yolu
// (okulun asıl yolu) boş barkod etiketleriyle başlar, liste yolu da içe
// aktarmadan sonra etikete döner. Bölümün sırası kullanıcının iş sırasıdır:
// etiket türleri → nereye yapıştırılır (sırtı dar kitapta ön kapak, koruyucu
// bant — §7.2, SU-13) → tabaka seçimi ve satın alma (QR kararı tabakayı
// belirler, satın alma ondan sonra — SU-12, S4) → kalibrasyon adım adım
// (kalibrasyon sayfasının kendi talimatıyla aynı dil: sağa ve aşağı artı) →
// basım kuyruğu ve basım sırası (D20) → "PDF'i almak basıldı saymaz" ve geri
// alma (D10) → yapıştırma ve doğrulama okutması → önce etiket yolu adım adım
// (ayır → bas → yapıştır → Hızlı Kayıt'ta künye + etiket → sırt → iptal) →
// etiketi olmayan kitap. Kâğıt ölçüsünün kısa adı yazılmaz (iç kod denetimi
// onu kod sanar); ölçüler milimetreyle yazılır.
//
// Sırtı dar kitapta köşe (üst/alt) bilinçli olarak dayatılmaz: tasarım yalnız
// "ön kapağa" der; kılavuz sırta yakın köşeyi ve bütün ince kitaplarda AYNI
// köşeyi önerir. Bozulan boş etiket için iki ayrı yol vardır ve kılavuz ikisini
// ayırır: etiket eldeyse aynı numaranın yenisi basılır (bozuğu atılır),
// kaybolduysa numara iptal edilir — kaybolan etiket bir kitapta çıkabilir.
//
// Metin kuralları (docs/sozluk.md — bağlayıcı): düğme, sekme ve alan adları
// ekrandaki metinle BİREBİR yazılır (depodan doğrulandı; test bir kısmını ekran
// sabitlerinden kilitler). İç kodlar (F1, U5, E14…) geçmez. Program kendini
// "yerel araç" diye tanıtır. Kaydırılmış iade tarihi Yönetmelik hükmü gibi
// sunulmaz: hafta sonu/tatil kaydırması TBK 93'e KIYASEN, ara tatil/yarıyıl
// kaydırması okulun tercihidir (CLAUDE.md §2-6); idari izin/diğer günlerindeki
// kaydırma dayanaksız program kuralıdır, TBK 93 maddesinin altında anılmaz.
//
// F5 iki bölüm yazar: "Tepsi, Çıkış ve Gün Değişimi" (yedek bölümünün ardında —
// pencerenin çarpısı gizler, Çık görevli kipinde yönetici parolası ister ve
// tepsiden seçilince onay sormaz, tepsi menüsü kipe göre değişir, kurucu programı
// kendisi kapatır, oturum açılınca başlatma, program günlerce açık kalsa da gün
// değişince yedek alınır ve adres denetlenir, Ağ Kataloğu açıkken yalnız boşta
// uyku engellenir) ve "Ağ Kataloğu". İkincisinin sırası kullanıcının sorusunun
// sırasıdır: ne olduğu → neyi gösterip neyi ASLA göstermediği (kişisel veri yok,
// "Ödünçte" görünür ama kimde olduğu görünmez) → BTR'yle yapılacaklar (ağ keşfi,
// sabit adres, gerekirse PYS talebi, bilgi notu, okul ağından erişim sınaması —
// hem kataloğun kendisi hem programın iki dış adresi) → açma adımları (ekrandaki
// "Ağ Kataloğunu Açmadan Önce" kartının adımlarıyla aynı adlar) → Ağ Doktoru'nun
// beş kartı → afiş ve yer imleri (ETAP her öğretmene ayrı hesap açtığı için
// kullanıcı başına yer imi yetmez; politika dosyası) → tahta kipi → adres
// değişirse → port → Pardus.
//
// Ad kaynakları: tepsi menüsü `desktop/tray.py` sabitleri, durum satırı
// `desktop/katalog_kontrol.py::tepsi_satiri`, adres uyarısı `ip_denetle`,
// kurucu görevleri `packaging/windows/kutuphane-defteri.iss` [Tasks], Ağ
// Doktoru ve Ayarlar → Ağ Kataloğu ekranların kaynağı (`modules/agkatalogu`),
// kataloğun kendi sayfa adları `backend/katalog/sablonlar`. Tepsiden seçilen Çık
// yönetici kipinde ve kilitliyken ONAY SORMADAN kapatır
// (`tepsi_eylemleri.quit = request_quit`); üst çubuktaki Çık sorar. Çok okunanlar
// listesi bu sürümde boştur (ödünç verisi yok; hesap sonraki fazda) ve kılavuz
// bunu söyler. "rezervasyon" sözcüğü sözlükte yasak olduğu için DHCP'deki sabit
// adres "sabit adres ayırma" diye anlatılır.
//
// Mevzuat atıfları yalnız `docs/mevzuat/`'taki tam metinlerden alınır; alıntılar
// BİREBİR, madde numarası uydurulmaz: Yönerge 11/6, 11/8, 11/12, 11/22 (yalnız
// ilk cümlesi) ve 11/23 (meb-bilgi-ve-sistem-guvenligi-yonergesi.md; atıf
// haritası docs/mevzuat/BENIOKU.md §3.3), Yönetmelik 10/3, 10/5, 11/1, 14/1-a,
// 16/1 ve 18/1 (meb-okul-kutuphaneleri-yonetmeligi.md), TBK 93
// (6098-…-md92-93.md).

import { useEffect } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { YONERGE, YONETMELIK } from "../../lib/mevzuat";

import Card from "../../ui/Card";
import Icon from "../../ui/Icon";

/** Bölümler (çapa → başlık + ikon), sayfadaki sırasıyla. Başlıklar Başlık Düzenindedir. */
const BOLUMLER = {
  "ilk-kurulum": { baslik: "İlk Kurulum", ikon: "checklist" },
  "yol-haritasi": { baslik: "Başlangıç Yol Haritası", ikon: "flag" },
  kipler: { baslik: "Görevli Kipi ve Yönetici Kipi", ikon: "admin_panel_settings" },
  kisiler: { baslik: "Kişiler ve e-Okul Listeleri", ikon: "group" },
  "kapali-gunler": { baslik: "Kapalı Günler", ikon: "event_busy" },
  katalog: { baslik: "Katalog", ikon: "menu_book" },
  "hizli-kayit": { baslik: "Hızlı Kayıt", ikon: "bolt" },
  etiketler: { baslik: "Etiketler", ikon: "label" },
  "katalog-sablonu": { baslik: "Katalog Excel Şablonu", ikon: "table_view" },
  "ice-aktarma": { baslik: "İçe Aktarma", ikon: "upload_file" },
  yedek: { baslik: "Yedek ve Güvenlik Dosyası", ikon: "backup" },
  "tepsi-ve-cikis": { baslik: "Tepsi, Çıkış ve Gün Değişimi", ikon: "power_settings_new" },
  "ag-katalogu": { baslik: "Ağ Kataloğu", ikon: "lan" },
} as const;

type BolumId = keyof typeof BOLUMLER;

/** "Bu kılavuzda" listesi — bölüm çapaları ve başlıklar tek kaynaktan (test de okur). */
export const KILAVUZ_BOLUMLERI: ReadonlyArray<{ id: BolumId; baslik: string }> = (
  Object.keys(BOLUMLER) as BolumId[]
).map((id) => ({ id, baslik: BOLUMLER[id].baslik }));

/**
 * Kılavuz bölümü — ikon rozeti + başlık + içerik. `scroll-mt-24`: "Bu kılavuzda"
 * bağlantısıyla gelindiğinde başlık yapışkan üst çubuğun altında kalmasın.
 */
function Bolum({ id, children }: { id: BolumId; children: ReactNode }) {
  const tanim = BOLUMLER[id];
  return (
    <section id={id} aria-labelledby={`${id}-baslik`} className="scroll-mt-24">
      <Card className="p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-shape-md bg-primary-container text-on-primary-container">
            <Icon name={tanim.ikon} size="xl" />
          </span>
          <div className="min-w-0 flex-1 space-y-3 text-body-medium text-on-surface-variant">
            <h2 id={`${id}-baslik`} className="text-title-large font-semibold text-on-surface">
              {tanim.baslik}
            </h2>
            {children}
          </div>
        </div>
      </Card>
    </section>
  );
}

/** Bölüm içi alt başlık. */
function AltBaslik({ children }: { children: ReactNode }) {
  return <h3 className="pt-1 text-title-small font-semibold text-on-surface">{children}</h3>;
}

/** Vurgulu ipucu kutusu (tertiary yüzey — gövde metninden ayrışır). */
function Ipucu({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-shape-md bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
      <Icon name="lightbulb" size="lg" className="mt-0.5 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Mevzuat alıntısı — birebir metin + kaynak adı ve madde (docs/mevzuat'tan). */
function Mevzuat({ kaynak, children }: { kaynak: string; children: ReactNode }) {
  return (
    <figure className="rounded-shape-md border-l-4 border-outline bg-surface-container px-4 py-3">
      <blockquote className="text-body-medium text-on-surface">{children}</blockquote>
      <figcaption className="mt-1 text-body-small text-on-surface-variant">{kaynak}</figcaption>
    </figure>
  );
}

/** Ekran bağlantısı — kılavuzdan doğrudan ilgili sayfaya (ya da sekmeye) atlar. */
function Ekran({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {children}
    </Link>
  );
}

/** Klavye kısayolu. */
function Tus({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-shape-xs border border-outline-variant bg-surface-container px-1.5 py-0.5 font-mono text-label-medium text-on-surface">
      {children}
    </kbd>
  );
}

/** Dosya yolu, komut ya da dosya adı. */
function Kod({ children }: { children: ReactNode }) {
  return <code className="break-all font-mono text-body-small text-on-surface">{children}</code>;
}

/**
 * Başka bir ekrandan çapalı adresle gelindiğinde (ör. yol haritasındaki BTR
 * maddesi → `/kilavuz#ag-katalogu`) ilgili bölüme kaydırır.
 *
 * Tarayıcı çapayı YALNIZ gerçek gezinmede kendisi uygular; SPA'da rota
 * değiştiğinde adresteki `#` yok sayılır, sayfa tepede açılırdı. Sayfa içi
 * "Bu kılavuzda" bağlantıları düz `<a href="#...">` olduğu için onları
 * tarayıcı zaten kaydırır; bu etki onları bozmaz (aynı hedefe kaydırır).
 */
function useCapayaKaydir(): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const hedef = document.getElementById(decodeURIComponent(hash.slice(1)));
    // jsdom ve eski gömülü motorlarda yok olabilir; kaydırma kritik değildir.
    hedef?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [hash]);
}

export default function KilavuzPage() {
  useCapayaKaydir();
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <p className="text-label-medium font-semibold tracking-wide text-primary">
          Kütüphane Defteri
        </p>
        <h1 className="mt-1 text-headline-medium font-semibold tracking-tight text-on-surface">
          Kullanım Kılavuzu
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Programı ilk kez kuran bir okul için iş sırasıyla anlatım. Kütüphane Defteri, okulun
          kütüphane işlerini yürüttüğü yerel araçtır: çevrimdışı çalışır, veriler yalnız bu
          bilgisayarda durur. Kılavuz, programa yeni özellikler geldikçe genişler.
        </p>
      </header>

      <Card className="p-5 sm:p-6">
        <nav aria-label="Kılavuz bölümleri">
          <p className="text-label-large font-semibold text-on-surface">Bu kılavuzda</p>
          <ol className="mt-2 grid list-decimal gap-x-8 gap-y-1 pl-5 text-body-medium sm:grid-cols-2">
            {KILAVUZ_BOLUMLERI.map((b) => (
              <li key={b.id}>
                <a
                  href={`#${b.id}`}
                  className="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  {b.baslik}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </Card>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="ilk-kurulum">
        <p>
          Program ilk açıldığında <strong>Kurulum Sihirbazı</strong> gelir. Üç adım tamamlanıp
          “Kurulumu tamamla” denmeden diğer ekranlar açılmaz. Sihirbaz her açılışta ilk eksik
          adımdan başlar.
        </p>

        <AltBaslik>1. Yönetici parolası ve kurtarma anahtarı</AltBaslik>
        <p>
          Yönetici parolası zorunludur ve bu adım atlanamaz. Öğrenci, öğretmen ve diğer personelin
          ad-soyadları ile öğrencilerin okul numaraları bu parolayla açılan bir anahtarla
          şifrelenir; parola kurulmadan kişi kaydı yapılamaz. Parolayı iki kez yazıp “Yönetici
          parolasını kur” düğmesine basın. Parola en az 8 karakterdir; kurulduktan sonra
          kaldırılamaz, yalnız değiştirilebilir.
        </p>
        <p>
          Parola kurulunca <strong>kurtarma anahtarı</strong> bir kez gösterilir. Parola unutulursa
          kayıtlara erişmenin tek yolu budur ve program anahtarı saklamaz. Anahtarı üç yoldan
          biriyle saklayın:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>“Yazdır”: yazıcıdan yalnız anahtarın bulunduğu alan çıkar.</li>
          <li>
            “PDF olarak kaydet”: okul adı, tarih ve bilgisayarın demirbaş no&apos;suyla birlikte
            kurtarma anahtarı çıktısı hazırlanır.
          </li>
          <li>
            Kâğıda elle yazmak: grupları sırasıyla, büyük harfle yazın. Anahtarda 0, 1, 8 ve 9
            rakamları yoktur; O ve I her zaman harftir.
          </li>
        </ul>
        <p>
          Sonra “Sakladım, doğrula” düğmesine basın. Anahtar ekrandan kalkar; sakladığınız kopyaya
          bakarak istenen iki grubu yazarsınız. İki grup tuttuğunda program anahtarın saklandığını
          kaydeder; <strong>kurulum bu doğrulama yapılmadan tamamlanmaz</strong>. Doğrulama bitmeden
          “Devam” düğmesi açılmaz; kopyaya yeniden bakmanız gerekirse “Anahtarı yeniden göster”i
          kullanın. Bu sırada görevli kipine geçer ya da kilitlerseniz anahtar kaybolmaz: yönetici
          kipine döndüğünüzde sihirbaz anahtarı yeniden gösterir ve doğrulamayı yeniden ister.
          Kurulum bitene kadar program kendiliğinden görevli kipine geçmez (boşta ve mutlak süre
          kurulum tamamlanınca işlemeye başlar), ama programı kapatırsanız anahtar gider: kapanan
          programda anahtar yeniden gösterilemez. Beş dakika hiçbir işlem yapılmazsa anahtar ekranda
          gizlenir (“Anahtarı göster” ile geri gelir): masadan kalktığınızda ekranda açık kalmasın
          diyedir, anahtar kaybolmaz.
        </p>
        <p>
          Anahtar ekranda değilken (ör. program kapandı ya da kurtarma anahtarını kaydedemediniz)
          sihirbazın 1. adımı iki yol sunar:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Kurtarma Anahtarını Doğrula:</strong> kâğıttaki ya da PDF&apos;teki anahtarın
            tamamını yazın. Anahtar doğruysa saklandığı kaydedilir ve kuruluma devam edersiniz.
          </li>
          <li>
            <strong>Kurtarma Anahtarını Yenile:</strong> anahtarı kaydedemediyseniz yönetici
            parolasını girip yeni bir anahtar üretin. Yeni anahtar bir kez gösterilir; onu da
            saklayıp doğrularsınız. Yenilemeden sonra zarftaki eski anahtar bu bilgisayarda kilidi
            açmaz, ama eski yedekler için gerekebilir (bkz. Yedek ve Güvenlik Dosyası bölümü).
          </li>
        </ul>
        <Ipucu>
          <p>
            Kurtarma anahtarının çıktısını bir zarfa koyup kapatın ve müdürlükte kilitli dolapta
            saklayın. PDF dosyasını USB belleğe aldıktan sonra bu bilgisayarda (ör. İndirilenler
            klasöründe) bırakmayın. Yönetici parolası en az iki görevlendirilmiş kişide bulunsun
            (ör. kütüphaneden sorumlu öğretmen ile sorumlu müdür yardımcısı): parolayı bilen tek
            kişi okuldan ayrılırsa ya da parolayı unutursa kayıtlara yalnız kurtarma anahtarıyla
            ulaşılır.
          </p>
        </Ipucu>
        <p>
          Elle yazdığınız anahtarın temiz bir çıktısını sonradan{" "}
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>&apos;teki “Kurtarma anahtarı
          çıktısı” kartından alabilirsiniz: anahtarı yazıp “PDF olarak kaydet”e basın. Program
          anahtarı doğrular; yanlış yazılmış anahtar basılmaz. Aynı ekranda “Kurtarma Anahtarını
          Yenile” kartı da vardır: anahtar kaybolursa yenisini oradan üretirsiniz. Kurtarma anahtarı
          doğrulanmamışsa Genel Bakış&apos;taki Başlangıç Yol Haritası ve Güvenlik ekranı uyarı
          gösterir.
        </p>

        <AltBaslik>2. Okul bilgileri</AltBaslik>
        <p>
          Okul adı, programın bastığı evrakın antedinin ilk satırıdır. <strong>Kademe</strong>{" "}
          (İlkokul, Ortaokul ya da Ortaöğretim (lise)) ve <strong>kısa ad</strong> zorunludur. Kısa
          ad etiketlerde ve üye kartlarında basılır, en çok 24 karakterdir. Kayıp kitap bedeli ve
          sınıf kitaplığı kuralları kademeye göre uygulanır. İl, ilçe ve okul müdürü evrakta
          kullanılır; “Hazırlık sınıfı” alanında “Var” seçilirse sınıf düzeylerine Hazırlık eklenir.
        </p>
        <p>
          “Bu bilgisayar okul demirbaşıdır.” onayı zorunludur: program yalnız okulun demirbaşı olan
          bilgisayara kurulur. Dayanağı Bilgi ve Sistem Güvenliği Yönergesi&apos;nin iki hükmüdür:
        </p>
        <Mevzuat kaynak={`${YONERGE}, md. 11/8`}>
          “Kullanıcılar, kişisel bilişim kaynaklarını kurum ağında sistem yöneticisinden izin
          almadan kullanamaz.”
        </Mevzuat>
        <Mevzuat kaynak={`${YONERGE}, md. 11/23`}>
          “Bakanlığa ait gizli ya da açık her türlü veri Bakanlık sistemleri üzerinde barındırılır.
          Herhangi bir bulut depolama sistemine veri aktarılmaz.”
        </Mevzuat>
        <p>
          Bilgisayarın demirbaş no&apos;su isteğe bağlıdır: taşınır kaydındaki numara yazılır,
          kurtarma anahtarı çıktısında da basılır. Bilgileri girip “Kaydet ve devam et”e basın.
        </p>

        <AltBaslik>3. Ders yılı ve kapalı günler</AltBaslik>
        <p>
          “Yeni ders yılı” formuna ders yılının adını (ör. 2026-2027), başlangıç ve bitiş
          tarihlerini, 1. dönemin bitişini ve 2. dönemin başlangıcını yazıp “Ders yılını kaydet ve
          aktifleştir” düğmesine basın. Aynı anda yalnız bir ders yılı aktif olabilir; şube kataloğu
          ve e-Okul aktarımı aktif ders yılına bağlanır. Yarıyıl tatili 1. dönemin bitişiyle 2.
          dönemin başlangıcı arasında kalır.
        </p>
        <p>
          Ders yılı kaydedilince iki takvim yılının resmî tatilleri ve dini bayramları kendiliğinden
          eklenir. Programda bir yılın dini bayram tarihleri yoksa uyarı çıkar; o tarihleri Diyanet
          takvimine bakarak “Dini bayram” türünde elle eklersiniz. Ara tatil ve yarıyılı “Öğrenciye
          kapalı gün” türünde siz girersiniz (bkz. Kapalı Günler bölümü).
        </p>
        <p>
          “Kurulumu tamamla” dediğinizde program Genel Bakış ile açılır. Bir adım eksikse program
          hangi adımın ve hangi bilginin eksik olduğunu yazar. Okul bilgilerini, ders yıllarını ve
          kapalı günleri sonradan <Ekran to="/ayarlar?tab=okul">Ayarlar → Okul Bilgileri</Ekran>,
          Ders Yılları ve Kapalı Günler sekmelerinden değiştirebilirsiniz. Sihirbazı yeniden açmak
          için Ayarlar sayfasının altındaki “Kurulum Sihirbazı” kartını kullanın.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="yol-haritasi">
        <p>
          Kurulumdan sonra <Ekran to="/">Genel Bakış</Ekran>&apos;taki “Başlangıç Yol Haritası”
          kartı, programı okulda kullanmaya başlamak için sıradaki yedi işi gösterir. Her madde
          ilgili ekrana bağlanır:
        </p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>e-Okul öğrenci listesini aktarmak,</li>
          <li>öğretmen ve diğer personel listesini aktarmak,</li>
          <li>öğrenciye kapalı günleri (ara tatil, yarıyıl) girmek,</li>
          <li>katalog Excel şablonunu indirip doldurmaya başlamak,</li>
          <li>kurtarma anahtarını müdürlükte kapalı zarfta saklamak,</li>
          <li>yönetici parolasını en az iki görevlendirilmiş kişiyle paylaşmak,</li>
          <li>Ağ Kataloğu için bilişim teknolojileri rehber öğretmeniyle (BTR) görüşmek.</li>
        </ol>
        <p>
          İlk üç madde yapıldığında kendiliğinden işaretlenir; şablon maddesi şablonu indirdiğinizde
          işaretlenir. Program diğerlerinin yapıldığını bilemez: yaptıkça “Yapıldı” kutusunu siz
          işaretlersiniz. İşaretler programda saklanır. Bütün maddeler tamamlanınca “Kartı gizle”
          düğmesi çıkar. Kurtarma anahtarının saklandığı doğrulanmadıysa kart gizlenmez: uyarı
          kartın başındadır ve gözden kaçmamalıdır.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="kipler">
        <p>
          Program kişi ayrımını kullanıcı hesabıyla değil <strong>kiple</strong> yapar. Yönetici
          parolası kurulduktan sonra program her açılışta “Kayıtlar kilitli” ekranıyla açılır;
          yönetici parolasını yazıp “Aç” düğmesine basınca yönetici kipi başlar. Kipin adı ve kip
          düğmeleri üst çubuktadır.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Yönetici kipi</strong> kütüphane yöneticisi (kütüphaneci ya da kütüphaneden
            sorumlu öğretmen) içindir. Bütün ekranlar açıktır: Kişiler, Ayarlar, e-Okul aktarımı,
            yedek.
          </li>
          <li>
            <strong>Görevli kipi</strong> masadaki görevli (öğrenci görevli ya da personel) içindir.
            Menüdeki bağlantılar gizlenir, ekranda “Görevli Kipi” sayfası durur. Yönetici işleri bu
            kipte kapalıdır; program onları arka planda da reddeder. Görevli, kitaplara yapıştırılan
            etiketleri bu sayfadaki “Doğrulama okutmasını aç” düğmesiyle okutup doğrulayabilir;
            etiket basmak, basım işaretini geri almak ve “Doğrulanmamış Etiketler” listesi yönetici
            kipindedir.
          </li>
        </ul>

        <AltBaslik>Kipler arasında geçiş</AltBaslik>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Yönetici kipinden görevli kipine “Görevli kipine geç” düğmesiyle ya da{" "}
            <Tus>Ctrl+Shift+G</Tus> kısayoluyla geçilir; parola istenmez.
          </li>
          <li>
            Görevli kipinden çıkmak için “Yönetici kipine geç” düğmesine basıp yönetici parolasını
            yazın.
          </li>
          <li>
            Yönetici kipi <strong>3 dakika</strong> işlem yapılmazsa ya da açıldıktan en geç{" "}
            <strong>30 dakika</strong> sonra kendiliğinden kapanır; program görevli kipine geçer.
            Üst çubuktaki geri sayım kalan süreyi gösterir. Çalışmayı sürdürüyor olsanız da 30
            dakika dolunca parola yeniden sorulur.
          </li>
          <li>
            “Kilitle” her kipte parolasızdır: kayıtların anahtarı bellekten silinir ve “Kayıtlar
            kilitli” ekranı gelir. Açmak için yönetici parolası gerekir. “Kilitle” düğmesi Ayarlar →
            Güvenlik&apos;te de vardır.
          </li>
        </ul>
        <Ipucu>
          <p>
            Masadan kalkarken görevli çalışmayı sürdürecekse “Görevli kipine geç”i, kimse
            çalışmayacaksa “Kilitle”yi seçin. Pencerenin çarpı düğmesi programı ne kapatır ne
            kilitler: program saatin yanındaki simge alanında (tepside) çalışmayı sürdürür. Görevli
            kipi masadaki görevlinin yönetici ekranlarına ulaşmasını önler, bilgisayarın kendisini
            korumaz; masa için yönetici yetkisi olmayan ayrı bir kütüphane masası Windows hesabı
            önerilir.
          </p>
        </Ipucu>

        <AltBaslik>Parolayı unutursanız</AltBaslik>
        <p>
          Kilit ekranında “Parolamı unuttum”u seçin, kurtarma anahtarını ve yeni parolayı yazıp
          “Kurtar ve aç” düğmesine basın. Bu işlem kurtarma anahtarını DEĞİŞTİRMEZ: zarftaki kâğıt,
          siz <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>&apos;teki “Kurtarma
          Anahtarını Yenile” kartını kullanana kadar geçerli kalır. Yeni parolayı, parolayı bilen
          öbür görevlendirilmiş kişiye de bildirin.
        </p>

        <AltBaslik>Parolayı değiştirmek</AltBaslik>
        <p>
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>&apos;te “Parolayı değiştir”
          düğmesine basın; mevcut parolayı ve yeni parolayı iki kez yazıp “Uygula”yı seçin. Parolayı
          bilen biri görevden ayrılırsa parolayı değiştirin. Parola değiştikten sonra eski yedekler,
          alındıkları dönemdeki parolayla ya da kurtarma anahtarıyla açılır.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="kisiler">
        <p>
          <Ekran to="/kisiler">Kişiler</Ekran> sayfasının üç sekmesi vardır: “Öğrenciler”,
          “Öğretmenler ve Diğer Personel” ve “Ayrılış Havuzu”. Program T.C. kimlik numarası, veli
          bilgisi, cinsiyet, unvan ve branş tutmaz. Öğrencide ad, soyad, okul no, sınıf ve şube;
          öğretmen ve diğer personelde ad, soyad ve üye türü tutulur. Kişi kaydı için yönetici
          parolasının kurulmuş olması gerekir.
        </p>
        <Ipucu>
          <p>
            <strong>Aktarım kimseyi okuldan ayırmaz ve kimsenin kaydını silmez.</strong> Listede
            bulunmayan öğrenci ve personel “Ayrılış Havuzu” sekmesine eklenir, durumları aktif
            kalır. Ayrılıp ayrılmadıklarına siz karar verirsiniz; böylece iade edilmemiş kitabı olan
            kişi kayıp olmaz.
          </p>
        </Ipucu>

        <AltBaslik>Öğrenci listesi</AltBaslik>
        <p>
          e-Okul&apos;da Öğrenci İşlemleri → Raporlar → <strong>OOG01001R020</strong> — Sınıf/Şube
          Öğrenci Listesi raporunu Excel olarak indirin ve dosyayı değiştirmeden “Öğrenciler”
          sekmesinin altındaki aktarım paneline yükleyin. e-Okul dosyası .XLS uzantısıyla iner; şube
          blokları ve sayaç satırları kendiliğinden çözülür, cinsiyet ve pansiyon sütunları okunmaz.
          e-Okul raporu yerine “Şablon indir” ile programın şablonunu (sınıf, okul numarası, ad,
          soyad) doldurabilir ya da tabloyu Excel&apos;den kopyalayıp “Ya da tabloyu yapıştırın”
          alanına yapıştırabilirsiniz.
        </p>
        <p>
          Aktarım iki aşamalıdır. “Önizle” hiçbir kaydı yazmaz: şube bazında kaç öğrencinin yeni,
          güncellenen, değişmeyen ve ayrılış havuzuna eklenecek olduğunu gösterir. “Aktar” düğmesi
          önizlemeden sonra açılır.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Öğrenciler okul numarasıyla eşleştirilir. Dosyada yeni şubesiyle görünen öğrenci
            ayrılmaz, kaydı güncellenir; ayrılış havuzunda bekliyorsa havuzdan kendiliğinden çıkar.
            Ayrıldı olarak duran bir öğrenci aynı numara ve aynı adla listeye dönerse kaydı yeniden
            aktif olur; numara adı farklı bir öğrenciye verilmişse eski kayıt olduğu gibi kalır ve
            yeni kayıt açılır.
          </li>
          <li>
            Karşılaştırma varsayılan olarak <strong>yalnız dosyada bulunan şubelerle</strong>{" "}
            yapılır. Tek bir şubenin listesini yüklemek diğer şubelere dokunmaz; dosyadaki bir
            şubede kayıtlı olup dosyada bulunmayan öğrenci ayrılış havuzuna eklenir.{" "}
            <strong>
              Başka bir şubeye geçtiği için bu dosyada bulunmayan öğrenci de havuza eklenir.
            </strong>{" "}
            Bu yüzden yeni ders yılı başında ya da şube değişikliklerinden sonra listeyi şube şube
            yüklemeyin: okulun bütün şubelerini içeren listeyi tek dosyada yükleyin. (Şube şube
            yüklerseniz de kimse ayrılmaz; öğrenci yeni şubesinin listesi gelene kadar havuzda
            bekler.)
          </li>
          <li>
            “Bu dosya okulun tam listesidir” kutusunu yalnız okulun bütün şubelerini içeren dosyada
            işaretleyin: işaretlenirse dosyada hiç bulunmayan şubelerdeki öğrenciler de ayrılış
            havuzuna eklenir.
          </li>
          <li>
            Bir satır atlanırsa (ad ya da sınıf okunamadıysa) o satırdaki okul numarasına sahip
            öğrenci havuza eklenmez. Okul numarası boş bir öğrenci satırı kimin olduğu bilinemediği
            için o şubeden kimseyi havuza eklemez. Önizleme bu satırları numarasıyla gösterir.
          </li>
        </ul>

        <AltBaslik>Öğretmen ve diğer personel listesi</AltBaslik>
        <p>
          e-Okul&apos;da Kurum İşlemleri → Raporlar → <strong>OOK01001R1</strong> — Personel Listesi
          raporunu Excel olarak indirip “Öğretmenler ve Diğer Personel” sekmesindeki panele
          değiştirmeden yükleyin. Ad-soyad okunur; görev sütunu yalnız <strong>üye türünü</strong>{" "}
          (Öğretmen ya da Diğer personel) belirlemek için kullanılır ve saklanmaz, branş hiç
          okunmaz. Görevi tanınmayan satırlar için önizlemede üye türünü denetleme uyarısı çıkar; bu
          satırlar öğretmen olarak açılır, gerekirse kişiyi düzenleyip “Diğer personel”i seçin.
          Ödünç sayı sınırı üye türüne göre uygulanır.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Kişiler ad-soyadla eşleştirilir. Kayıtta olup listede bulunmayanlar ayrılış havuzuna
            eklenir; kimse kendiliğinden ayrılmaz.
          </li>
          <li>
            <strong>Olası aynı kişi:</strong> listedeki yeni bir ad kayıttaki bir kişiye benziyorsa
            (ör. soyadı değişimi) önizleme ikisini birlikte gösterir. Bu kişiyi ayrıldı diye
            işaretlemeyin; aktardıktan sonra “Birleştir” düğmesine basın (aynı düğme “Ayrılış
            Havuzu” sekmesinde de vardır). Eski kaydın kütüphane bağları yeni kayda taşınır ve eski
            kayıt silinir. Benzerlik yalnız addan hesaplanır: okula yeni gelen bir adaş da eş olarak
            görünebilir. Her satır <strong>neden aday olduğunu</strong> yazar (“adı aynı, soyadı
            farklı”, “ad-soyadında küçük yazım farkı” gibi); havuzda ayrıca adayın üye türü ve
            sicile eklendiği gün görünür. Birleştirme geri alınamadığı için onay kutusunu
            işaretlemeden düğme açılmaz: kutuyu yalnız iki kaydın aynı kişiye ait olduğundan
            eminseniz işaretleyin.
          </li>
        </ul>

        <AltBaslik>Ayrılış Havuzu</AltBaslik>
        <p>
          <Ekran to="/kisiler?tab=havuz">Kişiler → Ayrılış Havuzu</Ekran> aktarımda listede
          bulunmayan kişileri toplar. Havuzdaki kişinin durumu <strong>aktif kalır</strong>: hiçbir
          kayıt kendiliğinden ayrılmış sayılmaz, silinmez. Her kişi için iki seçenek vardır:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>“Ayrıldı olarak işaretle”</strong> (onay ister): kişi okuldan ayrılmış sayılır
            ve seçicilerden düşer. Kaydı silinmez; sicilde “Ayrıldı · gg.aa.yyyy” rozetiyle kalır,
            iade etmediği kitap varsa izlenebilir. Sonraki bir e-Okul listesinde yeniden görünürse
            kaydı yeniden aktif olur.
          </li>
          <li>
            <strong>“Aktif kalsın”</strong>: kişi havuzdan çıkar, hiçbir şey değişmez. Bir sonraki
            listede yine bulunmazsa havuza yeniden girer.
          </li>
        </ul>
        <p>
          Satırlar tek tek ya da toplu seçilebilir; “Sınıf” süzgeci yıl sonunda mezun şubeleri bir
          kerede işaretlemeye yarar. Her satırda kişinin havuza hangi gün ve hangi aktarımla girdiği
          yazar. Genel Bakış&apos;taki “Ayrılış Havuzu” kartı bekleyen kişi sayısını gösterir ve
          buraya getirir.
        </p>
        <Ipucu>
          <p>
            Ayrılan kişilerin kayıtları bu sürümde programda kalır. Kayıtların ne kadar süre
            saklanacağı ve otomatik silinmesi sonraki sürümlerde gelecek; o zamana kadar gereksiz
            bulduğunuz bir kaydı düzenleme penceresindeki “Sil” ile kaldırabilirsiniz (kütüphane
            işlemi olmayan kayıtlarda).
          </p>
        </Ipucu>

        <AltBaslik>Elle kayıt ve ayrılış</AltBaslik>
        <p>
          Tek kişi eklemek için “Öğrenci ekle” ya da “Kişi ekle” düğmesini kullanın; düzenlemek için
          listedeki satıra tıklayın. Okuldan ayrılan kişi için düzenleme penceresindeki “Ayrıldı
          olarak işaretle”yi seçin: kişi seçicilerden düşer, kaydı silinmez ve “Ayrıldı ·
          gg.aa.yyyy” rozetiyle kalır. “Sil” yalnız yanlış girilmiş kayıtlar içindir.
        </p>
        <p>
          Okul numarası şifreli saklandığı için arama numaranın tamamıyla yapılır; numaranın bir
          parçasıyla arama yapılamaz. Öğrenci aktarımında görülen şubeler{" "}
          <Ekran to="/ayarlar?tab=subeler">Ayarlar → Şubeler</Ekran>&apos;e kendiliğinden eklenir.
        </p>
        <Ipucu>
          <p>
            e-Okul listeleri kişisel veri içerir. Dosyayı bu bilgisayara şifreli bir taşıyıcıyla
            (ör. parolalı USB bellek) getirin ve aktarım biter bitmez silin; İndirilenler klasörünü
            ve Geri Dönüşüm Kutusu&apos;nu da denetleyin. Listeyi e-postayla göndermeyin, ortak
            klasörde bırakmayın.
          </p>
        </Ipucu>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="kapali-gunler">
        <p>
          <Ekran to="/ayarlar?tab=kapali-gunler">Ayarlar → Kapalı Günler</Ekran> kütüphanenin kapalı
          olduğu günleri takvim yılına göre listeler. Dört tür vardır, her biri rozetle gösterilir:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Resmî tatil</strong> ve <strong>Dini bayram</strong>: “Resmî ve dini tatilleri
            ekle” düğmesi seçili yılın tatillerini ekler; düğmeye yeniden basmak aynı kaydı ikinci
            kez eklemez.
          </li>
          <li>
            <strong>Öğrenciye kapalı gün</strong>: ara tatil ve yarıyıl. Kanunen tatil değildir,
            okulda mesai sürer; bu yüzden tatillerden ayrı tutulur.
          </li>
          <li>
            <strong>İdari izin / diğer</strong>: personelin de izinli olduğu, kütüphanenin kapalı
            kaldığı günler.
          </li>
        </ul>
        <p>
          “tahmini” rozetli dini bayram tarihleri hesapla bulunmuştur ve bir gün kayabilir. Diyanet
          takvimi kesinleşince kontrol edin; tarih farklıysa kaydı silip doğru tarihle “Dini bayram”
          türünde yeniden ekleyin. Programda tarihi hiç bulunmayan yıllarda dini bayramları aynı
          yolla elle girersiniz.
        </p>
        <p>
          Ara tatil ve yarıyılı “Kapalı Gün Ekle” formuyla girin: adı (ör. Yarıyıl tatili), türü
          “Öğrenciye kapalı gün”, başlangıç ve bitiş tarihini yazıp “Ekle”ye basın; bitiş boş
          bırakılırsa tek gün sayılır. Kurulum sihirbazı ders yılının iki takvim yılının tatillerini
          kendiliğinden ekler; yeni ders yılını Ayarlar → Ders Yılları&apos;ndan açarsanız iki yıl
          için de “Resmî ve dini tatilleri ekle”yi kullanın.
        </p>

        <AltBaslik>İade tarihindeki anlamı</AltBaslik>
        <Mevzuat kaynak={`${YONETMELIK}, md. 18/1`}>
          “Bir kitabı ödünç alma süresi on beş gündür.”
        </Mevzuat>
        <p>
          Kapalı günler ödünçte iade tarihinin hesabında kullanılır. İade tarihi, ödünç verildiği
          günden on beş gün sonrasıdır; o gün kapalı bir güne denk gelirse iade tarihi izleyen ilk
          açık güne kayar. Kaydırmanın dayanağı günün türüne göre değişir:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Hafta sonu, resmî tatil ve dini bayram</strong> her zaman kapalıdır. Yönetmelik,
            sürenin son günü tatile rastlarsa ne olacağını söylemez; program Türk Borçlar
            Kanunu&apos;ndaki genel kuralı kıyasen uygular.
          </li>
          <li>
            <strong>İdari izin ve diğer kapalı günler</strong> de her zaman kapalı sayılır. Bu bir
            mevzuat hükmü değil, programın kuralıdır: idari izin kanunda tatil sayılmaz, ama
            kütüphane o gün kapalı olduğu için kitap iade edilemez.
          </li>
          <li>
            <strong>Öğrenciye kapalı günlerde</strong> (ara tatil, yarıyıl) kaydırma bir mevzuat
            hükmü değil, okulun tercihidir: öğrenciler bu günlerde okulda olmadığı için kitabı iade
            edemez.
          </li>
        </ul>
        <Mevzuat kaynak="Türk Borçlar Kanunu, md. 93">
          “İfa zamanı veya sürenin son günü, kanunlarda tatil olarak kabul edilen bir güne
          rastlarsa, kendiliğinden bu günü izleyen ve tatil olmayan ilk güne geçer.”
        </Mevzuat>
        <p>
          Kapalı bir günü silerseniz bundan sonra hesaplanan iade tarihlerinde o gün açık gün
          sayılır.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="katalog">
        <p>
          Kenar çubuğundaki <Ekran to="/katalog">Katalog</Ekran> kütüphanenin künye ve nüsha
          kayıtlarını tutar. Sayfanın iki sekmesi vardır: “Eserler” ve “Nüshalar”.
        </p>

        <AltBaslik>Eser ve nüsha</AltBaslik>
        <p>
          <strong>Eser</strong> künyedir: kaynak adı, yazar, yayınevi, konu, ISBN, sınıflama.{" "}
          <strong>Nüsha</strong> rafta duran kitabın kendisidir. Aynı kitaptan beş tane aldıysanız
          bir eser ve beş nüsha olur; her nüshanın kendi barkodu ve kayıt numarası vardır, her biri
          ayrı ödünç verilir. Künye bir kez yazılır, nüshalar ona bağlanır.
        </p>
        <p>
          “Eserler” sekmesinde arama kaynak adı, yazar, konu ve ISBN üzerinde çalışır; yazmayı
          bırakınca sonuç kendiliğinden gelir. Büyük-küçük harf farkı aranmaz: “şiir” ile “ŞİİR”,
          “İnce” ile “ince” aynı sonucu verir. Düzeltme işareti (şapka) de aranmaz: “rüzgar” yazınca
          “Rüzgâr Gibi Geçti” bulunur. Ama <strong>“ı” ile “i” ayrı harflerdir</strong>: “ılık” ile
          “ILIK” “Ilık Sular”ı getirir, “ilik” ise “İlik Nakli”ni — Türkçede bunlar iki ayrı harftir
          ve program onları birleştirmez. “Sırala” kutusunda üç katalog ekseni vardır — “Kaynak
          adına göre”, “Yazar adına göre”, “Konuya göre” — ve bir de “En yeni eklenen”. Üç eksen
          Yönetmelikteki katalog düzenidir; sıralama Türkçe alfabeye göre yapılır, Ç ve Ş harfleri
          listenin sonuna atılmaz.
        </p>
        <Mevzuat kaynak={`${YONETMELIK}, md. 11/1`}>
          “Kataloglar; yazar adı, kaynak adı ve konularına göre alfabetik olarak düzenlenir.”
        </Mevzuat>
        <p>
          “Nüshalar” sekmesi fiziksel eksendir: barkodun tamamını yazarak tek kitabı bulursunuz
          (numaranın bir parçasıyla arama yapılmaz), bölüme ve duruma göre süzersiniz. Üç kutu
          listeyi daraltır: “Yalnız ödünç verilebilenler”, “Yalnız etiketlenmemişler” (barkod
          etiketi basılmamış nüshalar) ve “Kayıttan düşülenleri gizle”. Listeler sayfalıdır; bir
          süzgeci değiştirince ilk sayfaya dönülür.
        </p>
        <p>
          Yeni künye “Eser ekle” düğmesiyle açılır. Listede bir satıra tıklamak{" "}
          <strong>Eser Ayrıntısı</strong> sayfasını getirir: künye kartı, “Künyeyi düzenle” ve “Sil”
          düğmeleri, altında da o eserin nüshaları. Nüsha “Nüsha ekle” ile açılır; “Nüsha sayısı”na
          birden büyük bir sayı yazarsanız aynı künyeden o kadar nüsha tek işlemde açılır (bir
          seferde en çok 50) ve her biri ayrı numara alır. “Eski kayıt no” yalnız tek nüsha açarken
          yazılır, çünkü her kitabın damgası başkadır.
        </p>
        <Ipucu>
          <p>
            Bu ekran tek tek kayıt içindir. Kitabı elinize alıp ISBN barkodunu okutarak girmek için{" "}
            <Ekran to="/katalog/hizli-kayit">Katalog → Hızlı Kayıt</Ekran>, hazır bir listeyi
            topluca almak için <Ekran to="/katalog/ice-aktarma">Katalog → İçe Aktarma</Ekran>{" "}
            ekranını kullanın. İkisi de aşağıda anlatılır; iki bağlantı da Katalog sayfasının sağ
            üstündedir.
          </p>
        </Ipucu>

        <AltBaslik>Bölümler</AltBaslik>
        <p>
          Bölüm, kütüphanenin konu bölümüdür (Edebiyat, Tarih, Başvuru gibi). Serbest metin değil,
          kontrollü bir listedir: <Ekran to="/ayarlar?tab=bolumler">Ayarlar → Bölümler</Ekran>
          &apos;den “Bölüm ekle” ile tanımlanır, eser ve nüsha formlarında seçilir. Böylece
          “Edebiyat”, “edebiyat” ve “EDEBİYAT” tek bölüme düşer; raf etiketleri ve ağdaki dizinler
          tutarlı kalır.
        </p>
        <p>
          Her bölümün isteğe bağlı bir Dewey Onlu Sınıflama (DOS) aralığı (“DOS aralığı başı” ve
          “DOS aralığı sonu”, ör. 800-899), bir “Kısa tarif”i ve bir “Sıra” numarası vardır; küçük
          sıra numarası önce gelir, eşitlikte ad sırası uygulanır. Aralık yalnız bilgilendirmedir:
          aralığın dışında kalan bir eseri de o bölüme koyabilirsiniz, program engellemez. İçinde
          eser ya da nüsha bulunan bölüm silinemez; önce kayıtları başka bir bölüme taşıyın.
        </p>

        <AltBaslik>Sınıflama kodu ve yer numarası</AltBaslik>
        <p>
          “Sınıflama kodu” kitabın DOS kodudur (ör. 813.54). “Yer numarası” sırt etiketine basılacak
          numaradır ve kitabın rafta duracağı yeri söyler. Boş bırakırsanız program onu sınıflama
          kodu ile yazar soyadının ilk üç harfinden üretir: “813.54 STE”. Soyad, “Yazar(lar)”
          alanındaki ilk adın son sözcüğü sayılır; bileşik soyadlarda bu sezgi yanılabilir, bu
          yüzden alan elle değiştirilebilir bırakılmıştır. Yazarı “Ad Soyad” sırasıyla yazın, birden
          çok yazarı virgülle ayırın. Aynı eserin bütün nüshaları aynı yer numarasını taşır.
        </p>
        <p>
          “Sınıflama kaynağı” kodun nereden geldiğini söyler: “Katalogdan bulundu”, “Tahmini” ya da
          “Elle girildi”. “Tahmini” işaretli kodları raf düzenini kurarken gözden geçirin.
        </p>

        <AltBaslik>ISBN</AltBaslik>
        <p>
          ISBN kitabın künye sayfasında yazan numaradır; tireli yazabilirsiniz, program tireleri
          atar. On haneli bir numara yazarsanız 13 haneli karşılığı da hesaplanır ve ikisi birden
          aramaya girer: elinizdeki eski numarayla da arama yapabilirsiniz. Numaranın son hanesi
          (sağlama hanesi) tutmuyorsa ya da uzunluk 10 ile 13&apos;ten başkaysa{" "}
          <strong>kayıt engellenmez</strong>: numara olduğu gibi saklanır, ekranda “ISBN uyarısı”
          bandı durur. Saha verisi bozuk olabilir; uyarıyı görünce kitabın künye sayfasından
          denetleyin. Aynı ISBN&apos;li birden çok künye bulunabilir, program buna da karışmaz.
        </p>
        <Ipucu>
          <p>
            Kitabın arkasındaki çizgili kod ISBN barkodudur, kütüphane etiketi değildir: 13
            hanelidir ve 978 ya da 979 ile başlar. Barkod okuyucuyla ödünç verme sonraki sürümde
            gelecek; o zaman ISBN barkodu okutulursa program “Bu ISBN barkodu. Kitabın kütüphane
            etiketini okutun.” diyecek. Bu sürümde “Nüshalar” sekmesindeki “Barkod” kutusu yalnız
            kütüphane etiketini arar: ISBN barkodu okutursanız liste boş kalır.
          </p>
        </Ipucu>

        <AltBaslik>Barkod ve kayıt no</AltBaslik>
        <p>
          Her nüsha açıldığında programdan iki numara alır: <strong>barkod</strong> ve{" "}
          <strong>kayıt no</strong>. İkisi de aynı sayaçtan doğar ve aynı sayıdır. Barkod on
          hanedir, ilk dört hane nüshanın açıldığı yıl, kalan altı hane o yılın sıra numarasıdır;
          etikette ve ekranda “2026-000123” diye yazılır. Kayıt no aynı sayının düz hâlidir
          (2026000123) ve Taşınır Kütüphane Defteri dökümünde bu sayı kullanılır. Numaraları siz
          girmezsiniz ve değiştiremezsiniz; nüsha penceresinde barkod, kayıt no ile barkod etiketi,
          sırt etiketi ve etiket doğrulaması tarihleri yalnız bilgi satırıdır. Tarihleri Etiketler
          ekranı yazar: basım tarihini “Basıldı olarak işaretle”, doğrulama tarihini doğrulama
          okutması.
        </p>
        <p>
          <strong>Bir numara asla yeniden kullanılmaz.</strong> Yanlış açılmış bir nüshayı
          silerseniz numarası boşta kalır, başka bir kitaba verilmez: taşınır kayıtları ve eski
          defterler geriye doğru okunabilir kalmalıdır. Bu yüzden nüsha penceresindeki “Sil” yalnız
          veri giriş hatası içindir. Ayıklanan, kaybolan ya da devredilen kitap silinmez; kayıttan
          düşme yolu sonraki sürümlerde gelecek.
        </p>
        <p>
          Kitabın üzerinde eski bir damga ya da defter numarası varsa “Eski kayıt no” alanına yazın;
          programın verdiği numarayla karışmaz. Taşınır kaydındaki karşılığı biliyorsanız Taşınır
          Kayıt ve Yönetim Sistemi (TKYS) kodunu “TKYS kodu” alanına yazabilirsiniz; program bu kodu
          doğrulamaz. Bu alan hiçbir işlemde zorunlu değildir: okulunuz TKYS’de nüsha bazında kayıt
          tutmuyorsa boş bırakın.
        </p>

        <AltBaslik>Ödünç verilmeyen kaynaklar</AltBaslik>
        <p>
          Bir nüshanın ödünç verilip verilemeyeceği tek yerden belirlenir. Nüsha penceresindeki iki
          kutu doğrudan Yönetmelikten gelir: “Danışma kaynağı (ödünç verilmez)” ve “Piyasada mevcudu
          yok (ödünç verilmez)”. Üçüncüsü kaynak türüdür: “Süreli yayın” türündeki eserin nüshaları
          ödünç verilmez (“Ciltli süreli yayın” kutusu ciltlenmiş yıllıkları işaretler).
        </p>
        <Mevzuat kaynak={`${YONETMELIK}, md. 16/1`}>
          “Ancak; a) Danışma kaynakları, b) Piyasada mevcudu bulunmayan kitaplar, c) Süreli
          yayınlar, ödünç verilmez.”
        </Mevzuat>
        <p>
          Listelerde bu nüshalar gerekçesiyle görünür: “Ödünç verilmez — kütüphanede okunur.”,
          “Piyasada mevcudu yok — ödünç verilmez.”, “Süreli yayın — ödünç verilmez.” Gerekçe kişisel
          veri taşımaz; masada öğrencinin de gördüğü ekranda durabilir.
        </p>
        <p>
          Danışma kaynağı kütüphanede okunan, dışarı çıkmayan kaynaktır.{" "}
          <strong>Ders kitapları da danışma dermesindedir</strong>: ders kitabı nüshalarında bu
          kutuyu işaretleyin.
        </p>
        <Mevzuat kaynak={`${YONETMELIK}, md. 14/1-a`}>
          “Danışma dermesi oluşturulur. Burada ders kitapları, ansiklopediler, sözlükler, atlaslar,
          yıllıklar, rehberler, bibliyografyalar, kataloglar, listeler ve benzerleri bulundurulur.”
        </Mevzuat>
        <p>
          “El yazması / nadir eser” kutusu ödünç verilebilirliği değiştirmez; bu nüshalar Genel
          Müdürlüğe gönderilecek listede toplanır (sonraki sürüm). Kaynak türleri: Kitap, Süreli
          yayın, Görsel-işitsel materyal, E-kitap, E-veri tabanı. E-kitap ve e-veri tabanında nüsha
          açılmaz — bu türlerde “Nüsha ekle” düğmesi yerine “E-kitap ve e-veri tabanında nüsha
          açılmaz.” yazar.
        </p>

        <AltBaslik>Edinimler ve bağışlar</AltBaslik>
        <p>
          Kütüphaneye giren her nüsha bir <strong>edinim partisine</strong> bağlıdır: kaynağın
          nereden ve ne zaman geldiğinin kaydıdır. Katalog sayfasının sağ üstündeki{" "}
          <Ekran to="/katalog/edinimler">Edinimler ve Bağışlar</Ekran> bağlantısı üç sekme açar:
          “Edinim Partileri”, “Bağış Ön Kayıtları” ve “Komisyon Kararları”.
        </p>
        <p>
          Parti “Edinim ekle” ile açılır. “Edinim yolu” seçenekleri: Bakanlık gönderimi, Satın alma,
          Bağış, Değişim, Sayım fazlası (kayda giriş), Mevcut koleksiyon (programa aktarım). İlk
          dördü Yönetmeliğin saydığı yollardır; son ikisi kayıt içi girişlerdir — sayımda çıkan
          fazlanın kayda alınması ve raftaki eski koleksiyonun programa aktarılmasıdır.
        </p>
        <Mevzuat kaynak={`${YONETMELIK}, md. 10/5`}>
          “Kütüphane kaynakları; Bakanlıktan gönderilen kaynaklar ile satın alma, bağış ve imkânlara
          göre değişim yoluyla sağlanır.”
        </Mevzuat>
        <p>
          “Kaynak notu”na bağışçı, satıcı ya da partinin açıklaması yazılır; kişi adı yazdıysanız
          şifreli saklanır ve yönetici parolası kurulmadan kaydedilemez. “Birim fiyat” isteğe
          bağlıdır, ondalık ayracı nokta ile yazılır.
        </p>
        <p>
          <strong>Bağış kataloğa doğrudan girmez.</strong> Okula bağış geldiğinde “Bağış ön kaydı
          ekle” ile bir ön kayıt açın ve kitapları “Kalem ekle” ile tek tek yazın. Bu aşamada nüsha
          açılmaz, numara verilmez; liste günler içinde tamamlanabilir, yanlış yazılan kalem “Çıkar”
          ile listeden alınır.
        </p>
        <Mevzuat kaynak={`${YONETMELIK}, md. 10/3`}>
          “Okul kütüphanesine bağışlanacak kitaplar, bu Yönetmelik çerçevesinde Seçim ve Ayıklama
          Komisyonu tarafından değerlendirilir.”
        </Mevzuat>
        <p>
          Komisyon toplanınca kararını “Komisyon Kararları” sekmesinde “Karar ekle” ile yazın:
          “Karar türü”, “Karar tarihi”, “Karar sayısı”, “Başkan adı” ve “Katılımcılar”. Karar
          türleri “Kaynak seçimi”, “Bağış değerlendirme” ve “Ayıklama”dır; bağış ancak bir bağış
          değerlendirme kararıyla kataloglanır, ayıklama kararı sonraki sürümde ayıklama işinde
          kullanılacaktır. Başkan adı ile katılımcılar kişi adıdır ve şifreli saklanır. Sonra ön
          kayda dönüp “Komisyon kararını uygula” düğmesine basın:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Kabul edilen kalemleri işaretli bırakın.</li>
          <li>
            İşareti kaldırdığınız her kalem için “Ret gerekçesi” zorunludur: okul bağışçıya ne
            olduğunu buradan söyleyebilir.
          </li>
          <li>
            “Kararı uygula” dediğinizde kabul edilenler tek işlemde kataloglanır — künyeleri açılır,
            nüshaları numaralanır. Reddedilenler gerekçesiyle kayıtta kalır.
          </li>
        </ul>
        <p>
          Bu işlem <strong>geri alınamaz</strong>; onay penceresi kaç kalemin kabul, kaç kalemin ret
          edileceğini yazar. Bağış geri verildiyse ya da liste yanlış girildiyse ön kayıt “İptal et”
          ile kapatılır ve gerekçe kaydın notlarına yazılır. Bir edinime ya da bağış ön kaydına
          bağlanmış komisyon kararının türü değiştirilemez, kaydı da silinemez: listede “Kullanımda”
          rozetiyle görünür.
        </p>

        <AltBaslik>Kütüphane Politikası</AltBaslik>
        <p>
          <Ekran to="/ayarlar?tab=politika">Ayarlar → Kütüphane Politikası</Ekran> ödünç kurallarını
          tutar. Ödünç ve iade ekranları sonraki sürümde gelecek; buradaki kurallar o ekranlarda
          uygulanır.
        </p>
        <p>
          <strong>Ödünç süresi burada bir ayar değildir ve değiştirilemez.</strong> Yönetmelik
          süreyi belirlemiştir; panel bunu yalnız bilgi satırı olarak gösterir.
        </p>
        <Mevzuat kaynak={`${YONETMELIK}, md. 18/1`}>
          “Bir kitabı ödünç alma süresi on beş gündür.”
        </Mevzuat>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>“Ödünç Sınırları”:</strong> Yönetmelik öğrenciye bir defasında en fazla üç,
            öğretmene en fazla beş kitap der. Sayıları okul daha düşük tutabilir, bu üst değerlerin
            üstüne çıkamaz.
          </li>
          <li>
            <strong>“Diğer personele ödünç verilir”:</strong> Yönetmelik ödünç servisinde öğrenci
            ile öğretmeni sayar, diğer personeli saymaz. Seçeneği açarsanız “Müdürlük kararı tarihi”
            ve “Müdürlük kararı sayısı” zorunludur: okul bu kararı kendi sorumluluğunda alır.
          </li>
          <li>
            <strong>“Gecikmiş kitabı olana yeni ödünç verilmez”:</strong> okulun tercihidir;
            kapatılabilir.
          </li>
          <li>
            <strong>“İade tarihi öğrenciye kapalı günlerde kaydırılır”:</strong> ara tatil ve
            yarıyıl için geçerlidir ve okulun tercihidir (bkz. Kapalı Günler). Resmî tatil, dini
            bayram ve hafta sonu kaydırması bu ayardan bağımsızdır, her zaman uygulanır.
          </li>
          <li>
            <strong>“Yıl sonu son ödünç tarihi”</strong> ve{" "}
            <strong>“Son sınıflar için son ödünç tarihi”:</strong> bu tarihlerden sonra yeni ödünç
            verilmez. İkincisi isteğe bağlıdır, mezun olacak sınıflar için daha erken bir tarih
            yazmanızı sağlar.
          </li>
          <li>
            <strong>“Çok okunanlar için en az üye sayısı”:</strong> bir eser çok okunanlar listesine
            ancak en az bu kadar farklı üye ödünç aldıysa girer; sayı hiçbir yerde gösterilmez.
          </li>
          <li>
            <strong>Saklama süreleri:</strong> üyelik sonlandıktan, ödünç iade edildikten, kayıp ya
            da hasar dosyası kapandıktan ve teslim geri alındıktan kaç yıl sonra kaydın kişiyle bağı
            koparılacağını belirler.
          </li>
        </ul>
        <Ipucu>
          <p>
            Ödünç kaydı bir başarı ya da okuma ölçüsü değildir: öğrenci bazlı ödünç sayısı öğretmene
            ya da e-Okul&apos;a aktarılmaz, program not ya da başarı bilgisi tutmaz. Çok okunanlar
            listesi de sayı göstermez, yalnız sırayı verir.
          </p>
        </Ipucu>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="hizli-kayit">
        <p>Raftaki kitapları programa geçirmenin iki yolu vardır; kılavuz ikisini de anlatır:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Önce liste:</strong> kitaplar Excel&apos;de yazılır, dosya programa aktarılır,
            sonra etiketler basılıp raf raf yapıştırılır. Elinizde hazır bir liste varsa (eski bir
            defter, bir bağış listesi ya da başka bir okuldan gelen dosya) bu yol hızlıdır; aşağıda
            Katalog Excel Şablonu ve İçe Aktarma bölümlerinde anlatılır.
          </li>
          <li>
            <strong>Önce etiket:</strong> boş barkod etiketleri önceden basılıp kitaplara
            yapıştırılır; kitap elde ISBN okutulur, künye yazılır ve kitaptaki etiket okutularak
            nüsha o numarayla açılır. <strong>Okulun asıl yolu budur</strong>, çünkü okulda hazır
            bir kitap listesi yoktur ve katalog kitap kitap kurulur. Bu yolun ekranı{" "}
            <Ekran to="/katalog/hizli-kayit">Katalog → Hızlı Kayıt</Ekran>&apos;tır.
          </li>
        </ul>
        <p>
          İki yol birbirini dışlamaz: listesi olan bölümleri aktarıp gerisini kitap kitap
          girebilirsiniz. Etiketler iki yolda da{" "}
          <Ekran to="/katalog/etiketler">Katalog → Etiketler</Ekran> ekranından basılır; önce etiket
          yolunun adımları aşağıdaki Etiketler bölümünde sırasıyla anlatılır.
        </p>
        <Ipucu>
          <p>
            Geçiş dönemindeki kural: ödünç istenen etiketsiz bir kitap masaya geldiğinde onu
            bekletmeyin, Hızlı Kayıt&apos;ta “Etiket yok — yeni numara ver” seçeneğiyle o an
            kaydedip çıkan “Etiketini bas” düğmesiyle tek etiketini basın. Dönüşüm bitene kadar
            kâğıt defter açık kalır, bittiğinde kapatılır.
          </p>
        </Ipucu>

        <AltBaslik>Kitabı okutmak</AltBaslik>
        <p>
          Ekran açıldığında imleç “ISBN barkodu” kutusundadır. Kitabın arka kapağındaki ISBN
          barkodunu okutun; okuyucunuz yoksa numarayı yazıp <Tus>Enter</Tus>&apos;a ya da “Künyeyi
          getir” düğmesine basın. Nüsha açıldıktan sonra künye ve nüsha alanları boşalır ve imleç
          yeniden bu kutuya döner, böylece sıradaki kitabı doğrudan okutabilirsiniz; edinim ve bölüm
          seçiminiz korunur, çünkü aynı parti arka arkaya girilir. Yanlış bir kayda başladıysanız
          “Formu temizle” deyin.
        </p>
        <p>
          Program ne okuttuğunuzu tanır: kütüphane etiketi ya da üye kartı okutulursa kayıt
          başlamaz, “Bu bir kütüphane etiketi. Hızlı kayıtta kitabın arka kapağındaki ISBN barkodu
          okutulur.” der. “Kitaptaki etiketi okutun” seçiliyken bu kutuya etiket okutursanız program
          önce ISBN barkodunu okutmanızı, etiketi de “Kütüphane etiketi” kutusuna okutmanızı söyler.
        </p>
        <AltBaslik>Künye nereden gelir</AltBaslik>
        <p>
          <strong>ISBN ile künye getirme</strong> açıksa program numarayı iki dış katalogda arar ve
          künye <strong>önerisi</strong> getirir: önce Kültür ve Turizm Bakanlığı&apos;nın halk
          kütüphaneleri kataloğuna, orada bulunamazsa Open Library&apos;ye bakar. Öneri bir kaynak
          ve tarih etiketiyle (“Bakanlık kataloğu, 23.09.2026”) ve “Dış kaynaktan alındı,
          doğrulayın” rozetiyle gelir. Her alanın yanında bir kutu vardır: işaretini kaldırdığınız
          alan forma yazılmaz, “Seçilenleri forma yaz” dediğinizde yalnız işaretlediğiniz alanlar
          dolar ve dolu bir alanın üzerine sessizce yazılmaz.
        </p>
        <p>
          <strong>Gelen künyeyi kitabın künye sayfasından doğrulayın.</strong> Bu kayıtlar başka
          kurumların kataloglarından gelir, okulun kendi kaydı değildir ve hatalı olabilir: Open
          Library&apos;nin Türkçe kayıtlarında düşen harfler, yanlış yayın tarihleri ve yazar
          sanılmış çevirmenler görülmüştür. <strong>Çevirmen alanı dışarıdan doldurulmaz</strong>:
          kaynaklar çevirmeni yazardan ayırmadığı için çeviri eserlerde çevirmeni siz yazarsınız.
          Aynı numarayla birden çok kayıt bulunursa program kaç kayıt bulduğunu yazar ve en
          ayrıntılısını getirir.
        </p>
        <p>
          Bir numara ikinci kez sorulduğunda program dışarıya çıkmaz, ilk gelen künyeyi gösterir ve
          “daha önce sorulduğu için yeniden sorulmadı” der. Gelen künye bozuk ya da eksikse
          <strong> “Yeniden getir”</strong> deyin: program o numarayı kaynağa yeniden sorar. Form
          doluysa gelen alanlar kendiliğinden yazılmaz; hangilerini istediğinizi işaretleyip
          “Seçilenleri forma yaz” dersiniz.
        </p>
        <p>
          Ayar <Ekran to="/ayarlar?tab=politika">Ayarlar → Kütüphane Politikası</Ekran> ekranının
          “Künye Getirme” bölümündedir: “ISBN ile künye getirme açık” anahtarı{" "}
          <strong>varsayılan olarak kapalıdır</strong> ve kaynak seçenekleri o anahtar açılmadan
          işaretlenemez. Kapalıyken program bu iş için hiçbir bağlantı kurmaz; künyeyi elle yazmak
          her koşulda tam işlevlidir. Açtığınızda dışarıya yalnız numaranın kendisi gider: okul adı,
          kitap listesi, kişi bilgisi ya da kitabın kütüphane barkodu gönderilmez. İnternet yoksa ya
          da adres kapalıysa program aksamaz, “İnternetten getirilemedi, elle girebilirsiniz.” der.
        </p>
        <Ipucu>
          <p>
            Kütüphane masasında internet yoksa ayarı kapalı bırakın. Künye eksiğini dosyayla da
            kapatabilirsiniz:{" "}
            <Ekran to="/katalog/ice-aktarma?tab=cevrimdisi">
              Katalog → İçe Aktarma → Çevrimdışı Künye
            </Ekran>{" "}
            (aşağıda anlatılır). Kurum bilgisayarına telefon ya da mobil modem bağlayarak internet
            alınmaz.
          </p>
        </Ipucu>
        <AltBaslik>Aynı kitabın ikinci nüshası</AltBaslik>
        <p>
          Okuttuğunuz numara katalogda zaten varsa program bunu söyler ve “Bu esere nüsha ekle”
          düğmesini gösterir; düğmeye bastığınızda künye formu kapanır, çünkü künye yeniden
          yazılmaz. Aynı kitabı ikinci kez kataloglamayın: künye tektir, her kitap onun bir
          nüshasıdır. Bu arama yerel kataloğunuzda yapılır, dışarıya bir şey sorulmaz.
        </p>
        <p>
          Sonra “Nüsha” bölümünde edinimi, nüsha sayısını, bölümü ve gerekiyorsa eski kayıt
          numarasını yazıp “Nüshayı aç” deyin; ders kitabı gibi ödünç verilmeyecek bir kaynaksa
          “Danışma kaynağı (ödünç verilmez)” kutusunu işaretleyin. Barkod ve kayıt numarasını
          program verir; numara asla yeniden kullanılmaz. Açılan nüshanın etiketi Etiketler → Basım
          Kuyruğu&apos;nda bekler; kitap elinizdeyse kayıttan sonra çıkan “Etiketini bas” düğmesiyle
          hemen basabilirsiniz. Etiket bekleyenleri{" "}
          <Ekran to="/katalog?tab=nushalar">Katalog → Nüshalar</Ekran> sekmesinde “Yalnız
          etiketlenmemişler” kutusuyla da görürsünüz.
        </p>
        <AltBaslik>Kitaptaki etiketi okutmak</AltBaslik>
        <p>
          Kitaplara önceden basılmış boş barkod etiketi yapıştırdıysanız “Kitabın etiketi” kartında{" "}
          <strong>“Kitaptaki etiketi okutun”</strong> seçili olsun; bağlanmamış boş etiket varken
          ekran bu seçenekle açılır. Bu yolda her etiket tek bir nüshadır, “Nüsha sayısı” sorulmaz.
          ISBN okutulduktan sonra imleç “Kütüphane etiketi” kutusuna geçer. Künye eksikse önce onu
          tamamlayın, sonra kitaba yapıştırdığınız etiketi bu kutuya okutun: okuyucunun gönderdiği
          Enter kaydı bitirir, nüsha o numarayla açılır, barkod etiketi okutulmuş sayılır ve yalnız
          sırt etiketi basılmayı bekler. Katalogda aynı ISBN&apos;li eser varsa imleç önce ISBN
          kutusunda kalır: “Bu esere nüsha ekle” deyin, imleç etiket kutusuna geçer, sonra etiketi
          okutun. Etiketi künyeyi tamamlamadan okuttuysanız kod kutuda seçili kalır; künyeyi
          tamamlayıp etiketi yeniden okutunca eski kod silinir, yenisi yazılır.
        </p>
        <p>
          Program etiketi eseri açmadan önce denetler: numara boş barkod aralığından değilse, başka
          bir kitaba bağlıysa ya da iptal edildiyse nedenini söyler ve eser açılmaz. Etiket zaten
          kayıtlı bir nüshanınsa elinizdeki kitap büyük olasılıkla o nüshadır: kitabı yeniden
          kaydetmeyin; başka bir kitapsa etiketi sökün ve boş bir etiket yapıştırın. Kitapta etiket
          yoksa <strong>“Etiket yok — yeni numara ver”</strong> seçeneğine geçin. Kayıttan sonra
          çıkan “Sırt etiketini bas” düğmesi o kitabın sırt etiketini hemen basmanızı sağlar; önce
          etiket yolunun bütün adımları aşağıdaki Etiketler bölümündedir.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="etiketler">
        <p>
          <Ekran to="/katalog/etiketler">Katalog → Etiketler</Ekran> ekranı kitapların sırt ve
          barkod etiketlerini basar, basılanı kayda geçirir ve yapıştırılan etiketi okutarak
          doğrular. Beş sekmesi vardır: Basım Kuyruğu, Basım Geçmişi, Boş Barkod Aralığı, Doğrulama
          Okutması, Şablonlar ve Kalibrasyon. Sayfanın üstündeki sayaçlar (“Sırt etiketi bekleyen”,
          “Barkod etiketi bekleyen”, “Doğrulanmamış etiket”, “Bağlanmamış boş etiket”) tıklanınca
          ilgili sekmeyi açar. Basıldı olarak işaretlenmemiş bir basım partisi varsa sayaçların
          üstünde uyarı durur.
        </p>

        <AltBaslik>Etiket türleri</AltBaslik>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Sırt etiketi</strong> kitabın rafta nereye döneceğini söyler. Yer numarasının
            boşlukla ayrılmış parçaları alt alta basılır: “813.54 STE” iki satır olur; cilt ya da
            nüsha bilgisini yer numarasının sonuna yazarsanız (“894.3533 ALİ 2. cilt”) üçüncü satıra
            geçer. Altında okulun kısa adı yazar. Yer numarası çıkarılamayan kitabın sırtına çizgi
            (—) basılır; böyle bir kitabın sırt etiketini künyesi tamamlandıktan sonra basın.
          </li>
          <li>
            <strong>Barkod etiketi</strong> masada okutulan kütüphane etiketidir: barkodu, okunur
            numarası (“2026-000123”), yer numarasını, kısaltılmış kaynak adını ve okulun kısa adını
            taşır.
          </li>
          <li>
            <strong>Boş barkod etiketi</strong> önce etiket yolunda, kitap kataloğa girmeden
            basılır: üzerinde yalnız barkod, okunur numara ve okulun kısa adı vardır, kitaba ait
            bilgi yoktur.
          </li>
        </ul>
        <p>
          Okulun kısa adı <Ekran to="/ayarlar?tab=okul">Ayarlar → Okul Bilgileri</Ekran>
          &apos;ndeki “Kısa ad” alanından gelir; en çok 24 karakterdir. Etiket basmadan önce bu
          alanı doldurun.
        </p>

        <AltBaslik>Etiket nereye yapıştırılır</AltBaslik>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Sırt etiketini bütün kitaplarda sırtın alt kenarından aynı yüksekliğe yapıştırın: rafta
            yer numaraları bir hizada okunur.
          </li>
          <li>
            Sırtı dar kitaplarda (ince çocuk kitapları, broşürler) sırt etiketi sırta sığmaz; onu ön
            kapağa, sırta yakın köşeye yapıştırın. Bütün ince kitaplarda aynı köşeyi kullanın ki
            etiket her kitapta aynı yerde aransın.
          </li>
          <li>
            Barkod etiketini de bütün kitaplarda aynı yere yapıştırın; kitabın ISBN barkodunun ve
            kapak yazısının üstüne gelmesin. Önce etiket yolunda Hızlı Kayıt&apos;ta ISBN barkodu da
            okutulur.
          </li>
        </ul>
        <Ipucu>
          <p>
            Etiketlerin üzerine şeffaf koruyucu bant yapıştırmanızı öneririz: en çok sırt etiketi
            aşınır, elden ele geçen kitapta barkod da okunmaz hâle gelir. Bandı yapıştırdıktan sonra
            doğrulama okutmasını yapın; bant parlayıp okuyucuyu şaşırtıyorsa bunu hemen görürsünüz.
          </p>
        </Ipucu>

        <AltBaslik>Etiket tabakası seçimi ve satın alma</AltBaslik>
        <p>
          Program yaygın tabakaların hazır şablonlarıyla gelir: 38,1 × 21,2 mm ölçüsünde 65&apos;li
          tabaka (varsayılan; barkod etiketi ve sırt etiketi için aynı tabaka), 48,5 × 25,4 mm
          ölçüsünde 44&apos;lü ve 52,5 × 29,7 mm ölçüsünde 40&apos;lı tabaka. Şablonların listesi
          Şablonlar ve Kalibrasyon sekmesindedir.
        </p>
        <Ipucu>
          <p>
            <strong>Tabaka almadan önce QR kararını verin.</strong> Barkodun yanına QR eklemek
            isteğe bağlıdır ve varsayılan olarak kapalıdır. QR 65&apos;li tabakanın etiketine
            sığmaz; QR istenirse 44&apos;lü ya da 40&apos;lı tabaka alınır ve bir tabakaya daha az
            etiket düşer. QR yalnız barkod numarasını taşır, adres taşımaz. Çizgili barkodu her
            okuyucu okur, QR&apos;ı okumak için iki boyutlu (2D) okuyucu gerekir; okuyucu
            alacaksanız ikisini de okuyan iki boyutlu bir USB okuyucu önerilir.
          </p>
        </Ipucu>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Kâğıt boyu:</strong> program etiketleri 210 × 297 mm&apos;lik sayfaya dizer; bu
            boydan başka tabaka almayın.
          </li>
          <li>
            <strong>Kaç tabaka:</strong> her kitaba bir barkod ve bir sırt etiketi gider. 65&apos;li
            tabakayla 1.000 kitap için 16 barkod ve 16 sırt tabakası gerekir; bozulan etiketler için
            pay bırakın.
          </li>
          <li>
            <strong>Sırt etiketinin tabakası:</strong> raftaki kitapların sırt genişliğine bakarak
            seçin; yazı sırtın genişliğine sığmalıdır. Hazır sırt şablonu barkod tabakasıyla aynı
            65&apos;li tabakadır. Başka bir sırt tabakası alır ve iki etiketi birlikte basmak
            isterseniz o tabakanın satır ve sütun sayısı barkod tabakasınınkiyle aynı olmalıdır:
            “Sırt etiketi tabakası” seçicisi yalnız böyle tabakaları listeler. Düzeni tutmayan bir
            sırt tabakasında iki etiketi ayrı basın: önce “Barkod etiketi”, sonra “Sırt etiketi”
            içeriğiyle, aynı süzgeç ve basım sırasıyla; etiketler yine aynı kitap sırasıyla çıkar.
          </li>
          <li>
            <strong>Farklı ölçüde tabaka:</strong> Şablonlar ve Kalibrasyon sekmesinde “Yeni şablon”
            deyip tabaka kutusundaki üretici ölçülerini yazın: etiket genişliği ve yüksekliği, üst
            ve sol kenar boşluğu, sütun ve satır aralığı, satır ve sütun sayısı. Şablon kartındaki
            “QR&apos;a uygun” rozeti QR&apos;ın sığdığını, “Barkod bu etikete sığmaz” rozeti
            tabakanın barkod etiketi için küçük olduğunu gösterir.
          </li>
          <li>
            44&apos;lü şablonun kenar boşlukları yaklaşıktır (adında “yaklaşık ölçü” yazar); ilk
            basımdan önce kalibrasyon sayfasıyla denetleyin. 40&apos;lı tabaka kâğıdın kenarına
            kadar uzanır; yazıcıların çoğu ise kâğıdın kenarından 4-5 milimetreyi basamaz. Program
            bu yüzden dış sütun ve satırlardaki etiketlerde barkodu, QR&apos;ı ve yazıyı sayfa
            kenarından en az 5 mm içeride basar: içerik o etiketlerde kenardan biraz içeri kayar.
            Yazıcınızın basamadığı kenar 5 mm&apos;den genişse (yazıcının kılavuzunda “basılamayan
            alan” diye geçer) 40&apos;lı tabaka yerine kenar boşluklu bir tabaka seçin.
          </li>
        </ul>

        <AltBaslik>Kalibrasyon</AltBaslik>
        <p>
          Her yazıcı kâğıdı biraz kaydırarak basar ve bu kayma iki yazıcıda farklıdır. Kalibrasyon
          kaymayı ölçüp basıma uygular; her şablon ve yazıcı çifti için bir kez, ilk etiket
          basımından önce düz kâğıtla yapılır:
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            <Ekran to="/katalog/etiketler?tab=sablonlar">
              Etiketler → Şablonlar ve Kalibrasyon
            </Ekran>
            &apos;da kullanacağınız şablonun “Kalibrasyon” düğmesine basın. “Sayfaya uygulanacak
            kayma” seçicisi “— yok —” kalsın; “PDF&apos;i indir” deyip kalibrasyon sayfasını düz
            kâğıda <strong>gerçek boyutta (%100)</strong> yazdırın. Sayfanın ortasındaki çizgi 100
            mm olmalıdır; değilse yazdırma penceresinde “sayfaya sığdır” seçeneğini kapatıp yeniden
            yazdırın.
          </li>
          <li>
            Çıktıyı etiket tabakasının üstüne koyup ışığa tutun. Dört köşe etiketinin birer dikey ve
            yatay kenarında milimetre cetveli vardır; cetvelin 0 çizgisi basılı çerçevedir. Etiketin
            gerçek kenarının cetvelde düştüğü değeri okuyun: cetvelin sağ ve alt tarafı artı, sol ve
            üst tarafı eksidir. Yazıcı kâğıdın kenarından birkaç milimetreyi basamadığı için kâğıt
            kenarına yakın cetvel etiketin iç kenarına, yan etiketle arasındaki kesime konur; okuma
            kuralı aynıdır. Etiketler arasında boşluk olan tabakada bu cetvelde yan etiketin kesimi
            de görünür: cetvelin 0 çizgisindeki çerçeveye ait kesimi okuyun.
          </li>
          <li>
            “Yeni yazıcı kalibrasyonu” deyin ve “Yazıcı adı”na yazıcıyı tanıyacağınız bir ad yazın.
            Okuduğunuz değerleri işaretleriyle “Okunan yatay değer” ve “Okunan dikey değer”
            kutularına yazıp “Kaymaya ekle” deyin: değerler “Yatay kayma (mm)” ve “Dikey kayma (mm)”
            alanlarına eklenir. Artı değer sağa ve aşağı, eksi değer sola ve yukarı kaydırır;
            ondalık için virgül de nokta da kullanılabilir. Sonra “Kaydet” deyin.
          </li>
          <li>
            Kayıttan sonra “Sayfaya uygulanacak kayma” seçicisinde bu yazıcı seçili gelir; sayfayı
            yeniden indirip basın. Etiketlerin kenarı cetvelde 0&apos;a oturuyorsa kalibrasyon
            tamamdır. Oturmuyorsa “Kayıtlı yazıcılar” listesinde yazıcının “Düzenle” düğmesine basıp
            yeni okuduğunuz değeri yine “Kaymaya ekle” ile ekleyin.
          </li>
        </ol>
        <p>
          Dört köşede okunan değer aynı değilse sorun kayma değil ölçektir: yazıcı sayfayı
          küçültüyor ya da büyütüyordur; yazdırma ayarında ölçeklemeyi kapatın. Kayma en çok 10 mm
          olabilir; daha büyük bir fark çıkarsa yazdırma penceresinde kâğıt boyunu (210 × 297 mm) ve
          ölçeği denetleyin, sonra şablonun ölçülerini tabakanın kutusundaki ölçülerle
          karşılaştırın.
        </p>
        <p>
          Etiket basarken “Yazıcı (kalibrasyon)” seçicisinde o an kullandığınız yazıcıyı seçin.
          Şablonun tek kayıtlı yazıcısı varsa kendiliğinden seçilir; “— yok —” seçiliyse etiketler
          kaymasız basılır. Etiketi başka bir yazıcıda (ör. idarenin yazıcısında) basacaksanız o
          yazıcıyı da ayrıca kalibre edin: bir yazıcının kayması başka yazıcıya uymaz.
        </p>

        <AltBaslik>Basım kuyruğu ve basım sırası</AltBaslik>
        <p>
          Açılan her nüsha kendiliğinden Basım Kuyruğu&apos;na girer; etiketi basıldı olarak
          işaretlenince kuyruktan çıkar. “Etiket içeriği” seçicisi ne basılacağını söyler: “Sırt ve
          barkod etiketi” iki etiketi de basılmamış nüshaları, “Barkod etiketi” ve “Sırt etiketi”
          yalnız o etiketi basılmamış nüshaları gösterir. Kuyruğu “Bölüm”, “Edinim partisi”, “Boş
          barkod aralığı” ve kayıt tarihine göre süzebilirsiniz. İçe Aktarma&apos;nın sonucundaki
          “Bu partinin etiketlerini bas” düğmesi kuyruğu o edinim partisine süzülmüş açar.
        </p>
        <p>“Basım sırası” üç türlüdür:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Yer numarası</strong> (varsayılan): etiketler raftaki sırayla çıkar, raf raf
            yapıştırılır. Yer numarası olmayan nüshalar sona düşer.
          </li>
          <li>
            <strong>İçe aktarma sırası</strong>: nüshaların kayda girdiği sıradır. Excel aktarımında
            dosyanın satır sırası, Hızlı Kayıt&apos;ta kitapların masadan geçtiği sıradır.
          </li>
          <li>
            <strong>Barkod</strong>: numara sırası.
          </li>
        </ul>
        <p>
          “Sırt ve barkod etiketi” birlikte basılırken PDF&apos;te önce sırt tabakaları, sonra
          barkod tabakaları gelir. İkisi aynı sıra ve hücre düzeninde çıkar: iki tabakanın aynı
          hücresi aynı kitabındır, barkod etiketindeki kaynak adı sırt etiketinin hangi kitaba
          gideceğini gösterir. Bir partiye en çok 1.300 nüsha girer; kuyruk daha uzunsa kalanlar
          kuyrukta kalır ve bir sonraki parti kaldığı yerden devam eder.
        </p>

        <AltBaslik>Basmak ve “Basıldı olarak işaretle”</AltBaslik>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Basım Kuyruğu&apos;nda basılacak nüshaları seçin; seçim yapmazsanız süzgece uyan kuyruk
            seçilen sırayla basılır.
          </li>
          <li>
            “Basım Ayarları”nda “Etiket şablonu”nu ve “Yazıcı (kalibrasyon)”u seçin. Kısmen
            kullanılmış bir tabakaya basacaksanız tabakanın küçük resminde ilk boş hücreye tıklayın
            ya da numarasını “Başlangıç hücresi” kutusuna yazın: hücreler satır satır, soldan sağa
            sayılır ve ondan önceki hücreler boş bırakılır. Ekran kaç etiket ve kaç tabaka
            basılacağını yazar.
          </li>
          <li>
            “Basım partisini hazırla” deyin. Hazırlanan partinin kartında “Önizle” ile bakın,
            “PDF&apos;i indir” ile alıp gerçek boyutta (%100) yazdırın.
          </li>
          <li>
            Tabakayı denetleyin. Etiketler hücrelere düzgün oturduysa “Basıldı olarak işaretle”
            deyin ve onaylayın; nüshalar kuyruktan çıkar.
          </li>
        </ol>
        <p>
          <strong>PDF&apos;i almak “basıldı” saymaz.</strong> “Önizle” ve “PDF&apos;i indir” hiçbir
          işarete dokunmaz; PDF&apos;i istediğiniz kadar yeniden alabilirsiniz. Yazıcı sıkışır,
          kâğıt ters takılır ya da PDF hiç yazdırılmazsa nüshalar kuyrukta kalır; işaretlenmeyen
          parti Basım Geçmişi&apos;nde “Basım onayı bekliyor” olarak durur ve nüshaları kuyrukta
          “Onay bekleyen partide” rozetiyle görünür. Aynı etiketi iki kez basmamak için yeni parti
          hazırlamadan önce o partiyi işaretleyin; hiç basmadıysanız “Partiden vazgeç” deyin.
        </p>
        <p>
          Bir tabaka sonradan hatalı çıktıysa{" "}
          <Ekran to="/katalog/etiketler?tab=gecmis">Etiketler → Basım Geçmişi</Ekran>&apos;nde
          partinin satırına tıklayıp “Basım işaretini geri al” deyin: nüshaların işareti bu basımdan
          önceki hâline döner (etiketi ilk kez basılan nüshalar kuyruğa geri gelir), parti iz olarak
          kalır. Okutularak doğrulanmış etiketlerin işareti korunur, çünkü o etiketler kitabın
          üzerindedir: sırt ve barkod etiketi partisinde barkodu okutulmuş nüshanın sırt işareti de
          korunur ve nüsha hiçbir kuyruğa dönmez. Partideki nüshaların etiketi sonradan başka bir
          partiyle yeniden basıldıysa ve o parti hâlâ basılmış görünüyorsa program önce o partinin
          işaretini geri almanızı ister.
        </p>
        <p>
          Partideki bir nüsha sonradan silinir ya da kayıttan düşülürse partinin PDF&apos;i yine
          alınır: o nüshanın hücresi boş kalır, sonraki etiketler kaymaz. “Nüshaları göster”
          listesinde böyle nüshanın yanında “PDF&apos;te hücresi boş kalır” yazar; “Basıldı olarak
          işaretle” ona dokunmaz, “Yeniden bas” onu yeni partiye almaz.
        </p>
        <p>
          “Yeniden bas” aynı nüshaları aynı sırayla yeni bir partide basar; yalnız bozulan içeriği
          (ör. yalnız barkod etiketini), başka bir şablonu, yazıcıyı ya da başlangıç hücresini
          seçebilirsiniz. Yeni parti de aynı kuralla işaretlenir. Barkod etiketi içeren bir parti
          basıldı olarak işaretlenince o nüshaların doğrulaması sıfırlanır: yeni etiket henüz
          okutulmamıştır. “Nüshaları göster” partinin nüshalarını tabakadaki sırasıyla listeler.
        </p>

        <AltBaslik>Yapıştırma ve doğrulama okutması</AltBaslik>
        <p>
          Etiketleri raf raf yapıştırın: yer numarası sırasında basılan tabaka raftaki sırayı izler.
          Sonra <Ekran to="/katalog/etiketler?tab=dogrulama">Etiketler → Doğrulama Okutması</Ekran>
          &apos;nı açın ve yapıştırdığınız her barkod etiketini “Kütüphane etiketi” kutusuna okutun.
          Okunan etiket doğrulanır; kutu her okutmadan sonra boşalır ve imleç kutuda kalır,
          kitapları arka arkaya okutabilirsiniz. Yanlış bir şey okutursanız program söyler: kitabın
          ISBN barkodu, üye kartı, henüz bir kitaba bağlanmamış ya da numarası iptal edilmiş boş
          etiket ve basıldı olarak işaretlenmemiş nüsha ayrı iletilerle ayrılır. Okutmayı masadaki
          görevli de yapabilir: görevli kipinde “Görevli Kipi” sayfasındaki “Doğrulama okutmasını
          aç” düğmesiyle açılır, “Okutmayı bitir” ile kapanır; ekranda yalnız okutulan etiketin
          numarası ve kaynak adı görünür, yönetici işi gerektiren etiket için görevliye kitabı
          ayırıp kütüphane yöneticisine göstermesi söylenir.
        </p>
        <p>
          Doğrulama barkod etiketi içindir; sırt etiketinde barkod yoktur, okutulmaz. Önce etiket
          yolunda kaydedilen kitapların barkod etiketi kayıt sırasında okutulduğu için doğrulanmış
          sayılır. Okutulmayan etiketler “Doğrulanmamış Etiketler” listesinde kalır; listede kalan
          kitabın etiketi ya yapıştırılmamıştır ya da okunmuyordur. Önce kitabı bulup etiketini
          yeniden okutmayı deneyin. Etiket yoksa ya da bozuksa etiketini Basım Geçmişi&apos;nden
          yeniden basın. “Yeniden bas” partideki bütün nüshaların etiketini basar ve yeni parti
          işaretlenince o nüshaların hepsi doğrulanmamış sayılır; numara değişmediği için
          kitaplardaki eski etiketleri okutmak onları yeniden doğrular.
        </p>
        <Ipucu>
          <p>
            Okutma kutusu odakta değilse ekranda uyarı çıkar; “Kutuya dön” deyin. Okuyucu klavye
            gibi yazar: imleç başka bir yazı kutusundayken okuttuğunuz kod oraya yazılır. İmleç
            hiçbir yazı kutusunda değilse okutulan kod kendiliğinden okutma kutusuna gider.
          </p>
        </Ipucu>

        <AltBaslik>Önce etiket yolu adım adım</AltBaslik>
        <p>
          Okulun asıl yolu budur: kitaplar kataloğa girmeden önce boş barkod etiketleri basılıp
          kitaplara yapıştırılır, künye kitap elde girilir.
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            <strong>Numara ayırın.</strong>{" "}
            <Ekran to="/katalog/etiketler?tab=bos-barkod">Etiketler → Boş Barkod Aralığı</Ekran>
            &apos;nda “Numara Ayır” kartının “Adet” kutusuna kaç etiket istediğinizi yazın
            (tabakanın katları kâğıt israfını önler; bir seferde en çok 1.300). “Açıklama”ya
            etiketlerin nerede kullanılacağını yazabilirsiniz (ör. hangi raf; kişi adı yazmayın).
            “Numara ayır” deyip onaylayın. Numaralar kütüphanenin tek sayacından sırayla alınır;
            ayrılan numara başka hiçbir kitaba verilmez.
          </li>
          <li>
            <strong>Basın.</strong> Ayırdığınız aralık “Seçilen Aralık” kartında açılır (sonra da
            listede satırına tıklayarak açarsınız). Şablonu, yazıcıyı ve başlangıç hücresini seçip
            “PDF&apos;i indir” deyin ve gerçek boyutta (%100) yazdırın; tabaka düzgünse “Basıldı
            olarak işaretle” deyin. PDF yalnız bağlanmamış ve iptal edilmemiş numaraların etiketini
            basar. Aralıktan hiçbir etiket kitaba bağlanmadıysa basım işareti geri alınabilir.
          </li>
          <li>
            <strong>Yapıştırın.</strong> Etiketleri raf başında kitaplara, bütün kitaplarda aynı
            yere ve ISBN barkodunu örtmeden yapıştırın.
          </li>
          <li>
            <strong>Kaydedin.</strong>{" "}
            <Ekran to="/katalog/hizli-kayit">Katalog → Hızlı Kayıt</Ekran>&apos;ta “Kitabın etiketi”
            kartında “Kitaptaki etiketi okutun” seçiliyken kitabın ISBN barkodunu okutun ve künyeyi
            tamamlayın. Sonra kitaba yapıştırdığınız etiketi “Kütüphane etiketi” kutusuna okutun:
            okuyucunun gönderdiği Enter kaydı bitirir, nüsha o numarayla açılır ve barkod etiketi
            okutulmuş sayılır. Bu yüzden “Nüsha” kartındaki edinim ve bölüm etiketi okutmadan önce
            seçili olsun; seçim kitaptan kitaba korunur. Raftaki eski kitaplar için edinimi önceden{" "}
            <Ekran to="/katalog/edinimler">Edinimler ve Bağışlar</Ekran>&apos;da “Mevcut koleksiyon
            (programa aktarım)” yoluyla açın. Aynı kitaptan birden çok nüsha varsa her birini kendi
            etiketiyle ayrı ayrı kaydedin.
          </li>
          <li>
            <strong>Sırt etiketlerini basın.</strong> Bu kitapların sırt etiketleri Basım
            Kuyruğu&apos;nda “Sırt etiketi” içeriğiyle birikir. Aralığın kartındaki “Sırt
            etiketlerini bas” bağlantısı kuyruğu o aralığa süzülmüş açar. Kitaplar masadan
            geçtikleri sırayla duruyorsa “İçe aktarma sırası”nı, rafa yer numarasıyla dizildiyse
            “Yer numarası”nı seçin. Sırt etiketinde barkod yoktur: yer numarasına bakarak doğru
            kitaba yapıştırın.
          </li>
          <li>
            <strong>Kullanılmayanları iptal edin.</strong> Bozulan etiket elinizdeyse numarasını
            aralığın “Numaralar” tablosunda seçip PDF&apos;i yeniden alın: yalnız o numaranın
            etiketi basılır, bozuk etiketi atın. Kaybolan ya da artan etiketlerin numaralarını seçip
            “Seçilenleri iptal et” deyin; bütün kitaplar kaydedildikten sonra kalanlar için
            “Bağlanmamış bütün numaraları iptal et” düğmesi vardır. Onay penceresinde “Bu
            numaraların etiketlerinin kitaplara yapıştırılmadığını denetledim.” kutusunu
            işaretlemeden iptal düğmesi açılmaz. İptal geri alınmaz ve numara sayaca dönmez;
            kaybolan etiket bir gün bir kitapta çıkar da okutulursa program numaranın iptal
            edildiğini söyler: etiketi sökün ve kitaba başka bir boş etiket yapıştırın.
          </li>
        </ol>
        <Ipucu>
          <p>
            Bağlanmamış görünen bir numaranın etiketi rafta bir kitaba yapıştırılmış, kitap henüz
            kaydedilmemiş olabilir. Toplu iptali yalnız o aralığın bütün kitapları Hızlı
            Kayıt&apos;tan geçtikten sonra yapın.
          </p>
        </Ipucu>

        <AltBaslik>Etiketi olmayan kitap</AltBaslik>
        <p>
          Masaya etiketsiz bir kitap gelirse Hızlı Kayıt&apos;ta “Etiket yok — yeni numara ver”
          seçeneğiyle kaydedin: program sayaçtan yeni numara verir. Kayıttan sonra çıkan “Etiketini
          bas” düğmesi aynı ekranda “Etiket Basımı” kartını açar: “Etiket içeriği”ni, şablonu ve
          başlangıç hücresini seçip “Basım partisini hazırla” deyin, PDF&apos;i yazdırıp “Basıldı
          olarak işaretle” deyin. Kısmen kullanılmış tabakada ilk boş hücreyi seçmeniz yeterlidir.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="katalog-sablonu">
        <p>
          Çok sayıda kitabı tek tek yazmak yerine listenizi Excel&apos;de hazırlayabilirsiniz;
          hazırladığınız dosyayı sonra İçe Aktarma ekranından kataloğa alırsınız. Şablonu{" "}
          <Ekran to="/">Genel Bakış</Ekran>&apos;taki “Katalog Excel Şablonu” kartında (ya da
          Başlangıç Yol Haritası&apos;nda) “Şablonu indir” düğmesiyle alın; aynı dosya İçe Aktarma
          ekranının sağ üstündeki “Katalog Excel şablonu” düğmesinden de iner. Dosyanın adı
          indirildiği günün tarihini taşır.
        </p>
        <p>
          Şablonda üç sayfa vardır: <strong>Katalog</strong> kitapları yazacağınız sayfadır ve
          program yalnız onu okur; <strong>Sütunlar</strong> her sütuna ne yazılacağını anlatır;{" "}
          <strong>Örnek</strong> doldurulmuş birkaç satır gösterir, içe aktarılmaz.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Birinci satırdaki sütun adlarını silmeyin, değiştirmeyin; kullanmadığınız sütunu boş
            bırakın.
          </li>
          <li>
            Tek zorunlu sütun <strong>Eser Adı</strong>&apos;dır.
          </li>
          <li>
            Bir eserin nüshalarını iki yoldan biriyle yazın: eseri bir kez yazıp{" "}
            <strong>Nüsha Sayısı</strong>&apos;na kaç tane olduğunu yazın (bir satırda en çok 50) ya
            da her nüshayı ayrı satıra yazın. Kitapların üzerinde eski kayıt numarası varsa,
            nüshalar farklı bölümlerde duruyorsa ya da biri danışma kaynağıysa ayrı satır gerekir.
          </li>
          <li>
            <strong>Danışma Kaynağı</strong> sütununa “Evet” yazılan nüsha ödünç verilmez,
            kütüphanede okunur. Kaynak türü ya da konusu “Ders kitabı” olan eser de danışma kaynağı
            sayılır.
          </li>
          <li>
            Sınıflama Kodu, ISBN ve Eski Kayıt No sütunları metin biçimindedir; başka bir dosyadan
            kopyaladığınızda değerlerin sayıya dönüşmediğini denetleyin.
          </li>
        </ul>
        <Ipucu>
          <p>
            Listeye kişisel veri yazılmaz: öğrenci, öğretmen ya da bağışçı adı bu dosyaya girmez.
            Dosyayı Excel çalışma kitabı olarak kaydedin ve çalışırken ara ara yedeğini alın.
          </p>
        </Ipucu>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="ice-aktarma">
        <p>
          Hazır listeyi kataloğa almak{" "}
          <Ekran to="/katalog/ice-aktarma">Katalog → İçe Aktarma</Ekran> ekranındadır. Dört sekmesi
          vardır: <strong>Excel Aktarımı</strong>, <strong>Yapay Zekâ Köprüsü</strong>,{" "}
          <strong>Çevrimdışı Künye</strong> ve <strong>Aktarım Geçmişi</strong>.
        </p>
        <AltBaslik>Excel aktarımı: önce önizleme</AltBaslik>
        <p>
          Dosyayı seçip “Önizle” deyin. Önizleme <strong>hiçbir kayıt yazmaz</strong> ama işin
          kendisini prova eder: ekrandaki sayılar uygulamanın gerçekten yazacağı sayılardır. Üstteki
          kutular toplamı verir; “Satır listesi”ni açtığınızda her satırın “Durum” sütununda ne
          olacağı yazar:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Yeni eser</strong> — katalogda karşılığı yok, künye açılacak;
          </li>
          <li>
            <strong>Mevcut esere nüsha</strong> — künye katalogda var, yalnız nüsha eklenecek;
          </li>
          <li>
            <strong>Şüpheli</strong> — katalogdaki bir esere benziyor ama tam eşleşmiyor; bu satır
            karar bekler;
          </li>
          <li>
            <strong>Aktarılmadı</strong> — satır okunamadı (ör. kaynak adı boş); gerekçesi “Notlar”
            sütunundadır.
          </li>
        </ul>
        <p>
          Program iki eksiği tek tek sorar; ikisi de giderilmeden “Uygula” düğmesi açılmaz ve ekran
          neyin eksik olduğunu yazar:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>“Karar bekleyen satırlar”:</strong> şüpheli her satır için “Yeni eser aç” ya da
            benzeyen kayıtlardan birini seçersiniz (“… eserine nüsha ekle”). Aynı dosyanın başka bir
            satırına da bağlayabilirsiniz. Kararları verdikten sonra “Yeniden önizle” deyin.
          </li>
          <li>
            <strong>“Bölüm listesinde bulunmayan değerler”:</strong> dosyadaki “Bölüm” değeri
            kontrollü listede yoksa karşılığı sorulur; var olan bir bölümü seçer ya da “Yeni bölüm
            aç” dersiniz. Değer karşılıksız kaldığı sürece aktarım yazmaz — kitabın rafta nerede
            durduğu bilgisi kaybolmasın.
          </li>
        </ul>
        <p>
          Önizleme ayrıca tanınmayan sütun başlıklarını, dosyada bulunmayan sütunları,{" "}
          <strong>ders kitabı olduğu için danışma kaynağı sayılan</strong> satırları (“Danışma
          Kaynağı” sütunu boş bırakılmış olanlar; bu nüshalar ödünç verilmez) ve sınıflama kodu
          “tahmini” işaretlenen satırları sayar.
        </p>
        <p>
          Eksik kalmadıysa “Açılacak Edinim Partisi” bölümünde edinim yolunu ve tarihi seçip
          “Uygula” deyin. Aktarılan bütün nüshalar tek bir edinim partisinden doğar; uygulamadan
          sonra kaç nüsha açıldığı ve barkodların hangi iki numara arasında olduğu yazılır. Bu
          nüshaların hiçbiri etiketli değildir: “Bu partinin etiketlerini bas” düğmesi Etiketler →
          Basım Kuyruğu&apos;nu bu edinim partisine süzülmüş açar. Yer numarası sırasında basıp raf
          raf yapıştırın (bkz. Etiketler bölümü).
        </p>
        <p>
          Toplu aktarımda program <strong>internetten künye getirmez</strong>: dosyada ne yazıyorsa
          o aktarılır. Künye eksiğini sonradan Hızlı Kayıt ekranından ya da aşağıdaki Çevrimdışı
          Künye yolundan tamamlarsınız.
        </p>
        <Ipucu>
          <p>
            <strong>Aynı dosya ikinci kez uygulanamaz.</strong> Program dosyanın içeriğini tanır ve
            “Bu dosya … tarihinde zaten aktarıldı” der; yoksa kitaplar kayda iki kez girerdi. Yeni
            kitaplar için yalnız onları içeren bir dosya hazırlayın.
          </p>
        </Ipucu>
        <AltBaslik>Çevrimdışı künye: dosyayla gidip gelen bilgi</AltBaslik>
        <p>
          Kütüphane masasında internet yoksa künye eksiğini dosyayla kapatabilirsiniz. “ISBN
          listesini indir” deyin: program künyesi eksik eserlerin listesini{" "}
          <strong>ISBN Künye Listesi</strong> adıyla indirir. Boş hücreleri internete bağlı{" "}
          <strong>başka bir cihazda</strong> doldurun ve dosyayı aynı sekmedeki “Doldurulmuş dosya”
          kutusundan geri yükleyin. “Eser No” ve “ISBN” sütunlarını değiştirmeyin: eşleşme o iki
          sütundan yapılır. Dosyada çevirmen sütunu yoktur; çeviri eserlerde çevirmeni programda
          elle yazarsınız.
        </p>
        <p>
          Program önce önizleme gösterir ve hiçbir kaydı değiştirmez: her alanın kendi kutusu
          vardır, <strong>dolu alanlar işaretsiz gelir</strong> — yani mevcut künyenin üzerine
          sessizce yazılmaz. “Seçilenleri kaydet” dediğinizde yalnız işaretlediğiniz alanlar
          eserlere yazılır. Dosyaya öğrenci, veli ya da personel bilgisi yazılmaz; dosya yalnız
          kitap künyesi taşır.
        </p>
        <Mevzuat kaynak={`${YONERGE}, md. 11/18`}>
          “Bakanlık merkez ve taşra teşkilatında tanımı Başkanlık tarafından yapılan MEBNET ağı
          dışında bir ağ kullanılamaz. Kullanıcı Bakanlık merkez ve taşra teşkilatında bulunan
          bilgisayarlardan MEBNET ağı dışında cep telefonu, ADSL, VDSL, fiber, mobil modem, kişisel
          erişim noktası, kablosuz bağlantı alanı cihazı vb. cihazlarını kullanamaz.”
        </Mevzuat>
        <p>
          Bu yüzden “başka cihaz” gerçekten ayrı bir cihazdır: okul bilgisayarına telefon ya da
          mobil modem bağlayarak internet alınmaz. Dosyayı taşınabilir bellekle taşırken
          Yönerge&apos;nin taşınabilir bellek kuralları geçerlidir.
        </p>
        <AltBaslik>Yapay zekâ köprüsü: isteğe bağlı ve dikkatli kullanılır</AltBaslik>
        <p>
          Bu sekme <strong>isteğe bağlıdır</strong>; kullanmadan da katalog kurulur. Dağınık bir
          listeniz varsa (başlıksız bir tablo, karışık satırlar) köprü sekmesindeki “Komut metni”
          kutusu işe yarar: “Komutu kopyala” deyip metni kullandığınız araca yapıştırır, listenizi
          de altına eklersiniz; aracın verdiği metni “Yapay zekâ aracının verdiği JSON” kutusuna
          yapıştırıp aynı önizlemeden geçirirsiniz.{" "}
          <strong>Program hiçbir yapay zekâ servisine bağlanmaz</strong> ve bu iş için internete
          çıkmaz; metni bir yerden bir yere siz taşırsınız.
        </p>
        <p>
          <strong>Listeye kişisel veri yazılmaz:</strong> öğrenci, veli, personel ya da bağışçı adı
          bu listeye girmez, köprüye yalnız kitapların künye bilgileri verilir.
        </p>
        <p>
          Bu adımda okulun kitap listesi dışarıya çıkar; ekrandaki uyarılar bunu ve Yönerge&apos;yle
          çatışabileceğini söyler. Asıl yol Excel ile içe aktarmadır; künye eksiğini kapatmak için
          ISBN ile künye getirme daha güvenlidir, çünkü orada dışarıya yalnız kitabın arka
          kapağındaki numara çıkar.
        </p>
        <p>
          <strong>Aktarım Geçmişi</strong> sekmesinde hangi dosyanın ne zaman aktarıldığı yazar. Her
          önizleme de buraya bir satır bırakır; yarım kalan bir denemeyi “Önizlemeyi iptal et” ile
          düşürebilirsiniz. Uygulanmış aktarım listede kalır: aynı dosyanın ikinci kez uygulanmasını
          engelleyen iz odur.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="yedek">
        <p>
          Yönetici parolası kurulduktan sonra program her gün o günün şifreli{" "}
          <strong>günlük yedeğini</strong> alır (aynı gün ikinci yedek almaz) ve son 14 günün
          yedeklerini saklar. Program yeni bir sürüme güncellendiğinde, veritabanını güncellemeden
          önce ayrıca bir yedek alır. Yedekler güçlü şifrelemeyle korunur; yalnız yönetici
          parolasıyla ya da kurtarma anahtarıyla açılır.
        </p>
        <Ipucu>
          <p>
            Program tepside günlerce açık kalsa da <strong>gün değişince</strong> o günün yedeğini
            alır: program açılışta ve açık kaldığı sürece saatte bir tarihi denetler (bkz. “Tepsi,
            Çıkış ve Gün Değişimi”). Bilgisayar kapalıyken yedek alınmaz; bilgisayar açıldığında ilk
            iş o günün yedeğidir.
          </p>
        </Ipucu>
        <p>
          Otomatik yedekler bu bilgisayardadır; disk bozulursa onlar da gider. Ayda bir{" "}
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>&apos;teki “Şifreli Veritabanı
          Yedeği” kartından “Şifreli yedeği indir” düğmesiyle yedek alıp USB belleğe kopyalayın ve
          belleği bilgisayardan ayrı saklayın. Yedeği bulut depolama hizmetine yüklemeyin (Yönerge
          md. 11/23).
        </p>

        <AltBaslik>Yedekten geri yükleme</AltBaslik>
        <p>
          Yanlış veri girişinden sonra eski bir güne dönmek için Ayarlar → Güvenlik&apos;teki
          “Yedekten Geri Yükleme” kartında günlük yedeklerden birini seçin ya da elinizdeki yedek
          dosyasını yükleyin. Yedeğin alındığı dönemdeki yönetici parolasını ya da kurtarma
          anahtarını yazıp “Geri yükle”ye basın. O yedekten sonra girilen kayıtlar kalkar. Mevcut
          veritabanı silinmez, veri klasöründe <Kod>db-onceki-…</Kod> adıyla kenara alınır. İşlemden
          sonra gelen “Programı kapatıp yeniden açın” ekranındaki “Programdan çık” düğmesiyle (ya da
          tepsideki simgeden “Çık”ı seçerek) programı kapatın ve yeniden açın; pencerenin çarpı
          düğmesi programı kapatmaz. Ağ Kataloğu açıksa geri yükleme sırasında kapanır. Program
          yeniden açılınca Ağ Kataloğunun ayarı geri yüklenen yedekten okunur: yedekte katalog
          açıksa kendiliğinden kalkar; değilse Ayarlar → Ağ Kataloğu&apos;ndan yeniden açın ve Ağ
          Doktoru&apos;nda beş denetimin geçtiğini görün (yedekteki port farklıysa güvenlik duvarı
          kuralı da güncellenmelidir).
        </p>
        <p>
          Program hiç açılmıyorsa Windows&apos;ta Başlat menüsündeki “Kütüphane Defteri — Yedekten
          Geri Yükle” kısayolunu, Pardus&apos;ta uçbirimden{" "}
          <Kod>kutuphane-defteri --geri-yukle</Kod> komutunu kullanın. Program tepsideyse önce
          tepsideki simgeden “Çık”ı seçin.
        </p>

        <AltBaslik>Kurtarma anahtarını yenilerseniz</AltBaslik>
        <p>
          Kurtarma anahtarı kaybolduysa ya da kurulumda kaydedilemediyse{" "}
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>&apos;teki “Kurtarma
          Anahtarını Yenile” kartından yönetici parolanızı girip yenisini üretirsiniz. Kayıtlar
          yeniden şifrelenmez, yönetici parolası ve numaralar değişmez; yalnız anahtarın açtığı
          kilit yenilenir. Yeni anahtar bir kez gösterilir: onu da saklayıp doğrulayın.
        </p>
        <p>
          <strong>Eski kâğıdı hemen atmayın.</strong> Her yedek, alındığı günün güvenlik dosyasını
          içinde taşır. Yenilemeden önce alınmış bir yedek:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            bu bilgisayarda (güvenlik dosyası yerindeyken) <strong>yeni</strong> kurtarma
            anahtarıyla ya da güncel yönetici parolasıyla açılır;
          </li>
          <li>
            başka bir bilgisayarda ya da güvenlik dosyası kaybolduğunda yalnız <strong>eski</strong>{" "}
            kurtarma anahtarıyla (ya da o dönemin yönetici parolasıyla) açılır.
          </li>
        </ul>
        <p>
          Bu yüzden USB bellekteki eski yedekler duruyorsa eski kâğıdı “Eski anahtar — [tarih]
          öncesi yedekler için” diye işaretleyip ayrı saklayın. Bu bilgisayarda eski bir yedeği geri
          yüklerken güncel parolayı ya da yeni anahtarı kullanın: eski anahtarla geri yüklerseniz
          güvenlik dosyası da yedeğin dönemine döner ve kilidi yeniden eski anahtar açar.
        </p>
        <Ipucu>
          <p>
            Yenileme, başkasının eline geçmiş bir anahtara karşı koruma değildir: kayıtların
            anahtarı değişmez; eski yedekler ve veri klasöründe <Kod>guvenlik-arsiv-…</Kod> adıyla
            saklanan önceki güvenlik dosyası eski anahtarla açılabilir. Anahtarın başkasının eline
            geçtiğini düşünüyorsanız yönetici parolasını da değiştirin ve eski yedekleri gözden
            geçirin.
          </p>
        </Ipucu>

        <AltBaslik>Güvenlik dosyası bulunamazsa</AltBaslik>
        <p>
          Kayıtların anahtarı, veri klasöründeki güvenlik dosyasında (<Kod>guvenlik.json</Kod>)
          durur. Veri klasörü Windows&apos;ta <Kod>%LOCALAPPDATA%\KutuphaneDefteri\data</Kod>,
          Pardus&apos;ta <Kod>~/.local/share/kutuphane-defteri/data</Kod> klasörüdür. Dosya silinir,
          adı değişir ya da içi bozulursa (ör. Not Defteri&apos;nde açılıp kaydedilirse) program
          “Güvenlik dosyası bulunamadı ya da okunamıyor” ekranını gösterir: kayıtlar açılmaz, yeni
          parola da kurulamaz. Sırasıyla:
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Dosyanın sağlam bir kopyası varsa (ör. bilgisayar taşınırken alınan veri klasörü)
            dosyayı veri klasörüne geri koyun ve “Yeniden denetle” düğmesine basın.
          </li>
          <li>
            Kopya yoksa aynı ekrandan bir yedeği geri yükleyin: her yedek güvenlik dosyasını da
            içinde taşır ve geri yükleme dosyayı yeniden oluşturur.
          </li>
          <li>
            Veritabanında hiç kişi kaydı yoksa ve yedek klasöründe yedek bulunmuyorsa ekranda
            “Güvenlik dosyasını sıfırla ve kuruluma dön” düğmesi de çıkar. Okunamayan dosya
            silinmez, “guvenlik-arsiv” adıyla kenara alınır; sihirbaz yönetici parolası adımından
            açılır ve yeni bir kurtarma anahtarı verilir. Yedek varsa düğme çıkmaz: eski kayıtlar
            yedektedir, yedekten geri yükleyin.
          </li>
        </ol>
        <p>
          Bu durumda program eski yedekleri silmez. Güvenlik dosyasını ve veri klasörünü elle
          düzenlemeyin.
        </p>
        <Ipucu>
          <p>
            Program kişisel veri alanlarını şifreler, ama bu tam disk şifrelemesi değildir: sınıf ve
            şube, üye türü ve tarihler şifrelenmez. Bilgisayarın tamamını korumak için
            Windows&apos;ta BitLocker, Pardus&apos;ta LUKS disk şifrelemesi kullanın.
          </p>
        </Ipucu>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="tepsi-ve-cikis">
        <p>
          Pencerenin çarpı düğmesi programı kapatmaz: pencere gizlenir, program saatin yanındaki
          simge alanında (tepside) çalışmayı sürdürür. Ağ Kataloğu açıksa o da hizmet vermeyi
          sürdürür. Pencereyi yeniden açmak için tepsideki simgeye tıklayın ya da menüsünden
          “Pencereyi aç”ı seçin.
        </p>

        <AltBaslik>Programdan çıkmak</AltBaslik>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Üst çubuktaki “Çık” düğmesi ya da tepsideki simgenin menüsündeki “Çık” programı düzenli
            kapatır: Ağ Kataloğu kapanır, veritabanı tek dosyada toparlanır. Bilgisayarı kapatmadan
            önce en güvenli yol budur. Dar pencerede üst çubuktaki düğmenin yalnız simgesi görünür.
          </li>
          <li>
            Yönetici kipinde ve kayıtlar kilitliyken üst çubuktaki “Çık” yalnız “Programdan çıkılsın
            mı?” diye onay ister; tepsiden seçilen “Çık” bu durumlarda onay sormadan kapatır.
          </li>
          <li>
            Görevli kipinde “Çık” <strong>yönetici parolası</strong> ister: açılan “Programdan çık”
            penceresinde “Yönetici parolası” alanını doldurup “Çık” düğmesine basın. Tepsiden
            seçilirse pencere öne gelir ve parola orada sorulur. Bu koruma masadaki görevlinin
            programı yanlışlıkla kapatmasını önler, bir güvenlik sınırı değildir.
          </li>
          <li>
            Yedekten geri yüklemeden sonra gelen “Programı kapatıp yeniden açın” ekranındaki
            “Programdan çık” düğmesi parola ve onay sormaz: programın yeniden açılması şarttır.
          </li>
          <li>
            Masaüstünde tepsi yoksa (bazı Pardus masaüstleri) çarpı düğmesi pencereyi küçültür;
            programdan çıkmanın yolu üst çubuktaki “Çık” düğmesidir.
          </li>
          <li>
            Program açıkken kurulum, güncelleme ya da kaldırma başlatılırsa kurucu programı kendisi
            düzenli kapatır. Program yarım dakika içinde kapanmazsa kurucu tepsideki simgeden “Çık”ı
            seçmenizi ister; programı zorla kapatmaz.
          </li>
        </ul>

        <AltBaslik>Tepsi menüsü</AltBaslik>
        <p>
          Menüdeki komutlar kipe göre değişir. Her durumda “Pencereyi aç”, Ağ Kataloğunun durum
          satırı (ör. “Ağ Kataloğu: açık — http://…” ya da “Ağ Kataloğu: kapalı”) ve “Çık” görünür.
          Yönetici kipinde “Ağ Kataloğunu aç” ya da “Ağ Kataloğunu kapat”, “Görevli kipine geç” ve
          “Kilitle” de vardır; katalog açıkken durum satırına tıklamak kataloğu bu bilgisayarın
          tarayıcısında okul ağındaki adresiyle açar. Görevli kipinde yalnız “Kilitle” eklenir ve
          durum satırı yalnız bilgi verir; ayar değiştiren komutlar görevli kipinde çalışmaz, eski
          bir menüden seçilseler de reddedilir. Kayıtlar kilitliyken menüde pencere, Ağ Kataloğunun
          durumu ve “Çık” kalır.
        </p>

        <AltBaslik>Oturum açılınca başlatma</AltBaslik>
        <p>
          Windows kurulumunda “Oturum açılınca Kütüphane Defteri&apos;ni başlat” seçildiyse program,
          kurulumun başlatıldığı hesapta (kütüphane masası hesabı) oturum açılınca kilit ekranıyla
          açılır. “Pencereyi açmadan tepside başlat” da seçildiyse pencere açılmaz, program doğrudan
          tepsiye iner. Windows oturumu açılmadan ne program ne Ağ Kataloğu çalışır: bilgisayar
          sabah açılınca masa hesabında oturum açın.
        </p>

        <AltBaslik>Gün değişimi</AltBaslik>
        <p>
          Program günlerce kapanmadan açık kalabilir. Günde bir yapılması gereken işler bu yüzden
          açılışa değil tarihe bağlıdır: program açılışta ve açık kaldığı sürece saatte bir tarihi
          denetler; gün değiştiyse o günün şifreli yedeğini alır, 14 günden eski yedekleri siler ve
          bilgisayarın ağ adresini denetler. Adres değiştiyse Ağ Doktoru&apos;nun “Katalog Durumu”
          kartında adresin değiştiğini söyleyen ve “Afişi yeniden basın, yer imlerini güncelleyin.”
          diyen uyarı çıkar (bkz. Ağ Kataloğu bölümü, “Adres değişirse”). Bir iş yapılamazsa (ör.
          yönetici parolası henüz kurulmadıysa) bir saat sonra yeniden denenir. Yedek için kilidin
          açılması gerekmez: kayıtlar kilitliyken de alınır. Bilgisayar kapalıyken ya da uykudayken
          hiçbir iş yapılmaz; program açılınca ilk iş o günün yedeğidir, bilgisayar uykudan uyanırsa
          yedek en geç bir saat içinde alınır.
        </p>

        <AltBaslik>Uyku</AltBaslik>
        <p>
          Ağ Kataloğu açıkken bilgisayarın boşta kalınca uykuya geçmesi engellenir; böylece
          tahtalardan gün boyu erişilebilir. Kapağı kapatmak ya da bilgisayarı elle uyutmak
          engellenmez; bilgisayar uyursa ya da kapanırsa katalog da erişilemez. Bu davranış{" "}
          <Ekran to="/ayarlar?tab=ag-katalogu">Ayarlar → Ağ Kataloğu</Ekran>&apos;ndaki “Uyku”
          bölümünde “Ağ Kataloğu açıkken bilgisayar boşta uykuya geçmesin” kutusuyla kapatılır.
          Katalog kapalıyken uyku hiç engellenmez.
        </p>
      </Bolum>

      {/* ------------------------------------------------------------------ */}
      <Bolum id="ag-katalogu">
        <p>
          Ağ Kataloğu, okul ağındaki bilgisayarlardan ve etkileşimli tahtalardan tarayıcıyla kitap
          aramayı sağlar. Program bu bilgisayarda açıkken katalog okul ağına buradan sunulur:
          tahtaya ya da öğretmen bilgisayarına bir şey kurulmaz, internet gerekmez; tarayıcının
          adres çubuğuna kataloğun adresi yazılır. Katalog yalnız okunur: oradan ödünç alınamaz,
          hiçbir kayıt değiştirilemez. Varsayılan olarak kapalıdır ve yalnız yönetici kipinde
          açılır.
        </p>

        <AltBaslik>Neyi gösterir, neyi asla göstermez</AltBaslik>
        <p>Ağ Kataloğunda görünenler:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            künye: kaynak adı, yazar, çevirmen, yayınevi, baskı, yayın yılı, ISBN, konu, dil ve
            kaynak türü;
          </li>
          <li>sınıflama kodu ve DOS ana sınıfı, yer numarası ve bölüm;</li>
          <li>
            nüshaların durumu: “Rafta”, “Ödünçte”, “Sınıf kitaplığında” ya da “Onarımda”; danışma
            kaynaklarında “Ödünç verilmez — kütüphanede okunur”;
          </li>
          <li>ana sayfada vitrin: yeni gelenler ve çok okunanlar;</li>
          <li>
            kaynak adına, yazara ve konuya göre alfabetik dizinler; okulun adı ve kütüphane
            saatleri.
          </li>
        </ul>
        <p>
          <strong>Kişisel veri göstermez.</strong> Ağ Kataloğunun hiçbir sayfasında şunlar yoktur:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>üye listesi; hiçbir kişinin adı, sınıfı, okul numarası ya da kart no&apos;su;</li>
          <li>
            kimin hangi kitabı ödünç aldığı, ödünç geçmişi, iade tarihi ve gecikenler: bir nüshanın
            “Ödünçte” olduğu görünür, kimde olduğu ve ne zaman döneceği görünmez;
          </li>
          <li>
            kayıp ve hasar kayıtları, bağışçı, fiyat, TKYS kodu, eski kayıt no, komisyon ve sayım
            kurulu adları;
          </li>
          <li>yönetim ekranları, yedek ve dışa aktarım.</li>
        </ul>
        <p>
          Aramalar ve bağlanan bilgisayarların adresleri kaydedilmez. Katalog kişisel veri
          taşımadığı için kayıtlar kilitliyken de çalışır; internete hiç bağlanmaz. Çok okunanlarda
          yalnız sıra görünür, sayı gösterilmez; bu liste ödünç işlemleriyle birlikte sonraki
          sürümlerde dolmaya başlar, bu sürümde vitrinde yeni gelenler görünür.
        </p>
        <p>
          Kataloğun üst menüsünde “Ara”, “Kaynak Adları”, “Yazarlar”, “Konular” ve “Hakkında”
          bağlantıları vardır. Kataloğun kendi Hakkında sayfası da ziyaretçiye neyi gösterip neyi
          göstermediğini söyler. Vitrin ve konu dizini{" "}
          <Ekran to="/ayarlar?tab=ag-katalogu">Ayarlar → Ağ Kataloğu</Ekran>&apos;ndaki “Katalog
          Sayfaları” bölümünden kapatılabilir; aynı bölüme yazılan kütüphane saatleri kataloğun
          Hakkında sayfasında ve afişte görünür.
        </p>

        <AltBaslik>BTR&apos;yle yapılacaklar</AltBaslik>
        <p>
          Ağ Kataloğu bu bilgisayardan okul ağına bir port (varsayılan 8765) üzerinden hizmet verir.
          Bu yüzden okul ağında açılmadan önce bilişim teknolojileri rehber öğretmeninin (BTR)
          bilgisi alınır: kullanılacak port, güvenlik duvarı kuralı ve bilgisayarın ağ adresinin
          sabit kalması BTR&apos;yle birlikte belirlenir.
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            <strong>Ağ keşfi.</strong> Kütüphane bilgisayarının ve tahtaların hangi ağ bölümünde
            olduğunu, bilgisayarın ağ profilini ve BTR&apos;nin tahtalara dosya ya da politika
            gönderip gönderemediğini (ör. Liderahenk ile) öğrenin; yer imleri bu yolla dağıtılır.
            Aynı bölümdeki bilgisayarlar kataloğa doğrudan ulaşır. Tahtalar ayrı bir bölümdeyse
            erişim iki şeye bağlıdır: bölümler arasındaki geçiş (ağ cihazları merkezden yönetilir,
            bu ayar okulda değiştirilemez) ve tahta tarayıcısının vekil sunucu ayarı (yerel adres
            için istisnayı BTR tanımlar).
          </li>
          <li className="space-y-2">
            <p>
              <strong>Sabit adres.</strong> BTR, DHCP&apos;de bu bilgisayarın ağ kartına sabit adres
              ayırır ya da bunu yetkili birimden ister. Adres değişirse afiş ve yer imleri eski
              adresi gösterir (bkz. aşağıda “Adres değişirse”). Bilgisayarın adresini siz elle
              değiştirmeyin:
            </p>
            <Mevzuat kaynak={`${YONERGE}, md. 11/6`}>
              “Bilgisayarlara tahsis edilen IP numarası ve ortam erişim kontrolü adresi (MAC adresi)
              ile BIOS ayarları Bakanlık tarafından yetkilendirilmiş kişiler dışında
              değiştirilemez.”
            </Mevzuat>
          </li>
          <li className="space-y-2">
            <p>
              <strong>Tahta ağından erişim kapalıysa PYS talebi.</strong> Ağ Doktoru&apos;ndaki “PYS
              talep metnini kopyala” düğmesi talebi hazırlar: “yerel ağ VLAN düzenlemesi — tek yön”
              konulu, tahtalardan bu bilgisayara yalnız katalog portuna erişim isteyen, portu ve
              gerekçesini yazan bir metindir. BTR metni okul müdürünün onayıyla FATİH PYS&apos;ye
              girer. Talebi “internet ya da site açma” diye yazmayın; başka birime gider. Portları
              okul değil Bakanlık düzenler, bu yüzden süre okulun elinde değildir:
            </p>
            <Mevzuat kaynak={`${YONERGE}, md. 11/22`}>
              “Başkanlık MEBNET ağında erişime açılacak ve kapanacak portları belirleme ve düzenleme
              yetkisine sahiptir.”
            </Mevzuat>
          </li>
          <li>
            <strong>Ağ Hizmeti Bilgi Notu.</strong> Not bilgisayarın demirbaş no&apos;sunu, portu ve
            gerekçesini, güvenlik duvarı kuralının gerçek değerlerini, neyin sunulup neyin
            sunulmadığını ve programın giden bağlantılarını yazar. Ağ Doktoru&apos;ndaki “Ağ Hizmeti
            Bilgi Notu&apos;nu bas” düğmesiyle basılır. BTR ve okul müdürü imzalar, not okulda
            saklanır. Bu bir izin belgesi değil, bilgi notudur.
          </li>
          <li className="space-y-2">
            <p>
              <strong>Okul ağından erişim sınaması.</strong> Katalog açıldıktan sonra erişimi başka
              bir bilgisayardan ve bir tahtadan sınayın: Ağ Doktoru&apos;nun verdiği{" "}
              <Kod>Test-NetConnection</Kod> komutunu okul ağındaki başka bir Windows bilgisayarda
              çalıştırın, tahtanın tarayıcısında kataloğun adresini açın. Bilgi notunda ayrıca bu
              bilgisayardan güncelleme denetiminin ve (açıksa) ISBN ile künye getirmenin adreslerine
              erişimi sınayan hazır komutlar vardır. Bu adreslerden biri okul ağında kapalıysa
              erişim talebi Yardım Masası&apos;ndan açılır:
            </p>
            <Mevzuat kaynak={`${YONERGE}, md. 11/12`}>
              “MEBNET ağında kategorisi olmayan ip adresi, içerik veya sitelere erişim izni
              verilmez. Erişim talepleri Yardım Masası Modülü (yardimmasasi.meb.gov.tr) üzerinden
              yapılır.”
            </Mevzuat>
          </li>
        </ol>

        <AltBaslik>Açma adımları</AltBaslik>
        <p>
          Katalog hiç açılmamışken ve afiş hiç basılmamışken{" "}
          <Ekran to="/ayarlar?tab=ag-katalogu">Ayarlar → Ağ Kataloğu</Ekran> sekmesinin başında “Ağ
          Kataloğunu Açmadan Önce” kartı durur. Adımları sırasıyla:
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            <strong>BTR&apos;yle görüşün:</strong> yukarıdaki görüşme. Kartta “Ağ Hizmeti Bilgi
            Notu&apos;nu bas” düğmesi de vardır.
          </li>
          <li>
            <strong>Güvenlik duvarını hazırlayın:</strong> Windows&apos;ta kurulumda “Yerel ağdan
            katalog taramasına izin ver (güvenlik duvarı kuralı)” seçildiyse kural hazırdır; kartın
            “Ağ Doktoru&apos;nu aç” bağlantısıyla Ağ Doktoru&apos;na geçip beş denetimin geçtiğini
            görün. Geçmiyorsa oradaki “Kuralı ekle/güncelle” düğmesi kuralı yazar; Windows&apos;un
            yönetici onayını (UAC) ister, kimliği BTR girer. Pardus&apos;ta kuralı BTR açar.
          </li>
          <li>
            <strong>Adresi seçin:</strong> sekmenin “Dinleme” bölümündeki “Katalog hangi ağ
            bağlantısında açılsın?” sorusunu yanıtlayıp “Kaydet”e basın. Bilgisayarda tek ağ
            bağlantısı varsa varsayılan “Bu bilgisayarın bütün ağ bağlantılarında” seçeneği
            yeterlidir. İkinci ağ kartı varsa “Yalnız seçili IP adresinde” seçeneğini ve “IP adresi”
            listesinden okul ağındaki adresi seçin; katalog yalnız o ağa açılır.
          </li>
          <li>
            <strong>Ağ Kataloğunu açın:</strong> “Ağ Kataloğunu aç” düğmesine basın.
          </li>
          <li>
            <strong>Afişi basın, yer imlerini dağıtın:</strong> Ağ Doktoru&apos;ndaki “Belgeler”
            kartından (aşağıda). Afiş basılınca kart gizlenir.
          </li>
        </ol>
        <p>
          Windows&apos;ta güvenlik duvarı denetiminin beş maddesinden biri tutmazsa katalog okul
          ağına hiç açılmaz; durum “Güvenlik duvarı izni yok” olur ve Ağ Doktoru düzeltme adımını
          gösterir. Açma kalıcıdır: program yeniden açıldığında katalog da açılır. Yönetici kipinde
          tepsi menüsündeki “Ağ Kataloğunu aç” ve “Ağ Kataloğunu kapat” komutları da aynı işi görür.
          Windows&apos;ta kurulum yapılmadan çalıştırılan (taşınabilir) sürümde Ağ Kataloğu
          sunulmaz: güvenlik duvarı kuralı kurulu programın yoluna bağlıdır. Pardus&apos;un
          taşınabilir arşivinde katalog açılır; paket tanımı gelmediği için Ağ Doktoru portu
          doğrudan açan komutu verir.
        </p>

        <AltBaslik>Ağ Doktoru</AltBaslik>
        <p>
          <Ekran to="/ag-doktoru">Ağ Doktoru</Ekran> menüde yoktur: Ayarlar → Ağ Kataloğu&apos;ndaki
          “Ağ Doktoru” bağlantısıyla açılır. Ağ Doktoru yalnız yönetici kipinde açılır. Beş kartı
          vardır:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Katalog Durumu:</strong> durum rozeti, port, dinlenen ağ bağlantısı, katalog
            adresi (tıklanınca bu bilgisayarın tarayıcısında açılır) ve QR kodu, bugün gösterilen
            sayfa ve yapılan arama sayısı, son hata ve uyarılar; “Ağ Kataloğunu aç” ya da “Ağ
            Kataloğunu kapat”, “Yeniden başlat” ve “Yenile” düğmeleri. Kimin neyi aradığı tutulmaz,
            yalnız günlük sayılar tutulur.
          </li>
          <li>
            <strong>Güvenlik Duvarı:</strong> beş denetimin her biri “Geçti”, “Geçmedi”, “Uyarı” ya
            da “Denetlenemedi” olarak; kuraldaki uzak adres ve profil, bu bilgisayarın ağ profili
            (“Genel”, “Özel” ya da “Etki alanı”); “Kuralı ekle/güncelle” ve “Yeniden denetle”
            düğmeleri. Program için birden çok izin kuralı varsa hepsi listelenir: Windows herhangi
            birine uyan bağlantıyı kabul eder, biri bütün adreslere açıksa denetim uyarır.
            Pardus&apos;ta bu kart BTR&apos;nin çalıştıracağı komutu gösterir.
          </li>
          <li>
            <strong>Ağ Bağlantıları:</strong> bu bilgisayarın ağ bağlantıları, adresleri ve ağ
            profilleri. Varsayılan bağlantı dışında etkin bir bağlantı varsa kataloğun o ağda da
            erişilebileceği uyarısı çıkar; bilgisayarda IP yönlendirme açıksa o da uyarılır.
            Bilgisayarın adresi Ayarlar&apos;daki tahta ağı bloklarından birindeyse “Bu bilgisayar
            öğrenci erişimli ağda” uyarısı çıkar: kütüphane masası hesabında kişisel oturum açmayın,
            bilgisayardan ayrılırken programı kilitleyin.
          </li>
          <li>
            <strong>Dinleyici Sınaması:</strong> “Dinleyiciyi sına” düğmesi ve başka bilgisayar için
            hazır sınama komutu.
          </li>
          <li>
            <strong>Belgeler:</strong> “Afişi bas”, “Yer imi dosyalarını üret”, “PYS talep metnini
            kopyala” ve “Ağ Hizmeti Bilgi Notu&apos;nu bas” düğmeleri; belgelerin hangi adresi
            taşıyacağı “Belgelerde kullanılacak adres” seçicisinden seçilir.
          </li>
        </ul>
        <p>Durum rozetinin anlamları:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Açık:</strong> katalog okul ağında hizmet veriyor; <strong>Kapalı:</strong>{" "}
            katalog kapatılmış ya da hiç açılmamış.
          </li>
          <li>
            <strong>Güvenlik duvarı izni yok:</strong> beş denetimden biri tutmadı, katalog hiç
            dinlemiyor; “Güvenlik Duvarı” kartındaki madde neyin düzeltileceğini yazar. Denetim hiç
            okunamadıysa (ör. bilgisayar açılışta çok yavaşsa) program birkaç dakika arayla, sonra
            saatte bir kendiliğinden yeniden dener. Katalogu kullanmaktan vazgeçtiyseniz “Ağ
            Kataloğunu kapat” ile ayarı kapatın; ayar açık kaldıkça program her açılışta yeniden
            dener.
          </li>
          <li>
            <strong>Açılamadı:</strong> katalog başlatılamadı ya da seçili adres bu bilgisayarda
            artık yok; “Son hata” nedenini yazar.
          </li>
          <li>
            <strong>Port bekleniyor:</strong> port başka bir program tarafından kullanılıyor;
            program birkaç dakika boyunca kendiliğinden yeniden dener.
          </li>
          <li>
            <strong>Geri yükleme nedeniyle kapalı:</strong> yedekten geri yükleme yapıldı. Program
            yeniden açılınca geri yüklenen yedekte Ağ Kataloğu açıksa katalog kendiliğinden kalkar;
            değilse Ayarlar → Ağ Kataloğu&apos;ndan yeniden açılır.
          </li>
        </ul>
        <p>
          “Dinleyiciyi sına” düğmesi kataloğun bu bilgisayardaki her ağ bağlantısında yanıt verip
          vermediğini sınar. Bu sınama güvenlik duvarını ya da ağ bölümlerini kanıtlamaz, çünkü
          bilgisayarın kendi adresine yapılan bağlantı ağa çıkmaz. Asıl kanıt başka bir
          bilgisayardan alınır: Ağ Doktoru&apos;nun verdiği <Kod>Test-NetConnection</Kod> komutunu
          (“Kopyala” ile alınır) okul ağındaki başka bir Windows bilgisayarda PowerShell&apos;de
          çalıştırın; sonuçta <Kod>TcpTestSucceeded : True</Kod> görülmelidir.
        </p>

        <AltBaslik>Afiş ve yer imleri</AltBaslik>
        <p>
          “Afişi bas” kataloğun adresini büyük ve tek satırda basar; QR kodu küçük ve ikincildir,
          çünkü okul bilgisayarları ve tahtalar QR okumaz. Afiş tek sayfadır: okulun adını, adresin
          nasıl yazılacağını, kütüphane saatlerini ve kataloğun kişisel veri göstermediğini yazar.
          Afiş basılınca program o adresi hatırlar; bilgisayarın adresi sonradan değişirse uyarır.
        </p>
        <p>
          Tahtalarda yer imi tek tek eklenmez: ETAP her öğretmene tahtada ayrı bir hesap açar ve bir
          hesaba eklenen yer imi öbür öğretmenlerin hesabında görünmez. Bu yüzden kullanıcı başına
          yer imi yetmez; program tahtanın bütün hesaplarında görünen bir yer imi politika dosyası
          üretir. “Yer imi dosyalarını üret” tek bir arşiv indirir:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            ETAP/Pardus tahtalar için Chromium&apos;un yer imi politika dosyası (
            <Kod>/etc/chromium/policies/managed/</Kod> klasörüne konur) ve uygulama menüsü kısayolu
            (<Kod>/usr/share/applications/</Kod> klasörüne konur);
          </li>
          <li>
            Windows bilgisayarlar için internet kısayolu ve Windows tahtalar için tahta kipinde açan
            ikinci bir kısayol;
          </li>
          <li>
            her dosyanın nereye ve hangi komutla konacağını yazan açıklama dosyası (
            <Kod>BENIOKU.txt</Kod>).
          </li>
        </ul>
        <p>
          Dosyaları tahtalara ve bilgisayarlara BTR dağıtır. Dağıtım yetkisi ağ keşfinde öğrenilir.
        </p>

        <AltBaslik>Tahta kipi</AltBaslik>
        <p>
          Tahtalar için üretilen yer imleri kataloğu tahta kipinde açar: yazılar ve dokunma
          hedefleri büyür, sayfadan sayfaya geçerken büyük düzen korunur. Ekran klavyesine gerek
          kalmadan bir kaynağa ulaşmak için üst menüdeki “Kaynak Adları”, “Yazarlar” ve “Konular”
          dizinleri kullanılır: önce harfe, sonra kaynağa dokunulur; kaynağın sayfası yer numarasını
          ve nüshaların rafta olup olmadığını gösterir. Dokunmatik ekranlı cihazlarda büyük düzen
          kendiliğinden de açılır. Yer imini bir tahtaya elle eklerseniz adresin sonuna{" "}
          <Kod>?tahta=1</Kod> yazın (ör. <Kod>{"http://<IP>:8765/?tahta=1"}</Kod>).
        </p>

        <AltBaslik>Adres değişirse</AltBaslik>
        <p>
          Program her gün, gün değişimi denetiminde bu bilgisayarın ağ adresine bakar. Adres son
          basılan afişteki adresten farklıysa Ağ Doktoru&apos;nun “Katalog Durumu” kartında “Bu
          bilgisayarın IP adresi değişti (… → …). Afişi yeniden basın, yer imlerini güncelleyin.”
          uyarısı çıkar. Sırasıyla:
        </p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            BTR&apos;ye haber verin: sabit adres ayırma yapılmamış ya da bozulmuş olabilir. Adres
            yeniden değişecekse belgeleri yenilemek kalıcı çözüm değildir.
          </li>
          <li>“Afişi bas” ile yeni afişi basıp eskisinin yerine asın; uyarı yeni afişle kalkar.</li>
          <li>
            “Yer imi dosyalarını üret” ile yeni arşivi üretip BTR&apos;ye verin; dosyalar eskilerin
            yerine konur.
          </li>
          <li>
            Ağ Hizmeti Bilgi Notu&apos;nu yeniden basıp imzalatın. Tahta ağından erişim için PYS
            talebi açıldıysa yeni adresi BTR&apos;ye bildirin.
          </li>
        </ol>
        <p>
          “Yalnız seçili IP adresinde” seçiliyken seçili adres bilgisayarda kalmazsa: bilgisayarın
          tek adresi varsa katalog o adreste açılır ve aynı uyarıyı verir; birden çok adresi varsa
          katalog açılmaz, adresi Ayarlar → Ağ Kataloğu&apos;nun “Dinleme” bölümünden yeniden seçin.
          Kütüphane bilgisayarı değişirse sabit adres ayırma yeni bilgisayarın ağ kartına taşınır.
        </p>

        <AltBaslik>Port</AltBaslik>
        <p>
          Varsayılan port 8765&apos;tir ve çoğu okulda değiştirmek gerekmez. Ayarlar → Ağ
          Kataloğu&apos;ndaki “Portu değiştir” Windows&apos;ta güvenlik duvarı kuralını da yeni
          portla yazar ve yönetici onayı (UAC) ister; onay verilmezse port değişmez. Port değişince
          afişi yeniden basın, yer imlerini ve Ağ Hizmeti Bilgi Notu&apos;nu yenileyin; PYS talebi
          açıldıysa yeni portu BTR&apos;ye bildirin.
        </p>

        <AltBaslik>Pardus</AltBaslik>
        <p>
          Pardus&apos;ta program güvenlik duvarı kuralı açmaz; paket hazır bir tanım bırakır. Ağ
          Doktoru&apos;nun “Güvenlik Duvarı” kartı bilgisayardaki güvenlik duvarını ve BTR&apos;nin
          çalıştıracağı komutu gösterir; komut “Kopyala” ile alınır. Komut katalogu yalnız bu
          bilgisayarın yerel ağına ve Ayarlar&apos;daki tahta ağı bloklarına açar (her blok ayrı
          satırdır); Windows&apos;taki kural gibi bütün adreslere açmaz. Pardus&apos;ta port
          değiştirilince komut yeni portla yenilenir ve kuralı BTR yeniden açar.
        </p>
      </Bolum>
    </div>
  );
}
