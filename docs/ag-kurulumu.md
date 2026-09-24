# Kütüphane Defteri — Ağ Kataloğu Kurulum Kılavuzu (BTR için)

Bu belge okulun bilişim teknolojileri rehber öğretmeni (BTR) içindir. Kütüphane
yöneticisinin kılavuzu `docs/kurulum.md` §8'dir; burada ağ tarafının ayrıntısı
vardır. Örneklerde gerçek ağ bilgisi yerine yer tutucular kullanılır:
`<idari-ağ>`, `<tahta-ağı>`, `<ek-alt-ağ>`, `<bilgisayar-adı>`, `<IP>`, `<port>`.

## 1. Ne açılıyor?

Kütüphane Defteri, okulun kütüphane işlerini yürüttüğü yerel araçtır. Ağ
Kataloğu programın salt okur, kişisel veri içermeyen katalog sayfalarıdır:

- **Yön:** yalnız gelen bağlantı; `http://<IP>:<port>/` (varsayılan port 8765,
  TCP). Program bu porttan dışarı bağlantı başlatmaz.
- **Sunulan:** eser künyesi, sınıflama ve yer numarası, bölüm, nüsha özeti
  (rafta / ödünçte / ödünç verilmez), yeni gelenler, kütüphane saatleri.
- **Sunulmayan:** üye listesi ve adları, kart no, ödünç alan, iade tarihi,
  ödünç geçmişi, bağışçı, fiyat; yönetim ekranları, yedek, dışa aktarım.
- **Yöntemler:** yalnız GET/HEAD; gövde en çok 1 KB; çerez yok; JavaScript yok;
  dış kaynak yok (CSP `default-src 'none'`). Adres başına hız sınırı ve aynı
  adresten en çok 20 eşzamanlı bağlantı.
- **Günlük:** erişim günlüğü tutulmaz; istemci adresi ve arama terimi hiçbir
  yere yazılmaz. Yalnız kişisiz günlük sayılar bellekte durur.
- **Yönetim yüzeyi** yalnız `127.0.0.1`'de, rastgele bir portta ve oturum
  belirteciyle dinler; ağa hiçbir durumda açılmaz. Katalog portunda yönetim
  yollarının hepsi 404 döner.
- **Katalog internete çıkmaz.** Programın giden bağlantıları yalnız
  kullanıcının başlattığı güncelleme denetimi ve (açıksa) ISBN ile künye
  getirmedir; ayrıntı Ağ Hizmeti Bilgi Notu'ndadır (§6).

Ağ Kataloğu varsayılan olarak kapalıdır; yalnız yönetici kipinde açılır.

## 2. Kurulum (Windows)

1. Kurucuyu **kütüphane masası hesabında** başlatın; UAC penceresine yönetici
   kimliğinizi girin. Kurucuyu kendi oturumunuzda başlatırsanız otomatik
   başlatma görevi sizin hesabınıza yazılır ve program masa hesabında
   kendiliğinden açılmaz.
2. Görevler:
   - **Yerel ağdan katalog taramasına izin ver (güvenlik duvarı kuralı).**
     İlk kurulumda önce programın eski engelleme kuralları silinir
     (`netsh advfirewall firewall delete rule name=all dir=in program="<kurulum
     klasörü>\kutuphane-defteri.exe"`), sonra şu kural eklenir:

     ```
     netsh advfirewall firewall add rule name="Kutuphane Defteri Katalog" dir=in action=allow
       program="<kurulum klasörü>\kutuphane-defteri.exe" protocol=TCP localport=<port>
       remoteip=LocalSubnet profile=domain,private,public enable=yes
     ```

     `<port>` kayıt defterindeki `HKLM\SOFTWARE\KutuphaneDefteri\KatalogPortu`
     (DWORD) değeridir; yoksa 8765 yazılır. **Güncellemede** kural varsa silme
     ve ekleme adımları atlanır: değiştirilmiş port ve eklediğiniz bloklar
     korunur. Kaldırmada kural silinir.
   - **Oturum açılınca başlat.** Görev Zamanlayıcı'ya "Kutuphane Defteri"
     görevi, kurucuyu başlatan hesabın oturum açılışında tetiklenecek biçimde
     yazılır. İsteğe bağlı alt görev pencereyi açmadan tepside başlatır.
     Kaldırmada görev silinir.
3. Genel profil de kurala dahildir: okul ağları çoğu zaman "Genel" görünür.
   RFC1918'in tamamı açılmaz; MEB WAN'ındaki başka kurumların adresleri de özel
   aralıktadır.

**Program içi denetim.** Program, güvenlik duvarının yapılandırmasını
(`Get-NetFirewallRule -PolicyStore ActiveStore` ve ona bağlı uygulama, port,
adres filtreleri) okuyarak beş maddeyi denetler: kural etkin mi; program yolu
bu program mı; port ayarla aynı mı; kural etkin ağ profilini kapsıyor mu ve
uzak adres ne; program için gelen engelleme kuralı var mı. Biri tutmazsa ya da
denetim okunamazsa katalog **hiç dinlemez**. Uzak adres "her yer" ise yalnız
uyarı verilir. Denetimin yönetici olmayan masa hesabında çalıştığı sahada
doğrulanacaktır.

**Kuralı güncelleme.** Ağ Doktoru'ndaki "Kuralı ekle/güncelle" programı UAC ile
yükseltilmiş bir yardımcı kipte yeniden çalıştırır: kural silinip yeniden
yazılır (yerel alt ağ + Ayarlar → Ağ Kataloğu'ndaki tahta ağı blokları),
program için gelen engelleme kuralları kaldırılır, port HKLM değerine yazılır.
Yardımcı kip veri klasörüne, günlüğe ya da sizin hesabınızın profiline bir şey
yazmaz. Tahta ağı blokları yalnız sizin doğruladığınız dar bloklardır (en geniş
`/16`).

**Üçüncü parti güvenlik duvarları.** Antivirüs yazılımının kendi güvenlik
duvarı Windows kuralını yok sayabilir; o yazılımda da programa yerel ağdan
gelen bağlantı için izin verin.

## 3. Pardus

Paket kural **açmaz**; iki tanım bırakır:

- ufw uygulama profili: `/etc/ufw/applications.d/kutuphane-defteri`
  (`[Kutuphane Defteri]`, `ports=8765/tcp`);
- firewalld servisi: `/usr/lib/firewalld/services/kutuphane-defteri.xml`.

Kuralı siz açarsınız:

```bash
# ufw
sudo ufw allow from <idari-ağ> to any app 'Kutuphane Defteri'
sudo ufw allow from <tahta-ağı> to any app 'Kutuphane Defteri'
# firewalld (kaynaksız --add-service katalogu her adrese açar; kullanmayın)
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<idari-ağ>" service name="kutuphane-defteri" accept'
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<tahta-ağı>" service name="kutuphane-defteri" accept'
sudo firewall-cmd --reload
```

Port programda değiştirildiyse ya da program taşınabilir arşivden kurulduysa
(tanım dosyaları yalnız `.deb` ile gelir) profil yerine portu açın (`sudo ufw
allow from <idari-ağ> to any port <port> proto tcp`; firewalld'de zengin kuralda
`port port="<port>" protocol="tcp"`). Ağ Doktoru bilgisayardaki aracı ve bu
bilgisayarın yerel ağı ile Ayarlar'daki tahta ağı bloklarından üretilmiş komutu
gösterir.

## 4. Adres ve ağ yapısı

1. **Sabit adres.** Kütüphane bilgisayarına DHCP'de MAC adresine bağlı
   rezervasyon yapın. Afiş, yer imleri ve PYS talebi bu adresi taşır. Program
   gün değişiminde adresi denetler ve değiştiyse "afişi yeniden basın, yer
   imlerini güncelleyin" uyarısı verir. Bilgisayar değişirse rezervasyonu yeni
   kartın MAC adresine taşıyın.
2. **Ağ keşfi.** Kütüphane bilgisayarının (`<idari-ağ>`) ve tahtaların
   (`<tahta-ağı>`) aynı bölümde olup olmadığını öğrenin. Aynı bölüm içindeki
   trafik merkezi filtreye uğramaz. Tahtada bir tarayıcıyla
   `http://<IP>:<port>/` adresini deneyin; açılmıyorsa:
   - tahta tarayıcısının vekil sunucu (proxy) ayarı yerel adresi vekil sunucuya
     gönderiyor olabilir — yerel adres için vekil sunucu istisnası sizin
     yetkinizdedir;
   - bölümler arası geçiş kapalı olabilir — bu okulda değiştirilemez (§5).
3. **Çok ağ bağlantılı bilgisayar.** Ayarlar → Ağ Kataloğu'nda "Yalnız seçili IP
   adresinde" seçilirse katalog yalnız o adreste dinler. Ağ Doktoru varsayılan
   bağlantı dışındaki bağlantıları "katalog bu ağda da erişilebilir" uyarısıyla
   listeler.

## 5. Tahta ağından erişim kapalıysa

**PYS talebi.** Ağ Doktoru'ndaki "PYS talep metnini kopyala" FATİH PYS'ye
yapıştırılacak metni hazırlar. Talep "internet ya da site açma" diye değil,
**"yerel ağ VLAN düzenlemesi — tek yön, TCP/<port>"** diye yazılmalıdır; yoksa
filtre birimine gider. Metin kaynak blokları (`<tahta-ağı>`), hedef adresi
(`<IP>`), yönü (tahtadan kütüphane bilgisayarına), protokolü ve portun
gerekçesini içerir. Zincir: BTR → okul müdürü → FATİH PYS → il/ilçe →
yüklenici. Süre okulun elinde değildir.

**Yedek yollar** yalnız ilçe sistem yöneticisinin uygun görüşüyle kullanılır:

- **Bilgisayarı tahta ağındaki bir porta bağlamak.** Bu durumda bilgisayar
  öğrenci erişimli ağdadır; masa hesabında kişisel oturum açılmaması daha da
  önemlidir.
- **İkinci ağ kartı** (`<ek-alt-ağ>`). IP yönlendirme **kapalı** olmalıdır
  (Windows: `Get-NetIPInterface` Forwarding / `IPEnableRouter`); Ağ Doktoru
  açık olduğunu görürse uyarır. Katalog yalnız seçilen bağlantıda dinlesin
  ("Yalnız seçili IP adresinde").

## 6. Ağ Hizmeti Bilgi Notu

Ağ Doktoru'ndan basılan not sizin ve okul müdürünün imzasına sunulur ve okulda
saklanır. İzin değil bilgi notudur; gerekirse ilçeye gönderilecek üst yazının
eki olarak kullanılır. İçeriği: bilgisayarın demirbaş no'su, adres ve port,
portun gerekçesi, kuraldaki **gerçek** uzak adres ve profil değerleri, beş
denetimin sonucu, neyin sunulup neyin sunulmadığı, kişisel veri bulunmadığı,
programın giden bağlantıları ve sınama komutları, Bilgi ve Sistem Güvenliği
Yönergesi atıfları (md. 5/11, 11/16, 11/22; 11/7 notu; künye getirme açıksa
11/12 ve 11/19). Not yerel üretildiği için gerçek adresleri içerir; depoya ya
da herkese açık bir yere konmaz.

## 7. Sınama

Okul ağındaki başka bir Windows bilgisayarda:

```powershell
Test-NetConnection <IP> -Port <port>
```

`TcpTestSucceeded : True` görülmelidir. Ağ Doktoru'ndaki "Dinleyiciyi sına"
yalnız dinleyicinin her bağlantıda ayakta olduğunu gösterir; güvenlik duvarını
ya da bölümler arası geçişi **kanıtlamaz**, çünkü bilgisayarın kendi adresine
yapılan bağlantı ağa çıkmaz.

Pardus'tan: `curl -I http://<IP>:<port>/` (yanıt `200 OK` ve
`Content-Security-Policy` başlığı taşır).

## 8. Yer imleri

Ağ Doktoru'ndaki "Yer imi dosyalarını üret" bir arşiv indirir:

| Dosya | Nereye | Ne yapar |
|---|---|---|
| `pardus-etap/kutuphane-katalogu-chromium.json` | `/etc/chromium/policies/managed/kutuphane-katalogu.json` | Chromium'un yönetilen yer imi (`ManagedBookmarks`); bütün hesaplarda görünür |
| `pardus-etap/kutuphane-katalogu.desktop` | `/usr/share/applications/` | Uygulama menüsü kısayolu; varsayılan tarayıcıda açar |
| `windows/Kutuphane-Katalogu.url` | masaüstü ya da ortak masaüstü | Öğretmen ve laboratuvar bilgisayarları |
| `windows/Kutuphane-Katalogu-Tahta.url` | Windows tahtalar | Tahta kipi (büyük dokunma düzeni) |

Tahtaya giden adresler `?tahta=1` taşır. Kullanıcı başına yer imi yetmez:
tahtalarda her öğretmenin ayrı hesabı olabilir. Toplu dağıtım (ör. Liderahenk)
sizin yetkinizdedir. Adres değişince dosyaları yeniden üretip eskilerin yerine
koyun.

Chromium yönetilen yer imlerini yer imleri menüsünde "Okul" klasöründe gösterir;
yer imi çubuğunu varsayılan olarak yalnız yeni sekme sayfasında açar. Çubuğun her
sayfada görünmesi isteniyorsa okulun kararıyla politika dosyasına
`"BookmarkBarEnabled": true` eklenir. Tahtada `ManagedBookmarks` içeren başka bir
politika dosyası varsa ikisini tek dosyada birleştirin: aynı politika iki dosyada
tanımlanırsa yalnız biri geçerli olur.

## 9. Bilinen sınırlar

- Windows oturumu açılmadan ne program ne katalog çalışır.
- Windows'un taşınabilir paketinde Ağ Kataloğu sunulmaz (kural kurulu
  programın yoluna bağlıdır). Pardus'un taşınabilir arşivinde katalog açılır;
  ufw/firewalld tanımı gelmediği için port temelli komut kullanılır (§3).
- Katalogda TLS yoktur: kişisel veri taşımadığı için düz HTTP'dir. Tarayıcıların
  `http://<IP>:<port>` adresini HTTPS'e zorlamadan açtığı sahada
  doğrulanacaktır.
- Ağ Kataloğu açıkken bilgisayarın boşta uykuya geçmesi engellenir; kapak
  kapatma ve elle uyutma engellenmez.
