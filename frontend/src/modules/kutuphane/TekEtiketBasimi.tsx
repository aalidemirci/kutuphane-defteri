// Tek etiket kısayolu — Hızlı Kayıt'ta az önce açılan nüshanın etiketini hemen
// basmak için (tasarım §8.1 geçiş dönemi kuralı: etiketsiz kitap masaya gelirse
// hızlı kayıt yapılır ve TEK etiket basılır).
//
// Kısayol ayrı bir yol DEĞİLDİR: seçilen nüshalarla bir basım partisi açar ve
// Etiketler → Basım Kuyruğu ile aynı kuralları izler (PDF almak "basıldı"
// saymaz; "Basıldı olarak işaretle" onaylıdır ve geri alınabilir). Kısmen
// kullanılmış tabakada ilk boş hücre ızgaradan seçilir.
//
// Pencere (Dialog) değil sayfa içi karttır: PDF önizlemesi ve onay diyaloğu iç
// içe pencere açmasın.

import { useState } from "react";

import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import type { Copy } from "./api";
import { ETIKET_ICERIGI_TR, etiketApi } from "./etiketApi";
import type { BasimPartisi, EtiketIcerigi } from "./etiketApi";
import {
  BOS_BASIM_AYARI,
  BasimAyarlari,
  BasimPartisiKarti,
  basimAyariGovdesi,
  useEtiketSablonlari,
} from "./etiketOrtak";
import type { BasimAyari } from "./etiketOrtak";

export default function TekEtiketBasimi({
  nushalar,
  ilkIcerik,
  onKapat,
}: {
  nushalar: Copy[];
  ilkIcerik: EtiketIcerigi;
  onKapat: () => void;
}) {
  const { sablonlar, hata: sablonHatasi } = useEtiketSablonlari();
  const [icerik, setIcerik] = useState<EtiketIcerigi>(ilkIcerik);
  const [ayar, setAyar] = useState<BasimAyari>(BOS_BASIM_AYARI);
  const [parti, setParti] = useState<BasimPartisi | null>(null);
  // Onaylanan partinin içeriği: doğrulama iletisi yalnız barkod içeren partide
  // verilir (sırt etiketi barkod taşımaz, doğrulanamaz).
  const [onaylananIcerik, setOnaylananIcerik] = useState<EtiketIcerigi | null>(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const govde = basimAyariGovdesi(ayar, icerik);
  const barkodlar = nushalar.map((n) => n.barcode_display).join(", ");

  const hazirla = async () => {
    if (govde === null) return;
    setBusy(true);
    setHata(null);
    try {
      const yeni = await etiketApi.partiAc({
        kind: icerik,
        // Kayıt sırası: aynı künyeden açılan nüshalar açıldıkları sırayla basılır.
        order: "IMPORT_ROW",
        copies: nushalar.map((n) => n.id),
        ...govde,
      });
      setParti(yeni);
    } catch (e) {
      setHata(hataOku(e, "Basım partisi hazırlanamadı."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-title-medium text-on-surface">
          <Icon name="print" size="lg" className="text-primary" />
          Etiket Basımı
        </p>
        <Button
          variant="text"
          icon="close"
          onClick={onKapat}
          disabled={busy}
          aria-label="Etiket basımını kapat"
        >
          Kapat
        </Button>
      </div>
      <p className="text-body-medium text-on-surface">
        {formatNumber(nushalar.length)} nüsha: {barkodlar}
      </p>

      {sablonHatasi && <ErrorBand hata={sablonHatasi} />}
      {hata && <ErrorBand hata={hata} />}

      {onaylananIcerik !== null ? (
        <p
          role="status"
          className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-medium text-on-secondary-container"
        >
          <Icon name="check_circle" size="lg" className="mt-0.5 shrink-0" />
          {onaylananIcerik === "SPINE"
            ? "Sırt etiketi basıldı olarak işaretlendi."
            : "Etiket basıldı olarak işaretlendi. Kitaba yapıştırdıktan sonra Etiketler → Doğrulama Okutması'nda okutabilirsiniz."}
        </p>
      ) : parti ? (
        <BasimPartisiKarti
          parti={parti}
          sablon={sablonlar.find((s) => s.id === parti.template)}
          onDegisti={(guncel) => {
            setParti(null);
            if (guncel.status === "CONFIRMED") setOnaylananIcerik(guncel.kind);
          }}
        />
      ) : (
        <>
          <Select
            className="max-w-sm"
            label="Etiket içeriği"
            value={icerik}
            onChange={(e) => {
              setIcerik(e.target.value as EtiketIcerigi);
              // Şablon içeriğin varsayılanına döner (sırt ↔ barkod tabakası).
              setAyar((onceki) => ({ ...onceki, sablon: "", kalibrasyon: "", qr: false }));
            }}
            options={(Object.keys(ETIKET_ICERIGI_TR) as EtiketIcerigi[]).map((kod) => ({
              value: kod,
              label: ETIKET_ICERIGI_TR[kod],
            }))}
          />
          <BasimAyarlari
            icerik={icerik}
            sablonlar={sablonlar}
            ayar={ayar}
            onAyar={setAyar}
            adet={nushalar.length}
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button icon="print" onClick={() => void hazirla()} disabled={busy || govde === null}>
              {busy ? "Hazırlanıyor…" : "Basım partisini hazırla"}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
