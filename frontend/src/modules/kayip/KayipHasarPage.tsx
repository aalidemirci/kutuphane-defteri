// Kayıp ve Hasar (F7; Yönetmelik Md. 19, tasarım §9-9, D3). YALNIZ yönetici kipinde
// açılır: görevli kipinde her adreste görevli ekranı durur ve dosya uçları görevli
// izin listesinde değildir (§4.4 "kayıp dosyaları" kapalı). Menüde yoktur; Dolaşım
// Masası sayfasının sağ üstündeki "Kayıp ve Hasar" bağlantısıyla açılır.
//
// Sayfa dosyaların listesidir; dosyaya tıklayınca ayrıntı ve çözüm adımları açılır
// (`DosyaAyrintisi`). "Kayıp bildir" ve "Hasar dosyası aç" kitabı okutarak dosya
// açar (`DosyaAcDiyalogu`). `?dosya=<id>` adresi dosyayı doğrudan açar (Eser
// Ayrıntısı'ndaki "Dosyayı göster" bağlantısı).
//
// Program TAHSİLAT YAPMAZ, disiplin süreci başlatmaz; dil "bedel belirlendi", "bedel
// teslim alındı"dır — borç ya da ceza değil (sözlük). Kişi adları sunucuda şifrelidir.
// "Bedel teslim alındı" dosyası "Çözülmemiş dosyalar"da kalır (okulun açık işi) ama
// kişiye yazılmaz; satırında "Okulun açık işi" notu durur.
//
// Md. 19 kademe kapısı sunucudadır: liste yanıtının `price_options_available` alanı
// (liste boşken de gelir) "Çözüm" süzgecindeki bedel yollarını ve açıklamadaki bedel
// cümlesini açar; ilkokul ve ortaokulda ikisi de görünmez. Ekran kademeyi kendisi
// yorumlamaz.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import ModuleHeader from "../../ui/ModuleHeader";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { BEDEL_YOLLARI, COZUM_TR, DOSYA_SAYFA_BOYUTU, DOSYA_TURU_TR, kayipApi } from "./api";
import type { Cozum, Dosya, DosyaTuru } from "./api";
import DosyaAcDiyalogu, {
  HASAR_DUGMESI,
  KAYIP_DUGMESI,
  dosyaAcildiIletisi,
} from "./DosyaAcDiyalogu";
import DosyaAyrintisi from "./DosyaAyrintisi";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const KAYIP_HASAR_BASLIGI = "Kayıp ve Hasar";
export const KAYIP_HASAR_ADRESI = "/dolasim/kayip-hasar";

/**
 * "Bedel teslim alındı" dosyasının satırındaki not: dosya açıktır ama kişinin değil okulun
 * açık işidir (25.09.2026 kullanıcı kararı; sunucunun `is_person_open_work` alanı).
 */
export const OKULUN_ACIK_ISI_ETIKETI = "Okulun açık işi";

/** Görünüm süzgeci: çözülmemiş dosyalar (varsayılan) ya da hepsi. */
type Gorunum = "acik" | "tumu";

export default function KayipHasarPage() {
  const [params, setParams] = useSearchParams();
  const snackbar = useSnackbar();
  const [gorunum, setGorunum] = useState<Gorunum>("acik");
  const [tur, setTur] = useState<DosyaTuru | "">("");
  const [cozum, setCozum] = useState<Cozum | "">("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Dosya>>(emptyPage<Dosya>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [acilan, setAcilan] = useState<DosyaTuru | null>(null);
  const [secili, setSecili] = useState<Dosya | null>(null);
  // Md. 19: bedel seçenekleri sunuluyor mu? (sunucunun yanıtından; yalnız ortaöğretim)
  const [bedelVar, setBedelVar] = useState(false);

  const tazele = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kayipApi
      .listele({
        open: gorunum === "acik",
        caseType: tur,
        resolution: gorunum === "tumu" ? cozum : "",
        limit: DOSYA_SAYFA_BOYUTU,
        offset,
      })
      .then((s) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(s, offset, DOSYA_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(s);
        setBedelVar(s.price_options_available === true);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Kayıp ve hasar dosyaları yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [gorunum, tur, cozum, offset, tazeleme]);

  // `?dosya=<id>`: başka ekrandan gelen bağlantı dosyayı doğrudan açar.
  const dosyaParam = params.get("dosya");
  useEffect(() => {
    const id = Number(dosyaParam);
    if (!dosyaParam || !Number.isInteger(id) || id <= 0) return;
    let iptal = false;
    kayipApi
      .getir(id)
      .then((d) => {
        if (!iptal) setSecili(d);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Dosya bulunamadı."));
      });
    return () => {
      iptal = true;
    };
  }, [dosyaParam]);

  const ayrintiyiKapat = () => {
    setSecili(null);
    if (params.has("dosya")) {
      const yeni = new URLSearchParams(params);
      yeni.delete("dosya");
      setParams(yeni, { replace: true });
    }
  };

  const sutunlar: Column<Dosya>[] = [
    { header: "Barkod", cell: (d) => <span className="font-mono">{d.barcode_display}</span> },
    { header: "Kaynak adı", cell: (d) => d.work_title },
    { header: "Tür", cell: (d) => d.case_type_display },
    {
      header: "Sorumlu",
      cell: (d) =>
        [d.responsible_name, d.responsible_class_label].filter(Boolean).join(" · ") || "—",
    },
    { header: "Tespit tarihi", cell: (d) => formatDate(d.reported_on) },
    {
      header: "Çözüm",
      cell: (d) =>
        d.is_open && !d.is_person_open_work ? (
          <>
            {d.resolution_display}
            <span className="block text-body-small text-on-surface-variant">
              {OKULUN_ACIK_ISI_ETIKETI}
            </span>
          </>
        ) : (
          d.resolution_display
        ),
    },
    { header: "Nüsha durumu", cell: (d) => d.copy_status_display },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader
        backTo="/dolasim"
        moduleLabel="Dolaşım Masası"
        title={KAYIP_HASAR_BASLIGI}
        actions={
          <>
            <Button variant="outlined" icon="healing" onClick={() => setAcilan("DAMAGED")}>
              {HASAR_DUGMESI}
            </Button>
            <Button icon="report" onClick={() => setAcilan("LOST")}>
              {KAYIP_DUGMESI}
            </Button>
          </>
        }
      />

      <p className="kd-page-description max-w-4xl">
        Kaybolan ya da hasar gören kaynakların dosyaları. Kayıp bildirilen kitabın ödüncü ya da
        teslimi kapanır ve dosya çözülene kadar kişinin kütüphaneyle açık işi olarak kalır
        {bedelVar
          ? "; bedel teslim alınınca kişinin açık işi biter, dosya okulun açık işi olarak kalır"
          : ""}
        . Program tahsilat yapmaz
        {bedelVar ? "; piyasa bedeli yalnız kaydedilir (Yönetmelik Md. 19)" : ""}. Kayıttan düşme
        burada yalnız önerilir. Bu liste kişisel veri içerir.
      </p>

      <Card
        elevation={0}
        className="flex flex-wrap items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <Select
          className="w-52"
          label="Görünüm"
          value={gorunum}
          onChange={(e) => {
            setGorunum(e.target.value as Gorunum);
            setOffset(0);
          }}
          options={[
            { value: "acik", label: "Çözülmemiş dosyalar" },
            { value: "tumu", label: "Bütün dosyalar" },
          ]}
        />
        <Select
          className="w-40"
          label="Tür"
          placeholder="Tümü"
          value={tur}
          onChange={(e) => {
            setTur(e.target.value as DosyaTuru | "");
            setOffset(0);
          }}
          options={(Object.keys(DOSYA_TURU_TR) as DosyaTuru[]).map((k) => ({
            value: k,
            label: DOSYA_TURU_TR[k],
          }))}
        />
        {gorunum === "tumu" && (
          <Select
            className="w-60"
            label="Çözüm"
            placeholder="Tümü"
            value={cozum}
            onChange={(e) => {
              setCozum(e.target.value as Cozum | "");
              setOffset(0);
            }}
            options={(Object.keys(COZUM_TR) as Cozum[])
              .filter((k) => bedelVar || !BEDEL_YOLLARI.has(k))
              .map((k) => ({ value: k, label: COZUM_TR[k] }))}
          />
        )}
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="task_alt"
          title={
            gorunum === "acik" ? "Çözülmemiş kayıp ya da hasar dosyası yok." : "Dosya bulunamadı."
          }
        />
      ) : (
        <div className="space-y-2">
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(sayfa.count)} dosya
          </p>
          <DataTable<Dosya>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(d) => setSecili(d)}
            rowLabel={(d) => `${d.barcode_display} numaralı nüshanın dosyasını aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={DOSYA_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </div>
      )}

      <DosyaAcDiyalogu
        open={acilan !== null}
        tur={acilan ?? "LOST"}
        onClose={() => setAcilan(null)}
        onAcildi={(d) => {
          snackbar.success(dosyaAcildiIletisi(d.case_type));
          setAcilan(null);
          tazele();
          setSecili(d);
        }}
      />

      {secili !== null && (
        <DosyaAyrintisi dosya={secili} onClose={ayrintiyiKapat} onDegisti={() => tazele()} />
      )}
    </div>
  );
}
