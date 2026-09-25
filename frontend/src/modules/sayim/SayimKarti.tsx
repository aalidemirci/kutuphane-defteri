// Genel Bakış'ın "Sayım" kartı ve kilitli işlemlerin bantları (F9; tasarım §9-10).
//
// - **Sayım kartı**: canlı (taslak, süren ya da onay bekleyen) sayım varken görünür; durumu,
//   kişisiz ilerlemeyi ve SÜREN iki seçeneği ayrı satırlarda yazar, iadenin her zaman açık
//   olduğunu söyler.
// - **Durdurma bandı**: TMY 32/3 durdurması sürerken, kapsadığı işlemlerin ekranında (edinim,
//   hızlı kayıt, eser ayrıntısı, ayıklama, kayıp ve hasar) işlemin neden yapılamadığını
//   ÖNCEDEN söyler. Asıl kapı sunucudadır (`tmy_kapisi.ensure_open`); ret iletisi yine
//   gösterilir.
// - **Aktarım bandı** (F9 ekleri K4): programa aktarım durdurma süresince kapalıdır ama
//   TMY'ye dayandırılmaz — içe aktarmada ve "Mevcut koleksiyon (programa aktarım)" edinimiyle
//   Hızlı Kayıt'ta "Sayım sürüyor" bandı sunucunun iletisini yazar.
// - **Hizmet arası şeridi**: sayım için hizmet arası sürerken masada ve teslim ekranında (yeni
//   ödünç ve yeni teslim durur — madde 27). Masa durumu masa ucundan okunur; görevli kipinde
//   de açılışta çizilir (madde 26 — `dolasim/DolasimMasasi`).
//
// Durum `GET library/stocktakes/state/`'ten okunur (kişisiz; kullanıcı eylemi değildir —
// `X-KD-Etkinlik` gitmez). Okunamazsa hiçbir şey çizilmez.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatNumber } from "../../lib/format";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import {
  HIZMET_ARASI,
  PROGRAMA_AKTARIM_KAPALI,
  SAYIM_BASLIGI,
  TMY_DURDURMA_KAPSAMAZ,
  TMY_DURDURMA_KAPSAMI,
  TMY_DURDURMASI,
  sayimAdresi,
  sayimApi,
} from "./api";
import type { SayimDurumOzeti } from "./api";

/**
 * Hizmet arasının masadaki ve teslim ekranındaki iletisi — backend
 * `circulation.SERVICE_PAUSE_MESSAGE` ile BİREBİR (`test_on_yuz_sabitleri.py` sınar); görevli
 * kipinde de aynı cümle yazılır. Madde 27: yeni teslim de durur.
 */
export const HIZMET_ARASI_SURUYOR =
  "Sayım için hizmet arası — yeni ödünç ve teslim yapılamıyor. İade ve teslimden geri alma açık.";
export const IADE_ACIK = "İade her zaman açıktır.";
/** Aktarım bandının başlığı (K4 — TMY'ye dayanmaz). */
export const SAYIM_SURUYOR = "Sayım sürüyor";

const BAGLANTI =
  "inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";

/** Masa gün boyu açık kalır: yönetici kipinde durum bu aralıkla yeniden okunur (ms). */
export const DURUM_YENILEME_MS = 60_000;

/**
 * Sayımın kişisiz durumu (okunamazsa `null`). `yenilemeMs` verilirse durum o aralıkla yeniden
 * okunur (masa gün boyu açık kalır; hizmet arası kalkınca şerit de kalkmalı — F9 düzeltme turu).
 */
export function useSayimDurumu(etkin = true, yenilemeMs?: number): SayimDurumOzeti | null {
  const [durum, setDurum] = useState<SayimDurumOzeti | null>(null);
  useEffect(() => {
    if (!etkin) return;
    let iptal = false;
    const oku = () => {
      sayimApi
        .durum()
        .then((d) => {
          if (!iptal) setDurum(d);
        })
        .catch(() => undefined);
    };
    oku();
    const zamanlayici = yenilemeMs ? setInterval(oku, yenilemeMs) : null;
    return () => {
      iptal = true;
      if (zamanlayici !== null) clearInterval(zamanlayici);
    };
  }, [etkin, yenilemeMs]);
  return durum;
}

function kartMetni(canli: NonNullable<SayimDurumOzeti["live"]>): string {
  if (canli.status === "DRAFT") return "Sayım taslağı hazırlanıyor; henüz başlatılmadı.";
  if (canli.status === "COMPLETED")
    return "Sayım tamamlandı; harcama yetkilisinin onayı bekleniyor.";
  const ilerleme = `${formatNumber(canli.physical_found)} / ${formatNumber(
    canli.physical_expected,
  )} nüsha bulundu`;
  return canli.round === 2 ? `İkinci sayım sürüyor: ${ilerleme}.` : `Sayım sürüyor: ${ilerleme}.`;
}

export default function SayimKarti() {
  const durum = useSayimDurumu();
  const canli = durum?.live ?? null;
  if (durum === null || canli === null) return null;
  return (
    <section aria-labelledby="sayim-karti">
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-secondary-container text-on-secondary-container">
            <Icon name="inventory_2" />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id="sayim-karti" className="text-title-medium font-semibold text-on-surface">
              {SAYIM_BASLIGI}
            </h2>
            <p className="text-body-medium text-on-surface">{kartMetni(canli)}</p>
            {(durum.tmy_stop_active || durum.service_pause_active) && (
              <ul aria-label="Süren seçenekler" className="space-y-0.5 text-body-small">
                {durum.tmy_stop_active && (
                  <li className="text-on-surface">
                    <span className="font-semibold">{TMY_DURDURMASI}:</span>{" "}
                    {`${TMY_DURDURMA_KAPSAMI} yapılamaz.`}
                  </li>
                )}
                {durum.service_pause_active && (
                  <li className="text-on-surface">
                    <span className="font-semibold">{HIZMET_ARASI}:</span> yeni ödünç ve teslim
                    yapılamıyor.
                  </li>
                )}
              </ul>
            )}
            <p className="text-body-small text-on-surface-variant">{IADE_ACIK}</p>
            <Link to={sayimAdresi(canli.id)} className={BAGLANTI}>
              Sayım&apos;ı aç
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}

/**
 * TMY 32/3 durdurması sürerken işlemin ekranında bant. `islem` kullanıcı dilindedir
 * ("edinim ve yeni nüsha kaydı" gibi); durdurma yoksa hiçbir şey çizilmez.
 */
export function DurdurmaBandi({ islem }: { islem: string }) {
  const durum = useSayimDurumu();
  if (!durum?.tmy_stop_active) return null;
  return (
    <div
      role="status"
      aria-label={`${TMY_DURDURMASI} sürüyor`}
      className="flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-on-tertiary-container"
    >
      <Icon name="pause_circle" size="lg" className="mt-0.5 shrink-0" />
      <div className="min-w-0 space-y-0.5">
        <p className="text-label-large">{`${TMY_DURDURMASI} sürüyor`}</p>
        <p className="text-body-small">
          {`Sayım onaylanana ya da iptal edilene dek ${islem} yapılamaz (Taşınır Mal Yönetmeliği md. 32/3). ${TMY_DURDURMA_KAPSAMAZ}`}
        </p>
        {durum.live && (
          <Link to={sayimAdresi(durum.live.id)} className={BAGLANTI}>
            Sayım&apos;ı aç
          </Link>
        )}
      </div>
    </div>
  );
}

/**
 * TMY 32/3 durdurması sürerken programa aktarımın ekranında bant (K4): ileti TMY'ye DAYANMAZ,
 * sunucunun ret iletisiyle aynıdır. Durdurma yoksa hiçbir şey çizilmez.
 */
export function AktarimBandi() {
  const durum = useSayimDurumu();
  if (!durum?.tmy_stop_active) return null;
  return (
    <div
      role="status"
      aria-label={SAYIM_SURUYOR}
      className="flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-on-tertiary-container"
    >
      <Icon name="pause_circle" size="lg" className="mt-0.5 shrink-0" />
      <div className="min-w-0 space-y-0.5">
        <p className="text-label-large">{SAYIM_SURUYOR}</p>
        <p className="text-body-small">{PROGRAMA_AKTARIM_KAPALI}</p>
        {durum.live && (
          <Link to={sayimAdresi(durum.live.id)} className={BAGLANTI}>
            Sayım&apos;ı aç
          </Link>
        )}
      </div>
    </div>
  );
}

/**
 * Sayım için hizmet arası şeridi (ileti sunucununkiyle aynıdır). Masada altında iade ipucu
 * durur; teslim ekranında (`ipucu` verilmezse) yalnız ileti yazılır.
 */
export function HizmetArasiSeridi({
  ipucu = "Üye kartı okutmadan kitabın kütüphane etiketini okuttuğunuzda iadesi alınır.",
}: {
  ipucu?: string;
}) {
  return (
    <div
      role="status"
      aria-label={HIZMET_ARASI}
      className="flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-on-tertiary-container"
    >
      <Icon name="pause_circle" size="lg" className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p className="text-label-large">{HIZMET_ARASI_SURUYOR}</p>
        {ipucu && <p className="text-body-small">{ipucu}</p>}
      </div>
    </div>
  );
}
