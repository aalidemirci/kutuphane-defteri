// Gecikmiş Ödünçler (F6; tasarım §9-13, §10 E4; A11). YALNIZ yönetici kipinde açılır:
// görevli kipinde her adreste görevli ekranı durur ve uç da görevli izin listesinde
// değildir (§4.4 "gecikme listesi" kapalı). Menüde yoktur; Genel Bakış'taki
// "Gecikmiş Ödünçler" kartından açılır.
//
// Liste kişi sırasıyladır (sınıf → şube → okul no → ad, sonra personel); kişinin
// bütün gecikmiş ödünçleri alt alta gelir. Uzatma, ceza ve harç YOKTUR; gecikme
// yalnız gün sayısıdır ("… gün gecikti").
//
// İki belge (E4):
// - **İade hatırlatma pusulası**: TEK KİŞİLİK; seçilen kişilerin (seçim yoksa
//   süzgeçteki herkesin) pusulaları, sayfada üç pusula. Kütüphane yöneticisi ya da
//   sınıf rehber öğretmeni dağıtır; sınıfta okunmaz, görevliye dağıttırılmaz.
// - **Gecikmiş ödünç listesi**: toplu liste; her sayfada "Kişisel veri içerir —
//   asılmaz, çoğaltılmaz." dipnotu.

import { useEffect, useState } from "react";

import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Card from "../../ui/Card";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { GECIKME_LISTESI_ADI, LISTE_DIPNOTU, PUSULA_ADI, uyelikApi } from "./api";
import type { OverdueLoanRow } from "./api";
import { subeOku, TD, TH, TumunuSec, useSubeSecenekleri } from "./ortak";

export const GECIKMIS_ODUNCLER_BASLIGI = "Gecikmiş Ödünçler";
export const GECIKMIS_ODUNCLER_ADRESI = "/gecikmis-oduncler";

const PAGE_SIZE = 100;

export default function GecikmisOdunclerPage() {
  const subeler = useSubeSecenekleri();
  const [sube, setSube] = useState("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<OverdueLoanRow>>(emptyPage<OverdueLoanRow>());
  // Seçim ÜYELİK kimliğidir: pusula kişiye basılır, kişinin bütün gecikmeleri gelir.
  const [secim, setSecim] = useState<Set<number>>(new Set());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const kapsam = subeOku(sube);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    const { classLevel, classSection } = subeOku(sube);
    uyelikApi
      .gecikmisOduncler({ classLevel, classSection, limit: PAGE_SIZE, offset })
      .then((s) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(s, offset, PAGE_SIZE);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(s);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Gecikmiş ödünçler yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [sube, offset]);

  const uyeler = [...new Set(sayfa.results.map((s) => s.membership_id))];
  const tarih = formatDate(todayIso());

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{GECIKMIS_ODUNCLER_BASLIGI}</h1>
          <p className="kd-page-description max-w-4xl">
            İade tarihi geçmiş açık ödünçler. Programda uzatma, ceza ve harç yoktur; hatırlatma
            kişiye özel pusulayla yapılır. Bu liste kişisel veri içerir.
          </p>
        </div>
      </div>

      <Card
        elevation={0}
        className="flex flex-wrap items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <Select
          className="w-44"
          label="Şube"
          placeholder="Bütün okul"
          value={sube}
          onChange={(e) => {
            setSube(e.target.value);
            setOffset(0);
            setSecim(new Set());
          }}
          options={subeler}
        />
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() =>
              uyelikApi.pusulaPdf(
                secim.size > 0
                  ? { membershipIds: [...secim] }
                  : { classLevel: kapsam.classLevel, classSection: kapsam.classSection },
              )
            }
            dosyaAdi={() => dosyaAdi([PUSULA_ADI, tarih], "pdf")}
            onizlemeBasligi={PUSULA_ADI}
            disabled={sayfa.count === 0}
            onHata={setHata}
          />
        </div>
      </Card>

      <div className="flex items-start gap-3 rounded-shape-sm bg-surface-container-high px-4 py-3 text-body-medium text-on-surface">
        <Icon name="info" className="mt-0.5 shrink-0" />
        <p>
          {secim.size > 0
            ? `Pusula yalnız seçilen ${formatNumber(secim.size)} kişiye basılır.`
            : "Kişi seçmezseniz pusula süzgeçteki herkese basılır."}{" "}
          Her pusula tek kişiliktir ve katlanınca içeriği görünmez. Kütüphane yöneticisi ya da sınıf
          rehber öğretmeni eliyle verilir; sınıfta okunmaz, öğrenci görevliye dağıttırılmaz.
        </p>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={5} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState icon="event_available" title="Gecikmiş ödünç yok." />
      ) : (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(sayfa.count)} gecikmiş ödünç
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-body-small">
              <caption className="sr-only">Gecikmiş ödünçler</caption>
              <thead>
                <tr className="border-b border-outline-variant">
                  <th className={TH}>
                    <TumunuSec
                      kimlikler={uyeler}
                      secim={secim}
                      onSecim={setSecim}
                      etiket="Bu sayfadaki kişilerin tümünü seç"
                    />
                  </th>
                  <th className={TH}>Ad soyad</th>
                  <th className={TH}>Sınıf / üye türü</th>
                  <th className={TH}>Kaynak adı</th>
                  <th className={TH}>Barkod</th>
                  <th className={TH}>İade tarihi</th>
                  <th className={TH}>Gecikme</th>
                </tr>
              </thead>
              <tbody>
                {sayfa.results.map((s, i) => {
                  const ilk = i === 0 || sayfa.results[i - 1].membership_id !== s.membership_id;
                  return (
                    <tr key={s.id} className="border-t border-outline-variant/50">
                      <td className={TD}>
                        {ilk && (
                          <input
                            type="checkbox"
                            aria-label={`${s.full_name} seç`}
                            checked={secim.has(s.membership_id)}
                            onChange={(e) => {
                              const yeni = new Set(secim);
                              if (e.target.checked) yeni.add(s.membership_id);
                              else yeni.delete(s.membership_id);
                              setSecim(yeni);
                            }}
                            className="size-5 accent-primary"
                          />
                        )}
                      </td>
                      <td className={TD}>{ilk ? s.full_name : ""}</td>
                      <td className={TD}>{ilk ? s.person_label : ""}</td>
                      <td className={TD}>{s.work_title}</td>
                      <td className={`${TD} tabular-nums`}>{s.barcode_display}</td>
                      <td className={TD}>{formatDate(s.due_date)}</td>
                      <td className={TD}>{formatNumber(s.overdue_days)} gün gecikti</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {sayfa.count > PAGE_SIZE && (
            <PaginationBar
              count={sayfa.count}
              offset={offset}
              pageSize={PAGE_SIZE}
              onOffset={setOffset}
            />
          )}
        </Card>
      )}

      <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">{GECIKME_LISTESI_ADI}</p>
        <p className="max-w-3xl text-body-small text-on-surface-variant">
          Süzgeçteki bütün gecikmiş ödünçlerin toplu listesi. Her sayfanın dibinde “{LISTE_DIPNOTU}”
          dipnotu bulunur: liste panoya asılmaz, çoğaltılmaz ve yalnız iade takibi için kullanılır.
        </p>
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() =>
              uyelikApi.gecikmeListesiPdf({
                classLevel: kapsam.classLevel,
                classSection: kapsam.classSection,
              })
            }
            dosyaAdi={() => dosyaAdi([GECIKME_LISTESI_ADI, tarih], "pdf")}
            onizlemeBasligi={GECIKME_LISTESI_ADI}
            disabled={sayfa.count === 0}
            onHata={setHata}
          />
        </div>
      </Card>
    </div>
  );
}
