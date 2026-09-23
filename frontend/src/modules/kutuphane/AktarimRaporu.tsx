// Toplu katalog aktarımının rapor görünümü (tasarım §8.1) — önizleme ile
// uygulama AYNI biçimi kullanır: sunucu tek bir rapor döndürür, ekran yalnız
// zamanı değiştirir ("açılacak" / "açıldı").
//
// Ekranın topladığı iki eksik burada sorulur:
//   * ŞÜPHELİ satır: ISBN ya da ad+yazar birden çok adaya denk geldi. Kullanıcı
//     "yeni eser aç" ya da "şu esere nüsha ekle" der. Karar verilmeden uygulama
//     yazmaz (sunucu 400 döner) — burada sorulmazsa akış tıkanır.
//   * BİLİNMEYEN BÖLÜM: dosyadaki "Bölüm" değeri kontrollü listede yok. Değer
//     SESSİZCE DÜŞÜRÜLMEZ (D5): ya var olan bir bölümle eşlenir ya yeni bölüm
//     açılır.
//
// Kişisel veri: aktarım raporu katalog satırlarından ibarettir; kişi adı
// taşımaz (bağışçı ve komisyon adları edinim kaydındadır, raporda değil).

import type { ReactNode } from "react";

import { formatNumber } from "../../lib/format";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { AKTARIM_KOVASI_TR } from "./api";
import type { AktarimKarari, AktarimRaporu, AktarimSatiri, Section } from "./api";

/** Kova rozetinin tonu: sorunlu kovalar uyarı tonundadır. */
const KOVA_TONU: Record<string, string> = {
  new: "bg-secondary-container text-on-secondary-container",
  existing: "bg-surface-container-highest text-on-surface-variant",
  suspect: "bg-tertiary-container text-on-tertiary-container",
  skipped: "bg-error-container text-on-error-container",
};

/** Şüpheli satırın karar seçicisinde kullanılan değer (`action:row` biçimi). */
export function kararDegeri(karar: AktarimKarari | undefined): string {
  if (karar === undefined) return "";
  if (karar.action === "new") return "new";
  return "work" in karar ? `work:${karar.work}` : `row:${karar.row}`;
}

/** Seçici değerini karara çevirir; boş seçim kararı SİLER. */
export function kararCoz(deger: string): AktarimKarari | null {
  if (deger === "new") return { action: "new" };
  const [tur, ham] = deger.split(":");
  const sayi = Number(ham);
  if (!Number.isFinite(sayi)) return null;
  if (tur === "work") return { action: "attach", work: sayi };
  if (tur === "row") return { action: "attach", row: sayi };
  return null;
}

/** Yeni bölüm açma seçeneğinin değeri (bölüm kimlikleriyle çakışmaz). */
export const YENI_BOLUM = "yeni";

export default function AktarimRaporuGorunumu({
  rapor,
  bolumler,
  kararlar,
  onKarar,
  bolumSecimi,
  onBolum,
}: {
  rapor: AktarimRaporu;
  bolumler: Section[];
  kararlar: Record<number, AktarimKarari>;
  onKarar: (satir: number, deger: string) => void;
  bolumSecimi: Record<string, string>;
  onBolum: (deger: string, secim: string) => void;
}) {
  const onizleme = rapor.dry_run;
  const s = rapor.stats;
  const kutular: { label: string; value: number }[] = [
    { label: "Toplam satır", value: s.total_rows },
    { label: onizleme ? "Açılacak eser" : "Açılan eser", value: s.new_works },
    { label: "Mevcut esere eklenen", value: s.existing_matches },
    { label: onizleme ? "Açılacak nüsha" : "Açılan nüsha", value: s.copies_created },
    { label: "Karar bekleyen", value: s.suspect },
    { label: "Aktarılmayan satır", value: s.skipped_rows + s.error_rows },
  ];

  return (
    <div className="space-y-4 rounded-shape-md bg-surface-container-low p-4">
      <p className="text-title-small text-on-surface">
        {onizleme ? "Önizleme — hiçbir kayıt yazılmadı" : "Aktarım sonucu"}
      </p>

      {onizleme && (
        <p className="text-body-small text-on-surface-variant">
          Aşağıdaki sayılar uygulamanın gerçekten yazacağı sayılardır: önizleme aynı işi koşup geri
          sarar.
        </p>
      )}

      {rapor.already_applied && (
        <Bant tonu="tertiary" simge="content_copy">
          Bu dosya {rapor.applied_at} tarihinde zaten aktarıldı. Aynı dosya ikinci kez uygulanamaz —
          kitaplar kayda iki kez girerdi. Yeni kitaplar için yalnız onları içeren bir dosya
          hazırlayın.
        </Bant>
      )}

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {kutular.map((k) => (
          <div key={k.label} className="rounded-shape-sm bg-surface-container px-3 py-2">
            <dt className="text-label-small text-on-surface-variant">{k.label}</dt>
            <dd className="text-title-medium text-on-surface">{formatNumber(k.value)}</dd>
          </div>
        ))}
      </dl>

      <Notlar rapor={rapor} />

      {rapor.unknown_sections.length > 0 && (
        <BolumEslestirme
          rapor={rapor}
          bolumler={bolumler}
          bolumSecimi={bolumSecimi}
          onBolum={onBolum}
        />
      )}

      {rapor.pending_decisions.length > 0 && (
        <SupheliSatirlar rapor={rapor} kararlar={kararlar} onKarar={onKarar} />
      )}

      <SatirTablosu rapor={rapor} />
    </div>
  );
}

/** Tek biçimli bilgi/uyarı bandı (sayfa hatası DEĞİLDİR — akışı durdurmaz). */
function Bant({
  tonu,
  simge,
  children,
}: {
  tonu: "tertiary" | "secondary";
  simge: string;
  children: ReactNode;
}) {
  const sinif =
    tonu === "tertiary"
      ? "bg-tertiary-container text-on-tertiary-container"
      : "bg-secondary-container text-on-secondary-container";
  return (
    <p className={`flex items-start gap-2 rounded-shape-sm px-4 py-3 text-body-medium ${sinif}`}>
      <Icon name={simge} size="lg" className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** Dosyanın başlık satırı hakkında söylenecekler (aktarımı engellemez). */
function Notlar({ rapor }: { rapor: AktarimRaporu }) {
  const notlar: string[] = [];
  if (rapor.unknown_headers.length > 0) {
    notlar.push(
      `Tanınmayan sütun başlıkları okunmadı: ${rapor.unknown_headers.join(", ")}. ` +
        "Programın bildiği başlıklar katalog şablonundadır.",
    );
  }
  if (rapor.missing_columns.length > 0) {
    notlar.push(`Dosyada bulunmayan sütunlar boş geçildi: ${rapor.missing_columns.join(", ")}.`);
  }
  if (rapor.stats.reference_defaults > 0) {
    notlar.push(
      `${formatNumber(rapor.stats.reference_defaults)} satırda “Danışma Kaynağı” sütunu boştu ve ` +
        "ders kitabı olduğu için danışma kaynağı sayıldı: bu nüshalar ödünç verilmez. " +
        "Sütuna “Hayır” yazarak değiştirebilirsiniz.",
    );
  }
  if (rapor.stats.estimated_codes > 0) {
    notlar.push(
      `${formatNumber(rapor.stats.estimated_codes)} satırın sınıflama kodu “tahmini” olarak ` +
        "işaretlendi; katalogda da bu rozetle görünür.",
    );
  }
  if (rapor.stats.corrections > 0) {
    notlar.push(
      `${formatNumber(rapor.stats.corrections)} alan yapay zekâ aracı tarafından düzeltildi; ` +
        "düzeltmeler aşağıdaki satır listesinde tek tek yazılıdır.",
    );
  }
  if (notlar.length === 0) return null;
  return (
    <ul className="list-disc space-y-1 pl-5 text-body-small text-on-surface-variant">
      {notlar.map((not) => (
        <li key={not}>{not}</li>
      ))}
    </ul>
  );
}

/** Bilinmeyen "Bölüm" değerleri — her biri için karşılık istenir (D5). */
function BolumEslestirme({
  rapor,
  bolumler,
  bolumSecimi,
  onBolum,
}: {
  rapor: AktarimRaporu;
  bolumler: Section[];
  bolumSecimi: Record<string, string>;
  onBolum: (deger: string, secim: string) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-label-large text-on-surface">
        Bölüm listesinde bulunmayan değerler ({formatNumber(rapor.unknown_sections.length)})
      </p>
      <p className="text-body-small text-on-surface-variant">
        Dosyadaki bu değerler kontrollü bölüm listesinde yok. Her biri için var olan bir bölüm seçin
        ya da yeni bölüm açın; karşılığı verilmeden aktarım yazmaz — değer kaybolmasın.
      </p>
      <div className="space-y-2">
        {rapor.unknown_sections.map((bilinmeyen) => (
          <div
            key={bilinmeyen.value}
            className="flex flex-wrap items-end justify-between gap-3 rounded-shape-sm bg-surface-container px-3 py-2"
          >
            <div className="min-w-0">
              <p className="text-body-medium text-on-surface">“{bilinmeyen.value}”</p>
              <p className="text-body-small text-on-surface-variant">
                {formatNumber(bilinmeyen.count)} satır (ör. satır {bilinmeyen.rows.join(", ")})
              </p>
            </div>
            <Select
              label="Karşılığı"
              placeholder="Seçin"
              className="min-w-[14rem]"
              value={bolumSecimi[bilinmeyen.value] ?? ""}
              onChange={(e) => onBolum(bilinmeyen.value, e.target.value)}
              options={[
                ...bolumler.map((b) => ({ value: String(b.id), label: b.name })),
                { value: YENI_BOLUM, label: `Yeni bölüm aç: “${bilinmeyen.value}”` },
              ]}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Şüpheli satırlar — tek tek karar istenir (§8.1). */
function SupheliSatirlar({
  rapor,
  kararlar,
  onKarar,
}: {
  rapor: AktarimRaporu;
  kararlar: Record<number, AktarimKarari>;
  onKarar: (satir: number, deger: string) => void;
}) {
  const satirlar = rapor.rows.filter((satir) => satir.needs_decision);
  // Rapor satırları tavanlıdır (sunucuda `MAX_REPORT_ROWS`): 500'den fazla satır
  // karar bekliyorsa listede yalnız bir bölümü görünür. Kullanıcı "hepsini
  // karara bağladım ama sayı düşmedi" sanmasın diye fark AÇIKÇA söylenir.
  const eksikSatir = rapor.pending_decisions.length - satirlar.length;
  return (
    <div className="space-y-3">
      <p className="text-label-large text-on-surface">
        Karar bekleyen satırlar ({formatNumber(rapor.pending_decisions.length)})
      </p>
      <p className="text-body-small text-on-surface-variant">
        Bu satırların künyesi katalogdaki bir esere benziyor ama tam eşleşmiyor. Yeni eser açmayı ya
        da nüshaların ekleneceği eseri seçin. Karar vermeden aktarım yazmaz.
      </p>
      {eksikSatir > 0 && (
        <p className="text-body-small text-on-surface-variant">
          Dosya uzun olduğu için burada ilk {formatNumber(satirlar.length)} satır gösteriliyor.
          Bunları karara bağlayıp “Yeniden önizle” deyin; kalan {formatNumber(eksikSatir)} satır
          sırayla gelecek.
        </p>
      )}
      <div className="space-y-2">
        {satirlar.map((satir) => (
          <div
            key={satir.row}
            className="flex flex-wrap items-end justify-between gap-3 rounded-shape-sm bg-surface-container px-3 py-2"
          >
            <div className="min-w-0">
              <p className="text-body-medium text-on-surface">
                Satır {satir.row}: {satir.title}
              </p>
              {satir.candidates.length > 0 && (
                <p className="text-body-small text-on-surface-variant">
                  Benzeyen kayıtlar: {satir.candidates.map((a) => a.title).join(" · ")}
                  {satir.candidates_truncated &&
                    ` ve ${formatNumber(satir.candidate_count - satir.candidates.length)} kayıt daha`}
                </p>
              )}
            </div>
            <Select
              label="Kararınız"
              placeholder="Seçin"
              className="min-w-[18rem]"
              value={kararDegeri(kararlar[satir.row])}
              onChange={(e) => onKarar(satir.row, e.target.value)}
              options={[
                { value: "new", label: "Yeni eser aç" },
                ...satir.candidates.map((aday) => ({
                  value: aday.work !== null ? `work:${aday.work}` : `row:${aday.row}`,
                  label:
                    aday.work !== null
                      ? `“${aday.title}” eserine nüsha ekle`
                      : `Bu dosyanın ${aday.row}. satırındaki “${aday.title}” eserine bağla`,
                })),
              ]}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Satır listesi — KAPALI gelir (10.000 satırlık bir dosyada rapor ekranı satır
 * tablosundan ibaret olurdu). Başlıkta kaç satırın sorunlu olduğu yazar;
 * kullanıcı açtığında bütün satırları sırayla görür.
 */
function SatirTablosu({ rapor }: { rapor: AktarimRaporu }) {
  const sorunlu = rapor.rows.filter(
    (satir) => satir.issues.length > 0 || satir.bucket === "skipped" || satir.needs_decision,
  );
  return (
    <details className="rounded-shape-sm bg-surface-container px-3 py-2">
      <summary className="min-h-11 cursor-pointer list-none py-2 text-label-large text-primary">
        Satır listesi ({formatNumber(rapor.rows.length)} satır, {formatNumber(sorunlu.length)}{" "}
        sorunlu)
      </summary>
      {rapor.rows_truncated && (
        <p className="mb-2 text-body-small text-on-surface-variant">
          Dosya uzun olduğu için listede yalnız bir bölümü gösteriliyor; sorunlu satırların hepsi
          listededir.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-body-small">
          <thead>
            <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
              <th className="p-2">Satır</th>
              <th className="p-2">Kaynak adı</th>
              <th className="p-2">Durum</th>
              <th className="p-2">Nüsha</th>
              <th className="p-2">Bölüm</th>
              <th className="p-2">Notlar</th>
            </tr>
          </thead>
          <tbody>
            {rapor.rows.map((satir) => (
              <SatirHucresi key={satir.row} satir={satir} onizleme={rapor.dry_run} />
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function SatirHucresi({ satir, onizleme }: { satir: AktarimSatiri; onizleme: boolean }) {
  return (
    <tr className="border-t border-outline-variant/50 align-top">
      <td className="p-2 text-on-surface-variant">{satir.row}</td>
      <td className="p-2 text-on-surface">{satir.title || "—"}</td>
      <td className="p-2">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-label-small ${KOVA_TONU[satir.bucket]}`}
        >
          {AKTARIM_KOVASI_TR[satir.bucket]}
        </span>
      </td>
      <td className="p-2 text-on-surface-variant">
        {formatNumber(onizleme ? satir.copies : satir.copies_created)}
      </td>
      <td className="p-2 text-on-surface-variant">
        {satir.section || satir.shelf_location || "—"}
      </td>
      <td className="p-2 text-on-surface-variant">
        <div className="space-y-0.5">
          {satir.reference_by_textbook && <p>Ders kitabı → danışma kaynağı (ödünç verilmez).</p>}
          {satir.classification_source === "ESTIMATED" && <p>Sınıflama kodu tahmini.</p>}
          {satir.corrections.map((duzeltme) => (
            <p key={`${duzeltme.field}-${duzeltme.corrected}`}>
              Düzeltildi: “{duzeltme.original}” → “{duzeltme.corrected}”
            </p>
          ))}
          {satir.issues.map((sorun) => (
            <p key={sorun} className="text-on-surface">
              {sorun}
            </p>
          ))}
          {satir.issues.length === 0 &&
            satir.corrections.length === 0 &&
            !satir.reference_by_textbook &&
            satir.classification_source !== "ESTIMATED" &&
            "—"}
        </div>
      </td>
    </tr>
  );
}
