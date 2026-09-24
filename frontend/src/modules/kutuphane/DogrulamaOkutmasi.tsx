// Etiketler → Doğrulama Okutması (tasarım §7.2): etiket kitaba yapıştırıldıktan
// sonra okutulur; okunan her etiket "doğrulandı" olarak işaretlenir. Okunmayan
// ya da hiç yapıştırılmayan etiketler "Doğrulanmamış Etiketler" listesinde kalır.
//
// Okuyucu masa ekranı kuralları (§7.3 BarcodeInput):
//   * kutu kendiliğinden odaklanır, okuyucunun gönderdiği Enter okutmayı bitirir;
//   * okutma anında kutu boşalır, sonuç beklenirken gelen okutmalar SIRAYA
//     alınır (hızlı okutmada hiçbir kod kaybolmaz);
//   * odak kutudan çıkarsa görünür uyarı çıkar; sayfada bir yazı alanı dışında
//     rakam ya da harf tuşuna basılırsa (okuyucu da klavyedir) odak kutuya döner.
//
// Okutma bir OLAYDIR, hata değil: sunucu her durumda bir sonuç gövdesi döner
// (doğrulandı · daha önce doğrulandı · reddedildi) ve ileti Türkçedir: ISBN
// barkodu, üye kartı, henüz bağlanmamış ya da iptal edilmiş boş etiket, basıldı
// olarak işaretlenmemiş nüsha ayrı ayrı söylenir.
//
// Görevli kipi (kullanıcı kararı 24.09.2026): bu ekran görevli ekranından da
// açılır (`kip/GorevliEkrani`, `gorevli`). Görevli kipinde açık tek etiket ucu
// okutmadır (`POST library/labels/verify/`); "Doğrulanmamış Etiketler" listesi
// yönetici ucudur, görevli kipinde İSTENMEZ ve gösterilmez (istenseydi 403
// `kip_yetkisiz` kip olayını tetiklerdi). Sunucu görevliye nüsha özetinden
// yalnız barkodu ve eser adını döndürür; ekran zaten yalnız onları yazar.

import { useCallback, useEffect, useRef, useState } from "react";

import { formatDateTime, formatNumber } from "../../lib/format";
import { emptyPage } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { ETIKET_SAYFA_BOYUTU, etiketApi } from "./etiketApi";
import type { DogrulamaSonucuTuru, KuyrukNushasi, TaramaNushasi } from "./etiketApi";

/** Ekranda tutulan son okutma sayısı. */
const GOSTERILEN_OKUTMA = 30;
/** Okuyucunun gönderebileceği tek karakter: rakam, Latin harfi, tire. */
const OKUYUCU_KARAKTERI = /^[0-9A-Za-z-]$/;

interface Okutma {
  no: number;
  kod: string;
  sonuc: DogrulamaSonucuTuru | "hata";
  ileti: string;
  nusha: TaramaNushasi | null;
}

const SONUC_GORUNUMU: Record<Okutma["sonuc"], { ikon: string; sinif: string }> = {
  verified: { ikon: "check_circle", sinif: "bg-secondary-container text-on-secondary-container" },
  already_verified: {
    ikon: "done_all",
    sinif: "bg-surface-container-high text-on-surface",
  },
  rejected: { ikon: "error", sinif: "bg-error-container text-on-error-container" },
  hata: { ikon: "cloud_off", sinif: "bg-error-container text-on-error-container" },
};

/** Odak bir yazı alanında mı? (oradaysa kullanıcı yazıyordur, odak çalınmaz) */
function yaziAlanindaMi(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const etiket = el.tagName;
  return etiket === "INPUT" || etiket === "TEXTAREA" || etiket === "SELECT" || el.isContentEditable;
}

export default function DogrulamaOkutmasi({
  tazeleme = 0,
  onDegisti,
  gorevli = false,
}: {
  /** Etiketler sayfasının tazeleme sayacı (başka sekmede yazma olunca liste yenilenir). */
  tazeleme?: number;
  /** Bir etiket doğrulanınca (sayaçlar tazelensin). */
  onDegisti?: () => void;
  /** Görevli kipi: yalnız okutma; doğrulanmamışlar listesi istenmez. */
  gorevli?: boolean;
}) {
  const kutuRef = useRef<HTMLInputElement>(null);
  const [kod, setKod] = useState("");
  const [odakta, setOdakta] = useState(true);
  const [okutmalar, setOkutmalar] = useState<Okutma[]>([]);
  const [dogrulanan, setDogrulanan] = useState(0);
  const [bekleyen, setBekleyen] = useState(0);
  const sira = useRef<string[]>([]);
  const isleniyor = useRef(false);
  const sayac = useRef(0);
  const acik = useRef(true);

  // Doğrulanmamışlar listesi
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<KuyrukNushasi>>(emptyPage<KuyrukNushasi>());
  const [ilkYukleme, setIlkYukleme] = useState(true);
  const [listeHatasi, setListeHatasi] = useState<SayfaHatasi | null>(null);
  const [listeTazeleme, setListeTazeleme] = useState(0);

  useEffect(() => {
    acik.current = true;
    kutuRef.current?.focus();
    return () => {
      acik.current = false;
    };
  }, []);

  useEffect(() => {
    // Görevli kipinde liste ucu kapalıdır (403): hiç istenmez.
    if (gorevli) return;
    let iptal = false;
    etiketApi
      .dogrulanmamislar({ limit: ETIKET_SAYFA_BOYUTU, offset })
      .then((sonuc) => {
        if (iptal) return;
        setSayfa(sonuc);
        setListeHatasi(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setListeHatasi(hataOku(e, "Doğrulanmamış etiketler yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setIlkYukleme(false);
      });
    return () => {
      iptal = true;
    };
  }, [gorevli, offset, tazeleme, listeTazeleme]);

  // Okuyucu klavye gibi yazar: odak bir yazı alanında değilken gelen rakam ya da
  // harf okutma kutusuna yönlendirilir (tuşun kendisi de kutuya düşer). Yalnız
  // okuyucunun gönderebileceği karakterler yönlendirilir: Boşluk yönlendirilseydi
  // odaktaki düğme ya da sekme Boşluk ile çalışmazdı (klavye erişilebilirliği).
  useEffect(() => {
    const yakala = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.altKey || e.metaKey || !OKUYUCU_KARAKTERI.test(e.key)) return;
      if (yaziAlanindaMi(document.activeElement)) return;
      kutuRef.current?.focus();
    };
    document.addEventListener("keydown", yakala, true);
    return () => document.removeEventListener("keydown", yakala, true);
  }, []);

  const ekle = useCallback((okutma: Omit<Okutma, "no">) => {
    sayac.current += 1;
    const no = sayac.current;
    setOkutmalar((onceki) => [{ ...okutma, no }, ...onceki].slice(0, GOSTERILEN_OKUTMA));
  }, []);

  const isle = useCallback(async () => {
    if (isleniyor.current) return;
    isleniyor.current = true;
    try {
      while (sira.current.length > 0) {
        const siradaki = sira.current.shift() as string;
        setBekleyen(sira.current.length);
        try {
          const sonuc = await etiketApi.dogrula(siradaki);
          if (!acik.current) return;
          ekle({ kod: siradaki, sonuc: sonuc.result, ileti: sonuc.message, nusha: sonuc.copy });
          if (sonuc.result === "verified") {
            setDogrulanan((n) => n + 1);
            setListeTazeleme((k) => k + 1);
            onDegisti?.();
          }
        } catch (e) {
          if (!acik.current) return;
          ekle({
            kod: siradaki,
            sonuc: "hata",
            ileti: hataOku(e, "Okutma kaydedilemedi; etiketi yeniden okutun.").message,
            nusha: null,
          });
        }
      }
    } finally {
      isleniyor.current = false;
    }
  }, [ekle, onDegisti]);

  const okut = () => {
    const ham = kod.trim();
    // Kutu HEMEN boşalır: okuyucunun sıradaki kodu öncekine eklenmesin.
    setKod("");
    if (!ham) return;
    sira.current.push(ham);
    setBekleyen(sira.current.length);
    void isle();
  };

  const son = okutmalar[0];

  return (
    <div className="space-y-4">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Yapıştırılan Etiketi Okutun</p>
        <p className="max-w-4xl text-body-medium text-on-surface-variant">
          {gorevli
            ? "Etiketleri kitaplara yapıştırdıktan sonra her kitabın kütüphane etiketini okutun. " +
              "Okunan etiket doğrulanır. Kitabın arka kapağındaki ISBN barkodunu değil, " +
              "yapıştırdığınız etiketi okutun."
            : "Etiketleri kitaplara yapıştırdıktan sonra her kitabın kütüphane etiketini okutun. " +
              "Okunan etiket doğrulanır; okutulmayanlar aşağıdaki listede kalır. Kitabın arka " +
              "kapağındaki ISBN barkodunu değil, yapıştırdığınız etiketi okutun."}
        </p>
        <TextField
          className="max-w-xl"
          label="Kütüphane etiketi"
          ref={kutuRef}
          value={kod}
          autoComplete="off"
          onChange={(e) => setKod(e.target.value)}
          onFocus={() => setOdakta(true)}
          onBlur={() => setOdakta(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              okut();
            }
          }}
          placeholder="2026-000123"
          helperText="Okuyucuyla okutun ya da numarayı yazıp Enter'a basın."
        />
        {!odakta && (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
          >
            <Icon name="warning" size="lg" className="shrink-0" />
            <span className="min-w-0 flex-1">
              Okutma kutusu odakta değil. Okutmadan önce kutuya dönün; okuyucunun gönderdiği kod
              başka bir yere yazılabilir.
            </span>
            <Button variant="text" icon="barcode_reader" onClick={() => kutuRef.current?.focus()}>
              Kutuya dön
            </Button>
          </div>
        )}

        {son && (
          <div
            role="status"
            aria-live="polite"
            className={`flex items-start gap-3 rounded-shape-md px-4 py-3 ${SONUC_GORUNUMU[son.sonuc].sinif}`}
          >
            <Icon name={SONUC_GORUNUMU[son.sonuc].ikon} size="2xl" className="shrink-0" />
            <div className="min-w-0">
              <p className="text-title-medium">{son.ileti}</p>
              <p className="text-body-medium">
                {son.nusha
                  ? `${son.nusha.barcode_display} — ${son.nusha.work_title}`
                  : `Okutulan: ${son.kod}`}
              </p>
            </div>
          </div>
        )}

        <p className="text-body-small text-on-surface-variant">
          Bu ekranda doğrulanan: {formatNumber(dogrulanan)}
          {bekleyen > 0 && ` · sırada bekleyen okutma: ${formatNumber(bekleyen)}`}
        </p>

        {okutmalar.length > 1 && (
          <ol aria-label="Son okutmalar" className="space-y-1 text-body-small">
            {okutmalar.slice(1).map((o) => (
              <li key={o.no} className="flex items-start gap-2 text-on-surface-variant">
                <Icon name={SONUC_GORUNUMU[o.sonuc].ikon} size="sm" className="mt-0.5 shrink-0" />
                <span>
                  {o.nusha ? `${o.nusha.barcode_display} — ${o.nusha.work_title}` : o.kod}:{" "}
                  {o.ileti}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Card>

      {!gorevli && (
        <DogrulanmamisListesi
          sayfa={sayfa}
          offset={offset}
          onOffset={setOffset}
          ilkYukleme={ilkYukleme}
          hata={listeHatasi}
        />
      )}
    </div>
  );
}

/** "Doğrulanmamış Etiketler" listesi — yalnız yönetici kipinde (liste ucu görevliye kapalı). */
function DogrulanmamisListesi({
  sayfa,
  offset,
  onOffset,
  ilkYukleme,
  hata,
}: {
  sayfa: Paginated<KuyrukNushasi>;
  offset: number;
  onOffset: (offset: number) => void;
  ilkYukleme: boolean;
  hata: SayfaHatasi | null;
}) {
  const sutunlar: Column<KuyrukNushasi>[] = [
    { header: "Barkod", cell: (n) => <span className="font-mono">{n.barcode_display}</span> },
    { header: "Kaynak adı", cell: (n) => n.work_title },
    { header: "Yer numarası", cell: (n) => n.call_number || "—" },
    { header: "Bölüm", cell: (n) => n.section_name || "—" },
    { header: "Basıldı", cell: (n) => formatDateTime(n.label_printed_at) },
  ];

  return (
    <div className="space-y-3">
      <p className="text-title-medium text-on-surface">
        Doğrulanmamış Etiketler: {formatNumber(sayfa.count)}
      </p>
      <p className="text-body-small text-on-surface-variant">
        Barkod etiketi basıldı olarak işaretlenmiş ama henüz okutulmamış nüshalar. Listedeki bir
        kitabın etiketi yoksa ya da okunmuyorsa etiketini Basım Geçmişi'nden yeniden basın.
      </p>
      {hata && <ErrorBand hata={hata} />}
      {ilkYukleme ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          compact
          icon="task_alt"
          title="Doğrulanmamış etiket yok — basılan bütün etiketler okutuldu."
        />
      ) : (
        <>
          <DataTable columns={sutunlar} rows={sayfa.results} />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={ETIKET_SAYFA_BOYUTU}
            onOffset={onOffset}
          />
        </>
      )}
    </div>
  );
}
