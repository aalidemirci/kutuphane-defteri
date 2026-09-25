// İlişik Listesi (F7; tasarım §8.3, §9-8, §10 E5). YALNIZ yönetici kipinde açılır:
// görevli kipinde her adreste görevli ekranı durur ve uçlar görevli izin listesinde
// değildir (§4.4 "ilişik" kapalı). Menüde yoktur; Genel Bakış'taki "İlişik Listesi"
// kartından açılır.
//
// Liste kütüphaneyle açık işi olan kişilerdir: iade edilmemiş ödünç, geri alınmamış
// teslim ve çözülmemiş kayıp/hasar dosyası; okuldan AYRILMIŞ kişiler dahil. Son
// sınıflar ve okuldan ayrılanlar önce gelir. Sınıf kitaplıkları (şube teslimleri)
// kişisizdir, ayrı kartta durur.
//
// İki belge (E5):
// - **İlişik listesi**: toplu liste; her sayfada "Kişisel veri içerir — asılmaz,
//   çoğaltılmaz." dipnotu; kaynak adı basılmaz (yalnız barkod).
// - **"Kütüphaneden ilişiği yoktur" belgesi**: kişi başına bir sayfa; yalnız açık
//   işi olmayan kişiye basılır. Belge okulun yerel kayıtlarına dayanır; başka bir
//   işlemin ön koşulu diye sunulmaz (tasarım §8.3 — dayanağı yok).

import { useEffect, useState } from "react";

import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
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
import TextField from "../../ui/TextField";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { subeOku, useSubeSecenekleri } from "../uyelik/ortak";
import {
  ILISIK_BELGESI_ADI,
  ILISIK_LISTESI_ADI,
  ILISIK_LISTESI_BASLIGI,
  KAPSAM_SECENEKLERI,
  LISTE_DIPNOTU,
  YIL_BASI_ADRESI,
  YIL_SONU_ADRESI,
  yilApi,
} from "./api";
import type { IlisikKapsami, IlisikSatiri } from "./api";
import { IlisikTablosu, SinifKitapliklari, secimiAyir, YanEkranBaglantilari } from "./ortak";

const PAGE_SIZE = 50;

export default function IlisikListesiPage() {
  const subeler = useSubeSecenekleri();
  const [kapsam, setKapsam] = useState<IlisikKapsami>("");
  const [sube, setSube] = useState("");
  const [arama, setArama] = useState("");
  const [aranan, setAranan] = useState("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<IlisikSatiri>>(emptyPage<IlisikSatiri>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const secilenSube = subeOku(sube);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    const { classLevel, classSection } = subeOku(sube);
    yilApi
      .ilisikListesi({
        group: kapsam,
        classLevel,
        classSection,
        search: aranan,
        limit: PAGE_SIZE,
        offset,
      })
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
        if (!iptal) setHata(hataOku(e, "İlişik listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [kapsam, sube, aranan, offset]);

  const tarih = formatDate(todayIso());

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{ILISIK_LISTESI_BASLIGI}</h1>
          <p className="kd-page-description max-w-4xl">
            Kütüphaneden iade edilmemiş kaynağı, geri alınmamış teslimi ya da çözülmemiş kayıp/hasar
            dosyası olan kişiler; okuldan ayrılanlar dahil. Son sınıflar ve okuldan ayrılanlar önce
            gelir. Bu liste kişisel veri içerir.
          </p>
        </div>
        <YanEkranBaglantilari
          baglantilar={[
            { to: YIL_SONU_ADRESI, label: "Yıl Sonu", icon: "event_upcoming" },
            { to: YIL_BASI_ADRESI, label: "Yıl Başı", icon: "event_available" },
          ]}
        />
      </div>

      <Card
        elevation={0}
        className="flex flex-wrap items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <Select
          className="w-64"
          label="Kapsam"
          value={kapsam}
          onChange={(e) => {
            setKapsam(e.target.value as IlisikKapsami);
            setOffset(0);
          }}
          options={KAPSAM_SECENEKLERI}
        />
        <Select
          className="w-44"
          label="Şube"
          placeholder="Bütün okul"
          value={sube}
          onChange={(e) => {
            setSube(e.target.value);
            setOffset(0);
          }}
          options={subeler}
        />
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setAranan(arama.trim());
            setOffset(0);
          }}
        >
          <TextField
            className="w-64"
            label="Ara"
            placeholder="Ad soyad ya da okul no…"
            helperText="Okul no tam yazılarak aranır."
            value={arama}
            onChange={(e) => setArama(e.target.value)}
          />
          <Button type="submit" variant="tonal" icon="search">
            Ara
          </Button>
        </form>
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={5} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="task_alt"
          title="Bu seçimde kütüphaneyle açık işi olan kişi yok."
          description="Açık işi olmayan kişiye aşağıdan “Kütüphaneden ilişiği yoktur” belgesi basılabilir."
        />
      ) : (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(sayfa.count)} kişi
          </p>
          <IlisikTablosu satirlar={sayfa.results} baslik="İlişik listesi" />
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

      <SinifKitapliklari onHata={setHata} />

      <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">{ILISIK_LISTESI_ADI}</p>
        <p className="max-w-3xl text-body-small text-on-surface-variant">
          Süzgeçteki kişilerin toplu listesi; sınıf kitaplıkları ayrı tabloda. Listede kaynak adı
          yoktur, yalnız barkod ve tarih vardır. Her sayfanın dibinde “{LISTE_DIPNOTU}” dipnotu
          bulunur.
        </p>
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() =>
              yilApi.ilisikListesiPdf({
                group: kapsam,
                classLevel: secilenSube.classLevel,
                classSection: secilenSube.classSection,
              })
            }
            dosyaAdi={() => dosyaAdi([ILISIK_LISTESI_ADI, tarih], "pdf")}
            onizlemeBasligi={ILISIK_LISTESI_ADI}
            onHata={setHata}
          />
        </div>
      </Card>

      <IlisikBelgesiKarti />
    </div>
  );
}

/**
 * "Kütüphaneden ilişiği yoktur" belgesi: kişi aranır, açık işi olmayanlar seçilir.
 * Açık işi olan kişi seçilemez; sunucu da reddeder (kişi adı yazmadan).
 */
export function IlisikBelgesiKarti() {
  const [arama, setArama] = useState("");
  const [sonuclar, setSonuclar] = useState<IlisikSatiri[] | null>(null);
  const [secim, setSecim] = useState<Set<string>>(new Set());
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);

  const ara = async () => {
    const metin = arama.trim();
    if (!metin) return;
    setMesgul(true);
    setHata(null);
    try {
      const s = await yilApi.ilisikListesi({ state: "all", search: metin, limit: 50 });
      setSonuclar(s.results);
      setSecim(new Set());
    } catch (e) {
      setHata(hataOku(e, "Kişi aranamadı."));
    } finally {
      setMesgul(false);
    }
  };

  const tarih = formatDate(todayIso());
  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="text-title-medium text-on-surface">{ILISIK_BELGESI_ADI}</p>
      <p className="max-w-3xl text-body-small text-on-surface-variant">
        Kütüphanenin kayıtlarına göre açık işi olmayan kişiye kişi başına bir sayfa basılır. Belge
        okulun yerel kayıtlarına dayanır; Bakanlık otomasyon sistemindeki kaydın yerine geçmez.
      </p>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ara();
        }}
      >
        <TextField
          className="w-72"
          label="Kişi"
          placeholder="Ad soyad ya da okul no…"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
        />
        <Button type="submit" variant="tonal" icon="search" disabled={mesgul || !arama.trim()}>
          Ara
        </Button>
      </form>
      {hata && <ErrorBand hata={hata} />}
      {sonuclar !== null &&
        (sonuclar.length === 0 ? (
          <EmptyState compact icon="person_search" title="Bu aramayla kişi bulunamadı." />
        ) : (
          <>
            <IlisikTablosu
              satirlar={sonuclar}
              secim={secim}
              onSecim={setSecim}
              secilebilir={(s) => s.is_clear}
              baslik="Belge için arama sonuçları"
            />
            <div className="flex flex-wrap gap-2">
              <PdfDugmeleri
                pdfAl={() => yilApi.ilisikBelgesiPdf(secimiAyir(secim))}
                dosyaAdi={() => dosyaAdi([ILISIK_BELGESI_ADI, tarih], "pdf")}
                onizlemeBasligi={ILISIK_BELGESI_ADI}
                disabled={secim.size === 0}
                onHata={setHata}
              />
            </div>
          </>
        ))}
    </Card>
  );
}
