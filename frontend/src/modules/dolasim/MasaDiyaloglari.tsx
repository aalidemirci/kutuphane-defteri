// Dolaşım masasının pencereleri ve kart okutma kilidi şeridi (tasarım §4.4):
//
//   * KartKilidiSeridi — geçersiz kart okutmalarından sonra (GA-7) kart okutmayı
//     yönetici parolasıyla sürdürür (görevli kipinden ÇIKMADAN). PENCERE DEĞİLDİR:
//     okutma kutusunun üstünde durur ve kutu açık kalır, çünkü iade kilitlenmez —
//     kilitliyken okutulan kitabın iadesi alınır (F6 düzeltme turu; önceki kipsel
//     pencere bütün okutmaları yutuyordu). Parola yalnız istek gövdesinde gider; şerit
//     kalkınca alan temizlenir. Parola alanı kendiliğinden odaklanmaz: odak okutma
//     kutusunda kalır, yönetici alana kendisi tıklar.
//   * IstisnaDiyalogu — YALNIZ yönetici kipi: gecikme engeline gerekçeli istisna
//     (kapalı listeden gerekçe + zorunlu açıklama; "Sağlık ya da aile bilgisi
//     yazmayın."). Pencere hangi kitap için açıldığını gösterir. Sayı sınırı ve ödünç
//     verilmeyen kaynaklar hiçbir kipte istisna almaz; bu pencere yalnız gecikme
//     reddinde açılır.
//   * KartsizOduncDiyalogu — YALNIZ yönetici kipi: okul no ya da adla üye bulunur,
//     kapalı listeden gerekçe seçilir; ödünç kaydı "kartsız" işaretini taşır (U12).
//
// İlk odak: ortak `ui/Dialog` açılışta odağı panele alır ve bu, çocuktaki `autoFocus`'tan
// SONRA olur. Arama alanı bu yüzden `ui/Dialog`un `initialFocusRef` özelliğiyle odaklanır.

import { useId, useRef, useState } from "react";
import type { FormEvent } from "react";

import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import { hataOku } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import {
  ISTISNA_ACIKLAMA_EN_COK,
  ISTISNA_GEREKCELERI,
  KARTSIZ_GEREKCELER,
  dolasimApi,
} from "./api";
import type { IstisnaGerekcesi, KartsizGerekce, KartSonucu, UyeAramaSatiri } from "./api";

/** Kart okutma kilidi (GA-7) şeridinin başlığı. */
export const KART_KILIDI_BASLIGI = "Kart okutma durduruldu";
export const KART_KILIDI_IADE_NOTU =
  "İade almak kilitlenmez: üye kartı okutmadan kitabın kütüphane etiketini okuttuğunuzda iadesi alınır.";
export const ISTISNA_BASLIGI = "Gerekçeli istisna";
export const ISTISNA_YARDIMI = "Sağlık ya da aile bilgisi yazmayın.";
export const KARTSIZ_BASLIGI = "Kartsız ödünç";

export function KartKilidiSeridi({
  ileti,
  onAcildi,
  onOdakIcinde,
}: {
  ileti: string;
  /** Kilit açıldı (parola doğru). */
  onAcildi: () => void;
  /** Odak şeridin içine girdi / çıktı (okutma kutusunun odak uyarısı için). */
  onOdakIcinde?: (icinde: boolean) => void;
}) {
  const formId = useId();
  const [parola, setParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setCalisiyor(true);
    try {
      await dolasimApi.kartKilidiniAc(parola);
      setParola("");
      onOdakIcinde?.(false);
      onAcildi();
    } catch (err) {
      setHata(hataOku(err, "Kart okutma açılamadı.").message);
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <section
      aria-label={KART_KILIDI_BASLIGI}
      className="space-y-3 rounded-shape-md border border-error/40 bg-error-container px-4 py-3 text-on-error-container"
      onFocus={() => onOdakIcinde?.(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onOdakIcinde?.(false);
      }}
    >
      <div className="flex items-start gap-3">
        <Icon name="lock" size="2xl" className="shrink-0" />
        <div className="min-w-0 space-y-1">
          <p className="text-title-medium">{KART_KILIDI_BASLIGI}</p>
          <p className="text-body-medium">{ileti}</p>
          <p className="text-body-medium">{KART_KILIDI_IADE_NOTU}</p>
        </div>
      </div>
      <form id={formId} onSubmit={gonder} className="flex flex-wrap items-start gap-2">
        <TextField
          className="min-w-[14rem] flex-1"
          label="Yönetici parolası"
          type="password"
          value={parola}
          onChange={(e) => setParola(e.target.value)}
          autoComplete="current-password"
          error={hata ?? undefined}
          required
        />
        <Button type="submit" className="mt-6" disabled={calisiyor || parola === ""}>
          {calisiyor ? "Denetleniyor…" : "Kart okutmayı aç"}
        </Button>
      </form>
    </section>
  );
}

export function IstisnaDiyalogu({
  open,
  ileti,
  kitap,
  onVazgec,
  onGonder,
}: {
  open: boolean;
  /** Sunucunun gecikme reddi iletisi. */
  ileti: string;
  /** İstisna istenen kitap: "2026-000302 — Eser adı" (ad okunamazsa yalnız barkod). */
  kitap: string;
  onVazgec: () => void;
  /** Gerekçeyle ödünç verir; hata dönerse diyalog açık kalır ve hatayı gösterir. */
  onGonder: (gerekce: IstisnaGerekcesi, aciklama: string) => Promise<string | null>;
}) {
  const formId = useId();
  const [gerekce, setGerekce] = useState("");
  const [aciklama, setAciklama] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  function kapat() {
    setGerekce("");
    setAciklama("");
    setHata(null);
    onVazgec();
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setCalisiyor(true);
    const sonuc = await onGonder(gerekce as IstisnaGerekcesi, aciklama.trim());
    setCalisiyor(false);
    if (sonuc) {
      setHata(sonuc);
      return;
    }
    setGerekce("");
    setAciklama("");
    setHata(null);
  }

  return (
    <Dialog
      open={open}
      onClose={kapat}
      title={ISTISNA_BASLIGI}
      actions={
        <>
          <Button variant="text" type="button" onClick={kapat}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            form={formId}
            disabled={calisiyor || gerekce === "" || aciklama.trim() === ""}
          >
            {calisiyor ? "Kaydediliyor…" : "Gerekçeyle ödünç ver"}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={gonder} className="flex flex-col gap-4">
        <p className="text-title-small text-on-surface">Kitap: {kitap}</p>
        <p>{ileti}</p>
        <p>
          Gerekçeli istisna yalnız gecikme engeline tanınır ve ödünç kaydına geçer. Ödünç sınırı ve
          ödünç verilmeyen kaynaklar için istisna yoktur.
        </p>
        <Select
          label="Gerekçe"
          required
          placeholder="Seçin"
          options={ISTISNA_GEREKCELERI.map((g) => ({ value: g.value, label: g.label }))}
          value={gerekce}
          onChange={(e) => setGerekce(e.target.value)}
        />
        <label className="flex flex-col gap-1.5">
          <span className="text-label-medium font-semibold text-on-surface-variant">
            Açıklama <span className="text-error">*</span>
          </span>
          <textarea
            className="min-h-24 rounded-shape-md border border-outline-variant bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            value={aciklama}
            maxLength={ISTISNA_ACIKLAMA_EN_COK}
            onChange={(e) => setAciklama(e.target.value)}
            aria-describedby={`${formId}-yardim`}
            required
          />
          <span id={`${formId}-yardim`} className="text-body-small text-on-surface-variant">
            {ISTISNA_YARDIMI}
          </span>
        </label>
        {hata && (
          <p role="alert" className="text-body-medium text-error">
            {hata}
          </p>
        )}
      </form>
    </Dialog>
  );
}

export function KartsizOduncDiyalogu({
  open,
  onVazgec,
  onAcildi,
}: {
  open: boolean;
  onVazgec: () => void;
  /** Üye bağlamı kartsız ödünç için açıldı. */
  onAcildi: (sonuc: KartSonucu, uyelikId: number, gerekce: KartsizGerekce) => void;
}) {
  const formId = useId();
  const aramaAlani = useRef<HTMLInputElement>(null);
  const [arama, setArama] = useState("");
  const [sonuclar, setSonuclar] = useState<UyeAramaSatiri[] | null>(null);
  const [secili, setSecili] = useState<number | null>(null);
  const [gerekce, setGerekce] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  function kapat() {
    setArama("");
    setSonuclar(null);
    setSecili(null);
    setGerekce("");
    setHata(null);
    onVazgec();
  }

  async function ara() {
    if (!arama.trim()) return;
    setHata(null);
    setCalisiyor(true);
    try {
      const sayfa = await dolasimApi.uyeAra(arama.trim());
      setSonuclar(sayfa.results);
      setSecili(sayfa.results.length === 1 ? sayfa.results[0].id : null);
    } catch (err) {
      setHata(hataOku(err, "Üye aranamadı.").message);
    } finally {
      setCalisiyor(false);
    }
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (secili === null || !gerekce) return;
    setHata(null);
    setCalisiyor(true);
    try {
      const sonuc = await dolasimApi.uyeAc(secili);
      onAcildi(sonuc, secili, gerekce as KartsizGerekce);
      setArama("");
      setSonuclar(null);
      setSecili(null);
      setGerekce("");
    } catch (err) {
      setHata(hataOku(err, "Üye açılamadı.").message);
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={kapat}
      title={KARTSIZ_BASLIGI}
      wide
      initialFocusRef={aramaAlani}
      actions={
        <>
          <Button variant="text" type="button" onClick={kapat}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            form={formId}
            disabled={calisiyor || secili === null || gerekce === ""}
          >
            Üyeyi aç
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={gonder} className="flex flex-col gap-4">
        <p>
          Kart yanında olmayan üyeye ödünç verirken üyeyi okul no ya da adıyla bulun ve gerekçe
          seçin. Ödünç kaydı “kartsız ödünç” olarak işaretlenir.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <TextField
            ref={aramaAlani}
            className="min-w-[16rem] flex-1"
            label="Okul no ya da ad"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void ara();
              }
            }}
          />
          <Button
            type="button"
            variant="tonal"
            icon="search"
            onClick={() => void ara()}
            disabled={calisiyor || !arama.trim()}
          >
            Ara
          </Button>
        </div>
        {sonuclar !== null &&
          (sonuclar.length === 0 ? (
            <p className="text-body-medium">Aktif üyeliği olan kişi bulunamadı.</p>
          ) : (
            <fieldset className="space-y-1">
              <legend className="mb-1 text-label-medium font-semibold text-on-surface-variant">
                Üye
              </legend>
              {sonuclar.map((s) => (
                <label
                  key={s.id}
                  className="flex min-h-11 cursor-pointer items-center gap-3 rounded-shape-sm px-2 hover:bg-on-surface/5"
                >
                  <input
                    type="radio"
                    name={`${formId}-uye`}
                    checked={secili === s.id}
                    onChange={() => setSecili(s.id)}
                    className="size-5 shrink-0 accent-primary"
                  />
                  <span className="min-w-0 flex-1 text-body-medium text-on-surface">
                    {s.full_name}
                    <span className="text-on-surface-variant">
                      {" · "}
                      {[s.member_type_display, s.class_label, s.student_number]
                        .filter(Boolean)
                        .join(" · ")}
                      {" · kalan hak "}
                      {formatNumber(s.remaining_quota)}
                    </span>
                  </span>
                </label>
              ))}
            </fieldset>
          ))}
        <Select
          label="Gerekçe"
          required
          placeholder="Seçin"
          options={KARTSIZ_GEREKCELER.map((g) => ({ value: g.value, label: g.label }))}
          value={gerekce}
          onChange={(e) => setGerekce(e.target.value)}
        />
        {hata && (
          <p role="alert" className="text-body-medium text-error">
            {hata}
          </p>
        )}
      </form>
    </Dialog>
  );
}
