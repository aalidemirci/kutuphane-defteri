// Sayımın ayrıntısı (F9; TMY 32, tasarım §9-10, §9-11, §10 E10, D17).
//
// Adım rayı: Taslak → Sayım → İkinci sayım (yalnız noksan çıkarsa — TMY 32/6) → Harcama
// yetkilisi onayı → Onaylandı. Her adımın eylemi yalnız o adımda görünür; kural (hangi
// geçişin hangi durumda yapılabildiği, kurul, durdurma, onay tarihi) SUNUCUDADIR ve ret
// iletisi olduğu gibi gösterilir.
//
// İki seçenek (TMY 32/3 durdurması ve sayım için hizmet arası) ve iade üç AYRI satırda
// gösterilir (`options` — tutanakla aynı satırlar). Seçilen kilitler "Sürüyor" ve
// "Tamamlandı"da sürer, onaya ya da iptale dek (D17).
//
// Geri dönüşü olmayan işlemler onaydan geçer: başlatma (anlık görüntü), tamamlama, harcama
// yetkilisinin onayı (ikinci doğrulama kutusu) ve iptal.

import { useCallback, useEffect, useRef, useState } from "react";

import { formatDate, formatDateTime, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Stepper from "../../ui/Stepper";
import type { StepperItem, StepperStatus } from "../../ui/Stepper";
import { BelgeSatiri, Bilgi, Rozet } from "../ayiklama/ortak";
import { EK_ADI, sayimAdi, sayimApi } from "./api";
import type { SayimAyrintisi as SayimVerisi, SayimBelgesi } from "./api";
import { IptalDiyalogu, OnayDiyalogu } from "./SayimDiyaloglari";
import { Fazlalar, Kalemler, Sonuclar } from "./SayimKalemleri";
import SayimOkutmasi from "./SayimOkutmasi";
import SayimTaslagi from "./SayimTaslagi";

/** Adım rayının adları (sözlük §4.15). */
export const SAYIM_ADIMLARI = [
  "Taslak",
  "Sayım",
  "İkinci sayım",
  "Harcama yetkilisi onayı",
  "Onaylandı",
] as const;

/** Tamamlama onayının metinleri (ilk tur ve ikinci sayım). */
export const TAMAMLA_METNI =
  "Okutulmayan nüshalar sınıflanır: ödünçte ve teslimde olan kayda göre alınır, sayım " +
  "sırasında kütüphaneye dönen bulunmuş sayılır. Bulunamayan nüsha varsa ikinci sayıma " +
  "geçilir (Taşınır Mal Yönetmeliği md. 32/6).";
export const IKINCI_TAMAMLA_METNI =
  "Yine bulunamayan nüshalar “Noksan” olarak yazılır ve harcama yetkilisinin onayı beklenir. " +
  "Seçilen durdurma ve hizmet arası onaya ya da iptale dek sürer.";
/**
 * Sırada okutma varken tamamlama başlamaz (F9 düzeltme turu): sayım tamamlanınca okutma
 * kutusu kalkar ve sıradaki kodlar kaybolurdu; ikinci sayımda bulunan kitap noksan kalırdı.
 */
export function bekleyenOkutmaIletisi(sayi: number): string {
  return `Sırada işlenmeyi bekleyen ${formatNumber(sayi)} okutma var. Okutmalar bitince yeniden tamamlayın.`;
}

type Diyalog = "onay" | "iptal" | null;

function adimlar(s: SayimVerisi): StepperItem[] {
  const [taslak, sayim, ikinci, onay, onaylandi] = SAYIM_ADIMLARI;
  const iptal = s.status === "CANCELLED";
  const ikinciVar = s.round === 2;
  const sira: Record<string, number> = {
    DRAFT: 0,
    IN_PROGRESS: ikinciVar ? 2 : 1,
    COMPLETED: 3,
    APPROVED: 4,
  };
  const guncel = sira[s.status] ?? -1;
  const liste = [
    { key: "taslak", label: taslak, icon: "edit_note" },
    { key: "sayim", label: sayim, icon: "barcode_reader" },
    { key: "ikinci", label: ikinci, icon: "replay" },
    { key: "onay", label: onay, icon: "approval" },
    { key: "onaylandi", label: onaylandi, icon: "task_alt" },
  ];
  return liste.map((a, i) => {
    let st: StepperStatus = "upcoming";
    if (iptal) st = "skipped";
    else if (i === 2 && !ikinciVar && guncel >= 3) st = "skipped";
    else if (i < guncel || s.status === "APPROVED") st = "done";
    else if (i === guncel) st = "current";
    return { ...a, status: st };
  });
}

function kurulMetni(s: SayimVerisi): string {
  const uyeler = s.committee_members.split("\n").filter((u) => u.trim());
  return [s.committee_chair, s.committee_property_officer, ...uyeler]
    .filter((a) => a.trim())
    .join(" · ");
}

export default function SayimAyrintisi({ id, onGeri }: { id: number; onGeri: () => void }) {
  const [sayim, setSayim] = useState<SayimVerisi | null>(null);
  const [belgeler, setBelgeler] = useState<SayimBelgesi[]>([]);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const [diyalog, setDiyalog] = useState<Diyalog>(null);
  // F9 düzeltme turu: okutma kutusu YALNIZ bu sayfanın iki penceresinde değil, sayım fazlası
  // pencerelerinde ve onay kutularında (tamamla, çıkar) da beklemededir — pencere açıkken
  // okutulan kod tampona alınır, pencere kapanınca işlenir (F6 tamponu).
  const [fazlaPenceresi, setFazlaPenceresi] = useState(0);
  const [tamamlaOnayi, setTamamlaOnayi] = useState(false);
  // Sırada bekleyen ve işlenmekte olan okutma sayısı (`BarcodeInput` bildirir).
  const [bekleyen, setBekleyen] = useState(0);
  const bekleyenRef = useRef(0);
  const bekleyeniYaz = useCallback((n: number) => {
    bekleyenRef.current = n;
    setBekleyen(n);
  }, []);
  const fazlaPenceresiDegisti = useCallback(
    (acik: boolean) => setFazlaPenceresi((n) => Math.max(0, n + (acik ? 1 : -1))),
    [],
  );
  const [yenile, setYenile] = useState(0);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const yukle = useCallback(async () => {
    const [s, b] = await Promise.all([sayimApi.sayim(id), sayimApi.belgeler(id)]);
    setSayim(s);
    setBelgeler(b);
    setYenile((n) => n + 1);
  }, [id]);

  useEffect(() => {
    let iptal = false;
    Promise.all([sayimApi.sayim(id), sayimApi.belgeler(id)])
      .then(([s, b]) => {
        if (iptal) return;
        setSayim(s);
        setBelgeler(b);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Sayım yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [id]);

  const tazele = useCallback(
    (ileti?: string) => {
      if (ileti) snackbar.success(ileti);
      void yukle().catch((e: unknown) => setHata(hataOku(e, "Sayım yüklenemedi.")));
    },
    [snackbar, yukle],
  );

  if (sayim === null) {
    return (
      <div className="space-y-3">
        <Button variant="text" icon="arrow_back" onClick={onGeri}>
          Sayımlara dön
        </Button>
        {hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={4} />}
      </div>
    );
  }

  const durum = sayim.status;
  const ikinci = durum === "IN_PROGRESS" && sayim.round === 2;

  const tamamla = async () => {
    if (bekleyenRef.current > 0) {
      setHata({ message: bekleyenOkutmaIletisi(bekleyenRef.current), parolaGerekli: false });
      return;
    }
    // Onay kutusu açıkken okutma kutusu beklemededir: okutulan kod tampona alınır.
    setTamamlaOnayi(true);
    let onay = false;
    try {
      onay = await confirm({
        title: ikinci ? "İkinci sayım tamamlansın mı?" : "Sayım tamamlansın mı?",
        message: ikinci ? IKINCI_TAMAMLA_METNI : TAMAMLA_METNI,
        confirmLabel: "Tamamla",
      });
    } finally {
      setTamamlaOnayi(false);
    }
    if (!onay) return;
    // Pencere açıkken okutulan kod sıraya girdiyse önce o işlenir; tamamlama başlamaz.
    if (bekleyenRef.current > 0) {
      setHata({ message: bekleyenOkutmaIletisi(bekleyenRef.current), parolaGerekli: false });
      return;
    }
    setBusy(true);
    setHata(null);
    try {
      const sonuc = await sayimApi.tamamla(sayim.id);
      snackbar.success(
        sonuc.second_round
          ? `${formatNumber(sonuc.missing)} nüsha bulunamadı; ikinci sayım başladı.`
          : sonuc.missing > 0
            ? `Sayım tamamlandı: ${formatNumber(sonuc.missing)} noksan.`
            : "Sayım tamamlandı: noksan yok.",
      );
      await yukle();
    } catch (e) {
      setHata(hataOku(e, "Sayım tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Button variant="text" icon="arrow_back" onClick={onGeri}>
        Sayımlara dön
      </Button>

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="text-title-large font-semibold text-on-surface">{sayimAdi(sayim)}</h2>
          <Rozet ton={durum === "APPROVED" ? "ikincil" : "notr"}>
            {ikinci ? "İkinci sayım" : sayim.status_display}
          </Rozet>
        </div>
        <Stepper items={adimlar(sayim)} ariaLabel="Sayım adımları" />
        {durum === "CANCELLED" && (
          <p className="rounded-shape-sm bg-surface-container px-3 py-2 text-body-medium text-on-surface">
            Sayım {formatDate(sayim.cancelled_at)} tarihinde iptal edildi
            {sayim.cancel_reason ? `: ${sayim.cancel_reason}` : "."} Nüshalara dokunulmadı.
          </p>
        )}
        {durum !== "DRAFT" && (
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Bilgi etiket="Mali yıl">{sayim.fiscal_year ?? "—"}</Bilgi>
            <Bilgi etiket="Sayım kurulu">{kurulMetni(sayim) || "—"}</Bilgi>
            <Bilgi etiket="Başlangıç">{formatDateTime(sayim.started_at)}</Bilgi>
            <Bilgi etiket="Tamamlanma">{formatDateTime(sayim.completed_at)}</Bilgi>
            <Bilgi etiket="Harcama yetkilisinin onayı">
              {sayim.approved_on
                ? `${sayim.approved_by_name} · ${formatDate(sayim.approved_on)}`
                : "—"}
            </Bilgi>
          </dl>
        )}
        {durum !== "DRAFT" && (
          <section aria-label="Seçenekler" className="space-y-1">
            <p className="text-label-large text-on-surface">Seçenekler</p>
            <ul className="divide-y divide-outline-variant/50 rounded-shape-md border border-outline-variant/60">
              {sayim.options.map((o) => (
                <li
                  key={o.key}
                  className="flex flex-wrap gap-x-3 gap-y-1 px-3 py-2 text-body-small"
                >
                  <span className="shrink-0 font-semibold text-on-surface sm:w-48">{o.label}</span>
                  <span className="min-w-0 flex-1 text-on-surface">{o.text}</span>
                  {o.key === "tmy_32_3" && sayim.tmy_stop && sayim.locks_active && (
                    <Rozet ton="ucuncul">Sürüyor</Rozet>
                  )}
                  {o.key === "service_pause" && sayim.service_pause && sayim.locks_active && (
                    <Rozet ton="ucuncul">Sürüyor</Rozet>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {hata && <ErrorBand hata={hata} />}

        {(durum === "IN_PROGRESS" || durum === "COMPLETED") && (
          <div className="flex flex-wrap gap-2">
            {durum === "IN_PROGRESS" && (
              <Button
                icon="done_all"
                onClick={() => void tamamla()}
                disabled={busy || bekleyen > 0}
              >
                {ikinci ? "İkinci sayımı tamamla" : "Sayımı tamamla"}
              </Button>
            )}
            {durum === "COMPLETED" && (
              <Button icon="approval" onClick={() => setDiyalog("onay")} disabled={busy}>
                Harcama yetkilisinin onayını işle
              </Button>
            )}
            <Button
              variant="text"
              icon="cancel"
              onClick={() => setDiyalog("iptal")}
              disabled={busy}
            >
              İptal et
            </Button>
          </div>
        )}
        {durum === "DRAFT" && (
          <Button variant="text" icon="cancel" onClick={() => setDiyalog("iptal")} disabled={busy}>
            İptal et
          </Button>
        )}
      </Card>

      {durum === "DRAFT" && (
        <SayimTaslagi
          sayim={sayim}
          onDegisti={(s, ileti) => {
            setSayim(s);
            tazele(ileti);
          }}
          onSilindi={onGeri}
        />
      )}

      {durum === "IN_PROGRESS" && (
        <SayimOkutmasi
          key={`tur-${sayim.round}`}
          sayimId={sayim.id}
          tur={sayim.round}
          beklemede={diyalog !== null || fazlaPenceresi > 0 || tamamlaOnayi}
          onBekleyen={bekleyeniYaz}
          onOkutuldu={(kod) => {
            if (kod === "fazla") setYenile((n) => n + 1);
          }}
        />
      )}

      {durum !== "DRAFT" && (
        <Fazlalar
          sayim={sayim}
          yenile={yenile}
          onDegisti={(ileti) => tazele(ileti)}
          onPencere={fazlaPenceresiDegisti}
        />
      )}

      {(durum === "COMPLETED" || durum === "APPROVED" || durum === "CANCELLED") && (
        <>
          <Sonuclar ozet={sayim.summary} tamam={durum !== "CANCELLED"} />
          <Kalemler
            sayim={sayim}
            varsayilanSonuc={durum === "COMPLETED" ? "MISSING" : ""}
            yenile={yenile}
          />
        </>
      )}

      {durum !== "DRAFT" && belgeler.length > 0 && (
        <Card elevation={0} className="shadow-elevation-1">
          <div className="border-b border-outline-variant/60 px-4 py-3">
            <h2 className="text-title-medium font-semibold text-on-surface">Sayım Belgeleri</h2>
            <p className="text-body-small text-on-surface-variant">
              {`Sayım tutanağının ekinde “${EK_ADI}” (Taşınır Mal Yönetmeliği md. 34/1) yer alır; ödünç alanın kimliği tutanağa yazılmaz. Resmî tutanaklar, Varlık İşlem Fişi ve Taşınır Sayım ve Döküm Cetveli Taşınır Kayıt ve Yönetim Sistemi'nde (TKYS) düzenlenir.`}
            </p>
          </div>
          <ul className="divide-y divide-outline-variant/50">
            {belgeler.map((b) => (
              <BelgeSatiri
                key={b.kind}
                ad={b.title}
                basilabilir={b.available}
                gerekce={b.reason}
                aciklama={
                  durum === "IN_PROGRESS"
                    ? "Sayım sürerken ara döküm olarak basılır (“TASLAK” ibaresiyle)."
                    : durum === "COMPLETED"
                      ? "Kurul ve harcama yetkilisi imzalar; onay imzalı tutanağın tarihiyle işlenir."
                      : undefined
                }
                pdfAl={() => sayimApi.belge(sayim.id, b.kind)}
                excelAl={
                  b.formats.includes("xlsx")
                    ? () => sayimApi.belge(sayim.id, b.kind, "xlsx")
                    : undefined
                }
              />
            ))}
          </ul>
        </Card>
      )}

      {diyalog === "onay" && (
        <OnayDiyalogu
          sayim={sayim}
          onClose={() => setDiyalog(null)}
          onOnaylandi={(sonuc) => {
            setDiyalog(null);
            tazele(
              `Sayım onaylandı: ${formatNumber(
                sonuc.written_off + sonuc.damage_written_off,
              )} nüsha kayıttan düşüldü, ${formatNumber(sonuc.surplus_entered)} fazla kayda alındı.`,
            );
          }}
        />
      )}
      {diyalog === "iptal" && (
        <IptalDiyalogu
          sayimId={sayim.id}
          onClose={() => setDiyalog(null)}
          onIptal={() => {
            setDiyalog(null);
            tazele("Sayım iptal edildi.");
          }}
        />
      )}
    </div>
  );
}
