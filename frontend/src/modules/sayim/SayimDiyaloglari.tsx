// Sayım pencereleri (F9): harcama yetkilisinin onayı, iptal ve sayım fazlası (etiketsiz kitap
// ekle · kayda alınacağı eser · kayda alınmayacak).
//
// Onay GERİ ALINMAZ ve tek işlemdir (TMY 10/1-e, 32/7, 27/1, 17): noksan nüshalar kayıttan
// düşülür, hasar dosyasında kayıttan düşme önerilen nüshalar düşülür, sayım fazlası kayda
// alınır; onayda her noksan yeniden denetlenir, durumu değişen düşülmez. Pencere başlığı
// sorudur ve ikinci doğrulama kutusu ister (sözlük §3). Harcama yetkilisinin onaylamadığı
// kalem gerekçesiyle işaretlenir ve kayıtta kalır.

import { useEffect, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatNumber, todayIso } from "../../lib/format";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import TextField from "../../ui/TextField";
import { OnayKutusu } from "../ayiklama/ortak";
import { kutuphaneApi } from "../kutuphane/api";
import type { Work } from "../kutuphane/api";
import { sayimApi } from "./api";
import type { OnayYaniti, SayimAyrintisi, SayimKalemi } from "./api";

export const ONAY_BASLIGI = "Sayım onaylansın mı?";
export const ONAY_DOGRULAMASI = "Harcama yetkilisinin imzaladığı sayım tutanağını denetledim.";
export const IPTAL_BASLIGI = "Sayım iptal edilsin mi?";
/**
 * Onaylanmama gerekçesinin yardımı: gerekçe sayım tutanağına ve Excel'e basılır; tutanağın
 * noksan sayfaları Varlık İşlem Fişine eklenip muhasebe birimine gider (TMY 10/1-g, 32/8).
 */
export const GEREKCE_YARDIMI = "Kişi adı yazmayın.";

/**
 * Onay uyarıları (F9 düzeltme turu; K1, K2 — 25.09.2026). Kayıtta kayıp görünen kitap sayım
 * tamamlandıktan sonra getirilmiş olabilir: okutma kapanmıştır ama kayıp dosyasında
 * “Bulundu” TMY 32/3 durdurması sürerken de seçilir (K1) — onaydan önce seçilirse onay kalemi
 * yeniden denetler ve düşmez. Onarımdaki nüsha kurulun seçimiyle kayda göre alınır (K2);
 * noksanda “Onarımda” görünen, sayım sırasında onarıma gönderilmiş kitaptır ve onarımcıda
 * olabilir — harcama yetkilisi “Onaylanmadı” ile kayıtta bırakabilir.
 */
export function kayipUyarisi(sayi: number): string {
  return `Noksanlardan ${formatNumber(sayi)} kitap kayıtta kayıp görünüyor. Kitap sayım tamamlandıktan sonra getirildiyse onaydan önce kayıp dosyasında “Bulundu”yu seçin; onayda kayıttan düşülmez.`;
}
export function onarimUyarisi(sayi: number): string {
  return `Noksanlardan ${formatNumber(sayi)} kitap sayım sırasında onarıma gönderilmiş. Kitap onarımcıdaysa “Onaylanmadı” ile işaretleyin; onaylanırsa kayıttan düşülür.`;
}
/** Listede kalemin altındaki kısa uyarı (tamamlanırken kayıttaki durum). */
const KALEM_UYARISI: Partial<Record<string, string>> = {
  LOST: "Kitap getirildiyse önce kayıp dosyasında “Bulundu”yu seçin.",
  IN_REPAIR: "Kitap onarımcıdaysa onaylamayın.",
};

// ---------------------------------------------------------------------------
// Harcama yetkilisinin onayı
// ---------------------------------------------------------------------------

interface Secili {
  kalem: SayimKalemi;
  gerekce: string;
}

/** Onaylanabilecek kalemler: noksan (32/7) ve hasar önerisi (27/1). */
function useOnayKalemleri(sayimId: number, arama: string) {
  const [kalemler, setKalemler] = useState<SayimKalemi[]>([]);
  const [toplam, setToplam] = useState(0);
  useEffect(() => {
    let iptal = false;
    Promise.all([
      sayimApi.kalemler(sayimId, { result: "MISSING", q: arama, limit: 200 }),
      sayimApi.kalemler(sayimId, { damage: true, q: arama, limit: 200 }),
    ])
      .then(([noksan, hasar]) => {
        if (iptal) return;
        const hepsi = [...noksan.results];
        for (const k of hasar.results) if (!hepsi.some((h) => h.id === k.id)) hepsi.push(k);
        setKalemler(hepsi);
        setToplam(noksan.count + hasar.count);
      })
      .catch(() => {
        if (!iptal) setKalemler([]);
      });
    return () => {
      iptal = true;
    };
  }, [sayimId, arama]);
  return { kalemler, toplam };
}

export function OnayDiyalogu({
  sayim,
  onClose,
  onOnaylandi,
}: {
  sayim: SayimAyrintisi;
  onClose: () => void;
  onOnaylandi: (sonuc: OnayYaniti) => void;
}) {
  const [ad, setAd] = useState("");
  const [tarih, setTarih] = useState(todayIso());
  const [arama, setArama] = useState("");
  const [secili, setSecili] = useState<Record<number, Secili>>({});
  const [denetlendi, setDenetlendi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const { kalemler, toplam } = useOnayKalemleri(sayim.id, arama);
  const ozet = sayim.summary;
  // Etiketi sayım sırasında bağlanan fazla kayda girmiştir; onay onu yeniden kayda almaz.
  const kaydaGirecek = Math.max(0, ozet.surplus - ozet.surplus_excluded - ozet.surplus_bound);
  const onaylanmayan = Object.values(secili);

  const onayla = async () => {
    clearErrors();
    setHata(null);
    if (!ad.trim()) {
      setFieldError("approved_by_name", "Harcama yetkilisinin adını yazın.");
      return;
    }
    if (onaylanmayan.some((s) => !s.gerekce.trim())) {
      setFieldError("not_approved", "Onaylanmayan her kalemin gerekçesini yazın.");
      return;
    }
    setBusy(true);
    try {
      const sonuc = await sayimApi.onayla(sayim.id, {
        approved_by_name: ad.trim(),
        approved_on: tarih,
        not_approved: Object.fromEntries(
          onaylanmayan.map((s) => [String(s.kalem.id), s.gerekce.trim()]),
        ),
      });
      onOnaylandi(sonuc);
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Onay işlenemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={ONAY_BASLIGI}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="approval" onClick={() => void onayla()} disabled={busy || !denetlendi}>
            {busy ? "İşleniyor…" : "Onayla"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-medium text-on-surface">
          {`${formatNumber(ozet.results.MISSING)} noksan nüsha kayıttan düşülür (Taşınır Mal Yönetmeliği md. 32/7)`}
          {ozet.damage_write_off > 0 &&
            `, hasar dosyasında kayıttan düşme önerilen ${formatNumber(ozet.damage_write_off)} nüsha kullanılamaz hâle gelen taşınır olarak düşülür (md. 27/1)`}
          {kaydaGirecek > 0 &&
            `, ${formatNumber(kaydaGirecek)} sayım fazlası “Sayım fazlası (kayda giriş)” edinimiyle kayda alınır (md. 17)`}
          . Onayda her noksan yeniden denetlenir: bu arada iade edilen ya da bulunan nüsha düşülmez.
          Seçilen durdurma ve hizmet arası kalkar. İşlem geri alınamaz.
        </p>
        {(ozet.missing_recorded_lost > 0 || ozet.missing_in_repair > 0) && (
          <div
            role="note"
            aria-label="Kayıtta kayıp ya da onarımda görünen noksanlar"
            className="space-y-1 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container"
          >
            {ozet.missing_recorded_lost > 0 && <p>{kayipUyarisi(ozet.missing_recorded_lost)}</p>}
            {ozet.missing_in_repair > 0 && <p>{onarimUyarisi(ozet.missing_in_repair)}</p>}
          </div>
        )}
        {ozet.surplus_unresolved > 0 && (
          <p
            role="alert"
            className="rounded-shape-sm bg-error-container px-3 py-2 text-body-small text-on-error-container"
          >
            {`${formatNumber(ozet.surplus_unresolved)} sayım fazlası kitabın kayda alınacağı eseri seçin ya da “Kayda alınmayacak” diye işaretleyin; onay ondan sonra işlenir.`}
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Harcama yetkilisinin adı"
            required
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            error={errors.approved_by_name}
            helperText="Kayıttan düşmeyi harcama yetkilisi onaylar (TMY md. 10/1-e). Şifreli saklanır."
          />
          <TextField
            label="Onay tarihi"
            required
            type="date"
            value={tarih}
            onChange={(e) => setTarih(e.target.value)}
            error={errors.approved_on}
            helperText="İmzalı tutanağın tarihi: sayımın tamamlandığı günden önce ve bugünden sonra olamaz."
          />
        </div>

        <section aria-label="Onaylanmayan kalemler" className="space-y-2">
          <p className="text-label-large text-on-surface">Onaylanmayan kalemler</p>
          <p className="text-body-small text-on-surface-variant">
            Harcama yetkilisinin onaylamadığı noksan ya da hasar önerisi kalemini işaretleyin ve
            gerekçesini yazın; kalem kayıttan düşülmez.
          </p>
          {errors.not_approved && (
            <p role="alert" className="text-body-small text-error">
              {errors.not_approved}
            </p>
          )}
          <TextField
            label="Ara"
            placeholder="Kaynak adı ya da barkod"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
          />
          {kalemler.length === 0 ? (
            <p className="text-body-small text-on-surface-variant">
              Onaylanacak noksan ya da hasar önerisi yok.
            </p>
          ) : (
            <ul className="max-h-72 space-y-2 overflow-y-auto scrollbar-thin">
              {kalemler.map((k) => {
                const s = secili[k.id];
                return (
                  <li
                    key={k.id}
                    className="rounded-shape-md border border-outline-variant/70 px-3 py-2"
                  >
                    <p className="text-body-medium text-on-surface">
                      <span className="font-mono">{k.barcode_display}</span> — {k.work_title}
                    </p>
                    <p className="text-body-small text-on-surface-variant">
                      {k.damage_write_off
                        ? "Hasar önerisi (TMY 27/1)"
                        : `Noksan (TMY 32/7) · kayda göre ${k.expected_status_display}`}
                    </p>
                    {!k.damage_write_off && KALEM_UYARISI[k.status_at_completion] && (
                      <p className="text-body-small text-tertiary">
                        {KALEM_UYARISI[k.status_at_completion]}
                      </p>
                    )}
                    <OnayKutusu
                      etiket="Onaylanmadı"
                      checked={s !== undefined}
                      onChange={(d) =>
                        setSecili((o) => {
                          const yeni = { ...o };
                          if (d) yeni[k.id] = { kalem: k, gerekce: "" };
                          else delete yeni[k.id];
                          return yeni;
                        })
                      }
                    />
                    {s && (
                      <TextField
                        label="Gerekçe"
                        helperText={GEREKCE_YARDIMI}
                        value={s.gerekce}
                        onChange={(e) =>
                          setSecili((o) => ({
                            ...o,
                            [k.id]: { kalem: k, gerekce: e.target.value },
                          }))
                        }
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {toplam > kalemler.length && (
            <p className="text-body-small text-on-surface-variant">
              Listede ilk kalemler var; aradığınız kalemi kaynak adı ya da barkodla arayın.
            </p>
          )}
        </section>

        <OnayKutusu etiket={ONAY_DOGRULAMASI} checked={denetlendi} onChange={setDenetlendi} />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// İptal
// ---------------------------------------------------------------------------

export function IptalDiyalogu({
  sayimId,
  onClose,
  onIptal,
}: {
  sayimId: number;
  onClose: () => void;
  onIptal: () => void;
}) {
  const [gerekce, setGerekce] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const iptalEt = async () => {
    setBusy(true);
    setHata(null);
    try {
      await sayimApi.iptalEt(sayimId, gerekce.trim());
      onIptal();
    } catch (e) {
      setHata(hataOku(e, "Sayım iptal edilemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={IPTAL_BASLIGI}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="cancel" onClick={() => void iptalEt()} disabled={busy}>
            {busy ? "İptal ediliyor…" : "İptal et"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-medium text-on-surface">
          Sayım “İptal edildi” olarak kapanır; seçilen durdurma ve hizmet arası kalkar, nüshalara
          dokunulmaz. Okutmalar iz olarak kalır. İptal geri alınmaz.
        </p>
        <TextField
          label="İptal gerekçesi (isteğe bağlı)"
          value={gerekce}
          onChange={(e) => setGerekce(e.target.value)}
        />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Sayım fazlası
// ---------------------------------------------------------------------------

export type FazlaKipi = "ekle" | "eser" | "haric";

const FAZLA_BASLIKLARI: Record<FazlaKipi, string> = {
  ekle: "Etiketsiz kitap ekle",
  eser: "Kayda alınacağı eser",
  haric: "Kayda alınmayacak kitap",
};

/** Sayım fazlasının penceresi: etiketsiz kitap ekle, kayda alınacağı eseri seç ya da hariç tut. */
export function FazlaDiyalogu({
  sayimId,
  kip,
  kalem,
  onClose,
  onKaydedildi,
}: {
  sayimId: number;
  kip: FazlaKipi;
  kalem: SayimKalemi | null;
  onClose: () => void;
  onKaydedildi: (ileti: string) => void;
}) {
  const [not, setNot] = useState(kalem?.surplus_note ?? "");
  const [eser, setEser] = useState<Work | null>(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    if ((kip === "ekle" || kip === "haric") && !not.trim()) {
      setFieldError(
        "note",
        kip === "ekle"
          ? "Kitabın adını ya da kısa bir açıklama yazın."
          : "Kayda alınmama gerekçesini yazın.",
      );
      return;
    }
    if (kip === "eser" && eser === null) {
      setFieldError("work", "Kitabın kayda alınacağı eseri seçin.");
      return;
    }
    setBusy(true);
    try {
      if (kip === "ekle") {
        await sayimApi.fazlaEkle(sayimId, { note: not.trim(), work: eser?.id ?? null });
        onKaydedildi("Sayım fazlası eklendi.");
      } else if (kip === "eser" && kalem) {
        await sayimApi.fazlaGuncelle(sayimId, kalem.id, {
          work: eser?.id ?? null,
          ...(not.trim() ? { note: not.trim() } : {}),
        });
        onKaydedildi("Kayda alınacağı eser seçildi.");
      } else if (kalem) {
        await sayimApi.fazlaGuncelle(sayimId, kalem.id, { excluded: true, note: not.trim() });
        onKaydedildi("Kitap “Kayda alınmayacak” diye işaretlendi.");
      }
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Sayım fazlası kaydedilemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={FAZLA_BASLIKLARI[kip]}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="save" onClick={() => void kaydet()} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-small text-on-surface-variant">
          {kip === "haric"
            ? "Kütüphaneye ait olmayan ya da kayıttan çıkmış (ör. imhayı bekleyen) kitap kayda alınmaz; gerekçesi sayım tutanağına yazılır."
            : "Sayım fazlası, onayda “Sayım fazlası (kayda giriş)” edinimiyle ve yeni numarayla kayda alınır (Taşınır Mal Yönetmeliği md. 17). Kitabın kaydı katalogda varsa o eseri seçin; yoksa önce Katalog'da eseri açın."}
        </p>
        {kip !== "haric" && (
          <Autocomplete<Work>
            label="Eser"
            required={kip === "eser"}
            placeholder="Kaynak adı ya da yazar"
            selected={eser}
            search={async (q) => (await kutuphaneApi.listWorks({ q, limit: 20 })).results}
            onSelect={setEser}
            onClear={() => setEser(null)}
            getLabel={(w) => w.title}
            getSublabel={(w) => w.authors}
            getKey={(w) => w.id}
            emptyText="Eser bulunamadı."
            error={errors.work}
            helperText={kip === "ekle" ? "İsteğe bağlı: onaydan önce de seçilebilir." : undefined}
          />
        )}
        <TextField
          label={kip === "haric" ? "Gerekçe" : "Açıklama"}
          required={kip !== "eser"}
          value={not}
          onChange={(e) => setNot(e.target.value)}
          error={errors.note}
          helperText={
            kip === "haric"
              ? "Kişi adı yazmayın."
              : "Kitabın adı ve bulunduğu yer. Kişi adı yazmayın."
          }
        />
      </div>
    </Dialog>
  );
}
