// Sayımın sonuçları, kalemleri ve sayım fazlası (F9). Hepsi kişisizdir: kalemde ödünç
// alanın ya da teslim alanın kimliği yoktur (sunucu göndermez).
//
// - "Sonuçlar": kayıtlara göre miktar (anlık görüntü), bulunan, kayda göre alınan, noksan,
//   fazla, hasar önerisi — sayım tutanağının sayıları.
// - "Kalemler": sonuca göre süzülen sayfalı liste (tamamlanmış sayımda varsayılan "Noksan").
// - "Sayım Fazlası": etiketsiz eklenen ya da anlık görüntüde olmayan kitaplar; onaydan önce
//   her birinin kayda alınacağı eser seçilir ya da gerekçesiyle "Kayda alınmayacak" denir.

import { useEffect, useRef, useState } from "react";

import { formatNumber } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { Bilgi, Rozet } from "../ayiklama/ortak";
import { KATALOG_SAYFA_BOYUTU } from "../kutuphane/api";
import { kodSecenekleri } from "../kutuphane/ortak";
import { barkodBicimle } from "../kutuphane/tarama";
import { SAYIM_SONUCU_TR, sayimApi } from "./api";
import type { SayimAyrintisi, SayimKalemi, SayimOzeti, SayimSonucu } from "./api";
import { FazlaDiyalogu } from "./SayimDiyaloglari";
import type { FazlaKipi } from "./SayimDiyaloglari";

/** Sonuç kartının başlığı ve kalem listesinin başlığı (kılavuz bu adlarla anlatır). */
export const SONUCLAR_BASLIGI = "Sonuçlar";
export const KALEMLER_BASLIGI = "Kalemler";
export const FAZLA_BASLIGI = "Sayım Fazlası";

// ---------------------------------------------------------------------------
// Sonuçlar
// ---------------------------------------------------------------------------

export function Sonuclar({ ozet, tamam }: { ozet: SayimOzeti; tamam: boolean }) {
  const fazla = ozet.surplus - ozet.surplus_excluded;
  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <h2 className="text-title-medium font-semibold text-on-surface">{SONUCLAR_BASLIGI}</h2>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Bilgi etiket="Kayıtlara göre (anlık görüntü)">{formatNumber(ozet.snapshot)}</Bilgi>
        <Bilgi etiket="Bulunan">{formatNumber(ozet.results.FOUND)}</Bilgi>
        <Bilgi etiket="Kayda göre alınan">{formatNumber(ozet.results.BY_RECORD)}</Bilgi>
        <Bilgi etiket="Noksan">{formatNumber(ozet.results.MISSING)}</Bilgi>
        <Bilgi etiket="Sayım fazlası">{formatNumber(fazla)}</Bilgi>
        {!tamam && <Bilgi etiket="Henüz sayılmayan">{formatNumber(ozet.results.PENDING)}</Bilgi>}
        {ozet.results.EXITED > 0 && (
          <Bilgi etiket="Sayım sırasında kayıttan çıkan">{formatNumber(ozet.results.EXITED)}</Bilgi>
        )}
        {ozet.damage_write_off > 0 && (
          <Bilgi etiket="Hasar önerisi (TMY 27/1)">{formatNumber(ozet.damage_write_off)}</Bilgi>
        )}
        {ozet.found_in_round2 > 0 && (
          <Bilgi etiket="İkinci sayımda bulunan">{formatNumber(ozet.found_in_round2)}</Bilgi>
        )}
      </dl>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Kalemler
// ---------------------------------------------------------------------------

const SONUC_TONU: Record<SayimSonucu, "ikincil" | "ucuncul" | "hata" | "notr"> = {
  PENDING: "notr",
  FOUND: "ikincil",
  BY_RECORD: "notr",
  MISSING: "hata",
  SURPLUS: "ucuncul",
  EXITED: "notr",
};

export function Kalemler({
  sayim,
  varsayilanSonuc = "",
  yenile = 0,
}: {
  sayim: SayimAyrintisi;
  varsayilanSonuc?: SayimSonucu | "";
  /** Dışarıdan tazeleme sayacı (okutma, onay). */
  yenile?: number;
}) {
  const [sonuc, setSonuc] = useState<SayimSonucu | "">(varsayilanSonuc);
  const [arama, setArama] = useState("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<SayimKalemi>>(emptyPage<SayimKalemi>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    sayimApi
      .kalemler(sayim.id, {
        result: sonuc,
        surplus: false,
        q: arama.trim(),
        limit: KATALOG_SAYFA_BOYUTU,
        offset,
      })
      .then((s) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(s, offset, KATALOG_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(s);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Kalemler yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [sayim.id, sonuc, arama, offset, yenile]);

  const secenekler = kodSecenekleri(
    Object.fromEntries(
      Object.entries(SAYIM_SONUCU_TR).filter(([kod]) => kod !== "SURPLUS"),
    ) as Record<string, string>,
  );

  return (
    <section aria-labelledby="sayim-kalemleri" className="space-y-3">
      <h2 id="sayim-kalemleri" className="text-title-medium font-semibold text-on-surface">
        {KALEMLER_BASLIGI}
      </h2>
      <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-end gap-3">
          <Select
            className="w-56"
            label="Sonuç"
            placeholder="Tümü"
            value={sonuc}
            onChange={(e) => {
              setSonuc(e.target.value as SayimSonucu | "");
              setOffset(0);
            }}
            options={secenekler}
          />
          <TextField
            className="w-72"
            label="Ara"
            placeholder="Kaynak adı ya da barkod"
            value={arama}
            onChange={(e) => {
              setArama(e.target.value);
              setOffset(0);
            }}
          />
        </div>
      </Card>
      {hata && <ErrorBand hata={hata} />}
      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <p className="text-body-medium text-on-surface-variant">Bu seçimde kalem yok.</p>
      ) : (
        <>
          <Card elevation={0} className="overflow-x-auto p-0 shadow-elevation-1 scrollbar-thin">
            <table className="w-full min-w-table border-collapse text-body-small">
              <thead className="bg-surface-container-low">
                <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
                  <th className="px-4 py-3 font-semibold">Barkod</th>
                  <th className="px-4 py-3 font-semibold">Kaynak adı</th>
                  <th className="px-4 py-3 font-semibold">Bölüm</th>
                  <th className="px-4 py-3 font-semibold">Kayda göre durum</th>
                  <th className="px-4 py-3 font-semibold">Sonuç</th>
                  <th className="px-4 py-3 font-semibold">Onay sonucu</th>
                </tr>
              </thead>
              <tbody>
                {sayfa.results.map((k) => (
                  <tr key={k.id} className="border-t border-outline-variant/50 align-top">
                    <td className="whitespace-nowrap px-4 py-3 font-mono">{k.barcode_display}</td>
                    <td className="px-4 py-3">
                      <p className="text-on-surface">{k.work_title}</p>
                      {k.work_authors && (
                        <p className="text-on-surface-variant">{k.work_authors}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {[k.section_name, k.class_library].filter(Boolean).join(" · ") || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <p>{k.expected_status_display || "—"}</p>
                      <p className="text-on-surface-variant">{k.basis_display}</p>
                    </td>
                    <td className="px-4 py-3">
                      <Rozet ton={SONUC_TONU[k.result]}>{k.result_display}</Rozet>
                      {k.found_via === "RETURN" && (
                        <p className="mt-1 text-on-surface-variant">{k.found_via_display}</p>
                      )}
                      {k.basis_fallback && (
                        <p className="mt-1 text-on-surface-variant">
                          {k.expected_status === "IN_REPAIR"
                            ? "Onarımdan geri alınamadı; kayda göre alındı."
                            : "Toplanamadı; kayda göre alındı."}
                        </p>
                      )}
                      {k.damage_write_off && (
                        <p className="mt-1 text-on-surface-variant">Hasar önerisi (TMY 27/1)</p>
                      )}
                      {k.case_type && (
                        <p className="mt-1 text-on-surface-variant">
                          {`${k.case_type === "LOST" ? "Kayıp" : "Hasar"} dosyası: ${k.case_resolution_display}`}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <p>{k.outcome_display || "—"}</p>
                      {k.outcome_note && (
                        <p className="text-on-surface-variant">{k.outcome_note}</p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sayım fazlası
// ---------------------------------------------------------------------------

/** "Sayım Fazlası" kartının süzgeci: kararı bekleyenler ya da hepsi (onay bekleyenleri ister). */
export const FAZLA_SUZGECI_TR = { bekleyen: "Karar bekleyenler", hepsi: "Tümü" } as const;
type FazlaSuzgeci = keyof typeof FAZLA_SUZGECI_TR;

function fazlaKarari(k: SayimKalemi): { metin: string; ton: "ikincil" | "notr" | "hata" } {
  if (k.outcome === "ENTERED") {
    return { metin: `Kayda alındı: ${barkodBicimle(k.created_copy_barcode)}`, ton: "ikincil" };
  }
  if (k.outcome === "NOT_ENTERED") return { metin: "Kayda alınmadı", ton: "notr" };
  if (k.surplus_bound_barcode) {
    // Etiket sayım sırasında Hızlı Kayıt'ta bağlandı: kitap kayıtta, onay yeniden almaz.
    return { metin: `Sayım sırasında kayda girdi: ${k.surplus_bound_barcode}`, ton: "ikincil" };
  }
  if (k.surplus_excluded) return { metin: "Kayda alınmayacak", ton: "notr" };
  if (k.surplus_work_title)
    return { metin: `Kayda alınacak: ${k.surplus_work_title}`, ton: "ikincil" };
  return { metin: "Karar bekliyor", ton: "hata" };
}

export function Fazlalar({
  sayim,
  yenile = 0,
  onDegisti,
  onPencere,
}: {
  sayim: SayimAyrintisi;
  yenile?: number;
  onDegisti: (ileti: string) => void;
  /**
   * Bir pencere (fazla penceresi ya da onay kutusu) açıldı/kapandı: süren sayımda okutma kutusu
   * pencere açıkken beklemededir, okutulan kod kaybolmaz (F9 düzeltme turu).
   */
  onPencere?: (acik: boolean) => void;
}) {
  const [sayfa, setSayfa] = useState<Paginated<SayimKalemi> | null>(null);
  const [offset, setOffset] = useState(0);
  const [suzgec, setSuzgec] = useState<FazlaSuzgeci>("hepsi");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [diyalog, setDiyalog] = useState<{ kip: FazlaKipi; kalem: SayimKalemi | null } | null>(
    null,
  );
  const [ic, setIc] = useState(0);
  const confirm = useConfirm();
  const suruyor = sayim.status === "IN_PROGRESS";
  const duzenlenir = suruyor || sayim.status === "COMPLETED";
  const bekleyenSayisi = sayim.summary.surplus_unresolved;

  // Pencere açık mı? Ebeveyne bildirilir (okutma kutusu beklemeye alınır).
  const pencereAcik = diyalog !== null;
  const onPencereRef = useRef(onPencere);
  onPencereRef.current = onPencere;
  useEffect(() => {
    if (!pencereAcik) return undefined;
    onPencereRef.current?.(true);
    return () => onPencereRef.current?.(false);
  }, [pencereAcik]);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    sayimApi
      .kalemler(sayim.id, {
        surplus: true,
        undecided: suzgec === "bekleyen" ? true : undefined,
        limit: KATALOG_SAYFA_BOYUTU,
        offset,
      })
      .then((s) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(s, offset, KATALOG_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(s);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal && !geriDusuluyor) setHata(hataOku(e, "Sayım fazlası yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [sayim.id, yenile, ic, suzgec, offset]);

  const bitti = (ileti: string) => {
    setDiyalog(null);
    setIc((n) => n + 1);
    onDegisti(ileti);
  };

  const cikar = async (k: SayimKalemi) => {
    onPencere?.(true);
    let onay = false;
    try {
      onay = await confirm({
        title: "Sayım fazlası listeden çıkarılsın mı?",
        message: "Yanlış okutulan kod listeden kalkar; kitap kayda alınmaz.",
        confirmLabel: "Çıkar",
      });
    } finally {
      onPencere?.(false);
    }
    if (!onay) return;
    try {
      await sayimApi.fazlaCikar(sayim.id, k.id);
      bitti("Sayım fazlası listeden çıkarıldı.");
    } catch (e) {
      setHata(hataOku(e, "Sayım fazlası çıkarılamadı."));
    }
  };

  if (sayfa === null && hata === null) return null;
  if (sayfa !== null && sayfa.count === 0 && suzgec === "hepsi" && !suruyor) return null;
  const kalemler = sayfa?.results ?? [];

  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-title-medium font-semibold text-on-surface">{FAZLA_BASLIGI}</h2>
          <p className="max-w-3xl text-body-small text-on-surface-variant">
            Sayım başladığında kayıtta olmayan kitaplar. Onaydan önce her birinin kayda alınacağı
            eseri seçin ya da gerekçesiyle “Kayda alınmayacak” deyin; onayda yeni numarayla kayda
            alınır (Taşınır Mal Yönetmeliği md. 17).
          </p>
        </div>
        {suruyor && (
          <Button
            variant="outlined"
            icon="add"
            onClick={() => setDiyalog({ kip: "ekle", kalem: null })}
          >
            Etiketsiz kitap ekle
          </Button>
        )}
      </div>
      {duzenlenir && (
        <div className="flex flex-wrap items-end gap-3">
          <Select
            className="w-56"
            label="Göster"
            value={suzgec}
            onChange={(e) => {
              setSuzgec(e.target.value as FazlaSuzgeci);
              setOffset(0);
            }}
            options={kodSecenekleri(FAZLA_SUZGECI_TR)}
          />
          <p className="text-body-small text-on-surface-variant">
            {`${formatNumber(sayim.summary.surplus)} sayım fazlası · kararı bekleyen ${formatNumber(bekleyenSayisi)}`}
          </p>
        </div>
      )}
      {hata && <ErrorBand hata={hata} />}
      {sayfa !== null && sayfa.count === 0 ? (
        <p className="text-body-medium text-on-surface-variant">
          {suzgec === "bekleyen" ? "Kararı bekleyen sayım fazlası yok." : "Sayım fazlası yok."}
        </p>
      ) : (
        <>
          <ul aria-label="Sayım fazlası kitaplar" className="divide-y divide-outline-variant/50">
            {kalemler.map((k) => {
              const karar = fazlaKarari(k);
              return (
                <li key={k.id} className="flex flex-wrap items-start justify-between gap-3 py-2">
                  <div className="min-w-0 space-y-0.5">
                    <p className="text-body-medium text-on-surface">
                      <span className="font-mono">{k.surplus_barcode_display || "Etiketsiz"}</span>
                      {k.surplus_note ? ` — ${k.surplus_note}` : ""}
                    </p>
                    <Rozet ton={karar.ton}>{karar.metin}</Rozet>
                  </div>
                  {duzenlenir && !k.outcome && !k.surplus_bound_barcode && (
                    <div className="flex flex-wrap gap-1">
                      <Button
                        variant="text"
                        icon="menu_book"
                        onClick={() => setDiyalog({ kip: "eser", kalem: k })}
                        aria-label={`${k.surplus_barcode_display || "Etiketsiz kitap"} için eser seç`}
                      >
                        Eseri seç
                      </Button>
                      <Button
                        variant="text"
                        icon="block"
                        onClick={() => setDiyalog({ kip: "haric", kalem: k })}
                      >
                        Kayda alınmayacak
                      </Button>
                      {suruyor && (
                        <Button variant="text" icon="close" onClick={() => void cikar(k)}>
                          Çıkar
                        </Button>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
          {sayfa !== null && (
            <PaginationBar
              count={sayfa.count}
              offset={offset}
              pageSize={KATALOG_SAYFA_BOYUTU}
              onOffset={setOffset}
            />
          )}
        </>
      )}
      {diyalog !== null && (
        <FazlaDiyalogu
          sayimId={sayim.id}
          kip={diyalog.kip}
          kalem={diyalog.kalem}
          onClose={() => setDiyalog(null)}
          onKaydedildi={bitti}
        />
      )}
    </Card>
  );
}
