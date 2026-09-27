// Kişi dökümü (KVKK md. 11) — Raporlar → Dökümler (F10 — D kolu; tasarım §8.4).
//
// İlgili kişinin başvurusuna cevap HAZIRLIĞIDIR: bir kişinin üyelik, ödünç, kayıp/hasar dosyası
// ve (personelde) teslim kayıtları tek PDF'te. Kişi okul no ile (kör indeksle TAM eşleşme —
// sunucuda) ya da adla bulunur; aynı okul numaralı birden çok kayıt (ayrılan öğrencinin numarası
// yeniden verilmiş olabilir) ayrı aday olarak listelenir ve döküm SEÇİLEN kişinin kaydıyla
// basılır. Okul no sorgu dizesine değil istek gövdesine yazılır. Yalnız yönetici kipinde.

import { useState } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import TextField from "../../ui/TextField";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { KISI_DOKUMU_ADI, dokumDosyaAdi, dokumlerApi } from "./api";
import type { KisiAdayi } from "./api";

export const KISI_DOKUMU_ACIKLAMASI =
  "6698 sayılı Kişisel Verilerin Korunması Kanunu md. 11'e göre herkes kendisiyle ilgili " +
  "kişisel veri işlenip işlenmediğini öğrenebilir ve bilgi isteyebilir; başvuru en geç otuz " +
  "gün içinde sonuçlandırılır (md. 13/2). Döküm, kişinin üyelik, ödünç, kayıp/hasar ve teslim " +
  "kayıtlarını tek belgede toplar; cevabı okul müdürlüğü verir. Belge kişisel veri içerir, yalnız " +
  "başvuru sahibine verilir.";
export const ADAY_YOK = "Bu bilgiyle eşleşen kişi bulunamadı.";

function AdaySatiri({ aday }: { aday: KisiAdayi }) {
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-body-medium font-semibold text-on-surface">{aday.full_name}</p>
          <p className="text-body-small text-on-surface-variant">
            {`${aday.detail} · ${aday.status_display}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() => dokumlerApi.kisiDokumu(aday.kind, aday.id)}
            dosyaAdi={() => dokumDosyaAdi(KISI_DOKUMU_ADI, "pdf")}
            onizlemeBasligi={KISI_DOKUMU_ADI}
            onHata={setHata}
          />
        </div>
      </div>
      {hata && <ErrorBand hata={hata} />}
    </li>
  );
}

export default function KisiDokumuKarti() {
  const [okulNo, setOkulNo] = useState("");
  const [ad, setAd] = useState("");
  const [adaylar, setAdaylar] = useState<KisiAdayi[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const ara = async () => {
    setBusy(true);
    setHata(null);
    try {
      const yanit = await dokumlerApi.kisiAra({ school_no: okulNo.trim(), name: ad.trim() });
      setAdaylar(yanit.results);
    } catch (e) {
      setAdaylar(null);
      setHata(hataOku(e, "Kişi aranamadı."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={0} className="shadow-elevation-1">
      <div className="space-y-3 border-b border-outline-variant/60 px-4 py-3">
        <div>
          <h2 className="text-title-medium font-semibold text-on-surface">Kişi Dökümü</h2>
          <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
            {KISI_DOKUMU_ACIKLAMASI}
          </p>
        </div>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void ara();
          }}
        >
          <TextField
            className="w-40"
            label="Okul no"
            inputMode="numeric"
            autoComplete="off"
            value={okulNo}
            onChange={(e) => setOkulNo(e.target.value)}
          />
          <TextField
            className="w-64"
            label="Ad soyad"
            autoComplete="off"
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            helperText="Personel için adı yazın."
          />
          <Button type="submit" icon="search" disabled={busy || (!okulNo.trim() && !ad.trim())}>
            {busy ? "Aranıyor…" : "Ara"}
          </Button>
        </form>
        {hata && <ErrorBand hata={hata} />}
      </div>
      {adaylar !== null &&
        (adaylar.length === 0 ? (
          <p className="px-4 py-3 text-body-medium text-on-surface-variant">{ADAY_YOK}</p>
        ) : (
          <ul className="divide-y divide-outline-variant/50" aria-label="Bulunan kişiler">
            {adaylar.map((a) => (
              <AdaySatiri key={`${a.kind}-${a.id}`} aday={a} />
            ))}
          </ul>
        ))}
    </Card>
  );
}
