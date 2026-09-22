// Kurulum kapısı (DD kalıbı) — programın İLK açılışında kullanıcıyı kurulum
// sihirbazına kilitler. Kapıyı açan koşul kurulumun tamamlanmış olması VE yönetici
// parolasının kurulu olmasıdır (tasarım §6.3-1: parola sihirbazın atlanamaz ilk
// adımıdır, isteğe bağlı değildir). Parola yoksa — kurulum eskiden tamamlanmış
// bir veritabanında bile — kullanıcı sihirbaza, ilk eksik adım olan parola
// adımına gider. Okul künyesi girilmeden resmî evrak antedi boş çıkar, aktif
// ders yılı olmadan da şube kataloğu ve e-Okul aktarımı yanlış yıla bağlanır.
// Bu yüzden `GET /setup/status/` bu iki koşulu sağlamadığı sürece "/kurulum"
// dışındaki her rota oraya yönlendirilir. (Kilit ekranı ayrı kapıdır:
// `modules/guvenlik/GuvenlikKapisi`, bu kapının dışında durur.)
//
// Kapı FAIL-OPEN'dır: durum okunamazsa (backend kapalı/uç hata) kullanıcı içeri
// alınır — sihirbaz da aynı backend'e muhtaç olduğundan kilitlemek çıkmaz sokak olurdu.

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { okulApi } from "./modules/okul/api";
import { SkeletonList } from "./ui/Skeleton";

/** Okunan durum, HANGİ yol için okunduğuyla birlikte tutulur — yol değişince bayatlar. */
interface KapiSonucu {
  yol: string;
  tamam: boolean;
}

/**
 * Yönlendirmenin sebebi sihirbaza gezinme durumuyla taşınır: üst menü kapı
 * devredeyken de görünür olduğundan (AppShell), sekmeye tıklayan kullanıcı aksi
 * halde sessizce geri sekerdi. Sihirbaz bu bilgiyle "neden buradasınız"ı yazar.
 */
export interface KapiYonlendirmesi {
  /** Kullanıcının gitmek istediği yol (ör. "/kisiler"). */
  kapiYonlendirdi: string;
}

export default function KurulumKapisi({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const kurulumdaMi = pathname === "/kurulum" || pathname.startsWith("/kurulum/");

  const [sonuc, setSonuc] = useState<KapiSonucu | null>(null);
  // Kurulum bir kez tamamlandıysa geri alınamaz: kapı kalıcı açılır, durum bir
  // daha sorulmaz (her gezinmede gereksiz istek çıkmaz).
  const tamamRef = useRef(false);

  // Rota her değiştiğinde durum yeniden okunur. Sebep: kullanıcı sihirbazı bitirip
  // "/"e gittiğinde elimizdeki "eksik" sonucu bayattır; tazelenmezse sihirbaza
  // geri sekerdi. Tamamlanmış kurulumda `tamamRef` kısa devre yapar.
  useEffect(() => {
    if (tamamRef.current) return;
    let iptal = false;
    okulApi
      .getSetupStatus()
      .then((s) => {
        if (iptal) return;
        // Parola bir kez kurulunca kaldırılamaz; kurulum da geri alınmaz — kapı
        // kalıcı açılabilir.
        const tamam = s.setup_completed && s.password_set;
        tamamRef.current = tamam;
        setSonuc({ yol: pathname, tamam });
      })
      .catch(() => {
        // Fail-open (dosya başı notu): durum okunamıyorsa kapı açılır.
        if (iptal) return;
        tamamRef.current = true;
        setSonuc({ yol: pathname, tamam: true });
      });
    return () => {
      iptal = true;
    };
  }, [pathname]);

  // Sihirbazın kendisi durum beklenmeden açılır: hem ilk açılışta bekleme olmaz,
  // hem de kurulum tamamlandıktan sonra ayarları gözden geçirmek için elle
  // "/kurulum" adresine girilebilir kalır.
  if (kurulumdaMi) return <>{children}</>;

  if (tamamRef.current) return <>{children}</>;

  // Bu yol için taze sonuç yok (ilk açılış ya da sihirbazdan yeni çıkıldı):
  // içerik yerine iskelet. Karar render sırasında verilir — effect'e bırakılsaydı
  // bayat "eksik" sonucuyla aynı commit'te sihirbaza sekerdi.
  if (!sonuc || sonuc.yol !== pathname) {
    return <SkeletonList rows={3} className="mx-auto max-w-3xl" />;
  }

  if (!sonuc.tamam) {
    const sebep: KapiYonlendirmesi = { kapiYonlendirdi: pathname };
    return <Navigate to="/kurulum" replace state={sebep} />;
  }

  return <>{children}</>;
}
