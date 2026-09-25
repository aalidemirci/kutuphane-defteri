// Eser Ayrıntısı → nüsha penceresindeki "Kayıp, Hasar ve Onarım" bölümü (F7; D3,
// Md. 19, U11). Nüshanın dolaşım dışı durumunu gösterir — açık teslimi (kime, hangi
// belgeyle), çözülmemiş kayıp/hasar dosyası — ve durumuna uygun işlemleri sunar:
//
// | Durum | İşlemler |
// |---|---|
// | Rafta | Onarıma gönder · Hasar dosyası aç · Kayıp bildir |
// | Ödünçte, Sınıf kitaplığında | Kayıp bildir (hasar dosyası iade / geri almadan sonra) |
// | Onarımda | Onarımdan dön · Hasar dosyası aç |
// | Kayıp | — (son dosyanın bağlantısı; öneriyle kapandıysa "Bulundu" orada) |
// | Kayıttan düşülmüş, devredilmiş | — |
//
// Çözülmemiş dosyası olan nüshaya ikinci dosya açılmaz (sunucu da reddeder); onun
// yerine "Dosyayı göster" bağlantısı durur. TEK istisna: çözülmemiş HASAR dosyası olan
// nüsha kaybolursa "Kayıp bildir" durur — kayıp bildirimi hasar dosyasını "Kayba
// dönüştü" ile kapatır (F7 düzeltme turu). "Kayıp" nüshada son dosya (kapanmış da
// olsa) gösterilir: kayıttan düşme önerisiyle kapanmışsa kitap bulununca "Bulundu"
// oradan seçilir. Kayıp ve hasar pencereleri bu pencerenin
// ÜSTÜNE açılmaz: ebeveyn nüsha penceresini kapatıp dosya penceresini açar. Onarım
// onay diyaloğundan geçer (başlık soru, gövde sonuç). Bütün uçlar yönetici kipindedir.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import { hataOku } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Copy, CopyStatus } from "../kutuphane/api";
import { teslimApi } from "../teslim/api";
import type { TeslimSatiri } from "../teslim/api";
import { kayipApi } from "./api";
import type { Dosya, DosyaTuru } from "./api";

export const NUSHA_ISLEMLERI_BASLIGI = "Kayıp, Hasar ve Onarım";

/** Kayıttan düşülmüş ya da devredilmiş nüsha (backend `TERMINAL_COPY_STATUSES`). */
const SON_DURUMLAR: ReadonlySet<CopyStatus> = new Set<CopyStatus>([
  "WITHDRAWN_WEEDED",
  "WITHDRAWN_MISSING",
  "WITHDRAWN_LOST",
  "WITHDRAWN_DAMAGED",
  "TRANSFERRED",
]);

/** Kayıp ve Hasar sayfasında dosyayı doğrudan açan adres. */
export function dosyaAdresi(id: number): string {
  return `/dolasim/kayip-hasar?dosya=${id}`;
}

export default function NushaIslemleri({
  nusha,
  onDosyaAc,
  onDegisti,
}: {
  nusha: Copy;
  /** Kayıp bildirimi ya da hasar dosyası: ebeveyn bu pencereyi kapatıp dosya penceresini açar. */
  onDosyaAc: (tur: DosyaTuru) => void;
  /** Onarım işlendi (liste tazelensin). */
  onDegisti: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [dosya, setDosya] = useState<Dosya | null>(null);
  const [teslim, setTeslim] = useState<TeslimSatiri | null>(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const son = SON_DURUMLAR.has(nusha.status);

  const oku = useCallback(() => {
    let iptal = false;
    if (son) return () => undefined;
    // Kayıp nüshada son dosya (kapanmış da olsa); öbür durumlarda çözülmemiş dosya.
    kayipApi
      .listele({ copy: nusha.id, open: nusha.status !== "LOST", limit: 1 })
      .then((s) => {
        if (!iptal) setDosya(s.results[0] ?? null);
      })
      .catch(() => {
        if (!iptal) setDosya(null);
      });
    if (nusha.status === "DELIVERED") {
      teslimApi
        .listele({ copy: nusha.id, status: "OPEN", limit: 1 })
        .then((s) => {
          if (!iptal) setTeslim(s.results[0] ?? null);
        })
        .catch(() => {
          if (!iptal) setTeslim(null);
        });
    }
    return () => {
      iptal = true;
    };
  }, [nusha.id, nusha.status, son]);

  useEffect(oku, [oku]);

  const onarim = async (yon: "gonder" | "don") => {
    const onay = await confirm(
      yon === "gonder"
        ? {
            title: "Nüsha onarıma gönderilsin mi?",
            message: `${nusha.barcode_display} “Onarımda” olur ve dönene kadar ödünç verilmez. Onarım kaydı yıl sonu raporuna girer.`,
            confirmLabel: "Onarıma gönder",
          }
        : {
            title: "Nüsha onarımdan dönsün mü?",
            message: `${nusha.barcode_display} için onarım kaydı bugünle kapanır ve nüsha rafa döner. Hasar dosyası kendiliğinden kapanmaz; kitap onarıldıysa dosyada “Onarıldı” çözümünü seçin.`,
            confirmLabel: "Onarımdan dön",
          },
    );
    if (!onay) return;
    setHata(null);
    setBusy(true);
    try {
      const sonuc =
        yon === "gonder"
          ? await kayipApi.onarimaGonder(nusha.id)
          : await kayipApi.onarimdanDon(nusha.id);
      snackbar.success(sonuc.message);
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, "Onarım işlenemedi.").message);
    } finally {
      setBusy(false);
    }
  };

  if (son) return null;

  const dosyaYok = dosya === null;
  // Çözülmemiş hasar dosyası kaybı engellemez (kayıp bildirimi onu kayba dönüştürür).
  const kayipBildirilir = dosyaYok || (dosya.is_open && dosya.case_type === "DAMAGED");
  const durum = nusha.status;

  return (
    <section aria-label={NUSHA_ISLEMLERI_BASLIGI} className="space-y-2">
      <p className="text-title-small text-on-surface">{NUSHA_ISLEMLERI_BASLIGI}</p>

      {teslim && (
        <p className="flex items-start gap-2 text-body-medium text-on-surface">
          <Icon name="outbox" size="sm" className="mt-0.5 shrink-0" />
          <span>
            Teslimde — {teslim.recipient_kind_display}: {teslim.recipient_label || "—"} · belge no{" "}
            {teslim.document_no} · teslim {formatDate(teslim.delivered_on)}
          </span>
        </p>
      )}

      {dosya && (
        <p className="flex flex-wrap items-center gap-2 text-body-medium text-on-surface">
          <Icon name="report" size="sm" className="shrink-0" />
          <span>
            {dosya.is_open
              ? `Çözülmemiş ${dosya.case_type_display.toLocaleLowerCase("tr")} dosyası`
              : `${dosya.case_type_display} dosyası`}{" "}
            · tespit {formatDate(dosya.reported_on)} · {dosya.resolution_display}
          </span>
          <Link
            to={dosyaAdresi(dosya.id)}
            className="text-label-large text-primary underline underline-offset-2"
          >
            Dosyayı göster
          </Link>
        </p>
      )}

      {hata && (
        <p role="alert" className="text-body-small text-error">
          {hata}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {durum === "AVAILABLE" && (
          <Button
            variant="outlined"
            icon="build"
            onClick={() => void onarim("gonder")}
            disabled={busy}
          >
            Onarıma gönder
          </Button>
        )}
        {durum === "IN_REPAIR" && (
          <Button
            variant="outlined"
            icon="assignment_return"
            onClick={() => void onarim("don")}
            disabled={busy}
          >
            Onarımdan dön
          </Button>
        )}
        {dosyaYok && (durum === "AVAILABLE" || durum === "IN_REPAIR") && (
          <Button variant="outlined" icon="healing" onClick={() => onDosyaAc("DAMAGED")}>
            Hasar dosyası aç
          </Button>
        )}
        {kayipBildirilir &&
          (durum === "AVAILABLE" || durum === "ON_LOAN" || durum === "DELIVERED") && (
            <Button variant="outlined" icon="report" onClick={() => onDosyaAc("LOST")}>
              Kayıp bildir
            </Button>
          )}
      </div>
    </section>
  );
}
