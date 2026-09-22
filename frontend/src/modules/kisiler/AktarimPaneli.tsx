// e-Okul listesinden (ya da şablondan) aktarım paneli — önizle → aktar, MUTABAKATLA
// (tasarım §8.3). Dosya VEYA pano metni aynı boru hattından geçer.
//
// AKTARIM KİMSEYİ AYIRMAZ VE SİLMEZ (F1 eki 7, kullanıcı kararı 22.09.2026): listede
// bulunmayan aktif kişi Ayrılış Havuzu'na eklenir, durumu aktif kalır; dosyada
// bulunan havuzdaki kişi havuzdan kendiliğinden çıkar. Karar Kişiler → Ayrılış
// Havuzu'nda verilir. Önizleme "N öğrenci ayrılış havuzuna eklenecek, M öğrenci
// havuzdan çıkacak" der; ayrılış olmadığı için aktarım ayrıca onay istemez.
//
// Öğrenci: panel bütün şubeleri içeren TEK dosyayı belirgin biçimde önerir.
// Karşılaştırma varsayılan olarak YALNIZ dosyada bulunan şubelerle yapılır; "Bu dosya
// okulun tam listesidir" onayı verilirse dosyada olmayan şubelerdeki öğrenciler de
// havuza eklenir. Önizleme şube bazında etki tablosu ve havuza eklenecekleri gösterir.
//
// Personel: listede olmayanlar havuza eklenir (eski "ayrıldı sayılsın mı?" seçimi
// kalktı); "olası aynı kişi" çiftleri gösterilir, aktarımdan sonra onaylı "Birleştir"
// ile eski kayıt yeni kayda katılır (Ayrılış Havuzu'ndan da yapılabilir). Görev
// sütunu yalnız üye türü için okunur; tanınmayan satırlar "Üye türünü denetleyin"
// uyarısı alır.

import { useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { saveBlob } from "../../lib/download";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import {
  importCounts,
  okulApi,
  PERSONNEL_TEMPLATE_FILENAME,
  STUDENT_TEMPLATE_FILENAME,
} from "../okul/api";
import type {
  ImportInput,
  ImportIssue,
  ImportReport,
  PersonnelImportReport,
  SimilarPair,
  StudentImportReport,
} from "../okul/api";
import { ErrorBand, HAVUZ_ADRESI, hataOku } from "./ortak";
import type { SayfaHatasi } from "./ortak";

export type ImportKind = "students" | "personnel";

const IMPORT_LABEL: Record<ImportKind, { title: string; hint: string; template: string }> = {
  students: {
    title: "e-Okul Raporundan veya Şablondan Öğrenci Aktar",
    hint: "e-Okul Öğrenci İşlemleri → Raporlar → OOG01001R020 — Sınıf/Şube Öğrenci Listesi raporunu Excel olarak indirip DEĞİŞTİRMEDEN yükleyin: şube blokları, sınıf başlıkları ve sayaç dipnotları otomatik çözülür. Alternatif olarak uygulama şablonu (sınıf, okul numarası, ad, soyad) doldurulabilir ya da tablo doğrudan panoya yapıştırılabilir. Cinsiyet ve pansiyon sütunları okunmaz.",
    template: STUDENT_TEMPLATE_FILENAME,
  },
  personnel: {
    title: "e-Okul Raporundan veya Şablondan Öğretmen ve Diğer Personeli Aktar",
    hint: "e-Okul Kurum İşlemleri → Raporlar → OOK01001R1 — Personel Listesi raporunu Excel olarak indirip DEĞİŞTİRMEDEN yükleyin. Ad-soyad okunur; görev sütunu yalnız üye türünü (öğretmen ya da diğer personel) belirlemek için kullanılır ve saklanmaz, branş okunmaz; sayaç dipnotu atlanır. Alternatif olarak uygulama şablonu doldurulabilir ya da tablo panoya yapıştırılabilir.",
    template: PERSONNEL_TEMPLATE_FILENAME,
  },
};

/** Panelin belirgin önerisi: bütün şubeleri içeren tek dosya (Karar 1-8). */
const TEK_DOSYA_ONERISI =
  "Önerilen yol: okulun bütün şubelerini içeren listeyi tek dosyada yükleyin ve “Bu dosya okulun tam listesidir” kutusunu işaretleyin. Böylece şube değiştiren öğrencinin kaydı güncellenir ve kimse gereksiz yere ayrılış havuzuna düşmez.";

/**
 * Şube şube yüklemenin bilinen sınırı: öğrenci yalnız BU dosyada aranır. Kayıtlı
 * olduğu şube dosyada olup kendisi başka şubeye geçtiği için dosyada olmayan
 * öğrenci de havuza eklenir; yeni şubesinin listesi gelince kendiliğinden çıkar.
 */
const SUBE_DEGISIMI_UYARISI =
  "Başka bir şubeye geçtiği için bu dosyada bulunmayan öğrenci de ayrılış havuzuna eklenir; yeni şubesinin listesi aktarılınca havuzdan kendiliğinden çıkar. Yıl başında ya da şube değişikliklerinden sonra okulun bütün şubelerini içeren listeyi tek dosyada yükleyin.";

/** Havuzun ne olduğu — önizleme ve sonuçta aynı cümle. */
const HAVUZ_ACIKLAMASI =
  "Aktarım kimseyi ayırmaz ve kimsenin kaydını silmez: listede bulunmayanların durumu aktif kalır, karar Ayrılış Havuzu'nda verilir.";

/** Rapor satır sorunlarındaki alan kodlarının kullanıcı adları. */
const ALAN_ADI: Record<string, string> = {
  header: "Başlık",
  leave_pool: "Ayrılış havuzu",
  number: "Okul no",
  class: "Sınıf/şube",
  student_name: "Ad-soyad",
  full_name: "Ad-soyad",
  member_kind: "Üye türü",
};

function isStudentReport(report: ImportReport): report is StudentImportReport {
  return "created_students" in report;
}

export default function AktarimPaneli({
  kind,
  onImported,
}: {
  kind: ImportKind;
  onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [fullList, setFullList] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SayfaHatasi | null>(null);
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const fileId = useId();
  const textId = useId();
  const fullListId = useId();
  // Seçimi geri almak için gerçek DOM alanına erişim şart: `value` sıfırlanmadan
  // aynı dosya yeniden seçilemez ve tarayıcı "dosya seçilmedi" durumuna dönmez.
  const fileRef = useRef<HTMLInputElement>(null);

  const labels = IMPORT_LABEL[kind];
  // Dosya öncelikli: ikisi birden doluysa backend 400 döner, o yüzden tek girdi seçilir.
  const input: ImportInput | null = file ? { file } : text.trim() ? { text } : null;
  // Aktarma yalnız önizlemeden sonra açılır (dry_run raporu görülmeden yazma yok).
  const canCommit = report !== null && report.dry_run;

  /** Girdi ya da kapsam değişince eski önizleme geçersizdir. */
  const sifirla = () => {
    setReport(null);
    setError(null);
  };

  const run = async (mode: "preview" | "commit") => {
    if (!input) {
      setError({ message: "Önce bir dosya seçin ya da listeyi yapıştırın.", parolaGerekli: false });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let result: ImportReport;
      if (kind === "students") {
        const options = { fullList };
        result =
          mode === "preview"
            ? await okulApi.previewStudentImport(input, options)
            : await okulApi.commitStudentImport(input, options);
      } else {
        result =
          mode === "preview"
            ? await okulApi.previewPersonnelImport(input)
            : await okulApi.commitPersonnelImport(input);
      }
      setReport(result);
      if (mode === "commit") {
        snackbar.success("İçe aktarma tamamlandı.");
        onImported();
      }
    } catch (e) {
      setError(hataOku(e, mode === "preview" ? "Önizleme yapılamadı." : "İçe aktarma yapılamadı."));
    } finally {
      setBusy(false);
    }
  };

  const downloadTemplate = async () => {
    setError(null);
    try {
      const blob =
        kind === "students" ? await okulApi.studentTemplate() : await okulApi.personnelTemplate();
      saveBlob(blob, labels.template);
    } catch (e) {
      setError(hataOku(e, "Şablon indirilemedi."));
    }
  };

  const birlestir = async (pair: SimilarPair) => {
    if (pair.new_id === null || report === null || isStudentReport(report)) return;
    const ok = await confirm({
      title: "Kayıtlar birleştirilsin mi?",
      message: `“${pair.existing_name}” kaydının kütüphane bağları “${pair.row_name}” kaydına taşınır ve eski kayıt silinir. Bu işlem geri alınamaz.`,
      confirmLabel: "Birleştir",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.mergePersonnel(pair.existing_id, pair.new_id);
      setReport({
        ...report,
        similar_pairs: report.similar_pairs.filter((p) => p !== pair),
        pool_added: report.pool_added.filter((m) => m.id !== pair.existing_id),
      });
      snackbar.success("Kayıtlar birleştirildi.");
      onImported();
    } catch (e) {
      setError(hataOku(e, "Kayıtlar birleştirilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">{labels.title}</p>
          <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">{labels.hint}</p>
        </div>
        <Button variant="outlined" icon="download" onClick={downloadTemplate}>
          Şablon indir
        </Button>
      </div>

      {kind === "students" && (
        <p className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-medium text-on-secondary-container">
          <Icon name="recommend" size="lg" className="mt-0.5 shrink-0" />
          <span>{TEK_DOSYA_ONERISI}</span>
        </p>
      )}

      <div>
        <label htmlFor={fileId} className="mb-1 block text-label-large text-on-surface-variant">
          Dosya (e-Okul .xls veya şablon .xlsx)
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <input
            id={fileId}
            ref={fileRef}
            type="file"
            /* e-Okul ihraçları BÜYÜK harfli .XLS uzantısıyla iner; tarayıcı
               accept eşleşmesi büyük/küçük harfe duyarsızdır ama MIME tipini
               tanımayan Windows kurulumları için uzantı listesi de verilir. */
            accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              sifirla();
            }}
            className="block min-h-[var(--kd-field-height)] flex-1 rounded-shape-sm border border-outline bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1.5 file:text-label-large file:text-on-secondary-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          {file && (
            <Button
              variant="text"
              icon="close"
              onClick={() => {
                if (fileRef.current) fileRef.current.value = "";
                setFile(null);
                sifirla();
              }}
            >
              Dosyayı kaldır
            </Button>
          )}
        </div>
      </div>

      <div>
        <label htmlFor={textId} className="mb-1 block text-label-large text-on-surface-variant">
          Ya da tabloyu yapıştırın
        </label>
        <textarea
          id={textId}
          rows={3}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            sifirla();
          }}
          disabled={file !== null}
          placeholder="Excel satırlarını kopyalayıp buraya yapıştırın…"
          className="block w-full rounded-shape-xs border border-outline bg-surface px-4 py-3 text-body-medium text-on-surface outline-none placeholder:text-on-surface-variant/60 focus-visible:ring-2 focus-visible:ring-primary focus:border-primary disabled:opacity-50"
        />
      </div>

      {kind === "students" && (
        <div className="rounded-shape-sm bg-surface-container-low px-4 py-3">
          <label htmlFor={fullListId} className="flex items-start gap-3 text-body-medium">
            <input
              id={fullListId}
              type="checkbox"
              checked={fullList}
              onChange={(e) => {
                setFullList(e.target.checked);
                sifirla();
              }}
              className="mt-0.5 size-5 shrink-0 accent-primary"
            />
            <span>
              <span className="block text-label-large text-on-surface">
                Bu dosya okulun tam listesidir
              </span>
              <span className="block text-body-small text-on-surface-variant">
                İşaretlemezseniz yalnız dosyada bulunan şubeler karşılaştırılır; diğer şubelere
                dokunulmaz. İşaretlerseniz dosyada bulunmayan şubelerdeki öğrenciler de ayrılış
                havuzuna eklenir. Kimse kendiliğinden ayrılmaz; karar Ayrılış Havuzu&apos;nda
                verilir.
              </span>
            </span>
          </label>
        </div>
      )}

      {error && <ErrorBand hata={error} />}

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="tonal" icon="visibility" onClick={() => run("preview")} disabled={busy}>
          {busy ? "Çalışıyor…" : "Önizle"}
        </Button>
        <Button icon="upload" onClick={() => run("commit")} disabled={busy || !canCommit}>
          Aktar
        </Button>
      </div>

      {report && <ImportReportView report={report} onMerge={birlestir} busy={busy} />}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Rapor görünümü
// ---------------------------------------------------------------------------

function ImportReportView({
  report,
  onMerge,
  busy,
}: {
  report: ImportReport;
  onMerge: (pair: SimilarPair) => void;
  busy: boolean;
}) {
  const counts = importCounts(report);
  const ogrenci = isStudentReport(report);
  const cells: { label: string; value: number }[] = [
    { label: "Toplam satır", value: report.total_rows },
    { label: "İşlenen", value: report.processed },
    { label: "Yeni", value: counts.created },
    { label: "Güncellenen", value: counts.updated },
    { label: "Değişmeyen", value: counts.unchanged },
    { label: report.dry_run ? "Havuza eklenecek" : "Havuza eklenen", value: counts.poolAdded },
    { label: report.dry_run ? "Havuzdan çıkacak" : "Havuzdan çıkan", value: counts.poolRemoved },
  ];

  return (
    <div className="space-y-3 rounded-shape-md bg-surface-container-low p-4">
      <p className="text-title-small text-on-surface">
        {report.dry_run ? "Önizleme — hiçbir kayıt yazılmadı" : "İçe aktarma sonucu"}
      </p>

      {report.already_imported && (
        <div className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
          <Icon name="info" size="lg" />
          <span>
            Bu içerik daha önce aktarılmış. Güncelleme amaçlı yeniden aktarma engellenmez.
          </span>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {cells.map((c) => (
          <div key={c.label} className="rounded-shape-sm bg-surface-container px-3 py-2">
            <dt className="text-label-small text-on-surface-variant">{c.label}</dt>
            <dd className="text-title-medium text-on-surface">{formatNumber(c.value)}</dd>
          </div>
        ))}
      </dl>

      <HavuzOzeti report={report} poolAdded={counts.poolAdded} poolRemoved={counts.poolRemoved} />

      {ogrenci ? (
        <OgrenciMutabakati report={report} />
      ) : (
        <PersonelMutabakati report={report} onMerge={onMerge} busy={busy} />
      )}

      <IssueTable
        title={`Uyarılar (${report.warnings.length})`}
        issues={report.warnings}
        emptyText="Uyarı yok."
      />
      <IssueTable
        title={`Atlanan satırlar (${report.skipped.length})`}
        issues={report.skipped}
        emptyText="Atlanan satır yok."
      />
    </div>
  );
}

/** "N … ayrılış havuzuna eklenecek, M … havuzdan çıkacak" + havuza bağlantı. */
function HavuzOzeti({
  report,
  poolAdded,
  poolRemoved,
}: {
  report: ImportReport;
  poolAdded: number;
  poolRemoved: number;
}) {
  const birim = isStudentReport(report) ? "öğrenci" : "kişi";
  const cumle = report.dry_run
    ? `${formatNumber(poolAdded)} ${birim} ayrılış havuzuna eklenecek, ${formatNumber(poolRemoved)} ${birim} havuzdan çıkacak.`
    : `${formatNumber(poolAdded)} ${birim} ayrılış havuzuna eklendi, ${formatNumber(poolRemoved)} ${birim} havuzdan çıktı.`;
  return (
    <div className="flex items-start gap-2 rounded-shape-sm bg-surface-container px-4 py-3 text-body-medium text-on-surface">
      <Icon name="pending_actions" size="lg" className="mt-0.5 shrink-0" />
      <div className="min-w-0 space-y-1">
        <p className="text-label-large">{cumle}</p>
        <p className="text-body-small text-on-surface-variant">{HAVUZ_ACIKLAMASI}</p>
        {!report.dry_run && poolAdded > 0 && (
          <Link
            to={HAVUZ_ADRESI}
            className="inline-flex text-label-large text-primary underline underline-offset-2"
          >
            Ayrılış Havuzu&apos;nu aç
          </Link>
        )}
      </div>
    </div>
  );
}

const TH = "p-2 text-left text-label-medium text-on-surface-variant";
const TD = "p-2 text-on-surface";

function OgrenciMutabakati({ report }: { report: StudentImportReport }) {
  const kapsam = report.full_list
    ? "Karşılaştırma okulun tamamıyla yapıldı (dosya okulun tam listesi)."
    : "Karşılaştırma yalnız dosyada bulunan şubelerle yapıldı; diğer şubelere dokunulmadı.";
  return (
    <div className="space-y-3">
      <p className="text-body-small text-on-surface-variant">{kapsam}</p>

      {report.classes.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-body-small">
            <caption className="mb-1 text-left text-label-large text-on-surface-variant">
              Şube bazında etki
            </caption>
            <thead>
              <tr className="border-b border-outline-variant">
                <th className={TH}>Şube</th>
                <th className={TH}>Yeni</th>
                <th className={TH}>Güncellenen</th>
                <th className={TH}>Değişmeyen</th>
                <th className={TH}>{report.dry_run ? "Havuza eklenecek" : "Havuza eklenen"}</th>
              </tr>
            </thead>
            <tbody>
              {report.classes.map((c) => (
                <tr
                  key={`${c.class_level ?? "-"}-${c.class_section}`}
                  className="border-t border-outline-variant/50"
                >
                  <td className={TD}>{c.class_label || "Sınıfsız"}</td>
                  <td className={TD}>{formatNumber(c.created)}</td>
                  <td className={TD}>{formatNumber(c.updated)}</td>
                  <td className={TD}>{formatNumber(c.unchanged)}</td>
                  <td className={c.to_pool > 0 ? `${TD} font-semibold` : TD}>
                    {formatNumber(c.to_pool)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {report.pool_added.length > 0 && (
        <div>
          <p className="text-label-large text-on-surface-variant">
            {report.dry_run
              ? `Ayrılış havuzuna eklenecek öğrenciler (${formatNumber(report.pool_added.length)})`
              : `Ayrılış havuzuna eklenen öğrenciler (${formatNumber(report.pool_added.length)})`}
          </p>
          <p className="text-body-small text-on-surface-variant">
            {report.full_list
              ? "Okulun tam listesinde bulunmadıkları için ayrılış havuzuna eklenirler."
              : "Kayıtlı oldukları şube dosyada var ama kendileri dosyada bulunmadığı için ayrılış havuzuna eklenirler."}{" "}
            Durumları aktif kalır; ayrılıp ayrılmadıklarına havuzda karar verilir.
          </p>
          {!report.full_list && (
            <p className="mt-1 flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
              <Icon name="warning" />
              <span>{SUBE_DEGISIMI_UYARISI}</span>
            </p>
          )}
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-collapse text-body-small">
              <thead>
                <tr className="border-b border-outline-variant">
                  <th className={TH}>Okul no</th>
                  <th className={TH}>Ad soyad</th>
                  <th className={TH}>Sınıf</th>
                </tr>
              </thead>
              <tbody>
                {report.pool_added.map((s) => (
                  <tr key={s.id} className="border-t border-outline-variant/50">
                    <td className={TD}>{s.student_number || "—"}</td>
                    <td className={TD}>{s.full_name}</td>
                    <td className={TD}>{s.class_label || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function PersonelMutabakati({
  report,
  onMerge,
  busy,
}: {
  report: PersonnelImportReport;
  onMerge: (pair: SimilarPair) => void;
  busy: boolean;
}) {
  const ciftteki = new Set(report.similar_pairs.map((p) => p.existing_id));
  const turUyarisi = report.warnings.filter((w) => w.field === "member_kind").length;

  return (
    <div className="space-y-3">
      {turUyarisi > 0 && (
        <div className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
          <Icon name="warning" size="lg" />
          <span>
            {formatNumber(turUyarisi)} satırda üye türünü denetleyin: görev bilgisi tanınmadı. Yeni
            kayıtlar öğretmen olarak açılır; gerekirse kişiyi düzenleyip “Diğer personel” seçin.
            Satır numaraları aşağıdaki uyarılar tablosundadır.
          </span>
        </div>
      )}

      {report.pool_added.length > 0 && (
        <div className="space-y-2">
          <p className="text-label-large text-on-surface">
            {report.dry_run
              ? `Listede olmayan ${formatNumber(report.pool_added.length)} kişi ayrılış havuzuna eklenecek`
              : `Listede olmayan ${formatNumber(report.pool_added.length)} kişi ayrılış havuzuna eklendi`}
          </p>
          <p className="text-body-small text-on-surface-variant">
            Durumları aktif kalır; okuldan ayrılıp ayrılmadıklarına Ayrılış Havuzu&apos;nda karar
            verirsiniz.
          </p>
          <ul className="space-y-1">
            {report.pool_added.map((m) => (
              <li key={m.id} className="text-body-medium text-on-surface">
                {m.full_name}
                {ciftteki.has(m.id) && (
                  <span className="ml-2 text-body-small text-on-surface-variant">
                    (olası aynı kişi — aşağıya bakın)
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.similar_pairs.length > 0 && (
        <div className="space-y-2">
          <p className="text-label-large text-on-surface">
            Olası aynı kişi ({formatNumber(report.similar_pairs.length)})
          </p>
          <p className="text-body-small text-on-surface-variant">
            {report.dry_run
              ? "Listedeki yeni ad, kayıttaki bir kişiye benziyor (ör. soyadı değişimi). Aktardıktan sonra iki kaydı burada ya da Ayrılış Havuzu'nda birleştirebilirsiniz."
              : "Birleştirilen eski kaydın kütüphane bağları yeni kayda taşınır ve eski kayıt silinir."}
          </p>
          <ul className="space-y-2">
            {report.similar_pairs.map((p) => (
              <li
                key={`${p.row_number}-${p.existing_id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-shape-sm bg-surface-container px-3 py-2"
              >
                <span className="text-body-medium text-on-surface">
                  Satır {p.row_number}: {p.row_name} ↔ kayıttaki {p.existing_name}
                </span>
                {!report.dry_run && p.new_id !== null && (
                  <Button
                    variant="tonal"
                    icon="merge"
                    disabled={busy}
                    onClick={() => onMerge(p)}
                    aria-label={`${p.existing_name} kaydını ${p.row_name} kaydıyla birleştir`}
                  >
                    Birleştir
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function IssueTable({
  title,
  issues,
  emptyText,
}: {
  title: string;
  issues: ImportIssue[];
  emptyText: string;
}) {
  return (
    <div>
      <p className="text-label-large text-on-surface-variant">{title}</p>
      {issues.length === 0 ? (
        <EmptyState compact title={emptyText} icon="check_circle" />
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse text-body-small">
            <thead>
              <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
                <th className="p-2">Satır</th>
                <th className="p-2">Alan</th>
                <th className="p-2">Sorun</th>
                <th className="p-2">Değer</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((issue, i) => (
                <tr
                  key={`${issue.row_number}-${issue.field}-${i}`}
                  className="border-t border-outline-variant/50"
                >
                  <td className="p-2 text-on-surface-variant">{issue.row_number}</td>
                  <td className="p-2 text-on-surface-variant">
                    {ALAN_ADI[issue.field] ?? (issue.field || "—")}
                  </td>
                  <td className="p-2 text-on-surface">{issue.issue}</td>
                  <td className="p-2 text-on-surface-variant">{issue.raw_value || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
