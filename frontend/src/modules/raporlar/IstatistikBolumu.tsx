// Raporlar → İstatistik (F10): kütüphanenin KİŞİSİZ sayıları.
//
// Bölümler: koleksiyon (rapor anı), edinim, dolaşım, teslim, kayıp ve hasar, ayıklama ve devir
// (seçilen dönemin işlemleri). Sayılar sunucudan gelir (`GET library/statistics/`); ekran
// hesap yapmaz, yalnız yazar.
//
// Profil yasağı (CLAUDE.md §2-5, tasarım §3): üye bazında hiçbir bilgi yoktur. Dolaşımın üye
// türü ve sınıf düzeyi kırılımında k farklı üyenin altındaki grup sunucudan `loans: null`
// gelir ve "—" yazılır; toplamdan geri bulunamasın diye sunucu gerektiğinde bir grup daha
// gizler (yıl sonu raporunun hesabı — tek kaynak). Dolaşımda konu ya da bölüm kırılımı hiç
// yoktur. Eşiğin açıklaması tablonun hemen altındadır. Aktif üye sayısı eşiksizdir: üyelik
// sayısı ödünç verisi değildir (27.09.2026 kullanıcı kararı, tasarım F10 ekleri K1).

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { GEREKCE_TR, TMY_YOLU_TR, YIL_SONU_RAPORU_ADRESI } from "../ayiklama/api";
import type { EsikliSayi } from "../ayiklama/api";
import { COZUM_TR } from "../kayip/api";
import { ACQUISITION_METHOD_TR, COPY_STATUS_TR, RESOURCE_TYPE_TR } from "../kutuphane/api";
import { MEMBER_TYPE_TR } from "../uyelik/api";
import { raporlarApi } from "./api";
import type { DonemSecimi, Istatistik, UyeTuru } from "./api";
import DonemSecici, { eksikAralik } from "./DonemSecici";

/** Eşiğin altındaki grubun yerine yazılan işaret (yıl sonu raporuyla aynı). */
export const ESIK_ALTI = "—";

/** Dolaşım kırılımlarının açıklaması — yıl sonu raporunun notuyla aynı kural. */
export function esikAciklamasi(k: number): string {
  return (
    `${formatNumber(k)} farklı üyeden azının ödünç aldığı grubun sayısı gösterilmez ` +
    `(${ESIK_ALTI}); gizlenen sayı toplamdan çıkarılarak bulunamasın diye gerektiğinde bir ` +
    "grup daha gizlenir. Aktif üye sayısı ödünç verisi değildir; eşiksiz yazılır. Sınıf " +
    "düzeyi kaydı olmayan öğrencilerin ödüncü düzey kırılımına girmez. " +
    "Eşik, Ayarlar → Kütüphane Politikası'ndaki “Çok okunanlar için en az üye sayısı”dır."
  );
}

/** Sayfanın kişisizlik notu (kılavuz aynı cümleyi kullanır). */
export const KISISIZLIK_NOTU =
  "İstatistik kişisizdir: üye bazında bilgi, adlı sıralama ve konuya göre ödünç dağılımı " +
  "yoktur. Ödünç kaydı okunan kitabı göstermez.";

const UYE_TURLERI: UyeTuru[] = ["STUDENT", "TEACHER", "STAFF"];

const AYLAR = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];

/** '2026-09' → 'Eylül 2026'. */
export function ayEtiketi(ay: string): string {
  const [yil, sira] = ay.split("-");
  const n = Number(sira);
  return n >= 1 && n <= 12 ? `${AYLAR[n - 1]} ${yil}` : ay;
}

/** Eşikli hücre: gizliyse "—" (ekran okuyucu için açıklamalı), değilse sayı. */
export function EsikliHucre({ hucre }: { hucre: EsikliSayi | null | undefined }) {
  const sayi = hucre == null ? null : hucre.loans;
  if (sayi === null) {
    return (
      <span title="Eşiğin altında — gösterilmez">
        {ESIK_ALTI}
        <span className="sr-only"> (eşiğin altında, gösterilmez)</span>
      </span>
    );
  }
  return <>{formatNumber(sayi)}</>;
}

function Bolum({
  baslik,
  aciklama,
  children,
}: {
  baslik: string;
  aciklama?: string;
  children: ReactNode;
}) {
  const id = `istatistik-${baslik.replace(/\s+/g, "-").toLocaleLowerCase("tr")}`;
  return (
    <section aria-labelledby={id}>
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div>
          <h2 id={id} className="text-title-medium font-semibold text-on-surface">
            {baslik}
          </h2>
          {aciklama && (
            <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">{aciklama}</p>
          )}
        </div>
        {children}
      </Card>
    </section>
  );
}

function Sayilar({ kalemler }: { kalemler: Array<[etiket: string, deger: ReactNode]> }) {
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {kalemler.map(([etiket, deger]) => (
        <div key={etiket} className="min-w-0 rounded-shape-md bg-surface-container px-3 py-2">
          <dt className="text-label-medium text-on-surface-variant">{etiket}</dt>
          <dd className="text-title-medium font-semibold text-on-surface">{deger}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Başlıklı küçük kırılım tablosu (ilk sütun ad, öbürleri sayı). */
function Kirilim({
  baslik,
  sutunlar,
  satirlar,
}: {
  baslik: string;
  sutunlar: string[];
  satirlar: Array<{ ad: string; degerler: ReactNode[] }>;
}) {
  return (
    <div className="min-w-0 overflow-x-auto">
      <table className="w-full border-collapse text-body-small">
        <caption className="pb-1 text-left text-label-large font-semibold text-on-surface">
          {baslik}
        </caption>
        <thead>
          <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
            {sutunlar.map((s, i) => (
              <th key={s} scope="col" className={`px-2 py-1.5 ${i > 0 ? "text-right" : ""}`}>
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {satirlar.length === 0 ? (
            <tr className="border-t border-outline-variant/50">
              <td colSpan={sutunlar.length} className="px-2 py-1.5 text-on-surface-variant">
                Bu dönemde kayıt yok.
              </td>
            </tr>
          ) : (
            satirlar.map((s) => (
              <tr key={s.ad} className="border-t border-outline-variant/50">
                <th scope="row" className="px-2 py-1.5 text-left font-normal text-on-surface">
                  {s.ad}
                </th>
                {s.degerler.map((d, i) => (
                  <td key={i} className="px-2 py-1.5 text-right tabular-nums text-on-surface">
                    {d}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

/** Etiket sözlüğünün sırasıyla satırlar (sunucuda olmayan anahtar 0 sayılır). */
function etiketli(
  sayilar: Record<string, number>,
  etiketler: Record<string, string>,
  sifirlariAt = false,
): Array<{ ad: string; degerler: ReactNode[] }> {
  return Object.entries(etiketler)
    .map(([kod, ad]) => ({ ad, sayi: sayilar[kod] ?? 0 }))
    .filter((s) => !sifirlariAt || s.sayi > 0)
    .map((s) => ({ ad: s.ad, degerler: [formatNumber(s.sayi)] }));
}

function Koleksiyon({ ist }: { ist: Istatistik }) {
  const c = ist.collection;
  return (
    <Bolum
      baslik="Koleksiyon"
      aciklama="Bugünkü kayıtlarla: seçilen dönemden bağımsızdır. Elde bulunan nüsha kayıttan düşülmemiş ve devredilmemiş nüshadır."
    >
      <Sayilar
        kalemler={[
          ["Katalogdaki eser", formatNumber(c.catalog_work_count)],
          ["Nüshası elde bulunan eser", formatNumber(c.work_count)],
          ["Elde bulunan nüsha", formatNumber(c.in_stock_count)],
          ["Rafta", formatNumber(c.available_count)],
          ["Elde bulunan kitap", formatNumber(ist.book_threshold.in_stock_books)],
          ["Kayıt defterindeki nüsha", formatNumber(c.register_count)],
          ["Danışma kaynağı", formatNumber(c.reference_count)],
          ["El yazması ve nadir eser", formatNumber(c.rare_count)],
        ]}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Kirilim
          baslik="Kaynak türüne göre"
          sutunlar={["Kaynak türü", "Eser", "Elde bulunan nüsha"]}
          satirlar={Object.entries(RESOURCE_TYPE_TR).map(([kod, ad]) => ({
            ad,
            degerler: [
              formatNumber(c.works_by_resource_type[kod] ?? 0),
              formatNumber(c.resource_type_counts[kod] ?? 0),
            ],
          }))}
        />
        <Kirilim
          baslik="Nüsha durumuna göre"
          sutunlar={["Durum", "Nüsha"]}
          satirlar={etiketli(c.status_counts, COPY_STATUS_TR)}
        />
        <Kirilim
          baslik="Bölüme göre"
          sutunlar={["Bölüm", "Elde bulunan nüsha"]}
          satirlar={c.sections.map((s) => ({
            ad: s.section || "Bölümü yazılmamış",
            degerler: [formatNumber(s.copies)],
          }))}
        />
      </div>
      <p className="text-body-small text-on-surface-variant">
        {`Kayıt defterindeki nüsha, kayıttan düşülmüş ve devredilmiş nüshaları da sayar. Elde bulunan kitap, kaynak türü “Kitap” olan nüshalardır (Yönetmelik Md. 7/1 eşiği ${formatNumber(ist.book_threshold.threshold)}).`}
      </p>
    </Bolum>
  );
}

function Edinim({ ist }: { ist: Istatistik }) {
  const a = ist.acquisitions;
  return (
    <Bolum
      baslik="Edinim"
      aciklama="Kazandırılan, Yönetmelik Md. 10/5'teki yollarla gelen nüshadır; programa aktarım ve sayım fazlası kayıt içi giriştir ve ayrı sayılır."
    >
      <Sayilar
        kalemler={[
          ["Kazandırılan nüsha", formatNumber(a.total_copies)],
          ["Kazandırılan eser", formatNumber(a.works)],
          ["Kayıt içi giriş", formatNumber(a.register_entry_copies)],
          ["Karara bağlanan bağış ön kaydı", formatNumber(a.donation_intakes_decided)],
          ["Kabul edilen bağış kalemi", formatNumber(a.donation_items_accepted)],
          ["Reddedilen bağış kalemi", formatNumber(a.donation_items_rejected)],
        ]}
      />
      <Kirilim
        baslik="Edinim yoluna göre"
        sutunlar={["Edinim yolu", "Nüsha"]}
        satirlar={etiketli(a.copies_by_method, ACQUISITION_METHOD_TR)}
      />
    </Bolum>
  );
}

function Dolasim({ ist }: { ist: Istatistik }) {
  const d = ist.circulation;
  return (
    <Bolum
      baslik="Dolaşım"
      aciklama="Seçilen dönemde verilen ödünçler ve iadeler; “şu an” sayıları bugünündür."
    >
      <Sayilar
        kalemler={[
          ["Verilen ödünç", formatNumber(d.loans)],
          ["İade", formatNumber(d.returns)],
          ["Gecikmeyle iade edilen", formatNumber(d.returned_late)],
          ["Kayba dönüşen ödünç", formatNumber(d.lost_converted)],
          ["Ödünç alan farklı üye", formatNumber(d.distinct_borrowers)],
          ["Şu an ödünçte", formatNumber(d.open_now)],
          ["Şu an gecikmiş", formatNumber(d.overdue_now)],
        ]}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Kirilim
          baslik="Üye türüne göre"
          sutunlar={["Üye türü", "Ödünç", "Aktif üye (bugün)"]}
          satirlar={UYE_TURLERI.map((t) => ({
            ad: MEMBER_TYPE_TR[t],
            degerler: [
              <EsikliHucre key="o" hucre={d.by_member_type[t]} />,
              formatNumber(d.active_members[t]),
            ],
          }))}
        />
        <Kirilim
          baslik="Sınıf düzeyine göre"
          sutunlar={["Sınıf düzeyi", "Ödünç"]}
          satirlar={d.by_class_level.map((s) => ({
            ad: gradeLevelLabel(s.class_level),
            degerler: [<EsikliHucre key="o" hucre={s} />],
          }))}
        />
        <Kirilim
          baslik="Aylara göre"
          sutunlar={["Ay", "Ödünç"]}
          satirlar={d.by_month.map((s) => ({
            ad: ayEtiketi(s.month),
            degerler: [formatNumber(s.loans)],
          }))}
        />
      </div>
      <p
        className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface"
        aria-label="Eşik açıklaması"
      >
        <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
        {esikAciklamasi(d.k_threshold)}
      </p>
    </Bolum>
  );
}

function Teslim({ ist }: { ist: Istatistik }) {
  const t = ist.deliveries;
  return (
    <Bolum
      baslik="Teslim"
      aciklama="Sınıf kitaplığına ve öğretmene teslim ödünç değildir; ayrı sayılır."
    >
      <Sayilar
        kalemler={[
          ["Sınıf kitaplığına teslim", formatNumber(t.delivered.section)],
          ["Öğretmene teslim", formatNumber(t.delivered.teacher)],
          ["Teslimden geri alınan", formatNumber(t.returned)],
          ["Kayba dönüşen teslim", formatNumber(t.lost)],
          ["Şu an sınıf kitaplığında", formatNumber(t.open_now.section)],
          ["Şu an öğretmende", formatNumber(t.open_now.teacher)],
        ]}
      />
    </Bolum>
  );
}

function KayipHasar({ ist }: { ist: Istatistik }) {
  const f = ist.loss_damage;
  return (
    <Bolum baslik="Kayıp ve Hasar" aciklama="Kayıp ve hasar dosyaları ile onarım.">
      <Sayilar
        kalemler={[
          ["Açılan kayıp dosyası", formatNumber(f.loss_cases)],
          ["Açılan hasar dosyası", formatNumber(f.damage_cases)],
          ["Kayıttan düşme önerisi", formatNumber(f.write_off_proposals)],
          ["Onarıma gönderilen", formatNumber(f.repairs_sent)],
          ["Onarımdan dönen", formatNumber(f.repairs_returned)],
          ["Şu an onarımda", formatNumber(f.in_repair_now)],
          ["Şu an açık dosya", formatNumber(f.open_cases_now)],
          ["Şu an kayıp nüsha", formatNumber(f.lost_copies_now)],
        ]}
      />
      <Kirilim
        baslik="Kapanan dosyalar, çözüme göre"
        sutunlar={["Çözüm", "Dosya"]}
        satirlar={etiketli(f.resolutions, COZUM_TR, true)}
      />
    </Bolum>
  );
}

function Ayiklama({ ist }: { ist: Istatistik }) {
  const w = ist.weeding;
  return (
    <Bolum baslik="Ayıklama ve Devir" aciklama="Seçilen dönemde uygulanan ayıklama teklifleri.">
      <Sayilar
        kalemler={[
          ["Uygulanan teklif", formatNumber(w.batches_applied)],
          ["Kayıttan düşülen", formatNumber(w.withdrawn)],
          ["Devredilen", formatNumber(w.transferred)],
        ]}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Kirilim
          baslik="Gerekçeye göre (Md. 12/1)"
          sutunlar={["Gerekçe", "Nüsha"]}
          satirlar={etiketli(w.by_reason, GEREKCE_TR)}
        />
        <Kirilim
          baslik="Taşınır Mal Yönetmeliği yoluna göre"
          sutunlar={["Yol", "Nüsha"]}
          satirlar={etiketli(w.by_path, TMY_YOLU_TR)}
        />
      </div>
    </Bolum>
  );
}

export default function IstatistikBolumu() {
  const [donem, setDonem] = useState<DonemSecimi>({ tur: "etkin" });
  const [ist, setIst] = useState<Istatistik | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  useEffect(() => {
    // Tarih aralığı seçildi ama tarihler henüz "Göster"le verilmedi: son sayılar kalır.
    if (eksikAralik(donem)) return;
    let iptal = false;
    setYukleniyor(true);
    raporlarApi
      .istatistik(donem)
      .then((i) => {
        if (iptal) return;
        setIst(i);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "İstatistik yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [donem]);

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <DonemSecici deger={donem} onDegisti={setDonem} />
        {ist && (
          <p className="text-body-medium text-on-surface" aria-live="polite">
            {`Dönem ${formatDate(ist.period.start)} – ${formatDate(ist.period.end)} · ${formatDate(ist.generated_on)} tarihli kayıtlarla.`}
          </p>
        )}
        <p className="text-body-small text-on-surface-variant">
          {KISISIZLIK_NOTU} Okul müdürlüğüne gidecek ders yılı raporu için{" "}
          <Link
            to={YIL_SONU_RAPORU_ADRESI}
            className="font-medium text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Yıl Sonu Raporu
          </Link>
          &apos;nu kullanın.
        </p>
      </Card>

      {hata && <ErrorBand hata={hata} />}
      {ist === null ? (
        !hata && <SkeletonList rows={6} />
      ) : (
        <div className={`space-y-[var(--kd-page-gap)] ${yukleniyor ? "opacity-60" : ""}`}>
          <Koleksiyon ist={ist} />
          <Edinim ist={ist} />
          <Dolasim ist={ist} />
          <Teslim ist={ist} />
          <KayipHasar ist={ist} />
          <Ayiklama ist={ist} />
        </div>
      )}
    </div>
  );
}
