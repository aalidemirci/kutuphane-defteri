// Etiketler → Şablonlar ve Kalibrasyon (tasarım §7.2, E1).
//
// Şablon, tabakanın ÖLÇÜSÜDÜR (kenar boşlukları, etiket boyu, satır × sütun,
// aralıklar); program ilk açılışta dört hazır şablon yazar ve kullanıcı onları
// düzenleyebilir. Yazıcının kaydırması şablonda DEĞİL kalibrasyondadır: aynı
// tabaka iki yazıcıda farklı kayar, kalibrasyon şablon + yazıcı çiftiyle saklanır.
//
// Kalibrasyon akışı (kalibrasyon sayfasının kendi talimatıyla aynı dil):
//   1. Şablonu seç, kalibrasyon sayfasını indir ve GERÇEK BOYUTTA (%100) yazdır;
//      sayfadaki 100 mm'lik çizgi ölçeği denetletir.
//   2. Çıktıyı etiket tabakasının üstüne koyup ışığa tut (ya da doğrudan tabakaya
//      bas); köşe etiketlerindeki cetvelde etiketin gerçek kenarının düştüğü
//      değeri oku.
//   3. Okunan değeri kaymaya ekle (sağa ve aşağı artı) ve kaydet; sayfayı o
//      yazıcının kaymasıyla yeniden basıp doğrula.

import { useState } from "react";

import { formatDateTime, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import { useFormErrors } from "../../hooks/useFormErrors";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import {
  EN_COK_KAYMA_MM,
  KALIBRASYON_BELGE_ADI,
  SABLON_TURU_TR,
  etiketApi,
  kalibrasyonDosyaAdi,
} from "./etiketApi";
import type {
  EtiketSablonu,
  EtiketSablonuGovdesi,
  SablonTuru,
  YaziciKalibrasyonu,
} from "./etiketApi";
import {
  PdfDugmeleri,
  kalibrasyonEtiketi,
  mm,
  ondalikOku,
  sablonOlcusu,
  useKalibrasyonlar,
} from "./etiketOrtak";
import { kodSecenekleri } from "./ortak";

export default function SablonlarPaneli({
  sablonlar,
  yukleniyor,
  onDegisti,
}: {
  sablonlar: EtiketSablonu[];
  yukleniyor: boolean;
  /** Şablon eklendi, düzenlendi ya da silindi: liste yeniden okunur. */
  onDegisti: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [seciliId, setSeciliId] = useState<number | null>(null);
  const [form, setForm] = useState<EtiketSablonu | "yeni" | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const secili = sablonlar.find((s) => s.id === seciliId) ?? sablonlar[0] ?? null;

  const sil = async (sablon: EtiketSablonu) => {
    const tamam = await confirm({
      title: `“${sablon.name}” silinsin mi?`,
      message:
        "Şablonun yazıcı kalibrasyonları da silinir. Bu şablonla hazırlanıp henüz basıldı " +
        "olarak işaretlenmemiş partiler yeniden basılamaz; geçmişteki partilerin kaydı kalır.",
      confirmLabel: "Sil",
    });
    if (!tamam) return;
    setHata(null);
    try {
      await etiketApi.sablonSil(sablon.id);
      snackbar.success("Şablon silindi.");
      if (seciliId === sablon.id) setSeciliId(null);
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, "Şablon silinemedi."));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-4xl text-body-medium text-on-surface-variant">
          Şablon, etiket tabakasının ölçüsüdür. Hazır şablonlar yaygın tabakalardandır; kendi
          tabakanızın ölçüsü farklıysa kutusundaki ölçülerle yeni şablon tanımlayın. Yazıcının
          kaydırması şablona değil yazıcı kalibrasyonuna yazılır: ilk basımdan önce her yazıcı için
          kalibrasyon sayfası basın.
        </p>
        <Button icon="add" onClick={() => setForm("yeni")}>
          Yeni şablon
        </Button>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor && sablonlar.length === 0 ? (
        <SkeletonList rows={4} />
      ) : sablonlar.length === 0 ? (
        <EmptyState
          icon="straighten"
          title="Etiket şablonu yok."
          description="Etiket basmak için tabakanızın ölçüleriyle bir şablon tanımlayın."
          action={
            <Button icon="add" onClick={() => setForm("yeni")}>
              Yeni şablon
            </Button>
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {sablonlar.map((s) => (
            <li key={s.id}>
              <Card
                elevation={0}
                className={`space-y-2 p-4 shadow-elevation-1 ${
                  secili?.id === s.id ? "border-primary/60" : ""
                }`}
              >
                <p className="text-title-small font-semibold text-on-surface">{s.name}</p>
                <p className="text-body-small text-on-surface-variant">
                  {s.kind_display} · {sablonOlcusu(s)}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {s.is_default && <Rozet ikon="star">Varsayılan</Rozet>}
                  {s.supports_qr && <Rozet ikon="qr_code_2">QR'a uygun</Rozet>}
                  {s.kind === "BARCODE" && !s.supports_barcode && (
                    <Rozet ikon="warning">Barkod bu etikete sığmaz</Rozet>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={secili?.id === s.id ? "tonal" : "outlined"}
                    icon="straighten"
                    onClick={() => setSeciliId(s.id)}
                    aria-pressed={secili?.id === s.id}
                  >
                    Kalibrasyon
                  </Button>
                  <Button variant="text" icon="edit" onClick={() => setForm(s)}>
                    Düzenle
                  </Button>
                  <Button variant="text" icon="delete" onClick={() => void sil(s)}>
                    Sil
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {secili && <KalibrasyonPaneli key={secili.id} sablon={secili} />}

      {form !== null && (
        <SablonFormu
          sablon={form === "yeni" ? null : form}
          onKapat={() => setForm(null)}
          onKaydedildi={() => {
            setForm(null);
            onDegisti();
          }}
        />
      )}
    </div>
  );
}

function Rozet({ ikon, children }: { ikon: string; children: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-container-high px-2 py-0.5 text-label-medium text-on-surface-variant">
      <Icon name={ikon} size="sm" />
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Kalibrasyon
// ---------------------------------------------------------------------------

function KalibrasyonPaneli({ sablon }: { sablon: EtiketSablonu }) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [tazeleme, setTazeleme] = useState(0);
  const { kalibrasyonlar } = useKalibrasyonlar(sablon.id, tazeleme);
  const [sayfaKalibrasyonu, setSayfaKalibrasyonu] = useState("");
  const [form, setForm] = useState<YaziciKalibrasyonu | "yeni" | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const sil = async (k: YaziciKalibrasyonu) => {
    const tamam = await confirm({
      title: `“${k.printer_name}” kalibrasyonu silinsin mi?`,
      message: "Bu yazıcıyla bu şablona basılan etiketler bundan sonra kaymasız basılır.",
      confirmLabel: "Sil",
    });
    if (!tamam) return;
    setHata(null);
    try {
      await etiketApi.kalibrasyonSil(k.id);
      snackbar.success("Kalibrasyon silindi.");
      if (sayfaKalibrasyonu === String(k.id)) setSayfaKalibrasyonu("");
      setTazeleme((n) => n + 1);
    } catch (e) {
      setHata(hataOku(e, "Kalibrasyon silinemedi."));
    }
  };

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="text-title-medium text-on-surface">Yazıcı Kalibrasyonu: {sablon.name}</p>
      <ol className="list-decimal space-y-1 pl-5 text-body-medium text-on-surface-variant">
        <li>
          Kalibrasyon sayfasını indirip düz kâğıda <strong>gerçek boyutta (%100)</strong> yazdırın;
          sayfadaki çizgi 100 mm olmalıdır. Yazdırma penceresinde “sayfaya sığdır” seçiliyse
          kapatın.
        </li>
        <li>
          Çıktıyı etiket tabakasının üstüne koyup ışığa tutun. Köşe etiketlerindeki cetvelde,
          etiketin gerçek kenarının düştüğü değeri okuyun.
        </li>
        <li>
          Okuduğunuz değeri o yazıcının kaymasına ekleyin (sağa ve aşağı artı) ve kaydedin. Sayfayı
          o yazıcının kaymasıyla yeniden basıp kenarların sıfıra oturduğunu doğrulayın.
        </li>
      </ol>
      <p className="text-body-small text-on-surface-variant">
        Dört köşede okunan değer aynı değilse sorun kayma değil ölçektir: yazıcı sayfayı küçültüyor
        ya da büyütüyordur.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <Select
          className="min-w-[18rem]"
          label="Sayfaya uygulanacak kayma"
          placeholder="— yok —"
          value={sayfaKalibrasyonu}
          onChange={(e) => setSayfaKalibrasyonu(e.target.value)}
          options={kalibrasyonlar.map((k) => ({
            value: String(k.id),
            label: kalibrasyonEtiketi(k),
          }))}
          helperText="İlk ölçümde kaymasız basın; doğrulamada yazıcıyı seçin."
        />
        <PdfDugmeleri
          pdfAl={() =>
            etiketApi.kalibrasyonSayfasi(
              sablon.id,
              sayfaKalibrasyonu ? Number(sayfaKalibrasyonu) : null,
            )
          }
          dosyaAdi={kalibrasyonDosyaAdi}
          onizlemeBasligi={KALIBRASYON_BELGE_ADI}
          onHata={setHata}
        />
      </div>

      {hata && <ErrorBand hata={hata} />}

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-title-small font-semibold text-on-surface">Kayıtlı yazıcılar</p>
          <Button variant="outlined" icon="add" onClick={() => setForm("yeni")}>
            Yeni yazıcı kalibrasyonu
          </Button>
        </div>
        {kalibrasyonlar.length === 0 ? (
          <EmptyState
            compact
            icon="print"
            title="Bu şablon için kayıtlı yazıcı yok; etiketler kaymasız basılır."
          />
        ) : (
          <ul className="divide-y divide-outline-variant/60 rounded-shape-sm border border-outline-variant/70">
            {kalibrasyonlar.map((k) => (
              <li
                key={k.id}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
              >
                <span className="text-body-medium text-on-surface">
                  {k.printer_name}
                  <span className="block text-body-small text-on-surface-variant">
                    Yatay {mm(k.offset_x)} mm · dikey {mm(k.offset_y)} mm · güncellendi{" "}
                    {formatDateTime(k.updated_at)}
                  </span>
                </span>
                <span className="flex gap-1">
                  <Button variant="text" icon="edit" onClick={() => setForm(k)}>
                    Düzenle
                  </Button>
                  <Button variant="text" icon="delete" onClick={() => void sil(k)}>
                    Sil
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {form !== null && (
        <KalibrasyonFormu
          sablon={sablon}
          kalibrasyon={form === "yeni" ? null : form}
          onKapat={() => setForm(null)}
          onKaydedildi={(kayit) => {
            setForm(null);
            setSayfaKalibrasyonu(String(kayit.id));
            setTazeleme((n) => n + 1);
          }}
        />
      )}
    </Card>
  );
}

/** Kayma alanı (mm, ±10): virgül de nokta da kabul edilir. */
function kaymaOku(girdi: string): number | null {
  const deger = ondalikOku(girdi === "" ? "0" : girdi);
  if (deger === null || Math.abs(deger) > EN_COK_KAYMA_MM) return null;
  return Math.round(deger * 100) / 100;
}

function sayiYazimi(deger: number): string {
  return String(deger).replace(".", ",");
}

function KalibrasyonFormu({
  sablon,
  kalibrasyon,
  onKapat,
  onKaydedildi,
}: {
  sablon: EtiketSablonu;
  kalibrasyon: YaziciKalibrasyonu | null;
  onKapat: () => void;
  onKaydedildi: (kayit: YaziciKalibrasyonu) => void;
}) {
  const snackbar = useSnackbar();
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const [yazici, setYazici] = useState(kalibrasyon?.printer_name ?? "");
  const [x, setX] = useState(kalibrasyon ? sayiYazimi(kalibrasyon.offset_x) : "0");
  const [y, setY] = useState(kalibrasyon ? sayiYazimi(kalibrasyon.offset_y) : "0");
  const [olcumX, setOlcumX] = useState("");
  const [olcumY, setOlcumY] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const ekle = () => {
    clearErrors();
    const mevcutX = kaymaOku(x) ?? 0;
    const mevcutY = kaymaOku(y) ?? 0;
    const eklenecekX = olcumX.trim() ? ondalikOku(olcumX) : 0;
    const eklenecekY = olcumY.trim() ? ondalikOku(olcumY) : 0;
    if (eklenecekX === null) {
      setFieldError("olcum_x", "Sayı yazın (ör. 1,5 ya da -0,5).");
      return;
    }
    if (eklenecekY === null) {
      setFieldError("olcum_y", "Sayı yazın (ör. 1,5 ya da -0,5).");
      return;
    }
    setX(sayiYazimi(Math.round((mevcutX + eklenecekX) * 100) / 100));
    setY(sayiYazimi(Math.round((mevcutY + eklenecekY) * 100) / 100));
    setOlcumX("");
    setOlcumY("");
  };

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    if (!yazici.trim()) {
      setFieldError("printer_name", "Yazıcının adını yazın.");
      return;
    }
    const kaymaX = kaymaOku(x);
    const kaymaY = kaymaOku(y);
    const sinirIletisi = `-${EN_COK_KAYMA_MM} ile ${EN_COK_KAYMA_MM} mm arasında bir sayı yazın.`;
    if (kaymaX === null) {
      setFieldError("offset_x", sinirIletisi);
      return;
    }
    if (kaymaY === null) {
      setFieldError("offset_y", sinirIletisi);
      return;
    }
    setBusy(true);
    try {
      const govde = {
        template: sablon.id,
        printer_name: yazici.trim(),
        offset_x: kaymaX,
        offset_y: kaymaY,
      };
      const kayit =
        kalibrasyon === null
          ? await etiketApi.kalibrasyonOlustur(govde)
          : await etiketApi.kalibrasyonGuncelle(kalibrasyon.id, govde);
      snackbar.success("Kalibrasyon kaydedildi.");
      onKaydedildi(kayit);
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Kalibrasyon kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onKapat}
      title={kalibrasyon === null ? "Yeni yazıcı kalibrasyonu" : "Kalibrasyonu düzenle"}
      actions={
        <>
          <Button variant="text" onClick={onKapat} disabled={busy}>
            Vazgeç
          </Button>
          <Button onClick={() => void kaydet()} disabled={busy}>
            Kaydet
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-body-small text-on-surface-variant">Şablon: {sablon.name}</p>
        {hata && <ErrorBand hata={hata} />}
        <TextField
          label="Yazıcı adı"
          required
          value={yazici}
          maxLength={160}
          onChange={(e) => setYazici(e.target.value)}
          error={errors.printer_name}
          helperText="Masadaki yazıcıyı tanıyacağınız ad (ör. “Kütüphane lazer yazıcısı”)."
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Yatay kayma (mm)"
            inputMode="decimal"
            value={x}
            onChange={(e) => setX(e.target.value)}
            error={errors.offset_x}
            helperText="Artı sağa, eksi sola."
          />
          <TextField
            label="Dikey kayma (mm)"
            inputMode="decimal"
            value={y}
            onChange={(e) => setY(e.target.value)}
            error={errors.offset_y}
            helperText="Artı aşağı, eksi yukarı."
          />
        </div>
        <div className="space-y-2 rounded-shape-md bg-surface-container-low p-3">
          <p className="text-label-large text-on-surface">Cetvelde okuduğunuz değeri ekleyin</p>
          <p className="text-body-small text-on-surface-variant">
            Kalibrasyon sayfası bu yazıcının kaymasıyla basıldıysa cetvelde okuduğunuz değer
            yukarıdaki kaymaya eklenir. İlk ölçümde kayma sıfırdır.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <TextField
              className="w-40"
              label="Okunan yatay değer"
              inputMode="decimal"
              value={olcumX}
              onChange={(e) => setOlcumX(e.target.value)}
              error={errors.olcum_x}
            />
            <TextField
              className="w-40"
              label="Okunan dikey değer"
              inputMode="decimal"
              value={olcumY}
              onChange={(e) => setOlcumY(e.target.value)}
              error={errors.olcum_y}
            />
            <Button variant="tonal" icon="add" onClick={ekle}>
              Kaymaya ekle
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Şablon formu
// ---------------------------------------------------------------------------

interface OlcuAlani {
  ad: keyof EtiketSablonuGovdesi;
  etiket: string;
  yardim?: string;
}

const OLCU_ALANLARI: OlcuAlani[] = [
  { ad: "label_width", etiket: "Etiket genişliği (mm)" },
  { ad: "label_height", etiket: "Etiket yüksekliği (mm)" },
  {
    ad: "page_margin_top",
    etiket: "Üst kenar boşluğu (mm)",
    yardim: "Kâğıdın üst kenarından ilk satıra.",
  },
  {
    ad: "page_margin_left",
    etiket: "Sol kenar boşluğu (mm)",
    yardim: "Kâğıdın sol kenarından ilk sütuna.",
  },
  { ad: "gutter_x", etiket: "Sütun aralığı (mm)", yardim: "İki etiket arasındaki yatay boşluk." },
  { ad: "gutter_y", etiket: "Satır aralığı (mm)", yardim: "İki etiket arasındaki dikey boşluk." },
];

function SablonFormu({
  sablon,
  onKapat,
  onKaydedildi,
}: {
  sablon: EtiketSablonu | null;
  onKapat: () => void;
  onKaydedildi: () => void;
}) {
  const snackbar = useSnackbar();
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const [ad, setAd] = useState(sablon?.name ?? "");
  const [tur, setTur] = useState<SablonTuru>(sablon?.kind ?? "BARCODE");
  const [olculer, setOlculer] = useState<Record<string, string>>(() => {
    const ilk: Record<string, string> = {};
    for (const alan of OLCU_ALANLARI) {
      const deger = sablon ? (sablon[alan.ad as keyof EtiketSablonu] as number) : 0;
      ilk[alan.ad] = sablon ? sayiYazimi(deger) : "";
    }
    if (!sablon) {
      ilk.gutter_x = "0";
      ilk.gutter_y = "0";
    }
    return ilk;
  });
  const [satir, setSatir] = useState(sablon ? String(sablon.rows) : "");
  const [sutun, setSutun] = useState(sablon ? String(sablon.cols) : "");
  const [varsayilan, setVarsayilan] = useState(sablon?.is_default ?? false);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    if (!ad.trim()) {
      setFieldError("name", "Şablona bir ad verin.");
      return;
    }
    const sayilar: Record<string, number> = {};
    for (const alan of OLCU_ALANLARI) {
      const deger = ondalikOku(olculer[alan.ad] ?? "");
      if (deger === null || deger < 0) {
        setFieldError(alan.ad, "Milimetre olarak bir sayı yazın (ör. 38,1).");
        return;
      }
      sayilar[alan.ad] = Math.round(deger * 100) / 100;
    }
    const satirSayisi = Number(satir);
    const sutunSayisi = Number(sutun);
    if (!Number.isInteger(satirSayisi) || satirSayisi < 1) {
      setFieldError("rows", "Satır sayısı en az 1 olmalıdır.");
      return;
    }
    if (!Number.isInteger(sutunSayisi) || sutunSayisi < 1) {
      setFieldError("cols", "Sütun sayısı en az 1 olmalıdır.");
      return;
    }
    const govde: EtiketSablonuGovdesi = {
      name: ad.trim(),
      kind: tur,
      label_width: sayilar.label_width,
      label_height: sayilar.label_height,
      page_margin_top: sayilar.page_margin_top,
      page_margin_left: sayilar.page_margin_left,
      gutter_x: sayilar.gutter_x,
      gutter_y: sayilar.gutter_y,
      rows: satirSayisi,
      cols: sutunSayisi,
      is_default: varsayilan,
    };
    setBusy(true);
    try {
      if (sablon === null) await etiketApi.sablonOlustur(govde);
      else await etiketApi.sablonGuncelle(sablon.id, govde);
      snackbar.success("Şablon kaydedildi.");
      onKaydedildi();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Şablon kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onKapat}
      title={sablon === null ? "Yeni etiket şablonu" : "Şablonu düzenle"}
      actions={
        <>
          <Button variant="text" onClick={onKapat} disabled={busy}>
            Vazgeç
          </Button>
          <Button onClick={() => void kaydet()} disabled={busy}>
            Kaydet
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-small text-on-surface-variant">
          Ölçüleri tabaka kutusundaki üretici bilgisinden alın; yazıcının kaydırmasını buraya değil
          yazıcı kalibrasyonuna yazın.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            className="sm:col-span-2"
            label="Şablon adı"
            required
            value={ad}
            maxLength={120}
            onChange={(e) => setAd(e.target.value)}
            error={errors.name}
          />
          <Select
            label="Tür"
            value={tur}
            onChange={(e) => setTur(e.target.value as SablonTuru)}
            options={kodSecenekleri(SABLON_TURU_TR)}
            error={errors.kind}
            helperText="Seçicide hangi basım için önerileceğini belirler."
          />
          <label className="flex min-h-11 cursor-pointer items-center gap-2 self-end text-body-medium text-on-surface">
            <input
              type="checkbox"
              checked={varsayilan}
              onChange={(e) => setVarsayilan(e.target.checked)}
              className="size-5 shrink-0 accent-primary"
            />
            Bu türün varsayılan şablonu
          </label>
          <TextField
            label="Satır sayısı"
            required
            inputMode="numeric"
            value={satir}
            onChange={(e) => setSatir(e.target.value)}
            error={errors.rows}
          />
          <TextField
            label="Sütun sayısı"
            required
            inputMode="numeric"
            value={sutun}
            onChange={(e) => setSutun(e.target.value)}
            error={errors.cols}
          />
          {OLCU_ALANLARI.map((alan) => (
            <TextField
              key={alan.ad}
              label={alan.etiket}
              required={alan.ad === "label_width" || alan.ad === "label_height"}
              inputMode="decimal"
              value={olculer[alan.ad] ?? ""}
              onChange={(e) => setOlculer((onceki) => ({ ...onceki, [alan.ad]: e.target.value }))}
              error={errors[alan.ad]}
              helperText={alan.yardim}
            />
          ))}
        </div>
        {sablon !== null && (
          <p className="text-body-small text-on-surface-variant">
            Şu an: {formatNumber(sablon.labels_per_sheet)} etiket, {mm(sablon.label_width)} ×{" "}
            {mm(sablon.label_height)} mm.
          </p>
        )}
      </div>
    </Dialog>
  );
}
