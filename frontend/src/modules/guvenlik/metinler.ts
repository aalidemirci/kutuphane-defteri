// Güvenlik arayüzünün DÜRÜST metinleri — tek kaynak (tasarım §4.3, §6.3).
// Kural: bu program "veritabanını şifreliyorum" DEMEZ. Şifrelenen şey belirli
// kişisel veri alanlarıdır; anahtar da aynı bilgisayarda durur. Kullanıcıya
// olduğundan güçlü bir koruma vadetmek, gerçek önlemi (tam disk şifreleme)
// almasını engellerdi. Sözlük: "yönetici parolası", "kurtarma anahtarı"
// (docs/sozluk.md — "şifre", "uygulama parolası" kullanılmaz).

/** Ayarlar ve kilit ekranında gösterilen kapsam açıklaması. */
export const KAPSAM_METNI =
  "Bu koruma, kayıtlardaki kişisel veri alanlarını (öğrenci ve öğretmen " +
  "ad-soyadları) yönetici parolasıyla açılan bir anahtarla şifreler. TAM DİSK " +
  "ŞİFRELEME DEĞİLDİR: bilgisayarın tamamını korumak için Windows'ta " +
  "BitLocker, Pardus/Linux'ta LUKS kullanın.";

/** Şifrelenmeyen alanlar açıkça söylenir — sürpriz olmasın. */
export const KAPSAM_DISI_METNI =
  "Okul numarası ve sınıf/şube bilgisi şifrelenmez (sıralama, arama ve " +
  "süzgeçler bunlara dayanır).";

/** Kurtarma anahtarı diyaloğunun uyarısı. */
export const KURTARMA_UYARISI =
  "Bu anahtar bir daha gösterilmez. Parolanızı unutursanız kayıtlara ERİŞMENİN " +
  "TEK YOLU budur. Yazdırın veya elle yazıp okul kasasında saklayın; " +
  "bilgisayarın kendisinde saklamayın.";

/** Parola kurma açıklaması (yalnız ilk kurulumda; parola kaldırılamaz). */
export const KURMA_UYARISI =
  "Yönetici parolası zorunludur: parola kurulmadan öğrenci ve personel kaydı " +
  "yapılamaz. Kurulduktan sonra kaldırılamaz, yalnız değiştirilebilir. Kurulumdan " +
  "sonra gösterilecek kurtarma anahtarını mutlaka saklayın.";

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
