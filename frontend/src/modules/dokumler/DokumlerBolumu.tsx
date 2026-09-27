// Raporlar → Dökümler (F10 — D kolu): dışa aktarım ve üye özeti (tasarım §8.4), alfabetik
// katalog dökümü (E17 — Md. 11/1), Taşınır Kütüphane Defteri dökümü ve yönetim hesabı cetveli
// hazırlığı (E11 — TMY 9/1-ç, 34/2-c, 34/3-a) ve kişi dökümü (KVKK md. 11).
//
// Bölüm KENDİ BAŞINA durur (Raporlar sayfasına bir bileşen olarak girer). Bütün uçlar
// yönetici kipindedir; görevli kipinde her adreste görevli ekranı durduğu için bu bölüm orada
// hiç çizilmez. Kural ve basılabilirlik SUNUCUDADIR: yönetim hesabı hazırlığının "yalnız yıl
// sonu işaretli ve onaylanmış sayımdan" kuralı ve gerekçesi sunucudan okunur.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { saveBlob } from "../../lib/download";
import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { ExcelDugmesi } from "../ayiklama/ortak";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { DISA_AKTARIM_ICE_AKTARMA_ADRESI } from "../kutuphane/IceAktarmaPage";
import {
  ALFABETIK_KATALOG_ADI,
  BOLUMSUZ,
  BOLUMSUZ_ADI,
  DEFTER_DOKUMU_ADI,
  DISA_AKTARIM_ADI,
  YONETIM_HESABI_ADI,
  dokumDosyaAdi,
  dokumlerApi,
} from "./api";
import type { DokumOzeti, KatalogEkseni, UyeOzeti, YilSonuSayimi } from "./api";
import KisiDokumuKarti from "./KisiDokumuKarti";

/** Kartların açıklamaları (kılavuz aynı cümleleri kullanır). */
export const DISA_AKTARIM_ACIKLAMASI =
  "Kataloğun bütün eserleri ve nüshaları tek Excel dosyasında: barkod, kayıt no, durum, edinim, " +
  "bölüm ve bütün işaretlerle. Kişisel veri içermez. Aynı dosya boş bir kuruluma Katalog → İçe " +
  "Aktarma → “Dışa aktarım dosyası” ile geri yüklenir; barkod ve kayıt no korunur.";
export const ALFABETIK_KATALOG_ACIKLAMASI =
  "“Kataloglar; yazar adı, kaynak adı ve konularına göre alfabetik olarak düzenlenir.” (Okul " +
  "Kütüphaneleri Yönetmeliği Md. 11/1). PDF seçilen ekseni, Excel dosyası üç ekseni ayrı " +
  "sayfalarda taşır. Kayıtta nüshası olan eserler ve dijital kaynaklar girer.";
export const DEFTER_ACIKLAMASI =
  "Her nüsha kayıt no sırasıyla bir satırda (Taşınır Mal Yönetmeliği md. 9/1-ç). Kayıttan " +
  "düşülmüş ve devredilmiş nüsha çıkış tarihiyle kalır. Ciltletilmemiş süreli yayın girmez " +
  "(md. 10/1-a-4, 15/4). Resmî taşınır kaydı Taşınır Kayıt ve Yönetim Sistemi'ndedir (TKYS).";
export const YONETIM_HESABI_ACIKLAMASI =
  "Taşınır mal yönetim hesabının büyüklükleri (md. 34/1) nüsha sayısı ve birim fiyatı kayıtlı " +
  "nüshaların tutarıyla. Sayım kurulunca onaylanan Taşınır Sayım ve Döküm Cetveline dayanır; " +
  "resmî cetveller TKYS'dedir. Yalnız yıl sonu sayımı olarak işaretlenmiş ve onaylanmış sayımdan " +
  "basılır.";
/** E17 bölüm seçicisinin yardımı (bölümsüz eserler yalnız kendi seçeneğinde ve "Bütün bölümler"de). */
export const BOLUM_SECICI_YARDIMI =
  "Büyük koleksiyonda dökümü bölüm bölüm basabilirsiniz; bölümü yazılmamış eserler için " +
  "“Bölümü yazılmamış”ı seçin.";
/** Dışa Aktarım kartındaki geri yükleme bağlantısı (İçe Aktarma → Excel Aktarımı). */
export const DISA_AKTARIM_GERI_YUKLEME = "Dışa aktarım dosyasını içe aktar";
export const YIL_SONU_SAYIMI_YOK =
  "Yıl sonu sayımı olarak işaretlenmiş sayım yok. Katalog → Sayım'da sayımın ayrıntısında " +
  "“Yıl sonu sayımı”nı işaretleyin; hazırlık sayım onaylandıktan sonra basılır.";

const KARTI = "space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1" as const;

function KartBasligi({ baslik, aciklama }: { baslik: string; aciklama: string }) {
  return (
    <div>
      <h2 className="text-title-medium font-semibold text-on-surface">{baslik}</h2>
      <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">{aciklama}</p>
    </div>
  );
}

function DisaAktarimKarti({ ozet, uyeler }: { ozet: DokumOzeti; uyeler: UyeOzeti | null }) {
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const indir = async () => {
    setBusy(true);
    setHata(null);
    try {
      saveBlob(await dokumlerApi.disaAktarim(), dokumDosyaAdi(DISA_AKTARIM_ADI, "xlsx"));
    } catch (e) {
      setHata(hataOku(e, "Dışa aktarım dosyası hazırlanamadı."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card elevation={0} className={KARTI}>
      <KartBasligi baslik="Dışa Aktarım" aciklama={DISA_AKTARIM_ACIKLAMASI} />
      <p className="text-body-medium text-on-surface">
        {`${formatNumber(ozet.export.works)} eser · ${formatNumber(ozet.export.copies)} nüsha kayıtta · ${formatNumber(ozet.export.exited)} nüsha kayıttan düşülmüş ya da devredilmiş`}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Button icon="download" onClick={() => void indir()} disabled={busy}>
          {busy ? "Hazırlanıyor…" : "Dışa aktarım dosyasını indir"}
        </Button>
        {/* Geri yükleme İçe Aktarma'dadır (F10 bağlantısı): Excel Aktarımı dışa aktarım
            dosyası seçili açılır. */}
        <Link
          to={DISA_AKTARIM_ICE_AKTARMA_ADRESI}
          className="text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {DISA_AKTARIM_GERI_YUKLEME}
        </Link>
      </div>
      {hata && <ErrorBand hata={hata} />}
      {uyeler && (
        <section aria-label="Üye Özeti" className="space-y-2">
          <h3 className="text-title-small font-semibold text-on-surface">Üye Özeti</h3>
          <p className="text-body-small text-on-surface-variant">
            Aktif üyelik sayıları — kişisiz. Dışa aktarım dosyasının “Üye Özeti” sayfası da bu
            sayılardır.
          </p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-body-small sm:grid-cols-4">
            {uyeler.by_type.map((t) => (
              <div key={t.member_type} className="flex justify-between gap-2">
                <dt className="text-on-surface-variant">{t.label}</dt>
                <dd className="font-semibold text-on-surface">{formatNumber(t.count)}</dd>
              </div>
            ))}
            <div className="flex justify-between gap-2">
              <dt className="text-on-surface-variant">Toplam</dt>
              <dd className="font-semibold text-on-surface">{formatNumber(uyeler.total)}</dd>
            </div>
          </dl>
          {uyeler.by_class.length > 0 && (
            <dl className="grid grid-cols-3 gap-x-6 gap-y-1 text-body-small sm:grid-cols-6">
              {uyeler.by_class.map((s) => (
                <div key={s.class_label} className="flex justify-between gap-2">
                  <dt className="text-on-surface-variant">{s.class_label}</dt>
                  <dd className="text-on-surface">{formatNumber(s.count)}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      )}
    </Card>
  );
}

function AlfabetikKatalogKarti({ ozet }: { ozet: DokumOzeti }) {
  const [eksen, setEksen] = useState<KatalogEkseni>("title");
  const [bolum, setBolum] = useState("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const bolumNo = bolum ? Number(bolum) : null;
  const ekseninAdi = ozet.catalog_listing.axes.find((a) => a.value === eksen)?.label ?? "";
  return (
    <Card elevation={0} className={KARTI}>
      <KartBasligi baslik="Alfabetik Katalog Dökümü" aciklama={ALFABETIK_KATALOG_ACIKLAMASI} />
      <p className="text-body-medium text-on-surface">
        {`${formatNumber(ozet.catalog_listing.works)} eser · ${formatNumber(ozet.catalog_listing.copies)} nüsha kayıtta`}
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select
          label="Eksen"
          value={eksen}
          onChange={(e) => setEksen(e.target.value as KatalogEkseni)}
          options={ozet.catalog_listing.axes.map((a) => ({ value: a.value, label: a.label }))}
          helperText="PDF bu eksenle basılır."
        />
        <Select
          label="Bölüm"
          value={bolum}
          onChange={(e) => setBolum(e.target.value)}
          options={[
            { value: "", label: "Bütün bölümler" },
            ...ozet.catalog_listing.sections.map((b) => ({ value: String(b.id), label: b.name })),
            // F10 düzeltme turu: bölüm bölüm basan kullanıcı bölümsüz eserleri de basabilsin.
            ...(ozet.catalog_listing.unsectioned_works > 0
              ? [{ value: String(BOLUMSUZ), label: BOLUMSUZ_ADI }]
              : []),
          ]}
          helperText={BOLUM_SECICI_YARDIMI}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <PdfDugmeleri
          pdfAl={() => dokumlerApi.katalogDokumu("pdf", eksen, bolumNo)}
          dosyaAdi={() => dokumDosyaAdi(ALFABETIK_KATALOG_ADI, "pdf", ekseninAdi)}
          onizlemeBasligi={`${ALFABETIK_KATALOG_ADI} — ${ekseninAdi}`}
          onHata={setHata}
        />
        <ExcelDugmesi
          al={() => dokumlerApi.katalogDokumu("xlsx", eksen, bolumNo)}
          dosyaAdi={() => dokumDosyaAdi(ALFABETIK_KATALOG_ADI, "xlsx")}
          onHata={setHata}
        />
      </div>
      {hata && <ErrorBand hata={hata} />}
    </Card>
  );
}

function DefterKarti({ ozet }: { ozet: DokumOzeti }) {
  const [yil, setYil] = useState("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const yilNo = yil ? Number(yil) : null;
  const kapsam = yil ? `${yil} yılında girenler` : undefined;
  return (
    <Card elevation={0} className={KARTI}>
      <KartBasligi baslik="Taşınır Kütüphane Defteri Dökümü" aciklama={DEFTER_ACIKLAMASI} />
      <Select
        className="max-w-xs"
        label="Kapsam"
        value={yil}
        onChange={(e) => setYil(e.target.value)}
        options={[
          { value: "", label: "Bütün kayıt" },
          ...ozet.library_register.years.map((y) => ({
            value: String(y),
            label: `${y} yılında girenler`,
          })),
        ]}
      />
      <div className="flex flex-wrap gap-2">
        <PdfDugmeleri
          pdfAl={() => dokumlerApi.defterDokumu("pdf", yilNo)}
          dosyaAdi={() => dokumDosyaAdi(DEFTER_DOKUMU_ADI, "pdf", kapsam)}
          onizlemeBasligi={DEFTER_DOKUMU_ADI}
          onHata={setHata}
        />
        <ExcelDugmesi
          al={() => dokumlerApi.defterDokumu("xlsx", yilNo)}
          dosyaAdi={() => dokumDosyaAdi(DEFTER_DOKUMU_ADI, "xlsx", kapsam)}
          onHata={setHata}
        />
      </div>
      {hata && <ErrorBand hata={hata} />}
    </Card>
  );
}

function YonetimHesabiSatiri({ sayim }: { sayim: YilSonuSayimi }) {
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const kapsam = sayim.fiscal_year ? String(sayim.fiscal_year) : undefined;
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-body-medium font-semibold text-on-surface">{sayim.name}</p>
          <p className="text-body-small text-on-surface-variant">
            {sayim.available
              ? `Onaylandı · ${formatDate(sayim.approved_on)}`
              : `${sayim.status_display} — ${sayim.reason}`}
          </p>
        </div>
        {sayim.available && (
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={() => dokumlerApi.yonetimHesabi(sayim.id, "pdf")}
              dosyaAdi={() => dokumDosyaAdi(YONETIM_HESABI_ADI, "pdf", kapsam)}
              onizlemeBasligi={YONETIM_HESABI_ADI}
              onHata={setHata}
            />
            <ExcelDugmesi
              al={() => dokumlerApi.yonetimHesabi(sayim.id, "xlsx")}
              dosyaAdi={() => dokumDosyaAdi(YONETIM_HESABI_ADI, "xlsx", kapsam)}
              onHata={setHata}
            />
          </div>
        )}
      </div>
      {hata && <ErrorBand hata={hata} />}
    </li>
  );
}

function YonetimHesabiKarti({ ozet }: { ozet: DokumOzeti }) {
  const sayimlar = ozet.management_account.stocktakes;
  return (
    <Card elevation={0} className="shadow-elevation-1">
      <div className="border-b border-outline-variant/60 px-4 py-3">
        <KartBasligi
          baslik="Yönetim Hesabı Cetveli Hazırlığı"
          aciklama={YONETIM_HESABI_ACIKLAMASI}
        />
      </div>
      {sayimlar.length === 0 ? (
        <p className="px-4 py-3 text-body-medium text-on-surface-variant">{YIL_SONU_SAYIMI_YOK}</p>
      ) : (
        <ul className="divide-y divide-outline-variant/50">
          {sayimlar.map((s) => (
            <YonetimHesabiSatiri key={s.id} sayim={s} />
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function DokumlerBolumu() {
  const [ozet, setOzet] = useState<DokumOzeti | null>(null);
  const [uyeler, setUyeler] = useState<UyeOzeti | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  useEffect(() => {
    let iptal = false;
    Promise.all([dokumlerApi.ozet(), dokumlerApi.uyeOzeti()])
      .then(([o, u]) => {
        if (iptal) return;
        setOzet(o);
        setUyeler(u);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Dökümler yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, []);

  if (ozet === null) {
    return hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={4} />;
  }
  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <DisaAktarimKarti ozet={ozet} uyeler={uyeler} />
      <AlfabetikKatalogKarti ozet={ozet} />
      <DefterKarti ozet={ozet} />
      <YonetimHesabiKarti ozet={ozet} />
      <KisiDokumuKarti />
    </div>
  );
}
