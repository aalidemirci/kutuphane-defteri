// "Başlangıç Yol Haritası" kartı — Genel Bakış'ta, kurulum bittikten sonra
// (tasarım §14.1 F1). Programı okulda kullanmaya başlamak için sıradaki işleri
// sıralar; her madde ilgili sayfaya bağlanır. Bütün maddeler tamamlanınca kart
// gizlenebilir.
//
// İki tür madde vardır:
// * KENDİLİĞİNDEN tespit edilenler — `setup/status/` sayılarından: öğrenci ve
//   personel aktarımı (sayı > 0), aktif ders yılında öğrenciye kapalı gün (> 0).
// * KULLANICININ İŞARETLEDİKLERİ — program bunların yapıldığını bilemez (zarfın
//   kapatılması, parolanın paylaşılması, BTR görüşmesi). Şablon maddesi indirme
//   başarılı olunca kendiliğinden işaretlenir, elle de işaretlenebilir.
// İşaretler `SchoolConfig.yol_haritasi`'nda (backend) durur, tarayıcı
// depolamasında DEĞİL: yönetim yüzeyi her açılışta rastgele portta dinler, köken
// değiştiği için `localStorage` açılışlar arasında taşınmaz. İşaretler kişisel
// veri içermez (madde + tarih).
//
// Kurtarma anahtarının saklandığı sunucuda doğrulanmamışsa (kurulumu bu karardan
// önce tamamlanmış program ya da yenilenip doğrulanmamış anahtar — F1 eki,
// 22.09.2026 kararı 2) kartın başında uyarı ve Güvenlik ayarlarına bağlantı durur.

import { Link } from "react-router-dom";

import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { DOGRULANMADI_BASLIGI } from "../guvenlik/metinler";
import { useKatalogSablonuIndirme } from "../kutuphane/useKatalogSablonu";
import type { RoadmapManualItem, SetupStatus } from "../okul/api";

type OtomatikMadde = "ogrenci_aktarimi" | "personel_aktarimi" | "kapali_gunler";

interface MaddeTanimi {
  anahtar: OtomatikMadde | RoadmapManualItem;
  baslik: string;
  aciklama: string;
  bag?: { to: string; etiket: string };
}

/** Maddeler, sırasıyla (sözlük: "öğrenciye kapalı gün", "kurtarma anahtarı", "BTR"). */
export const YOL_HARITASI_MADDELERI: readonly MaddeTanimi[] = [
  {
    anahtar: "ogrenci_aktarimi",
    baslik: "e-Okul öğrenci listesini aktarın",
    aciklama:
      "e-Okul'dan aldığınız öğrenci listesini Kişiler ekranından aktarın. Önce önizleme gösterilir; kayıtlar yalnız siz onaylayınca yazılır.",
    bag: { to: "/kisiler", etiket: "Kişiler'e git" },
  },
  {
    anahtar: "personel_aktarimi",
    baslik: "Öğretmen ve diğer personel listesini aktarın",
    aciklama:
      "e-Okul'daki Personel Listesi'ni Kişiler ekranının “Öğretmenler ve Diğer Personel” sekmesinden aktarın.",
    bag: { to: "/kisiler?tab=personel", etiket: "Kişiler'e git" },
  },
  {
    anahtar: "kapali_gunler",
    baslik: "Öğrenciye kapalı günleri girin (ara tatil, yarıyıl)",
    aciklama:
      "Resmî ve dini tatiller kurulumda eklendi. Ara tatil ve yarıyıl tarihlerini girin; iade tarihi bu günlere denk gelirse izleyen ilk açık güne kayar.",
    bag: { to: "/ayarlar?tab=kapali-gunler", etiket: "Kapalı Günler'e git" },
  },
  {
    anahtar: "katalog_sablonu",
    baslik: "Katalog Excel şablonunu indirip doldurmaya başlayın",
    aciklama:
      "Kitap listenizi katalog ekranlarını beklemeden bu şablonla Excel'de hazırlayabilirsiniz. Şablonu indirdiğinizde madde kendiliğinden işaretlenir.",
  },
  {
    anahtar: "kurtarma_zarfi",
    baslik: "Kurtarma anahtarını müdürlükte kapalı zarfta saklayın",
    aciklama:
      "Kurtarma anahtarı çıktısını zarfa koyup kapatın ve müdürlükte kilitli dolapta saklayın. PDF dosyasını bu bilgisayarda bırakmayın.",
    bag: { to: "/ayarlar?tab=guvenlik", etiket: "Güvenlik ayarları" },
  },
  {
    anahtar: "parola_paylasimi",
    baslik: "Yönetici parolasını en az iki görevlendirilmiş kişiyle paylaşın",
    aciklama:
      "Parolayı bilen tek kişi okuldan ayrılır ya da parolayı unutursa kayıtlara yalnız kurtarma anahtarıyla erişilir. Parolayı masadaki görevlilere vermeyin; görevliler görevli kipinde çalışır.",
    bag: { to: "/ayarlar?tab=guvenlik", etiket: "Güvenlik ayarları" },
  },
  {
    anahtar: "btr_gorusmesi",
    baslik: "Ağ Kataloğu için bilişim teknolojileri rehber öğretmeniyle (BTR) görüşün",
    aciklama:
      "Ağ Kataloğu, okul ağındaki bilgisayar ve etkileşimli tahtalardan kitap aramayı sağlar; kişisel veri göstermez. Okul ağında açılmadan önce BTR'nin bilgisi alınır.",
    // Çapalı adres: kılavuz açılınca doğrudan "Ağ Kataloğu" bölümüne kayar
    // (KilavuzPage sayfa içi çapayı kendisi uygular).
    bag: { to: "/kilavuz#ag-katalogu", etiket: "Kılavuz'da okuyun" },
  },
];

const OTOMATIK: ReadonlySet<string> = new Set<OtomatikMadde>([
  "ogrenci_aktarimi",
  "personel_aktarimi",
  "kapali_gunler",
]);

function otomatikTamam(anahtar: OtomatikMadde, durum: SetupStatus): boolean {
  if (anahtar === "ogrenci_aktarimi") return durum.student_count > 0;
  if (anahtar === "personel_aktarimi") return durum.personnel_count > 0;
  return durum.school_break_count > 0;
}

/** Madde tamam mı? Kendiliğinden tespit edilenler sayılardan, diğerleri işaretten. */
export function maddeTamamMi(anahtar: MaddeTanimi["anahtar"], durum: SetupStatus): boolean {
  if (OTOMATIK.has(anahtar)) return otomatikTamam(anahtar as OtomatikMadde, durum);
  return Boolean(durum.roadmap.marks[anahtar as RoadmapManualItem]);
}

interface BaslangicYolHaritasiProps {
  durum: SetupStatus;
  /** Elle işaretlenen bir maddeyi işaretler / işareti kaldırır. */
  onIsaretle: (madde: RoadmapManualItem, yapildi: boolean) => void;
  /** Bütün maddeler tamamken kartı gizler. */
  onGizle: () => void;
}

export default function BaslangicYolHaritasi({
  durum,
  onIsaretle,
  onGizle,
}: BaslangicYolHaritasiProps) {
  const sablon = useKatalogSablonuIndirme(() => {
    if (!durum.roadmap.marks.katalog_sablonu) onIsaretle("katalog_sablonu", true);
  });
  const tamamSayisi = YOL_HARITASI_MADDELERI.filter((m) => maddeTamamMi(m.anahtar, durum)).length;
  const toplam = YOL_HARITASI_MADDELERI.length;
  const hepsiTamam = tamamSayisi === toplam;

  return (
    <Card elevation={1} className="p-5 sm:p-6">
      <section aria-labelledby="yol-haritasi-baslik">
        <div className="flex items-start gap-4">
          <span
            aria-hidden="true"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-primary-container text-primary"
          >
            <Icon name="flag" />
          </span>
          <div className="min-w-0 flex-1">
            <h2
              id="yol-haritasi-baslik"
              className="text-title-medium font-semibold text-on-surface"
            >
              Başlangıç Yol Haritası
            </h2>
            <p className="mt-1 text-body-medium text-on-surface-variant">
              Programı okulda kullanmaya başlamak için sıradaki işler. {toplam} maddeden{" "}
              {tamamSayisi} tanesi tamamlandı.
            </p>
            <div
              role="progressbar"
              aria-label="Yol haritası ilerlemesi"
              aria-valuemin={0}
              aria-valuemax={toplam}
              aria-valuenow={tamamSayisi}
              className="mt-3 h-2 overflow-hidden rounded-full bg-surface-container-high"
            >
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${Math.round((tamamSayisi / toplam) * 100)}%` }}
              />
            </div>
          </div>
        </div>

        {!durum.recovery_key_confirmed && (
          <div className="mt-4 flex items-start gap-2 rounded-shape-md bg-error-container px-4 py-3 text-body-medium text-on-error-container">
            <Icon name="key_off" />
            <div className="min-w-0">
              <p>
                <strong>{DOGRULANMADI_BASLIGI}.</strong> Parola unutulursa kayıtlara yalnız kurtarma
                anahtarıyla ulaşılır. Anahtarı sakladıysanız Güvenlik ayarlarında doğrulayın;
                kaydedemediyseniz aynı yerden yenisini üretin.
              </p>
              <Link
                to="/ayarlar?tab=guvenlik"
                className="mt-1 inline-flex items-center gap-1 text-label-large font-medium underline-offset-4 hover:underline"
              >
                Güvenlik ayarları
                <Icon name="arrow_forward" size="sm" />
              </Link>
            </div>
          </div>
        )}

        <ol className="mt-4 divide-y divide-outline-variant/50">
          {YOL_HARITASI_MADDELERI.map((madde) => {
            const tamam = maddeTamamMi(madde.anahtar, durum);
            const otomatik = OTOMATIK.has(madde.anahtar);
            const isaretTarihi = otomatik
              ? undefined
              : durum.roadmap.marks[madde.anahtar as RoadmapManualItem];
            return (
              <li key={madde.anahtar} className="flex items-start gap-3 py-3">
                <Icon
                  name={tamam ? "check_circle" : "radio_button_unchecked"}
                  className={tamam ? "mt-0.5 text-primary" : "mt-0.5 text-on-surface-variant"}
                />
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-body-large ${tamam ? "text-on-surface-variant" : "text-on-surface"}`}
                  >
                    {madde.baslik}
                    <span className="sr-only">{tamam ? " (tamamlandı)" : " (yapılacak)"}</span>
                  </p>
                  <p className="mt-0.5 text-body-small text-on-surface-variant">{madde.aciklama}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
                    {madde.bag && (
                      <Link
                        to={madde.bag.to}
                        className="inline-flex items-center gap-1 text-label-large font-medium text-primary underline-offset-4 hover:underline"
                      >
                        {madde.bag.etiket}
                        <Icon name="arrow_forward" size="sm" />
                      </Link>
                    )}
                    {madde.anahtar === "katalog_sablonu" && (
                      <Button
                        variant="text"
                        icon="download"
                        onClick={() => void sablon.indir()}
                        disabled={sablon.indiriliyor}
                      >
                        Şablonu indir
                      </Button>
                    )}
                    {otomatik ? (
                      !tamam && (
                        <span className="text-label-medium text-on-surface-variant">
                          Yapıldığında kendiliğinden işaretlenir.
                        </span>
                      )
                    ) : (
                      <label className="inline-flex min-h-10 items-center gap-2 text-label-large text-on-surface">
                        <input
                          type="checkbox"
                          checked={tamam}
                          onChange={(e) =>
                            onIsaretle(madde.anahtar as RoadmapManualItem, e.target.checked)
                          }
                          aria-label={`${madde.baslik} — yapıldı`}
                          className="size-5 accent-primary"
                        />
                        Yapıldı
                        {isaretTarihi && (
                          <span className="text-label-medium text-on-surface-variant">
                            · {formatDate(isaretTarihi)}
                          </span>
                        )}
                      </label>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        {hepsiTamam && (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-shape-md bg-secondary-container px-4 py-3 text-on-secondary-container">
            <span className="flex items-center gap-2 text-body-medium">
              <Icon name="celebration" />
              Bütün maddeler tamamlandı.
            </span>
            <Button variant="tonal" icon="visibility_off" onClick={onGizle}>
              Kartı gizle
            </Button>
          </div>
        )}
      </section>
    </Card>
  );
}
