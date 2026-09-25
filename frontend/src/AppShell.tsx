import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import CikisDugmesi from "./modules/cikis/CikisDugmesi";
import UpdateBanner from "./modules/guncelleme/UpdateBanner";
import { GOREVLI_EKRANI_BASLIGI } from "./modules/kip/GorevliEkrani";
import KipGostergesi from "./modules/kip/KipGostergesi";
import { useKip } from "./modules/kip/useKip";
import DensitySwitcher from "./ui/DensitySwitcher";
import { DurumBasligiSaglayici, useDurumBasligiYonetimi } from "./ui/DurumBasligi";
import Icon from "./ui/Icon";
import ThemeSwitcher from "./ui/ThemeSwitcher";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

// Gezinme etiketi KISA addır (docs/sozluk.md §4). Ana sayfanın tek adı "Genel
// Bakış"tır (gezinme + üst çubuk + h1). Kütüphane ekranları (katalog, dolaşım,
// sayım…) fazlarıyla birlikte eklenir. Liste `App.test.tsx` "kabuk gezinmesi"
// testiyle sabittir.
const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Genel Bakış", icon: "space_dashboard" },
  // F6: masa işi en sık yapılan iştir; Genel Bakış'ın hemen altında durur.
  { to: "/dolasim", label: "Dolaşım Masası", icon: "sync_alt" },
  { to: "/kisiler", label: "Kişiler", icon: "group" },
  { to: "/katalog", label: "Katalog", icon: "menu_book" },
  { to: "/ayarlar", label: "Ayarlar", icon: "settings" },
  { to: "/kilavuz", label: "Kılavuz", icon: "auto_stories" },
];

// Üst çubuk başlığı sayfanın h1'iyle AYNIDIR (docs/sozluk.md §4) — Başlık
// Düzeninde tam ad. Bir sayfanın h1'i değişirse burası da değişir; eşlik
// `App.test.tsx` "üst çubuk başlığı" testiyle korunur.
const PAGE_TITLES: Array<[prefix: string, title: string]> = [
  // F7: Dolaşım Masası'nın alt sayfaları köke göre ÖNCE gelir.
  ["/dolasim/teslimler", "Teslimler"],
  ["/dolasim/kayip-hasar", "Kayıp ve Hasar"],
  ["/dolasim", "Dolaşım Masası"],
  ["/kisiler", "Kişiler"],
  ["/gecikmis-oduncler", "Gecikmiş Ödünçler"],
  // F7 (İ kolu): menüde yok; Genel Bakış kartlarından ve birbirlerinin bağlantılarından açılır.
  ["/ilisik-listesi", "İlişik Listesi"],
  ["/yil-sonu", "Yıl Sonu"],
  ["/yil-basi", "Yıl Başı"],
  // Sıra anlamlıdır: alt sayfalar köke göre ÖNCE gelir ("/katalog/eser/3"
  // "/katalog" desenine de uyar, önce kendi başlığını bulmalıdır.)
  ["/katalog/eser", "Eser Ayrıntısı"],
  ["/katalog/edinimler", "Edinimler ve Bağışlar"],
  ["/katalog/ice-aktarma", "İçe Aktarma"],
  ["/katalog/hizli-kayit", "Hızlı Kayıt"],
  ["/katalog/etiketler", "Etiketler"],
  ["/katalog", "Katalog"],
  ["/ayarlar", "Ayarlar"],
  ["/ag-doktoru", "Ağ Doktoru"],
  ["/kilavuz", "Kullanım Kılavuzu"],
  ["/hakkinda", "Hakkında ve Lisans"],
  ["/kurulum", "Kurulum Sihirbazı"],
  ["/", "Genel Bakış"],
];

const COLLAPSE_KEY = "kutuphane-defteri-sidebar-collapsed";

function pageTitle(pathname: string): string {
  return (
    PAGE_TITLES.find(([prefix]) =>
      prefix === "/" ? pathname === "/" : pathname.startsWith(prefix),
    )?.[1] ?? "Kütüphane Defteri"
  );
}

function navLinkClass(isActive: boolean, collapsed: boolean): string {
  const base = `group relative flex min-h-11 items-center overflow-hidden rounded-shape-md text-label-large font-medium transition-all duration-short-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
    collapsed ? "justify-center px-2" : "gap-3 px-3"
  }`;
  return isActive
    ? `${base} bg-sidebar-active text-on-sidebar shadow-elevation-1`
    : `${base} text-on-sidebar-muted hover:bg-on-sidebar/8 hover:text-on-sidebar`;
}

function SidebarContent({
  collapsed,
  gorevli,
  onNavigate,
}: {
  collapsed: boolean;
  /** Görevli kipinde yönetici ekranlarının bağlantıları gösterilmez (tasarım §4.4). */
  gorevli: boolean;
  onNavigate?: () => void;
}) {
  return (
    <>
      <div
        className={`flex h-20 shrink-0 items-center border-b border-on-sidebar/10 ${
          collapsed ? "justify-center px-2" : "gap-3 px-4"
        }`}
      >
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-on-sidebar/95 shadow-elevation-2">
          <img src="/app-logo.png" alt="" className="h-10 w-10 object-contain" />
        </span>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-title-medium font-semibold tracking-tight text-on-sidebar">
              Kütüphane Defteri
            </p>
          </div>
        )}
      </div>

      {!collapsed && (
        <p className="px-5 pb-2 pt-5 text-label-small font-semibold uppercase tracking-widest text-on-sidebar-muted/70">
          Çalışma alanı
        </p>
      )}
      <nav aria-label="Ana gezinme" className="flex flex-1 flex-col gap-1.5 px-3 py-2">
        {/* Görevli kipinde rotalar zaten görevli ekranına düşer (KipKapisi);
            bağlantılar gösterilmez ki masadaki görevli boşuna tıklamasın. */}
        {(gorevli ? [] : NAV_ITEMS).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            title={collapsed ? item.label : undefined}
            aria-label={collapsed ? item.label : undefined}
            onClick={onNavigate}
            className={({ isActive }) => navLinkClass(isActive, collapsed)}
          >
            <span aria-hidden="true" className="state-layer" />
            <Icon name={item.icon} size="xl" filled className="relative z-10 shrink-0 opacity-95" />
            {!collapsed && <span className="relative z-10 truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-1 border-t border-on-sidebar/10 p-3">
        {!collapsed && (
          <div className="mb-2 rounded-shape-md border border-on-sidebar/10 bg-on-sidebar/5 px-3 py-2.5">
            <p className="flex items-center gap-2 text-label-medium text-on-sidebar">
              <span className="h-2 w-2 rounded-full bg-success" />
              Yerel çalışma
            </p>
            <p className="mt-0.5 text-body-small text-on-sidebar-muted">Veriler bu cihazda</p>
          </div>
        )}
        {!gorevli && (
          <NavLink
            to="/hakkinda"
            title={collapsed ? "Hakkında ve Lisans" : undefined}
            aria-label={collapsed ? "Hakkında ve Lisans" : undefined}
            onClick={onNavigate}
            className={({ isActive }) => navLinkClass(isActive, collapsed)}
          >
            <span aria-hidden="true" className="state-layer" />
            <Icon name="info" size="xl" filled className="relative z-10 shrink-0 opacity-95" />
            {!collapsed && <span className="relative z-10 truncate">Hakkında ve Lisans</span>}
          </NavLink>
        )}
        <DensitySwitcher
          collapsed={collapsed}
          className="text-on-sidebar-muted hover:bg-on-sidebar/8 hover:text-on-sidebar"
        />
        <div
          className={`flex min-h-10 items-center rounded-shape-md ${
            collapsed ? "justify-center" : "gap-1 px-1"
          }`}
        >
          <ThemeSwitcher className="text-on-sidebar-muted hover:bg-on-sidebar/8 hover:text-on-sidebar" />
          {!collapsed && <span className="text-label-large text-on-sidebar-muted">Tema</span>}
        </div>
      </div>
    </>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(
    () => window.localStorage.getItem(COLLAPSE_KEY) === "true",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const gorevli = useKip().ozet?.durum === "gorevli";
  // Program durumu ekranları (kilitli, güvenlik dosyası kayıp, yeniden başlat)
  // açıkken üst çubukta o ekranın h1'i yazar — sözlük §4.2. Adrese bağlı
  // olmadıkları için başlığı kendileri bildirir (ui/DurumBasligi).
  const { durumBasligi, yaz } = useDurumBasligiYonetimi();
  // Görevli kipinde her rota görevli ekranını gösterir; başlık onun h1'idir.
  const title = durumBasligi ?? (gorevli ? GOREVLI_EKRANI_BASLIGI : pageTitle(location.pathname));

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(COLLAPSE_KEY, String(next));
      return next;
    });
  };

  return (
    <div className="flex min-h-screen bg-surface text-on-surface">
      <aside
        className={`kd-sidebar-glow sticky top-0 z-40 hidden h-screen shrink-0 flex-col transition-[width] duration-medium-1 ease-emphasized lg:flex ${
          collapsed ? "w-[4.75rem]" : "w-60"
        }`}
      >
        <SidebarContent collapsed={collapsed} gorevli={gorevli} />
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Kenar çubuğunu genişlet" : "Kenar çubuğunu daralt"}
          title={collapsed ? "Kenar çubuğunu genişlet" : "Kenar çubuğunu daralt"}
          className="absolute -right-3 top-24 flex h-7 w-7 items-center justify-center rounded-full border border-outline-variant bg-surface-container-lowest text-on-surface-variant shadow-elevation-2 transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name={collapsed ? "chevron_right" : "chevron_left"} size="sm" />
        </button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-outline-variant/70 bg-surface-container-lowest/95 px-4 backdrop-blur-md sm:px-5 lg:px-7">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Gezinme menüsünü aç"
            className="kd-icon-button lg:hidden"
          >
            <Icon name="menu" />
          </button>
          <img src="/app-logo.png" alt="" className="h-9 w-9 shrink-0 object-contain lg:hidden" />
          <div className="min-w-0 lg:w-48">
            <p className="truncate text-title-medium font-semibold text-on-surface">{title}</p>
            <p className="hidden truncate text-body-small text-on-surface-variant lg:block">
              Kütüphane Defteri
            </p>
          </div>

          {/* Tema anahtarı YALNIZ kenar çubuğundadır (görünüm ayarları bir arada:
              yoğunluk + tema; dar ekranda menü çekmecesinden erişilir). Eskiden
              burada ikinci bir kopyası vardı — aynı ayarın iki düğmesi hangisinin
              "asıl" olduğu sorusunu doğuruyordu. */}

          {/* Kip göstergesi (tasarım §4.4): kip adı, görsel geri sayım,
              "Görevli kipine geç" / "Yönetici kipine geç", "Kilitle". Kilitliyken
              ve kip okunamazsa boştur. */}
          <div className="ml-auto flex min-w-0 items-center gap-1">
            <KipGostergesi />
            {/* Çık (tasarım §4.2-4, TB13): her durumda görünür — tepsisi olmayan
                Linux masaüstünde programın tek çıkış yolu; görevli kipinde
                yönetici parolası ister. Tepsinin `kd:cik-iste` olayını da dinler. */}
            <CikisDugmesi />
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-x-hidden px-4 py-5 sm:px-5 lg:px-7 lg:py-6">
          <div className="mx-auto w-full max-w-[100rem]">
            {/* Güncelleme bandı açılışta DENETİM YAPMAZ (tasarım T11): yalnız
                Ayarlar → Güncelleme'deki elle denetimin sonucunu gösterir.
                Açılışta `/updates/` isteği çıkmadığı `App.test.tsx`'te sabittir.
                Görevli kipinde gizlidir: indirme yönetici işidir (§4.4). */}
            <UpdateBanner gizli={gorevli} />
            <DurumBasligiSaglayici yaz={yaz}>{children}</DurumBasligiSaglayici>
          </div>
        </main>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 animate-scrim-in bg-scrim/50 backdrop-blur-sm"
            aria-label="Gezinme menüsünü kapat"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="kd-sidebar-glow relative flex h-full w-72 animate-dialog-in flex-col shadow-elevation-4">
            <SidebarContent
              collapsed={false}
              gorevli={gorevli}
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      )}
    </div>
  );
}
