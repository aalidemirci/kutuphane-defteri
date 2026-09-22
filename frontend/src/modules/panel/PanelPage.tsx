// Genel Bakış (hub). Sayfanın TEK adı "Genel Bakış"tır (gezinme + üst çubuk + h1 —
// docs/sozluk.md §4); kart başlıkları gittikleri sayfanın h1'iyle aynıdır.
//
// Kartlar: "Başlangıç Yol Haritası" (kurulumdan sonra sıradaki işler; bütün
// maddeler tamamlanınca gizlenebilir — tasarım §14.1 F1), "Ayrılış Havuzu" (havuz
// boş değilse "N kişi ayrılış kararı bekliyor" — F1 eki 7), modül kartları ve
// "Katalog Excel Şablonu" (bir sayfaya gitmez, şablonu indirir — tasarım §8.1;
// indirme yol haritasının şablon maddesini de işaretler). Diğer pano kartları
// (temiz kapanış uyarısı…) kendi fazlarında gelir.
//
// Durum `GET /setup/status/`'tan tek kez okunur (kişisel veri yok). Okunamazsa
// yol haritası gösterilmez; sayfanın geri kalanı çalışır.

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import HubFeatureCard from "../../ui/HubFeatureCard";
import { useSnackbar } from "../../ui/SnackbarProvider";
import KatalogSablonuKarti from "../kutuphane/KatalogSablonuKarti";
import { okulApi } from "../okul/api";
import type { RoadmapManualItem, SetupStatus } from "../okul/api";
import AyrilisHavuzuKarti from "./AyrilisHavuzuKarti";
import BaslangicYolHaritasi from "./BaslangicYolHaritasi";

export default function PanelPage() {
  const snackbar = useSnackbar();
  const [durum, setDurum] = useState<SetupStatus | null>(null);

  useEffect(() => {
    let iptal = false;
    okulApi
      .getSetupStatus()
      .then((s) => {
        if (!iptal) setDurum(s);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  const isaretle = useCallback(
    async (madde: RoadmapManualItem, yapildi: boolean) => {
      try {
        const roadmap = await okulApi.markRoadmapItem(madde, yapildi);
        setDurum((d) => (d ? { ...d, roadmap } : d));
      } catch (e) {
        snackbar.error(e instanceof ApiError ? e.message : "İşaret kaydedilemedi.");
      }
    },
    [snackbar],
  );

  const gizle = useCallback(async () => {
    try {
      const roadmap = await okulApi.setRoadmapHidden(true);
      setDurum((d) => (d ? { ...d, roadmap } : d));
      snackbar.success("Başlangıç yol haritası gizlendi.");
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Kart gizlenemedi.");
    }
  }, [snackbar]);

  // Kart üzerinden indirilen şablon da yol haritasının maddesini işaretler.
  const sablonIndirildi = useCallback(() => {
    if (durum && !durum.roadmap.marks.katalog_sablonu) void isaretle("katalog_sablonu", true);
  }, [durum, isaretle]);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">
          Genel Bakış
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Okulun kütüphane işlerini yürüttüğü yerel araç. Veriler yalnız bu bilgisayarda durur.
        </p>
      </header>
      {durum && !durum.roadmap.hidden && (
        <BaslangicYolHaritasi
          durum={durum}
          onIsaretle={(madde, yapildi) => void isaretle(madde, yapildi)}
          onGizle={() => void gizle()}
        />
      )}
      {/* Havuz boşsa görünmez; yalnız sayı okunur (F1 eki 7). */}
      <AyrilisHavuzuKarti />
      <div className="grid gap-4 sm:grid-cols-2">
        <HubFeatureCard
          to="/kisiler"
          icon="group"
          title="Kişiler"
          description="Öğrenci, öğretmen ve diğer personel sicili; e-Okul listelerinden içe aktarma."
        />
        <HubFeatureCard
          to="/ayarlar"
          icon="settings"
          title="Ayarlar"
          description="Ders yılı, şubeler, okul bilgileri, güvenlik, yedek ve güncelleme."
        />
      </div>
      <KatalogSablonuKarti onIndirildi={sablonIndirildi} />
    </div>
  );
}
