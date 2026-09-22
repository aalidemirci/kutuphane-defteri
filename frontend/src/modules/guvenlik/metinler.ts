// Güvenlik arayüzünün DÜRÜST metinleri — tek kaynak (tasarım §4.3, §6.3).
// Kural: bu program "veritabanını şifreliyorum" DEMEZ. Şifrelenen şey belirli
// kişisel veri alanlarıdır; anahtar da aynı bilgisayarda durur. Kullanıcıya
// olduğundan güçlü bir koruma vadetmek, gerçek önlemi (tam disk şifreleme)
// almasını engellerdi. Sözlük: "yönetici parolası", "kurtarma anahtarı"
// (docs/sozluk.md — "şifre", "uygulama parolası" kullanılmaz).

/** Ayarlar ve kilit ekranında gösterilen kapsam açıklaması. */
export const KAPSAM_METNI =
  "Bu koruma, kayıtlardaki kişisel veri alanlarını (öğrenci, öğretmen ve diğer " +
  "personelin ad-soyadları, öğrencilerin okul numaraları) yönetici parolasıyla açılan bir " +
  "anahtarla şifreler. TAM DİSK ŞİFRELEME DEĞİLDİR: bilgisayarın tamamını korumak " +
  "için Windows'ta BitLocker, Pardus/Linux'ta LUKS kullanın.";

/** Şifrelenmeyen alanlar açıkça söylenir — sürpriz olmasın. */
export const KAPSAM_DISI_METNI =
  "Sınıf/şube, üye türü ve tarihler şifrelenmez (süzgeçler bunlara dayanır). " +
  "Okul numarası şifrelidir; arama ve e-Okul eşleştirmesi numaranın tamamıyla " +
  "yapılır, numaranın bir parçasıyla arama yapılamaz.";

/** Kurtarma anahtarı panelinin uyarısı (kurulum sihirbazının ilk adımı). */
export const KURTARMA_UYARISI =
  "Bu anahtar bir daha gösterilmez. Yönetici parolası unutulursa kayıtlara erişmenin " +
  "tek yolu budur. Şimdi saklayın: yazdırın, PDF olarak USB belleğe kaydedin ya da " +
  "kâğıda elle yazın. Kâğıdı müdürlükte kapalı zarfta saklayın; anahtarı bu " +
  "bilgisayarda bırakmayın.";

/** Elle yazma yönergesi — çıktıdaki ipucuyla aynı (anahtar alfabesinde 0/1/8/9 yok). */
export const ELLE_YAZ_METNI =
  "Elle yazacaksanız grupları sırasıyla, büyük harfle yazın. Anahtarda 0, 1, 8 ve 9 " +
  "rakamları yoktur: O ve I her zaman harftir.";

/** Doğrulama adımının açıklaması (iki grup, istemci tarafında; anahtar sunucuda saklanmaz). */
export function dogrulamaMetni(birinci: number, ikinci: number): string {
  return (
    `Sakladığınız kopyaya bakarak anahtarın ${birinci}. ve ${ikinci}. grubunu yazın. ` +
    "Böylece kopyanın doğru ve okunaklı olduğundan emin olursunuz."
  );
}

/** Parola kurma açıklaması (yalnız ilk kurulumda, sihirbazın ilk adımı; kaldırılamaz). */
export const KURMA_UYARISI =
  "Yönetici parolası zorunludur: parola kurulmadan öğrenci, öğretmen ve diğer " +
  "personel kaydı yapılamaz. Kurulduktan sonra kaldırılamaz, yalnız değiştirilebilir. Parolayı en " +
  "az iki görevlendirilmiş kişi bilsin; kütüphane görevlileri görevli kipinde çalışır " +
  "ve parolayı bilmez.";

/** Kurtarma anahtarı çıktısını yeniden alma kartı (Ayarlar → Güvenlik). */
export const CIKTI_YENIDEN_METNI =
  "Kurtarma anahtarı programda saklanmaz; yalnız parola kurulurken ya da anahtar " +
  "yenilenirken bir kez gösterilir. Elinizdeki anahtarı yazın: anahtar doğruysa " +
  "yazdırılabilir çıktısı PDF olarak hazırlanır (ör. elle yazılmış kâğıdın temiz kopyası için).";

/** Anahtarın saklandığı sunucuda doğrulanmadıysa (kurulum sihirbazı, Güvenlik, yol haritası). */
export const DOGRULANMADI_BASLIGI = "Kurtarma anahtarı doğrulanmadı";

export const DOGRULANMADI_METNI =
  "Kurtarma anahtarının saklandığı henüz doğrulanmadı. Yönetici parolası unutulursa " +
  "kayıtlara yalnız bu anahtarla ulaşılır. Anahtarı sakladıysanız aşağıya yazıp " +
  "doğrulayın; kaydedemediyseniz yenisini üretin.";

/** "Kurtarma anahtarını doğrula" kartı: kâğıttaki anahtarın tamamı yazılır. */
export const DOGRULA_KARTI_METNI =
  "Sakladığınız kâğıttaki ya da PDF'teki anahtarı olduğu gibi yazın. Anahtar doğruysa " +
  "saklandığı kaydedilir; program anahtarı saklamaz.";

/** "Kurtarma anahtarını yenile" kartının açıklaması. */
export const YENILEME_METNI =
  "Anahtar kaybolduysa ya da kurulumda kaydedilemediyse yenisini üretin. Yeni anahtar bir " +
  "kez gösterilir; saklayıp doğrulamadan programı kapatmayın. Yönetici parolası değişmez, " +
  "kayıtlar yeniden şifrelenmez.";

/** Yenileme onay diyaloğu: sonuç (başlık soru, gövde sonuç — sözlük §3). */
export const YENILEME_SONUCU_METNI =
  "Yeni bir kurtarma anahtarı üretilir ve bir kez gösterilir. Zarftaki eski anahtar bu " +
  "bilgisayarda kilidi artık açmaz.";

/**
 * Eski yedekler (backend `backup_restore`: yedek, alındığı günün güvenlik dosyasını
 * taşır; güncel dosya yerindeyken yeni anahtar da açar). Testle kanıtlı:
 * `apps/okul/tests/test_kurtarma_yenileme.py::TestYedekler`.
 */
export const ESKI_YEDEK_METNI =
  "Her yedek, alındığı günün güvenlik dosyasını içinde taşır. Bugünden önce alınmış " +
  "yedekler bu bilgisayarda yeni anahtarla da açılır; ama başka bir bilgisayarda ya da " +
  "güvenlik dosyası kaybolduğunda yalnız eski kurtarma anahtarıyla (ya da o dönemin " +
  "yönetici parolasıyla) açılır. O yedekler (USB bellektekiler dahil) duruyorsa eski " +
  "kâğıdı atmayın: “Eski anahtar — bugünden önceki yedekler için” diye işaretleyip ayrı saklayın.";

/** Dürüst sınır: yenileme ele geçmiş anahtara karşı koruma değildir (DEK değişmez). */
export const ELE_GECMIS_ANAHTAR_METNI =
  "Yenileme, başkasının eline geçmiş bir anahtara karşı koruma değildir: kayıtların " +
  "anahtarı değişmez; eski yedekler ve veri klasöründe “guvenlik-arsiv” adıyla saklanan " +
  "önceki güvenlik dosyası eski anahtarla açılabilir.";

/** Yarım kalan kurulum uyarısı (elektrik kesintisi vb.). */
export const YARIM_GECIS_METNI =
  "Önceki güvenlik işlemi yarıda kalmış. Yönetici parolasıyla açtığınızda " +
  "kaldığı yerden otomatik olarak tamamlanacaktır.";

/** Güvenlik dosyası kayıp ekranının başlığı (dosya yok ya da bozuk — ikisi aynı ekran). */
export const DOSYA_KAYIP_BASLIGI = "Güvenlik dosyası bulunamadı ya da okunamıyor";

/** Güvenlik dosyası kayıp ekranı: ne oldu? */
export const DOSYA_KAYIP_METNI =
  "Bu bilgisayarda yönetici parolası kurulmuş, ancak kayıtların anahtarını " +
  "saklayan güvenlik dosyası (guvenlik.json) veri klasöründe bulunamadı ya da " +
  "okunamıyor (boş ya da bozuk). Dosya olmadan kayıtlar açılamaz. Yeni parola da " +
  "kurulamaz; kurulsaydı eski kayıtlar hiç okunamaz hâle gelirdi.";

/** Güvenlik dosyası kayıp ekranı: birinci çıkış yolu. */
export const DOSYA_KAYIP_GERI_KOY =
  "Dosyanın sağlam bir kopyası varsa (ör. bilgisayar taşınırken alınan veri klasörü " +
  "ya da USB bellekteki kopya) guvenlik.json dosyasını veri klasörüne geri koyun " +
  "(bozuk dosya varsa onun yerine), ardından “Yeniden denetle” düğmesine basın.";

/** Güvenlik dosyası kayıp ekranı: ikinci çıkış yolu. */
export const DOSYA_KAYIP_YEDEKTEN =
  "Kopya yoksa aşağıdan bir yedeği geri yükleyin: her yedek güvenlik dosyasını da " +
  "içinde taşır ve geri yükleme dosyayı yeniden oluşturur. Yedeğin alındığı " +
  "dönemdeki yönetici parolası ya da kurtarma anahtarı gerekir; o yedekten sonra " +
  "girilen kayıtlar ekrandan kalkar.";

/** Güvenlik dosyası kayıp ekranı: üçüncü çıkış yolu (yalnız korunan veri yokken görünür). */
export const DOSYA_KAYIP_SIFIRLA_METNI =
  "Bu veritabanında kişi kaydı yok, kayıtların anahtarı veritabanına işlenmemiş ve yedek " +
  "klasöründe yedek bulunmuyor: okunamayan dosya korunan bir veriyi açmıyor. Dosyayı " +
  "kenara alıp kurulum sihirbazına dönebilirsiniz. Dosya silinmez, veri klasöründe " +
  "“guvenlik-arsiv” adıyla " +
  "kalır; yönetici parolası yeniden kurulur ve yeni bir kurtarma anahtarı verilir.";
