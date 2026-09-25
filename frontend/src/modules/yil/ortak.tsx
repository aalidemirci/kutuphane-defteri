// İlişik listesi ve yıl akışı ekranlarının ortak parçaları (F7 — tasarım §8.3).
//
// - `IlisikTablosu`: kişi satırları (son sınıflar ve ayrılanlar önce — sıra
//   sunucudadır); açık işler kaynak adı, barkod ve tarihle alt alta yazılır.
//   Kişi verisi yalnız yönetici kipinde görünür (görevli kipinde bu ekranlar açılmaz).
// - `SinifKitapliklari`: şube (sınıf kitaplığı) teslimleri kişisizdir, AYRI gösterilir;
//   her şubenin güncel teslim listesi (E15) basılabilir.
// - `YanEkranBaglantilari`: sayfanın sağ üstündeki bağlantılar (Katalog kalıbı).
//
// Seçim anahtarı "student:12" / "personnel:4" biçimindedir: öğrenci ve personel
// kimlikleri ayrı sayaçlardan gelir.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
import Card from "../../ui/Card";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { TD, TH } from "../uyelik/ortak";
import { acikIslerOzeti, TESLIM_LISTESI_ADI, yilApi } from "./api";
import type { IlisikSatiri, SinifKitapligi, YilAkislari } from "./api";

export { TD, TH };

/** Seçim anahtarı: "student:12" ya da "personnel:4". */
export function kisiAnahtari(s: Pick<IlisikSatiri, "person_type" | "person_id">): string {
  return `${s.person_type}:${s.person_id}`;
}

/** Seçilen anahtarları istek gövdesinin iki kimlik listesine ayırır. */
export function secimiAyir(secim: Set<string>): { studentIds: number[]; personnelIds: number[] } {
  const studentIds: number[] = [];
  const personnelIds: number[] = [];
  for (const anahtar of secim) {
    const [tur, kimlik] = anahtar.split(":");
    if (tur === "student") studentIds.push(Number(kimlik));
    else personnelIds.push(Number(kimlik));
  }
  return { studentIds, personnelIds };
}

const BAGLANTI_SINIFI =
  "inline-flex min-h-[var(--kd-control-height)] items-center gap-2 rounded-shape-md border border-outline-variant bg-surface-container-lowest px-4 text-label-large font-semibold text-primary transition hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";

export function YanEkranBaglantilari({
  baglantilar,
}: {
  baglantilar: Array<{ to: string; label: string; icon: string }>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {baglantilar.map((b) => (
        <Link key={b.to} to={b.to} className={BAGLANTI_SINIFI}>
          <Icon name={b.icon} size="lg" />
          {b.label}
        </Link>
      ))}
    </div>
  );
}

/** Metin içi bağlantı (adım kartlarında başka ekrana yönlendirme). */
export function MetinBaglantisi({ to, children }: { to: string; children: string }) {
  return (
    <Link
      to={to}
      className="inline-flex text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {children}
    </Link>
  );
}

/** Kişinin durum rozeti (sözlük: "Son sınıf", "Ayrıldı · gg.aa.yyyy", "Ayrılış kararı bekliyor"). */
export function DurumRozeti({ satir }: { satir: Pick<IlisikSatiri, "status_text" | "group"> }) {
  if (!satir.status_text) return null;
  const ton =
    satir.group === "graduating"
      ? "bg-primary-container text-on-primary-container"
      : "bg-tertiary-container text-on-tertiary-container";
  return (
    <span className={`inline-flex rounded-shape-sm px-2 py-0.5 text-label-small ${ton}`}>
      {satir.status_text}
    </span>
  );
}

function AcikIsler({ satir }: { satir: IlisikSatiri }) {
  return (
    <ul className="space-y-0.5">
      {satir.loans.map((lo) => (
        <li key={`o${lo.id}`}>
          <span className="font-medium">Ödünç</span> · {lo.work_title} ·{" "}
          <span className="tabular-nums">{lo.barcode_display}</span> · iade{" "}
          {formatDate(lo.due_date)}
          {lo.overdue_days > 0 && (
            <span className="text-error"> · {formatNumber(lo.overdue_days)} gün gecikti</span>
          )}
        </li>
      ))}
      {satir.deliveries.map((d) => (
        <li key={`t${d.id}`}>
          <span className="font-medium">Teslim</span> · {d.work_title} ·{" "}
          <span className="tabular-nums">{d.barcode_display}</span> · belge no {d.document_no}
        </li>
      ))}
      {satir.cases.map((c) => (
        <li key={`d${c.id}`}>
          <span className="font-medium">{c.case_type_display}</span> · {c.work_title} ·{" "}
          <span className="tabular-nums">{c.barcode_display}</span> · {c.resolution_display}
        </li>
      ))}
    </ul>
  );
}

/**
 * İlişik satırları tablosu. `secim` verilirse ilk sütunda seçim kutusu vardır;
 * `secilebilir` hangi satırın seçilebileceğini söyler (ör. yalnız açık işi olmayanlar).
 */
export function IlisikTablosu({
  satirlar,
  secim,
  onSecim,
  secilebilir = () => true,
  baslik,
}: {
  satirlar: IlisikSatiri[];
  secim?: Set<string>;
  onSecim?: (s: Set<string>) => void;
  secilebilir?: (s: IlisikSatiri) => boolean;
  baslik: string;
}) {
  const secimli = secim !== undefined && onSecim !== undefined;
  const adaylar = satirlar.filter(secilebilir).map(kisiAnahtari);
  const secilen = secimli ? adaylar.filter((a) => secim.has(a)).length : 0;
  const hepsi = adaylar.length > 0 && secilen === adaylar.length;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body-small">
        <caption className="sr-only">{baslik}</caption>
        <thead>
          <tr className="border-b border-outline-variant">
            {secimli && (
              <th className={TH}>
                <input
                  type="checkbox"
                  aria-label="Bu sayfadakilerin tümünü seç"
                  checked={hepsi}
                  disabled={adaylar.length === 0}
                  ref={(el) => {
                    if (el) el.indeterminate = secilen > 0 && !hepsi;
                  }}
                  onChange={(e) => {
                    const yeni = new Set(secim);
                    for (const a of adaylar) {
                      if (e.target.checked) yeni.add(a);
                      else yeni.delete(a);
                    }
                    onSecim(yeni);
                  }}
                  className="size-5 accent-primary"
                />
              </th>
            )}
            <th className={TH}>Ad soyad</th>
            <th className={TH}>Sınıf / üye türü</th>
            <th className={TH}>Durum</th>
            <th className={TH}>Açık işler</th>
          </tr>
        </thead>
        <tbody>
          {satirlar.map((s) => {
            const anahtar = kisiAnahtari(s);
            return (
              <tr key={anahtar} className="border-t border-outline-variant/50">
                {secimli && (
                  <td className={TD}>
                    <input
                      type="checkbox"
                      aria-label={`${s.full_name} seç`}
                      checked={secim.has(anahtar)}
                      disabled={!secilebilir(s)}
                      onChange={(e) => {
                        const yeni = new Set(secim);
                        if (e.target.checked) yeni.add(anahtar);
                        else yeni.delete(anahtar);
                        onSecim(yeni);
                      }}
                      className="size-5 accent-primary"
                    />
                  </td>
                )}
                <td className={TD}>
                  <span className="font-medium">{s.full_name}</span>
                  {s.student_number && (
                    <span className="block text-on-surface-variant">
                      Okul no {s.student_number}
                    </span>
                  )}
                </td>
                <td className={TD}>{s.person_label || "—"}</td>
                <td className={TD}>
                  <DurumRozeti satir={s} />
                </td>
                <td className={TD}>
                  <p className="font-medium">{acikIslerOzeti(s)}</p>
                  {!s.is_clear && <AcikIsler satir={s} />}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Sınıf kitaplıklarındaki açık teslimler (kişisiz). Her şubenin güncel teslim
 * listesi basılabilir; geri alma Dolaşım Masası → Teslimler ekranında okutmayla yapılır.
 */
export function SinifKitapliklari({
  yalnizSonSinif = false,
  onHata,
}: {
  yalnizSonSinif?: boolean;
  onHata: (h: SayfaHatasi | null) => void;
}) {
  const [satirlar, setSatirlar] = useState<SinifKitapligi[] | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  useEffect(() => {
    let iptal = false;
    yilApi
      .sinifKitapliklari(yalnizSonSinif)
      .then((s) => {
        if (!iptal) setSatirlar(s);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Sınıf kitaplıkları yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [yalnizSonSinif]);

  const tarih = formatDate(todayIso());
  return (
    <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="text-title-medium text-on-surface">Sınıf Kitaplıkları</p>
      <p className="max-w-3xl text-body-small text-on-surface-variant">
        Şubelere teslim edilen kitaplar kişiye bağlı değildir; burada ayrı listelenir
        {yalnizSonSinif ? " (yalnız son sınıf şubeleri)" : ", son sınıf şubeleri önce"}. Kitaplar
        Dolaşım Masası → Teslimler ekranında okutularak geri alınır.
      </p>
      {hata && <ErrorBand hata={hata} />}
      {satirlar === null && !hata ? (
        <SkeletonList rows={2} />
      ) : satirlar !== null && satirlar.length === 0 ? (
        <EmptyState compact icon="shelves" title="Sınıf kitaplıklarında açık teslim yok." />
      ) : (
        satirlar !== null && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-body-small">
              <caption className="sr-only">Sınıf kitaplıklarındaki açık teslimler</caption>
              <thead>
                <tr className="border-b border-outline-variant">
                  <th className={TH}>Şube</th>
                  <th className={TH}>Ders yılı</th>
                  <th className={TH}>Kitap</th>
                  <th className={TH}>Belge no</th>
                  <th className={TH}>Teslim listesi</th>
                </tr>
              </thead>
              <tbody>
                {satirlar.map((s) => (
                  <tr key={s.section_id} className="border-t border-outline-variant/50">
                    <td className={TD}>
                      <span className="font-medium">{s.section_label}</span>{" "}
                      {s.is_graduating && (
                        <DurumRozeti satir={{ status_text: "Son sınıf", group: "graduating" }} />
                      )}
                    </td>
                    <td className={TD}>
                      {s.school_year_name}
                      {!s.is_active_year && (
                        <span className="block text-on-surface-variant">önceki ders yılı</span>
                      )}
                    </td>
                    <td className={`${TD} tabular-nums`}>
                      {formatNumber(s.delivery_count)}
                      {s.open_case_count > 0 && (
                        <span className="block text-on-surface-variant">
                          {formatNumber(s.open_case_count)} kayıp/hasar dosyası
                        </span>
                      )}
                    </td>
                    <td className={TD}>{s.document_numbers.join(", ")}</td>
                    <td className={TD}>
                      <div className="flex flex-wrap gap-2">
                        <PdfDugmeleri
                          pdfAl={() => yilApi.sinifKitapligiListesiPdf(s.section_id)}
                          dosyaAdi={() =>
                            dosyaAdi(
                              [TESLIM_LISTESI_ADI, s.section_label.replace("/", "-"), tarih],
                              "pdf",
                            )
                          }
                          onizlemeBasligi={`${TESLIM_LISTESI_ADI} — ${s.section_label}`}
                          disabled={s.delivery_count === 0}
                          onHata={onHata}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </Card>
  );
}

/** Yıl akışları özetini okur (kişisiz; kullanıcı eylemi değildir). */
export function useYilAkislari(): {
  akislar: YilAkislari | null;
  hata: SayfaHatasi | null;
  yenile: () => void;
} {
  const [akislar, setAkislar] = useState<YilAkislari | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [surum, setSurum] = useState(0);
  useEffect(() => {
    let iptal = false;
    yilApi
      .akislar()
      .then((a) => {
        if (!iptal) {
          setAkislar(a);
          setHata(null);
        }
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Yıl akışlarının durumu okunamadı."));
      });
    return () => {
      iptal = true;
    };
  }, [surum]);
  return { akislar, hata, yenile: () => setSurum((s) => s + 1) };
}

/** Adım kartının başlığı: numara ya da onay işareti + başlık + kısa durum. */
export function AdimBasligi({
  sira,
  baslik,
  tamam,
  durum,
}: {
  sira: number;
  baslik: string;
  tamam: boolean;
  durum: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-label-large ${
          tamam ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"
        }`}
      >
        {tamam ? <Icon name="check" size="lg" /> : sira}
      </span>
      <div className="min-w-0">
        <h2 className="text-title-medium font-semibold text-on-surface">{baslik}</h2>
        <p className="text-body-small text-on-surface-variant">{durum}</p>
      </div>
    </div>
  );
}
