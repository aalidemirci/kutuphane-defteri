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
// Metin kuralları (docs/sozluk.md — bağlayıcı): düğme, sekme ve alan adları
// ekrandaki metinle BİREBİR yazılır (depodan doğrulandı; test bir kısmını ekran
// sabitlerinden kilitler). İç kodlar (F1, U5, E14…) geçmez. Program kendini
// "yerel araç" diye tanıtır. Kaydırılmış iade tarihi Yönetmelik hükmü gibi
// sunulmaz: hafta sonu/tatil kaydırması TBK 93'e KIYASEN, ara tatil/yarıyıl
// kaydırması okulun tercihidir (CLAUDE.md §2-6); idari izin/diğer günlerindeki
// kaydırma dayanaksız program kuralıdır, TBK 93 maddesinin altında anılmaz.
//
// Mevzuat atıfları yalnız `docs/mevzuat/`'taki tam metinlerden alınır; alıntılar
// BİREBİR, madde numarası uydurulmaz: Yönerge 11/8 ve 11/23
// (meb-bilgi-ve-sistem-guvenligi-yonergesi.md), Yönetmelik 18/1
// (meb-okul-kutuphaneleri-yonetmeligi.md), TBK 93 (6098-…-md92-93.md).

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import Card from "../../ui/Card";
import Icon from "../../ui/Icon";

/** Bölümler (çapa → başlık + ikon), sayfadaki sırasıyla. Başlıklar Başlık Düzenindedir. */
const BOLUMLER = {
  "ilk-kurulum": { baslik: "İlk Kurulum", ikon: "checklist" },
  "yol-haritasi": { baslik: "Başlangıç Yol Haritası", ikon: "flag" },
  kipler: { baslik: "Görevli Kipi ve Yönetici Kipi", ikon: "admin_panel_settings" },
  kisiler: { baslik: "Kişiler ve e-Okul Listeleri", ikon: "group" },
  "kapali-gunler": { baslik: "Kapalı Günler", ikon: "event_busy" },
  "katalog-sablonu": { baslik: "Katalog Excel Şablonu", ikon: "table_view" },
  yedek: { baslik: "Yedek ve Güvenlik Dosyası", ikon: "backup" },
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

const YONERGE = "Millî Eğitim Bakanlığı Bilgi ve Sistem Güvenliği Yönergesi";

export default function KilavuzPage() {
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
          bakarak istenen iki grubu yazarsınız. Doğrulama bitmeden “Devam” düğmesi açılmaz; kopyaya
          yeniden bakmanız gerekirse “Anahtarı yeniden göster”i kullanın. Bu sırada program görevli
          kipine geçer ya da kilitlenirse anahtar kaybolmaz: yönetici kipine döndüğünüzde sihirbaz
          anahtarı yeniden gösterir ve doğrulamayı yeniden ister. Anahtarı saklayıp doğrulamadan
          programı kapatmayın: kapanan programda anahtar yeniden gösterilemez.
        </p>
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
          anahtarı doğrular; yanlış yazılmış anahtar basılmaz.
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
          düğmesi çıkar.
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
            kipte kapalıdır; program onları arka planda da reddeder.
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
          “Kurtar ve aç” düğmesine basın. Kurtarma anahtarı değişmez, bundan sonra da geçerlidir;
          zarftaki kâğıt geçerli kalır. Yeni parolayı, parolayı bilen öbür görevlendirilmiş kişiye
          de bildirin.
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
          <Ekran to="/kisiler">Kişiler</Ekran> sayfasının iki sekmesi vardır: “Öğrenciler” ve
          “Öğretmenler ve Diğer Personel”. Program T.C. kimlik numarası, veli bilgisi, cinsiyet,
          unvan ve branş tutmaz. Öğrencide ad, soyad, okul no, sınıf ve şube; öğretmen ve diğer
          personelde ad, soyad ve üye türü tutulur. Kişi kaydı için yönetici parolasının kurulmuş
          olması gerekir.
        </p>

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
          güncellenen, değişmeyen ve ayrılacak olduğunu gösterir. “Aktar” düğmesi önizlemeden sonra
          açılır; öğrenci ayrılacaksa işlem bir kez daha onay ister.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Öğrenciler okul numarasıyla eşleştirilir. Dosyada yeni şubesiyle görünen öğrenci
            ayrılmaz, kaydı güncellenir. Ayrıldı olarak duran bir öğrenci aynı numara ve aynı adla
            listeye dönerse kaydı yeniden aktif olur; numara adı farklı bir öğrenciye verilmişse
            eski kayıt olduğu gibi kalır ve yeni kayıt açılır.
          </li>
          <li>
            Karşılaştırma varsayılan olarak <strong>yalnız dosyada bulunan şubelerle</strong>{" "}
            yapılır. Tek bir şubenin listesini yüklemek diğer şubelere dokunmaz; dosyadaki bir
            şubede kayıtlı olup dosyada bulunmayan öğrenci “ayrılacak” sayılır.{" "}
            <strong>
              Başka bir şubeye geçtiği için bu dosyada bulunmayan öğrenci de “ayrılacak” sayılır.
            </strong>{" "}
            Bu yüzden yeni ders yılı başında ya da şube değişikliklerinden sonra listeyi şube şube
            yüklemeyin: okulun bütün şubelerini içeren listeyi tek dosyada yükleyin.
          </li>
          <li>
            “Bu dosya okulun tam listesidir” kutusunu yalnız okulun bütün şubelerini içeren dosyada
            işaretleyin: işaretlenirse dosyada hiç bulunmayan şubelerdeki öğrenciler de okuldan
            ayrılmış sayılır.
          </li>
          <li>
            Bir satır atlanırsa (ad ya da sınıf okunamadıysa) o satırdaki okul numarasına sahip
            öğrenci ayrılmış sayılmaz. Okul numarası boş bir öğrenci satırı kimin olduğu
            bilinemediği için o şubede kimseyi ayırmaz. Önizleme bu satırları numarasıyla gösterir.
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
            Kişiler ad-soyadla eşleştirilir. Kayıtta olup listede bulunmayanlar önizlemede “… kişi
            listede yok. Ayrıldı sayılsın mı?” başlığıyla sorulur: yalnız işaretlediğiniz kişiler
            ayrılır, işaretlemedikleriniz olduğu gibi kalır.
          </li>
          <li>
            <strong>Olası aynı kişi:</strong> listedeki yeni bir ad kayıttaki bir kişiye benziyorsa
            (ör. soyadı değişimi) önizleme ikisini birlikte gösterir. Bu kişiyi ayrıldı diye
            işaretlemeyin; aktardıktan sonra “Birleştir” düğmesine basın. Eski kaydın kütüphane
            bağları yeni kayda taşınır ve eski kayıt silinir.
          </li>
        </ul>

        <AltBaslik>Elle kayıt ve ayrılış</AltBaslik>
        <p>
          Tek kişi eklemek için “Öğrenci ekle” ya da “Kişi ekle” düğmesini kullanın; düzenlemek için
          listedeki satıra tıklayın. Okuldan ayrılan kişi için düzenleme penceresindeki “Ayrıldı
          olarak işaretle”yi seçin: kütüphane üyeliği ve açık işlemi olmayan kişinin kaydı hemen
          silinir, kişisel veri saklanmaz; üyeliği ya da açık işlemi varsa kayıt “Ayrıldı ·
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
        <Mevzuat kaynak="Millî Eğitim Bakanlığı Okul Kütüphaneleri Yönetmeliği, md. 18/1">
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
      <Bolum id="katalog-sablonu">
        <p>
          Katalog ekranlarını beklemeden kitap listenizi Excel&apos;de hazırlamaya
          başlayabilirsiniz; hazırladığınız dosya katalog içe aktarımında olduğu gibi kullanılır.
          Şablonu <Ekran to="/">Genel Bakış</Ekran>&apos;taki “Katalog Excel Şablonu” kartında (ya
          da Başlangıç Yol Haritası&apos;nda) “Şablonu indir” düğmesiyle alın. Dosyanın adı
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
      <Bolum id="yedek">
        <p>
          Yönetici parolası kurulduktan sonra program açılırken o günün şifreli{" "}
          <strong>günlük yedeğini</strong> alır (aynı gün yeniden açılınca ikinci yedek almaz) ve
          son 14 günün yedeklerini saklar. Program yeni bir sürüme güncellendiğinde, veritabanını
          güncellemeden önce ayrıca bir yedek alır. Yedekler güçlü şifrelemeyle korunur; yalnız
          yönetici parolasıyla ya da kurtarma anahtarıyla açılır.
        </p>
        <p>
          Otomatik yedekler bu bilgisayardadır; disk bozulursa onlar da gider. Ayda bir{" "}
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>&apos;teki “Şifreli veritabanı
          yedeği” kartından “Şifreli yedeği indir” düğmesiyle yedek alıp USB belleğe kopyalayın ve
          belleği bilgisayardan ayrı saklayın. Yedeği bulut depolama hizmetine yüklemeyin (Yönerge
          md. 11/23).
        </p>

        <AltBaslik>Yedekten geri yükleme</AltBaslik>
        <p>
          Yanlış veri girişinden sonra eski bir güne dönmek için Ayarlar → Güvenlik&apos;teki
          “Yedekten geri yükle” kartında günlük yedeklerden birini seçin ya da elinizdeki yedek
          dosyasını yükleyin. Yedeğin alındığı dönemdeki yönetici parolasını ya da kurtarma
          anahtarını yazıp “Geri yükle”ye basın. O yedekten sonra girilen kayıtlar kalkar. Mevcut
          veritabanı silinmez, veri klasöründe <Kod>db-onceki-…</Kod> adıyla kenara alınır. İşlemden
          sonra programı tepsideki simgeden “Çık”ı seçerek kapatın ve yeniden açın; pencerenin çarpı
          düğmesi programı kapatmaz.
        </p>
        <p>
          Program hiç açılmıyorsa Windows&apos;ta Başlat menüsündeki “Kütüphane Defteri — Yedekten
          Geri Yükle” kısayolunu, Pardus&apos;ta uçbirimden{" "}
          <Kod>kutuphane-defteri --geri-yukle</Kod> komutunu kullanın. Program tepsideyse önce
          tepsideki simgeden “Çık”ı seçin.
        </p>

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
      <Bolum id="ag-katalogu">
        <p>
          Ağ Kataloğu, okul ağındaki bilgisayarlardan ve etkileşimli tahtalardan tarayıcıyla kitap
          aramayı sağlar. Kişisel veri göstermez: üye, ödünç, iade tarihi ya da kişi adı hiçbir
          sayfasında geçmez. Varsayılan olarak kapalıdır.
        </p>
        <p>
          Ağ Kataloğu bu bilgisayardan okul ağına bir port üzerinden hizmet verir. Bu yüzden okul
          ağında açılmadan önce bilişim teknolojileri rehber öğretmeninin (BTR) bilgisi alınır:
          kullanılacak port, güvenlik duvarı kuralı ve bilgisayarın ağ adresinin sabit kalması
          BTR&apos;yle birlikte belirlenir.
        </p>
      </Bolum>
    </div>
  );
}
