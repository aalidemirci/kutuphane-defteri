// Teslimler → Teslim Kayıtları (U11, tasarım §9-11). Açık teslimler varsayılandır;
// geri alınan ve kayba dönüşen teslimler süzgeçle görülür. YALNIZ yönetici kipinde
// (liste uçları görevli izin listesinde değildir; öğretmen adı kişi verisidir).
//
// Beklenen dönüşü geçen teslim GECİKME DEĞİLDİR (teslim ödünç değildir): satırda
// yalnız bilgi rozeti durur, ceza ya da hatırlatma dili yoktur.
//
// Belge no'ya tıklanınca liste o belgeye süzülür ve o belgenin Teslim listesi ile Geri
// alma dökümü (E15) basılır. Döküm belgenin BÜTÜN satırlarını durumlarıyla yazar
// (geri alındı · teslimde · kayba dönüştü): geri alma görevli kipinde, masada ya da
// başka bir oturumda yapılmış olsa da döküm buradan alınır. Açık teslimdeki kitap
// kaybolduysa "Kayıp bildir" teslimi "Kayba dönüştü" ile kapatır
// (`kayip/DosyaAcDiyalogu`).

import { useEffect, useState } from "react";

import { formatDate, formatNumber } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import DosyaAcDiyalogu from "../kayip/DosyaAcDiyalogu";
import type { SeciliNusha } from "../kayip/DosyaAcDiyalogu";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { TD, TH } from "../uyelik/ortak";
import {
  GERI_ALMA_DOKUMU_ADI,
  TESLIM_ALAN_TURU_TR,
  TESLIM_DURUMU_TR,
  TESLIM_LISTESI_ADI,
  TESLIM_SAYFA_BOYUTU,
  teslimApi,
} from "./api";
import type { TeslimAlanTuru, TeslimDurumu, TeslimSatiri } from "./api";
import { belgeDosyaAdi, dokumDosyaAdi } from "./YeniTeslim";

export const BEKLENEN_DONUS_GECTI = "beklenen dönüş geçti";

export default function TeslimKayitlari({ tazeleme = 0 }: { tazeleme?: number }) {
  const snackbar = useSnackbar();
  const [durum, setDurum] = useState<TeslimDurumu | "">("OPEN");
  const [alanTuru, setAlanTuru] = useState<TeslimAlanTuru | "">("");
  const [belgeNo, setBelgeNo] = useState("");
  const [arananBelge, setArananBelge] = useState("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<TeslimSatiri>>(emptyPage<TeslimSatiri>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [icTazeleme, setIcTazeleme] = useState(0);
  const [kayipNushasi, setKayipNushasi] = useState<SeciliNusha | null>(null);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    teslimApi
      .listele({
        status: durum,
        recipientKind: alanTuru,
        documentNo: arananBelge,
        limit: TESLIM_SAYFA_BOYUTU,
        offset,
      })
      .then((s) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(s, offset, TESLIM_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(s);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Teslimler yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [durum, alanTuru, arananBelge, offset, tazeleme, icTazeleme]);

  const belgeyeSuz = (no: string) => {
    setBelgeNo(no);
    setArananBelge(no);
    setDurum("");
    setOffset(0);
  };

  const ilkSatir = sayfa.results[0];

  return (
    <div className="space-y-4">
      <Card
        elevation={0}
        className="flex flex-wrap items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <Select
          className="w-44"
          label="Durum"
          placeholder="Tümü"
          value={durum}
          onChange={(e) => {
            setDurum(e.target.value as TeslimDurumu | "");
            setOffset(0);
          }}
          options={(Object.keys(TESLIM_DURUMU_TR) as TeslimDurumu[]).map((k) => ({
            value: k,
            label: TESLIM_DURUMU_TR[k],
          }))}
        />
        <Select
          className="w-44"
          label="Teslim alan"
          placeholder="Tümü"
          value={alanTuru}
          onChange={(e) => {
            setAlanTuru(e.target.value as TeslimAlanTuru | "");
            setOffset(0);
          }}
          options={(Object.keys(TESLIM_ALAN_TURU_TR) as TeslimAlanTuru[]).map((k) => ({
            value: k,
            label: TESLIM_ALAN_TURU_TR[k],
          }))}
        />
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setArananBelge(belgeNo.trim());
            setOffset(0);
          }}
        >
          <TextField
            className="w-40"
            label="Belge no"
            value={belgeNo}
            onChange={(e) => setBelgeNo(e.target.value)}
            placeholder="2026/1"
          />
          <Button type="submit" variant="tonal" icon="search">
            Ara
          </Button>
          {arananBelge && (
            <Button
              type="button"
              variant="text"
              onClick={() => {
                setBelgeNo("");
                setArananBelge("");
                setOffset(0);
              }}
            >
              Temizle
            </Button>
          )}
        </form>
      </Card>

      {arananBelge && ilkSatir && (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-title-medium text-on-surface">
            {TESLIM_LISTESI_ADI} — belge no {arananBelge}
          </p>
          <p className="text-body-small text-on-surface-variant">
            {ilkSatir.recipient_kind_display}: {ilkSatir.recipient_label || "—"} · teslim{" "}
            {formatDate(ilkSatir.delivered_on)}
          </p>
          <section aria-label={TESLIM_LISTESI_ADI} className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={() => teslimApi.teslimListesiPdf(arananBelge)}
              dosyaAdi={() => belgeDosyaAdi(arananBelge, ilkSatir.delivered_on)}
              onizlemeBasligi={TESLIM_LISTESI_ADI}
              onHata={setHata}
            />
          </section>
          <section aria-label={GERI_ALMA_DOKUMU_ADI} className="space-y-2 pt-2">
            <p className="text-title-small text-on-surface">{GERI_ALMA_DOKUMU_ADI}</p>
            <p className="max-w-3xl text-body-small text-on-surface-variant">
              Belgenin bütün kitapları durumlarıyla: geri alındı, teslimde ya da kayba dönüştü. Geri
              alma görevli kipinde ya da masada yapılmış olsa da döküm buradan basılır.
            </p>
            <div className="flex flex-wrap gap-2">
              <PdfDugmeleri
                pdfAl={() => teslimApi.geriAlmaDokumuPdf({ documentNo: arananBelge })}
                dosyaAdi={() => dokumDosyaAdi(arananBelge)}
                onizlemeBasligi={GERI_ALMA_DOKUMU_ADI}
                onHata={setHata}
              />
            </div>
          </section>
        </Card>
      )}

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="outbox"
          title={durum === "OPEN" && !arananBelge ? "Açık teslim yok." : "Teslim bulunamadı."}
        />
      ) : (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(sayfa.count)} teslim satırı
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-body-small">
              <caption className="sr-only">Teslimler</caption>
              <thead>
                <tr className="border-b border-outline-variant">
                  <th className={TH}>Belge no</th>
                  <th className={TH}>Teslim alan</th>
                  <th className={TH}>Barkod</th>
                  <th className={TH}>Kaynak adı</th>
                  <th className={TH}>Teslim tarihi</th>
                  <th className={TH}>Beklenen dönüş</th>
                  <th className={TH}>Durum</th>
                  <th className={TH}>
                    <span className="sr-only">İşlem</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sayfa.results.map((s) => (
                  <tr key={s.id} className="border-t border-outline-variant/50">
                    <td className={TD}>
                      <button
                        type="button"
                        className="text-primary underline underline-offset-2"
                        onClick={() => belgeyeSuz(s.document_no)}
                        aria-label={`Belge no ${s.document_no} satırlarını göster`}
                      >
                        {s.document_no}
                      </button>
                    </td>
                    <td className={TD}>
                      {s.recipient_kind_display}: {s.recipient_label || "—"}
                    </td>
                    <td className={`${TD} font-mono`}>{s.barcode_display}</td>
                    <td className={TD}>{s.work_title}</td>
                    <td className={TD}>{formatDate(s.delivered_on)}</td>
                    <td className={TD}>
                      {formatDate(s.expected_return)}
                      {s.expected_return_passed && (
                        <span className="ml-2 rounded-full bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
                          {BEKLENEN_DONUS_GECTI}
                        </span>
                      )}
                    </td>
                    <td className={TD}>
                      {s.status_display}
                      {s.returned_at && ` · ${formatDate(s.returned_at.slice(0, 10))}`}
                    </td>
                    <td className={TD}>
                      {s.status === "OPEN" && (
                        <Button
                          variant="text"
                          icon="report"
                          onClick={() =>
                            setKayipNushasi({
                              id: s.copy,
                              barcode: s.barcode,
                              barcode_display: s.barcode_display,
                              work_title: s.work_title,
                            })
                          }
                          aria-label={`${s.barcode_display} için kayıp bildir`}
                        >
                          Kayıp bildir
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={TESLIM_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </Card>
      )}

      <DosyaAcDiyalogu
        open={kayipNushasi !== null}
        tur="LOST"
        nusha={kayipNushasi}
        onClose={() => setKayipNushasi(null)}
        onAcildi={() => {
          snackbar.success("Kayıp bildirildi; teslim kayba dönüştü ve kayıp dosyası açıldı.");
          setKayipNushasi(null);
          setIcTazeleme((k) => k + 1);
        }}
      />
    </div>
  );
}
